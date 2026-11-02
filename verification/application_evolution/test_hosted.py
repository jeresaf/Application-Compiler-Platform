import ast,json,textwrap,unittest
from pathlib import Path
class Hosted(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.text=Path('.github/workflows/phase10-r8.yml').read_text()
 def test_actual_evolution_runner(self):self.assertIn('-m engineering.application_evolution.run',self.text);self.assertNotIn('-m engineering.jobs.run',self.text)
 def test_exact_candidates_exist(self):
  source=self.text.split('          from engineering.documents.target',1)[1].split('          PYTHON',1)[0];source='from engineering.documents.target'+source
  tree=ast.parse(textwrap.dedent('\n'.join(line[10:] if line.startswith('          ') else line for line in source.splitlines())))
  paths=[n.args[0].value for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='Path' and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str) and n.args[0].value.startswith('proposals/')]
  self.assertEqual(set(paths),{'proposals/phase10-r6-documents/candidate.json','proposals/phase10-r7-jobs/candidate.json'})
  for p in paths:self.assertTrue(Path(p).is_file())
 def test_pinned_and_fail_closed(self):
  for token in ('ubuntu-24.04',"python-version: '3.14.7'",'--require-hashes --only-binary=:all:','not result.skipped','set -euo pipefail'):self.assertIn(token,self.text)
  self.assertNotIn('continue-on-error',self.text)
 def test_real_continuity_and_identity_checks(self):
  for token in ("record['sourceCommit']","record['beforeCandidate']","record['afterCandidate']","record['planDigest']","record['migration']['sourceDatabase']==record['migration']['targetDatabase']","record['continuity']['documentsExact']","record['restore']['exactRowsBeforeMigration']","len(record['browser'])==9"):self.assertIn(token,self.text)
 def test_release_boundary_and_output_exclusions(self):
  self.assertIn("record['semanticApproval']=='NOT_APPROVED'",self.text);self.assertIn("record['scope']=='QUALIFICATION_ONLY'",self.text)
  self.assertIn('r6-outputs/frontend/node_modules/**',self.text);self.assertIn('r7-outputs/frontend/node_modules/**',self.text)
