"""H1 qualification using the existing real R7 executor, not a replacement test suite."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import types

from engineering.jobs import run as jobs
from engineering.hardening import application
from engineering.hardening.assessment import verify_realms, reassess
from engineering.hardening.target import source_digest
from engineering.source_intelligence.model import require, sha


@contextmanager
def observed_offline_maven():
    previous = os.environ.get('MAVEN_ARGS')
    os.environ['MAVEN_ARGS'] = '-o -X'
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop('MAVEN_ARGS', None)
        else:
            os.environ['MAVEN_ARGS'] = previous


def qualify(workspace, *, maven_seed=None, npm_seed=None, browser_seed=None, offline=False):
    # This private host binding changes the candidate, not a result or assertion.
    # Every original browser, worker, DB, restart, ownership and Phase 8 check runs.
    function = types.FunctionType(jobs.qualify.__code__,
        {**vars(jobs), 'target': application, 'offline_maven': observed_offline_maven},
        'h1_qualification')
    function.__kwdefaults__ = jobs.qualify.__kwdefaults__
    files = {p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}
    result = function(workspace, maven_seed=maven_seed, npm_seed=npm_seed,
                      browser_seed=browser_seed, offline=offline)
    workspace = Path(workspace).absolute()
    repo = workspace.parent/(workspace.name+'-inputs')/'m2'
    realms = {}
    for phase in ('r0-build', 'r1-build'):
        log = workspace/phase/'production-backend.log'
        realms[phase] = verify_realms(log.read_text(), repo)
    security = reassess(workspace/'h1-osv')
    require(files == {p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')},
            'H1_EXECUTOR_CHANGED')
    record = {'scope': 'QUALIFICATION_ONLY', 'sourceCommit': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], text=True).strip(), 'sourceSHA256': files,
        'generatorSourceDigest': source_digest(), 'application': result,
        'pluginRealms': realms, 'specificSecurityAssessment': security,
        'otherFindings': 'OPEN_NOT_SUPPRESSED', 'releaseClosure': 'BLOCKED'}
    (workspace/'h1-result.json').write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    for name in ('maven-seed', 'npm-seed', 'browser-seed'):
        parser.add_argument('--'+name, type=Path)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    qualify(args.workspace, maven_seed=args.maven_seed, npm_seed=args.npm_seed,
            browser_seed=args.browser_seed, offline=args.offline)


if __name__ == '__main__':
    main()
