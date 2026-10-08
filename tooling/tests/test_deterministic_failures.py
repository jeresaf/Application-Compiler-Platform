"""F-01 closed contracts, exact occurrences and transaction rollback witnesses."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical_json import load, canonical_bytes
from deterministic_model import validate_deterministic
from deterministic_canonical import data,migration_review
from deterministic_failure_reference import FailureReferenceExecution,SemanticFailure
from execution_reference import ExecutionFailure
from deterministic_failures import retry_allowed
from deterministic_invocation import reserve,recover

ROOT=Path(__file__).resolve().parents[2]
BOOL={'tag':'literal','type':{'kind':'Boolean'},'value':True}


class FailureBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources={d:load(ROOT/'test-corpus/deterministic-v04'/f'{d}-proposal-authoring.json') for d in ('payment','case-management')}
        cls.engines={d:FailureReferenceExecution(load(ROOT/'test-corpus/deterministic-v04'/f'{d}-canonical-candidate.json')) for d in cls.sources}
    def source(self):return copy.deepcopy(self.sources['payment'])
    def by(self,s):return {n['id']:n for n in s['nodes']}
    def ref(self,by,id):return {'id':id,'revision':by[id]['revision']}
    def codes(self,s):return {e['code'] for e in validate_deterministic(s)}
    def test_reference_bindings_and_migration_require_exact_new_choice(self):
        for domain,s in self.sources.items():
            self.assertEqual([],validate_deterministic(s))
            for op in (n for n in s['nodes'] if n['kind']=='Command'):
                self.assertEqual('WORKFLOW_NO_APPLICABLE_TRANSITION',op['data']['failureBindings'][0]['trigger']['kind'])
                self.assertEqual('DEPENDENCY_UNAVAILABLE',op['data']['failureBindings'][1]['trigger']['faultClass'])
            old=load(ROOT/'test-corpus/execution-v03'/f'{domain}-authoring.json')
            r=migration_review(old);self.assertEqual('REVIEW_REQUIRED',r['status']);self.assertIsNone(r['candidate'])
            by=self.by(old)
            for b in r['blockers']:
                if by[b['subject']['id']]['kind']=='Command':self.assertIn('failureBindings',b['missing'])
    def test_reference_membership_stale_wrong_kind_and_missing_targets(self):
        for variant in ('stale','absent','kind','undeclared'):
            s=self.source();by=self.by(s);op=by['CMD-RECORD']['data'];b=op['failureBindings'][0]
            if variant=='stale':b['failure']['revision']+=1
            if variant=='absent':b['trigger']['machine']['id']='MISSING'
            if variant=='kind':b['trigger']['machine']=self.ref(by,'FAIL-BUSINESS')
            if variant=='undeclared':op['failures']=[self.ref(by,'FAIL-TRANSIENT')]
            self.assertTrue(self.codes(s),variant)
    def test_duplicates_precedence_category_and_platform_strings_reject(self):
        for variant in ('duplicate','order','stage','infra_business','workflow_transient','retryable_business','platform'):
            s=self.source();by=self.by(s);op=by['CMD-RECORD']['data'];b=op['failureBindings']
            if variant=='duplicate':b.insert(1,copy.deepcopy(b[0]))
            if variant=='order':b.reverse()
            if variant=='stage':b[0]['stage']='POST_ASSIGNMENT'
            if variant=='infra_business':b[1]['failure']=self.ref(by,'FAIL-BUSINESS')
            if variant=='workflow_transient':b[0]['failure']=self.ref(by,'FAIL-TRANSIENT')
            if variant=='retryable_business':by['FAIL-BUSINESS']['data']['retryable']=True
            if variant=='platform':b[1]['trigger']['faultClass']='java.sql.SQLException'
            self.assertTrue(self.codes(s),variant)
        s=self.source();by=self.by(s);by['CMD-RECORD']['data']['failureBindings'][1]['trigger']['sqlState']='40001'
        self.assertIn('ACP-DETERMINISTIC-SHAPE',self.codes(s))
    def predicate(self,by,condition=BOOL,stage='PRE_STATE'):
        return {'failure':self.ref(by,'FAIL-BUSINESS'),'stage':stage,'trigger':{'kind':'PREDICATE','condition':copy.deepcopy(condition)}}
    def test_boolean_predicates_stage_context_and_exact_typed_references(self):
        for variant in ('valid','nonbool','post_pre','usecase','wrong_kind','stale_field','literal_wrong_nominal'):
            s=self.source();by=self.by(s);condition=copy.deepcopy(BOOL)
            if variant=='nonbool':condition={'tag':'literal','type':{'kind':'String'},'value':'true'}
            if variant=='post_pre':condition={'tag':'postField','field':self.ref(by,'FLD-AMOUNT')}
            if variant=='usecase':condition={'tag':'input','scope':'USE_CASE','field':self.ref(by,'INPUT-TASK-TEXT')}
            if variant=='wrong_kind':condition={'tag':'parameter','ref':self.ref(by,'CMD-RECORD')}
            if variant=='stale_field':condition={'tag':'postField','field':{'id':'FLD-AMOUNT','revision':999}}
            if variant=='literal_wrong_nominal':condition={'tag':'literal','type':{'kind':'Named','definition':self.ref(by,'FAIL-BUSINESS')},'value':'x'}
            by['CMD-RECORD']['data']['failureBindings'].insert(0,self.predicate(by,condition))
            self.assertEqual(variant!='valid',bool(self.codes(s)),variant)
    def test_applicable_invariant_and_wrong_workflow_resource_or_command(self):
        s=self.source();by=self.by(s);b={'failure':self.ref(by,'FAIL-BUSINESS'),'stage':'INVARIANT','trigger':{'kind':'INVARIANT_FAILURE','invariant':self.ref(by,'INV-POSITIVE')}}
        by['CMD-RECORD']['data']['failureBindings'].insert(1,b)
        self.assertEqual([],validate_deterministic(s))
        by['INV-POSITIVE']['data']['enforcement']=['READ']
        self.assertTrue(self.codes(s))
        s=copy.deepcopy(self.sources['case-management']);by=self.by(s)
        # A machine exists, but the command must actually have an exact transition on it.
        for n in s['nodes']:
            if n['kind']=='Transition' and n['data']['command']['id']=='CMD-REVIEW':n['data']['command']=self.ref(by,'CMD-APPROVE')
        self.assertTrue(self.codes(s))
    def test_order_is_canonical_and_duplicate_predicate_rejects(self):
        s=self.source();by=self.by(s);op=by['CMD-RECORD']['data'];p=self.predicate(by)
        op['failureBindings'].insert(0,p)
        first=canonical_bytes(data(op,by,'Command'))
        op['failureBindings'][0],op['failureBindings'][1]=op['failureBindings'][1],op['failureBindings'][0]
        self.assertEqual([],validate_deterministic(s));self.assertNotEqual(first,canonical_bytes(data(op,by,'Command')))
        duplicate=copy.deepcopy(p);duplicate['failure']=self.ref(by,'FAIL-TRANSIENT');op['failureBindings'].insert(0,duplicate);self.assertIn('ACP-DETERMINISTIC-FAILURE_DUPLICATE',self.codes(s))
    def context(self,domain='payment'):
        e=copy.deepcopy(self.engines[domain]);by=e.index;root='ENT-PAYMENT' if domain=='payment' else 'CASE';machine='WF-PAYMENT' if domain=='payment' else 'WF-CASE';initial='STATE-DRAFT' if domain=='payment' else 'STATE-OPEN'
        entity=by[root]['data'];scope=next(n['data'] for n in by.values() if n['kind']=='Scope' and n['data']['resource']['id']==root)
        row={entity['identity'][0]['id']:'resource',entity['tenantField']['id']:'tenant','FLD-TASK-SUMMARY':'old','@state:'+machine:initial}
        if domain=='payment':row['FLD-AMOUNT']='12.50'
        else:row['FLD-CASE-TITLE']={'FLD-TITLE':'title'}
        resources={(root,'resource'):row};actor={scope['actorTenant']['id']:'tenant'}
        return e,resources,actor
    def run_engine(self,e,resources,actor,**kwargs):
        return e.execute('UC-TASK',{'INPUT-TASK-TEXT':'new','INPUT-TASK-RESOURCE':'resource'},resources,actor=actor,authorize=lambda *a:True,**kwargs)
    def test_payment_valid_draft_and_exact_workflow_failure_no_commit_or_idem_success(self):
        e,resources,actor=self.context();result=self.run_engine(e,resources,actor)
        self.assertTrue(result['events']);self.assertEqual('STATE-DRAFT',next(iter(resources.values()))['@state:WF-PAYMENT'])
        next(iter(resources.values()))['@state:WF-PAYMENT']='STATE-POSTED';before=copy.deepcopy(resources)
        state,_=reserve({},'identity','digest',0,60)
        with self.assertRaises(SemanticFailure) as caught:self.run_engine(e,resources,actor,correlation='corr')
        f=caught.exception.occurrence
        self.assertEqual(self.ref(e.index,'FAIL-BUSINESS'),f['failure']);self.assertEqual('INVALID_STATE',f['code']);self.assertEqual('corr',f['correlationId'])
        self.assertEqual(before,resources);self.assertEqual('IN_FLIGHT',state['identity']['status']);self.assertNotIn('result',state['identity'])
        self.assertEqual({},recover(state,'identity',proof='ROLLBACK_NO_EFFECT'))
        self.assertNotIn('events',f);self.assertNotIn('output',f)
    def test_case_correct_states_and_stop_prevents_subsequent_steps(self):
        e,resources,actor=self.context('case-management');steps=[]
        result=self.run_engine(e,resources,actor,after_step=steps.append)
        self.assertEqual(['STEP-CMD-REVIEW','STEP-CMD-APPROVE','STEP-CMD-ARCHIVE'],steps);self.assertEqual(3,len(result['events']))
        # Start at each incorrect state and verify exact operation-local failure.
        for op,state,prior in (('CMD-REVIEW','STATE-ARCHIVED',0),('CMD-APPROVE','STATE-OPEN',1),('CMD-ARCHIVE','STATE-OPEN',2)):
            e,resources,actor=self.context('case-management');steps=[]
            if prior==0:next(iter(resources.values()))['@state:WF-CASE']=state
            else:
                # Trusted test fault changes staged state just before the intended step;
                # use a false canonical guard on that transition for this witness.
                for n in e.index.values():
                    if n['kind']=='Transition' and n['data']['command']['id']==op:n['data']['guard']={'tag':'literal','type':{'kind':'Boolean'},'value':False}
            original=copy.deepcopy(resources)
            with self.assertRaises(SemanticFailure) as caught:self.run_engine(e,resources,actor,after_step=steps.append)
            self.assertEqual(op,caught.exception.occurrence['operation']['id']);self.assertEqual('FAIL-BUSINESS',caught.exception.occurrence['failure']['id'])
            self.assertEqual(prior,len(steps));self.assertEqual(original,resources)
    def test_exact_portable_fault_retry_and_unknown_internal(self):
        e,resources,actor=self.context();policy=next(n['data'] for n in e.index.values() if n['kind']=='RetryPolicy')
        with self.assertRaises(SemanticFailure) as caught:self.run_engine(e,resources,actor,faults={'CMD-RECORD':'DEPENDENCY_UNAVAILABLE'})
        f=caught.exception.occurrence;self.assertEqual('FAIL-TRANSIENT',f['failure']['id']);self.assertTrue(retry_allowed(e.index,policy,f))
        self.assertFalse(retry_allowed(e.index,policy,{**f,'origin':'INTERNAL'}))
        for fault in ('java.sql.SQLException','SERIALIZATION_CONFLICT','TIMEOUT','UNKNOWN'):
            with self.assertRaises(ExecutionFailure) as unknown:self.run_engine(e,resources,actor,faults={'CMD-RECORD':fault})
            self.assertNotIsInstance(unknown.exception,SemanticFailure)
    def test_overlap_precedence_and_post_assignment_rollback(self):
        e,resources,actor=self.context();op=e.index['CMD-RECORD'];by=e.index
        p=self.predicate(by);op['data']['failureBindings'].insert(0,p)
        next(iter(resources.values()))['@state:WF-PAYMENT']='STATE-POSTED'
        with self.assertRaises(SemanticFailure) as caught:self.run_engine(e,resources,actor)
        self.assertEqual(0,caught.exception.occurrence['bindingIndex'])
        op['data']['failureBindings'][0],op['data']['failureBindings'][1]=op['data']['failureBindings'][1],op['data']['failureBindings'][0]
        with self.assertRaises(SemanticFailure) as caught:self.run_engine(e,resources,actor)
        self.assertEqual(0,caught.exception.occurrence['bindingIndex']);self.assertEqual('WORKFLOW_NO_APPLICABLE_TRANSITION',op['data']['failureBindings'][0]['trigger']['kind'])
        e,resources,actor=self.context();before=copy.deepcopy(resources);op=e.index['CMD-RECORD'];op['data']['failureBindings'].insert(1,self.predicate(e.index,stage='POST_ASSIGNMENT'))
        with self.assertRaises(SemanticFailure):self.run_engine(e,resources,actor)
        self.assertEqual(before,resources)
    def test_invariant_binding_and_security_is_not_auth_denial(self):
        e,resources,actor=self.context();op=e.index['CMD-RECORD'];by=e.index
        op['data']['failureBindings'].insert(1,{'failure':self.ref(by,'FAIL-BUSINESS'),'stage':'INVARIANT','trigger':{'kind':'INVARIANT_FAILURE','invariant':self.ref(by,'INV-POSITIVE')}})
        by['INV-POSITIVE']['data']['predicate']={'tag':'literal','type':{'kind':'Boolean'},'value':False}
        with self.assertRaises(SemanticFailure) as caught:self.run_engine(e,resources,actor)
        self.assertEqual('FAIL-BUSINESS',caught.exception.occurrence['failure']['id'])
        with self.assertRaises(ExecutionFailure) as caught:e.execute('UC-TASK',{'INPUT-TASK-TEXT':'new','INPUT-TASK-RESOURCE':'resource'},resources,actor=actor,authorize=lambda *a:False)
        self.assertNotIsInstance(caught.exception,SemanticFailure)

    def test_explicit_security_predicate_is_distinct_from_protocol_denial(self):
        s=self.source();by=self.by(s);f=copy.deepcopy(by['FAIL-BUSINESS']);f.update(id='FAIL-SECURITY',name='Explicit semantic security condition')
        f['data'].update(code='TASK_RESTRICTED',category='SECURITY',retryable=False);s['nodes'].append(f)
        op=by['CMD-RECORD'];r={'id':'FAIL-SECURITY','revision':f['revision']};op['data']['failures'].append(r)
        op['data']['failureBindings'].insert(0,{'failure':r,'stage':'PRE_STATE','trigger':{'kind':'PREDICATE','condition':copy.deepcopy(BOOL)}})
        self.assertEqual([],validate_deterministic(s))
        e,resources,actor=self.context();e.index[f['id']]=f;e.index['CMD-RECORD']['data']=op['data']
        with self.assertRaises(SemanticFailure) as caught:self.run_engine(e,resources,actor)
        self.assertEqual('SECURITY',caught.exception.occurrence['category']);self.assertEqual('FAIL-SECURITY',caught.exception.occurrence['failure']['id'])
    def test_retry_keeps_job_occurrence_idempotency_and_operation_identity(self):
        from deterministic_invocation import identity
        e,resources,actor=self.context();op=self.ref(e.index,'CMD-RECORD');policy=next(n for n in e.index.values() if n['kind']=='IdempotencyPolicy')
        key=identity(self.ref(e.index,policy['id']),'tenant',{'type':{'kind':'Identifier'},'value':'resource'},op,
            {'type':{'kind':'String'},'value':'key'},occurrence={'schedule':{'id':'SCHEDULE','revision':1},'instant':'2026-10-08T00:00:00Z'})
        ledger={}
        for attempt in (1,2):
            ledger,status=reserve(ledger,key,'exact-input-digest',attempt,60,owner=str(attempt));self.assertEqual('RESERVED',status['status'])
            with self.assertRaises(SemanticFailure) as caught:self.run_engine(e,resources,actor,faults={'CMD-RECORD':'DEPENDENCY_UNAVAILABLE'})
            self.assertEqual(op,caught.exception.occurrence['operation'])
            self.assertEqual([key],list(ledger));ledger=recover(ledger,key,proof='ROLLBACK_NO_EFFECT')
    def test_each_case_command_correct_and_incorrect_state_directly(self):
        for command,correct in (('CMD-REVIEW','STATE-OPEN'),('CMD-APPROVE','STATE-REVIEWED'),('CMD-ARCHIVE','STATE-APPROVED')):
            for valid in (True,False):
                e,resources,actor=self.context('case-management');by=e.index
                step=by['STEP-'+command];sr=self.ref(by,step['id'])
                # A bounded isolated task witness uses the same accepted input/output
                # constructions, without fabricating prior successful step results.
                by['UC-TASK']['data']['steps']=[sr]
                step['data']['inputBindings']=copy.deepcopy(by['STEP-CMD-REVIEW']['data']['inputBindings'])
                for binding in by['UC-TASK']['data']['outputBindings']:
                    binding['value']['step']=copy.deepcopy(sr)
                next(iter(resources.values()))['@state:WF-CASE']=correct if valid else ('STATE-ARCHIVED' if command=='CMD-REVIEW' else 'STATE-OPEN')
                before=copy.deepcopy(resources);visited=[]
                if valid:
                    result=self.run_engine(e,resources,actor,after_step=visited.append)
                    self.assertEqual(1,len(result['events']));self.assertEqual([step['id']],visited)
                else:
                    with self.assertRaises(SemanticFailure) as caught:self.run_engine(e,resources,actor,after_step=visited.append)
                    self.assertEqual('FAIL-BUSINESS',caught.exception.occurrence['failure']['id'])
                    self.assertEqual(command,caught.exception.occurrence['operation']['id']);self.assertEqual([],visited)
                self.assertEqual(before,resources)
