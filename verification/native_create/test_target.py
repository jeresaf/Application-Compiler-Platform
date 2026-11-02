"""Real compiler/target plans, native versions, publication and provenance."""
import copy,json,tempfile,unittest
from pathlib import Path
from engineering.native_create.application import materialize
from engineering.native_create.target import lower_create
from engineering.native_create import semantics
from compiler_contracts import Document
from filesystem_artifacts import StoreConflict

class NativeTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='acp-r4-target-test-')
        cls.root=Path(cls.temp.name)/'application'
        cls.c,cls.s,cls.r,cls.p=materialize(cls.root)
        cls.target=cls.c.targets[(cls.r.snapshot_digest,cls.r.compiler,cls.r.pipeline)]
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def test_native_versions_route_and_model_reference(self):
        model=json.loads((self.root/'backend/src/main/resources/acp-model.json').read_bytes())
        self.assertEqual(model['canonicalVersion'],'0.4.0')
        self.assertEqual(model['semanticModelVersion'],'0.5.0')
        create=model['intakePreview']
        self.assertEqual(create['operation'],'CREATE-CASE')
        self.assertTrue(any(a['origin']['id']=='CREATE-CASE' and a['path']==create['path'] for a in model['api']))
        from engineering.source_intelligence.model import sha
        ref=json.loads((self.root/'contracts/target-ir.json').read_bytes())
        self.assertEqual(ref['sha256'],sha((self.root/ref['path']).read_bytes()))
    def test_authenticated_creation_and_consumed_source_symbol(self):
        controller=(self.root/'backend/src/main/java/acp/api/IntakeController.java').read_text()
        for expected in ('OPERATION_ID="CREATE-CASE"','String operation=OPERATION_ID','policy.actor(jwt)','SUBJECT_TENANT_BINDING','authorizationScope','invocations.invoke','InvocationCore.replay','InvocationCore.capture','store.audit','IDENTITY_CONFLICT'):
            self.assertIn(expected,controller)
        form=(self.root/'frontend/src/IntakeForm.vue').read_text()
        self.assertIn('import {createContract as contract}',form)
        self.assertIn('name in contract.controls',form)
        self.assertNotIn('>Create case</button>',form)
        self.assertIn('operation: operationId',(self.root/'frontend/src/create-contract.ts').read_text())
        self.assertNotIn('fixture:operator',controller)
        self.assertEqual({d.role:d.choice.read()['choice'] for d in self.r.decisions},self.c.native.profile['decisions'])
        observed=self.c.native.profile;observed['profile']='substituted'
        self.assertNotEqual(self.c.native.profile['profile'],'substituted')
        self.c.native._verify()
        from types import SimpleNamespace
        from dataclasses import replace
        bad=[replace(d,choice=Document.of({'choice':'wrong-target','status':'TEST_ONLY'})) if d.role=='architecture' else d for d in self.r.decisions]
        fake=SimpleNamespace(architecture=tuple(d for d in bad if d.role=='architecture'),design=tuple(d for d in bad if d.role=='design'))
        with self.assertRaisesRegex(ValueError,'CREATE_ARCHITECTURE_DESIGN_BINDING'):self.c.native.lower(fake,self.r)

    def test_native_provenance_build_and_all_artifact_bytes(self):
        result=self.c.verify_materialized(self.root,self.p,self.s,self.r)
        self.assertEqual(result['status'],'VERIFIED_OFFLINE')
        provenance=json.loads((self.root/'acp/provenance.json').read_bytes())
        self.assertEqual(provenance['build']['canonicalVersion'],'0.4.0')
        self.assertEqual(provenance['build']['canonicalSnapshotDigest'],self.s.read()['contentDigest'])
        create=next(a for a in self.p.artifacts if a.path.endswith('/IntakeController.java'))
        self.assertTrue({'CREATE-CASE','PERM-CREATE-CASE','FORM-CREATE-CASE'}<={o.id for o in create.mappings})
    def test_source_substitution_rejects_without_publication(self):
        path=self.root/'frontend/src/create-contract.ts';raw=path.read_bytes()
        try:
            path.write_bytes(raw+b'\n// substituted\n')
            with self.assertRaises((ValueError,StoreConflict)):self.c.verify_materialized(self.root,self.p,self.s,self.r)
        finally:path.write_bytes(raw)
    def test_preview_binding_is_explicit_and_default_source_admission_rejects(self):
        from engineering.native_create.preview import Preview
        from engineering.source_intelligence.analysis import binding
        preview=Preview(self.c,self.s,self.r,self.p,self.c.audit,self.root)
        with tempfile.TemporaryDirectory(prefix='acp-r4-binding-test-') as directory:
            baseline=Path(directory)/'baseline.json';baseline.write_bytes(preview.document)
            self.assertEqual(preview.binding(baseline,preview.pin)[0]['namespace'],'case-management-create-preview')
            with self.assertRaises(ValueError):binding(baseline,preview.pin)
            with self.assertRaises(ValueError):preview.binding(baseline,'0'*64)
            baseline.write_bytes(preview.document+b' ')
            with self.assertRaises(ValueError):preview.binding(baseline,preview.pin)
    def test_changed_compilation_binding_rejects_preview(self):
        from dataclasses import replace
        from engineering.native_create.preview import Preview
        audit=replace(self.c.audit,artifact_plan_digest='sha256:'+'0'*64)
        with self.assertRaises(ValueError):Preview(self.c,self.s,self.r,self.p,audit,self.root)
    def test_mcp_preview_namespace_does_not_alias_approved_applications(self):
        from engineering.native_create.mcp import PreviewQuery
        from engineering.mcp_adapter.server import Query
        from pydantic import ValidationError
        self.assertEqual(PreviewQuery(application='case-management-create-preview').application,'case-management-create-preview')
        with self.assertRaises(ValidationError):PreviewQuery(application='case-management')
        with self.assertRaises(ValidationError):Query(application='case-management-create-preview')
    def test_missing_or_multiple_native_operations_target_reject(self):
        model=self.target.target_model.read();value=self.s.read()
        missing=copy.deepcopy(value)
        missing['content']['nodes']=[n for n in missing['content']['nodes'] if n['kind']!='CreateOperation']
        with self.assertRaises(ValueError):lower_create(missing,model)
        source=semantics.authoring(value);nodes={n['id']:n for n in source['nodes']}
        identities={'CREATE-CASE':'CREATE-OTHER','PERM-CREATE-CASE':'PERM-CREATE-OTHER','FORM-CREATE-CASE':'FORM-CREATE-OTHER'}
        for old,new in identities.items():
            node=copy.deepcopy(nodes[old]);node['id']=new;node['name']='PROPOSED '+new
            node['origins'][0]['locator']=new
            for key in ('operation','permission'):
                if key in node['data']:node['data'][key]['id']=identities[node['data'][key]['id']]
            source['nodes'].append(node)
        # This is a VALID two-operation semantic model. Rejection must come
        # from the target's bounded capability, not an invalid digest/reference.
        multiple=semantics.normalize_candidate(source)
        with self.assertRaisesRegex(ValueError,'CREATE_TARGET_SINGLE_OPERATION'):lower_create(multiple,model)

if __name__=='__main__':unittest.main()
