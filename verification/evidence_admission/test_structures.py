"""All examples are synthetic structures, including non-authentic signature bytes."""
import copy
import json
from pathlib import Path
import unittest
import subprocess
import sys
from unittest.mock import patch

from engineering.evidence_admission.encoding import canonicalize, payload_digest
from engineering.evidence_admission.validation import KINDS, validate_structure, validate_bundle

FIXTURE = Path(__file__).parent / 'fixtures/synthetic-records.json'


def records():
    return json.loads(FIXTURE.read_text())['records']


def encoded(record):
    record = copy.deepcopy(record)
    record['payloadDigest'] = payload_digest(record['payload'])
    return canonicalize(record)


def graph_bytes(examples):
    """Recompute the synthetic DAG after a mutation; do not fake stale hashes.

    References initially address the original payloads. Rebuild dependencies
    recursively so rejection tests isolate consistency rather than hash errors.
    """
    original=records()
    objects={original[k]['payloadDigest'] if k in original else v['payloadDigest']: v
             for k,v in examples.items()}
    rebuilt={}
    def build(digest):
        if digest in rebuilt:return rebuilt[digest]
        record=copy.deepcopy(objects[digest])
        def walk(value):
            if isinstance(value,dict):
                if set(value)=={'schema','payloadDigest'}:
                    if value['payloadDigest'] in objects:
                        value['payloadDigest']=build(value['payloadDigest'])['payloadDigest']
                else:
                    for child in value.values():walk(child)
            elif isinstance(value,list):
                for child in value:walk(child)
        walk(record['payload'])
        record['payloadDigest']=payload_digest(record['payload'])
        rebuilt[digest]=record
        return record
    return [canonicalize(build(digest)) for digest in objects]


class StructuralTests(unittest.TestCase):
    def consistent_graph(self):
        examples=records()
        self.assertEqual(validate_bundle(graph_bytes(examples)).status,'STRUCTURE_VALID_UNTRUSTED')
        return examples

    def clone_reference(self, examples, kind):
        clone=copy.deepcopy(examples[kind]);clone['payload']['recordId']='f'*32
        clone['payloadDigest']=payload_digest(clone['payload'])
        examples['second-'+kind]=clone
        return {'schema':clone['payload']['schema'],'payloadDigest':clone['payloadDigest']}

    def test_envelope_attestation_manifest_identity_mismatch(self):
        examples=self.consistent_graph()
        examples['execution-attestation']['payload']['manifestRef']=self.clone_reference(examples,'artifact-manifest')
        self.assertEqual(validate_bundle(graph_bytes(examples)).errors,
                         ('INCONSISTENT_EXECUTION_REFERENCE:manifestRef',))

    def test_envelope_challenge_criterion_mismatch(self):
        for scope in ([9],[8,9],[]):
            examples=self.consistent_graph();examples['execution-challenge']['payload']['criteria']=scope
            with self.subTest(scope=scope):
                self.assertEqual(validate_bundle(graph_bytes(examples)).status,'STRUCTURE_INVALID')

    def test_registration_reference_identity_mismatch(self):
        for kind in ('execution-attestation','execution-challenge'):
            examples=self.consistent_graph()
            examples[kind]['payload']['registrationRef']=self.clone_reference(examples,'verifier-registration')
            with self.subTest(record=kind):
                self.assertEqual(validate_bundle(graph_bytes(examples)).errors,
                                 ('INCONSISTENT_EXECUTION_REFERENCE:registrationRef',))

    def test_attestation_challenge_identity_mismatch(self):
        examples=self.consistent_graph()
        examples['execution-attestation']['payload']['challengeRef']=self.clone_reference(examples,'execution-challenge')
        self.assertEqual(validate_bundle(graph_bytes(examples)).errors,
                         ('INCONSISTENT_EXECUTION_REFERENCE:challengeRef',))

    def test_registration_scope_must_cover_execution(self):
        examples=self.consistent_graph()
        registration=examples['verifier-registration']['payload']
        registration['criteria']=[9];registration['witnessContracts'][0]['criterion']=9
        self.assertEqual(validate_bundle(graph_bytes(examples)).errors,('INCONSISTENT_EXECUTION_SCOPE',))
        examples=self.consistent_graph();registration=examples['verifier-registration']['payload']
        registration['criteria']=[registration['criteria'][0],9]
        witness=copy.deepcopy(registration['witnessContracts'][0]);witness['criterion']=9
        registration['witnessContracts'].append(witness)
        # Registration may describe more witnesses than this execution selects.
        self.assertEqual(validate_bundle(graph_bytes(examples)).status,'STRUCTURE_VALID_UNTRUSTED')

    def test_missing_wrong_type_and_modified_binding_in_consistent_graph(self):
        examples=self.consistent_graph()
        examples['engineering-envelope']['payload']['manifestRef']['payloadDigest']='sha256:'+'b'*64
        self.assertEqual(validate_bundle(graph_bytes(examples)).errors,('MISSING_REFERENCE',))
        examples=self.consistent_graph()
        examples['engineering-envelope']['payload']['attestationRef']['schema']='acp-phase6-evidence/human-decision/1'
        self.assertEqual(validate_bundle(graph_bytes(examples)).status,'STRUCTURE_INVALID')
        examples=self.consistent_graph()
        examples['execution-attestation']['payload']['binding']['executionCommit']='b'*40
        self.assertEqual(validate_bundle(graph_bytes(examples)).errors,('REFERENCE_BINDING_MISMATCH',))

    def test_cross_application_reference_confusion(self):
        examples=self.consistent_graph()
        examples['execution-attestation']['payload']['subjects'][0]['application']='CASE_MANAGEMENT'
        self.assertEqual(validate_bundle(graph_bytes(examples)).errors,('REFERENCE_BINDING_MISMATCH',))

    def test_duplicate_and_conflicting_record_identities(self):
        examples=self.consistent_graph();raw=graph_bytes(examples)
        self.assertEqual(validate_bundle(raw+[raw[0]]).errors,('DUPLICATE_RECORD',))
        examples=self.consistent_graph()
        clone=copy.deepcopy(examples['artifact-manifest']);clone['payload']['artifacts'][0]['size']=1
        clone['payloadDigest']=payload_digest(clone['payload']);examples['conflict']=clone
        self.assertEqual(validate_bundle(graph_bytes(examples)).errors,('DUPLICATE_RECORD_IDENTITY',))

    def test_receipt_cannot_restate_different_execution_references(self):
        examples=self.consistent_graph()
        examples['admission-receipt']['payload']['manifestRef']=self.clone_reference(examples,'artifact-manifest')
        self.assertEqual(validate_bundle(graph_bytes(examples)).status,'STRUCTURE_INVALID')

    def test_ci_step_failure_propagation(self):
        from engineering.ci.aggregate import JOBS,ARTIFACTS,evaluate
        root=Path(__file__).resolve().parents[2]
        workflow=(root/'.github/workflows/acp-contracts.yml').read_text()
        command='python3.14 -m unittest discover -s verification/evidence_admission -v'
        step='      - name: Verify Stage 1 evidence contract structures\n        run: '+command+'\n'
        self.assertEqual(workflow.count(step),1)
        contracts=workflow.split('  contracts:\n',1)[1].split('  phase5-experiments:',1)[0]
        self.assertGreater(contracts.index(step),contracts.index('name: ci-source-contracts'))
        self.assertNotIn('continue-on-error',contracts)
        # Execute the exact workflow command with an isolated synthetic suite
        # whose discovery always fails. This is a local shell simulation, not a
        # hosted job claim. No source file or workflow is modified.
        shim="""import sys, unittest
suite=unittest.TestSuite([unittest.FunctionTestCase(lambda: (_ for _ in ()).throw(AssertionError('intentional Stage 1 failure')))])
unittest.TestLoader.discover=lambda *args,**kwargs: suite
sys.argv=['unittest']+sys.argv[1:]
unittest.main(module=None)
"""
        import shlex
        simulated=command.replace('python3.14 -m unittest',shlex.quote(sys.executable)+' -c '+shlex.quote(shim),1)
        result=subprocess.run(['bash','--noprofile','--norc','-e','-o','pipefail','-c',simulated],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('intentional Stage 1 failure',result.stderr)
        source='a'*40
        jobs=[{'name':n,'conclusion':'failure' if n=='contracts' else 'success'} for n in JOBS]
        bindings={n:{'source':source,'run':'1','attempt':'1','job':n} for n in JOBS}
        artifacts={n:{'source':source,'valid':True} for n in ARTIFACTS}
        closure={'baseline':{'auditExecutionCommit':source},'auditExecution':{'status':'PERFORMED'},
                 'recommendation':'PHASE6_CLOSURE_RECOMMENDED','blockers':[],
                 'criteria':[{'requirement':i,'status':'PASS','evaluationProvenance':{'executionCommit':source,'evaluationCommit':source}} for i in range(1,40)]}
        verdict=evaluate(source,'1','1',jobs,bindings,artifacts,closure)
        self.assertFalse(verdict['releasePassed'])
        self.assertIn('JOB_NOT_SUCCESS:contracts',verdict['errors'])

    def invalid(self, record):
        result = validate_structure(encoded(record))
        self.assertEqual(result.status, 'STRUCTURE_INVALID', result)

    def test_every_supported_schema_is_valid_but_untrusted(self):
        examples = records()
        self.assertEqual(set(examples), set(KINDS))
        for kind, record in examples.items():
            with self.subTest(schema=kind):
                self.assertEqual(validate_structure(canonicalize(record)).status, 'STRUCTURE_VALID_UNTRUSTED')
        self.assertEqual(validate_bundle([canonicalize(v) for v in examples.values()]).status,
                         'STRUCTURE_VALID_UNTRUSTED')

    def test_all_required_fields_and_top_level_unknowns(self):
        for kind, record in records().items():
            for key in record:
                value = copy.deepcopy(record); del value[key]
                with self.subTest(schema=kind, outer_missing=key):
                    self.assertEqual(validate_structure(canonicalize(value)).status, 'STRUCTURE_INVALID')
            for key in record['payload']:
                value = copy.deepcopy(record); del value['payload'][key]
                with self.subTest(schema=kind, payload_missing=key):
                    self.invalid(value)
            value = copy.deepcopy(record); value['releaseApproved'] = True
            with self.subTest(schema=kind, unknown=True):
                self.assertEqual(validate_structure(canonicalize(value)).status, 'STRUCTURE_INVALID')

    def test_unknown_fields_in_every_nested_object(self):
        def paths(value, path=()):
            if isinstance(value, dict):
                yield path
                for k, v in value.items(): yield from paths(v, path+(k,))
            elif isinstance(value, list):
                for i, v in enumerate(value): yield from paths(v, path+(i,))
        for kind, record in records().items():
            for path in paths(record):
                value = copy.deepcopy(record); target = value
                for key in path: target = target[key]
                target['unexpected'] = 'no-extension'
                with self.subTest(schema=kind, path=path):
                    self.assertEqual(validate_structure(encoded(value)).status, 'STRUCTURE_INVALID')

    def test_invalid_digests_timestamps_identities_and_versions(self):
        for kind, record in records().items():
            for digest in ('a'*64, 'sha256:'+'A'*64, 'sha256:'+'a'*63, 'sha256:'+'a'*64+'\n'):
                value=copy.deepcopy(record);value['payloadDigest']=digest
                with self.subTest(schema=kind, digest=digest):
                    self.assertEqual(validate_structure(canonicalize(value)).status, 'STRUCTURE_INVALID')
            for timestamp in ('2026-02-30T12:00:00Z','2026-10-13T12:00:00+00:00',
                              '2026-10-13T12:00:00.0Z','2026-10-13T12:00:60Z','2026-10-13T12:00:00Z\n'):
                value=copy.deepcopy(record);value['payload']['issuedAt']=timestamp
                with self.subTest(schema=kind, timestamp=timestamp):self.invalid(value)
            for identity in ('', '0'*32+'\n', 'A'*32, 'synthetic', 5):
                value=copy.deepcopy(record);value['payload']['recordId']=identity
                with self.subTest(schema=kind, identity=identity):self.invalid(value)
            value=copy.deepcopy(record);value['payload']['schema']=value['payload']['schema'][:-1]+'2'
            self.invalid(value)

    def test_signature_syntax_not_authentication(self):
        record=records()['human-decision']
        for signature in ('', 'A'*85, 'A'*86+'=', '+'*86, 'A'*85+'B'):
            value=copy.deepcopy(record);value['signatures'][0]['signature']=signature
            with self.subTest(signature=signature):self.invalid(value)
        value=copy.deepcopy(record);value['signatures'][0]['algorithm']='none';self.invalid(value)
        value=copy.deepcopy(record);value['signatures'][0]['keyId']='principal:synthetic-only';self.invalid(value)
        # 64 zero bytes are well-encoded, not an authenticated signature.
        self.assertEqual(validate_structure(encoded(record)).status,'STRUCTURE_VALID_UNTRUSTED')

    def test_nested_required_fields(self):
        def objects(value, path=()):
            if isinstance(value,dict):
                yield path,value
                for k,v in value.items():yield from objects(v,path+(k,))
            elif isinstance(value,list):
                for i,v in enumerate(value):yield from objects(v,path+(i,))
        for kind,record in records().items():
            for path,obj in objects(record):
                if not path or path==('payload',):continue
                for missing in obj:
                    value=copy.deepcopy(record);target=value
                    for key in path:target=target[key]
                    del target[missing]
                    with self.subTest(schema=kind,path=path,missing=missing):self.invalid(value)

    def test_identity_terminators_and_nonce_encoding(self):
        for identity in ('key:synthetic-only\n','key:synthetic-only ','key:synthetic/only','key:Synthetic'):
            value=records()['human-decision'];value['signatures'][0]['keyId']=identity
            with self.subTest(identity=identity):self.invalid(value)
        for nonce in ('A'*42+'B','A'*43+'=','A'*42):
            value=records()['execution-challenge'];value['payload']['nonce']=nonce
            with self.subTest(nonce=nonce):self.invalid(value)
        value=records()['artifact-manifest'];value['payload']['artifacts'][0]['path']='file\n';self.invalid(value)

    def test_execution_failure_and_expired_claims_remain_structural_only(self):
        value=records()['execution-attestation'];value['payload']['cases'][0]['outcome']='FAILED'
        value['payload']['termination']={'kind':'NORMAL_EXIT','exitCode':1}
        # Structural validity deliberately does not judge the test outcome or
        # the historical fixture's current freshness, nor issue acceptance.
        self.assertEqual(validate_structure(encoded(value)).status,'STRUCTURE_VALID_UNTRUSTED')

    def test_bundle_duplicate_and_partial_records(self):
        values=[canonicalize(v) for v in records().values()]
        self.assertEqual(validate_bundle(values+[values[0]]).errors,('DUPLICATE_RECORD',))
        self.assertEqual(validate_bundle([]).status,'STRUCTURE_INVALID')
        self.assertEqual(validate_bundle(values[:-1]).status,'STRUCTURE_VALID_UNTRUSTED')
        # A single record is not claimed to have resolved its references.
        self.assertEqual(validate_structure(values[-1]).status,'STRUCTURE_VALID_UNTRUSTED')
        self.assertEqual(validate_bundle([canonicalize(records()['engineering-envelope'])]).errors,('MISSING_REFERENCE',))

    def test_nullable_fields_and_enum(self):
        for bad in ('null', {}, [], False):
            value=records()['human-decision'];value['payload']['supersedes']=bad
            with self.subTest(nullable=bad):self.invalid(value)
        value=records()['human-decision'];value['payload']['disposition']='RELEASE_APPROVED';self.invalid(value)
        value=records()['human-decision'];value['payload']['scope']['criterion']=8;self.invalid(value)

    def test_duplicate_array_identity_and_set_ordering(self):
        value=records()['artifact-manifest'];other=copy.deepcopy(value['payload']['artifacts'][0])
        other['size']=1;value['payload']['artifacts'].append(other);self.invalid(value)
        value=records()['engineering-envelope'];value['payload']['criteria']=[9,8];self.invalid(value)
        value=records()['engineering-envelope'];value['payload']['criteria']=[8,8];self.invalid(value)
        value=records()['trust-policy'];value['payload']['supportedSchemas'].reverse();self.invalid(value)
        value=records()['human-registry'];other=copy.deepcopy(value['payload']['grants'][0]);other['reviewerId']='principal:other'
        value['payload']['grants'].append(other);self.invalid(value)

    def test_manifest_paths(self):
        for path in ('/absolute','../escape','a/../b','a//b','a/./b','a\\b','C:/file','a/','a\x00b'):
            value=records()['artifact-manifest'];value['payload']['artifacts'][0]['path']=path
            with self.subTest(path=path):self.invalid(value)

    def test_numbers_bool_coercion_and_payload_digest(self):
        for bad in (True, -1, 2**53):
            value=records()['human-registry'];value['payload']['sequence']=bad
            with self.subTest(number=bad):
                if bad==2**53:
                    raw=json.dumps(value,separators=(',',':')).encode()
                    self.assertEqual(validate_structure(raw).status,'STRUCTURE_INVALID')
                else:self.invalid(value)
        value=records()['engineering-envelope'];value['payload']['criteria']=[True];self.invalid(value)
        value=records()['artifact-manifest'];value['payload']['artifacts'][0]['size']=1
        self.assertEqual(validate_structure(canonicalize(value)).errors,('PAYLOAD_DIGEST_MISMATCH',))

    def test_normal_exit_and_signal_are_disjoint(self):
        record=records()['execution-attestation']
        for termination in ({'kind':'NORMAL_EXIT','exitCode':1},
                            {'kind':'SIGNAL','signalNumber':9,'coreDumped':False}):
            value=copy.deepcopy(record);value['payload']['termination']=termination
            self.assertEqual(validate_structure(encoded(value)).status,'STRUCTURE_VALID_UNTRUSTED')
        for termination in ({'kind':'NORMAL_EXIT','exitCode':-9},
                            {'kind':'SIGNAL','signalNumber':9,'exitCode':0,'coreDumped':False},
                            {'kind':'SIGNAL','signalNumber':0,'coreDumped':False},
                            {'kind':'SIGNAL','signalNumber':9},
                            {'kind':'NORMAL_EXIT','exitCode':0,'signalNumber':9}):
            value=copy.deepcopy(record);value['payload']['termination']=termination
            with self.subTest(termination=termination):self.invalid(value)

    def test_reference_type_missing_and_wrong_binding(self):
        value=records()['engineering-envelope'];value['payload']['attestationRef']['schema']='acp-phase6-evidence/human-decision/1'
        self.invalid(value)
        examples=records();examples['engineering-envelope']['payload']['attestationRef']['payloadDigest']=examples['human-decision']['payloadDigest']
        result=validate_bundle([encoded(v) for v in examples.values()])
        self.assertEqual(result.errors,('REFERENCE_TYPE_MISMATCH',))
        result=validate_bundle([canonicalize(v) for k,v in records().items() if k!='execution-attestation'])
        self.assertEqual(result.errors,('MISSING_REFERENCE',))
        examples=records();examples['engineering-envelope']['payload']['binding']['executionCommit']='b'*40
        result=validate_bundle([encoded(v) for v in examples.values()])
        self.assertEqual(result.errors,('REFERENCE_BINDING_MISMATCH',))

    def test_structural_intervals_and_replacement(self):
        value=records()['human-decision'];value['payload']['expiresAt']=value['payload']['issuedAt'];self.invalid(value)
        value=records()['execution-attestation'];value['payload']['finishedAt']='2026-10-13T11:59:59Z';self.invalid(value)
        value=records()['trust-policy'];value['payload']['sequence']=1;self.invalid(value)
        value=records()['revocation'];value['payload']['action']='REPLACE';self.invalid(value)
        value=records()['revocation'];value['payload']['replacementRef']=copy.deepcopy(value['payload']['targetRef']);self.invalid(value)

    def test_invalid_wire_inputs_never_return_acceptance(self):
        for raw in (b'{}',b'null',b'[]',b'{"payload":{},"payload":{}}',b'not json',b'{ }'):
            with self.subTest(raw=raw):self.assertEqual(validate_structure(raw).status,'STRUCTURE_INVALID')


if __name__=='__main__':unittest.main()
