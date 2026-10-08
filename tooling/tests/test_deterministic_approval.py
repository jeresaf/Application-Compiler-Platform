"""Explicit dated human approval, exact binding and preserved proposal history."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical_json import load
from canonical_ir import admit,CanonicalError
from changes import ChangeError
from deterministic_approval import APPROVED,ASSETS,DEST,WHEN,PRINCIPAL,authority,record,approved_snapshot


class DeterministicApprovalTests(unittest.TestCase):
    def test_explicit_record_reproduces_and_admits_only_exact_current_content(self):
        stored=load(DEST/'human-approval.json')
        self.assertEqual(record(),stored)
        self.assertIn('including the F-01 failure bindings',stored['statement'])
        for e in stored['examples']:
            snapshot=approved_snapshot(e['domain'])
            self.assertEqual(APPROVED[e['domain']]['contentDigest'],snapshot['contentDigest'])
            verdict=authority().verify(e['proof'],e['request'],WHEN)
            self.assertEqual(PRINCIPAL,verdict['principal']);self.assertNotEqual(PRINCIPAL,e['request']['author'])
            changed=copy.deepcopy(e['request']);changed['contentDigest']='sha256:'+'0'*64
            with self.assertRaises(ChangeError):authority().verify(e['proof'],changed,WHEN)
            # Imported status/proof data alone cannot replace the trusted host port.
            with self.assertRaises(CanonicalError):admit(snapshot,None)
    def test_stale_or_tampered_plan_source_proof_and_header_reject(self):
        from deterministic_approval import load as original
        for variant in ('plan','source','proof','header'):
            def altered(path):
                value=copy.deepcopy(original(path))
                if variant=='plan' and Path(path).name=='payment-plan.json':value['author']='somebody-else'
                if variant=='source' and Path(path).name=='payment-proposal-authoring.json':value['snapshotId']='CHANGED'
                if Path(path).name=='human-approval.json':
                    if variant=='proof':value['examples'][0]['proof']['signature']='0'*64
                    if variant=='header':value['statement']='Other approval'
                return value
            with patch('deterministic_approval.load',side_effect=altered):
                with self.assertRaises((ValueError,ChangeError)):approved_snapshot('payment')
    def test_approval_does_not_rewrite_reviewed_bytes_origins_or_target_gate(self):
        root=DEST.parents[1]
        paths=[p.relative_to(root).as_posix() for p in DEST.glob('*.json') if p.name!='human-approval.json']
        paths += ['contracts/authoring-0.4.schema.json','contracts/canonical-0.3.schema.json','contracts/change-0.3.schema.json',
            'contracts/authoring-0.3.schema.json','contracts/canonical-0.2.schema.json','contracts/change-0.2.schema.json',
            'docs/adr/0015-explicit-operation-effects-and-dataflow.md','targets/spring-vue-postgres/expected-open-blockers.json',
            'targets/spring-vue-postgres/worker/capability_contract.py']
        for path in paths:
            self.assertEqual(subprocess.check_output(['git','show','76e7700:'+path],cwd=root),(root/path).read_bytes(),path)
        for domain in APPROVED:
            snapshot=approved_snapshot(domain)
            decision=next(n for n in snapshot['content']['nodes'] if n['id']=='DEC-DETERMINISTIC-V04')
            self.assertTrue(any(o['actorType']=='AI' for o in decision['origins']))
            source=load(DEST/(domain+'-proposal-authoring.json'))
            self.assertEqual([],source['approvals']);self.assertTrue(all(n['lifecycle']=='PROPOSED' for n in source['nodes']))
