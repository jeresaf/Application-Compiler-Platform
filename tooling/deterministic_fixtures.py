"""AI-authored successor proposals. No authority proof or approval is issued.

Stored authoring is PROPOSED with no attestations. The separate ChangeSet plan and
Canonical candidate use the established active-candidate structural convention;
planning is not admission. Only a later explicit human act can admit that digest.
"""
import copy
import json
from canonical_json import load, digest, PROFILE
from canonical_fixtures import byte_vectors
from changes import prepare, index
from change_fixtures import change, revise
from deterministic_contract import RATE, INVOCATION
from validate import ROOT

DEST=ROOT/'test-corpus/deterministic-v04'


def proposal(domain):
    base=load(ROOT/'test-corpus/execution-v03'/(domain+'-canonical.json'))
    by=index(base); r=lambda id:{'id':id,'revision':by[id]['revision']}
    payment=domain=='payment'; root='ENT-PAYMENT' if payment else 'CASE'
    identity='FLD-PAYMENT-ID' if payment else 'CASE-ID'
    machine='WF-PAYMENT' if payment else 'WF-CASE'
    closed='STATE-POSTED' if payment else 'STATE-ARCHIVED'
    requirement=next(n for n in by.values() if n['kind']=='Requirement')
    decision={'id':'DEC-DETERMINISTIC-V04','revision':1,'kind':'Decision','name':'Proposed deterministic execution reference semantics',
        'lifecycle':'APPROVED','steward':'fixture:authors','origins':[{'source':'fixture:deterministic-v04-proposal','locator':domain,
        'actor':'assistant:proposal-author','actorType':'AI'}], 'basis':[r(requirement['id'])],
        'data':{'statement':'PROPOSED ONLY: identity ASC query ordering, explicit terminal closure commit anchor, exact anonymization constants, deterministic admission, commit-anchored idempotency/delivery, ordered emissions, SKIP jobs, action-local hold release and observability redaction.',
        'strength':'REQUIRED','rationale':'HUMAN REVIEW REQUIRED. Planning and structural candidate markers are not approval or production business requirements.',
        'alternatives':['Retain approved 0.3/0.2 meaning and reject incomplete target capabilities']}}
    ops=[{'op':'ADD','node':decision}]
    for n in by.values():
        d=copy.deepcopy(n['data']); changed=True
        if n['kind']=='Query': d.update(orderBy=[{'field':r(identity),'direction':'ASC'}],invocationOrder=INVOCATION)
        elif n['kind']=='Command': d.update(emissionOrder='DECLARED_BINDING_SEQUENCE',invocationOrder=INVOCATION)
        elif n['kind']=='UseCase': d['invocationOrder']=INVOCATION
        elif n['kind']=='IdempotencyPolicy': d.update(windowAnchor='COMMITTED_RESULT',inFlight='RETURN_IN_PROGRESS')
        elif n['kind']=='DeliveryPolicy': d.update(windowAnchor='EVENT_COMMIT',occurrenceOrder='COMMIT_STEP_EMISSION_SEQUENCE')
        elif n['kind']=='Job': d.update(missedOccurrences='SKIP',catchUp=None)
        elif n['kind']=='LegalHold': d['releaseMode']='CURRENT_LIFECYCLE_ACTION'
        elif n['kind']=='DataClassification': d['redactionScope']='NON_DOMAIN_OBSERVABILITY'
        elif n['kind']=='DataLifecycle': d['anchor']={'kind':'CLOSED_COMMIT','machine':r(machine),'states':[r(closed)],'instant':'COMMITTED_ENTRY','terminal':True}
        elif n['kind']=='DeletionPolicy':
            d['anonymizationEffects']=([{'field':r('FLD-AMOUNT'),'action':'REPLACE','replacement':{'type':copy.deepcopy(by['FLD-AMOUNT']['data']['type']),'value':'1.00'}}] if payment else
                [{'field':r('FLD-NOTE'),'action':'REMOVE'}]) if d['mode']=='ANONYMIZE' else []
        elif n['kind']=='RatePolicy': d['algorithm']=copy.deepcopy(RATE)
        elif n['kind']=='RetryPolicy': d.update(delayBasis='AFTER_FAILURE_COMPLETION',jitter='NONE',attemptCounting='INCLUDING_INITIAL')
        else: changed=False
        if changed:
            origins=[*n['origins'],{'source':'fixture:deterministic-v04-proposal','locator':n['id'],'actor':'assistant:proposal-author','actorType':'AI'}]
            ops.append(revise(base,n['id'],data=d,basis=[*n['basis'],{'id':decision['id'],'revision':1}],origins=origins))
    head={'sequence':0,'digest':base['contentDigest'],'journalDigest':'sha256:'+'0'*64}
    c=change('CHANGE-DETERMINISTIC-V04',head,ops,author='assistant:proposal-author')
    c.update(changeVersion='0.3.0',canonicalVersion='0.3.0',intent='PROPOSED reference-only deterministic semantics; HUMAN REVIEW REQUIRED')
    plan=prepare(base,c)
    draft={'modelVersion':'0.4.0','applicationId':base['content']['applicationId'],'snapshotId':'DRAFT-DETERMINISTIC-V04',
        'nodes':copy.deepcopy(plan['candidate']['content']['nodes']),'issues':[],'approvals':[]}
    for n in draft['nodes']: n['lifecycle']='PROPOSED'
    return base,c,plan,draft


def build():
    DEST.mkdir(exist_ok=True)
    manifest={'profile':PROFILE,'status':'PROPOSED_HUMAN_REVIEW_REQUIRED','authority':'NONE; no human/reference approval proof generated',
        'authoringVersion':'0.4.0','canonicalVersion':'0.3.0','changeVersion':'0.3.0','examples':[]}
    for domain in ('payment','case-management'):
        base,c,plan,draft=proposal(domain)
        for suffix,value in [('proposal-authoring',draft),('change',c),('plan',plan),('canonical-candidate',plan['candidate'])]:
            (DEST/(domain+'-'+suffix+'.json')).write_text(json.dumps(value,indent=2)+'\n')
        manifest['examples'].append({'file':domain+'-canonical-candidate.json','contentDigest':plan['candidate']['contentDigest'],
            'baseContentDigest':base['contentDigest'],'planDigest':plan['planDigest'],'proposalSourceDigest':digest(draft,'authoring')})
    (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (DEST/'byte-vectors.json').write_text(json.dumps(byte_vectors(),indent=2)+'\n')
    return manifest


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
