from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
import unittest

from engineering.evidence_admission.encoding import payload_digest
from engineering.evidence_admission.signatures import LabVerificationError
from engineering.evidence_admission.trust import verify_lab_policy, check_revocation
from lab_fixtures import LabFixture,NOW,signed


class TrustTests(unittest.TestCase):
    def setUp(self):self.lab=LabFixture(self)

    def test_external_pinned_policy(self):
        self.assertEqual(verify_lab_policy(self.lab.policy_raw,self.lab.context),self.lab.context.policy_digest)

    def test_unavailable_or_candidate_controlled_context(self):
        for context in (None,{},self.lab.policy):
            with self.subTest(context=type(context)),self.assertRaises(LabVerificationError):verify_lab_policy(self.lab.policy_raw,context)
        with self.assertRaises(LabVerificationError):replace(self.lab.context,anchor_keys=())

    def test_candidate_policy_cannot_pin_itself(self):
        self.lab.policy['recordId']='f'*32
        raw=signed(self.lab.policy,['policy-1','policy-2'],self.lab.private)
        with self.assertRaisesRegex(LabVerificationError,'UNPINNED_POLICY'):verify_lab_policy(raw,self.lab.context)

    def test_wrong_policy_signer_and_threshold(self):
        for signers in (['custodian-1','custodian-2'],['policy-1']):
            raw=signed(self.lab.policy,signers,self.lab.private)
            with self.subTest(signers=signers),self.assertRaises(LabVerificationError):verify_lab_policy(raw,self.lab.context)

    def test_expired_policy(self):
        self.lab.policy['expiresAt']='2026-10-14T11:00:00Z';self.lab.repin_policy()
        with self.assertRaisesRegex(LabVerificationError,'EXPIRED_POLICY'):verify_lab_policy(self.lab.policy_raw,self.lab.context)

    def test_offline_policy_rollback_and_conflict(self):
        for changes in ({'policy_floor':1},{'policy_sequence':1}):
            with self.subTest(changes=changes),self.assertRaises(LabVerificationError):
                verify_lab_policy(self.lab.policy_raw,replace(self.lab.context,**changes))

    def test_missing_incomplete_expired_and_conflicting_revocation(self):
        views=[None,replace(self.lab.context.revocation,complete=False),
               replace(self.lab.context.revocation,expires_at=NOW),
               replace(self.lab.context.revocation,sequence=0),
               replace(self.lab.context.revocation,revoked_keys=frozenset(['key:other']))]
        for view in views:
            with self.subTest(view=view),self.assertRaises(LabVerificationError):
                verify_lab_policy(self.lab.policy_raw,replace(self.lab.context,revocation=view))

    def test_revoked_policy_signer_and_policy_record(self):
        for changes in ({'revoked_keys':frozenset(['key:policy-1'])},
                        {'revoked_records':frozenset([self.lab.context.policy_digest])}):
            self.lab=LabFixture(self);self.lab.change_revocation(**changes)
            with self.subTest(changes=changes),self.assertRaises(LabVerificationError):verify_lab_policy(self.lab.policy_raw,self.lab.context)

    def test_policy_replacement_uses_previous_authority(self):
        previous=self.lab.policy_raw;previous_digest=self.lab.context.policy_digest
        self.lab.policy.update(sequence=1,predecessorPolicyRef={'schema':'acp-phase6-evidence/trust-policy/1','payloadDigest':previous_digest})
        self.lab.repin_policy()
        context=replace(self.lab.context,previous_policy_raw=previous,previous_policy_digest=previous_digest,policy_sequence=1)
        self.assertEqual(verify_lab_policy(self.lab.policy_raw,context),context.policy_digest)
        with self.assertRaises(LabVerificationError):verify_lab_policy(self.lab.policy_raw,self.lab.context)
        bad=replace(context,anchor_keys=tuple(k for k in context.keys if 'REGISTRATION_CUSTODIAN' in k.roles))
        with self.assertRaises(LabVerificationError):verify_lab_policy(self.lab.policy_raw,bad)

    def test_context_is_deeply_immutable(self):
        mutable=list(self.lab.context.keys);context=replace(self.lab.context,keys=mutable)
        mutable.clear();self.assertTrue(context.keys)
        with self.assertRaises(FrozenInstanceError):context.policy_digest='sha256:'+'0'*64
        with self.assertRaises(AttributeError):context.candidate_authors.add('principal:other')
        with self.assertRaises(LabVerificationError):replace(context,source_inventory=bytearray(context.source_inventory))
        with self.assertRaises(LabVerificationError):replace(context,laboratory=False)
        with self.assertRaises(LabVerificationError):replace(context.witness_contracts[0],path=['mutable'])
        with self.assertRaises(LabVerificationError):replace(context,registration_heads=(list(context.registration_heads[0]),))

    def test_unpinned_independence_role_combination(self):
        with self.assertRaises(LabVerificationError):verify_lab_policy(self.lab.policy_raw,
            replace(self.lab.context,allow_reviewer_custodian_combination=True))

    def test_conflicting_registration_heads_rejected(self):
        head=self.lab.context.registration_heads[0]
        with self.assertRaises(LabVerificationError):replace(self.lab.context,registration_heads=(head,(head[0],'sha256:'+'b'*64,None)))

    def test_new_policy_cannot_authorize_its_own_signers(self):
        previous=self.lab.policy_raw;digest=self.lab.context.policy_digest
        self.lab.policy.update(sequence=1,predecessorPolicyRef={'schema':'acp-phase6-evidence/trust-policy/1','payloadDigest':digest})
        self.lab.repin_policy()
        context=replace(self.lab.context,previous_policy_raw=previous,previous_policy_digest=digest,policy_sequence=1)
        candidate_signed=signed(self.lab.policy,['custodian-1','custodian-2'],self.lab.private)
        with self.assertRaises(LabVerificationError):verify_lab_policy(candidate_signed,context)

    def test_criterion_contract_identity_and_stale_checkpoint(self):
        self.lab.policy['criterionContracts'][0]['contractDigest']='sha256:'+'b'*64;self.lab.repin_policy()
        with self.assertRaises(LabVerificationError):verify_lab_policy(self.lab.policy_raw,self.lab.context)
        self.lab=LabFixture(self);self.lab.policy['freshness']['maxSnapshotAgeSeconds']=1;self.lab.repin_policy()
        with self.assertRaises(LabVerificationError):verify_lab_policy(self.lab.policy_raw,self.lab.context)
