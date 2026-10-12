"""Retained population verification rejects independently rehashed drift."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'audit'))
from retained_inventory import digest,population_digest,verify,writer_inventory

class RetainedInventoryTests(unittest.TestCase):
 def setUp(self):
  self.writers={'sources':[{'path':'fixture.py','digest':'sha256:pinned'}]}
  self.body={'domain':'payment','applicationId':'APP-FIXTURE','database':{'database':'reference','schema':'frozen','captureTimestamp':'first','transactionSnapshot':'snapshot'},'tables':{'owner':[{'id':'01','tenant':'10','field':'abcd'},{'id':'02','tenant':'20','field':'ef'}]},'writerInventoryDigest':digest(self.writers)}
  self.frozen=self.seal(copy.deepcopy(self.body))
 def seal(self,body):
  body['populationDigest']=population_digest(body)
  return {'body':body,'inventoryDigest':digest(body)}
 def reject(self,mutate):
  body=copy.deepcopy(self.body);mutate(body)
  with self.assertRaises(ValueError):verify(self.frozen,self.seal(body),self.writers)
 def test_read_only_recapture_allows_timestamp_change_only(self):
  body=copy.deepcopy(self.body);body['database']['captureTimestamp']='later';body['database']['transactionSnapshot']='new snapshot'
  self.assertEqual('PASS',verify(self.frozen,self.seal(body),self.writers)['result'])
 def test_missing_row(self):self.reject(lambda b:b['tables']['owner'].pop())
 def test_extra_row(self):self.reject(lambda b:b['tables']['owner'].append({'id':'03','tenant':'10','field':'abcd'}))
 def test_changed_tenant(self):self.reject(lambda b:b['tables']['owner'][0].update(tenant='99'))
 def test_modified_stored_bytes(self):self.reject(lambda b:b['tables']['owner'][0].update(field='abce'))
 def test_unexpected_writer(self):
  with self.assertRaisesRegex(ValueError,'WRITER_DRIFT'):verify(self.frozen,self.frozen,{'sources':self.writers['sources']+[{'path':'new_import.py','digest':'sha256:extra'}]})
 def test_database_mismatch(self):self.reject(lambda b:b['database'].update(database='other'))
 def test_schema_mismatch(self):self.reject(lambda b:b['database'].update(schema='other'))
 def test_stale_population_digest(self):
  observed=copy.deepcopy(self.frozen);observed['body']['populationDigest']='sha256:stale';observed['inventoryDigest']=digest(observed['body'])
  with self.assertRaisesRegex(ValueError,'INVALID_INVENTORY_DIGEST'):verify(self.frozen,observed,self.writers)
 def test_wrong_application(self):self.reject(lambda b:b.update(applicationId='APP-CASE-MANAGEMENT'))
 def test_runtime_drift(self):self.reject(lambda b:b['tables'].update(acp_outbox=[{'payload':'01'}]))
 def test_new_source_even_without_literal_sql_is_a_writer_boundary_change(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'tooling').mkdir();(root/'tooling/seed.py').write_text('provision()\n')
   old=writer_inventory(root);(root/'tooling/import.py').write_text('dynamic_driver.write(payload)\n')
   self.assertNotEqual(digest(old),digest(writer_inventory(root)))
class PublishedReferenceInventoryTests(unittest.TestCase):
 def test_both_measured_populations_and_all_negative_checks(self):
  from retained_inventory import ROOT
  from prepare_measured_binding_review import negative_checks
  evidence=ROOT/'targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12'
  writers=json.loads((evidence/'writers.json').read_bytes())
  self.assertEqual(writers,writer_inventory())
  for domain in ('payment','case-management'):
   frozen=json.loads((evidence/(domain+'.json')).read_bytes())
   recapture=json.loads((evidence/(domain+'-recapture.json')).read_bytes())
   self.assertEqual('PASS',verify(frozen,recapture,writers)['result'])
   self.assertEqual(3,len(frozen['body']['population']))
   checks=negative_checks(frozen,writers)
   self.assertEqual(9,len(checks));self.assertTrue(all(x['result']=='REJECTED' for x in checks.values()))
if __name__=='__main__':unittest.main()
