"""Synthetic authority fixtures only: no enrolled trust, approvals or closure evidence."""
import base64
from functools import lru_cache
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from engineering.evidence_admission import release as R
from engineering.evidence_admission.encoding import canonicalize,signature_input
from engineering.evidence_admission.registration import source_inventory,source_tree_digest
from tooling.audit import criteria


def stamp(t):return t.strftime('%Y-%m-%dT%H:%M:%SZ')


@lru_cache(maxsize=1)
def native_binding():
    return canonicalize(criteria.current_binding())


class Fixture:
    def __init__(self):
        self.temp=tempfile.TemporaryDirectory(prefix='acp-release-unit-');self.root=Path(self.temp.name)
        self.now=datetime.now(timezone.utc).replace(microsecond=0);self.start=stamp(self.now-timedelta(seconds=30));self.end=stamp(self.now+timedelta(minutes=10))
        self.private={};self.keys={}
        for role in ('PROJECT_AUTHORITY','SECURITY_AUTHORITY','REVOCATION','REGISTRAR','INDEPENDENT_REVIEWER','EXECUTOR','COLLECTOR'):
            key=Ed25519PrivateKey.generate();self.private[role]=key
            self.keys[role]=R.TrustedKey(role,role,key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw),role,self.now-timedelta(days=1),self.now+timedelta(days=1))
        self.source=self.root/'source';self.source.mkdir()
        # Pin actual loaded admission source, but do not execute anything from
        # this independently materialized source repository.
        for p in (ROOT/'engineering/evidence_admission').rglob('*.py'):
            q=self.source/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
        q=self.source/'tooling/audit/criteria.py';q.parent.mkdir(parents=True);shutil.copyfile(ROOT/'tooling/audit/criteria.py',q)
        (self.source/'Witness.java').write_text('class Witness { void freshHostedSuccessorAuditPerformed() {} }')
        (self.source/'requirements.txt').write_text('authenticated fixture lock\n')
        for cmd in (['init','-q'],['add','.'],['-c','user.name=Synthetic Fixture','-c','user.email=fixture@invalid','commit','-qm','synthetic source, not accepted history']):
            subprocess.run(['git','-c','commit.gpgsign=false','-c','core.hooksPath=/dev/null','-C',str(self.source),*cmd],check=True,capture_output=True,timeout=30)
        self.commit=subprocess.check_output(['git','-C',str(self.source),'rev-parse','HEAD'],text=True).strip();self.inventory=source_inventory(self.source)
        self.description={'commit':self.commit,'treeDigest':source_tree_digest(self.inventory),'entrypoint':'Witness.java','dependencyPath':'requirements.txt','dependencyDigest':R.sha((self.source/'requirements.txt').read_bytes())}
        self.binding=json.loads(native_binding());self.binding['executionCommit']=self.commit
        self.artifacts=self.root/'artifacts';self.artifacts.mkdir()
        self.cases=[]
        for domain in self.binding['canonicalDigests']:
            name=domain+'.xml';(self.artifacts/name).write_text('<testsuite tests="1"><testcase classname="Witness" name="freshHostedSuccessorAuditPerformed"/></testsuite>')
            self.cases.append({'criterion':33,'application':domain,'witnessId':'fixture-'+domain,'caseId':'fresh-hosted','sourcePath':'Witness.java','className':'Witness','method':'freshHostedSuccessorAuditPerformed','assertionArtifactPaths':[name]})
        self.record=dict(self.binding,criterion=33,evaluatedAt=self.now.isoformat(),artifacts=[{'path':p.name,'sha256':R.sha(p.read_bytes())} for p in sorted(self.artifacts.iterdir())])
        operational=[dict(identity=k.identity,principal=k.principal,public=k.public.hex(),role=k.role,validFrom=stamp(k.valid_from),validUntil=stamp(k.valid_until)) for role,k in self.keys.items() if role in ('REGISTRAR','INDEPENDENT_REVIEWER','EXECUTOR','COLLECTOR')]
        self.cfg=dict(schema='acp-release-authority/1',issuedAt=self.start,expiresAt=self.end,release=R.RELEASE,seal=R.SEAL,evaluator=self.description,execution=self.description,witness=self.description,application=self.description,keys=operational,decisions={k:R.sha(('SYNTHETIC '+k).encode()) for k in ('keyCustody','executionInfrastructure','registrationScope')},executionContract={'executableDigest':R.sha(b'fixture executable'),'argv':['/fixture/verifier'],'environmentDigest':R.sha(b'fixture env'),'workingDirectory':'/fixture','timeoutSeconds':60,'dependencyDigest':self.description['dependencyDigest']})
        self.reg=dict(schema='acp-release-registry/1',issuedAt=self.start,expiresAt=self.end,configurationDigest='',release=R.RELEASE,seal=R.SEAL,predicateDigest=R.sha(Path(criteria.__file__).read_bytes()),cases=self.cases)
        self.rev=dict(schema='acp-release-revocation/1',issuedAt=self.start,expiresAt=self.end,configurationDigest='',revoked=[])
        self.refresh()

    def sign(self,p,roles):
        return canonicalize({'payload':p,'signatures':[{'keyId':role,'signature':base64.urlsafe_b64encode(self.private[role].sign(signature_input(p))).decode().rstrip('=')} for role in roles]})

    def refresh(self):
        self.configuration=self.sign(self.cfg,['PROJECT_AUTHORITY','SECURITY_AUTHORITY']);self.reg['configurationDigest']=R.sha(self.configuration);self.rev['configurationDigest']=R.sha(self.configuration)
        self.registry=self.sign(self.reg,['REGISTRAR','INDEPENDENT_REVIEWER']);self.revocation=self.sign(self.rev,['REVOCATION'])
        self.pins=R.HostPins(tuple(self.keys[k] for k in ('PROJECT_AUTHORITY','SECURITY_AUTHORITY','REVOCATION')),R.sha(self.configuration),R.sha(self.revocation),R.sha(self.registry),self.inventory,self.inventory,self.inventory,self.inventory,self.commit,self.commit,self.commit,self.commit,self.reg['predicateDigest'],'synthetic-challenge-0000000000000000001',self.now)
        self.att=dict(schema='acp-release-execution/1',issuedAt=stamp(self.now),expiresAt=self.end,configurationDigest=R.sha(self.configuration),registryDigest=R.sha(self.registry),revocationDigest=R.sha(self.revocation),release=R.RELEASE,seal=R.SEAL,predicateDigest=self.reg['predicateDigest'],evaluatorCommit=self.commit,executionCommit=self.commit,witnessCommit=self.commit,applicationCommit=self.commit,recordDigest=R.sha(canonicalize(self.record)),nonce=self.pins.nonce,observedInputs={**{k:self.cfg[k] for k in ('evaluator','execution','witness','application')},'contract':self.cfg['executionContract']},artifacts={p.name:R.sha(p.read_bytes()) for p in self.artifacts.iterdir()},cases=self.cases,exitCode=0,cleanup='COMPLETE',startedAt=self.start,finishedAt=stamp(self.now),resourceLimitEvents=[],exitSignal=None)
        self.execution=self.sign(self.att,['EXECUTOR','COLLECTOR'])

    def run(self,**changes):
        args=dict(pins=self.pins,configuration=self.configuration,revocation=self.revocation,registry=self.registry,execution=self.execution,record=self.record,binding=self.binding,artifact_root=self.artifacts,evaluator_root=self.source,execution_root=self.source,witness_root=self.source,application_root=self.source)
        args.update(changes)
        with patch.object(criteria,'current_binding',return_value=dict(self.binding)):
            return R.evaluate(**args)


class ReleaseTests(unittest.TestCase):
    def setUp(self):self.f=Fixture();self.addCleanup(self.f.temp.cleanup)

    def test_authenticated_fixture_runs_exact_unchanged_33_predicate(self):
        f=self.f;before=criteria.validate.__code__;result=f.run()
        self.assertEqual(result['status'],'PASS');self.assertEqual(result['releaseDisposition'],'PHASE6_RELEASE_CLOSURE_BLOCKED');self.assertIs(criteria.validate.__code__,before)
        with self.assertRaisesRegex(ValueError,'REGISTERED_TEST_SOURCE_REQUIRED'):
            criteria.validate(33,{p.name:p for p in f.artifacts.iterdir()},f.binding,f.now,{})

    def test_no_default_release_authority(self):
        with self.assertRaisesRegex(ValueError,'RELEASE_AUTHORITY_NOT_CONFIGURED'):self.f.run(pins=None)

    def test_wrong_or_unsealed_release(self):
        self.f.cfg['release']='acp-spring-vue-postgres/0.6.0';self.f.refresh()
        with self.assertRaisesRegex(ValueError,'WRONG_RELEASE_PROFILE'):self.f.run()

    def test_forged_signature(self):
        f=self.f;value=json.loads(f.execution);value['payload']['nonce']='forged'
        with self.assertRaisesRegex(ValueError,'INVALID_SIGNATURE'):f.run(execution=canonicalize(value))

    def test_missing_independent_collector(self):
        with self.assertRaisesRegex(ValueError,'RELEASE_SIGNATURE_THRESHOLD'):self.f.run(execution=self.f.sign(self.f.att,['EXECUTOR']))

    def test_revoked_executor_and_principal(self):
        for identity in ('EXECUTOR','COLLECTOR'):
            with self.subTest(identity=identity):
                self.f.rev['revoked']=[identity];self.f.refresh()
                with self.assertRaisesRegex(ValueError,'REVOKED'):self.f.run()

    def test_revoked_authority(self):
        for role in ('PROJECT_AUTHORITY','REVOCATION'):
            with self.subTest(role=role):
                self.f.rev['revoked']=[role];self.f.refresh()
                with self.assertRaisesRegex(ValueError,'REVOKED'):self.f.run()

    def test_stale_config_and_host_context(self):
        self.f.cfg['expiresAt']=self.f.start;self.f.refresh()
        with self.assertRaisesRegex(ValueError,'STALE_RELEASE'):self.f.run()
        with self.assertRaisesRegex(ValueError,'STALE_HOST_CONTEXT'):self.f.run(pins=replace(self.f.pins,now=self.f.now-timedelta(hours=1)))

    def test_old_revocation_checkpoint(self):
        old=self.f.revocation;self.f.rev['revoked']=['EXECUTOR'];self.f.refresh()
        with self.assertRaisesRegex(ValueError,'RELEASE_RECORD_PIN'):self.f.run(revocation=old)

    def test_registry_and_evaluator_pins(self):
        for name in ('registry_digest','predicate_digest','witness_commit','execution_commit','application_commit'):
            with self.subTest(pin=name),self.assertRaises(ValueError):self.f.run(pins=replace(self.f.pins,**{name:'0'*40}))

    def test_wrong_nonce_wrong_artifacts_and_wrong_observed_inputs(self):
        for field,value in [('nonce','other-reservation'),('recordDigest',R.sha(b'wrong')),('artifacts',{}),('observedInputs',{}),('cleanup','INCOMPLETE'),('cases',[])]:
            with self.subTest(field=field):
                self.f.refresh();self.f.att[field]=value
                with self.assertRaisesRegex(ValueError,'AUTHENTICATED_EXECUTION_BINDING'):self.f.run(execution=self.f.sign(self.f.att,['EXECUTOR','COLLECTOR']))

    def test_duplicate_and_unrelated_registration(self):
        self.f.reg['cases']=self.f.cases+[self.f.cases[0]];self.f.refresh()
        with self.assertRaisesRegex(ValueError,'DUPLICATE_REGISTERED'):self.f.run()
        self.f.reg['cases']=self.f.cases[:1];self.f.refresh()
        with self.assertRaisesRegex(ValueError,'INCOMPLETE_RELEASE_APPLICATIONS'):self.f.run()

    def test_missing_approval_decision_and_unknown_schema(self):
        del self.f.cfg['decisions']['keyCustody'];self.f.refresh()
        with self.assertRaisesRegex(ValueError,'CLOSED_RELEASE_RECORD'):self.f.run()

    def test_source_modification_rejected(self):
        (self.f.source/'Witness.java').write_text('changed source')
        with self.assertRaises(ValueError):self.f.run()

    def test_junit_failure_and_retry_rejected_even_with_valid_attestation(self):
        for tag in ('failure','skipped','rerunFailure'):
            with self.subTest(tag=tag):
                p=self.f.artifacts/'payment.xml';p.write_text('<testsuite><testcase classname="Witness" name="freshHostedSuccessorAuditPerformed"><'+tag+'/></testcase></testsuite>')
                for row in self.f.record['artifacts']:
                    if row['path']==p.name:row['sha256']=R.sha(p.read_bytes())
                self.f.refresh()
                with self.assertRaisesRegex(ValueError,'TEST_NOT_GREEN_OR_RETRIED'):self.f.run()

    def test_artifact_symlink_and_unexpected_file(self):
        p=self.f.artifacts/'extra';p.write_bytes(b'not registered')
        with self.assertRaises(ValueError):self.f.run()
        p.unlink();p=self.f.artifacts/'payment.xml';raw=p.read_bytes();p.unlink();target=self.f.root/'external';target.write_bytes(raw);p.symlink_to(target)
        with self.assertRaises(ValueError):self.f.run()

    def test_signal_resource_timeout_rejected(self):
        for field,value in [('exitSignal',9),('resourceLimitEvents',['OOM']),('startedAt',stamp(self.f.now-timedelta(hours=2)))]:
            with self.subTest(field=field):
                self.f.refresh();self.f.att[field]=value
                with self.assertRaisesRegex(ValueError,'EXECUTION_OUTCOME'):self.f.run(execution=self.f.sign(self.f.att,['EXECUTOR','COLLECTOR']))

    def test_unknown_fields_rejected(self):
        self.f.cfg['unapproved']='extra';self.f.refresh()
        with self.assertRaisesRegex(ValueError,'CLOSED_RELEASE_RECORD'):self.f.run()

    def test_native_predicates_and_laboratory_sources_unchanged(self):
        paths=['tooling/audit/criteria.py','tooling/audit/phase6.py','engineering/evidence_admission/scoped']
        self.assertEqual(subprocess.check_output(['git','diff','df8e03c','--',*paths],cwd=ROOT),b'')


if __name__=='__main__':unittest.main()
