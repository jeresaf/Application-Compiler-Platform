import copy,json,tempfile,unittest
from pathlib import Path
from engineering.jobs import semantics as s
from engineering.jobs.reference import proposal
from engineering.documents.reference import proposal as parent
from engineering.jobs.schema import schemas,CONTRACTS
from engineering.jobs.application import materialize

class Semantics(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.source=proposal();cls.snapshot=s.normalize_candidate(cls.source)
 def reject(self,identity,**change):
  a=copy.deepcopy(self.source);next(n for n in a['nodes'] if n['id']==identity)['data'].update(change)
  with self.assertRaises(ValueError):s.normalize_candidate(a)
 def test_closed_contracts(self):
  for name,value in zip(('authoring-0.8.schema.json','canonical-0.7.schema.json'),schemas()):self.assertEqual(json.loads((CONTRACTS/name).read_bytes()),value)
 def test_prior_semantics_exact(self):
  nodes={n['id']:n for n in self.source['nodes']}
  for n in parent()['nodes']:self.assertEqual(nodes[n['id']],n)
 def test_candidate_cannot_approve_itself(self):
  for authority in (None,lambda q:'approved'):
   with self.assertRaises(ValueError):s.admit(self.snapshot,authority)
 def test_schedule_bounds(self):
  for x in (0,3601):self.reject('SCHEDULE-INTEGRITY',intervalSeconds=x)
 def test_anchor_precision(self):self.reject('SCHEDULE-INTEGRITY',anchorInstant='2026-11-01T00:00:00.5Z')
 def test_retry_bounds(self):self.reject('RETRY-INTEGRITY',maxAttempts=6)
 def test_failure_identity(self):self.reject('FAIL-JOB-TIMEOUT',code='UNRELATED')
 def test_lease_exceeds_timeout(self):self.reject('JOB-INTEGRITY',leaseSeconds=2)
 def test_no_manual_trigger(self):self.reject('JOB-INTEGRITY',manualTrigger='ALLOW')
 def test_no_content_mutation(self):self.reject('JOB-INTEGRITY',contentMutation='REPAIR')
 def test_no_interactive_impersonation(self):self.reject('WORKER-INTEGRITY',binding='USER_JWT')
 def test_owner_binding(self):self.reject('PERM-JOB-READ',principalField={'id':'CASE-TENANT','revision':2})
 def test_unknown_privilege(self):self.reject('WORKER-INTEGRITY',privileges=['EXECUTE_COMMAND'])
 def test_stale_digest(self):
  a=copy.deepcopy(self.snapshot);a['contentDigest']='sha256:'+'0'*64
  with self.assertRaises(ValueError):s.validate_snapshot(a)

class Pipeline(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='acp-jobs-unit-');cls.root=Path(cls.tmp.name)/'application';cls.c,cls.s,cls.r,cls.p=materialize(cls.root)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_human_owned_replanning_within_unchanged_budget(self):
  from filesystem_artifacts import FilesystemArtifactStore
  from engineering.reference_application.lifecycle import HUMAN
  store=FilesystemArtifactStore(self.root);store.adopt_human(HUMAN);path=self.root/HUMAN;path.write_bytes(path.read_bytes()+b'\n// preserved human extension\n');plan=self.c.plan(self.s,self.r,store.inventory());self.assertTrue(plan.artifacts)
 def test_eight_stages(self):self.assertEqual(len(self.c.audit.stages),8);self.assertEqual(self.c.audit.status,'COMPLETE')
 def test_worker_has_no_interactive_jwt(self):
  text=(self.root/'backend/src/main/java/acp/api/IntegrityWorker.java').read_text();self.assertNotIn('Jwt',text);self.assertIn('ServiceContext',text);self.assertIn('SKIP LOCKED',text);self.assertIn('FENCED_RESULT',text)
 def test_durable_unique_effects(self):
  text=(self.root/'backend/src/main/resources/db/migration/V5__integrity_jobs.sql').read_text();self.assertIn('UNIQUE(job,tenant,occurrence,document)',text);self.assertIn('REFERENCES acp_audit(id)',text);self.assertIn('_attempt',text)
 def test_read_only_ui(self):
  text=(self.root/'frontend/src/JobPanel.vue').read_text();self.assertIn('Refresh jobs',text);self.assertNotIn('Run job',text)
 def test_complete_provenance_survives_runtime_projection(self):
  ir=json.loads((self.root/'contracts/target-ir.json').read_bytes());self.assertEqual(ir['schema'],'acp-runtime-target-projection/1');self.assertIn('fullTargetIRDigest',ir)
