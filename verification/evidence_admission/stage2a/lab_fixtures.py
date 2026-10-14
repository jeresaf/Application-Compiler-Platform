"""PUBLIC SYNTHETIC TEST KEYS AND REVIEWS. Never use as operational authority."""
import base64
import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from engineering.evidence_admission.encoding import canonicalize, parse_canonical, payload_digest, signature_input
from engineering.evidence_admission.registration import source_inventory, source_tree_digest, review_subject_digest, sha
from engineering.evidence_admission.signatures import LabKey
from engineering.evidence_admission.trust import LabTrustContext, RevocationView, ReviewerGrant, WitnessContract

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,10,14,12,tzinfo=timezone.utc)
START=NOW-timedelta(days=1)
END=NOW+timedelta(days=1)


def signed(payload, names, private_keys, domain=None):
    signatures=[]
    message=signature_input(payload) if domain is None else domain+canonicalize(payload)
    for name in names:
        signatures.append({'signerId':'principal:'+name,'keyId':'key:'+name,'algorithm':'Ed25519',
                           'signature':base64.urlsafe_b64encode(private_keys[name].sign(message)).decode().rstrip('=')})
    signatures.sort(key=lambda s:(s['signerId'],s['keyId']))
    return canonicalize({'payload':payload,'payloadDigest':payload_digest(payload),'signatures':signatures})


class LabFixture:
    def __init__(self, test):
        temp=tempfile.TemporaryDirectory(prefix='acp-lab-verifier-');test.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        (self.root/'verifier.py').write_text('raise RuntimeError("REGISTRATION MUST NOT EXECUTE THIS")\n')
        (self.root/'requirements.txt').write_text('synthetic-verifier==1\n')
        (self.root/'assertions.json').write_bytes(canonicalize({'criterion':8,'assertions':['exact-synthetic-assertion']}))
        for path in self.root.iterdir():path.chmod(0o644)
        self.git('init','-q','--initial-branch=main');self.git('add','verifier.py','requirements.txt','assertions.json')
        self.git('-c','user.name=Synthetic Laboratory','-c','user.email=synthetic@example.invalid','commit','-q','-m','Synthetic verifier fixture')
        commit=self.git('rev-parse','HEAD').decode().strip()
        roles={'policy-1':'POLICY_CUSTODIAN','policy-2':'POLICY_CUSTODIAN',
               'custodian-1':'REGISTRATION_CUSTODIAN','custodian-2':'REGISTRATION_CUSTODIAN',
               'technical':'REVIEWER','security':'REVIEWER'}
        self.private={name:Ed25519PrivateKey.from_private_bytes(hashlib.sha256(('PUBLIC TEST ONLY '+name).encode()).digest()) for name in roles}
        keys=tuple(LabKey('key:'+name,'principal:'+name,self.private[name].public_key().public_bytes(Encoding.Raw,PublicFormat.Raw),
                          frozenset([role]),START,END) for name,role in roles.items())
        examples=json.loads((ROOT/'fixtures/synthetic-records.json').read_text())['records']
        self.policy=copy.deepcopy(examples['trust-policy']['payload'])
        self.policy.update(issuedAt='2026-10-14T10:00:00Z',expiresAt='2026-10-15T12:00:00Z')
        self.policy['thresholds'].update(policy=2,registration=2)
        self.policy['freshness'].update(maxSnapshotAgeSeconds=900,maxEvidenceAgeSeconds=86400,maxFutureSkewSeconds=300,maxChallengeAgeSeconds=7200)
        self.policy['signerRoles']=sorted([{'signerId':k.principal_id,'role':next(iter(k.roles)),'keyIds':[k.key_id]} for k in keys],key=lambda r:(r['signerId'],r['role']))
        independence=canonicalize({'schema':'acp-phase6-lab-independence/1','allowReviewerCustodianCombination':False,
                                  'distinctTechnicalSecurityReviewers':True,'candidateCannotReview':True})
        self.policy['independenceContractDigest']=payload_digest(parse_canonical(independence))
        contract=sha((self.root/'assertions.json').read_bytes())
        self.policy['criterionContracts']=[{'criterion':8,'contractDigest':contract}]
        self.policy_raw=signed(self.policy,['policy-1','policy-2'],self.private)
        rev=RevocationView(1,NOW-timedelta(minutes=1),NOW+timedelta(minutes=10),frozenset(),frozenset(),frozenset(),True)
        self.payload=copy.deepcopy(examples['verifier-registration']['payload'])
        self.payload.update(issuedAt='2026-10-14T10:00:00Z',expiresAt='2026-10-15T12:00:00Z',criteria=[8],
                            requiredApplications=['CASE_MANAGEMENT','PAYMENT'],executorIds=['executor:synthetic-only'])
        inventory=source_inventory(self.root)
        self.payload['source']={'repository':'jeresaf/Application-Compiler-Platform','commit':commit,
            'treeDigest':source_tree_digest(inventory),'entrypoint':'verifier.py',
            'dependencyManifestDigest':sha((self.root/'requirements.txt').read_bytes())}
        self.payload['policyRef']={'schema':self.policy['schema'],'payloadDigest':payload_digest(self.policy)}
        self.payload['witnessContracts']=[{'criterion':8,'witnessId':'integratedCrossOwnerTransitions','assertionContractDigest':contract}]
        grants=tuple(ReviewerGrant('principal:'+name,frozenset([purpose]),frozenset([8]),frozenset(['PAYMENT','CASE_MANAGEMENT']),START,END)
                     for name,purpose in (('technical','TECHNICAL'),('security','SECURITY')))
        self.context=LabTrustContext(repository='jeresaf/Application-Compiler-Platform',policy_digest=payload_digest(self.policy),
            policy_sequence=0,policy_floor=0,previous_policy_digest=None,previous_policy_raw=None,
            anchor_keys=tuple(k for k in keys if 'POLICY_CUSTODIAN' in k.roles),keys=keys,policy_threshold=2,registration_threshold=2,
            reviewer_grants=grants,reviews=(),candidate_authors=frozenset(['principal:candidate']),allow_reviewer_custodian_combination=False,
            now=NOW,revocation=rev,expected_revocation_digest=rev.digest,expected_revocation_sequence=1,registration_heads=(),
            criteria=frozenset([8]),applications=frozenset(['PAYMENT','CASE_MANAGEMENT']),executor_ids=frozenset(['executor:synthetic-only']),
            witness_contracts=(WitnessContract(8,'integratedCrossOwnerTransitions','assertions.json',contract),),
            environment_contract_digest=self.payload['environmentContractDigest'],independence_contract_digest=self.policy['independenceContractDigest'],
            independence_contract=independence,criterion_contracts=((8,contract),),source_commit=commit,source_inventory=inventory,
            entrypoint='verifier.py',dependency_path='requirements.txt',dependency_digest=self.payload['source']['dependencyManifestDigest'])
        self.refresh()

    def git(self,*args):
        env=dict(os.environ,GIT_AUTHOR_DATE='2026-10-14T10:00:00Z',GIT_COMMITTER_DATE='2026-10-14T10:00:00Z')
        return subprocess.check_output(['git','-c','core.hooksPath=/dev/null','-c','core.autocrlf=false',
                                        '-c','commit.gpgsign=false','-c','core.fsmonitor=false',
                                        '-C',str(self.root),*args],stderr=subprocess.PIPE,env=env)

    def refresh(self, refresh_reviews=True, pin=True, signers=('custodian-1','custodian-2')):
        if refresh_reviews:
            review_bytes=[]
            for field,purpose,name in (('technicalReviewDigests','TECHNICAL','technical'),('securityReviewDigests','SECURITY','security')):
                raw=canonicalize({'schema':'acp-phase6-lab-review/1','subjectDigest':review_subject_digest(self.payload),
                    'purpose':purpose,'reviewerId':'principal:'+name,'criteria':self.payload['criteria'],
                    'applications':self.payload['requiredApplications'],'issuedAt':'2026-10-14T10:00:00Z','expiresAt':'2026-10-15T12:00:00Z'})
                review_bytes.append(raw);self.payload[field]=[sha(raw)]
            self.context=replace(self.context,reviews=tuple(review_bytes))
        self.raw=signed(self.payload,signers,self.private)
        if pin:self.context=replace(self.context,registration_heads=((self.payload['verifierId'],payload_digest(self.payload),None),))

    def change_revocation(self,**changes):
        rev=replace(self.context.revocation,**changes)
        self.context=replace(self.context,revocation=rev,expected_revocation_digest=rev.digest)

    def repin_policy(self):
        self.policy_raw=signed(self.policy,['policy-1','policy-2'],self.private)
        self.context=replace(self.context,policy_digest=payload_digest(self.policy))
        self.payload['policyRef']['payloadDigest']=self.context.policy_digest
        self.refresh()
