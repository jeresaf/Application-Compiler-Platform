"""Signed challenge and exact contract adversarial regressions."""
import copy
from dataclasses import replace
from datetime import timedelta
import unittest

from lab_fixtures import Fixture, NOW, signed
from engineering.evidence_admission.challenge import authenticate_challenge, construct_challenge_payload, validate_challenge
from engineering.evidence_admission.encoding import canonicalize, parse_canonical
from engineering.evidence_admission.execution_context import contract_digest, execution_contract
from engineering.evidence_admission.signatures import LabVerificationError


class ChallengeTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture(self)

    def test_new_modules_have_no_signer_workload_or_admission_api(self):
        import ast
        from pathlib import Path
        root=Path(__file__).resolve().parents[3]/'engineering/evidence_admission'
        forbidden={'EVIDENCE_ADMITTED','RELEASE_APPROVED','PHASE6_CLOSURE_RECOMMENDED','LAB_EXECUTION_VERIFIED'}
        for name in ['execution_context.py','challenge.py','execution_ledger.py']:
            tree=ast.parse((root/name).read_text())
            values={node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str)}
            self.assertTrue(values.isdisjoint(forbidden))
            imports=[node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
            self.assertFalse(any(module and ('subprocess' in module or 'asymmetric.ed25519' in module) for module in imports))
            self.assertFalse(any(isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ('sign','Popen','system','execv','execve') for node in ast.walk(tree)))

    def test_valid_synthetic_challenge_and_idempotent_read_only(self):
        f = self.f; digest = f.issue(); before = f.ledger.checkpoint()
        self.assertEqual(authenticate_challenge(f.raw, f.context, f.ledger), digest)
        self.assertEqual(authenticate_challenge(f.raw, f.context, f.ledger), digest)
        self.assertEqual(f.ledger.checkpoint(), before)

    def test_unknown_issuer(self):
        f=self.f; payload=copy.deepcopy(f.payload);payload['issuerId']='principal:unknown'
        with self.assertRaises(LabVerificationError):validate_challenge(f.sign(payload),f.context)

    def test_incorrect_signature_and_unsigned_record(self):
        f=self.f;record=parse_canonical(f.raw)
        record['signatures'][0]['signature']='A'*86
        with self.assertRaises(LabVerificationError):validate_challenge(canonicalize(record),f.context)
        record['signatures']=[]
        with self.assertRaises(LabVerificationError):validate_challenge(canonicalize(record),f.context)

    def test_altered_contract_command_and_case_inventory(self):
        f=self.f
        for field in ['commands','cases','limits','isolationProfileDigest']:
            changed=copy.deepcopy(f.contract)
            if field=='commands':changed[field][0]['argv'].append('--changed')
            elif field=='cases':changed[field][0]['caseId']='changedCase'
            elif field=='limits':changed[field]['executionTimeoutSeconds']+=1
            else:changed[field]='sha256:'+'1'*64
            with self.subTest(field=field),self.assertRaises(LabVerificationError):
                replace(f.context,contract_raw=canonicalize(changed))

    def test_wrong_registration(self):
        f=self.f;payload=copy.deepcopy(f.payload);payload['registrationRef']['payloadDigest']='sha256:'+'1'*64
        with self.assertRaises(LabVerificationError):validate_challenge(f.sign(payload),f.context)

    def test_wrong_source_commit(self):
        f=self.f;payload=copy.deepcopy(f.payload);payload['binding']['executionCommit']='1'*40
        with self.assertRaises(LabVerificationError):validate_challenge(f.sign(payload),f.context)

    def test_wrong_package(self):
        f=self.f;payload=copy.deepcopy(f.payload);payload['subjects'][0]['packageDigest']='sha256:'+'1'*64
        with self.assertRaises(LabVerificationError):validate_challenge(f.sign(payload),f.context)

    def test_wrong_application(self):
        f=self.f;payload=copy.deepcopy(f.payload);payload['subjects']=payload['subjects'][1:]
        with self.assertRaises(LabVerificationError):validate_challenge(f.sign(payload),f.context)

    def test_wrong_canonical(self):
        f=self.f;payload=copy.deepcopy(f.payload);payload['binding']['canonicalDigests']['payment']='sha256:'+'1'*64
        with self.assertRaises(LabVerificationError):validate_challenge(f.sign(payload),f.context)

    def test_wrong_bundle(self):
        f=self.f;payload=copy.deepcopy(f.payload);payload['binding']['bundleDigest']='sha256:'+'1'*64
        with self.assertRaises(LabVerificationError):validate_challenge(f.sign(payload),f.context)

    def test_policy_mismatch(self):
        f=self.f;payload=copy.deepcopy(f.payload);payload['policyRef']['payloadDigest']='sha256:'+'1'*64
        with self.assertRaises(LabVerificationError):validate_challenge(f.sign(payload),f.context)

    def test_expired_and_overlong_challenge(self):
        f=self.f
        later=replace(f.context,trust=replace(f.context.trust,now=NOW+timedelta(minutes=10)))
        with self.assertRaises(LabVerificationError):validate_challenge(f.raw,later)
        payload=copy.deepcopy(f.payload);payload['expiresAt']='2026-10-14T12:16:00Z'
        with self.assertRaises(LabVerificationError):validate_challenge(f.sign(payload),f.context)
        self.assertEqual(f.contract['limits']['executionTimeoutSeconds'],3600)
        with self.assertRaises(LabVerificationError):construct_challenge_payload(f.context,'a'*32,901)

    def test_revoked_issuer_and_registration(self):
        f=self.f
        for changes in [{'revoked_principals':frozenset(['principal:issuer'])},
                        {'revoked_keys':frozenset(['key:issuer'])},
                        {'revoked_records':frozenset([f.contract['registrationDigest']])}]:
            view=replace(f.context.trust.revocation,**changes)
            context=replace(f.context,trust=replace(f.context.trust,revocation=view,expected_revocation_digest=view.digest))
            with self.subTest(changes=changes),self.assertRaises(LabVerificationError):validate_challenge(f.raw,context)

    def test_missing_revocation_checkpoint(self):
        f=self.f;context=replace(f.context,trust=replace(f.context.trust,revocation=None))
        with self.assertRaises(LabVerificationError):validate_challenge(f.raw,context)

    def test_candidate_issuer_keys_do_not_establish_authority(self):
        f=self.f
        with self.assertRaises(LabVerificationError):replace(f.context,issuer_id='principal:candidate')
        payload=copy.deepcopy(f.payload)
        forged=signed(payload,['custodian-1'],f.base.private)
        with self.assertRaises(LabVerificationError):validate_challenge(forged,f.context)

    def test_closed_contract_unknown_fields_versions_and_shell_strings(self):
        f=self.f
        for changed in [dict(f.contract,unknown=True),dict(f.contract,schema='unsupported/2'),dict(f.contract,commands=['echo unsafe'])]:
            with self.assertRaises((LabVerificationError,ValueError)):execution_contract(canonicalize(changed))
        changed=copy.deepcopy(f.contract);changed['commands'][0]['argv']='echo unsafe'
        with self.assertRaises(LabVerificationError):execution_contract(canonicalize(changed))

    def test_contract_rejects_ambiguous_cases_paths_environment_and_shells(self):
        f=self.f
        mutations=[]
        changed=copy.deepcopy(f.contract);changed['cases'].append(dict(changed['cases'][0],criterion=9));mutations.append(changed)
        changed=copy.deepcopy(f.contract);changed['artifacts'][0]['path']='../escape';mutations.append(changed)
        changed=copy.deepcopy(f.contract);changed['artifacts'][0]['expectedDigest']=None;mutations.append(changed)
        changed=copy.deepcopy(f.contract);changed['commands'][0]['environment']={'PATH\n':'candidate'};mutations.append(changed)
        changed=copy.deepcopy(f.contract);changed['commands'][0]['argv']=['bin/bash','-c','echo unsafe'];changed['commands'][0]['executablePath']='bin/bash';mutations.append(changed)
        for changed in mutations:
            with self.subTest(changed=changed),self.assertRaises(LabVerificationError):execution_contract(canonicalize(changed))

    def test_nonce_is_random_32_bytes_and_payload_is_not_authority(self):
        import base64
        f=self.f;nonces={construct_challenge_payload(f.context,'a'*32)['nonce'] for _ in range(8)}
        self.assertEqual(len(nonces),8)
        for nonce in nonces:self.assertEqual(len(base64.urlsafe_b64decode(nonce+'=')),32)
        with self.assertRaises(LabVerificationError):authenticate_challenge(f.raw,f.context,f.ledger)

    def test_issuance_record_pins_contract_even_with_same_challenge_fields(self):
        f=self.f;f.issue();changed=copy.deepcopy(f.contract);changed['commands'][0]['argv'].append('--different')
        raw=canonicalize(changed);context=replace(f.context,contract_raw=raw,expected_contract_digest=contract_digest(raw))
        with self.assertRaises(LabVerificationError):authenticate_challenge(f.raw,context,f.ledger)


if __name__=='__main__':unittest.main()
