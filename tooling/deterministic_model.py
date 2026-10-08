"""Pure validation of PROPOSED deterministic semantics; no target/authority."""
import copy
from jsonschema import Draft202012Validator
from referencing import Registry
from deterministic_contract import authoring_schema, EXTENSIONS
from execution_model import validate_execution
from type_semantics import Types

SHAPES = Draft202012Validator(authoring_schema(), registry=Registry())


def validate_deterministic(document, mode='draft'):
    from canonical_json import canonical_bytes
    errors = []
    def emit(code, node, message):
        errors.append({'code':'ACP-DETERMINISTIC-'+code,'severity':'ERROR','stage':'semantic',
            'subject':node.get('id','') if node else '', 'path':'/nodes/' + node.get('id','') if node else '/',
            'message':message, 'remediation':'Author explicit reviewed deterministic semantics for this exact revision.'})
    try:
        canonical_bytes(document)
        if not SHAPES.is_valid(document):
            raise ValueError()
    except (ValueError,TypeError,RecursionError):
        emit('SHAPE',{},'Closed Authoring 0.4 schema or bounded JSON violation.')
        return errors
    legacy = copy.deepcopy(document); legacy['modelVersion']='0.3.0'
    for n in legacy['nodes']:
        for k in EXTENSIONS.get(n['kind'],{}): n['data'].pop(k)
        if n['kind']=='Schedule': n['data'].pop('anchorInstant',None)
    errors.extend(validate_execution(legacy,mode))
    if errors: return errors
    by = {n['id']:n for n in document['nodes']}
    types = Types(by,lambda *a:None)
    ref = lambda n: {'id':n['id'],'revision':n['revision']}
    def target(r,kind,n):
        t=by.get(r['id'])
        if t is None or t['revision']!=r['revision'] or t['kind']!=kind:
            emit('REF',n,'New semantic reference must have exact kind and revision.'); return None
        return t
    for n in document['nodes']:
        k,d=n['kind'],n['data']
        if k=='Job':
            if (d['missedOccurrences']=='CATCH_UP') != (d['catchUp'] is not None):
                emit('JOB_CATCH_UP',n,'Only CATCH_UP requires a bounded maximum and explicit overflow; other modes require null.')
        elif k=='DeliveryPolicy' and 'deduplication' in d:
            idem=target(d['deduplication'],'IdempotencyPolicy',n)
            if idem and idem['data']['windowSeconds'] < d['windowSeconds']:
                emit('DELIVERY_DEDUP',n,'Deduplication retention must cover the entire event delivery window.')
        elif k=='Command':
            events=[b['event']['id'] for b in d['eventBindings']]
            if len(events)!=len(set(events)):
                emit('EMISSION_AMBIGUITY',n,'One binding per event semantic identity; IDs detect ambiguity and never sort emissions.')
        elif k=='Query':
            resource=by[d['resource']['id']]; seen=[]
            for order in d['orderBy']:
                f=target(order['field'],'Field',n)
                if not f: continue
                fd=f['data']; typ=fd['type']; nullable=typ['kind']=='Nullable'
                if fd['owner']!=d['resource']: emit('ORDER_OWNER',n,'Order key must belong to query resource.')
                if order['field'] in seen: emit('ORDER_DUPLICATE',n,'Order keys cannot repeat.')
                seen.append(order['field'])
                if nullable != ('nulls' in order) or fd['optional'] != ('absent' in order):
                    emit('ORDER_PRESENCE',n,'Nullable and optional keys need distinct explicit placement; irrelevant placement is forbidden.')
                if nullable: typ=typ['item']
                if typ['kind']=='Named': typ=by[typ['definition']['id']]['data']['base']
                if typ['kind'] not in {'String','Identifier','Integer','Duration','Boolean','Money','Decimal','Percentage','Date','Instant'}:
                    emit('ORDER_TYPE',n,'Only declared totally ordered scalar semantic types are supported.')
            identity=resource['data']['identity']
            if d['paginated'] and (len(seen)<len(identity) or {r['id'] for r in seen[-len(identity):]}!={r['id'] for r in identity}):
                emit('ORDER_TOTAL',n,'Paginated query requires the complete identity as its explicit final tie-breaker; independent uniqueness proofs are outside this bounded version.')
        elif k=='DataLifecycle':
            anchor=d['anchor']; trigger=by[d['retention']['id']]['data']['trigger']
            if (trigger=='CLOSED') != (anchor['kind']=='CLOSED_COMMIT'):
                emit('CLOSURE_TRIGGER',n,'Lifecycle anchor must match both policy triggers.')
            if anchor['kind']=='CLOSED_COMMIT':
                machine=target(anchor['machine'],'StateMachine',n)
                if machine and machine['data']['resource']!=d['resource']:
                    emit('CLOSURE_RESOURCE',n,'Closing machine must govern lifecycle resource.')
                for state in anchor['states']:
                    s=target(state,'State',n)
                    if s and (s['data']['machine']!=anchor['machine'] or not s['data']['terminal']):
                        emit('CLOSURE_STATE',n,'Closing states must belong to the machine and be terminal.')
        elif k in {'Retention','DeletionPolicy'}:
            if d['trigger']=='CLOSED' and not any(x['kind']=='DataLifecycle' and x['data']['resource']==d['resource'] and
                    x['data']['anchor']['kind']=='CLOSED_COMMIT' for x in document['nodes']):
                emit('CLOSURE_MISSING',n,'CLOSED policy requires an explicit lifecycle anchor; names are not evidence.')
            if k=='DeletionPolicy':
                fields=[]
                for effect in d['anonymizationEffects']:
                    f=target(effect['field'],'Field',n)
                    if not f: continue
                    fields.append(effect['field']); fd=f['data']; entity=by[d['resource']['id']]['data']
                    if fd['owner']!=d['resource'] or effect['field'] in [*entity['identity'],entity.get('tenantField')]:
                        emit('ANONYMIZE_OWNER',n,'Cannot anonymize foreign, identity or tenant fields.')
                    if effect['action']=='REMOVE' and not fd['optional']: emit('ANONYMIZE_REMOVE',n,'REMOVE requires an optional field.')
                    if effect['action']=='NULL' and fd['type']['kind']!='Nullable': emit('ANONYMIZE_NULL',n,'NULL requires Nullable, distinct from absence.')
                    if effect['action']=='REPLACE' and (effect['replacement']['type']!=fd['type'] or
                            not types.valid_value(fd['type'],effect['replacement']['value'])):
                        emit('ANONYMIZE_TYPE',n,'Replacement must be a valid explicit constant of the exact field type.')
                replacements={e['field']['id']:e['replacement']['value'] for e in d['anonymizationEffects'] if e['action']=='REPLACE'}
                if replacements:
                    from deterministic_reference import check_disposal_invariants
                    try: check_disposal_invariants(by,d['resource'],replacements,partial=True)
                    except ValueError: emit('ANONYMIZE_INVARIANT',n,'Explicit replacement violates an applicable retained WRITE invariant.')
                if len(fields)!=len({r['id'] for r in fields}) or sorted(r['id'] for r in fields)!=sorted(r['id'] for r in d['fields']):
                    emit('ANONYMIZE_COVERAGE',n,'Every listed anonymization field needs exactly one effect; other modes have no effects.')
        elif k=='Schedule' and d['mode']=='INTERVAL':
            if not types.valid_value({'kind':'Instant'},d['anchorInstant']):
                emit('INTERVAL_ANCHOR',n,'Interval anchor must be an exact valid UTC Instant.')
    return sorted(errors,key=lambda e:(e['subject'],e['code'],e['path']))
