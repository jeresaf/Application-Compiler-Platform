"""Native CREATE version negotiation, semantic rejection and preservation."""
import copy,hashlib,json,subprocess,unittest
from pathlib import Path
from engineering.native_create.reference import proposal
from engineering.native_create import semantics as s
from engineering.native_create.schema import schemas
from jsonschema import Draft202012Validator
from deterministic_approval import approved_snapshot
from canonical_ir import validate_snapshot as legacy_validate,CanonicalError

class NativeSemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=proposal();cls.snapshot=s.normalize_candidate(cls.source)
    def mutate(self,change):
        value=copy.deepcopy(self.source);nodes={n['id']:n for n in value['nodes']}
        change(value,nodes)
        with self.assertRaises((CanonicalError,ValueError)):s.normalize_candidate(value)
    def test_closed_schemas_are_reproducible(self):
        for name,expected in zip(('authoring-0.5.schema.json','canonical-0.4.schema.json'),schemas()):
            self.assertEqual(json.loads((s.CONTRACTS/name).read_bytes()),expected)
            Draft202012Validator.check_schema(expected)
    def test_exact_normalization_and_structural_validation_is_not_admission(self):
        self.assertEqual(s.validate_snapshot(self.snapshot),self.snapshot)
        with self.assertRaises(CanonicalError):s.admit(self.snapshot)
        with self.assertRaises(CanonicalError):s.admit(self.snapshot,lambda q:'true')
    def test_original_nodes_and_default_admission_unchanged(self):
        old=approved_snapshot('case-management')
        self.assertEqual([n for n in self.snapshot['content']['nodes'] if n['id'] in {x['id'] for x in old['content']['nodes']}],old['content']['nodes'])
        self.assertEqual(s.legacy_snapshot(self.snapshot)['content']['schemaVersion'],'0.3.0')
        with self.assertRaises(CanonicalError):legacy_validate(self.snapshot)
    def test_unknown_version_feature_and_extra_properties_reject(self):
        for value in ('0.4.0','0.6.0'):
            self.mutate(lambda m,n:m.update(modelVersion=value))
        self.mutate(lambda m,n:n['CREATE-CASE']['data'].update(shell='run'))
        for key,value in [('schemaVersion','0.3.0'),('requiredFeatures',['unknown'])]:
            snap=copy.deepcopy(self.snapshot);snap['content'][key]=value
            with self.assertRaises(CanonicalError):s.validate_snapshot(snap)
    def test_missing_required_and_unknown_field_reject(self):
        self.mutate(lambda m,n:n['CREATE-CASE']['data']['bindings'].pop('FLD-TASK-SUMMARY'))
        self.mutate(lambda m,n:n['CREATE-CASE']['data']['bindings'].update(UNKNOWN={'kind':'ABSENT'}))
        self.mutate(lambda m,n:n['CREATE-CASE']['data']['bindings'].update({'FLD-TASK-SUMMARY':{'kind':'ABSENT'}}))
    def test_identity_tenant_principal_and_initial_state_reject(self):
        for field,kind in [('CASE-ID','ABSENT'),('CASE-TENANT','GENERATED_UUID'),('CASE-ASSIGNEE','GENERATED_UUID'),('FLD-TASK-SUMMARY','GENERATED_UUID')]:
            self.mutate(lambda m,n:n['CREATE-CASE']['data']['bindings'].update({field:{'kind':kind}}))
        self.mutate(lambda m,n:n['CREATE-CASE']['data'].update(initialState={'id':'STATE-ARCHIVED','revision':1}))
    def test_permissions_revision_controls_and_lengths_reject(self):
        self.mutate(lambda m,n:n['PERM-CREATE-CASE']['data']['operation'].update(revision=2))
        self.mutate(lambda m,n:n['FORM-CREATE-CASE']['data'].update(controls=['title']))
        self.mutate(lambda m,n:n['CREATE-CASE']['data']['bindings']['FLD-TASK-SUMMARY'].update(minimumLength=2000,maximumLength=1))
        self.mutate(lambda m,n:n['CREATE-CASE']['data']['bindings']['FLD-TASK-SUMMARY'].update(name='title'))
    def test_explicit_supplied_identity_changes_digest(self):
        value=copy.deepcopy(self.source);n={n['id']:n for n in value['nodes']}
        n['CREATE-CASE']['data']['bindings']['CASE-ID']={'kind':'INPUT','name':'identity','type':copy.deepcopy(n['CASE-ID']['data']['type']),'member':None,'minimumLength':1,'maximumLength':128}
        n['FORM-CREATE-CASE']['data']['controls'].append('identity')
        self.assertNotEqual(s.normalize_candidate(value)['contentDigest'],self.snapshot['contentDigest'])
    def test_original_artifact_bytes_and_seal(self):
        from target_worker import bundle_digest
        self.assertEqual(bundle_digest(),'ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb')
        for name in ('engineering/reference_application/intake.py','tooling/compiler_core.py','tooling/canonical_ir.py','tooling/audit/criteria.py','engineering/generator_candidates/spring_vue_postgres_0_6/candidate.py'):
            self.assertEqual((s.ROOT/name).read_bytes(),subprocess.check_output(['git','show','12d225900c7c50725ff27a8401fe8ca94bfc8901:'+name]))

if __name__=='__main__':unittest.main()
