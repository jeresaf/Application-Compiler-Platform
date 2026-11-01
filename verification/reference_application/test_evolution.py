"""R2 proposal integrity, preview boundaries and negative input regressions."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from engineering.reference_application import evolution as e
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
from engineering.demo.pipeline import PipelineCandidate,request
from compiler_contracts import Document
from filesystem_artifacts import FilesystemArtifactStore

class Evolution(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.old,cls.new,cls.plan=e.proposal();cls.c=SuccessorCandidate()
 def test_exact_existing_proposal_native_plan_and_scope(self):
  self.assertEqual(self.new.read()['contentDigest'],'sha256:e57eaee3f979f3b77feb255dde470772321b3354001547e71e02fbaadca2b59d');self.assertEqual(self.plan['compatibility'],'BREAKING');self.assertIn('MIGRATION',self.plan['requiredScopes'])
 def test_native_ddl_and_no_default(self):
  phases=e.statements(self.c,self.new);self.assertEqual(set(phases),{'EXPAND','VERIFY','CONTRACT'});self.assertNotIn('DEFAULT',''.join(phases.values()));self.assertNotIn('NOT NULL',phases['EXPAND']);self.assertIn('SET NOT NULL',phases['CONTRACT']);self.assertTrue(phases['VERIFY'].startswith('SET CONSTRAINTS ALL IMMEDIATE;'))
 def test_exact_unicode_and_nul_without_normalization(self):
  row={'tenant':'74656e616e74','resource':'726573'};sql=e.backfill([row],{('74656e616e74','726573'):e.PREVIEW_VALUE});self.assertIn('65cc8100f09fa68b27',sql);self.assertNotIn('c3a9',sql)
 def test_missing_extra_and_nonstring_bindings_rejected(self):
  row={'tenant':'aa','resource':'bb'}
  for value in ({},{('aa','bb'):'ok',('cc','dd'):'extra'},{('aa','bb'):None},{('aa','bb'):3}):
   with self.assertRaises(ValueError):e.backfill([row],value)
  for value in (None,True,3,[],{}):
   with self.assertRaisesRegex(ValueError,'EXPLICIT_NEW_RECORD_STRING'):e.explicit_value_insert("INSERT INTO fixture(id) VALUES('id')",value)
  self.assertIn("decode('','hex')",e.explicit_value_insert("INSERT INTO fixture(id) VALUES('id')",''))
 def test_changed_proposal_cannot_be_previewed(self):
  real=Path.read_bytes
  with patch.object(Path,'read_bytes',lambda p:real(p)+b' ' if p.name=='case-management-change.json' else real(p)):
   with self.assertRaisesRegex(ValueError,'PROPOSAL_SUBSTITUTION'):e.proposal()
 def test_preview_does_not_admit_original_pipeline_or_migration_history(self):
  p=PipelineCandidate()
  with self.assertRaisesRegex(ValueError,'EXACT_APPROVED_REFERENCE'):p.plan(self.new,request(p,self.new))
  class NoHistory:
   def read_accepted_plan(self,digest):raise PermissionError()
  with self.assertRaisesRegex(ValueError,'UNACCEPTED_HISTORY'):self.c.plan_upgrade(self.old,self.new,Document.of(self.plan),Document.of({'requiredFieldBackfills':{e.FIELD:e.PREVIEW_VALUE}}),NoHistory())
 def test_new_generated_artifacts_preserve_human_seam(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'app';store=FilesystemArtifactStore(root);store.apply(self.c.plan(self.old,request(self.c,self.old)));store.adopt_human(e.HUMAN);human=(root/e.HUMAN).read_bytes()+b'\n// owned\n';(root/e.HUMAN).write_bytes(human)
   r=request(self.c,self.new);inventory=store.inventory();p=e._ownership(self.c.plan(self.new,r,inventory=inventory),inventory);store.apply(p);self.c.verify_materialized(root,p,self.new,r);self.assertEqual(human,(root/e.HUMAN).read_bytes())
   expected=e.life.tree(root);output=root/'backend/target';output.mkdir();(output/'compiled.class').write_bytes(b'build output');e.life.detach_outputs(root,expected,Path(t)/'outputs');self.c.verify_materialized(root,p,self.new,r);self.assertEqual(e.life.tree(root),expected)
 def test_no_arbitrary_database_or_unverified_restore(self):
  with self.assertRaisesRegex(ValueError,'UNOWNED_DATABASE'):e.DisposableSQL('production',Path('/tmp'))
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'fake.zip';p.write_bytes(b'fake')
   with self.assertRaisesRegex(ValueError,'CUSTODY_ARCHIVE_DIGEST'):e.restore_database(p,Path(t)/'out')
   self.assertFalse((Path(t)/'out').exists())
 def test_occupied_application_port_fails_before_any_execution(self):
  import socket
  with tempfile.TemporaryDirectory() as t,socket.socket() as listener:
   listener.bind(('127.0.0.1',18081));listener.listen();workspace=Path(t)/'never-created'
   with self.assertRaises(OSError):e.qualify(workspace)
   self.assertFalse(workspace.exists())
 def test_review_request_is_not_execution_or_approval(self):
  with tempfile.TemporaryDirectory() as t:
   p=e.authorization_package(Path(t),self.plan,[],{})
   self.assertEqual(p['acceptedMigrationPlan'],'NOT_APPROVED');self.assertEqual(p['retainedMigrationExecution'],'NOT_AUTHORIZED');self.assertFalse(p['newRecordDefault']);self.assertEqual(p['deployment'],'NOT_AUTHORIZED')
if __name__=='__main__':unittest.main()
