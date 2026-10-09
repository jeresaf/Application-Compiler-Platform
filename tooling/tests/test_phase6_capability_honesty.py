"""Every claim is inventoried; narrowing cannot silently change target admission."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical_json import load
from target_worker import ROOT,TargetWorker,TargetWorkerError,PROFILE
from execution_approval import approved_snapshot


class CapabilityHonestyTests(unittest.TestCase):
    def test_inventory_covers_every_manifest_claim_and_expected_narrowing(self):
        manifest=TargetWorker().call('manifest',{})
        audit=load(ROOT/'evidence/task-interface-capability-audit.json')
        self.assertEqual(audit['capabilities'],manifest['capabilities'])
        self.assertEqual('INCOMPLETE',manifest['releaseStatus'])
        for capability,entry in manifest['capabilities'].items():
            self.assertTrue(entry['constraints'],capability);self.assertTrue(entry['evidence'],capability)
        for kind in ('Backup','Recovery','PerformanceRequirement','AccessibilityRequirement','Constraint','ObservabilityRequirement'):
            self.assertEqual('OBLIGATION_ONLY',manifest['capabilities'][kind+'/0.2.0']['status'])
        contract=load(ROOT/'expected-open-blockers.json')
        self.assertEqual('1.1.0',contract['contractVersion'])
        for d in ('payment','case-management'):
            snapshot=approved_snapshot(d)
            with self.assertRaises(TargetWorkerError) as error:
                TargetWorker().call('negotiate',{'nodes':snapshot['content']['nodes'],'required':['semantic.execution-dataflow/0.3'],
                    'decisions':PROFILE['decisions'],'canonicalVersion':'0.2.0'})
            self.assertEqual(sorted(contract['domains'][d]['blockers']),sorted(str(error.exception).split(';')))
            for kind in ('Table','Wizard','PermissionBoundary','Failure'):
                self.assertIn('UNSUPPORTED:'+kind+'/0.2.0',str(error.exception))

    def test_unenforced_invariant_cannot_be_admitted(self):
        nodes=approved_snapshot('payment')['content']['nodes']
        command=next(n for n in nodes if n['kind']=='Command')
        command['data']['invariants']=[]
        with self.assertRaisesRegex(TargetWorkerError,'UNENFORCED_RESOURCE_INVARIANT'):
            TargetWorker().call('negotiate',{'nodes':nodes,'required':['semantic.execution-dataflow/0.3'],
                'decisions':PROFILE['decisions'],'canonicalVersion':'0.2.0'})
        # Numeric equality cannot use Java Object.equals across typed encodings.
        # Reject that otherwise meaningful predicate instead of claiming enforcement.
        nodes=approved_snapshot('payment')['content']['nodes']
        money=next(n for n in nodes if n['id']=='FLD-AMOUNT')['data']['type']
        predicate={'tag':'binary','op':'eq','left':{'tag':'literal','type':money,'value':'1.00'},
            'right':{'tag':'literal','type':money,'value':'1.00'}}
        next(n for n in nodes if n['kind']=='Policy')['data']['predicate']=predicate
        with self.assertRaisesRegex(TargetWorkerError,'POLICY_COMPARISON_TYPE_UNSUPPORTED'):
            TargetWorker().call('negotiate',{'nodes':nodes,'required':['semantic.execution-dataflow/0.3'],
                'decisions':PROFILE['decisions'],'canonicalVersion':'0.2.0'})
