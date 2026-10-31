"""Existing generated applications and existing real offline qualification checks."""
import copy,json,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from engineering.verification.integration import *
from engineering.verification.inputs import reference_inputs

class VerificationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.work=Path(os.environ['ACP_VERIFICATION_WORKSPACE']);cls.sessions={}
  for domain in ('payment','case-management'):
   app=cls.work/domain/domain;ref=cls.work/'reference'/domain
   cls.sessions[domain]=Session(app,ref/'source-baseline.json',(ref/'source-baseline.sha256').read_text().strip(),ref/'source-model.json',sha((ref/'source-model.json').read_bytes()))
  cls.results={d:s.evaluate() for d,s in cls.sessions.items()}
  for d,r in cls.results.items():(cls.work/d/'verification-result.json').write_bytes(encode(r))
  cls.hosted=None;cls.executed={}
  if os.environ.get('ACP_EXECUTION_EVIDENCE'):
   from engineering.verification.execution import HostedExecutions
   cls.hosted=HostedExecutions(Path(os.environ['ACP_EXECUTION_EVIDENCE']),os.environ['ACP_EXECUTION_EVALUATED_AT'])
   (cls.work/'github-api-observations.json').write_bytes(encode(cls.hosted.observations))
   for d,session in cls.sessions.items():
    cls.executed[d]=session.evaluate(execution=cls.hosted);(cls.work/d/'execution-verification-result.json').write_bytes(encode(cls.executed[d]))
 def test_both_approved_specifications_target_ir_source_and_artifacts_are_bound(self):
  for d,s in self.sessions.items():
   r=self.results[d];self.assertEqual(r['inputs']['canonicalDigest'],approved_snapshot(d)['contentDigest']);self.assertEqual(r['inputs']['artifactPlanDigest'],s.b['artifactPlanDigest']);self.assertEqual(r['inputs']['targetIRDigest'],fingerprint(s.target));self.assertEqual(r['inputs']['sourceModelDigest'],s.model['digest'])
   checks=[v for v in r['results'] if v['kind']=='ARTIFACT_VERIFICATION'];self.assertEqual(len(checks),sum(len(a.verification) for a in s.plan.artifacts));self.assertTrue(all(v['result']=='PASS' for v in checks));self.assertTrue(all(v['origins'] and v['artifacts'] for v in checks))
 def test_semantic_obligations_are_never_discharged_by_source_integrity(self):
  for d,s in self.sessions.items():
   rows=[r for r in self.results[d]['results'] if r['kind']=='SEMANTIC_OBLIGATION'];self.assertEqual({r['obligation']['id'] for r in rows},set(s.obligations));self.assertTrue(all(r['result']=='NOT_RUN' and r['obligation']['status']=='OUTSTANDING' for r in rows))
 def test_partial_source_does_not_pass_complete_traceability(self):
  for r in self.results.values():self.assertEqual(next(v for v in r['results'] if v['id']=='source-model-completeness')['result'],'BLOCKED')
 def test_operational_obligations_remain_blocked(self):
  for r in self.results.values():self.assertTrue(all(v['result']=='BLOCKED' for v in r['results'] if v['kind']=='DEPLOYMENT_OBLIGATION'));self.assertEqual(r['releaseDisposition'],'PHASE6_RELEASE_CLOSURE_BLOCKED')
 def test_repeated_results_are_deterministic_and_source_is_unchanged(self):
  for d,s in self.sessions.items():
   before={n:sha(read(s.root,n)) for n in s.b['files']};self.assertEqual(encode(s.evaluate()),encode(self.results[d]));self.assertEqual(before,{n:sha(read(s.root,n)) for n in s.b['files']})
 def test_not_executed_checks_remain_not_run(self):
  r=self.sessions['payment'].evaluate(False);self.assertTrue(all(v['result']=='NOT_RUN' for v in r['results'] if v['kind']=='ARTIFACT_VERIFICATION'))
 def test_retained_real_results_are_independently_rechecked(self):
  for d,s in self.sessions.items():self.assertEqual(s.verify_retained(self.results[d]),self.results[d])
 def test_missing_verification_result_is_rejected(self):
  s=self.sessions['payment'];r=copy.deepcopy(self.results['payment']);r['results'].pop();r['summary']=summary(r['results']);r=seal({k:v for k,v in r.items() if k!='digest'})
  with self.assertRaisesRegex(ValueError,'MISSING_OR_CHANGED_VERIFICATION_RESULT'):s.verify_retained(r)
 def test_fabricated_business_pass_is_rejected(self):
  s=self.sessions['payment'];r=copy.deepcopy(self.results['payment']);next(v for v in r['results'] if v['kind']=='SEMANTIC_OBLIGATION')['result']='PASS';r['summary']=summary(r['results']);r=seal({k:v for k,v in r.items() if k!='digest'})
  with self.assertRaisesRegex(ValueError,'MISSING_OR_CHANGED_VERIFICATION_RESULT'):s.verify_retained(r)
 def test_wrong_snapshot_target_generator_tool_and_source_model_fail_closed(self):
  s=self.sessions['payment']
  for key in ('canonicalDigest','domain','targetIRDigest','generator','executorSHA256','sourceModelDigest','artifactPlanDigest'):
   r=copy.deepcopy(self.results['payment']);r['inputs'][key]='unrelated';r=seal({k:v for k,v in r.items() if k!='digest'})
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'STALE_OR_MISMATCHED_EVIDENCE'):s.verify_retained(r)
  detached=s.evaluate();detached['inputs']['canonicalDigest']='caller-edited'
  self.assertEqual(s.inputs['canonicalDigest'],approved_snapshot('payment')['contentDigest'])
  detached=seal({k:v for k,v in detached.items() if k!='digest'})
  with self.assertRaisesRegex(ValueError,'STALE_OR_MISMATCHED_EVIDENCE'):s.verify_retained(detached)
 def test_cross_application_evidence_is_rejected(self):
  with self.assertRaisesRegex(ValueError,'STALE_OR_MISMATCHED_EVIDENCE'):self.sessions['payment'].verify_retained(self.results['case-management'])
 def mutation(self,remove=False):
  s=self.sessions['payment'];p=s.root/'frontend/src/api.ts';raw=p.read_bytes()
  try:
   if remove:p.unlink()
   else:p.write_bytes(raw+b'\n')
   r=s.evaluate();self.assertGreater(r['summary']['FAIL'],0);self.assertEqual(next(v for v in r['results'] if v['id']=='source-model-binding')['result'],'BLOCKED');self.assertEqual(r['summary']['PASS'],0)
   with self.assertRaises(ValueError):s.verify_retained(self.results['payment'])
  finally:p.write_bytes(raw)
 def test_altered_source_fails_real_existing_executor_and_blocks_stale_evidence(self):self.mutation()
 def test_missing_source_fails_closed(self):self.mutation(True)
 def test_invalid_source_model_file_hash_is_rejected(self):
  s=self.sessions['payment']
  with self.assertRaisesRegex(ValueError,'SOURCE_MODEL_FILE_DIGEST'):load_model(s.model_path,'0'*64)
 def test_changed_retained_model_bytes_invalidate_results(self):
  s=self.sessions['payment'];p=s.model_path;raw=p.read_bytes()
  try:
   p.write_bytes(raw+b'\n');r=s.evaluate();self.assertEqual(r['summary']['PASS'],0);self.assertEqual(next(v for v in r['results'] if v['id']=='source-model-binding')['result'],'BLOCKED')
  finally:p.write_bytes(raw)
 def test_unknown_status_duplicate_and_corrupted_digest_are_rejected(self):
  for mode in ('status','duplicate','digest'):
   r=copy.deepcopy(self.results['payment'])
   if mode=='status':r['results'][0]['result']='SKIP'
   if mode=='duplicate':r['results'].append(r['results'][0])
   if mode!='digest':r=seal({k:v for k,v in r.items() if k!='digest'})
   else:r['digest']='0'*64
   with self.subTest(mode=mode),self.assertRaises(ValueError):validate_result(r)
 def test_evidence_executor_port_binds_inputs_and_retains_full_result(self):
  s=self.sessions['payment'];output=self.work/'port-result.json';port=ExistingEvidenceExecutor(s,output);request=Document.of({'schema':'acp-verification-request/1','operation':'VERIFY','inputsDigest':digest(s.inputs)})
  self.assertTrue(all(v.startswith('sha256:') and len(v)==71 for v in s.input_digests))
  try:
   result=port.execute(request,s.input_digests).read();self.assertEqual(result['fileSHA256'],sha(output.read_bytes()));self.assertEqual(json.loads(output.read_bytes()),self.results['payment'])
   with self.assertRaisesRegex(ValueError,'EXECUTION_INPUT_DIGESTS'):port.execute(request,('unrelated',))
   with self.assertRaisesRegex(ValueError,'EXECUTION_REQUEST'):port.execute(Document.of({'schema':'unregistered'}),s.input_digests)
  finally:output.unlink(missing_ok=True)
 def test_source_analysis_archive_substitution_is_rejected(self):
  p=self.work/'substituted.zip';p.write_bytes(b'not the accepted Phase 7 artifact')
  try:
   with self.assertRaisesRegex(ValueError,'PHASE7_ARCHIVE_DIGEST'):reference_inputs(p,self.work/'bad-reference')
  finally:p.unlink()

 def test_hosted_build_runtime_and_migration_results_bind_both_applications(self):
  from engineering.verification.execution import FAMILIES,PRODUCER
  self.assertIsNotNone(self.hosted,'LIVE_HOSTED_EVIDENCE_REQUIRED')
  for d,r in self.executed.items():
   by={row['id']:row for row in r['results']}
   for family in FAMILIES:
    row=by['execution:'+family];self.assertEqual(row['observation']['execution']['sourceCommit'],PRODUCER)
    if family!='dependency-security-assessment':self.assertEqual(row['result'],'PASS',(d,family,row['reasons']))
   self.assertEqual(r['inputs']['executionEvidence']['authority'],'AUTHENTICATED_GITHUB_API')
 def test_partial_source_does_not_block_independent_execution(self):
  for r in self.executed.values():
   by={row['id']:row for row in r['results']};self.assertEqual(by['source-model-completeness']['result'],'BLOCKED')
   self.assertEqual(by['execution:backend-build']['result'],'PASS');self.assertEqual(by['execution:migration-failure-recovery']['result'],'PASS')
 def test_only_existing_assertion_mapped_semantic_obligations_are_promoted(self):
  for d,r in self.executed.items():
   passed=[v for v in r['results'] if v['kind']=='SEMANTIC_OBLIGATION' and v['result']=='PASS']
   self.assertEqual(len(passed),1);self.assertEqual({o['id'] for o in passed[0]['origins']},{'BOUNDARY-TASK'})
   self.assertTrue(all(v['result']=='NOT_RUN' for v in r['results'] if v['kind']=='SEMANTIC_OBLIGATION' and v not in passed))
 def test_scanner_findings_remain_visible_and_do_not_mean_clean_security(self):
  for r in self.executed.values():
   row=next(v for v in r['results'] if v['id']=='execution:dependency-security-assessment')
   self.assertIn(row['result'],('FAIL','BLOCKED'));self.assertTrue(row['observation']['evidence']['findings'] or row['observation']['evidence']['unknown'] or row['observation']['evidence']['unresolvedEmbeddedBuildArtifacts'])
 def altered_hosted(self,kind,change):
  import copy
  value=copy.copy(self.hosted);value.assets=copy.deepcopy(self.hosted.assets);value.witnesses=dict(self.hosted.witnesses);change(value.assets[kind]['report']);return value
 def test_wrong_execution_application_and_canonical_are_rejected(self):
  for key in ('snapshot','canonical'):
   value=self.altered_hosted('demonstration',lambda r:r['applications']['payment'].__setitem__(key,'wrong'))
   self.assertFalse(any(v['result']=='PASS' for v in self.sessions['payment'].evaluate(execution=value)['results'] if v['kind']=='EXECUTION_OBLIGATION' and v['observation']['execution']['job']==self.hosted.assets['demonstration']['job']['id']))
 def test_stale_and_future_execution_timestamps_fail_closed(self):
  import copy
  from datetime import timedelta
  from engineering.verification.execution import instant
  for offset in (-2,2):
   value=copy.copy(self.hosted);value.evaluated_at=(instant(self.hosted.evaluated_at)+timedelta(days=offset)).isoformat();value.context=copy.deepcopy(self.hosted.context);value.context['executionEvidence']['evaluatedAt']=value.evaluated_at
   r=self.sessions['payment'].evaluate(execution=value);self.assertTrue(all(v['result']!='PASS' for v in r['results'] if v['kind']=='EXECUTION_OBLIGATION'))
 def test_changed_dependency_locks_and_test_executor_identities_are_rejected(self):
  from unittest.mock import patch
  from engineering.verification import execution
  value=self.altered_hosted('demonstration',lambda r:r['sourceHashes'].__setitem__('engineering/dependency_resolution/maven-artifacts.lock.json','0'*64))
  r=self.sessions['payment'].evaluate(execution=value);self.assertEqual(next(v for v in r['results'] if v['id']=='execution:backend-build')['result'],'BLOCKED')
  with patch.object(execution,'source_closure',side_effect=ValueError('CHANGED_EXECUTOR')):
   unavailable=execution.HostedExecutions(self.hosted.directory,self.hosted.evaluated_at)
  self.assertFalse(unavailable.assets)
 def test_forged_pass_report_cannot_replace_authenticated_artifact_bytes(self):
  value=self.altered_hosted('demonstration',lambda r:r.__setitem__('arbitrary','PASS'))
  r=self.sessions['payment'].evaluate(execution=value);self.assertEqual(next(v for v in r['results'] if v['id']=='execution:browser-e2e')['result'],'BLOCKED')
 def test_missing_required_results_and_conflicting_reports_fail_closed(self):
  from unittest.mock import patch
  original=self.hosted.json
  for path in ('runtime-results.json','payment-runtime/business-browser.json'):
   def changed(kind,name):
    r=original(kind,name)
    if kind=='demonstration' and name==path:
     if name=='runtime-results.json':r['applications']={}
     else:r['stats']['expected']=0
    return r
   with patch.object(self.hosted,'json',side_effect=changed):r=self.sessions['payment'].evaluate(execution=self.hosted)
   self.assertEqual(next(v for v in r['results'] if v['id']=='execution:browser-e2e')['result'],'BLOCKED')
 def test_changed_archive_and_missing_execution_evidence_never_pass(self):
  import copy
  value=copy.copy(self.hosted);value.assets=copy.deepcopy(self.hosted.assets);p=self.work/'wrong-execution.zip';p.write_bytes(b'forged')
  try:
   value.assets['demonstration']['path']=p;r=self.sessions['payment'].evaluate(execution=value)
   self.assertEqual(next(v for v in r['results'] if v['id']=='execution:backend-build')['result'],'BLOCKED')
   value.assets={};value.errors={};r=self.sessions['payment'].evaluate(execution=value);self.assertTrue(all(v['result']=='BLOCKED' for v in r['results'] if v['kind']=='EXECUTION_OBLIGATION'))
  finally:p.unlink()
 def test_live_authority_outage_cannot_be_replaced_by_local_checksum_claims(self):
  from unittest.mock import patch
  from engineering.verification import execution
  with patch.object(execution,'source_closure',return_value=self.hosted.closure),patch.object(execution,'api',side_effect=ValueError('API_OUTAGE')):
   value=execution.HostedExecutions(self.hosted.directory,self.hosted.evaluated_at)
  self.assertFalse(value.assets);r=self.sessions['payment'].evaluate(execution=value);self.assertTrue(all(v['result']=='BLOCKED' for v in r['results'] if v['kind']=='EXECUTION_OBLIGATION'))
  with patch.object(execution.subprocess,'check_output',return_value=b'{}') as transport:
   execution.api('repos/'+execution.REPOSITORY+'/actions/runs/'+str(execution.RUN))
   self.assertEqual(transport.call_args.args[0][:4],['gh','api','--hostname','github.com'])
 def test_execution_results_reproduce_and_replay_under_identical_declared_inputs(self):
  for d,s in self.sessions.items():self.assertEqual(s.verify_retained(self.executed[d],execution=self.hosted),self.executed[d])
