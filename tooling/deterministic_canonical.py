"""PROPOSED Canonical 0.3; structural candidates never confer approval."""
import copy
from jsonschema import Draft202012Validator
from referencing import Registry
from canonical_json import PROFILE, digest
from canonical_ir import CanonicalError, _check_input, _literal, _threshold, ordered, _normalize_issues
from deterministic_contract import canonical_schema, FEATURE, EXTENSIONS
from deterministic_model import validate_deterministic

SHAPES=Draft202012Validator(canonical_schema(),registry=Registry())


def data(value,index,kind,path=()):
    from canonical_ir import ORDERED_REFS, ORDERED_ARRAYS, SET_ARRAYS, MAP_ARRAYS
    if isinstance(value,dict):
        if value.get('tag')=='literal' or set(value)=={'type','value'}:
            return {**copy.deepcopy(value),'value':_literal(value['type'],value['value'],index)}
        return {k:data(v,index,kind,path+(k,)) for k,v in value.items()}
    if isinstance(value,list):
        items=[data(v,index,kind,path+(i,)) for i,v in enumerate(value)]
        key=(kind,path[0]) if len(path)==1 else None
        if key in ORDERED_REFS|ORDERED_ARRAYS or path in {('assignments',),('orderBy',),('eventBindings',)}: return items
        if key in SET_ARRAYS|MAP_ARRAYS or (path and path[-1] in {'inputBindings','outputBindings','compensationBindings','eventBindings','payload','writeFields','anonymizationEffects'}) or all(isinstance(v,dict) and set(v)=={'id','revision'} for v in value): return ordered(items)
        raise CanonicalError('NORMAL','Array has no proposed deterministic ordering policy.')
    return copy.deepcopy(value)


def normalize(source):
    _check_input(source)
    if validate_deterministic(source,'compile'):
        raise CanonicalError('SEMANTIC','Authoring 0.4 fails proposed deterministic semantics.')
    index={n['id']:n for n in source['nodes']}; nodes=[]
    for original in source['nodes']:
        n=copy.deepcopy(original); n['basis']=ordered(n['basis']); n['origins']=ordered(n['origins'])
        n['data']=data(n['data'],index,n['kind'])
        if n['kind']=='TypeDefinition' and n['data']['refinement']['kind']=='RANGE':
            for k in ('min','max'): n['data']['refinement'][k]=_literal(original['data']['base'],original['data']['refinement'][k],index)
        if n['kind'] in {'PerformanceRequirement','ReliabilityRequirement'}: n['data']['threshold']=_threshold(original['data']['threshold'])
        nodes.append(n)
    c={'irKind':'CanonicalApplication','schemaVersion':'0.3.0','semanticModelVersion':'0.4.0',
       'canonicalProfile':PROFILE,'applicationId':source['applicationId'],'requiredFeatures':[FEATURE],
       'nodes':sorted(nodes,key=lambda n:n['id']),'issues':_normalize_issues(source['issues'])}
    return {'content':c,'contentDigest':digest(c,'canonical')}


def validate(snapshot):
    _check_input(snapshot)
    if not SHAPES.is_valid(snapshot): raise CanonicalError('SHAPE','Closed Canonical 0.3 shape required.')
    c=snapshot['content']
    # Existing change-candidate convention: these are internal structural
    # witnesses, not persisted reviewer assertions and never authority proofs.
    source={'modelVersion':'0.4.0','applicationId':c['applicationId'],'snapshotId':'STRUCTURAL-ONLY',
        'nodes':c['nodes'],'issues':c['issues'],'approvals':[{'subject':{'id':n['id'],'revision':n['revision']},
            'reviewer':'structural-only','evidence':'not-authority'} for n in c['nodes']]}
    if normalize(source)!=snapshot: raise CanonicalError('NORMAL','Candidate/digest is not normalized.')


def migration_review(source):
    from execution_model import validate_execution
    if source.get('modelVersion')!='0.3.0' or validate_execution(source,'compile'):
        raise CanonicalError('SEMANTIC','Valid approved-version Authoring 0.3 source required.')
    blockers=[]
    for n in source['nodes']:
        missing=list(EXTENSIONS.get(n['kind'],{}))
        if n['kind']=='Schedule' and n['data']['mode']=='INTERVAL': missing.append('anchorInstant')
        if missing: blockers.append({'subject':{'id':n['id'],'revision':n['revision']},'status':'REVIEW_REQUIRED','missing':sorted(missing)})
    candidate=None
    if not blockers:
        candidate=copy.deepcopy(source);candidate['modelVersion']='0.4.0';candidate['approvals']=[]
    return {'sourceDigest':digest(source,'authoring'),'targetModelVersion':'0.4.0',
        'status':'REVIEW_REQUIRED' if blockers else 'REQUIRES_NEW_APPROVAL',
        'blockers':sorted(blockers,key=lambda b:b['subject']['id']),'candidate':candidate,'requiresFreshExactContentApproval':True}


def main():
    import argparse,json
    from pathlib import Path
    from canonical_json import load
    parser=argparse.ArgumentParser(description='Review missing meaning for proposed Authoring 0.3 to 0.4 migration; never approve.')
    parser.add_argument('source',type=Path)
    args=parser.parse_args()
    try:
        result=migration_review(load(args.source))
        print(json.dumps(result,indent=2))
        return 1 if result['status']=='REVIEW_REQUIRED' else 0
    except (OSError,ValueError,TypeError,RecursionError):
        print(json.dumps({'status':'INVALID_INPUT','candidate':None,'authority':'NONE'}))
        return 2


if __name__=='__main__':raise SystemExit(main())
