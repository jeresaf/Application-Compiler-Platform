"""Exact original job-body preservation with the authorized scheduling/isolation deltas."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASELINE = '0057b008bd8fa5519b3b625c89fb262f53f6f844'
WORKFLOW = '.github/workflows/acp-contracts.yml'


def jobs(text):
    return {m.group(1): m.group(2) for m in re.finditer(r'^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)', text.split('jobs:\n', 1)[1], re.M | re.S)}


def verify():
    baseline = subprocess.check_output(['git', 'show', BASELINE+':'+WORKFLOW], cwd=ROOT, text=True)
    current = (ROOT/WORKFLOW).read_text()
    old, new = jobs(baseline), jobs(current)
    assert set(new) == set(old) | {'final-ci-aggregate'}, 'JOB_INVENTORY'
    for name, body in old.items():
        actual = new[name]
        assert 'run: python3.14 engineering/ci/aggregate.py capture' in actual, 'SOURCE_CAPTURE:'+name
        assert 'name: ci-source-'+name in actual, 'SOURCE_ARTIFACT:'+name
        actual = actual.split('      - name: Bind fresh job evidence to exact source and attempt')[0].rstrip()
        if name == 'contracts':
            actual = actual.replace('      - name: Verify CI parity and fail-closed aggregation regressions\n        run: python3.14 -m unittest discover -s verification/ci -v\n', '')
        if name == 'phase6-closure-audit':
            actual = actual.replace('needs: [contracts, phase5c-hard-gates]', 'needs: [contracts, phase5c-hard-gates, phase6-target]', 1)
        actual = actual.replace('ephemeral-test-only-target', 'ephemeral-test-only').replace('ephemeral-test-only-closure', 'ephemeral-test-only')
        assert actual == body.rstrip(), 'ORIGINAL_JOB_BODY_CHANGED:'+name
    assert 'needs: [contracts, phase5c-hard-gates]\n' in new['phase6-closure-audit'], 'AUDIT_NOT_PARALLEL'
    assert 'ephemeral-test-only-target' in new['phase6-target']
    assert 'ephemeral-test-only-closure' in new['phase6-closure-audit']
    final = new['final-ci-aggregate']
    assert 'run: python3.14 engineering/ci/aggregate.py hosted' in final, 'AGGREGATOR_NOT_WIRED'
    assert 'EXPECTED_NEEDS: ${{ toJSON(needs) }}' in final, 'ACTUAL_NEEDS_NOT_BOUND'
    assert '    if: always()' in final
    assert '    needs: [contracts, phase5-experiments, phase5c-hard-gates, phase6-target, phase6-closure-audit]' in final
    assert 'continue-on-error' not in current
    assert current[:current.index('jobs:')] == baseline[:baseline.index('jobs:')], 'WORKFLOW_TRIGGER_OR_PERMISSIONS'
    return {'baseline': BASELINE, 'originalJobs': len(old), 'originalJobBodies': 'EXACT_EXCEPT_AUTHORIZED_DAG_AND_ISOLATED_PASSWORDS', 'testCommandsAndArtifacts': 'PRESERVED'}


if __name__ == '__main__':
    print(verify())
