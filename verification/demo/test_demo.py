"""Focused full-compiler/demo/dependency regression; no release acceptance."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.demo.pipeline import inputs,PipelineCandidate,CandidatePort,request
from engineering.demo.reference import bind_owned_backend,proxy_source,stable_server,verify_replay_state,dependencies as demo_dependencies
from engineering.generator_candidates.spring_vue_postgres_0_6 import dependencies
from compiler_contracts import STAGES,Document
from filesystem_artifacts import FilesystemArtifactStore

class PipelineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.examples={d:inputs(d) for d in ('payment','case-management')}
 def test_both_approved_snapshots_execute_every_existing_compiler_stage(self):
  for domain,(c,s,r,p) in self.examples.items():
   with self.subTest(domain=domain):
    audit=c.executions[0]['audit'];self.assertEqual([x['stage'] for x in audit['stages']],[str(x) for x in STAGES]);self.assertEqual(audit['input_canonical_digest'],r.snapshot_digest);self.assertEqual(c.executions[0]['admission']['result'],'ACCEPTED');self.assertEqual(len(p.artifacts),72)
 def test_real_compiler_provenance_is_verified_against_its_actual_target_ir(self):
  for domain,(c,s,r,p) in self.examples.items():
   with self.subTest(domain=domain),tempfile.TemporaryDirectory() as folder:
    root=Path(folder)/domain;FilesystemArtifactStore(root).apply(p);c.verify_materialized(root,p,s,r)
 def test_unapproved_snapshot_and_wrong_generator_fail_before_compilation(self):
  c,s,r,p=self.examples['payment'];bad=s.read();bad['contentDigest']='sha256:'+'0'*64
  with self.assertRaisesRegex(ValueError,'EXACT_APPROVED_REFERENCE'):c.plan(Document.of(bad),r)
  wrong=copy.copy(r);wrong.generator='other'
  with self.assertRaisesRegex(ValueError,'EXACT_APPROVED_REFERENCE'):c.plan(s,wrong)
 def test_required_feature_identity_cannot_be_silently_dropped(self):
  c,s,r,p=self.examples['payment'];wrong=copy.copy(r);wrong.features=()
  with self.assertRaisesRegex(ValueError,'FEATURE_IDENTITY'):c.plan(s,wrong)
 def test_approved_tomcat_overlay_changes_only_the_generated_pom(self):
  original=(ROOT/'targets/spring-vue-postgres/templates/backend/pom.xml').read_text();given={dependencies.PATH:original,'other':'unchanged'};result=dependencies.apply(given)
  self.assertEqual(given[dependencies.PATH],original);self.assertEqual(result['other'],'unchanged');self.assertEqual(result[dependencies.PATH],original.replace('<properties>','<properties><tomcat.version>11.0.26</tomcat.version>',1))
  with self.assertRaisesRegex(ValueError,'DEPENDENCY_TEMPLATE_DRIFT'):dependencies.apply({dependencies.PATH:original+'tampered'})

class RuntimeBoundaryTests(unittest.TestCase):
 def test_default_acquisition_uses_a_private_empty_seed_and_restores_environment(self):
  import os
  with tempfile.TemporaryDirectory() as folder,patch('engineering.demo.reference.seed_maven') as acquire,patch.dict(os.environ,{'MAVEN_OPTS':'original'}):
   with demo_dependencies(Path(folder)/'demo') as root:
    seed,target,lock=acquire.call_args.args
    self.assertEqual(seed,root/'empty-m2');self.assertTrue(seed.is_dir());self.assertEqual(list(seed.iterdir()),[])
    self.assertEqual(target,root/'m2');self.assertTrue(lock['artifacts']);self.assertEqual(acquire.call_args.kwargs,{'online':True})
    self.assertEqual(os.environ['npm_config_cache'],str(root/'npm'))
   self.assertEqual(os.environ['MAVEN_OPTS'],'original')
 def test_backend_and_flyway_are_fenced_to_only_the_owned_database(self):
  env={'ACP_TEST_DATABASE_URL':'jdbc:postgresql://127.0.0.1:1234/acp_runtime','ACP_TEST_DATABASE_USER':'fixture','ACP_TEST_DATABASE_PASSWORD':'fixture-only'}
  actual={'ACP_DATABASE_URL':env['ACP_TEST_DATABASE_URL']+'?currentSchema=acp_browser_payment'}
  with patch.dict('os.environ',env),patch('subprocess.Popen') as launch:
   with bind_owned_backend(['acp-06-runtime-owned']):
    import subprocess
    subprocess.Popen(['java','acp.browser.BrowserServer'],env=actual)
   argv=launch.call_args.args[0];self.assertIn('--spring.datasource.url='+actual['ACP_DATABASE_URL'],argv);self.assertIn('--spring.flyway.url='+actual['ACP_DATABASE_URL'],argv)
 def test_existing_or_wrong_database_override_is_never_launched(self):
  import subprocess
  with patch.dict('os.environ',{'ACP_TEST_DATABASE_URL':'jdbc:postgresql://127.0.0.1:1234/acp_runtime'}),patch('subprocess.Popen') as launch:
   with bind_owned_backend(['acp-06-runtime-owned']):
    with self.assertRaisesRegex(ValueError,'UNOWNED_DATABASE_BINDING'):subprocess.Popen(['java','acp.browser.BrowserServer'],env={'ACP_DATABASE_URL':'jdbc:postgresql://production/db'})
   launch.assert_not_called()
 def test_replay_allows_only_append_of_the_same_authorized_classification_read(self):
  row={'id':1,'occurred_at':'old','mode':'READ','tenant':'tenant-a','subject':'user','operation':'QUERY','resource':'fixture','field':'summary'}
  before={'acp_classification_audit':[row],'acp_audit':[{'operation':'COMMITTED'}]};after=copy.deepcopy(before);after['acp_classification_audit'].append(dict(row,id=2,occurred_at='new'))
  self.assertEqual(verify_replay_state(before,after),1)
  for change in ('tenant','mode','old-row','business'):
   bad=copy.deepcopy(after)
   if change=='tenant':bad['acp_classification_audit'][1]['tenant']='other'
   elif change=='mode':bad['acp_classification_audit'][1]['mode']='WRITE'
   elif change=='old-row':bad['acp_classification_audit'][0]['occurred_at']='tampered'
   else:bad['acp_audit'].append({'operation':'DUPLICATED'})
   with self.assertRaises(ValueError):verify_replay_state(before,bad)
  before['acp_idempotency']=[{'identity':'key','owner':'winner','status':'COMMITTED_RESULT','commit_xid':'17','commit_ns':None}]
  after=copy.deepcopy(before);after['acp_idempotency'][0]['commit_ns']=123456
  with self.assertRaisesRegex(ValueError,'TIMESTAMP_UNVERIFIED'):verify_replay_state(before,after)
  self.assertEqual(verify_replay_state(before,after,{'17':123456}),0)
  with self.assertRaisesRegex(ValueError,'TIMESTAMP_UNVERIFIED'):verify_replay_state(before,after,{'17':999999})
  after['acp_idempotency'][0]['owner']='forged'
  with self.assertRaisesRegex(ValueError,'IDEMPOTENCY_CHANGED'):verify_replay_state(before,after,{'17':123456})
 def test_existing_proxy_and_stable_test_auth_are_not_production_implementations(self):
  for d,port in [('payment',4173),('case-management',4174)]:self.assertIn("listen("+str(port)+",'127.0.0.1')",proxy_source(d))
  self.assertIn('ACP_DEMO_AUTH_EVENT',stable_server('var now=Instant.now();return Jwt'))
  with self.assertRaisesRegex(ValueError,'TEST_AUTH_EVENT_BINDING'):stable_server('changed source')

if __name__=='__main__':unittest.main()
