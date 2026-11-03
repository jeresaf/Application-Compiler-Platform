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
