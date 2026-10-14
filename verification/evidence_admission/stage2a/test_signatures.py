import copy
from dataclasses import replace
from datetime import timedelta
import unittest

from engineering.evidence_admission.encoding import canonicalize, parse_canonical, payload_digest
from engineering.evidence_admission.signatures import LabVerificationError, verify_ed25519, verify_record_signatures
from lab_fixtures import LabFixture, NOW, signed


class SignatureTests(unittest.TestCase):
    def setUp(self):self.lab=LabFixture(self)

    def verify(self,raw=None,keys=None,threshold=2):
        return verify_record_signatures(raw or self.lab.raw,keys or self.lab.context.keys,'REGISTRATION_CUSTODIAN',threshold,NOW,frozenset(),frozenset())

    def test_rfc8032_vector_one(self):
        # RFC 8032 section 7.1 TEST 1, public key/signature for empty message.
        public=bytes.fromhex('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
        signature=bytes.fromhex('e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b')
        verify_ed25519(public,signature,b'')
        with self.assertRaises(LabVerificationError):verify_ed25519(public,signature,b'changed')

    def test_valid_synthetic_signatures(self):
        self.assertEqual(self.verify(),('principal:custodian-1','principal:custodian-2'))

    def test_rfc8032_vector_two(self):
        public=bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')
        signature=bytes.fromhex('92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00')
        verify_ed25519(public,signature,bytes.fromhex('72'))
        with self.assertRaises(LabVerificationError):verify_ed25519(public,signature,bytes.fromhex('73'))

    def test_changed_payload_with_recomputed_digest_still_rejected(self):
        for field in ('recordId','treeDigest','dependencyManifestDigest'):
            record=parse_canonical(self.lab.raw)
            if field=='recordId':record['payload'][field]='e'*32
            else:record['payload']['source'][field]='sha256:'+'e'*64
            record['payloadDigest']=payload_digest(record['payload'])
            with self.subTest(field=field),self.assertRaises(LabVerificationError):self.verify(canonicalize(record))

    def test_unknown_key_and_wrong_identity(self):
        for field,value in (('keyId','key:unknown'),('signerId','principal:unknown')):
            record=parse_canonical(self.lab.raw);record['signatures'][0][field]=value
            record['signatures'].sort(key=lambda s:(s['signerId'],s['keyId']))
            with self.subTest(field=field),self.assertRaises(LabVerificationError):self.verify(canonicalize(record))

    def test_wrong_role_and_insufficient_threshold(self):
        with self.assertRaises(LabVerificationError):self.verify(signed(self.lab.payload,['policy-1','policy-2'],self.lab.private))
        with self.assertRaises(LabVerificationError):self.verify(signed(self.lab.payload,['custodian-1'],self.lab.private))

    def test_wrong_algorithm_and_domain(self):
        record=parse_canonical(self.lab.raw);record['signatures'][0]['algorithm']='none'
        with self.assertRaises(LabVerificationError):self.verify(canonicalize(record))
        raw=signed(self.lab.payload,['custodian-1','custodian-2'],self.lab.private,domain=b'WRONG-DOMAIN\0')
        with self.assertRaises(LabVerificationError):self.verify(raw)

    def test_invalid_surplus_signature_is_never_ignored(self):
        record=parse_canonical(self.lab.raw);extra=copy.deepcopy(record['signatures'][0])
        extra['signature']='A'*86;record['signatures'][0]=extra
        with self.assertRaises(LabVerificationError):self.verify(canonicalize(record),threshold=1)

    def test_same_principal_with_two_distinct_keys_is_not_two_signers(self):
        keys=list(self.lab.context.keys);old=next(k for k in keys if k.key_id=='key:custodian-2')
        keys[keys.index(old)]=replace(old,principal_id='principal:custodian-1')
        record=parse_canonical(self.lab.raw);record['signatures'][1]['signerId']='principal:custodian-1'
        with self.assertRaisesRegex(LabVerificationError,'DUPLICATE_SIGNER'):self.verify(canonicalize(record),tuple(keys))

    def test_shared_public_key_or_key_id_aliases_rejected(self):
        keys=list(self.lab.context.keys)
        for change in ({'public_key':keys[0].public_key},{'key_id':keys[0].key_id}):
            changed=keys[:];changed[1]=replace(changed[1],**change)
            with self.subTest(change=change),self.assertRaises(LabVerificationError):self.verify(keys=tuple(changed))

    def test_expired_key_and_malformed_primitive_inputs(self):
        keys=tuple(replace(k,valid_until=NOW-timedelta(seconds=1)) if k.key_id=='key:custodian-1' else k for k in self.lab.context.keys)
        with self.assertRaises(LabVerificationError):self.verify(keys=keys)
        for public,signature in ((b'',bytes(64)),(bytes(32),b'')):
            with self.assertRaises(LabVerificationError):verify_ed25519(public,signature,b'')

    def test_unsupported_record_version(self):
        payload=copy.deepcopy(self.lab.payload);payload['schema']='acp-phase6-evidence/verifier-registration/2'
        with self.assertRaises(LabVerificationError):self.verify(signed(payload,['custodian-1','custodian-2'],self.lab.private))
