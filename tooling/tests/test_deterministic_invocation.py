"""Reference state-transition witnesses; no production durability claims."""
import copy
import json
from pathlib import Path
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical_json import load, canonical_bytes
from deterministic_invocation import *
from deterministic_reference import TokenBucket
from deterministic_contract import RATE
from deterministic_canonical import data, migration_review
from deterministic_model import validate_deterministic

ROOT=Path(__file__).resolve().parents[2]


class InvocationProposalTests(unittest.TestCase):
    def setUp(self):
        self.state={}; self.key=identity({'id':'IDEM','revision':1},'tenant',{'id':'r'}, {'id':'CMD','revision':1}, {'type':{'kind':'String'},'value':'key'})
        self.input='sha256:'+'a'*64
    def claim(self):
        self.state,o=reserve(self.state,self.key,self.input,0,10)
        self.assertEqual('RESERVED',o['status'])
    def commit(self,steps=None,guarantee='AT_LEAST_ONCE',ordering='PER_AGGREGATE'):
        steps=steps or [[{'event':{'id':'Z','revision':1},'payload':{}},{'event':{'id':'A','revision':1},'payload':{}}],[{'event':{'id':'Z','revision':1},'payload':{}}]]
        return commit_transaction(self.state,self.key,instant=SECOND,result={'ok':True},domain={'balance':1},steps=steps,aggregate={'tenant':'t','id':'r'},commit_sequence=4,policies={x:{'windowSeconds':10,'guarantee':guarantee,'ordering':ordering} for x in ('Z','A')})
    def test_concurrent_same_key_same_input_and_different_input(self):
        for different in (False,True):
            state={};lock=threading.Lock();out=[]
            def call(i):
                nonlocal state
                with lock: # explicit serialized storage premise, not a target lock implementation
                    state,r=reserve(state,self.key,self.input if not different else str(i),0,10)
                    out.append(r['status'])
            with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(call,range(20)))
            self.assertEqual(1,out.count('RESERVED'))
            self.assertEqual(19,out.count('CONFLICT' if different else 'IN_PROGRESS'))
    def test_replay_half_open_expiry_and_precommit_rollback(self):
        self.claim();c=self.commit();self.state=c['idempotency']
        for now in (SECOND,11*SECOND-1):
            _,o=reserve(self.state,self.key,self.input,now,10);self.assertEqual({'status':'REPLAY','result':{'ok':True}},o)
        _,o=reserve(self.state,self.key,'other',11*SECOND-1,10);self.assertEqual('CONFLICT',o['status'])
        self.state,o=reserve(self.state,self.key,'other',11*SECOND,10);self.assertEqual('RESERVED',o['status'])
        self.state=recover(self.state,self.key,proof='ROLLBACK_NO_EFFECT')
        _,o=reserve(self.state,self.key,self.input,11*SECOND,10);self.assertEqual('RESERVED',o['status'])
    def test_indeterminate_restart_requires_proven_commit_or_rollback(self):
        self.claim();self.state=uncertain(self.state,self.key)
        self.state=json.loads(json.dumps(self.state)) # restart from durable-model witness
        _,o=reserve(self.state,self.key,self.input,10**30,10);self.assertEqual('IN_PROGRESS',o['status'])
        _,o=reserve(self.state,self.key,'other',10**30,10);self.assertEqual('CONFLICT',o['status'])
        with self.assertRaises(ValueError):recover(self.state,self.key,proof='WORKER_DIED')
        done=recover(self.state,self.key,proof='COMMITTED',result=7,commit=SECOND)
        self.assertEqual('REPLAY',reserve(done,self.key,self.input,SECOND,10)[1]['status'])
        self.assertEqual({},recover(self.state,self.key,proof='ROLLBACK_NO_EFFECT'))
    def test_partition_and_scheduled_occurrence_identity(self):
        keys={identity({'id':'p','revision':rev},t,r,{'id':op,'revision':1},{'type':{'kind':'String'},'value':'k'},occurrence=occ)
              for rev in (1,2) for t in ('t1','t2') for r in ('r1','r2') for op in ('a','b') for occ in (1,2)}
        self.assertEqual(32,len(keys))
    def test_exact_canonical_typed_input_digest(self):
        typ={'kind':'Decimal','precision':8,'scale':2,'rounding':'REJECT'}
        self.assertEqual(typed_input_digest(typ,'1.00',{}),typed_input_digest(typ,'1',{}))
        self.assertNotEqual(typed_input_digest(typ,'1',{}),typed_input_digest(typ,'2',{}))
    def test_rollback_and_ordered_atomic_multi_step_emissions(self):
        self.claim();before=copy.deepcopy(self.state);c=self.commit()
        self.assertEqual(before,self.state) # failed staging has no deliverable occurrence
        self.assertEqual(['Z','A','Z'],[e['event']['event']['id'] for e in c['events']])
        self.assertEqual([[4,0,0],[4,0,1],[4,1,0]],[e['sequence'] for e in c['events']])
        with self.assertRaises(ValueError):self.commit([[{'event':{'id':'Z'}},{'event':{'id':'Z'}}]])
        bindings=[{'event':{'id':'Z','revision':1}},{'event':{'id':'A','revision':1}}]
        self.assertEqual(bindings,data(bindings,{},'Command',('eventBindings',)))
        self.assertNotEqual(canonical_bytes(data(bindings,{},'Command',('eventBindings',))),canonical_bytes(data(bindings[::-1],{},'Command',('eventBindings',))))
    def test_aggregate_order_retry_ack_and_deadline(self):
        self.claim();events=self.commit()['events']
        with self.assertRaises(ValueError):send(events,1,SECOND,outcome='ACKNOWLEDGED')
        events=send(events,0,SECOND,outcome='UNCERTAIN')
        self.assertEqual('PENDING',delivery_status(events[0],SECOND))
        events=send(events,0,2*SECOND,outcome='ACKNOWLEDGED')
        events=send(events,1,2*SECOND,outcome='FAILED')
        self.assertEqual(2,events[0]['attempts'])
        self.assertEqual('UNSATISFIED',delivery_status(events[1],11*SECOND))
        with self.assertRaises(ValueError):send(events,1,11*SECOND,outcome='ACKNOWLEDGED')
        # An expired earlier occurrence no longer blocks a later live commit.
        events[2]['deadline']=12*SECOND
        self.assertEqual('ACKNOWLEDGED',send(events,2,11*SECOND,outcome='ACKNOWLEDGED')[2]['status'])
    def test_at_most_once_uncertain_and_none_order(self):
        self.claim();events=self.commit(guarantee='AT_MOST_ONCE',ordering='NONE')['events']
        events=send(events,2,SECOND,outcome='UNCERTAIN')
        self.assertEqual('ATTEMPTED',delivery_status(events[2],100*SECOND))
        with self.assertRaises(ValueError):send(events,2,SECOND,outcome='ACKNOWLEDGED')
        with self.assertRaises(ValueError):send(events,0,SECOND-1,outcome='FAILED')
    def test_job_modes_bounds_overflow_and_exact_activation(self):
        occurrences=[1,4,2,3,5]
        self.assertEqual([],missed_occurrences({'missedOccurrences':'SKIP'},occurrences,5))
        self.assertEqual([4],missed_occurrences({'missedOccurrences':'RUN_LATEST'},occurrences,5))
        job={'missedOccurrences':'CATCH_UP','catchUp':{'maxOccurrences':2,'overflow':'DROP_OLDEST'}}
        self.assertEqual([3,4],missed_occurrences(job,occurrences,5))
        job['catchUp']['overflow']='REJECT'
        with self.assertRaises(ValueError):missed_occurrences(job,occurrences,5)
        self.assertEqual([1,2],missed_occurrences(job,[2,1,5],5))
    def test_current_action_hold_release_rollback_relatch_and_wrong_scope(self):
        hold={'release':{'id':'P','revision':2}}
        context={'tenant':'t','resource':'r','action':'ANONYMIZE','transaction':'tx'}
        exact={**context,'permission':hold['release']}
        def action(request,permission,committed=True):return lifecycle_action(hold,active=True,request=request,permission=permission,committed=committed,**context)
        for request,permission in ((None,None),(None,exact),(exact,None)):
            with self.assertRaises(ValueError):action(request,permission)
        self.assertEqual(False,action(exact,exact)['holdCleared'])
        self.assertEqual(1,len(action(exact,exact)['audit']))
        self.assertEqual({'disposed':False,'audit':[],'holdCleared':False},action(exact,exact,False))
        for field in ('tenant','resource','transaction','permission'):
            wrong={**exact,field:'wrong'}
            with self.assertRaises(ValueError):action(wrong,exact)
        context['transaction']='later'
        with self.assertRaises(ValueError):action(exact,exact)
    def test_observability_never_masks_business_values_or_leaks_raw_or_length(self):
        for surface in ('LOG','TRACE','DIAGNOSTIC_ERROR','AUDIT_VALUE'):
            for mode in ('MASK','OMIT'):
                outputs=[observation({'redaction':mode},v,surface=surface,metadata={'fieldId':'FLD'}) for v in ('secret','muchlongersecret')]
                self.assertEqual(outputs[0],outputs[1]);self.assertNotIn('secret',json.dumps(outputs))
        with self.assertRaises(ValueError):observation({'redaction':'MASK'},'secret',surface='API')
        with self.assertRaises(ValueError):observation({'redaction':'MASK'},'secret',surface='LOG',metadata={'raw':'secret'})
        self.assertEqual('secret',observation({'redaction':'NONE'},'secret',surface='LOG')['value'])
    def test_auth_rate_replay_order_no_duplicate_events_transport_independent(self):
        bucket=TokenBucket({'requests':1,'windowSeconds':60,'burst':2,'algorithm':RATE})
        calls=[];events=[]
        def execute(state):
            calls.append(1)
            self.state=state;c=self.commit();events.extend(c['events'])
            return c['idempotency'],{'status':'COMMITTED'}
        def invoke(auth=True,authorized=True):
            self.state,o=invocation(authenticated=auth,authorized=authorized,bucket=bucket,now=SECOND,state=self.state,key=self.key,input_digest=self.input,window_seconds=10,execute=execute)
            return o
        self.assertEqual('UNAUTHORIZED',invoke(False)['status']);self.assertIsNone(bucket.last);self.assertEqual({},self.state)
        self.assertEqual('UNAUTHORIZED',invoke(authorized=False)['status']);self.assertIsNone(bucket.last)
        self.assertEqual('COMMITTED',invoke()['status'])
        self.assertEqual('REPLAY',invoke()['status'])
        self.assertEqual('RATE_DENIED',invoke()['status']);self.assertEqual(1,len(calls));self.assertEqual(3,len(events))
        events=send(events,0,SECOND,outcome='FAILED');events=send(events,0,2*SECOND,outcome='ACKNOWLEDGED')
        self.assertEqual(2,events[0]['attempts']);self.assertEqual(1,len(calls))
    def test_migration_markers_closed_choices_and_fixture_meanings(self):
        for domain in ('payment','case-management'):
            old=load(ROOT/'test-corpus/execution-v03'/f'{domain}-authoring.json')
            missing={x for b in migration_review(old)['blockers'] for x in b['missing']}
            self.assertTrue({'windowAnchor','inFlight','occurrenceOrder','emissionOrder','invocationOrder','missedOccurrences','releaseMode','redactionScope'}<=missing)
            s=load(ROOT/'test-corpus/deterministic-v04'/f'{domain}-proposal-authoring.json')
            self.assertEqual([],validate_deterministic(s))
            job=next(n for n in s['nodes'] if n['kind']=='Job');self.assertEqual('SKIP',job['data']['missedOccurrences'])
            job['data']['missedOccurrences']='CATCH_UP'
            self.assertTrue(validate_deterministic(s))


class CombinedProposalTests(unittest.TestCase):
    def test_hold_authorized_anonymization_and_value_free_redacted_audit(self):
        from deterministic_reference import anonymize
        source=load(ROOT/'test-corpus/deterministic-v04/case-management-proposal-authoring.json')
        by={n['id']:n for n in source['nodes']}
        policy=next(n['data'] for n in by.values() if n['kind']=='DeletionPolicy')
        hold=next(n['data'] for n in by.values() if n['kind']=='LegalHold')
        row={'CASE-ID':'c','CASE-TENANT':'tenant','CASE-ASSIGNEE':'operator','FLD-TASK-SUMMARY':'summary',
             'FLD-CASE-TITLE':{'FLD-TITLE':'title'},'FLD-NOTE':'SENSITIVE-prior-secret'}
        context={'tenant':'tenant','resource':'c','action':'ANONYMIZE','transaction':'tx'}
        exact={**context,'permission':hold['release']}
        with self.assertRaises(ValueError):
            lifecycle_action(hold,active=True,request=None,permission=exact,committed=True,**context)
        release=lifecycle_action(hold,active=True,request=exact,permission=exact,committed=True,**context)
        staged=anonymize(by,policy,row,authorized=True,hold_active=not release['disposed'])
        self.assertNotIn('FLD-NOTE',staged)
        self.assertEqual('SENSITIVE-prior-secret',row['FLD-NOTE'])
        audit={'authorization':release['audit'],'value':observation({'redaction':'MASK'},row['FLD-NOTE'],surface='AUDIT_VALUE')}
        self.assertNotIn('SENSITIVE-prior-secret',json.dumps(audit))
        rolled=lifecycle_action(hold,active=True,request=exact,permission=exact,committed=False,**context)
        self.assertEqual([],rolled['audit']);self.assertFalse(rolled['disposed'])
    def test_reservation_fencing_and_dedup_window_validation(self):
        state,_=reserve({},'key','input',0,10,owner='first')
        with self.assertRaises(ValueError):
            commit_transaction(state,'key',instant=0,result=1,domain={},steps=[],aggregate='a',commit_sequence=1,policies={},owner='duplicate')
        for domain in ('payment','case-management'):
            s=load(ROOT/'test-corpus/deterministic-v04'/f'{domain}-proposal-authoring.json')
            by={n['id']:n for n in s['nodes']}
            d=next(n['data'] for n in s['nodes'] if n['kind']=='DeliveryPolicy')
            idem=by[d['deduplication']['id']]['data']
            d['windowSeconds']=idem['windowSeconds']+1
            self.assertTrue(validate_deterministic(s))
    def test_resource_partitions_and_inter_commit_aggregate_order(self):
        state={}
        for key in ('tenant1/resource1','tenant2/resource1','tenant1/resource2'):
            state,o=reserve(state,key,'input',0,10);self.assertEqual('RESERVED',o['status'])
        p={'E':{'windowSeconds':10,'guarantee':'AT_LEAST_ONCE','ordering':'PER_AGGREGATE'}}
        def commit(key,seq,aggregate):return commit_transaction(state,key,instant=0,result=1,domain={},steps=[[{'event':{'id':'E','revision':1}}]],aggregate=aggregate,commit_sequence=seq,policies=p)['events']
        events=commit('tenant1/resource1',1,'t1/r1')+commit('tenant1/resource1',2,'t1/r1')+commit('tenant2/resource1',3,'t2/r1')
        with self.assertRaises(ValueError):send(events,1,0,outcome='FAILED')
        events=send(events,2,0,outcome='ACKNOWLEDGED')
        self.assertEqual('ACKNOWLEDGED',events[2]['status'])
    def test_all_new_choice_markers_are_required_without_defaults(self):
        s=load(ROOT/'test-corpus/deterministic-v04/payment-proposal-authoring.json')
        for kind,field in (('IdempotencyPolicy','inFlight'),('DeliveryPolicy','windowAnchor'),('Command','emissionOrder'),
                           ('Job','missedOccurrences'),('LegalHold','releaseMode'),('DataClassification','redactionScope'),('UseCase','invocationOrder')):
            missing=copy.deepcopy(s)
            next(n for n in missing['nodes'] if n['kind']==kind)['data'].pop(field)
            self.assertEqual('ACP-DETERMINISTIC-SHAPE',validate_deterministic(missing)[0]['code'])
