"""Generate and exercise both opt-in successor applications with locked Maven inputs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
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


def smoke(project, domain):
    backend = project / 'backend'
    sources = {'browser/BrowserServer.java': server(domain), 'browser/RecoveryResponseGate.java': FILTER,
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
    logs = project / 'runtime'
    logs.mkdir()
    with database() as container:
        authenticated_database_ready(container, os.environ['ACP_TEST_DATABASE_PASSWORD'])
        lab = Lab(container, 'acp_cardinality', backend, backend / 'src/main/resources/db/migration',
                  logs, domain)
        try:
            lab.launch()
            lab.sql('BEGIN;' + lock() + ';'.join(seed_sql(domain)) + '; COMMIT;')
            frontend = (project / 'frontend/src/task-ui-model.ts').read_text()
            ui = json.loads(frontend.split('=', 1)[1].rsplit(' as const;', 1)[0])
            assert lab.http(ui['queryPath'], {'QUERY-TEXT': ''})[0] == 200
            payload = request_input('fixture-resource', 'cardinality-test', ui)
            result = lab.http(ui['actionPath'], payload)
            assert result[0] == 200
            assert lab.http(ui['actionPath'], payload) == result
            events = int(lab.sql('SELECT count(*) FROM acp_outbox'))
            assert events == (1 if domain == 'payment' else 3)
            history = lab.history()
            assert [entry['version'] for entry in history] == ['1', '2', '3', '10', '11']
            return {'queryHTTP': 200, 'actionHTTP': 200, 'replayHTTP': 200,
                    'businessEvents': events, 'flyway': history}
        finally:
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
        results[domain] = {'baseline': prior, 'successor': successor, 'runtime': smoke(project, domain)}
        print(domain, 'PASS', flush=True)
    report = {'scope': 'QUALIFICATION_ONLY', 'sourceCommit': subprocess.check_output(
              ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'candidate': candidate.descriptor(), 'applications': results}
    (root / 'results.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
