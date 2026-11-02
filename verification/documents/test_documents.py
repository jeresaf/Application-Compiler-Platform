import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from dataclasses import replace
from engineering.documents import semantics as s
from engineering.documents.reference import proposal
from engineering.documents.schema import schemas,CONTRACTS,FEATURES
from engineering.reporting.reference import proposal as parent
from engineering.documents.application import materialize
from engineering.documents.compiler import compile_pipeline
from compiler_contracts import Failure,Stage
from filesystem_artifacts import FilesystemArtifactStore,StoreConflict

class Semantics(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.source=proposal();cls.snapshot=s.normalize_candidate(cls.source)
 def reject(self,edit):
  a=copy.deepcopy(self.source);n={v['id']:v for v in a['nodes']};edit(a,n)
  with self.assertRaises((ValueError,KeyError)):s.normalize_candidate(a)
 def test_closed_schemas(self):
  for name,value in zip(('authoring-0.7.schema.json','canonical-0.6.schema.json'),schemas()):self.assertEqual(json.loads((CONTRACTS/name).read_bytes()),value)
 def test_exact_prior_nodes_preserved(self):
  n={n['id']:n for n in self.source['nodes']}
  for old in parent()['nodes']:self.assertEqual(n[old['id']],old)
 def test_no_human_acceptance(self):
  for authority in (None,lambda q:'approved'):
   with self.assertRaises(ValueError):s.admit(self.snapshot,authority)
 def test_unsupported_storage_rejected(self):self.reject(lambda a,n:n['DOC-ATTACHMENTS']['data'].update(storage='PUBLIC_FILESYSTEM'))
 def test_unsupported_types_rejected(self):self.reject(lambda a,n:n['DOC-ATTACHMENTS']['data'].update(mediaTypes=['application/octet-stream']))
 def test_size_bounds_rejected(self):
  for x in (0,65537):self.reject(lambda a,n:n['DOC-ATTACHMENTS']['data'].update(maximumBytes=x))
 def test_missing_audit_or_idempotency_rejected(self):
  for key in ('audit','idempotency'):self.reject(lambda a,n:n['DOC-ATTACHMENTS']['data'].pop(key))
 def test_cross_resource_scope_rejected(self):self.reject(lambda a,n:n['PERM-DOC-UPLOAD']['data'].update(scope={'id':'SCOPE-CASE','revision':1}))
 def test_wrong_principal_field_rejected(self):self.reject(lambda a,n:n['PERM-DOC-UPLOAD']['data'].update(principalField={'id':'CASE-TENANT','revision':2}))
 def test_wrong_read_grant_rejected(self):self.reject(lambda a,n:n['DOC-ATTACHMENTS']['data'].update(readPermission={'id':'PERM-DOC-UPLOAD','revision':1}))
 def test_wrong_view_rejected(self):self.reject(lambda a,n:n['VIEW-DOCUMENTS']['data'].update(uploadPermission={'id':'PERM-DOC-READ','revision':1}))
 def test_unapproved_or_unknown_version_rejected(self):
  self.reject(lambda a,n:n['DOC-ATTACHMENTS'].update(lifecycle='PROPOSED'));self.reject(lambda a,n:a.update(modelVersion='0.8.0'))
 def test_digest_and_reference_revision_rejected(self):
  bad=copy.deepcopy(self.snapshot);bad['contentDigest']='sha256:'+'0'*64
  with self.assertRaises(ValueError):s.validate_snapshot(bad)
  self.reject(lambda a,n:n['DOC-ATTACHMENTS']['data']['resource'].update(revision=999))

class Pipeline(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.tmp=tempfile.TemporaryDirectory(prefix='acp-documents-unit-');cls.root=Path(cls.tmp.name)/'application';cls.c,cls.s,cls.r,cls.p=materialize(cls.root)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def test_eight_stages_and_exact_identity(self):
  self.assertEqual(self.c.audit.status,'COMPLETE');self.assertEqual(len(self.c.audit.stages),8);self.assertEqual(self.c.audit.input_canonical_digest,self.s.read()['contentDigest']);self.assertEqual(self.c.native.targets[(self.r.snapshot_digest,self.r.compiler,self.r.pipeline)].obligations,self.p.obligations)
 def test_unknown_feature_fails_closed(self):
  ctx=replace(self.c.context,request=replace(self.r,features=('acp.phase1.0.2',),end=Stage.INGEST));result=compile_pipeline(self.c.source,ctx);self.assertIsInstance(result.result,Failure)
 def test_transactional_hash_audit_and_scope_enforcement(self):
  text=(self.root/'backend/src/main/java/acp/api/DocumentController.java').read_text()
  for token in ('policy.actor(jwt)','FOR UPDATE','DOCUMENT_IDEMPOTENCY_CONFLICT','DOCUMENT_CONTENT_INTEGRITY','MessageDigest','idempotency_key','PERMISSION_DENIED','RETURNING id','_audit(audit_id,document,sha256)','resource(jwt,resource)'):self.assertIn(token,text)
  for token in ('FileOutputStream','ProcessBuilder','Runtime.getRuntime','getRealPath'):self.assertNotIn(token,text)
 def test_storage_and_historical_migrations(self):
  sql=(self.root/'backend/src/main/resources/db/migration/V4__documents.sql').read_text();self.assertIn('content bytea NOT NULL',sql);self.assertIn('octet_length(content)=size',sql);self.assertIn('REFERENCES acp_audit(id)',sql);self.assertIn('FOREIGN KEY(tenant,resource)',sql)
  import hashlib
  for name,pin in {'V2__delivery_jobs.sql': '747a656c7004fd3b9ea784fcbfa678068b9469f283f8a2381fcb26671df139ad', 'V3__privacy_lifecycle.sql': '71d6792bd43301a63f0b9af69398a96620f634232f61c1aba9c99ce705f06fa5', 'V1__initial.sql': 'b84e41e5902c1f611d4692e454409cb0013b52f76129ce7b89c608d2934a4674'}.items():self.assertEqual(hashlib.sha256((self.root/'backend/src/main/resources/db/migration'/name).read_bytes()).hexdigest(),pin)
 def test_generated_interface_and_disabled_production_mode(self):
  text=(self.root/'frontend/src/DocumentPanel.vue').read_text();self.assertIn('crypto.subtle.digest',text);self.assertIn('URL.revokeObjectURL',text);self.assertIn('onUnmounted',text);self.assertIn('Attachment list',text);self.assertNotIn('postData()',Path('engineering/documents/journey.ts').read_text());self.assertIn('DOCUMENT_PREVIEW_ONLY',(self.root/'backend/src/main/java/acp/api/DocumentController.java').read_text());self.assertIn('DocumentPanel',(self.root/'frontend/src/App.vue').read_text())
 def test_provenance_and_drift_rejection(self):
  self.assertEqual(self.c.verify_materialized(self.root,self.p,self.s,self.r)['status'],'VERIFIED_OFFLINE');p=self.root/'frontend/src/DocumentPanel.vue';raw=p.read_bytes()
  try:
   p.write_bytes(raw+b'\n// tamper\n')
   with self.assertRaises(StoreConflict):FilesystemArtifactStore(self.root).inventory()
  finally:p.write_bytes(raw)
 def test_preservation_and_namespace(self):
  self.assertEqual(subprocess.check_output(['git','diff','eb2cad7','--','tooling','contracts','targets','engineering/reporting','engineering/native_create','proposals/phase10-r5-reporting']),b'')
  from engineering.documents.inspection import NAMESPACE
  from engineering.documents.mcp import PreviewQuery
  self.assertEqual(NAMESPACE,'case-management-document-preview')
  with self.assertRaises(ValueError):PreviewQuery(application='case-management')

class ExecutionBinding(unittest.TestCase):
 def test_changed_retained_file_rejected(self):
  from engineering.documents.execution import CandidateExecution
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'execution.json';p.write_text('{}');e=CandidateExecution(p);p.write_text('{"changed":true}')
   with self.assertRaises(ValueError):e.apply(None,[])
 def test_approval_scope_cannot_be_invented(self):
  from engineering.documents.execution import CandidateExecution
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'execution.json';p.write_text(json.dumps({'scope':'RELEASE_ACCEPTANCE','semanticApproval':'APPROVED'}));e=CandidateExecution(p)
   with self.assertRaises(ValueError):e.apply(None,[])
 def test_wrong_source_and_unexecuted_artifacts_rejected(self):
  from engineering.documents.execution import CandidateExecution
  from compiler_contracts import fingerprint
  from types import SimpleNamespace
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'execution.json';proof={'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED','canonicalDigest':'wrong','artifactPlanDigest':fingerprint(()),'generator':'test','sourceSHA256':{},'files':[]};p.write_text(json.dumps(proof));e=CandidateExecution(p);session=SimpleNamespace(inputs={'canonicalDigest':'actual','generator':'test'},plan=())
   with self.assertRaises(ValueError):e.apply(session,[])
   proof['canonicalDigest']='actual';p.write_text(json.dumps(proof));e=CandidateExecution(p)
   with self.assertRaises(ValueError):e.apply(session,[{'kind':'ARTIFACT_VERIFICATION','result':'NOT_RUN'}])
   with self.assertRaises(ValueError):e.apply(session,[{'kind':'ARTIFACT_VERIFICATION','result':'PASS'}])
