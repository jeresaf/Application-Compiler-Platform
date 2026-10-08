"""Successor release/version, provenance, constraints and preserved migration evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from target_worker import ROOT,PROFILE,ProductionTarget,bundle_digest,TargetWorker,TargetWorkerError
from target_release import verify_release,verify_preserved_releases
from deterministic_approval import approved_snapshot
sys.path.insert(0,str(ROOT/'worker'))
from generation import plan,schema
from model import lower,CapabilityError
from delivery_jobs import validate

class DeliveryJobTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshots={d:approved_snapshot(d) for d in ('payment','case-management')}
        cls.templates={p.relative_to(ROOT/'templates').as_posix():p.read_text() for p in (ROOT/'templates').rglob('*') if p.is_file()}
    def test_exact_release_identity_and_changed_bundle_requires_new_version(self):
        self.assertEqual('acp-spring-vue-postgres/0.2.0',PROFILE['profile'])
        self.assertEqual('acp-spring-vue-generator/0.2.0',PROFILE['generator'])
        verify_release(PROFILE,bundle_digest())
        with self.assertRaisesRegex(ValueError,'GENERATOR_VERSION_REUSE'):verify_release(PROFILE,'f'*64)
        with patch('target_worker.bundle_digest',return_value='f'*64):
            with self.assertRaisesRegex(ValueError,'GENERATOR_VERSION_REUSE'):ProductionTarget()
        previous=json.loads((ROOT/'release-contract.json').read_text());tampered=copy.deepcopy(previous);tampered['releases'][PROFILE['profile']]['bundleDigest']='f'*64
        with self.assertRaisesRegex(ValueError,'RELEASE_IDENTITY_REWRITE'):verify_preserved_releases(previous,tampered)
        changed=copy.deepcopy(PROFILE);changed['generator']='acp-spring-vue-generator/0.2.1'
        with self.assertRaisesRegex(ValueError,'GENERATOR_VERSION_UNRELEASED'):verify_release(changed,bundle_digest())
    def test_deterministic_bytes_and_portable_exact_build_provenance(self):
        for domain,snapshot in self.snapshots.items():
            model=lower(snapshot['content']['nodes'],PROFILE,'0.3.0');self.assertEqual('0.2.0',model['version'])
            build={'bundleDigest':'sha256:'+bundle_digest(),'canonicalSnapshotDigest':snapshot['contentDigest'],'features':['acp.deterministic-execution.0.4'],'compiler':'acp-reference-compiler/0.1.0','pipeline':'acp-reference-pipeline/0.1.0'}
            first=plan(model,self.templates,PROFILE,build=build);self.assertEqual(first,plan(model,self.templates,PROFILE,build=build))
            artifacts={a['path']:a['text'] for a in first};provenance=json.loads(artifacts['acp/provenance.json'])
            for k,v in build.items():self.assertEqual(v,provenance['build'][k])
            self.assertEqual(PROFILE['profile'],provenance['build']['targetProfile']);self.assertEqual(PROFILE,json.loads(artifacts['acp/profile.json']))
            self.assertEqual('0.3.0',provenance['build']['canonicalVersion']);self.assertEqual('0.4.0',provenance['build']['semanticModelVersion'])
            self.assertEqual('2026d',provenance['build']['tzdb']['version'])
            self.assertEqual(hashlib.sha256(artifacts['backend/src/main/resources/acp-tzdb-2026d.json'].encode()).hexdigest(),provenance['build']['tzdb']['sha256'])
            self.assertEqual((ROOT/'historical/invocation-0.1'/(domain+'-V1__initial.sql')).read_text(),artifacts['database/V1__initial.sql'])
            transition=json.loads(artifacts['acp/target-upgrade.json']);self.assertEqual(PROFILE['profile'],transition['to']['targetProfile'])
            self.assertEqual('acp-spring-vue-postgres/0.1.0',transition['from']['profile'])
            for migration in transition['migrations']:self.assertEqual(hashlib.sha256(artifacts[migration['path']].encode()).hexdigest(),migration['sha256'])
            for mapping in provenance['artifacts']:self.assertEqual('sha256:'+hashlib.sha256(artifacts[mapping['artifact']].encode()).hexdigest(),mapping['artifactDigest'])
    def test_unsupported_delivery_schedule_and_job_forms_reject(self):
        for domain,snapshot in self.snapshots.items():
            nodes=snapshot['content']['nodes'];validate(nodes)
            for kind,key,value in [('DeliveryPolicy','guarantee','AT_MOST_ONCE'),('DeliveryPolicy','ordering','UNORDERED'),('Schedule','tzdbVersion','host'),('Schedule','overlap','LATER'),('Job','missedOccurrences','RUN_LATEST'),('Job','timeoutSeconds',31)]:
                changed=copy.deepcopy(nodes);next(n for n in changed if n['kind']==kind)['data'][key]=value
                with self.assertRaises(CapabilityError,msg=(domain,kind,key)):validate(changed)
    def test_pinned_data_identity_and_explicit_ir_incompatibility(self):
        data=json.loads(self.templates['backend/src/main/resources/acp-tzdb-2026d.json']);self.assertEqual('2026d',data['version'])
        import tzdata
        from importlib.resources import files
        self.assertEqual(tzdata.IANA_VERSION,data['version'])
        for zone,entry in data['zones'].items():self.assertEqual(hashlib.sha256(files('tzdata.zoneinfo').joinpath(*zone.split('/')).read_bytes()).hexdigest(),entry['tzifSha256'])
        snapshot=self.snapshots['payment'];old=lower(snapshot['content']['nodes'],PROFILE,'0.3.0');old['version']='0.1.0'
        # Old IR is never reinterpreted: worker validation/negotiation remains closed.
        with self.assertRaisesRegex(TargetWorkerError,'TARGET_IR_VERSION'):TargetWorker().call('plan',{'model':old,'inventory':[]})

    def test_legacy_planning_keeps_v1_only_and_portable_provenance(self):
        from execution_approval import approved_snapshot as legacy_snapshot
        for domain in ('payment','case-management'):
            snapshot=legacy_snapshot(domain);model=lower(snapshot['content']['nodes'],PROFILE,'0.2.0')
            artifacts={a['path']:a['text'] for a in plan(model,self.templates,PROFILE)}
            self.assertIn('database/V1__initial.sql',artifacts)
            self.assertNotIn('database/V2__delivery_jobs.sql',artifacts)
            self.assertEqual('0.2.0',json.loads(artifacts['acp/provenance.json'])['build']['canonicalVersion'])
