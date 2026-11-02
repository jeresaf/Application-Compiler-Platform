import ast,json,textwrap,unittest
from pathlib import Path
class Hosted(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.text=Path('.github/workflows/phase10-r7.yml').read_text()
 def test_actual_runner(self):self.assertIn('-m engineering.jobs.run',self.text);self.assertNotIn('-m engineering.documents.run',self.text)
 def test_pinned_environment(self):
  for text in ('ubuntu-24.04',"python-version: '3.14.7'","node-version: '24.21.0'",'postgres@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336'):self.assertIn(text,self.text)
 def test_no_skips_or_failure_suppression(self):self.assertNotIn('continue-on-error',self.text);self.assertIn('not result.skipped',self.text);self.assertIn('set -euo pipefail',self.text)
 def test_exact_source_binding(self):
  for text in ("record['sourceCommit']",'git',"record['candidateDigest']","record['generator']['profile']==PROFILE",'source_digest()',"'engineering/jobs/run.py'",'hashlib.sha256'):self.assertIn(text,self.text)
  def check_candidate_path(workflow):
   script=workflow.split('          import hashlib,json,os,subprocess\n',1)[1].split('          PYTHON',1)[0]
   paths=[n.args[0].value for n in ast.walk(ast.parse(textwrap.dedent(script))) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='Path' and n.args and isinstance(n.args[0],ast.Constant) and isinstance(n.args[0].value,str) and n.args[0].value.startswith('proposals/')]
   self.assertEqual(paths,['proposals/phase10-r7-jobs/candidate.json'])
   self.assertTrue(Path(paths[0]).is_file())
   self.assertEqual(json.loads(Path(paths[0]).read_bytes())['content']['schemaVersion'],'0.7.0')
  check_candidate_path(self.text)
  with self.assertRaises(AssertionError):check_candidate_path(self.text.replace('proposals/phase10-r7-jobs/','proposals/phase10-r7-documents/'))
 def test_exact_actual_browser_and_cleanup(self):
  for text in ("len(record['browser'])==8","b['unexpected']==b['skipped']==b['flaky']==0","'database':'REMOVED'","'processes':'REAPED'"):self.assertIn(text,self.text)
 def test_no_dependency_trees_in_artifact(self):
  for r in ('r0','r1'):self.assertIn('/'+r+'-outputs/frontend/node_modules/**',self.text)
