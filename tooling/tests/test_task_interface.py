"""Closed UI lowering and exact historical byte preservation."""
import copy,hashlib,json,subprocess,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deterministic_approval import approved_snapshot
from target_worker import ROOT,PROFILE,TargetWorker,TargetWorkerError
sys.path.insert(0,str(ROOT/'worker'))
from task_ui import validate
from model import CapabilityError
class TaskInterfaceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.snapshots={d:approved_snapshot(d) for d in ('payment','case-management')}
 def test_exact_valid_model_and_successful_worker_negotiation(self):
  for d,s in self.snapshots.items():
   ui=validate(s['content']['nodes']);self.assertEqual([r['id'] for r in ui['screen']['data']['content']],[ui[k]['id'] for k in ('search','table','wizard')]);self.assertEqual('QueryCompletion.resourceId',ui['selectionBinding']['source'])
   r=TargetWorker().call('negotiate',{'nodes':s['content']['nodes'],'canonicalVersion':'0.3.0','required':['semantic.execution-dataflow/0.3','acp.deterministic-execution.0.4'],'decisions':PROFILE['decisions']});self.assertTrue(r['accepted'])
 def test_negative_forms_fail_closed_for_each_domain(self):
  variants=[('Screen','content',[]),('Form','useCase',{'id':'QUERY-TASKS','revision':3}),('InputControl','purpose','DATE'),('InputControl','required',False),('Table','columns',[{'id':'FLD-TASK-SUMMARY','revision':2}]),('Filter','operator','EQUALS'),('Filter','inputField',{'id':'OUTPUT-TASK-TEXT','revision':2}),('Search','filters',[]),('Wizard','steps',[]),('WizardStep','requiresPrevious',True),('Action','confirmation','NONE'),('Action','permissions',[]),('Screen','boundary',{'id':'NOT-FOUND','revision':1}),('PermissionBoundary','actor',{'id':'ACT-NOT-USER','revision':2}),('ViewState','state','CUSTOM'),('ResponsivePolicy','preserveActions',False),('ResponsivePolicy','preserveReadingOrder',False),('AccessibilityRequirement','checks',['LABELS'])]
  for d,s in self.snapshots.items():
   for kind,key,value in variants:
    with self.subTest(domain=d,kind=kind,key=key):
     ns=copy.deepcopy(s['content']['nodes']);next(n for n in ns if n['kind']==kind)['data'][key]=value
     with self.assertRaises((CapabilityError,KeyError)):validate(ns)
     with self.assertRaises(TargetWorkerError):TargetWorker().call('negotiate',{'nodes':ns,'canonicalVersion':'0.3.0','required':['semantic.execution-dataflow/0.3','acp.deterministic-execution.0.4'],'decisions':PROFILE['decisions']})
   ns=copy.deepcopy(s['content']['nodes']);extra=copy.deepcopy(next(n for n in ns if n['kind']=='Screen'));extra['id']='SECOND';ns.append(extra)
   with self.assertRaises(CapabilityError):validate(ns)
   ns=copy.deepcopy(s['content']['nodes']);next(n for n in ns if n['id']=='VIEW-ERROR')['data'].pop('recovery')
   with self.assertRaises(CapabilityError):validate(ns)
   ns=copy.deepcopy(s['content']['nodes']);next(n for n in ns if n['id']=='INPUT-TASK-TEXT')['data']['type']={'kind':'Boolean'}
   with self.assertRaises(CapabilityError):validate(ns)
   ns=copy.deepcopy(s['content']['nodes']);next(n for n in ns if n['kind']=='Wizard')['data']['steps']*=2
   with self.assertRaises(CapabilityError):validate(ns)
   ns=copy.deepcopy(s['content']['nodes']);next(n for n in ns if n['kind']=='Screen')['data']['task']['revision']+=1
   with self.assertRaises(CapabilityError):validate(ns)
 def test_historical_release_blockers_and_migrations_immutable(self):
  registry=json.loads((ROOT/'release-contract.json').read_text());old=json.loads(subprocess.check_output(['git','show','fc89eee:targets/spring-vue-postgres/release-contract.json']))
  for k,v in old['releases'].items():self.assertEqual(v,registry['releases'][k])
  for path in ['expected-open-blockers.json','expected-open-blockers-v2.json','expected-open-blockers-v3.json','expected-open-blockers-v4.json']:
   self.assertEqual(subprocess.check_output(['git','show','fc89eee:targets/spring-vue-postgres/'+path]),(ROOT/path).read_bytes())
