"""Public synthetic B0 fixtures. No actual execution or human approval is asserted."""
import base64
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from engineering.evidence_admission.encoding import canonicalize, signature_input, parse_canonical
from engineering.evidence_admission.registration import source_inventory, source_tree_digest
from engineering.evidence_admission.signatures import LabKey
from engineering.evidence_admission.scoped.context import LabContext
from engineering.evidence_admission.scoped.manifest import manifest,sha,digest,parse
from engineering.evidence_admission.scoped.verify import qualify

NOW=datetime(2026,10,17,12,tzinfo=timezone.utc)
ISSUE='2026-10-17T11:59:59Z';EXPIRY='2026-10-17T12:10:00Z'
D=lambda text:sha(text.encode())
REF=lambda text:{'schema':'acp-laboratory-'+text+'/1','payloadDigest':D(text)}


class Fixture:
    def __init__(self,human=False):
        self.temp=tempfile.TemporaryDirectory(prefix='acp-b0-synthetic-');self.root=Path(self.temp.name)
        self.source=self.root/'source';self.source.mkdir();self.artifacts=self.root/'artifacts';self.artifacts.mkdir()
        (self.source/'Witness.java').write_text('package lab; class Witness { void externalWitness() { throw new AssertionError("SYNTHETIC NOT EXECUTED"); } }\n')
        (self.source/'deps.lock').write_text('synthetic-no-dependencies\n')
        self.git('init','-q');self.git('add','Witness.java','deps.lock')
        self.git('-c','user.name=Synthetic B0 Fixture','-c','user.email=synthetic@example.invalid','commit','-qm','synthetic source fixture, not accepted history')
        commit=self.git('rev-parse','HEAD').strip();inventory=source_inventory(self.source);tree=source_tree_digest(inventory)
        self.private={role:Ed25519PrivateKey.from_private_bytes(bytes([i])*32) for i,role in enumerate(('EXECUTOR','COLLECTOR','REVIEWER'),1)}
        keys=tuple(LabKey('key:'+r.lower(),'principal:'+r.lower(),self.private[r].public_key().public_bytes(Encoding.Raw,PublicFormat.Raw),frozenset({r}),NOW-timedelta(days=1),NOW+timedelta(days=1)) for r in self.private)
        release={'kind':'UNSEALED_CANDIDATE','profile':'acp-spring-vue-postgres/0.6.0','generator':'acp-spring-vue-generator/0.6.0','candidateSourceDigest':tree,'ancestryDigest':D('synthetic ancestry'),'parentProfile':'acp-spring-vue-postgres/0.5.0','parentBundleSeal':'sha256:ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb'}
        subjects=[{'application':a,'canonicalDigest':D(a+' synthetic canonical'),'packageDigest':D(a+' synthetic package'),'generatedSourceDigest':D(a+' source'),'provenanceDigest':D(a+' provenance')} for a in ('CASE_MANAGEMENT','PAYMENT')]
        inputs={'executableDigest':D('synthetic executable'),'argv':['synthetic-runner','--test'],'workingDirectory':'source','environmentDigest':D('synthetic env'),'dependencyDigest':sha((self.source/'deps.lock').read_bytes())}
        scope={'schema':'acp-phase6-release-witness-scope/1','repository':'jeresaf/Application-Compiler-Platform','laboratory':True,'release':release,'purpose':'QUALIFICATION_ONLY','policyRef':REF('policy'),'source':{'commit':commit,'treeDigest':tree,'entrypoint':'Witness.java','dependencyPath':'deps.lock','dependencyDigest':inputs['dependencyDigest']},'cases':[{'witnessId':'witness:external','caseId':'case:contention','application':a['application'],'className':'lab.Witness','method':'externalWitness','sourcePath':'Witness.java','criterion':8,'assertionArtifactPaths':[a['application'].lower()+'.xml']} for a in subjects],'predicateContracts':[{'criterion':8,'digest':D('criterion 8')}]+([{'criterion':12,'digest':D('criterion 12')}] if human else []),'expectedInputs':inputs,'validFrom':ISSUE,'validUntil':EXPIRY}
        execution={'executionId':'e'*32,'contractDigest':D('execution contract'),'challengeRef':REF('challenge'),'executorId':'executor:lab','collectorId':'collector:lab','environmentDigest':inputs['environmentDigest'],'startedAt':ISSUE,'finishedAt':ISSUE,'provider':{'kind':'ISOLATED_EXECUTOR','hostConfigurationDigest':D('synthetic host'),'supervisorDigest':D('synthetic supervisor'),'sessionId':'session:lab'}}
        content={'source.json':inventory,**{a['application'].lower()+'.xml':b'<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase classname="lab.Witness" name="externalWitness"/></testsuite>' for a in subjects}}
        if human:content['deployment-review.json']=b'{"criteria":{"12":{"authority":"EXPLICIT_HUMAN_ACCEPTANCE","verification":"REVIEWED_EXTERNAL_OBLIGATION"}},"laboratory":true}'
        for name,raw in content.items():(self.artifacts/name).write_bytes(raw)
        evaluator={'commit':'a'*40,'treeDigest':D('trusted evaluator'),'predicateSetDigest':D('existing 39 criterion contracts')}
        self.m={'schema':'acp-phase6-evaluation-manifest/1','repository':'jeresaf/Application-Compiler-Platform','manifestId':'f'*32,'purpose':'CANDIDATE_QUALIFICATION','release':release,'applicationSource':{'commit':commit,'treeDigest':tree,'inventory':'source.json'},'evaluator':evaluator,'auditSessionId':'session:b0','policyRef':REF('policy'),'registrationCheckpoint':{'sequence':4,'digest':D('trusted head')},'applications':subjects,'approvalReferences':[],'executions':[execution],'criteria':[{'criterion':8,'predicateContractDigest':D('criterion 8'),'registrationRef':REF('registration'),'evidenceKind':'AUTOMATED','applicationScope':[a['application'] for a in subjects],'witnesses':[{'witnessId':c['witnessId'],'caseId':c['caseId'],'application':c['application'],'executionId':execution['executionId'],'assertionArtifactPaths':c['assertionArtifactPaths']} for c in scope['cases']],'artifactPaths':list(content)}]+([{'criterion':12,'predicateContractDigest':D('criterion 12'),'registrationRef':None,'evidenceKind':'HUMAN_REVIEW','applicationScope':[a['application'] for a in subjects],'witnesses':[],'artifactPaths':['deployment-review.json']}] if human else []),'artifacts':[{'path':p,'role':'JUNIT' if p.endswith('.xml') else 'REVIEW' if 'review' in p else 'SOURCE','mediaType':'application/xml' if p.endswith('.xml') else 'application/json','size':len(raw),'sha256':sha(raw)} for p,raw in content.items()],'createdAt':ISSUE,'expiresAt':EXPIRY}
        self.m['artifacts'].sort(key=lambda a:a['path'])
        self.payload={'schema':'acp-phase6-evidence/execution-attestation/2','laboratory':True,'release':release,'applicationSource':self.m['applicationSource'],'evaluator':evaluator,'auditSessionId':'session:b0','execution':execution,'manifestDigest':digest(canonicalize(self.m)),'registrationRef':REF('registration'),'nonce':'c'*32,'issuedAt':ISSUE,'expiresAt':EXPIRY,'monotonicDurationNanoseconds':1000,'termination':{'kind':'NORMAL_EXIT','exitCode':0},'resourceLimitEvents':[],'descendantCleanup':'COMPLETE','observedInputs':inputs,'cases':[{'witnessId':c['witnessId'],'caseId':c['caseId'],'application':c['application'],'outcome':'PASSED','assertionArtifactPaths':c['assertionArtifactPaths']} for c in scope['cases']],'isolationProfileDigest':D('synthetic isolation')}
        grant={'grantId':'grant:lab','reviewerId':'principal:reviewer','keyId':'key:reviewer','criteria':[12],'applications':[a['application'] for a in subjects],'release':release,'validFrom':ISSUE,'validUntil':EXPIRY,'independenceDigest':D('laboratory independence assertion')}
        self.context=LabContext(now=NOW,release=canonicalize(release),application_source=canonicalize(self.m['applicationSource']),evaluator=canonicalize(evaluator),subjects=canonicalize(subjects),policy_ref=canonicalize(REF('policy')),checkpoint=canonicalize(self.m['registrationCheckpoint']),scope=canonicalize(scope),registration_ref=canonicalize(REF('registration')),source_inventory=inventory,observations=(canonicalize(self.payload),),keys=keys,review_grants=(canonicalize(grant),),author_ids=frozenset({'principal:author'}),expected_checkpoint=canonicalize(self.m['registrationCheckpoint']),checkpoint_observed_at=ISSUE,checkpoint_expires_at=EXPIRY)
        self.reviews=()
        if human:
            self.review={'schema':'acp-phase6-lab-human-review/1','laboratory':True,'manifestDigest':digest(canonicalize(self.m)),'release':release,'criterion':12,'applications':[a['application'] for a in subjects],'reviewDigest':sha(content['deployment-review.json']),'reviewerId':'principal:reviewer','grantId':'grant:lab','independenceDigest':grant['independenceDigest'],'purpose':'DEPLOYMENT_REVIEW','disposition':'ACCEPT','reservations':[],'exclusions':[],'issuedAt':ISSUE,'expiresAt':EXPIRY}
            self.reviews=(self.sign(self.review,('REVIEWER',)),)

    def git(self,*args):
        return subprocess.check_output(['/usr/bin/git','-C',str(self.source),*args],stderr=subprocess.DEVNULL,text=True)

    def sign(self,payload,roles=('EXECUTOR','COLLECTOR')):
        return canonicalize({'payload':payload,'signatures':[{'signerId':'principal:'+r.lower(),'keyId':'key:'+r.lower(),'algorithm':'Ed25519','signature':base64.urlsafe_b64encode(self.private[r].sign(signature_input(payload))).decode().rstrip('=')} for r in roles]})

    def run(self):return qualify(canonicalize(self.m),self.sign(self.payload),self.reviews,self.context,self.source,self.artifacts)
    def close(self):self.temp.cleanup()


class ManifestTests(unittest.TestCase):
    def test_closed_roundtrip_and_schema_definitions(self):
        f=Fixture();self.addCleanup(f.close)
        self.assertEqual(manifest(canonicalize(f.m)),f.m)
        self.assertEqual(f.run().status,'QUALIFICATION_ONLY')
        f.m['PASS']=True
        with self.assertRaisesRegex(ValueError,'CLOSED_SCHEMA'):manifest(canonicalize(f.m))

    def test_immutable_context_and_copies(self):
        f=Fixture();self.addCleanup(f.close)
        value=f.context.value('release');value['kind']='SEALED_RELEASE'
        self.assertEqual(f.context.value('release')['kind'],'UNSEALED_CANDIDATE')
        with self.assertRaises((AttributeError,TypeError)):f.context.purpose='RELEASE'
        with self.assertRaises(ValueError):replace(f.context,release=bytearray(f.context.release))

    def test_source_and_artifact_identity_are_not_metadata(self):
        f=Fixture();self.addCleanup(f.close)
        f.run();(f.source/'Witness.java').write_text('substituted')
        with self.assertRaises(ValueError):f.run()
