"""Ensure a green parent runner cannot masquerade as document qualification."""
from pathlib import Path
import unittest

class HostedDispatch(unittest.TestCase):
 def test_exact_document_runner_and_source_binding(self):
  text=Path('.github/workflows/phase10-r6.yml').read_text()
  self.assertEqual(text.count('-m engineering.documents.run'),1)
  self.assertNotIn('-m engineering.reporting.run',text)
  for check in ("record['generator']['profile']==PROFILE","record['candidateDigest']==expected['contentDigest']","record['sourceCommit']==subprocess.check_output", "len(record['browser'])==6", "'engineering/documents/run.py' in record['sourceSHA256']"):
   self.assertIn(check,text)
  self.assertLess(text.index('-m engineering.documents.run'),text.index('Verify exact document execution identity'))
 def test_failure_and_toolchain_policy_preserved(self):
  text=Path('.github/workflows/phase10-r6.yml').read_text()
  for required in ('ubuntu-24.04',"python-version: '3.14.7'","node-version: '24.21.0'",'--require-hashes --only-binary=:all:','suite.countTestCases()==25','result.testsRun==25','not result.skipped','set -euo pipefail','if-no-files-found: error'):
   self.assertIn(required,text)
  self.assertNotIn('continue-on-error',text)
