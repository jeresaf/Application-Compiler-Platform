"""Compile unsealed successor artifacts; no application startup or database access."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tooling')]
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
from canonical_json import load
from compiler_contracts import Document
from filesystem_artifacts import FilesystemArtifactStore


def sha(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('SOURCE_BINDING')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, cwd):
    subprocess.run(argv, cwd=cwd, check=True, timeout=900)


def reject_substituted_source(path, command, cwd):
    original = path.read_bytes()
    try:
        path.write_bytes(original + b'\nACP deliberately invalid generated source !!!\n')
        try:
            run(command, cwd)
        except subprocess.CalledProcessError:
            return
        raise ValueError('BUILD_DID_NOT_CONSUME_SOURCE')
    finally:
        path.write_bytes(original)


def qualify(workspace):
    workspace = Path(workspace).resolve()
    workspace.mkdir(mode=0o700, exist_ok=False)
    run(['node', '-e', 'if(process.versions.node!=="24.21.0")process.exit(1)'], workspace)
    candidate = SuccessorCandidate()
    results = {'candidate': candidate.descriptor(), 'applications': {},
               'toolchains': {name: subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)
                              for name, command in {'java': ['java', '-version'], 'maven': ['mvn', '-version'],
                                                    'node': ['node', '--version'], 'npm': ['npm', '--version']}.items()}}
    if 'version "21' not in results['toolchains']['java']:
        raise ValueError('JAVA_VERSION')
    for domain in ('payment', 'case-management'):
        snapshot = Document.of(load(ROOT / f'test-corpus/deterministic-v04/{domain}-canonical-candidate.json'))
        request = SimpleNamespace(compiler='compiler/build-integration', pipeline='pipeline/build-integration',
                                  snapshot_digest=snapshot.read()['contentDigest'], features=(), generator=candidate.generator)
        plan = candidate.plan(snapshot, request)
        if plan != candidate.plan(snapshot, request):
            raise ValueError('NONREPRODUCIBLE_PLAN')
        root = workspace / domain
        FilesystemArtifactStore(root).apply(plan)
        candidate.verify_materialized(root, plan, snapshot, request)
        sources = {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}
        run(['mvn', '-B', '-ntp', 'clean', 'test-compile'], root / 'backend')
        reject_substituted_source(root / 'backend/src/main/java/acp/Application.java',
                                  ['mvn', '-B', '-ntp', 'clean', 'test-compile'], root / 'backend')
        run(['mvn', '-B', '-ntp', 'clean', 'test-compile'], root / 'backend')
        classes = list((root / 'backend/target/classes').rglob('*.class'))
        if not classes:
            raise ValueError('NO_COMPILED_GENERATED_CLASSES')
        run(['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund'], root / 'frontend')
        run(['npm', 'run', 'typecheck'], root / 'frontend')
        reject_substituted_source(root / 'frontend/src/main.ts',
                                  ['npm', 'run', 'build'], root / 'frontend')
        run(['npm', 'run', 'build'], root / 'frontend')
        if not (root / 'frontend/dist/index.html').is_file() or not list((root / 'frontend/dist/assets').glob('*.js')):
            raise ValueError('NO_GENERATED_FRONTEND_BUILD')
        if any(sha(root / name) != digest for name, digest in sources.items()):
            raise ValueError('BUILD_MODIFIED_GENERATED_SOURCE')
        outputs = workspace / (domain + '-build-outputs')
        outputs.mkdir()
        compiled = {p.relative_to(root).as_posix(): sha(p) for p in classes}
        frontend = {p.relative_to(root).as_posix(): sha(p) for p in (root / 'frontend/dist').rglob('*') if p.is_file()}
        # Remove only declared build scopes from the owned source tree by retaining
        # them separately, then revalidate every source and ownership record.
        for relative in ('backend/target', 'frontend/node_modules', 'frontend/dist'):
            (root / relative).rename(outputs / relative.replace('/', '-'))
        candidate.verify_materialized(root, plan, snapshot, request)
        results['applications'][domain] = {'backend': 'COMPILED', 'frontend': 'BUILT', 'sourceConsumptionProbes': 'REJECTED_THEN_REBUILT',
            'snapshot': snapshot.read()['contentDigest'], 'sources': sources,
            'classes': compiled,
            'frontendOutputs': frontend}
    (workspace / 'results.json').write_text(json.dumps(results, sort_keys=True, indent=2) + '\n')
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    qualify(parser.parse_args().workspace)
