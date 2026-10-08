"""Pure PROPOSED deterministic reference algebras; no production authority/I/O."""
import copy
from datetime import datetime,timedelta
from decimal import Decimal
from fractions import Fraction
from functools import cmp_to_key
from canonical_json import canonical_bytes
from execution_model import FlowTypes
from execution_reference import ReferenceExecution, ExecutionFailure
from type_semantics import Types

ABSENT=object()


def order_rows(by,query,rows):
    canonical_bytes(rows)
    types=Types(by,lambda *a:None)
    for row in rows:
        for key in query['orderBy']:
            field=by[key['field']['id']]['data']; id=key['field']['id']
            if id not in row:
                if not field['optional']:raise ValueError('REQUIRED_ORDER_KEY')
            elif not types.valid_value(field['type'],row[id]):raise ValueError('ORDER_KEY_TYPE')
    def compare(a,b):
        for key in query['orderBy']:
            field=by[key['field']['id']]['data'];typ=field['type'];id=key['field']['id']
            x,y=a.get(id,ABSENT),b.get(id,ABSENT)
            for value in (x,y):
                if value is ABSENT:
                    if not field['optional']: raise ValueError('REQUIRED_ORDER_KEY')
                elif not types.valid_value(typ,value): raise ValueError('ORDER_KEY_TYPE')
            if x is ABSENT or y is ABSENT:
                if x is y: continue
                return (-1 if key['absent']=='FIRST' else 1)*(1 if x is ABSENT else -1)
            if x is None or y is None:
                if x is y: continue
                return (-1 if key['nulls']=='FIRST' else 1)*(1 if x is None else -1)
            if typ['kind']=='Nullable':typ=typ['item']
            if typ['kind']=='Named':typ=by[typ['definition']['id']]['data']['base']
            if typ['kind'] in {'Integer','Duration','Money','Decimal','Percentage'}:x,y=Decimal(x),Decimal(y)
            elif typ['kind'] in {'Instant','Date'}:x,y=datetime.fromisoformat(x),datetime.fromisoformat(y)
            c=(x>y)-(x<y)
            if c:return c if key['direction']=='ASC' else -c
        return 0
    return copy.deepcopy(sorted(rows,key=cmp_to_key(compare)))


class _Values:
    # Reuse the accepted pure expression algebra, not its 0.2 executor or ports.
    value=ReferenceExecution.value
    read_field=ReferenceExecution.read_field
    def __init__(self,by):self.index=by;self.types=Types(by,lambda *a:None)


def check_disposal_invariants(by,resource,record,partial=False):
    engine=_Values(by);types=FlowTypes(by,lambda *a:None)
    for n in by.values():
        if n['kind']!='Invariant' or n['data']['resource']!=resource or 'WRITE' not in n['data']['enforcement']:continue
        context={'resource':record,'infer':lambda expr:types.expression(n,expr,{'resource':resource},())}
        try: valid=engine.value(n['data']['predicate'],context)
        except (KeyError,ExecutionFailure):
            if partial:continue
            raise ValueError('POST_DISPOSAL_INVARIANT_CONTEXT') from None
        if valid is not True:raise ValueError('POST_DISPOSAL_INVARIANT')


def anonymize(by,policy,record,*,authorized,hold_active):
    if authorized is not True or hold_active is not False:raise ValueError('DISPOSAL_DENIED_OR_HELD')
    if policy['mode']!='ANONYMIZE':raise ValueError('ANONYMIZE_POLICY_REQUIRED')
    result=copy.deepcopy(record)
    for effect in policy['anonymizationEffects']:
        id=effect['field']['id']
        if effect['action']=='REMOVE':result.pop(id,None)
        elif effect['action']=='NULL':result[id]=None
        else:result[id]=copy.deepcopy(effect['replacement']['value'])
    types=Types(by,lambda *a:None)
    for n in by.values():
        if n['kind']=='Field' and n['data']['owner']==policy['resource']:
            f=n['data'];id=n['id']
            if (id not in result and not f['optional']) or (id in result and not types.valid_value(f['type'],result[id])):
                raise ValueError('POST_DISPOSAL_FIELD_CONSTRAINT')
    canonical_bytes(result)
    check_disposal_invariants(by,policy['resource'],result)
    return result


def closure_anchor(anchor,previous_state,new_state,commit_instant,*,committed):
    if committed is not True:return None
    if not Types({},lambda *a:None).valid_value({'kind':'Instant'},commit_instant):raise ValueError('COMMIT_INSTANT')
    if anchor['kind']=='CREATED_COMMIT':return commit_instant if previous_state is None else None
    states={r['id'] for r in anchor['states']}
    return commit_instant if new_state in states and previous_state not in states else None


class TokenBucket:
    """One explicitly scoped policy partition, with exact rational continuous refill.

    Time is supplied by the trusted caller in integer nanoseconds on a
    nondecreasing semantic time axis; never read a host clock here.
    """
    def __init__(self,policy):
        from deterministic_contract import RATE
        if policy['algorithm']!=RATE:raise ValueError('RATE_ALGORITHM')
        self.policy=copy.deepcopy(policy);self.tokens=Fraction(policy['burst']);self.last=None
    def admit(self,instant_ns,*,authorized):
        if type(instant_ns) is not int or instant_ns<0:raise ValueError('SEMANTIC_TIME')
        if authorized is not True:return False
        if self.last is not None and instant_ns<self.last:raise ValueError('CLOCK_REVERSED')
        if self.last is not None:
            self.tokens=min(Fraction(self.policy['burst']), self.tokens+Fraction((instant_ns-self.last)*self.policy['requests'],self.policy['windowSeconds']*1_000_000_000))
        self.last=instant_ns
        if self.tokens<1:return False
        self.tokens-=1;return True


def retry_delays(policy):
    return [min(policy['initialSeconds']*policy['multiplier']**n,policy['maxDelaySeconds']) for n in range(policy['maxAttempts']-1)]


def interval_occurrence(schedule,index):
    if schedule['mode']!='INTERVAL' or type(index) is not int or index<0:raise ValueError('INTERVAL_INDEX')
    if not Types({},lambda *a:None).valid_value({'kind':'Instant'},schedule['anchorInstant']):raise ValueError('INTERVAL_ANCHOR')
    return datetime.fromisoformat(schedule['anchorInstant'])+timedelta(seconds=index*schedule['intervalSeconds'])
