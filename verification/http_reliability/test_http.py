import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from engineering.http_reliability.target import HttpTarget,source_digest,PARENT
from engineering.http_reliability.fixture import adapter_source
from engineering.http_reliability.scenarios import WORKLOAD,check_no_business_writes,public_response
from engineering.operations.target import OperationalTarget
from engineering.source_intelligence.model import sha
class HttpTests(unittest.TestCase):
 def test_parent_unchanged(self):self.assertEqual(OperationalTarget().bundle,PARENT)
 def test_distinct_qualification_identity(self):self.assertNotEqual(HttpTarget().generator,OperationalTarget().generator);self.assertEqual(HttpTarget().descriptor()['scope'],'QUALIFICATION_ONLY')
 def test_source_substitution_rejected(self):
  target=HttpTarget()
  with patch('engineering.http_reliability.target.source_digest',return_value='0'*64):
   with self.assertRaisesRegex(ValueError,'H9_SOURCE_CHANGED'):target._verify()
 def test_parent_substitution_rejected(self):
  target=HttpTarget()
  with patch('engineering.http_reliability.target.parent_digest',return_value='0'*64):
   with self.assertRaisesRegex(ValueError,'H9_SOURCE_CHANGED'):target._verify()
 def test_one_exact_missing_class_only(self):
  s=Path('engineering/http_reliability/target.py').read_text();self.assertIn('error.getClass()==org.springframework.web.servlet.resource.NoResourceFoundException.class',s);self.assertNotIn('instanceof',s);self.assertNotIn('getMessage()',s)
 def test_parent_mapping_falls_through(self):
  original=Path('targets/spring-vue-postgres/templates/backend/src/main/java/acp/api/Errors.java').read_text();path='backend/src/main/java/acp/api/Errors.java'
  rows=[{'path':path,'text':original,'origins':['REQ-CASE']},{'path':'acp/target-upgrade.json','text':'{}'},{'path':'acp/provenance.json','text':json.dumps({'build':{},'artifacts':[{'artifact':path}]})}]
  target=HttpTarget()
  with patch('engineering.operations.target.OperationalTarget._call',return_value=rows):result=target._call('plan',{})
  by={r['path']:r for r in result};branch='if(error.getClass()==org.springframework.web.servlet.resource.NoResourceFoundException.class) return ResponseEntity.status(404).body(new ErrorResponse("RESOURCE_NOT_FOUND","HTTP",false));\n        '
  self.assertEqual(by[path]['text'].count(branch),1);self.assertEqual(by[path]['text'].replace(branch,''),original)
  provenance=json.loads(by['acp/provenance.json']['text']);self.assertEqual(provenance['artifacts'][0]['artifactDigest'],'sha256:'+sha(by[path]['text'].encode()));self.assertEqual(provenance['build']['generator'],'acp-h9-http-generator/1')

 def test_fixture_has_no_trusted_decoder(self):self.assertNotIn('@Bean JwtDecoder',adapter_source());self.assertNotIn('browser-authorized',adapter_source())
 def test_correlation_is_server_derived(self):s=adapter_source();self.assertIn('res.getHeader("X-ACP-Correlation")',s);self.assertNotIn('req.getHeader("X-ACP-Correlation")',s)
 def test_observer_does_not_replace_handlers(self):self.assertIn('return null;',adapter_source());self.assertNotIn('getMessage()',adapter_source())
 def test_study_is_bounded_without_retries(self):self.assertLessEqual(sum(v['requests'] for v in WORKLOAD['variants']),WORKLOAD['maximumAttempts']);self.assertLessEqual(max(v['clients'] for v in WORKLOAD['variants']),8);self.assertFalse(WORKLOAD['automaticRetries'])
 def test_negative_business_change_rejected(self):
  check_no_business_writes({'cases':1},{'cases':1})
  with self.assertRaisesRegex(ValueError,'H9_NEGATIVE_BUSINESS_WRITE'):check_no_business_writes({'cases':1},{'cases':2})
 def test_public_response_excludes_business_values(self):
  r=public_response({'status':500,'value':{'code':'INTERNAL_ERROR','category':'INTERNAL','retryable':False,'secret':'do-not-export'},'correlation':'x'});self.assertNotIn('do-not-export',json.dumps(r));self.assertNotIn('secret',r['envelope'])

 def test_resource_variant_is_not_original_failure(self):
  from engineering.http_reliability.diagnostics import classify
  result=classify([{'variant':'pressure','response':{'status':500,'correlation':'x'}}],[{'id':'pressure','pool':4}]);self.assertEqual(result['studyOutcome'],'INJECTED_ANALOGOUS_FAILURE');self.assertEqual(result['normalProfile500s'],0)
 def test_normal_failure_never_claims_historical_cause(self):
  from engineering.http_reliability.diagnostics import classify
  result=classify([{'variant':'normal','response':{'status':500,'correlation':'x'}}],[{'id':'normal','pool':34}]);self.assertEqual(result['studyOutcome'],'CURRENT_PROFILE_FAILURE_CAUSE_UNRESOLVED');self.assertEqual(result['historicalCause'],'UNRESOLVED_NOT_CAUSALLY_ATTRIBUTED')
 def test_no_http_success_is_not_fabricated_as_a_commit(self):
  from engineering.http_reliability.diagnostics import ledger
  class Lab:
   class DB:
    def data(self,statement):return []
   db=DB()
  self.assertEqual(ledger(Lab(),'a'*64,'tenant','subject')['outcome'],'NO_COMMITTED_EFFECT_OBSERVED')

 def test_identity_matches_actual_native_java_reference(self):
  from engineering.http_reliability.diagnostics import identity
  self.assertEqual(identity('CREATE-CASE',1,'tenant-one','fixture:operator','h9-serial-0'),'bce03969a559d200aac4e2a25a9d5715c3999deef8daf79f14add7e2c6d44b1b')
