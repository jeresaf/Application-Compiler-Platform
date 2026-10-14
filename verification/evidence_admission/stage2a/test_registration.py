import copy
from dataclasses import replace
import os
from pathlib import Path
import unittest

from engineering.evidence_admission.encoding import canonicalize,parse_canonical,payload_digest
from engineering.evidence_admission.registration import authenticate_lab_registration,review_subject_digest,source_inventory,source_tree_digest,sha
from engineering.evidence_admission.signatures import LabVerificationError
from lab_fixtures import LabFixture,signed,NOW


class RegistrationTests(unittest.TestCase):
    def setUp(self):self.lab=LabFixture(self)

    def authenticate(self):
        return authenticate_lab_registration(self.lab.raw,self.lab.policy_raw,self.lab.root,self.lab.context)

    def rejected(self):
        with self.assertRaises((LabVerificationError,ValueError,OSError)):self.authenticate()

    def test_valid_lab_registration_and_idempotence(self):
        first=self.authenticate();self.assertEqual(first,self.authenticate())
        self.assertEqual(first.status,'LAB_REGISTRATION_VERIFIED');self.assertIs(first.laboratory,True)
        self.assertEqual(set(first.__dataclass_fields__),{'registration_digest','verifier_id','policy_digest','signer_ids','status','laboratory'})
        self.assertFalse((self.lab.root/'activation.json').exists())

    def test_source_code_is_not_executed(self):
        # Fixture entrypoint raises immediately if executed.
        self.assertIn('raise RuntimeError', (self.lab.root/'verifier.py').read_text())
        self.authenticate()

    def test_candidate_self_registration(self):
        self.lab.context=replace(self.lab.context,candidate_authors=frozenset(['principal:custodian-1']))
        self.rejected()

    def test_unauthorized_custodian(self):
        self.lab.raw=signed(self.lab.payload,['technical','security'],self.lab.private);self.rejected()

    def test_missing_or_untrusted_review_context(self):
        for purpose in ('technicalReviewDigests','securityReviewDigests'):
            self.lab=LabFixture(self);self.lab.payload[purpose]=['sha256:'+'b'*64]
            self.lab.refresh(refresh_reviews=False)
            with self.subTest(purpose=purpose):self.rejected()
        self.lab=LabFixture(self);self.lab.context=replace(self.lab.context,reviews=());self.rejected()

    def test_review_subject_excludes_only_the_two_review_arrays(self):
        payload=copy.deepcopy(self.lab.payload);original=review_subject_digest(payload)
        payload['technicalReviewDigests']=['sha256:'+'b'*64];payload['securityReviewDigests']=['sha256:'+'c'*64]
        self.assertEqual(review_subject_digest(payload),original)
        for field in payload:
            if field in ('technicalReviewDigests','securityReviewDigests'):continue
            altered=copy.deepcopy(payload);altered[field]=['changed']
            with self.subTest(field=field):
                if field=='schema':
                    with self.assertRaises(LabVerificationError):review_subject_digest(altered)
                else:self.assertNotEqual(review_subject_digest(altered),original)

    def test_tampered_review_subject(self):
        self.lab.payload['recordId']='d'*32;self.lab.refresh(refresh_reviews=False);self.rejected()

    def test_wrong_review_purpose_or_scope(self):
        for field,value in (('purpose','SECURITY'),('criteria',[9]),('applications',['PAYMENT']),('reviewerId','principal:candidate')):
            self.lab=LabFixture(self);raw=self.lab.context.reviews[0];review=parse_canonical(raw);review[field]=value
            changed=canonicalize(review)
            self.lab.payload['technicalReviewDigests']=[sha(changed)]
            self.lab.context=replace(self.lab.context,reviews=(changed,self.lab.context.reviews[1]))
            self.lab.refresh(refresh_reviews=False)
            with self.subTest(field=field):self.rejected()

    def test_candidate_is_not_an_independent_reviewer(self):
        self.lab.context=replace(self.lab.context,candidate_authors=frozenset(['principal:technical']));self.rejected()

    def test_custodian_reviewer_combination_requires_pinned_permission(self):
        lab=self.lab
        keys=tuple(replace(k,roles=k.roles|{'REVIEWER'}) if k.key_id=='key:custodian-1' else k for k in lab.context.keys)
        grant=replace(lab.context.reviewer_grants[0],principal_id='principal:custodian-1')
        lab.context=replace(lab.context,keys=keys,reviewer_grants=(grant,lab.context.reviewer_grants[1]))
        lab.policy['signerRoles'].append({'signerId':'principal:custodian-1','role':'REVIEWER','keyIds':['key:custodian-1']})
        lab.policy['signerRoles'].sort(key=lambda r:(r['signerId'],r['role']))
        def bind_review():
            review=parse_canonical(lab.context.reviews[0]);review['reviewerId']='principal:custodian-1'
            raw=canonicalize(review);lab.payload['technicalReviewDigests']=[sha(raw)]
            lab.context=replace(lab.context,reviews=(raw,lab.context.reviews[1]));lab.refresh(refresh_reviews=False)
        lab.repin_policy();bind_review();self.rejected()
        contract=parse_canonical(lab.context.independence_contract);contract['allowReviewerCustodianCombination']=True
        lab.context=replace(lab.context,allow_reviewer_custodian_combination=True,
                            independence_contract=canonicalize(contract),independence_contract_digest=payload_digest(contract))
        lab.policy['independenceContractDigest']=lab.context.independence_contract_digest
        lab.repin_policy();bind_review()
        self.assertEqual(self.authenticate().status,'LAB_REGISTRATION_VERIFIED')

    def test_technical_and_security_reviewers_must_be_distinct(self):
        lab=self.lab
        grant=replace(lab.context.reviewer_grants[0],purposes=frozenset(['TECHNICAL','SECURITY']))
        lab.context=replace(lab.context,reviewer_grants=(grant,))
        review=parse_canonical(lab.context.reviews[1]);review['reviewerId']='principal:technical'
        raw=canonicalize(review);lab.payload['securityReviewDigests']=[sha(raw)]
        lab.context=replace(lab.context,reviews=(lab.context.reviews[0],raw));lab.refresh(refresh_reviews=False)
        self.rejected()

    def test_ineligible_or_expired_reviewer(self):
        for grant in (replace(self.lab.context.reviewer_grants[0],purposes=frozenset(['SECURITY'])),
                      replace(self.lab.context.reviewer_grants[0],valid_until=NOW),
                      replace(self.lab.context.reviewer_grants[0],criteria=frozenset([9])),
                      replace(self.lab.context.reviewer_grants[0],applications=frozenset(['PAYMENT']))):
            self.lab.context=replace(self.lab.context,reviewer_grants=(grant,self.lab.context.reviewer_grants[1]))
            with self.subTest(grant=grant):self.rejected()

    def test_revoked_registration_key_reviewer_and_review(self):
        for case in ('registration','custodian-key','reviewer-key','reviewer','review'):
            self.lab=LabFixture(self)
            changes={'registration':{'revoked_records':frozenset([parse_canonical(self.lab.raw)['payloadDigest']])},
                     'custodian-key':{'revoked_keys':frozenset(['key:custodian-1'])},
                     'reviewer-key':{'revoked_keys':frozenset(['key:technical'])},
                     'reviewer':{'revoked_principals':frozenset(['principal:technical'])},
                     'review':{'revoked_records':frozenset([self.lab.payload['technicalReviewDigests'][0]])}}[case]
            self.lab.change_revocation(**changes)
            with self.subTest(case=case):self.rejected()

    def test_expired_registration_and_review(self):
        self.lab.payload['expiresAt']='2026-10-14T11:00:00Z';self.lab.refresh();self.rejected()
        self.lab=LabFixture(self);review=parse_canonical(self.lab.context.reviews[0]);review['expiresAt']='2026-10-14T11:00:00Z'
        raw=canonicalize(review);self.lab.payload['technicalReviewDigests']=[sha(raw)]
        self.lab.context=replace(self.lab.context,reviews=(raw,self.lab.context.reviews[1]))
        self.lab.refresh(refresh_reviews=False);self.rejected()

    def test_wrong_criterion_and_witness_scope(self):
        for field,value in (('criteria',[9]),('witnessContracts',[{'criterion':8,'witnessId':'unrelated','assertionContractDigest':'sha256:'+'b'*64}])):
            self.lab=LabFixture(self);self.lab.payload[field]=value
            if field=='criteria':self.lab.payload['witnessContracts'][0]['criterion']=9
            self.lab.refresh()
            with self.subTest(field=field):self.rejected()

    def test_wrong_application_scope(self):
        self.lab.payload['requiredApplications']=['PAYMENT'];self.lab.refresh();self.rejected()

    def test_wrong_executor_environment_and_entrypoint(self):
        for field,value in (('executorIds',['executor:other']),('environmentContractDigest','sha256:'+'b'*64)):
            self.lab=LabFixture(self);self.lab.payload[field]=value;self.lab.refresh()
            with self.subTest(field=field):self.rejected()
        self.lab=LabFixture(self);self.lab.payload['source']['entrypoint']='other.py';self.lab.refresh();self.rejected()

    def test_changed_source_and_dependency_digest(self):
        for field in ('treeDigest','dependencyManifestDigest','commit'):
            self.lab=LabFixture(self);self.lab.payload['source'][field]='b'*40 if field=='commit' else 'sha256:'+'b'*64
            self.lab.refresh()
            with self.subTest(field=field):self.rejected()

    def test_missing_extra_replaced_source_files_and_modes(self):
        for mutation in ('missing','extra','bytes','mode','dependency','assertion'):
            self.lab=LabFixture(self);root=self.lab.root
            if mutation=='missing':(root/'verifier.py').unlink()
            elif mutation=='extra':(root/'extra.py').write_text('extra')
            elif mutation=='bytes':(root/'verifier.py').write_text('replaced')
            elif mutation=='mode':(root/'verifier.py').chmod(0o755)
            elif mutation=='dependency':(root/'requirements.txt').write_text('changed')
            else:(root/'assertions.json').unlink()
            with self.subTest(mutation=mutation):self.rejected()

    def test_source_symlinks_traversal_and_ambiguous_paths(self):
        self.lab.root.joinpath('linked.py').symlink_to('verifier.py');self.rejected()
        self.lab=LabFixture(self);self.lab.root.joinpath('linked-dir').symlink_to(self.lab.root,target_is_directory=True);self.rejected()
        self.lab=LabFixture(self);self.lab.root.joinpath('bad\\path').write_text('bad');self.rejected()
        self.lab=LabFixture(self);self.lab.payload['source']['entrypoint']='../escape.py';self.lab.refresh();self.rejected()

    def test_source_inventory_bound_to_git_commit(self):
        # Even a newly pinned inventory may not relabel dirty bytes as a commit.
        (self.lab.root/'verifier.py').write_text('changed but not committed')
        inventory=source_inventory(self.lab.root)
        self.lab.context=replace(self.lab.context,source_inventory=inventory)
        self.lab.payload['source']['treeDigest']=source_tree_digest(inventory);self.lab.refresh();self.rejected()

    def test_git_environment_cannot_redirect_source_identity(self):
        from unittest.mock import patch
        with patch.dict(os.environ,{'GIT_DIR':'/nonexistent','GIT_WORK_TREE':'/nonexistent'}):
            self.authenticate()

    def test_untracked_source_cannot_be_included_in_registered_inventory(self):
        (self.lab.root/'extra.py').write_text('untracked')
        inventory=source_inventory(self.lab.root);self.lab.context=replace(self.lab.context,source_inventory=inventory)
        self.lab.payload['source']['treeDigest']=source_tree_digest(inventory);self.lab.refresh();self.rejected()

    def test_superseded_registration_replay_and_predecessor(self):
        self.lab.context=replace(self.lab.context,registration_heads=((self.lab.payload['verifierId'],'sha256:'+'b'*64,None),));self.rejected()
        self.lab=LabFixture(self);digest=parse_canonical(self.lab.raw)['payloadDigest']
        self.lab.context=replace(self.lab.context,registration_heads=((self.lab.payload['verifierId'],digest,'sha256:'+'b'*64),));self.rejected()

    def test_policy_binding_and_unsupported_version(self):
        self.lab.payload['policyRef']['payloadDigest']='sha256:'+'b'*64;self.lab.refresh();self.rejected()
        self.lab=LabFixture(self);self.lab.payload['schema']='acp-phase6-evidence/verifier-registration/2'
        self.lab.raw=signed(self.lab.payload,['custodian-1','custodian-2'],self.lab.private);self.rejected()

    def test_missing_or_mutable_external_context(self):
        for context in (None,{},dict(policy=self.lab.policy)):
            with self.subTest(context=type(context)),self.assertRaises(LabVerificationError):
                authenticate_lab_registration(self.lab.raw,self.lab.policy_raw,self.lab.root,context)


if __name__=='__main__':unittest.main()
