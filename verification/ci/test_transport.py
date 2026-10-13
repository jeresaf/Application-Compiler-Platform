"""Exercise artifact transport validation using isolated in-memory ZIPs."""
import hashlib
import io
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from pathlib import Path
from engineering.ci import aggregate as a


class TransportTests(unittest.TestCase):
    def zip(self, entries):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as z:
            for name, data in entries.items(): z.writestr(name, data)
        return stream.getvalue()

    def download(self, data, digest=None):
        artifact = {'name': 'isolated-test', 'archive_download_url': 'https://api.github.com/isolated',
                    'digest': digest or 'sha256:'+hashlib.sha256(data).hexdigest()}
        opener = unittest.mock.Mock()
        opener.open.return_value = io.BytesIO(data)
        with patch.dict(os.environ, {'GH_TOKEN': 'synthetic-not-a-credential'}), patch.object(a.urllib.request, 'build_opener', return_value=opener):
            return a.archive(artifact)

    def test_archive_integrity(self):
        self.assertEqual(self.download(self.zip({'proof.json': '{}'})).namelist(), ['proof.json'])
        with self.assertRaisesRegex(ValueError, 'DIGEST_MISMATCH'):
            self.download(self.zip({'proof.json': '{}'}), 'sha256:'+'0'*64)
        with self.assertRaises(zipfile.BadZipFile): self.download(b'malformed')
        with self.assertRaisesRegex(ValueError, 'INVALID_ARCHIVE'): self.download(self.zip({}))

    def test_redirect_never_forwards_github_token(self):
        data = self.zip({'tests.log': 'synthetic'})
        artifact = {'name': 'test', 'archive_download_url': 'https://api.github.com/isolated', 'digest': 'sha256:'+hashlib.sha256(data).hexdigest()}
        opener = unittest.mock.Mock()
        opener.open.side_effect = a.urllib.error.HTTPError(artifact['archive_download_url'], 302, 'redirect', {'Location': 'https://storage.invalid/isolated'}, None)
        with patch.dict(os.environ, {'GH_TOKEN': 'synthetic-not-a-credential'}), patch.object(a.urllib.request, 'build_opener', return_value=opener), patch.object(a.urllib.request, 'urlopen', return_value=io.BytesIO(data)) as request:
            self.assertEqual(a.archive(artifact).namelist(), ['tests.log'])
            request.assert_called_once_with('https://storage.invalid/isolated', timeout=180)

    def test_hosted_wrong_source_is_rejected(self):
        with patch.dict(os.environ, {'GITHUB_SHA': 'a'*40, 'GITHUB_RUN_ID': '1', 'GITHUB_RUN_ATTEMPT': '1', 'GITHUB_EVENT_PATH': '/missing'}), patch.object(a, 'api', return_value={'head_sha': 'b'*40, 'run_attempt': 1}):
            with self.assertRaises((ValueError, FileNotFoundError)): a.hosted()

    def test_capture_checks_actual_checkout(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(a, 'OUT', Path(temporary)), patch.dict(os.environ, {'GITHUB_SHA': 'a'*40, 'GITHUB_JOB': 'contracts', 'GITHUB_RUN_ID': '1', 'GITHUB_RUN_ATTEMPT': '2'}), patch.object(a.subprocess, 'check_output', return_value='a'*40), patch.object(a.sys, 'argv', ['aggregate.py', 'capture']):
            self.assertEqual(a.main(), 0)
            self.assertEqual(json.loads((Path(temporary)/'contracts.json').read_text())['attempt'], '2')
            with patch.object(a.subprocess, 'check_output', return_value='b'*40):
                with self.assertRaisesRegex(ValueError, 'CHECKOUT_SOURCE'): a.main()

class HostedIntegrationTests(unittest.TestCase):
    """Synthetic API responses and archives; no remote service or journal."""
    def setUp(self):
        self.source = 'a'*40
        self.jobs = [{'name': n, 'conclusion': 'success', 'started_at': '2026-10-13T00:00:00Z', 'completed_at': '2026-10-13T00:01:00Z'} for n in a.JOBS]
        self.entries = {}
        for job in a.JOBS:
            self.entries['ci-source-'+job] = {job+'.json': json.dumps({'source': self.source, 'run': '1', 'attempt': '1', 'job': job})}
        for name in a.ARTIFACTS:
            self.entries[name] = {p: '{}' if p.endswith('.json') else 'Ran 12 tests in 1.0s\nOK\n' for p in a.REQUIRED_FILES[name]}
        self.closure = {'baseline': {'auditExecutionCommit': self.source}, 'auditExecution': {'status': 'PERFORMED'},
                        'recommendation': 'PHASE6_CLOSURE_RECOMMENDED', 'blockers': [],
                        'criteria': [{'requirement': i, 'status': 'PASS', 'evaluationProvenance': {'executionCommit': self.source, 'evaluationCommit': self.source}} for i in range(1, 40)]}
        self.artifacts = [{'id': i, 'name': n, 'expired': False, 'created_at': '2026-10-13T00:00:30Z', 'digest': 'synthetic', 'workflow_run': {'head_sha': self.source, 'id': 1}} for i, n in enumerate(self.entries)]

    def run_hosted(self, needs=None):
        self.entries[a.ARTIFACTS[-1]]['phase6-final-closure.json'] = json.dumps(self.closure)
        def pages(path, key): return self.jobs if key == 'jobs' else self.artifacts
        def archive(artifact):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as z:
                for name, data in self.entries[artifact['name']].items(): z.writestr(name, data)
            return zipfile.ZipFile(io.BytesIO(stream.getvalue()))
        env = {'GITHUB_SHA': self.source, 'GITHUB_RUN_ID': '1', 'GITHUB_RUN_ATTEMPT': '1',
               'EXPECTED_NEEDS': json.dumps(needs or {n: {'result': j['conclusion']} for n, j in zip(a.JOBS, self.jobs)})}
        with tempfile.TemporaryDirectory() as temporary, patch.object(a, 'OUT', Path(temporary)), patch.dict(os.environ, env), patch.object(a, 'api', return_value={'head_sha': self.source, 'run_attempt': 1}), patch.object(a, 'pages', side_effect=pages), patch.object(a, 'archive', side_effect=archive), patch('builtins.print'):
            code = a.hosted()
            return code, json.loads((Path(temporary)/'aggregate.json').read_text())

    def test_complete_transport_pipeline_synthetic_pass(self):
        self.assertEqual(self.run_hosted()[0], 0)

    def test_actual_blocked_closure_pipeline_fails(self):
        self.jobs[-1]['conclusion'] = 'failure'
        self.closure.update(recommendation='PHASE6_CLOSURE_BLOCKED', blockers=[{'requirement': 5}])
        code, result = self.run_hosted()
        self.assertEqual(code, 1)
        self.assertEqual(result['release'], 'PHASE6_RELEASE_CLOSURE_BLOCKED')
        self.assertEqual(result['engineering'], 'ENGINEERING_VALIDATION_PASSED')

    def test_wrong_run_artifact_and_stale_binding_fail(self):
        self.artifacts[0]['workflow_run']['id'] = 2
        self.assertEqual(self.run_hosted()[0], 1)
        self.artifacts[0]['workflow_run']['id'] = 1
        self.entries['ci-source-contracts']['contracts.json'] = json.dumps({'source': self.source, 'run': '1', 'attempt': '0', 'job': 'contracts'})
        self.assertEqual(self.run_hosted()[0], 1)

    def test_missing_archive_and_duplicate_archive_fail(self):
        self.artifacts.pop()
        self.assertEqual(self.run_hosted()[0], 1)
        self.artifacts.append(self.artifacts[0])
        self.assertEqual(self.run_hosted()[0], 1)

    def test_required_report_missing_or_malformed_fails(self):
        del self.entries[a.ARTIFACTS[3]]['task-interface-report.json']
        with self.assertRaisesRegex(ValueError, 'REQUIRED_ARTIFACT_FILES_MISSING'): self.run_hosted()
        self.entries[a.ARTIFACTS[3]]['task-interface-report.json'] = '{'
        with self.assertRaises(json.JSONDecodeError): self.run_hosted()

    def test_malformed_binding_fails(self):
        self.entries['ci-source-contracts']['contracts.json'] = '{'
        with self.assertRaises(json.JSONDecodeError): self.run_hosted()

    def test_old_attempt_artifact_time_is_rejected(self):
        self.artifacts[0]['created_at'] = '2026-10-12T00:00:30Z'
        self.assertEqual(self.run_hosted()[0], 1)

    def test_needs_api_disagreement_fails(self):
        needs = {n: {'result': 'success'} for n in a.JOBS}
        needs['contracts']['result'] = 'cancelled'
        self.assertEqual(self.run_hosted(needs)[0], 1)


if __name__ == '__main__': unittest.main()
