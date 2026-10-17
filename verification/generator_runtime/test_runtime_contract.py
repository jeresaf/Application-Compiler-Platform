"""Regression contracts for disposable runtime execution and fail-closed counts."""
import ast
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engineering.generator_builds.runtime import IMAGE, verify_report, runtime, extra_tests, supervised_processes


class RuntimeContractTests(unittest.TestCase):
    def test_incomplete_failed_flaky_and_skipped_browser_runs_reject(self):
        valid = {'stats': {'expected': 14, 'unexpected': 0, 'flaky': 0, 'skipped': 0}}
        verify_report(valid, 14)
        for field in valid['stats']:
            report = {'stats': dict(valid['stats'])}
            report['stats'][field] += 1
            with self.assertRaises(ValueError): verify_report(report, 14)
        with self.assertRaises(KeyError): verify_report({'stats': {}}, 14)

    def test_existing_workspace_never_runs_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError): runtime(directory)

    def test_database_is_fresh_digest_pinned_loopback_ephemeral_and_removed(self):
        source = (ROOT / 'engineering/generator_builds/runtime.py').read_text()
        ast.parse(source)
        self.assertTrue(IMAGE.startswith('postgres@sha256:'))
        for token in ('--pull=never', '127.0.0.1::5432', '--tmpfs', "docker('rm', '--force', name)", 'DISPOSABLE_DATABASE_NOT_REMOVED'):
            self.assertIn(token, source)
        self.assertNotIn('physical', source.lower())
        self.assertIn('previous.items()', source)

    def test_process_cleanup_on_exception(self):
        with self.assertRaisesRegex(RuntimeError, 'abort'):
            with supervised_processes():
                child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
                raise RuntimeError('abort')
        self.assertIsNotNone(child.poll())

    def test_hosted_runtime_job_has_real_database_browser_and_no_waivers(self):
        workflow = (ROOT / '.github/workflows/phase6-v3-offline.yml').read_text()
        job = workflow.split('  successor-application-runtime:', 1)[1]
        for token in (IMAGE, "python-version: '3.14.7'", "node-version: '24.21.0'",
                      'engineering/generator_builds/runtime.py', 'verification/generator_runtime', 'if: always()'):
            self.assertIn(token, job)
        self.assertNotIn('continue-on-error', job)
        self.assertNotIn('if: false', job)

    def test_test_adapter_has_explicit_native_ownership_handoff(self):
        source = (ROOT / 'engineering/generator_builds/runtime.py').read_text()
        self.assertIn('store.adopt_human(identity_path)', source)
        self.assertIn('candidate.plan(snapshot, request, inventory=inventory)', source)
        self.assertIn('TEST_EXTENSION_NOT_HANDED_OFF', source)
        self.assertIn('TEST_EXTENSION_OWNERSHIP', source)

    def test_health_and_auth_boundaries_are_explicit(self):
        for domain, port in [('payment', 18080), ('case-management', 18081)]:
            tests = extra_tests(domain)
            self.assertIn(str(port) + '/actuator/health', tests)
            self.assertIn(".status).toBe('UP')", tests)
            self.assertEqual(tests.count('toBe(401)'), 2)
            self.assertIn('toBe(422)', tests)
            self.assertIn("code:'VALIDATION_FAILED',category:'INTERNAL',retryable:false", tests)
