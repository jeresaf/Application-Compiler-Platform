import unittest
from pathlib import Path


class Hosted(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.text=Path('.github/workflows/phase11-h3.yml').read_text()
    def test_pinned_environment_and_isolated_install(self):
        for value in ('ubuntu-24.04',"python-version: '3.14.7'","node-version: '24.21.0'",'--require-hashes --only-binary=:all:','$RUNNER_TEMP/acp-h3-venv'):self.assertIn(value,self.text)
    def test_actual_application_and_no_skips(self):
        for value in ('-m engineering.capacity.run','verification/capacity:46','verification/hardening:20','verification/reliability:45','not result.skipped','set -euo pipefail'):self.assertIn(value,self.text)
        self.assertNotIn('continue-on-error',self.text)
    def test_exact_bindings_and_no_production_acceptance(self):
        for value in ("r['sourceCommit']", "r['generator']==HardeningTarget().descriptor()", "r['sourceSHA256']==source_inventory()", "r['G22']=='NOT_SATISFIED'", "r['releaseClosure']=='BLOCKED'"):self.assertIn(value,self.text)
    def test_failure_and_hidden_ownership_evidence_retained(self):
        for value in ('if: always()','include-hidden-files: true','if-no-files-found: error','phase11-h3-capacity'):self.assertIn(value,self.text)
