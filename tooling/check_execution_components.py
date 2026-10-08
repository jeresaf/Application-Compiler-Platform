"""Reproduce isolated typed-lowering tests; NOT negotiated Phase 6 acceptance.

Unsupported capabilities remain visible in this report. A successful component
build cannot make either complete reference application supported.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from execution_approval import approved_snapshot
from phase6_reference_tests import source as test_source, variants, http_source
from target_worker import ROOT, PROFILE, TargetWorker, TargetWorkerError
sys.path.insert(0, str(ROOT / 'worker'))
from generation import plan
from model import lower


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-builds', action='store_true')
    parser.add_argument('--domain', choices=('payment', 'case-management'), help='Limit component diagnostics to one domain')
    args = parser.parse_args()
    output = args.output.absolute()
    if output.exists():
        parser.error('Use a new output directory; no existing files are overwritten')
    templates = {p.relative_to(ROOT / 'templates').as_posix(): p.read_text() for p in (ROOT / 'templates').rglob('*') if p.is_file()}
    report = {'mode': 'UNNEGOTIATED_EXECUTION_COMPONENTS_ONLY', 'phase6': 'NOT_CLOSED', 'domains': {}}
    output.mkdir(parents=True)
    for domain in ((args.domain,) if args.domain else ('payment', 'case-management')):
        snapshot = approved_snapshot(domain)
        nodes = snapshot['content']['nodes']
        try:
            TargetWorker().call('negotiate', {'nodes': nodes, 'required': ['semantic.execution-dataflow/0.3'],
                'decisions': PROFILE['decisions'], 'canonicalVersion': '0.2.0'})
            admission = 'ACCEPTED'
        except TargetWorkerError as error:
            admission = str(error)
        directory = output / domain
        artifacts = plan(lower(nodes, PROFILE, '0.2.0'), templates, PROFILE)
        for artifact in artifacts:
            p = directory / artifact['path']; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(artifact['text'])
        test = directory / 'backend/src/test/java/acp/generated/ExplicitExecutionTest.java'
        test.parent.mkdir(parents=True, exist_ok=True); test.write_text(test_source(domain))
        (test.parent / 'TypedHttpTest.java').write_text(http_source(domain))
        for path, text in variants(domain).items():
            p = directory / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
        evidence = {'canonicalDigest': snapshot['contentDigest'], 'fullTargetAdmission': admission, 'checks': {}}
        report['domains'][domain] = evidence
        if args.run_builds:
            for key, folder, command in (
                ('backend-postgresql', 'backend', ['mvn', '-B', '-ntp', 'test']),
                ('frontend-lock', 'frontend', ['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund']),
                ('frontend-types', 'frontend', ['npm', 'run', 'typecheck']),
                ('frontend-tests', 'frontend', ['npm', 'test']),
                ('frontend-build', 'frontend', ['npm', 'run', 'build'])):
                log = output / (domain + '-' + key + '.log')
                with log.open('wb') as handle:
                    result = subprocess.run(command, cwd=directory / folder, stdout=handle, stderr=subprocess.STDOUT, timeout=600)
                evidence['checks'][key] = 'PASS' if result.returncode == 0 else 'FAIL'
                (output / 'component-report.json').write_text(json.dumps(report, indent=2) + '\n')
                if result.returncode:
                    print(json.dumps({'failed': domain + ':' + key, 'log': str(log), 'phase6': 'NOT_CLOSED'}))
                    return 1
    (output / 'component-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
