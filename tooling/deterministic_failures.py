"""PROPOSED canonical FailureBinding typing, precedence and occurrences."""
import copy
from canonical_json import canonical_bytes
from execution_model import FlowTypes
from validate import semantic_walk
from phase1_semantics import typed_references
from deterministic_contract import FAILURE_BINDING, authoring_schema

STAGES={'PRE_STATE':0,'POST_ASSIGNMENT':1,'INVARIANT':2,'INFRASTRUCTURE':3}
FAULTS={'DEPENDENCY_UNAVAILABLE','SERIALIZATION_CONFLICT','TIMEOUT'}


def validate_bindings(document, emit):
    by={n['id']:n for n in document['nodes']}
    defs=authoring_schema()['$defs']
    for op in document['nodes']:
        if op['kind']!='Command':continue
        d=op['data']; bindings=d['failureBindings'];seen=set();covered=set();last=-1
        def err(code,message):emit('FAILURE_'+code,op,message)
        types=FlowTypes(by,lambda code,n,path,message:err('CONTEXT',message))
        actor_refs=[n['data']['actor'] for n in by.values() if n['kind']=='Permission' and n['data']['action']=={'id':op['id'],'revision':op['revision']}]
        actors=[by[r['id']]['data']['subject'] for r in actor_refs]
        for b in bindings:
            stage=b['stage'];tr=b['trigger'];kind=tr['kind'];failure=by.get(b['failure']['id'])
            bad=False
            for v,_ in semantic_walk(b):
                if isinstance(v,dict) and set(v)=={'id','revision'}:
                    node=by.get(v['id'])
                    if node is None or node['revision']!=v['revision']:
                        err('REF','Binding references an absent exact revision.');bad=True
            def expect(node, reference, kinds, path):
                nonlocal bad
                target=by.get(reference['id'])
                if target is None or target['revision']!=reference['revision'] or (kinds and target['kind'] not in kinds):
                    err('REF','Binding reference kind or exact revision is invalid.');bad=True
            typed_references(b,FAILURE_BINDING,defs,expect,op,())
            if bad:continue
            if failure['kind']!='Failure' or b['failure'] not in d['failures']:
                err('DECLARATION','Bound Failure must belong to this operation exact declaration.');continue
            covered.add(failure['id'])
            if STAGES[stage]<last:err('PRECEDENCE','Bindings must appear in nondecreasing semantic stage order.')
            last=STAGES[stage]
            allowed={'WORKFLOW_NO_APPLICABLE_TRANSITION':{'PRE_STATE'},'PREDICATE':{'PRE_STATE','POST_ASSIGNMENT'},'INVARIANT_FAILURE':{'INVARIANT'},'INFRASTRUCTURE_CLASS':{'INFRASTRUCTURE'}}
            if stage not in allowed[kind]:err('STAGE','Trigger is unavailable at this stage.')
            category=failure['data']['category']
            if category not in ({'TRANSIENT'} if kind=='INFRASTRUCTURE_CLASS' else {'BUSINESS','SECURITY'} if kind=='PREDICATE' else {'BUSINESS'}):
                err('CATEGORY','Trigger and Failure category are incompatible.')
            if kind=='WORKFLOW_NO_APPLICABLE_TRANSITION':
                m=by[tr['machine']['id']]
                if m['kind']!='StateMachine' or m['data']['resource']!=d['resource'] or not any(n['kind']=='Transition' and n['data']['machine']==tr['machine'] and n['data']['command']=={'id':op['id'],'revision':op['revision']} for n in by.values()):
                    err('WORKFLOW','Workflow binding requires this command exact applicable resource machine.')
            elif kind=='INVARIANT_FAILURE':
                inv=by[tr['invariant']['id']]
                if inv['kind']!='Invariant' or inv['data']['resource']!=d['resource'] or 'WRITE' not in inv['data']['enforcement']:
                    err('INVARIANT','Binding requires an exact applicable WRITE invariant.')
            elif kind=='PREDICATE':
                bad_expr=False
                for v,_ in semantic_walk(tr['condition']):
                    if not isinstance(v,dict):continue
                    tag=v.get('tag')
                    if tag in {'field','present','input','postField','stepResult'}:
                        r=v.get('ref',v.get('field'));target=by.get(r['id']) if r else None
                        if target is None or target['kind']!='Field':bad_expr=True
                    if tag=='parameter' and by[v['ref']['id']]['kind']!='Parameter':bad_expr=True
                    if tag=='stepResult' or (tag=='input' and v['scope']!='OPERATION') or (stage=='PRE_STATE' and tag=='postField'):bad_expr=True
                if bad_expr:
                    err('CONTEXT','Predicate uses an unavailable source or incompatible reference kind.');continue
                context={'resource':d['resource'],'OPERATION':d['input'],'actor':actors[0] if actors and all(a==actors[0] for a in actors) else None}
                if stage=='POST_ASSIGNMENT':context['post']=d['resource']
                if types.expression(op,tr['condition'],context,())!={'kind':'Boolean'}:
                    err('TYPE','Failure predicate must be an exact nonnullable Boolean.');continue
            from canonical_ir import _data
            signature=canonical_bytes({'stage':stage,'trigger':_data(tr,by,'Command')})
            if signature in seen:err('DUPLICATE','Duplicate trigger is ambiguous even when failures differ.')
            seen.add(signature)
        if covered!={r['id'] for r in d['failures']}:
            err('COVERAGE','Every declared Failure requires an explicit binding, including potential operational faults.')


def envelope(index, operation, failure, correlation):
    f=index[failure['id']]
    return {'failure':copy.deepcopy(failure),'code':f['data']['code'],
        'category':f['data']['category'],'retryable':f['data']['retryable'],
        'operation':{'id':operation['id'],'revision':operation['revision']},'correlationId':correlation}


def retry_allowed(index, policy, occurrence):
    """Caller must supply a trusted exact-binding occurrence, not a wire claim."""
    if occurrence.get('origin')!='EXACT_FAILURE_BINDING':return False
    op=index.get(occurrence['operation']['id']);f=index.get(occurrence['failure']['id'])
    if not op or not f or op['revision']!=occurrence['operation']['revision'] or f['revision']!=occurrence['failure']['revision']:return False
    binding=occurrence.get('bindingIndex')
    if type(binding) is not int or not 0<=binding<len(op['data']['failureBindings']):return False
    return (op['data']['failureBindings'][binding]['failure']==occurrence['failure'] and occurrence['failure'] in policy['failures'] and
            f['data']['category']=='TRANSIENT' and f['data']['retryable'] is True and occurrence['category']=='TRANSIENT' and occurrence['retryable'] is True)
