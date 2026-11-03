import os
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


class Hosted(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = Path('.github/workflows/phase11-h1.yml').read_text()

    def test_pinned_environment(self):
        for value in ('ubuntu-24.04', "python-version: '3.14.7'", "node-version: '24.21.0'",
                      '--require-hashes --only-binary=:all:', 'pip check'):
            self.assertIn(value, self.text)

    def test_real_executor_and_failure_propagation(self):
        for value in ('-m engineering.hardening.run', 'set -euo pipefail',
                      'not result.skipped', "record['specificSecurityAssessment']['status']=='PASS'"):
            self.assertIn(value, self.text)
        self.assertNotIn('continue-on-error', self.text)

    def test_exact_source_and_release_boundary(self):
        for value in ("record['sourceCommit']", "record['generatorSourceDigest']==source_digest()",
                      "record['releaseClosure']=='BLOCKED'", "record['scope']=='QUALIFICATION_ONLY'"):
            self.assertIn(value, self.text)

    def test_ownership_and_scanner_evidence_retained(self):
        self.assertIn('include-hidden-files: true', self.text)
        self.assertIn('${{ runner.temp }}/acp-h1/', self.text)
        self.assertIn('!${{ runner.temp }}/acp-h1/r0-outputs/frontend/node_modules/**', self.text)

    def test_identity_step_imports_without_inherited_pythonpath(self):
        step = self.text.split('      - name: Exact source and preserved release identities\n', 1)[1]
        prefix = step.split("<<'PYTHON'\n", 1)[1].split('          record=', 1)[0]
        script = textwrap.dedent(prefix)+'\nassert len(source_digest()) == 64\n'
        env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
        result = subprocess.run([sys.executable, '-B', '-c', script], env=env,
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
