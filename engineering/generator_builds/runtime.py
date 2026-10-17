"""Unsealed candidate runtime regression against newly created disposable databases."""
import argparse
from contextlib import contextmanager
import json
import hashlib
import os
from pathlib import Path
import secrets
import signal
import shutil
import socket
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tooling'), str(ROOT / 'tooling/tests')]
from engineering.generator_builds.qualify import sha, run
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
from canonical_json import load
from compiler_contracts import Document, Owner
from compiler_core import _ownership
from filesystem_artifacts import FilesystemArtifactStore
import check_task_interface as browser_gate
from tooling.integration import oidc

IMAGE = 'postgres@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336'


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True, timeout=120).strip()


@contextmanager
def database():
    name = 'acp-06-runtime-' + secrets.token_hex(8)
    password = secrets.token_hex(24)
    created = False
    previous = {key: os.environ.get(key) for key in ('ACP_TEST_DATABASE_URL', 'ACP_TEST_DATABASE_USER', 'ACP_TEST_DATABASE_PASSWORD')}
    try:
        docker('run', '--pull=never', '--detach', '--rm', '--name', name,
               '--publish', '127.0.0.1::5432', '--tmpfs', '/var/lib/postgresql',
               '--env', 'POSTGRES_USER=acp_runtime', '--env', 'POSTGRES_DB=acp_runtime',
               '--env', 'POSTGRES_PASSWORD=' + password, IMAGE, '-c', 'track_commit_timestamp=on')
        created = True
        port = docker('port', name, '5432/tcp').removeprefix('127.0.0.1:')
        for _ in range(120):
            result = subprocess.run(['docker', 'exec', name, 'pg_isready', '-U', 'acp_runtime', '-d', 'acp_runtime'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            if result.returncode == 0:
                break
            time.sleep(.5)
        else:
            raise RuntimeError('DISPOSABLE_POSTGRES_TIMEOUT')
        os.environ.update(ACP_TEST_DATABASE_URL='jdbc:postgresql://127.0.0.1:' + port + '/acp_runtime',
                          ACP_TEST_DATABASE_USER='acp_runtime', ACP_TEST_DATABASE_PASSWORD=password)
        yield name
    finally:
        for key, value in previous.items():
            if value is None: os.environ.pop(key, None)
            else: os.environ[key] = value
        if created:
            docker('rm', '--force', name)
            if name in docker('ps', '--all', '--format', '{{.Names}}').splitlines():
                raise RuntimeError('DISPOSABLE_DATABASE_NOT_REMOVED')


def verify_report(report, expected):
    stats = report['stats']
    if stats['expected'] != expected or any(stats[key] for key in ('unexpected', 'flaky', 'skipped')):
        raise ValueError('RUNTIME_TEST_FAILURE_OR_SKIP')


@contextmanager
def supervised_processes():
    original = subprocess.Popen
    children = []
    def launch(*args, **kwargs):
        kwargs['start_new_session'] = True
        process = original(*args, **kwargs)
        children.append(process)
        return process
    subprocess.Popen = launch
    try:
        yield
    finally:
        subprocess.Popen = original
        for process in reversed(children):
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=10)
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass


def runtime(workspace):
    with supervised_processes():
        return execute_runtime(workspace)


def execute_runtime(workspace):
    workspace = Path(workspace).resolve()
    workspace.mkdir(mode=0o700, exist_ok=False)
    # Existing browser fixture uses fixed loopback ports; fail before starting if occupied.
    for port in (18080, 18081, 4173, 4174):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
    run(['node', '-e', 'if(process.versions.node!=="24.21.0")process.exit(1)'], workspace)
    candidate = SuccessorCandidate()
    result = {'candidate': candidate.descriptor(), 'image': IMAGE, 'applications': {},
              'scope': 'NEW_DISPOSABLE_LAB_RUNTIME_ONLY', 'deploymentAcceptance': 'NOT_GRANTED'}
    original_tests = browser_gate.tests
    try:
        for domain in ('payment', 'case-management'):
            snapshot = Document.of(load(ROOT / f'test-corpus/deterministic-v04/{domain}-canonical-candidate.json'))
            request = SimpleNamespace(compiler='compiler/runtime-test', pipeline='pipeline/runtime-test',
                                      snapshot_digest=snapshot.read()['contentDigest'], features=(), generator=candidate.generator)
            plan = candidate.plan(snapshot, request)
            project = workspace / domain
            store = FilesystemArtifactStore(project)
            store.apply(plan)
            # The test identity adapter is an explicit disposable extension handoff,
            # never a manual edit concealed under COMPILER_OWNED provenance.
            identity_path = 'frontend/src/extensions/identity.ts'
            store.adopt_human(identity_path)
            inventory = store.inventory()
            plan = _ownership(candidate.plan(snapshot, request, inventory=inventory), inventory)
            if identity_path in {artifact.path for artifact in plan.artifacts}:
                raise ValueError('TEST_EXTENSION_NOT_HANDED_OFF')
            store.apply(plan)
            candidate.verify_materialized(project, plan, snapshot, request)
            owned = {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob('*') if p.is_file()}
            logs = workspace / (domain + '-runtime'); logs.mkdir()
            run(['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], project / 'frontend')
            if os.environ.get('CI') == 'true':
                run(['npx', '--no-install', 'playwright', 'install', '--with-deps', 'chromium'], project / 'frontend')
            with database() as container:
                browser_gate.tests = lambda current: original_tests(current) + extra_tests(current)
                report = browser_gate.browser(project, domain, logs)
                verify_report(report, 14)
                # Real RS256/JWKS/PKCE fixture, never an operational issuer.
                # Existing adapter runs both domains; isolate this domain with its normal name.
                oidc_report = run_oidc(project, domain, logs)
                verify_report(oidc_report, 2)
                schema = 'acp_browser_' + domain.replace('-', '_')
                migration = docker('exec', container, 'psql', '-U', 'acp_runtime', '-d', 'acp_runtime', '-Atc',
                                   "SELECT string_agg(version, ',' ORDER BY installed_rank) FROM " + schema + ".flyway_schema_history WHERE success AND type='SQL';")
                expected = [p.name.split('__')[0][1:] for p in sorted((project / 'backend/src/main/resources/db/migration').glob('V*__*.sql'))]
                if not expected or migration.split(',') != expected: raise ValueError('MIGRATIONS_NOT_APPLIED')
                version = docker('exec', container, 'psql', '-U', 'acp_runtime', '-d', 'acp_runtime', '-Atc', 'SHOW server_version;')
            # Only the explicitly handed-off test identity extension may be replaced in this laboratory build.
            for relative, content in owned.items():
                if relative == 'frontend/src/extensions/identity.ts':
                    (project / relative).write_bytes(content)
                elif (project / relative).read_bytes() != content:
                    raise ValueError('RUNTIME_MODIFIED_GENERATED_SOURCE:' + relative)
            retained = workspace / (domain + '-runtime-outputs'); retained.mkdir()
            for relative in ('backend/target', 'frontend/node_modules', 'frontend/dist'):
                path = project / relative
                if path.exists(): path.rename(retained / relative.replace('/', '-'))
            for path in sorted(project.rglob('*')):
                if path.is_file() and path.relative_to(project).as_posix() not in owned:
                    destination = retained / path.relative_to(project)
                    destination.parent.mkdir(parents=True, exist_ok=True); path.rename(destination)
            candidate.verify_materialized(project, plan, snapshot, request)
            if next(item for item in store.inventory() if item.path == identity_path).owner != Owner.HUMAN:
                raise ValueError('TEST_EXTENSION_OWNERSHIP')
            result['applications'][domain] = {'browserTests': 14, 'oidcTests': 2, 'postgres': version,
                'successfulMigrations': migration.split(','), 'health': 'UP', 'provenance': 'VERIFIED',
                'databaseCleanup': 'REMOVED', 'snapshot': snapshot.read()['contentDigest'],
                'testExtensionOwnership': str(Owner.HUMAN),
                'testIdentityFixtureSHA256': hashlib.sha256(browser_gate.IDENTITY.encode()).hexdigest(),
                'oidcAdapterSHA256': sha(ROOT / 'fixtures/deployment-oidc/identity.ts'),
                'sourceHashes': {name: sha(project / name) for name in owned}}
    finally:
        browser_gate.tests = original_tests
    (workspace / 'runtime-results.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    return result


def extra_tests(domain):
    port = 18080 if domain == 'payment' else 18081
    return '''
test('health and malformed or unauthenticated API requests fail safely',async({page})=>{
 const health=await page.request.get('http://127.0.0.1:PORT/actuator/health');
 expect(health.status()).toBe(200);expect((await health.json()).status).toBe('UP');
 expect((await page.request.post(ui.queryPath,{data:{'QUERY-TEXT':''}})).status()).toBe(401);
 expect((await page.request.post(ui.queryPath,{headers:{Authorization:'Bearer invalid'},data:{'QUERY-TEXT':''}})).status()).toBe(401);
 const malformed=await page.request.post(ui.queryPath,{headers,data:{'QUERY-TEXT':123}});
 // Frozen acp-failure-mapping 1.1.0 maps HttpMessageNotReadableException to 422.
 expect(malformed.status()).toBe(422);expect(await malformed.json()).toEqual({code:'VALIDATION_FAILED',category:'INTERNAL',retryable:false});
});
'''.replace('PORT', str(port))


def run_oidc(project, domain, logs):
    import tempfile
    with tempfile.TemporaryDirectory(prefix='acp-06-oidc-') as temporary:
        issuer = oidc.Issuer(Path(temporary))
        names = ('tests', 'IDENTITY', 'server_source')
        saved = {name: getattr(browser_gate, name) for name in names}
        original_popen = subprocess.Popen
        try:
            token = issuer.token()
            browser_gate.tests = lambda current: oidc.spec(issuer.url, token)
            browser_gate.IDENTITY = (ROOT / 'fixtures/deployment-oidc/identity.ts').read_text() + '''\nimport {ui} from '../task-ui-model';
configure({issuer:ISSUER,clientId:'acp-disposable',redirectUri:location.origin+'/',scopes:['openid'],developmentLoopback:true,hints:claims=>({actor:ui.boundary.data.actor.id,subject:String(claims.sub),tenant:String(claims.tenant),permissions:new Set(ui.boundary.data.permissions.map(p=>p.id))})});
void callback().catch(()=>clearIdentity());
Object.assign(window,{integrationLogin:login,integrationLogout:clearIdentity});
'''.replace('ISSUER', json.dumps(issuer.url))
            def server(current):
                source = saved['server_source'](current)
                start = source.index(' @Bean JwtDecoder decoder()')
                end = source.index(' @RestController', start)
                return (source[:start] + source[end:]).replace('decoder.decode("browser-authorized")', 'decoder.decode(' + json.dumps(token) + ')')
            browser_gate.server_source = server
            def popen(args, *a, **kw):
                if isinstance(args, list) and 'acp.browser.BrowserServer' in args:
                    args = args + ['--spring.security.oauth2.resourceserver.jwt.issuer-uri=' + issuer.url,
                                   '--spring.security.oauth2.resourceserver.jwt.audiences=acp-disposable']
                return original_popen(args, *a, **kw)
            subprocess.Popen = popen
            output = logs / 'oidc'; output.mkdir()
            return browser_gate.browser(project, domain, output)
        finally:
            subprocess.Popen = original_popen
            for name, value in saved.items(): setattr(browser_gate, name, value)
            issuer.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--workspace', required=True)
    runtime(parser.parse_args().workspace)
