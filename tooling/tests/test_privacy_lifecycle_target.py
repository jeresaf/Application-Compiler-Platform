"""Immutable semantic authority, deployment honesty and exact privacy constraints."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from target_worker import ROOT,PROFILE,bundle_digest,TargetWorker,TargetWorkerError
from deterministic_approval import approved_snapshot
sys.path.insert(0,str(ROOT/'worker'))
from privacy_lifecycle import validate,migration,requirements
from generation import plan
from model import lower,CapabilityError

class PrivacyLifecycleTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshots={d:approved_snapshot(d) for d in ('payment','case-management')}
        cls.templates={p.relative_to(ROOT/'templates').as_posix():p.read_text() for p in (ROOT/'templates').rglob('*') if p.is_file()}
    def test_prior_sealed_releases_and_historical_contract_are_immutable(self):
        current=json.loads((ROOT/'release-contract.json').read_text())
        old=json.loads(subprocess.check_output(['git','show','9703fc9:targets/spring-vue-postgres/release-contract.json']))
        for identity,release in old['releases'].items():self.assertEqual(release,current['releases'][identity])
        self.assertEqual(subprocess.check_output(['git','show','9703fc9:targets/spring-vue-postgres/expected-open-blockers-v3.json']),(ROOT/'expected-open-blockers-v3.json').read_bytes())
        prior=subprocess.run(['git','show','HEAD^:targets/spring-vue-postgres/expected-open-blockers-v4.json'],capture_output=True)
        if prior.returncode==0:self.assertEqual(prior.stdout,(ROOT/'expected-open-blockers-v4.json').read_bytes())
        self.assertEqual('0.2.0',PROFILE['targetIRVersion'])
    def test_historical_migrations_and_portable_deployment_obligations(self):
        for domain,snapshot in self.snapshots.items():
            nodes=snapshot['content']['nodes'];validate(nodes)
            model=lower(nodes,PROFILE,'0.3.0');first=plan(model,self.templates,PROFILE,build={'bundleDigest':'sha256:'+bundle_digest(),'canonicalSnapshotDigest':snapshot['contentDigest']})
            self.assertEqual(first,plan(model,self.templates,PROFILE,build={'bundleDigest':'sha256:'+bundle_digest(),'canonicalSnapshotDigest':snapshot['contentDigest']}))
            files={a['path']:a['text'] for a in first}
            for v in ('V1__initial.sql','V2__delivery_jobs.sql'):
                self.assertEqual((ROOT/'historical/delivery-0.2'/(domain+'-'+v)).read_bytes(),files['database/'+v].encode())
            self.assertEqual(migration(nodes),files['database/V3__privacy_lifecycle.sql'])
            obligations=json.loads(files['acp/deployment-requirements.json']);by={n['id']:n for n in nodes}
            self.assertTrue(obligations['requirements'])
            for r in obligations['requirements']:
                self.assertEqual('OUTSTANDING',r['status']);self.assertEqual(by[r['origin']['id']]['revision'],r['origin']['revision'])
            build=json.loads(files['acp/provenance.json'])['build'];self.assertEqual('0.2.0',build['targetIRVersion'])
            self.assertEqual(hashlib.sha256(files['acp/deployment-requirements.json'].encode()).hexdigest(),build['deploymentRequirements']['sha256'])
            for path,digest in build['migrationDigests'].items():self.assertEqual(hashlib.sha256(files[path].encode()).hexdigest(),digest)
            self.assertIn('LEGACY_UNPROVEN',files['database/V3__privacy_lifecycle.sql']);self.assertNotIn('CURRENT_TIMESTAMP',files['database/V3__privacy_lifecycle.sql'])
    def test_unsupported_privacy_forms_reject_and_replacement_is_not_inferred(self):
        for domain,snapshot in self.snapshots.items():
            for kind,key,value in [('DataClassification','export','PERMISSION_REQUIRED'),('DataClassification','redactionScope','DOMAIN'),('DataClassification','encryptAtRest',False),('Retention','trigger','CREATED'),('DeletionPolicy','mode','DELETE'),('LegalHold','releaseMode','PERMANENT'),('DataLifecycle','anchor',{'kind':'CREATED_COMMIT','instant':'COMMITTED_ENTRY'})]:
                nodes=copy.deepcopy(snapshot['content']['nodes']);next(n for n in nodes if n['kind']==kind)['data'][key]=value
                with self.assertRaises((CapabilityError,KeyError)):validate(nodes)
        nodes=copy.deepcopy(self.snapshots['payment']['content']['nodes']);next(n for n in nodes if n['kind']=='DeletionPolicy')['data']['anonymizationEffects'][0]['replacement']['value']='0'
        with self.assertRaisesRegex(CapabilityError,'DISPOSAL_EXACT_MONEY_CONSTANT_REQUIRED'):validate(nodes)
    def test_old_profile_ir_is_rejected_at_explicit_generation_boundary(self):
        snapshot=self.snapshots['payment'];model=lower(snapshot['content']['nodes'],PROFILE,'0.3.0');model['profile']='acp-spring-vue-postgres/0.2.0';model['generator']='acp-spring-vue-generator/0.2.0'
        with self.assertRaisesRegex(TargetWorkerError,'TARGET_IR_VERSION'):TargetWorker().call('plan',{'model':model,'inventory':[]})
