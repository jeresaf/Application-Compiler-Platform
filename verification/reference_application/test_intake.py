"""Synthetic creation-target contracts and preservation; no semantic approval."""
import copy,json,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from engineering.reference_application import intake as i
from compiler_contracts import Document,fingerprint
from compiler_core import CompilerFault
from filesystem_artifacts import StoreConflict
from engineering.verification.integration import seal,summary

class Intake(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.s,cls.contract,cls.native=i.proposal();cls.c=i.IntakeCandidate();cls.r=i.make_request(cls.c,cls.s);cls.t=cls.c.base.lower(cls.s,compiler=cls.r.compiler,pipeline=cls.r.pipeline)
 def lower(self,c):return i.lower_contract(self.s,c,self.t)
 def test_requirements_only_native_proposal_does_not_invent_command(self):
  self.assertEqual({d['after']['kind'] for d in self.native['diff']},{'Requirement','AcceptanceCriterion'})
  self.assertEqual(self.native['change']['migration']['mode'],'NONE')
  self.assertNotEqual(self.s.read()['contentDigest'],self.native['change']['base']['digest'])
 def test_closed_create_lowering_and_explicit_server_bindings(self):
  c=self.lower(self.contract);self.assertIn('INSERT INTO e_',c['insertSQL']);self.assertEqual(c['insertSQL'].count('?'),5);self.assertIn("'STATE-OPEN'",c['insertSQL']);self.assertIn('SELECT count(*)',c['principalSQL'])
  self.assertEqual({b['name'] for b in c['orderedInputs']},{'title','summary'})
 def test_unsupported_scope_operation_authority_and_policy_reject(self):
  for key,value in [('scope','PRODUCTION'),('schema','unknown'),('operation','UPSERT'),('authority','APPROVED'),('routing','ARBITRARY_CODE'),('idempotencySeconds',0)]:
   c=copy.deepcopy(self.contract);c[key]=value
   with self.assertRaises(ValueError):self.lower(c)
  c={**self.contract,'shell':'arbitrary'}
  with self.assertRaises(ValueError):self.lower(c)
 def test_identity_tenant_initial_state_and_ownership_reject(self):
  for key,value in [('identity','USER-ID'),('tenant','USER-TENANT'),('initialState','STATE-ARCHIVED'),('role','REQ-CASE')]:
   c=copy.deepcopy(self.contract);c[key]=value
   with self.assertRaises(ValueError):self.lower(c)
 def test_missing_duplicate_and_unsupported_fields_reject(self):
  c=copy.deepcopy(self.contract);del c['inputs']['summary']
  with self.assertRaisesRegex(ValueError,'FIELD_COVERAGE'):self.lower(c)
  c=copy.deepcopy(self.contract);c['inputs']['title']['member']=None
  with self.assertRaisesRegex(ValueError,'UNSUPPORTED_TYPE'):self.lower(c)
  c=copy.deepcopy(self.contract);c['inputs']['title']['field']='CASE-ID'
  with self.assertRaises(ValueError):self.lower(c)
  c=copy.deepcopy(self.contract);c['inputs']['title']['maxLength']=-1
  with self.assertRaises(ValueError):self.lower(c)
 def test_proposal_or_template_substitution_invalidates_identity(self):
  real=Path.read_bytes
  with patch.object(Path,'read_bytes',lambda p:real(p)+b' ' if p==i.PROPOSAL/'change.json' else real(p)):
   with self.assertRaisesRegex(ValueError,'SUBSTITUTED'):i.proposal()
  with patch.object(Path,'read_bytes',lambda p:real(p)+b' ' if p==i.TEMPLATES/'IntakeForm.vue' else real(p)):
   with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):self.c._verify()
 def test_native_cas_regeneration_and_candidate_bound_provenance(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'app';store=i.FilesystemArtifactStore(root);p=self.c.plan(self.s,self.r);store.apply(p);store.adopt_human(i.life.HUMAN);human=(root/i.life.HUMAN).read_bytes()+b'\n// owned\n';(root/i.life.HUMAN).write_bytes(human)
   p=self.c.plan(self.s,self.r,store.inventory());fingerprint(p);store.apply(p);self.c.verify_materialized(root,p,self.s,self.r);self.assertEqual((root/i.life.HUMAN).read_bytes(),human)
   for name in ('frontend/src/IntakeForm.vue','frontend/src/App.vue','backend/src/main/java/acp/api/IntakeController.java'):
    a=next(a for a in p.artifacts if a.path==name);self.assertIn('REQ-R3-INTAKE',{o.id for o in a.mappings})
   core=(root/'backend/src/main/java/acp/infrastructure/InvocationCore.java').read_text().split('public boolean syntheticToken',1)[1];self.assertLess(core.index('lockRates'),core.index('time.now()'));self.assertIn('return debit(',core);self.assertIn('instant.signum()<0',core)
   f=root/'frontend/src/IntakeForm.vue';f.write_bytes(f.read_bytes()+b'changed')
   with self.assertRaises(StoreConflict):store.inventory()
 def test_generation_is_off_by_default_and_uses_existing_security_and_transactions(self):
  text=(i.TEMPLATES/'IntakeController.java').read_text();self.assertIn('@ConditionalOnProperty(name="acp.intake.mode",havingValue="synthetic-preview")',text)
  for needed in ('policy.actor(jwt)','invocations.invoke','InvocationCore.replay','InvocationCore.capture','store.audit','SUBJECT_TENANT_BINDING'):self.assertIn(needed,text)
  self.assertNotIn('fixture:operator',text);self.assertNotIn('CASE-ID',text)
 def test_original_mcp_boundary_rejects_candidate_instead_of_aliasing(self):
  from engineering.mcp_adapter.service import Application
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);cfg={'root':str(root)}
   result=seal({'schema':'acp-verification-result/1','scope':'QUALIFICATION_ONLY','inputs':{},'results':[],'summary':summary([]),'releaseDisposition':'PHASE6_RELEASE_CLOSURE_BLOCKED'})
   values={'baseline':{'domain':'case-management','canonicalDigest':self.s.read()['contentDigest']},'model':{'deliberatelyInvalidNegativeInput':True},'verification':result,'plan':{}}
   for key,value in values.items():
    p=root/(key+'.json');p.write_bytes(i.encode(value));cfg[key]={'path':str(p),'sha256':i.sha(p.read_bytes())}
   with self.assertRaisesRegex(ValueError,'APPROVED_CANONICAL_IDENTITY'):Application(cfg)
 def test_immutable_parent_canonical_predicates_and_r2_evidence(self):
  self.assertEqual(i.life.bundle_digest(),'ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb')
  from engineering.generator_candidates.spring_vue_postgres_0_6.candidate import source_digest
  self.assertEqual(source_digest(),'600a552287cc1121be7578c31ba2a379332c9b0d55c60a79b2a5d054c92271aa')
  for name in ('tooling/audit/criteria.py','tooling/audit/phase6.py','engineering/reference_application/evolution.py','proposals/phase6-evolution-review/case-management-change.json'):
   self.assertEqual((i.ROOT/name).read_bytes(),subprocess.check_output(['git','show','a4e6cb96e6544318d25e52006205480ef9d45c24:'+name]))
if __name__=='__main__':unittest.main()
