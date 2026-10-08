"""Exact approved 0.3 adoption, deterministic evolution and fail-closed subsets."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical_json import load
from deterministic_approval import approved_snapshot,APPROVED
from target_worker import ROOT,PROFILE,TargetWorker,TargetWorkerError
sys.path.insert(0,str(ROOT/'worker'))
from generation import plan
from model import lower,CapabilityError
from execution_codegen import ExecutionGenerator
from compiler_contracts import fingerprint


class InvocationTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshots={d:approved_snapshot(d) for d in APPROVED}
        cls.templates={p.relative_to(ROOT/'templates').as_posix():p.read_text() for p in (ROOT/'templates').rglob('*') if p.is_file()}

    def payload(self,nodes,version='0.3.0'):
        return {'nodes':nodes,'canonicalVersion':version,'decisions':PROFILE['decisions'],
            'required':['semantic.execution-dataflow/0.3','acp.deterministic-execution.0.4']}

    def test_approved_version_reaches_real_worker_without_missing_semantic_review(self):
        for domain,snapshot in self.snapshots.items():
            self.assertEqual(APPROVED[domain]['contentDigest'],snapshot['contentDigest'])
            with self.assertRaises(TargetWorkerError) as e:TargetWorker().call('negotiate',self.payload(snapshot['content']['nodes']))
            blockers=str(e.exception).split(';')
            self.assertTrue(all(b.startswith('UNSUPPORTED:') for b in blockers),str(e.exception))
            self.assertIn('UNSUPPORTED:DeliveryPolicy/0.2.0',blockers)
            for k in ('Query','Failure','RatePolicy','IdempotencyPolicy','RetryPolicy'):
                self.assertNotIn('UNSUPPORTED:'+k+'/0.2.0',blockers)
            old=self.payload(snapshot['content']['nodes'],'0.2.0')
            with self.assertRaisesRegex(TargetWorkerError,'SEMANTIC_VALIDATION'):TargetWorker().call('negotiate',old)
            missing=self.payload(snapshot['content']['nodes']);missing['required'].remove('acp.deterministic-execution.0.4')
            with self.assertRaisesRegex(TargetWorkerError,'DETERMINISTIC_FEATURE_REQUIRED'):TargetWorker().call('negotiate',missing)

    def test_semantic_evolution_changes_real_component_plan_and_requires_fresh_approval(self):
        nodes=self.snapshots['payment']['content']['nodes']
        artifact=lambda ns:fingerprint(plan(lower(ns,PROFILE,'0.3.0'),self.templates,PROFILE),'target-plan')
        original=artifact(nodes)
        mutations={
            'Query':lambda d:d['orderBy'][0].update(direction='DESC'),
            'Command':lambda d:d['failureBindings'].insert(1,{'failure':copy.deepcopy(d['failureBindings'][0]['failure']),'stage':'PRE_STATE','trigger':{'kind':'PREDICATE','condition':{'tag':'literal','type':{'kind':'Boolean'},'value':True}}}),
            'RatePolicy':lambda d:d.update(burst=11),
            'IdempotencyPolicy':lambda d:d.update(windowSeconds=86401),
            'RetryPolicy':lambda d:d.update(initialSeconds=2),
        }
        for kind,mutate in mutations.items():
            changed=copy.deepcopy(nodes);mutate(next(n for n in changed if n['kind']==kind)['data'])
            digest=artifact(changed);self.assertNotEqual(original,digest,kind);self.assertEqual(digest,artifact(changed),kind)
            from deterministic_approval import load as real_load
            def altered(path):
                data=real_load(path)
                if Path(path).name=='payment-canonical-candidate.json':data['content']['nodes']=copy.deepcopy(changed)
                return data
            with patch('deterministic_approval.load',side_effect=altered):
                with self.assertRaisesRegex(ValueError,'FRESH_HUMAN_APPROVAL_REQUIRED'):approved_snapshot('payment')

    def test_unsupported_ordered_types_policies_and_preflight_dataflow_reject(self):
        nodes=copy.deepcopy(self.snapshots['payment']['content']['nodes']);by={n['id']:n for n in nodes}
        by['QUERY-TASKS']['data']['orderBy'].insert(0,{'field':{'id':'FLD-AMOUNT','revision':2},'direction':'ASC'})
        with self.assertRaisesRegex(CapabilityError,'ORDERED_TYPE_UNSUPPORTED'):ExecutionGenerator(nodes,'0.3.0').validate()
        nodes=copy.deepcopy(self.snapshots['payment']['content']['nodes'])
        next(n for n in nodes if n['kind']=='IdempotencyPolicy')['data']['keyType']={'kind':'Integer'}
        with self.assertRaisesRegex(CapabilityError,'IDEMPOTENCY_'):ExecutionGenerator(nodes,'0.3.0').validate()
        nodes=copy.deepcopy(self.snapshots['payment']['content']['nodes'])
        next(n for n in nodes if n['kind']=='RatePolicy')['data']['requests']=2**31
        with self.assertRaisesRegex(CapabilityError,'RATE_SUBSET_REQUIRED'):ExecutionGenerator(nodes,'0.3.0').validate()

    def test_new_contract_accepts_only_real_exact_expected_blocked_state(self):
        from phase6_open_state import assert_expected_blocked
        contract=load(ROOT/'expected-open-blockers-v3.json')
        report={'targetManifest':TargetWorker().call('manifest',{}),'mode':'FULL_NEGOTIATED_TARGET_GATE','result':'BLOCKED','domains':{}}
        for domain,snapshot in self.snapshots.items():
            with self.assertRaises(TargetWorkerError) as e:TargetWorker().call('lower',self.payload(snapshot['content']['nodes']))
            report['domains'][domain]={'canonicalDigest':snapshot['contentDigest'],'result':'BLOCKED','diagnostics':[{'code':'ACP-COMPILER-CAPABILITY','stage':'NegotiateLower'}],
                'admission':{'operation':'lower','result':'BLOCKED','error':str(e.exception)},'targetAdmission':str(e.exception)}
        self.assertTrue(assert_expected_blocked(report,contract))
        for change in ('added','removed','old-digest','review-defect'):
            changed=copy.deepcopy(report);entry=changed['domains']['payment']
            if change=='old-digest':entry['canonicalDigest']=load(ROOT/'expected-open-blockers.json')['domains']['payment']['canonicalDigest']
            else:
                error=entry['targetAdmission']
                if change=='added':error+=';UNSUPPORTED:Surprise/1'
                if change=='removed':error=';'.join(error.split(';')[1:])
                if change=='review-defect':error+=';QUERY_ORDERING_REVIEW_REQUIRED:QUERY-TASKS'
                entry['admission']['error']=entry['targetAdmission']=error
            with self.assertRaises(ValueError):assert_expected_blocked(changed,contract)
