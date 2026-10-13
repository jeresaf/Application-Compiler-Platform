"""Controlled synthetic inputs only; never accepted release evidence."""
import copy
import unittest
from unittest.mock import patch
from pathlib import Path
from engineering.ci.aggregate import JOBS, ARTIFACTS, evaluate
from engineering.ci.parity import verify


class AggregationTests(unittest.TestCase):
    def setUp(self):
        self.source = 'a'*40
        self.jobs = [{'name': n, 'conclusion': 'success'} for n in JOBS]
        self.bindings = {n: {'source': self.source, 'run': '1', 'attempt': '1', 'job': n} for n in JOBS}
        self.artifacts = {n: {'source': self.source, 'valid': True} for n in ARTIFACTS}
        self.closure = {'baseline': {'auditExecutionCommit': self.source}, 'auditExecution': {'status': 'PERFORMED'},
                        'recommendation': 'PHASE6_CLOSURE_RECOMMENDED', 'blockers': [], 'criteria': [{'requirement': i, 'status': 'PASS', 'evaluationProvenance': {'executionCommit': self.source, 'evaluationCommit': self.source}} for i in range(1,40)]}

    def result(self):
        return evaluate(self.source, '1', '1', self.jobs, self.bindings, self.artifacts, self.closure)

    def test_controlled_all_pass(self):
        self.assertTrue(self.result()['releasePassed'])

    def test_blocked_closure_never_passes(self):
        self.closure.update(recommendation='PHASE6_CLOSURE_BLOCKED', blockers=[{'id': 'synthetic'}])
        self.assertFalse(self.result()['releasePassed'])
        self.assertEqual(self.result()['engineering'], 'ENGINEERING_VALIDATION_PASSED')

    def test_every_required_job_failure_skip_cancellation_and_missing(self):
        for name in JOBS:
            for state in ('failure', 'skipped', 'cancelled', 'timed_out', None):
                with self.subTest(job=name, state=state):
                    self.jobs = [{'name': n, 'conclusion': state if n == name else 'success'} for n in JOBS]
                    self.assertFalse(self.result()['releasePassed'])
        self.jobs = self.jobs[:-1]
        self.assertFalse(self.result()['releasePassed'])

    def test_execution_exception(self):
        self.closure['auditExecution']['status'] = 'EXCEPTION'
        self.assertFalse(self.result()['releasePassed'])

    def test_every_missing_wrong_source_and_invalid_artifact(self):
        original = copy.deepcopy(self.artifacts)
        for name in ARTIFACTS:
            for mutation in ('missing', 'source', 'invalid'):
                with self.subTest(name=name, mutation=mutation):
                    self.artifacts = copy.deepcopy(original)
                    if mutation == 'missing': del self.artifacts[name]
                    elif mutation == 'source': self.artifacts[name]['source'] = 'b'*40
                    else: self.artifacts[name]['valid'] = False
                    self.assertFalse(self.result()['releasePassed'])

    def test_binding_source_attempt_and_job_confusion(self):
        original = copy.deepcopy(self.bindings)
        for name in JOBS:
            for key in ('source', 'run', 'attempt', 'job'):
                with self.subTest(name=name, key=key):
                    self.bindings = copy.deepcopy(original)
                    self.bindings[name][key] = 'wrong'
                    self.assertFalse(self.result()['releasePassed'])

    def test_inconsistent_closure_evidence(self):
        original = copy.deepcopy(self.closure)
        for key, value in [('criteria', []), ('criteria', [{'status': 'BLOCKED'}]), ('blockers', [{}]), ('baseline', {})]:
            self.closure = copy.deepcopy(original)
            self.closure[key] = value
            self.assertFalse(self.result()['releasePassed'])

    def test_duplicate_job(self):
        self.jobs.append(self.jobs[0])
        self.assertFalse(self.result()['releasePassed'])

    def test_parity_rejects_missing_commands_versions_artifacts_and_serialization(self):
        workflow = Path('.github/workflows/acp-contracts.yml').read_text()
        changes = [('node tooling/check_canonical_vectors.mjs test-corpus/deterministic-v04', 'true'),
                   ("python-version: '3.14.7'", "python-version: '3.14.6'"),
                   ('/tmp/acp-phase6-target/task-interface-report.json', '/tmp/omitted.json'),
                   ('    needs: [contracts, phase5c-hard-gates]\n    runs-on: ubuntu-24.04\n    timeout-minutes: 90',
                    '    needs: [contracts, phase5c-hard-gates, phase6-target]\n    runs-on: ubuntu-24.04\n    timeout-minutes: 90')]
        for old, new in changes:
            with self.subTest(change=old), patch.object(Path, 'read_text', return_value=workflow.replace(old, new)):
                with self.assertRaises(AssertionError): verify()

    def test_hidden_aggregate_evidence_requires_explicit_upload(self):
        workflow = Path('.github/workflows/acp-contracts.yml').read_text()
        with patch.object(Path, 'read_text', return_value=workflow.replace('          include-hidden-files: true\n', '')):
            with self.assertRaisesRegex(AssertionError, 'HIDDEN_EVIDENCE_NOT_RETAINED'): verify()

    def test_original_workflow_parity(self):
        self.assertEqual(verify()['originalJobs'], 5)


if __name__ == '__main__': unittest.main()
