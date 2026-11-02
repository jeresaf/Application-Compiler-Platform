"""Explicitly unapproved reference proposal; never an accepted snapshot lookup."""
import copy
from engineering.native_create import semantics
from deterministic_approval import approved_snapshot


def proposal():
    source = semantics.authoring(approved_snapshot('case-management'))
    nodes = {n['id']: n for n in source['nodes']}
    def ref(identity):
        return {'id': identity, 'revision': nodes[identity]['revision'] if identity in nodes else 1}
    def node(identity, kind, data, basis=()):
        value = {'id': identity, 'revision': 1, 'kind': kind,
                 'name': 'PROPOSED ' + identity, 'lifecycle': 'APPROVED',
                 'steward': 'assistant:proposal',
                 'origins': [{'source': 'proposal:phase10-r4-create', 'locator': identity,
                              'actor': 'assistant:proposal', 'actorType': 'AI'}],
                 'basis': [ref(i) for i in basis], 'data': data}
        source['nodes'].append(value)
        nodes[identity] = value
    node('REQ-R4-CREATE', 'Requirement', {
        'statement': 'PROPOSED native creation with explicit inputs, authenticated tenant and self-assignee, identity policy, initial state, authorization, audit and idempotency. Synthetic execution only until exact semantic approval.',
        'priority': 'MUST', 'acceptance': [ref('AC-R4-CREATE')]})
    node('AC-R4-CREATE', 'AcceptanceCriterion', {
        'requirement': ref('REQ-R4-CREATE'),
        'scenario': 'Create without a selected resource; validate closed typed inputs; preserve tenant, principal, required fields and optional absence; replay exactly once across restart; then review, approve and archive. Reject unauthorized and conflicting requests.'}, ('REQ-R4-CREATE',))
    bindings = {
        'CASE-ID': {'kind': 'GENERATED_UUID'},
        'CASE-TENANT': {'kind': 'AUTHENTICATED_TENANT'},
        'CASE-ASSIGNEE': {'kind': 'AUTHENTICATED_SUBJECT'},
        'FLD-NOTE': {'kind': 'ABSENT'}}
    for name, identity, member, maximum in (
            ('title', 'FLD-CASE-TITLE', 'FLD-TITLE', 200),
            ('summary', 'FLD-TASK-SUMMARY', None, 2000)):
        bindings[identity] = {'kind': 'INPUT', 'name': name,
            'type': {'kind': 'String'}, 'member': ref(member) if member else None,
            'minimumLength': 1, 'maximumLength': maximum}
    node('CREATE-CASE', 'CreateOperation', {
        **{k: ref(v) for k, v in {'resource': 'CASE', 'identity': 'CASE-ID',
            'tenant': 'CASE-TENANT', 'principal': 'CASE-ASSIGNEE',
            'permission': 'PERM-CREATE-CASE', 'initialState': 'STATE-OPEN'}.items()},
        'bindings': bindings,
        'idempotency': {'scope': 'ACTOR_TENANT_OPERATION_KEY', 'windowSeconds': 3600,
                        'replay': 'SAME_INPUT_ONLY', 'concurrency': 'ONE_COMMITTED_CREATION'},
        'rate': {'algorithm': 'TOKEN_BUCKET_CONTINUOUS_RATIONAL',
                 'partition': 'ACTOR_TENANT', 'requests': 30, 'windowSeconds': 60, 'burst': 10},
        'audit': 'REQUIRED', 'events': [],
        'outcomes': ['INVALID_INPUT', 'UNAUTHORIZED', 'IDENTITY_CONFLICT',
                     'IDEMPOTENCY_CONFLICT', 'IN_PROGRESS', 'RATE_DENIED', 'INTERNAL']},
         ('REQ-R4-CREATE', 'AC-R4-CREATE'))
    node('PERM-CREATE-CASE', 'CreatePermission', {
        **{k: ref(v) for k, v in {'operation': 'CREATE-CASE', 'actor': 'ACT-REVIEWER',
            'role': 'ROLE-REVIEWER', 'scope': 'SCOPE-CASE'}.items()},
        'effect': 'ALLOW', 'tenantRule': 'AUTHENTICATED_TENANT',
        'principalRule': 'AUTHENTICATED_SUBJECT'}, ('REQ-R4-CREATE',))
    screen = next(n['id'] for n in source['nodes'] if n['kind'] == 'Screen')
    node('FORM-CREATE-CASE', 'CreateForm', {
        'operation': ref('CREATE-CASE'), 'screen': ref(screen),
        'permission': ref('PERM-CREATE-CASE'), 'controls': ['title', 'summary'],
        'states': ['IDLE', 'SUBMITTING', 'SUCCESS', 'FAILURE'],
        'existingResourceSelection': False}, ('REQ-R4-CREATE',))
    return copy.deepcopy(source)
