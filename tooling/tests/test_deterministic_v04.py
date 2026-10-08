"""Proposed semantics, exact migration/revisions and no implicit approval."""
import copy
from pathlib import Path
import subprocess
import sys
import unittest
from datetime import datetime,timezone
from decimal import Decimal
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from canonical_json import load,digest
from canonical_ir import admit,normalize_candidate,validate_snapshot,CanonicalError
from deterministic_contract import authoring_schema,canonical_schema,change_schema,RATE
from deterministic_model import validate_deterministic
from deterministic_canonical import migration_review
from deterministic_fixtures import DEST,proposal
from deterministic_reference import order_rows,anonymize,closure_anchor,TokenBucket,retry_delays,interval_occurrence
from changes import prepare,ChangeError,request
from execution_approval import authority,WHEN
from execution_semantics import local_occurrence
from jsonschema import Draft202012Validator


class DeterministicProposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources={d:load(DEST/(d+'-proposal-authoring.json')) for d in ('payment','case-management')}
        cls.snapshots={d:load(DEST/(d+'-canonical-candidate.json')) for d in cls.sources}
    def source(self,d='payment'):return copy.deepcopy(self.sources[d])
    def by(self,s):return {n['id']:n for n in s['nodes']}
    def errors(self,s):return [e['code'] for e in validate_deterministic(s)]
    def test_closed_schemas_draft_proposals_and_structural_candidates(self):
        for build,name in [(authoring_schema,'authoring-0.4'),(canonical_schema,'canonical-0.3'),(change_schema,'change-0.3')]:
            schema=build();Draft202012Validator.check_schema(schema)
            self.assertEqual(schema,load(DEST.parents[1]/'contracts'/(name+'.schema.json')))
        for d,s in self.sources.items():
            self.assertEqual([],s['approvals']);self.assertTrue(all(n['lifecycle']=='PROPOSED' for n in s['nodes']))
            self.assertEqual([],validate_deterministic(s));validate_snapshot(self.snapshots[d])
            with self.assertRaises(CanonicalError):normalize_candidate(s)
            with self.assertRaises(CanonicalError):admit(self.snapshots[d],None)
            old=load(DEST.parent/'execution-v03'/(d+'-canonical.json'))
            with self.assertRaises(CanonicalError):admit(self.snapshots[d],lambda q:q['contentDigest']==old['contentDigest'])
        s=self.source();self.by(s)['QUERY-TASKS']['data']['undeclared']=True
        self.assertIn('ACP-DETERMINISTIC-SHAPE',self.errors(s))
    def test_query_total_order_exact_reference_duplicates_and_presence(self):
        for variant in ('missing','duplicate','stale','foreign'):
            s=self.source();by=self.by(s);q=by['QUERY-TASKS']['data'];key=copy.deepcopy(q['orderBy'][0])
            if variant=='missing':q['orderBy']=[]
            if variant=='duplicate':q['orderBy'].append({**key,'direction':'DESC'})
            if variant=='stale':q['orderBy'][0]['field']['revision']+=1
            if variant=='foreign':q['orderBy'][0]['field']={'id':'FLD-MEMBER-ID','revision':by['FLD-MEMBER-ID']['revision']}
            self.assertTrue(self.errors(s),variant)
        s=self.source('case-management');by=self.by(s);q=by['QUERY-TASKS']['data'];note=by['FLD-NOTE']
        q['orderBy'].insert(0,{'field':{'id':note['id'],'revision':note['revision']},'direction':'DESC','nulls':'FIRST','absent':'LAST'})
        self.assertEqual([],self.errors(s))
        q['orderBy'][0].pop('absent');self.assertIn('ACP-DETERMINISTIC-ORDER_PRESENCE',self.errors(s))
    def test_order_precedence_is_semantic_numeric_unicode_and_presence(self):
        by=self.by(self.sources['payment']);q=copy.deepcopy(by['QUERY-TASKS']['data'])
        q['orderBy'].insert(0,{'field':{'id':'FLD-AMOUNT','revision':by['FLD-AMOUNT']['revision']},'direction':'DESC'})
        rows=[{'FLD-PAYMENT-ID':'🦋','FLD-AMOUNT':'9.00'},{'FLD-PAYMENT-ID':'a','FLD-AMOUNT':'100.00'},{'FLD-PAYMENT-ID':'A','FLD-AMOUNT':'9.00'}]
        self.assertEqual(['a','A','🦋'],[r['FLD-PAYMENT-ID'] for r in order_rows(by,q,rows)])
        self.assertEqual('🦋',rows[0]['FLD-PAYMENT-ID'])
        by=self.by(self.sources['case-management']);q=copy.deepcopy(by['QUERY-TASKS']['data'])
        q['orderBy'].insert(0,{'field':{'id':'FLD-NOTE','revision':by['FLD-NOTE']['revision']},'direction':'DESC','nulls':'FIRST','absent':'LAST'})
        rows=[{'CASE-ID':'absent'},{'CASE-ID':'null','FLD-NOTE':None},{'CASE-ID':'value','FLD-NOTE':'x'}]
        self.assertEqual(['null','value','absent'],[r['CASE-ID'] for r in order_rows(by,q,rows)])
    def test_closure_references_terminal_state_and_commit_fact(self):
        s=self.source();by=self.by(s);life=next(n for n in s['nodes'] if n['kind']=='DataLifecycle');anchor=life['data']['anchor']
        anchor['states']=[{'id':'STATE-DRAFT','revision':by['STATE-DRAFT']['revision']}]
        self.assertIn('ACP-DETERMINISTIC-CLOSURE_STATE',self.errors(s))
        anchor=next(n for n in self.sources['payment']['nodes'] if n['kind']=='DataLifecycle')['data']['anchor']
        at='2026-10-08T12:00:00Z'
        self.assertEqual(at,closure_anchor(anchor,'STATE-DRAFT','STATE-POSTED',at,committed=True))
        self.assertIsNone(closure_anchor(anchor,'STATE-DRAFT','STATE-POSTED',at,committed=False))
        self.assertIsNone(closure_anchor(anchor,'STATE-POSTED','STATE-POSTED',at,committed=True))
    def test_anonymization_types_coverage_identity_and_retained_invariants(self):
        for variant in ('missing','duplicate','remove','null','currency','scale','zero','identity'):
            s=self.source();by=self.by(s);d=next(n['data'] for n in s['nodes'] if n['kind']=='DeletionPolicy');e=d['anonymizationEffects'][0]
            if variant=='missing':d['anonymizationEffects']=[]
            if variant=='duplicate':d['anonymizationEffects'].append(copy.deepcopy(e))
            if variant in {'remove','null'}:e.pop('replacement');e['action']=variant.upper()
            if variant=='currency':e['replacement']['type']['currency']='USD'
            if variant=='scale':e['replacement']['value']='1.001'
            if variant=='zero':e['replacement']['value']='0.00'
            if variant=='identity':e['field']=copy.deepcopy(by['ENT-PAYMENT']['data']['identity'][0]);d['fields']=[e['field']]
            self.assertTrue(self.errors(s),variant)
    def test_anonymization_is_staged_typed_and_unreleased_hold_blocks(self):
        by=self.by(self.sources['payment']);policy=next(n['data'] for n in by.values() if n['kind']=='DeletionPolicy')
        row={'FLD-PAYMENT-ID':'p','FLD-PAYMENT-TENANT':'tenant','FLD-AMOUNT':'12.50','FLD-TASK-SUMMARY':'unchanged'}
        after=anonymize(by,policy,row,authorized=True,hold_active=False)
        self.assertEqual(Decimal('1.00'),Decimal(after['FLD-AMOUNT']));self.assertEqual('12.50',row['FLD-AMOUNT'])
        for held in (True,None):
            with self.assertRaises(ValueError):anonymize(by,policy,row,authorized=True,hold_active=held)
        with self.assertRaises(ValueError):anonymize(by,policy,row,authorized=False,hold_active=False)
        by=self.by(self.sources['case-management']);policy=next(n['data'] for n in by.values() if n['kind']=='DeletionPolicy')
        row={'CASE-ID':'c','CASE-TENANT':'tenant','CASE-ASSIGNEE':'operator','FLD-TASK-SUMMARY':'old','FLD-CASE-TITLE':{'FLD-TITLE':'title'},'FLD-NOTE':'private'}
        self.assertNotIn('FLD-NOTE',anonymize(by,policy,row,authorized=True,hold_active=False))
        other=copy.deepcopy(policy);other['anonymizationEffects'][0]['action']='NULL'
        self.assertIsNone(anonymize(by,other,row,authorized=True,hold_active=False)['FLD-NOTE'])
        self.assertEqual('private',row['FLD-NOTE'])
    def test_rate_exact_boundaries_capacity_clock_and_authorization(self):
        p=next(n['data'] for n in self.sources['payment']['nodes'] if n['kind']=='RatePolicy');b=TokenBucket(p)
        self.assertFalse(b.admit(0,authorized=False));self.assertIsNone(b.last)
        self.assertTrue(all(b.admit(0,authorized=True) for _ in range(10)))
        self.assertFalse(b.admit(0,authorized=True));self.assertFalse(b.admit(599999999,authorized=True))
        self.assertTrue(b.admit(600000000,authorized=True))
        with self.assertRaises(ValueError):b.admit(1,authorized=True)
        self.assertTrue(all(b.admit(60_000_000_000,authorized=True) for _ in range(10)))
        self.assertFalse(b.admit(60_000_000_000,authorized=True))
        s=self.source();next(n for n in s['nodes'] if n['kind']=='RatePolicy')['data']['algorithm']['kind']='FIXED_WINDOW'
        self.assertIn('ACP-DETERMINISTIC-SHAPE',self.errors(s))
    def test_retry_exact_sequence_and_interval_anchor_and_daily_dst(self):
        p={'initialSeconds':2,'multiplier':3,'maxDelaySeconds':10,'maxAttempts':5}
        self.assertEqual([2,6,10,10],retry_delays(p));p['maxAttempts']=1;self.assertEqual([],retry_delays(p))
        s={'mode':'INTERVAL','intervalSeconds':60,'anchorInstant':'2026-10-08T12:00:00Z'}
        self.assertEqual(datetime(2026,10,8,12,0,tzinfo=timezone.utc),interval_occurrence(s,0))
        self.assertEqual(datetime(2026,10,8,12,2,tzinfo=timezone.utc),interval_occurrence(s,2))
        schedule={'tzdbVersion':'2026d','timezone':'America/New_York','gap':'SKIP','overlap':'EARLIER'}
        self.assertIsNone(local_occurrence('2026-03-08T02:30:00',schedule))
        early=local_occurrence('2026-11-01T01:30:00',schedule);schedule['overlap']='LATER'
        self.assertEqual(3600,(local_occurrence('2026-11-01T01:30:00',schedule)-early).total_seconds())
    def test_mechanical_migration_never_guesses_and_new_plan_is_unapproved(self):
        for domain in self.sources:
            old=load(DEST.parent/'execution-v03'/(domain+'-authoring.json'));review=migration_review(old)
            self.assertEqual('REVIEW_REQUIRED',review['status']);self.assertIsNone(review['candidate'])
            missing={k for b in review['blockers'] for k in b['missing']}
            self.assertTrue({'orderBy','anchor','anonymizationEffects','algorithm'}<=missing)
            base,c,plan,draft=proposal(domain)
            self.assertEqual(load(DEST/(domain+'-plan.json')),plan)
            self.assertEqual(self.sources[domain],draft);self.assertEqual('0.3.0',plan['planVersion'])
            self.assertNotEqual(base['contentDigest'],plan['candidate']['contentDigest'])
            oldproof=next(x['proof'] for x in load(DEST.parent/'execution-v03/human-approval.json')['examples'] if x['domain']==domain)
            with self.assertRaises(ChangeError):authority().verify_historical(oldproof,request(plan),WHEN)
            bad=copy.deepcopy(c);bad.update(changeVersion='0.2.0',canonicalVersion='0.2.0')
            with self.assertRaises(ChangeError):prepare(plan['candidate'],bad)
    def test_approved_assets_are_byte_identical_to_checkpoint(self):
        paths=['contracts/authoring-0.3.schema.json','contracts/canonical-0.2.schema.json','contracts/change-0.2.schema.json','docs/adr/0015-explicit-operation-effects-and-dataflow.md']
        paths += [p.relative_to(DEST.parents[1]).as_posix() for p in (DEST.parent/'execution-v03').glob('*.json')]
        for path in paths:
            old=subprocess.check_output(['git','show','101205d:'+path],cwd=DEST.parents[1])
            self.assertEqual(old,(DEST.parents[1]/path).read_bytes(),path)
