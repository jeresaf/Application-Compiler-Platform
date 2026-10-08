"""PROPOSED executable algebra, not a production store, scheduler or transport.

All instants are supplied integer nanoseconds. State is serializable evidence;
linearization/atomic persistence are premises a real target must independently
prove. No worker clock, lease expiry, process cache or transport is provided.
"""
import copy
from canonical_json import digest, canonical_bytes
from canonical_ir import _literal
from type_semantics import Types

SECOND = 1_000_000_000


def typed_input_digest(typ, value, index):
    """Bind the exact declared type and its canonical semantic value."""
    if not Types(index, lambda *a: None).valid_value(typ, value):
        raise ValueError('Exact semantic input type required')
    return digest({'type': typ, 'value': _literal(typ, value, index)}, 'canonical')


def identity(policy, tenant, resource, operation, key, occurrence=None):
    # Keys are canonical typed values, resource is an exact typed identity;
    # operation and policy are exact semantic references, not display names.
    return canonical_bytes({'policy': policy, 'tenant': tenant, 'resource': resource,
                            'operation': operation, 'key': key, 'occurrence': occurrence}).decode()


def reserve(state, key, input_digest, now, window_seconds, *, owner="reference-execution"):
    """One serialized transition. INDETERMINATE never times out."""
    if type(now) is not int or type(window_seconds) is not int or window_seconds < 1:
        raise ValueError('Exact instant and positive window required')
    s = copy.deepcopy(state)
    old = s.get(key)
    if old and old['status'] == 'COMMITTED' and now < old['commit']:
        raise ValueError('Invocation cannot precede recorded commit')
    if old and old['status'] == 'COMMITTED' and now >= old['commit'] + window_seconds * SECOND:
        old = None
    if old:
        if old['input'] != input_digest:
            return s, {'status': 'CONFLICT'}
        if old['status'] == 'COMMITTED':
            return s, {'status': 'REPLAY', 'result': copy.deepcopy(old['result'])}
        return s, {'status': 'IN_PROGRESS'}
    s[key] = {'status': 'IN_FLIGHT', 'input': input_digest, 'owner': owner}
    return s, {'status': 'RESERVED'}


def uncertain(state, key):
    s = copy.deepcopy(state)
    if s[key]['status'] != 'IN_FLIGHT':
        raise ValueError('Only a live reservation can become indeterminate')
    s[key]['status'] = 'INDETERMINATE'
    return s


def recover(state, key, *, proof, result=None, commit=None):
    """Proof is an explicit trusted semantic commit fact, never worker death."""
    s = copy.deepcopy(state)
    if s[key]['status'] not in {'IN_FLIGHT', 'INDETERMINATE'}:
        raise ValueError('Reservation is not pending')
    if proof == 'ROLLBACK_NO_EFFECT':
        del s[key]
    elif proof == 'COMMITTED' and type(commit) is int:
        s[key].update(status='COMMITTED', commit=commit, result=copy.deepcopy(result))
    else:
        raise ValueError('Definitive commit/rollback evidence required')
    return s


def commit_transaction(state, key, *, instant, result, domain, steps, aggregate,
                       commit_sequence, policies, owner="reference-execution"):
    """Single proposed atomic result: domain + result + occurrences + reservation.

    steps is ordered execution steps, each containing ordered emission bindings.
    A transaction-wide monotonically increasing commit sequence is supplied by
    the serialization witness; event IDs never determine sequence.
    """
    if state[key]['status'] != 'IN_FLIGHT' or state[key]['owner'] != owner:
        raise ValueError('Only the reservation owner can commit')
    occurrences = []
    for step, emissions in enumerate(steps):
        ids = [e['event']['id'] for e in emissions]
        if len(ids) != len(set(ids)):
            raise ValueError('Ambiguous duplicate emission binding')
        for emission, e in enumerate(emissions):
            p = policies[e['event']['id']]
            occurrences.append({'event': copy.deepcopy(e), 'aggregate': copy.deepcopy(aggregate),
                'sequence': [commit_sequence, step, emission], 'commit': instant,
                'deadline': instant + p['windowSeconds'] * SECOND,
                'guarantee': p['guarantee'], 'ordering': p['ordering'],
                'status': 'PENDING', 'attempts': 0})
    return {'idempotency': recover(state, key, proof='COMMITTED', result=result, commit=instant),
            'domain': copy.deepcopy(domain), 'result': copy.deepcopy(result), 'events': occurrences}


def delivery_status(event, now):
    if event['status'] in {'ACKNOWLEDGED', 'ATTEMPTED'}:
        return event['status']
    return 'UNSATISFIED' if now >= event['deadline'] else 'PENDING'


def send(events, selected, now, *, outcome):
    """An externally visible attempt consumes AT_MOST_ONCE before its outcome.

    For AT_LEAST_ONCE an unacknowledged attempt remains pending, including
    uncertain outcomes. The reference has no automatic transport side effects.
    """
    if outcome not in {'ACKNOWLEDGED', 'FAILED', 'UNCERTAIN'}:
        raise ValueError('Unknown outcome')
    s = copy.deepcopy(events); e = s[selected]
    if now < e['commit'] or delivery_status(e, now) != 'PENDING':
        raise ValueError('Not eligible')
    if e['ordering'] == 'PER_AGGREGATE' and any(
            p['aggregate'] == e['aggregate'] and p['sequence'] < e['sequence'] and
            delivery_status(p, now) == 'PENDING' for p in s):
        raise ValueError('Earlier unexpired occurrence must complete first')
    e['attempts'] += 1
    if e['guarantee'] == 'AT_MOST_ONCE':
        e['status'] = 'ATTEMPTED'
    elif outcome == 'ACKNOWLEDGED':
        e['status'] = 'ACKNOWLEDGED'
    return s


def missed_occurrences(job, occurrences, activation):
    """Input is the trusted schedule's not-started occurrence instants.

    Earlier means strictly < activation. An occurrence at activation belongs to
    normal scheduling. DROP_OLDEST retains the latest bounded suffix and runs
    it chronologically; REJECT runs none and exposes overflow for resolution.
    """
    if len(occurrences) != len(set(occurrences)):
        raise ValueError('Duplicate schedule occurrence')
    missed = sorted(x for x in occurrences if x < activation)
    mode = job['missedOccurrences']
    if mode == 'SKIP':
        return []
    if mode == 'RUN_LATEST':
        return missed[-1:]
    if mode != 'CATCH_UP' or not job['catchUp']:
        raise ValueError('Explicit recovery policy required')
    bound = job['catchUp']['maxOccurrences']
    if not 1 <= bound <= 10000:
        raise ValueError('Bounded replay required')
    if len(missed) > bound:
        if job['catchUp']['overflow'] == 'REJECT':
            raise ValueError('Missed-occurrence overflow')
        if job['catchUp']['overflow'] != 'DROP_OLDEST':
            raise ValueError('Explicit overflow rule required')
        missed = missed[-bound:]
    return missed


def lifecycle_action(hold, *, active, request, permission, tenant, resource,
                     action, transaction, committed):
    """One action, no reusable proof/token and no durable clearing of a hold.

    Caller authentication/disposal authorization precede this algebra. The
    request and exact permission proof must both bind this transaction scope.
    Returns only value-free audit facts; callers stage them with disposal.
    """
    context = {'tenant': tenant, 'resource': resource, 'action': action, 'transaction': transaction}
    if active is not True and active is not False:
        raise ValueError('Hold condition must be determinately evaluated')
    audit = []
    if active:
        expected = {**context, 'permission': hold['release']}
        if request != expected or permission != expected:
            raise ValueError('Active hold requires explicit exact current-action authorization')
        audit = [{**context, 'kind': 'HOLD_RELEASE_AUTHORIZED', 'permission': hold['release']}]
    return {'disposed': bool(committed), 'audit': audit if committed else [], 'holdCleared': False}


def observation(classification, value, *, surface, metadata=None):
    if surface not in {'LOG', 'TRACE', 'DIAGNOSTIC_ERROR', 'AUDIT_VALUE'}:
        raise ValueError('Observability only; never transform domain/API/event values')
    result = {'metadata': copy.deepcopy(metadata or {})}
    # Metadata must be semantic identifiers, not arbitrary derived field values.
    if any(k not in {'fieldId', 'resourceId', 'operationId'} for k in result['metadata']):
        raise ValueError('No arbitrary raw-value metadata')
    mode = classification['redaction']
    if mode == 'NONE':
        result['value'] = copy.deepcopy(value)
    elif mode == 'MASK':
        result['redacted'] = True  # fixed marker, deliberately outside domain type
    elif mode != 'OMIT':
        raise ValueError('Closed redaction mode required')
    return result


def invocation(*, authenticated, authorized, bucket, now, state, key,
               input_digest, window_seconds, execute):
    """Reference ordering: rejected auth/rate never executes or claims.

    execute owns the proposed single semantic commit transition above. Delivery
    is a separate postcommit transition. Replay cannot call execute or enqueue.
    """
    if not authenticated or not authorized:
        return state, {'status': 'UNAUTHORIZED'}
    if not bucket.admit(now, authorized=True):
        return state, {'status': 'RATE_DENIED'}
    claimed, outcome = reserve(state, key, input_digest, now, window_seconds)
    if outcome['status'] != 'RESERVED':
        return claimed, outcome
    return execute(claimed)
