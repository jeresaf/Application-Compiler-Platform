"""Security qualification invariants; live sandbox/build/scan runs are separate."""
import ast
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.security.qualification import assess_response,sandbox_source,READINESS_TEST,https_json,sha,resolve_backend_components

class SecurityTests(unittest.TestCase):
 def test_exact_sandbox_function_not_reimplementation(self):
  function,binding=sandbox_source();self.assertEqual(binding,sha((ROOT/'targets/spring-vue-postgres/worker/main.py').read_bytes()));self.assertEqual(ast.parse(function).body[0].name,'sandbox');self.assertIn('seccomp_load',function)
 def test_missing_scanner_results_rejected(self):
  for response in ({},{'results':[]},{'results':[{},{}]}):
   with self.subTest(response=response),self.assertRaisesRegex(ValueError,'INCOMPLETE_SCANNER_RESPONSE'):assess_response([{'name':'one'}],response,lambda _:None)
 def test_error_response_never_clean(self):
  with self.assertRaisesRegex(ValueError,'INVALID_SCANNER_RESULT'):assess_response([{}],{'results':[{'error':'unavailable'}]},lambda _:None)
 def test_wrong_advisory_rejected(self):
  with self.assertRaisesRegex(ValueError,'ADVISORY_IDENTITY'):assess_response([{}],{'results':[{'vulns':[{'id':'CVE-1'}]}]},lambda _:{'id':'CVE-2'})
 def test_unscored_not_dismissed(self):
  result=assess_response([{'ecosystem':'Maven','name':'one','version':'1'}],{'results':[{'vulns':[{'id':'CVE-1'}]}]},lambda _:{'id':'CVE-1','affected':[{'package':{'name':'one'}}]})
  self.assertEqual(result[0]['severityStatus'],'UNSCORED_BLOCKING');self.assertEqual(result[0]['disposition'],'REVIEW_REQUIRED')
 def test_scored_not_approved(self):
  result=assess_response([{}],{'results':[{'vulns':[{'id':'CVE-1'}]}]},lambda _:{'id':'CVE-1','severity':[{'type':'CVSS_V3','score':'vector'}]})
  self.assertEqual(result[0]['disposition'],'REVIEW_REQUIRED')
 def test_untrusted_scanner_url_rejected_before_network(self):
  for url in ('http://api.osv.dev/v1/querybatch','https://attacker.invalid/','https://api.osv.dev.attacker.invalid/'):
   with self.subTest(url=url),self.assertRaisesRegex(ValueError,'UNTRUSTED_SCANNER_ENDPOINT'):https_json(url)
 def test_identity_requires_exact_hash_bound_unambiguous_origin(self):
  def unknown():return {'hashes':[{'content':'hash'}],'name':'display-name','version':'not-authority'}
  locked={'one':{'sha256':'hash','lockedOrigins':['maven:org/example/lib/1.2/lib-1.2.jar']}}
  self.assertEqual(resolve_backend_components([unknown()],locked)[0]['purl'],'pkg:maven/org.example/lib@1.2')
  locked['two']={'sha256':'hash','lockedOrigins':['maven:other/group/lib/1.2/lib-1.2.jar']}
  self.assertNotIn('purl',resolve_backend_components([unknown()],locked)[0])
  self.assertNotIn('purl',resolve_backend_components([unknown()],{'wrong':{'sha256':'different','lockedOrigins':['maven:org/example/lib/1.2/lib-1.2.jar']}})[0])
 def test_test_adapter_excluded_from_main_source(self):
  self.assertNotIn('@SpringBootApplication',READINESS_TEST);self.assertIn('assertNull(jdbc.getDataSource())',READINESS_TEST);self.assertIn('missingPrincipalRejectedBeforeDatabaseAccess',READINESS_TEST)

if __name__=='__main__':unittest.main()
