import unittest
from pathlib import Path


class Hosted(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.text=Path('.github/workflows/phase11-h2.yml').read_text()
    def test_pinned_runner(self):
        for s in ('ubuntu-24.04',"python-version: '3.14.7'","node-version: '24.21.0'",'--require-hashes --only-binary=:all:'):self.assertIn(s,self.text)
    def test_real_execution_and_no_skips(self):
        for s in ('-m engineering.reliability.run','engineering/source_intelligence/qualification.py','not result.skipped','set -euo pipefail','result.testsRun==45'):self.assertIn(s,self.text)
        self.assertNotIn('continue-on-error',self.text)
    def test_exact_identity_and_complete_failure_scenarios(self):
        for s in ("record['sourceCommit']","record['generator']==HardeningTarget().descriptor()","record['canonicalDigest']",'==SCENARIOS',"record['cleanup']=='VERIFIED'"):self.assertIn(s,self.text)
        self.assertLess(self.text.index("sys.path.insert(0,str(Path('tooling').resolve()))"),self.text.index('from engineering.reliability.verification import'))
    def test_scope_and_hidden_ownership_evidence(self):
        for s in ("record['releaseClosure']=='BLOCKED'","record['scope']=='QUALIFICATION_ONLY'",'include-hidden-files: true','if: always()'):self.assertIn(s,self.text)
