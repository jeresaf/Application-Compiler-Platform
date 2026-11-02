"""Pure preview planning tests; not runtime, authority or accepted-history evidence."""
import copy,json,unittest
from pathlib import Path
from engineering.application_evolution.plan import preview,preconditions,validate_plan
from engineering.documents.target import DocumentTarget
from engineering.jobs.target import JobTarget
from compiler_contracts import fingerprint as compiler_fingerprint
from changes import fingerprint
from engineering.source_intelligence.model import sha

class Planning(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.before=json.loads(Path('proposals/phase10-r6-documents/candidate.json').read_bytes());cls.after=json.loads(Path('proposals/phase10-r7-jobs/candidate.json').read_bytes());cls.sql='CREATE TABLE synthetic_unit_only(id integer);'
  def artifact(path,text):return {'path':path,'content':{'encoding':'UTF-8','text':text},'mappings':[],'provenance':{'compiler':'unit-compiler','pipeline':'unit-pipeline'}}
  cls.a={'version':'unit','artifacts':[artifact('backend/src/main/resources/db/migration/V'+str(i)+'__unit.sql','SELECT '+str(i)+';') for i in range(1,5)]};cls.b=copy.deepcopy(cls.a);cls.b['artifacts'].append(artifact('backend/src/main/resources/db/migration/V5__integrity_jobs.sql',cls.sql))
  cls.i6={'candidate':cls.before['contentDigest'],'generator':DocumentTarget().generator,'compiler':'unit-compiler','pipeline':'unit-pipeline','artifactPlan':compiler_fingerprint(cls.a)};cls.i7={'candidate':cls.after['contentDigest'],'generator':JobTarget().generator,'compiler':'unit-compiler','pipeline':'unit-pipeline','artifactPlan':compiler_fingerprint(cls.b)}
  cls.plan=preview(cls.before,cls.after,cls.a,cls.b,cls.i6,cls.i7);cls.observed={'databaseIdentity':{'id':'synthetic-unit-not-a-deployment'},'schema':'acp_browser_case_management','history':[{'version':None,'type':'SCHEMA','success':True}]+[{'version':str(i),'type':'SQL','success':True} for i in range(1,5)],'populationDigest':'sha256:unit','source':cls.before['contentDigest'],'target':cls.after['contentDigest']}
 def test_exact_native_diff(self):self.assertEqual(len(self.plan['change']['operations']),9);self.assertTrue(all(d['operation']=='ADD' for d in self.plan['change']['operations']))
 def test_authority_is_not_manufactured(self):self.assertEqual(self.plan['semanticApproval'],'NOT_APPROVED');self.assertIn('NO ACCEPTED OPERATIONS',self.plan['acceptedProtocol']);self.assertEqual(self.plan['change']['compatibility'],'REVIEW_REQUIRED')
 def test_stop_migrate_restart_policy(self):self.assertEqual(self.plan['migration']['mode'],'STOP_MIGRATE_RESTART');self.assertEqual(self.plan['migration']['oldWriters'],'FENCED_BEFORE_MIGRATION')
 def test_bound_observation(self):self.assertFalse(preconditions(self.plan,self.observed,self.observed,self.sql)['acceptedMigrationApproval'])
 def test_every_observation_binding_rejects_mutation(self):
  for key in self.observed:
   with self.subTest(key=key):
    altered=copy.deepcopy(self.observed);altered[key]='wrong'
    with self.assertRaises(ValueError):preconditions(self.plan,altered,self.observed,self.sql)
 def test_wrong_sql(self):
  with self.assertRaises(ValueError):preconditions(self.plan,self.observed,self.observed,self.sql+'SELECT 1;')
 def test_missing_prerequisite(self):
  a=copy.deepcopy(self.observed);a['history']=a['history'][:-1]
  with self.assertRaises(ValueError):preconditions(self.plan,a,a,self.sql)
 def test_repeat_transition_is_not_a_new_migration(self):
  a=copy.deepcopy(self.observed);a['history'].append({'version':'5','type':'SQL','success':True})
  with self.assertRaises(ValueError):preconditions(self.plan,a,a,self.sql)
 def test_wrong_schema(self):
  a=copy.deepcopy(self.observed);a['schema']='public'
  with self.assertRaises(ValueError):preconditions(self.plan,a,a,self.sql)
 def test_unknown_observation_field(self):
  a={**self.observed,'approval':'invented'}
  with self.assertRaises(ValueError):preconditions(self.plan,a,a,self.sql)
 def test_tampered_plan(self):
  a=copy.deepcopy(self.plan);a['change']['compatibility']='BACKWARD'
  with self.assertRaises(ValueError):validate_plan(a)
 def test_forged_approval_rejected_even_with_new_digest(self):
  a=copy.deepcopy(self.plan);a['semanticApproval']='APPROVED';a['planDigest']=fingerprint({k:v for k,v in a.items() if k!='planDigest'},'plan')
  with self.assertRaises(ValueError):validate_plan(a)
 def test_wrong_generator(self):
  a={**self.i7,'generator':'untrusted'}
  with self.assertRaises(ValueError):preview(self.before,self.after,self.a,self.b,self.i6,a)
 def test_stale_artifact_plan(self):
  b=copy.deepcopy(self.b);b['artifacts'][0]['content']['text']='changed'
  with self.assertRaises(ValueError):preview(self.before,self.after,self.a,b,self.i6,self.i7)
 def test_historical_migration_cannot_change(self):
  b=copy.deepcopy(self.b);b['artifacts'][0]['content']['text']='changed';identity={**self.i7,'artifactPlan':compiler_fingerprint(b)}
  with self.assertRaises(ValueError):preview(self.before,self.after,self.a,b,self.i6,identity)
 def test_missing_migration(self):
  b=copy.deepcopy(self.a);identity={**self.i7,'artifactPlan':compiler_fingerprint(b)}
  with self.assertRaises(ValueError):preview(self.before,self.after,self.a,b,self.i6,identity)

class Capture(unittest.TestCase):
 def test_capture_hashes_and_inventory(self):
  import tempfile
  from engineering.application_evolution.plan import verify_capture,CAPTURE_FILES
  with tempfile.TemporaryDirectory(prefix='acp-r8-capture-unit-') as d:
   root=Path(d)
   for name in CAPTURE_FILES:(root/name).write_bytes(b'exact synthetic unit bytes')
   pins={n:sha((root/n).read_bytes()) for n in CAPTURE_FILES};self.assertEqual(verify_capture(root,pins),pins)
 def test_changed_capture_rejected(self):
  import tempfile
  from engineering.application_evolution.plan import verify_capture,CAPTURE_FILES
  with tempfile.TemporaryDirectory(prefix='acp-r8-capture-unit-') as d:
   root=Path(d)
   for name in CAPTURE_FILES:(root/name).write_bytes(b'original')
   pins={n:sha((root/n).read_bytes()) for n in CAPTURE_FILES};(root/'database.sql').write_bytes(b'changed')
   with self.assertRaises(ValueError):verify_capture(root,pins)
 def test_incomplete_capture_rejected(self):
  import tempfile
  from engineering.application_evolution.plan import verify_capture
  with tempfile.TemporaryDirectory(prefix='acp-r8-capture-unit-') as d:
   with self.assertRaises(ValueError):verify_capture(d,{'database.sql':sha(b'incomplete')})

class Credentials(unittest.TestCase):
 def test_owned_launcher_credentials_are_scoped_and_restored(self):
  import os
  from unittest.mock import patch
  from engineering.application_evolution.run import launch
  class Probe:
   def launch(self):return (os.environ['ACP_TEST_DATABASE_USER'],os.environ['ACP_TEST_DATABASE_PASSWORD'],os.environ['ACP_TEST_DATABASE_URL'])
  with patch.dict(os.environ,{'ACP_TEST_DATABASE_USER':'original','ACP_TEST_DATABASE_PASSWORD':'original-password','ACP_TEST_DATABASE_URL':'owned-only'}):
   self.assertEqual(launch(Probe(),'synthetic-password'),('r8_old_writer','synthetic-password','owned-only'));self.assertEqual(os.environ['ACP_TEST_DATABASE_USER'],'original');self.assertEqual(os.environ['ACP_TEST_DATABASE_PASSWORD'],'original-password')
 def test_failed_startup_restores_credentials(self):
  import os
  from unittest.mock import patch
  from engineering.application_evolution.run import launch
  class Probe:
   def launch(self):raise ValueError('synthetic unit failure')
  with patch.dict(os.environ,{'ACP_TEST_DATABASE_USER':'original','ACP_TEST_DATABASE_PASSWORD':'original-password'}):
   with self.assertRaises(ValueError):launch(Probe(),'synthetic-password')
   self.assertEqual(os.environ['ACP_TEST_DATABASE_USER'],'original');self.assertEqual(os.environ['ACP_TEST_DATABASE_PASSWORD'],'original-password')

class PriorRestart(unittest.TestCase):
 def test_restart_keeps_scoped_role_and_restores_host_credentials(self):
  import os
  from unittest.mock import patch
  from types import SimpleNamespace
  from engineering.application_evolution.run import restart_prior_writer
  class Probe:
   process=SimpleNamespace(pid=10)
   def launch(self):
    assert os.environ['ACP_TEST_DATABASE_USER']=='r8_old_writer';self.process=SimpleNamespace(pid=11);return 11
  with patch.dict(os.environ,{'ACP_TEST_DATABASE_USER':'original','ACP_TEST_DATABASE_PASSWORD':'original-password'}),patch('engineering.application_evolution.run.demo.stop',return_value=-15) as stop:
   result=restart_prior_writer(Probe(),'synthetic-password');stop.assert_called_once();self.assertEqual(result,{'oldPid':10,'oldExit':-15,'newPid':11,'principal':'r8_old_writer'});self.assertEqual(os.environ['ACP_TEST_DATABASE_USER'],'original')
