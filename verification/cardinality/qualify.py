"""Generate and exercise both opt-in successor applications with locked Maven inputs."""
import argparse
import json
import os
import secrets
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tooling')]
from engineering.cardinality.successor import CardinalityCandidate
from engineering.dependency_resolution.inputs import seed_maven
from engineering.dependency_resolution.qualify import SETTINGS
from engineering.generator_builds.runtime import database
from engineering.recovery.qualify import (
    FILTER, MIGRATOR, RUNTIME_PROBE, Lab, authenticated_database_ready, request_input, server,
)
from engineering.traceability.qualification import inputs
from filesystem_artifacts import FilesystemArtifactStore
from phase6_reference_tests import seed_sql
from verification.cardinality.integrated import exercise, lock


def compile_backend(project, domain):
    backend = project / 'backend'
    browser_source = server(domain)
    anchor = 'public class BrowserServer {'
    assert browser_source.count(anchor) == 1
    browser_source = browser_source.replace(anchor, anchor + """
 @org.springframework.context.annotation.Bean
 org.springframework.boot.flyway.autoconfigure.FlywayMigrationStrategy validateOnly() {
     return flyway -> flyway.validate();
 }
""")
    sources = {'browser/BrowserServer.java': browser_source, 'browser/RecoveryResponseGate.java': FILTER,
               'browser/RecoveryRuntimeProbe.java': RUNTIME_PROBE, 'recovery/MigrationProbe.java': MIGRATOR}
    for name, text in sources.items():
        path = backend / 'src/test/java/acp' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as stream:
            stream.write(text)
    with (project / 'compile.log').open('w') as stream:
        subprocess.run(['mvn', '-B', '-ntp', 'test-compile', 'dependency:build-classpath',
                        '-Dmdep.outputFile=target/recovery-classpath'], cwd=backend, stdout=stream,
                       stderr=subprocess.STDOUT, check=True, timeout=250)
    return backend


class RuntimeLab(Lab):
    """Run with runtime credentials only. Flyway runs in a separate process."""

    def application_argv(self, env=None):
        argv = super().application_argv(env)
        return [arg for arg in argv if not arg.startswith(('--spring.flyway.password=',
                                                           '--spring.datasource.password='))] + [
            '--spring.flyway.create-schemas=false']


def principal(lab, role):
    password = secrets.token_hex(32)
    lab.sql(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT PASSWORD '{password}';")
    return {'ACP_DATABASE_USER': role, 'ACP_DATABASE_PASSWORD': password}


def grant_runtime(lab, role, *, coordinated):
    identities = lab.data("""SELECT jsonb_agg(relname ORDER BY relname)
        FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relkind='r'
        AND relname NOT IN ('flyway_schema_history','acp_cardinality_participation')""")
    assert identities and all(name.replace('_', '').isalnum() for name in identities)
    tables = ','.join('"' + name + '"' for name in identities)
    lab.sql(f'GRANT USAGE ON SCHEMA {lab.schema} TO {role};'
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON {tables} TO {role};'
            f'GRANT SELECT ON flyway_schema_history TO {role};'
            f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA {lab.schema} TO {role};')
    if coordinated:
        lab.sql(f'GRANT EXECUTE ON FUNCTION acp_cardinality_enter(bytea) TO {role};')


def fence(lab, role, group):
    lab.sql(f'ALTER ROLE {role} NOLOGIN; REVOKE {group} FROM {role};')
    assert lab.sql(f"SELECT count(*) FROM pg_auth_members WHERE member='{role}'::regrole;") == '0'
    assert lab.sql(f"SELECT count(*) FROM pg_tables WHERE schemaname='{lab.schema}' "
                   f"AND (has_table_privilege('{role}',format('%I.%I',schemaname,tablename),'INSERT') "
                   f"OR has_table_privilege('{role}',format('%I.%I',schemaname,tablename),'UPDATE') "
                   f"OR has_table_privilege('{role}',format('%I.%I',schemaname,tablename),'DELETE'));") == '0'


def measure(lab, ui, resource, key):
    before = time.monotonic_ns()
    query = lab.http(ui['queryPath'], {'QUERY-TEXT': ''})
    queried = time.monotonic_ns()
    payload = request_input(resource, key, ui)
    started_action = time.monotonic_ns()
    action = lab.http(ui['actionPath'], payload)
    end = time.monotonic_ns()
    assert query[0] == action[0] == 200
    assert lab.http(ui['actionPath'], payload) == action
    return {'queryNs': queried - before, 'actionNs': end - started_action}


def smoke(project, old_project, domain):
    backend = compile_backend(project, domain)
    old_backend = compile_backend(old_project, domain)
    logs = project / 'runtime'
    logs.mkdir()
    with database() as container:
        authenticated_database_ready(container, os.environ['ACP_TEST_DATABASE_PASSWORD'])
        schema = 'acp_cardinality'
        lab = Lab(container, schema, backend, backend / 'src/main/resources/db/migration', logs, domain)
        old_logs = old_project / 'runtime'
        old_logs.mkdir()
        old = RuntimeLab(container, schema, old_backend, old_backend / 'src/main/resources/db/migration',
                         old_logs, domain)
        new_logs = project / 'cutover-runtime'
        new_logs.mkdir()
        new = RuntimeLab(container, schema, backend, lab.migrations, new_logs, domain)
        try:
            migration_identity = principal(lab, 'acp_migration')
            old_identity = principal(lab, 'acp_retired')
            new_identity = principal(lab, 'acp_writer')
            lab.sql(f'CREATE SCHEMA {schema} AUTHORIZATION acp_migration; CREATE ROLE acp_old_grants NOLOGIN;')
            lab.env.update(migration_identity)
            old.env.update(migration_identity)
            old.migration('migrate')
            historical = lab.history()
            grant_runtime(lab, 'acp_old_grants', coordinated=False)
            lab.sql('GRANT acp_old_grants TO acp_retired WITH INHERIT TRUE;')
            old.env.update(old_identity, SPRING_FLYWAY_PASSWORD=old_identity['ACP_DATABASE_PASSWORD'])
            seed = seed_sql(domain)
            seed += [sql.replace("'fixture-resource'", "'old-resource'") for sql in seed[2:]]
            lab.sql('BEGIN;' + ';'.join(seed) + '; COMMIT;')
            old.launch()
            assert int(lab.sql("SELECT count(*) FROM pg_stat_activity WHERE usename='acp_retired';")) > 0
            old_ui = json.loads((old_project / 'frontend/src/task-ui-model.ts').read_text().split('=', 1)[1].rsplit(' as const;', 1)[0])
            baseline_timing = measure(old, old_ui, 'old-resource', 'before-cutover')
            before = lab.state()
            fence(lab, 'acp_retired', 'acp_old_grants')
            assert old.http(old_ui['actionPath'], request_input('fixture-resource', 'retired', old_ui))[0] != 200
            assert lab.state() == before
            old.close()
            assert lab.sql("SELECT count(*) FROM pg_stat_activity WHERE usename='acp_retired';") == '0'
            lab.migration('migrate')
            lab.migration('validate')
            assert lab.history()[:len(historical)] == historical
            assert lab.state() == before
            grant_runtime(lab, 'acp_writer', coordinated=True)
            new.env.update(new_identity, SPRING_FLYWAY_PASSWORD=new_identity['ACP_DATABASE_PASSWORD'])
            new.launch()
            assert int(lab.sql("SELECT count(*) FROM pg_stat_activity WHERE usename='acp_writer';")) > 0
            frontend = (project / 'frontend/src/task-ui-model.ts').read_text()
            ui = json.loads(frontend.split('=', 1)[1].rsplit(' as const;', 1)[0])
            corrected_timing = measure(new, ui, 'fixture-resource', 'after-cutover')
            events = int(lab.sql('SELECT count(*) FROM acp_outbox'))
            assert events == (2 if domain == 'payment' else 6)
            history = lab.history()
            assert [entry['version'] for entry in history] == ['1', '2', '3', '10', '11']
            return {'queryHTTP': 200, 'actionHTTP': 200, 'replayHTTP': 200,
                    'businessEvents': events, 'flyway': history, 'retiredPooledWriterRejected': True,
                    'historicalFlywayChecksumsPreserved': True, 'separateMigrationOwner': True,
                    'singleSampleSmokeTiming': {'baseline': baseline_timing, 'corrected': corrected_timing}}
        finally:
            new.close()
            old.close()
            lab.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--maven-seed', required=True, type=Path)
    args = parser.parse_args()
    root = args.workspace.resolve()
    root.mkdir(mode=0o700, exist_ok=False)
    reference = json.loads((ROOT / 'engineering/dependency_resolution/maven-artifacts.lock.json').read_bytes())
    repo = root / 'verified-m2'
    seed_maven(args.maven_seed, repo, reference, online=False)
    settings = root / 'offline-settings.xml'
    settings.write_bytes(SETTINGS)
    os.environ['MAVEN_ARGS'] = f'-o -s {settings} -gs {settings} -Dmaven.repo.local={repo}'
    results = {}
    for index, domain in enumerate(('payment', 'case-management')):
        _, snapshot, request, baseline = inputs(domain)
        candidate = CardinalityCandidate()
        request = SimpleNamespace(**(vars(request) | {'generator': candidate.generator}))
        plan = candidate.plan(snapshot, request)
        project = root / domain
        FilesystemArtifactStore(project).apply(plan)
        for artifact in baseline.artifacts:
            if artifact.path.startswith(('database/', 'backend/src/main/resources/db/migration/')):
                assert (project / artifact.path).read_bytes() == artifact.content.read()['text'].encode()
        candidate.verify_materialized(project, plan, snapshot, request)
        with database() as container:
            authenticated_database_ready(container, os.environ['ACP_TEST_DATABASE_PASSWORD'])
            prior = exercise(container, f'baseline_{index}', project, domain, False)
            successor = exercise(container, f'successor_{index}', project, domain, True)
        old_project = root / (domain + '-old')
        FilesystemArtifactStore(old_project).apply(baseline)
        results[domain] = {'baseline': prior, 'successor': successor,
                           'runtime': smoke(project, old_project, domain)}
        print(domain, 'PASS', flush=True)
    report = {'scope': 'QUALIFICATION_ONLY', 'sourceCommit': subprocess.check_output(
              ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'candidate': candidate.descriptor(), 'applications': results}
    (root / 'results.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
