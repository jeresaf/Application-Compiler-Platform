import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from dataclasses import replace
from engineering.reporting import semantics as s,compiler as compiler
from engineering.reporting.schema import schemas,CONTRACTS,FEATURES
from engineering.reporting.reference import proposal
from engineering.compiler_extensions.dispatch import kernel
from engineering.reporting.application import materialize
from engineering.native_create import semantics as create
from canonical_ir import CanonicalError
from compiler_contracts import Failure,Document,fingerprint
from filesystem_artifacts import FilesystemArtifactStore,StoreConflict
import compiler_core

class Semantics(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.source=proposal();cls.snapshot=s.normalize_candidate(cls.source)
 def reject(self,fn):
  v=copy.deepcopy(self.source);nodes={n['id']:n for n in v['nodes']};fn(v,nodes)
  with self.assertRaises((ValueError,KeyError)):s.normalize_candidate(v)
 def test_schemas_are_exact_and_versioned(self):
  for name,value in zip(('authoring-0.6.schema.json','canonical-0.5.schema.json'),schemas()):self.assertEqual(json.loads((CONTRACTS/name).read_bytes()),value)
  self.assertEqual(s.validate_snapshot(self.snapshot),self.snapshot)
 def test_structural_validity_is_not_human_acceptance(self):
  with self.assertRaises(CanonicalError):s.admit(self.snapshot)
  with self.assertRaises(CanonicalError):s.admit(self.snapshot,lambda q:'approved')
  with self.assertRaises(CanonicalError):create.validate_snapshot(self.snapshot)
 def test_sensitive_and_foreign_projections_reject(self):
  for id in ['FLD-NOTE','USER-ID']:
   self.reject(lambda v,n:n['REPORT-CASES']['data']['fields'].append({'field':{'id':id,'revision':n[id]['revision']},'member':None}))
 def test_filter_type_and_tenant_override_reject(self):
  self.reject(lambda v,n:n['REPORT-CASES']['data']['filters'][0].update(name='tenant'))
  self.reject(lambda v,n:n['REPORT-CASES']['data']['filters'][0].update(field={'id':'CASE-TENANT','revision':2}))
  self.reject(lambda v,n:n['REPORT-CASES']['data']['filters'][1].update(operation='CONTAINS'))
 def test_invalid_sort_pagination_and_mutation_reject(self):
  self.reject(lambda v,n:n['REPORT-CASES']['data']['orderBy'][0].update(field='arbitrary SQL'))
  self.reject(lambda v,n:n['REPORT-CASES']['data']['pagination'].update(defaultSize=21,maximumSize=20))
  self.reject(lambda v,n:n['REPORT-CASES']['data'].update(mutation='ALLOW'))
 def test_permission_scope_and_revision_reject(self):
  self.reject(lambda v,n:n['PERM-REPORT']['data']['actor'].update(revision=99))
  self.reject(lambda v,n:n['PERM-REPORT']['data'].update(principalField={'id':'CASE-TENANT','revision':2}))
  self.reject(lambda v,n:n['PERM-HISTORY']['data'].update(access='REPORT'))
 def test_audit_projection_and_wrong_resource_reject(self):
  self.reject(lambda v,n:n['HISTORY-CASES']['data'].update(projection=['operation','subject']))
  self.reject(lambda v,n:n['HISTORY-CASES']['data'].update(operations=[{'id':'EVT-REVIEW','revision':2}]))
 def test_view_mismatch_and_unknown_versions_reject(self):
  self.reject(lambda v,n:n['VIEW-REPORT']['data'].update(columns=[]))
  self.reject(lambda v,n:v.update(modelVersion='0.5.0'))
  v=copy.deepcopy(self.snapshot);v['content']['requiredFeatures'].append('unknown')
  with self.assertRaises(CanonicalError):s.validate_snapshot(v)
 def test_preserved_create_nodes_and_original_root_files(self):
  old=create.normalize_candidate(__import__('engineering.native_create.reference',fromlist=['proposal']).proposal())
  ids={n['id'] for n in old['content']['nodes']};self.assertEqual([n for n in self.snapshot['content']['nodes'] if n['id'] in ids],old['content']['nodes'])
  root=Path(__file__).resolve().parents[2]
  self.assertFalse(subprocess.check_output(['git','diff','96cd633','--','tooling','contracts','targets','engineering/native_create','proposals/phase10-r3-intake','proposals/phase10-r4-create'],cwd=root))

class Pipeline(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='acp-report-unit-');cls.root=Path(cls.tmp.name)/'app';cls.c,cls.s,cls.r,cls.p=materialize(cls.root)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_all_eight_stages_and_obligations_survive(self):
  self.assertEqual(self.c.audit.status,'COMPLETE');self.assertEqual(len(self.c.audit.stages),8)
  self.assertTrue({'REPORT-CASES','HISTORY-CASES','VIEW-REPORT'}<={o.id for a in self.p.artifacts for o in a.mappings})
  self.assertTrue(all(o.status=='OUTSTANDING' for o in self.p.obligations))
 def test_no_new_constant_rewriting_and_unchanged_core_algorithms(self):
  ns=kernel(compiler.REGISTRATION)
  for name in ['_project','validate_plan','_approve','execute','compile_pipeline']:self.assertIs(ns[name].__code__,getattr(compiler_core,name).__code__)
  self.assertNotIn('co_consts',Path('engineering/compiler_extensions/dispatch.py').read_text())
  self.assertNotIn('ReportDefinition',compiler_core.APPLICATION_KINDS)
 def test_unknown_registration_fails_closed(self):
  bad=replace(self.c.context,request=replace(self.r,features=('unknown',)))
  self.assertIsInstance(compiler.compile_pipeline(self.c.source,bad).result,Failure)
 def test_query_contract_scopes_and_bounds(self):
  model=self.c.lower(self.s,self.r).target_model.read();c=model['reporting']
  self.assertIn('=? AND ',c['whereSQL']);self.assertIn('la.status',c['whereSQL']);self.assertIn('IN (',c['auditWhereSQL']);self.assertNotIn('FLD-NOTE',{f['id'] for f in c['fields']})
  self.assertEqual(c['pagination']['maximumSize'],20);self.assertNotIn('tenant',c['filters'])
 def test_generated_api_has_authorization_parameter_binding_and_readonly_tx(self):
  text=(self.root/'backend/src/main/java/acp/api/ReportingController.java').read_text()
  for marker in ['policy.actor(jwt)','PROPAGATION_REQUIRES_NEW','setReadOnly(true)','ISOLATION_REPEATABLE_READ','REPORT_PERMISSION_DENIED','REPORT_RESOURCE_NOT_FOUND','parameters.toArray()','REPORT_ID="REPORT-CASES"']:self.assertIn(marker,text)
  for bad in ['jdbc.update(', 'DELETE FROM','INSERT INTO','CASE-ASSIGNEE','fixture:operator']:self.assertNotIn(bad,text)
 def test_ui_loading_empty_error_and_keyboard_controls(self):
  from engineering.reporting.run import adapter_source
  adapter=adapter_source()
  self.assertEqual(adapter.count("VALUES('tenant-one'),('tenant-two')"),1)
  self.assertIn('/__test/report-negative',adapter)
  self.assertIn('fixture:reporter-two',adapter)
  self.assertIn('browser-report-tenant-two',adapter)
  assignment=next(n for n in proposal()['nodes'] if n['id']=='ASSIGN-R5-TENANT-TWO')
  self.assertEqual(assignment['data']['principal'],'fixture:reporter-two')
  self.assertNotIn('hidden-owned',adapter.split('@PostMapping("/__test/report-negative")')[0])
  self.assertNotIn("VALUES('fixture:operator','tenant-two')",adapter.split('@PostMapping("/__test/report-negative")')[0])
  self.assertIn('v-if="allowed"', (self.root/'frontend/src/App.vue').read_text())
  self.assertIn('snapshot.tenant', (self.root/'frontend/src/App.vue').read_text())
  self.assertIn('snapshot.subject', (self.root/'frontend/src/App.vue').read_text())
  self.assertIn('REPORT_RESPONSE', (self.root/'frontend/src/ReportPanel.vue').read_text())
  text=(self.root/'frontend/src/ReportPanel.vue').read_text()
  for marker in ['Loading report','No report results','Reporting unavailable','Selected audit history','focus-visible','Report pages','row.values[field.id]']:self.assertIn(marker,text)
  self.assertIn('ReportPanel',(self.root/'frontend/src/App.vue').read_text())
 def test_provenance_and_source_substitution(self):
  self.assertEqual(self.c.verify_materialized(self.root,self.p,self.s,self.r)['status'],'VERIFIED_OFFLINE')
  f=self.root/'frontend/src/ReportPanel.vue';raw=f.read_bytes()
  try:
   f.write_bytes(raw+b'changed')
   with self.assertRaises(StoreConflict):FilesystemArtifactStore(self.root).inventory()
  finally:f.write_bytes(raw)
 def test_mcp_and_default_namespaces_are_distinct(self):
  from engineering.reporting.mcp import PreviewQuery
  from engineering.mcp_adapter.server import Query
  from pydantic import ValidationError
  PreviewQuery(application='case-management-report-preview')
  with self.assertRaises(ValidationError):Query(application='case-management-report-preview')
  with self.assertRaises(ValidationError):PreviewQuery(application='case-management')

if __name__=='__main__':unittest.main()
