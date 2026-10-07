"""Authoring 0.3 validation. Pure dataflow; no target or approval implementation."""
import copy
from jsonschema import Draft202012Validator
from referencing import Registry
from execution_contract import authoring_schema, EXTENSIONS
from type_semantics import Types
from validate import semantic_walk

SHAPES = Draft202012Validator(authoring_schema(), registry=Registry())
SOURCE_TAGS = {'input', 'stepResult', 'postField'}
NEW_TAGS = SOURCE_TAGS | {'textContains'}
RANK = {'PUBLIC': 0, 'INTERNAL': 1, 'SENSITIVE': 2, 'SECRET': 3}


class FlowTypes(Types):
    def expression(self, node, expr, context, path):
        tag = expr['tag']
        if tag not in NEW_TAGS:
            return super().expression(node, expr, context, path)
        if tag == 'textContains':
            value = self.expression(node, expr['value'], context, (*path, 'value'))
            pattern = self.expression(node, expr['pattern'], context, (*path, 'pattern'))
            if value == pattern == {'kind': 'String'}:
                return {'kind': 'Boolean'}
            self.emit('FLOW_TYPE', node, path, 'Text containment requires two explicit nonnullable String operands.')
            return None
        field = self.target(expr['field'])['data']
        owner = None
        if tag == 'input':
            owner = context.get(expr['scope'])
        elif tag == 'postField':
            owner = context.get('post')
        elif tag == 'stepResult':
            owner = context.get('results', {}).get(expr['step']['id'])
        if owner != field['owner']:
            self.emit('FLOW_CONTEXT', node, path, 'Value source is unavailable in this exact execution context.')
            return None
        return {'kind': 'Optional', 'item': field['type']} if field['optional'] else field['type']


def validate_execution(document, mode='draft'):
    from validate import validate as historical_validate
    errors = []
    def emit(code, node, path, message):
        errors.append({'code': 'ACP-' + code, 'severity': 'ERROR', 'stage': 'semantic',
                       'subject': node.get('id', '') if node else '',
                       'path': '/' + '/'.join(map(str, path)), 'message': message,
                       'remediation': 'Author explicit typed, authorized dataflow for this exact semantic revision.'})
    try:
        from canonical_json import canonical_bytes
        canonical_bytes(document)
        if not SHAPES.is_valid(document):
            emit('FLOW_SHAPE', None, (), 'Input violates the closed Authoring 0.3 schema.')
            return errors
    except (ValueError, RecursionError, TypeError):
        emit('FLOW_SHAPE', None, (), 'Input violates bounded strict JSON.')
        return errors
    nodes = document['nodes']
    index = {n['id']: n for n in nodes}
    if len(index) != len(nodes):
        emit('FLOW_REF', None, (), 'Duplicate semantic ID.')
        return errors
    defs = SHAPES.schema['$defs']
    from phase1_semantics import typed_references
    def expect(node, reference, kinds, path):
        target = index.get(reference['id'])
        if target is None or target['revision'] != reference['revision']:
            emit('FLOW_REF', node, path, 'Exact referenced revision is absent.')
        elif kinds and target['kind'] not in kinds:
            emit('FLOW_REF', node, path, 'Reference has an incompatible kind.')
    for node in nodes:
        for item, path in semantic_walk(node):
            if isinstance(item, dict) and set(item) == {'id', 'revision'}:
                expect(node, item, (), path)
        typed_references(node['data'], defs[node['kind']], defs, expect, node, ('nodes', node['id'], 'data'))
        for item, path in semantic_walk(node['data']):
            if isinstance(item, dict) and item.get('tag') in SOURCE_TAGS:
                expect(node, item['field'], {'Field'}, path)
                if item['tag'] == 'stepResult':
                    expect(node, item['step'], {'ExecutionStep'}, path)
    if errors:
        return sorted(errors, key=lambda e: (e['subject'], e['path'], e['code']))
    # Validate every unchanged 0.2 rule, using an erasure only as an internal
    # structural check. This erasure is never canonicalized, admitted or executed.
    legacy = copy.deepcopy(document)
    legacy['modelVersion'] = '0.2.0'
    for node in legacy['nodes']:
        for key in EXTENSIONS.get(node['kind'], {}):
            node['data'].pop(key)
        if node['kind'] == 'ExecutionStep':
            node['data'].pop('compensationBindings', None)
        if any(isinstance(v, dict) and v.get('tag') in NEW_TAGS for v, _ in semantic_walk(node)):
            emit('FLOW_CONTEXT', node, (), 'New value sources require an explicit dataflow site.')
    if errors:
        return errors
    errors.extend(historical_validate(legacy, mode))
    if errors:
        return errors
    types = FlowTypes(index, emit)
    ref = lambda n: {'id': n['id'], 'revision': n['revision']}
    target = lambda r: index[r['id']]
    fields = lambda owner: types.owned_fields(owner)
    def actor(resource, operation=None):
        candidates = [n['data']['actor'] for n in nodes if n['kind'] == 'Permission' and n['data']['resource'] == resource
                      and (operation is None or n['data']['action'] == operation)]
        owners = [target(r)['data']['subject'] for r in candidates]
        return owners[0] if owners and all(r == owners[0] for r in owners) else None
    def base_context(n):
        d = n['data']
        return {'resource': d['resource'], 'actor': actor(d['resource'], ref(n)), 'OPERATION': d.get('input')}
    def check_expr(n, expr, context, wanted, path):
        inferred = types.expression(n, expr, context, path)
        if inferred != wanted:
            emit('FLOW_TYPE', n, path, 'Expression does not match its exact destination type or presence.')
    def check_classification(n, expr, destination, path):
        for value, _ in semantic_walk(expr):
            if isinstance(value, dict) and value.get('tag') in {'field', 'postField', 'input', 'stepResult'}:
                source = target(value.get('field', value.get('ref')))['data']
                if RANK[source['classification']] > RANK[destination['classification']]:
                    emit('FLOW_CLASSIFICATION', n, path, 'Dataflow cannot implicitly downgrade classified information.')
    def bindings(n, values, owner, context, path, expected=None):
        members = {f['id']: f for f in fields(owner)} if owner else {f['id']: f for f in expected}
        seen = set()
        for i, b in enumerate(values):
            f = target(b['field'])
            if f['id'] not in members or f['id'] in seen:
                emit('FLOW_BINDING', n, path, 'Binding is duplicated or does not belong to this destination.')
                continue
            seen.add(f['id'])
            check_expr(n, b['value'], context, f['data']['type'], (*path, i))
            check_classification(n, b['value'], f['data'], (*path, i))
        if any(not f['data']['optional'] and id not in seen for id, f in members.items()):
            emit('FLOW_REQUIRED', n, path, 'Required destination member has no explicit value binding.')
    def emissions(n, declared, values, context):
        by_event = {b['event']['id']: b for b in values}
        if len(by_event) != len(values) or set(by_event) != {r['id'] for r in declared}:
            emit('FLOW_EVENT', n, (), 'Every declared emission requires exactly one payload construction.')
        for b in values:
            event = target(b['event'])
            if event['data']['resource'] != context.get('post'):
                emit('FLOW_EVENT', n, (), 'Event resource differs from the command resource.')
            bindings(n, b['payload'], None, context, ('eventBindings', b['event']['id']),
                     [target(f) for f in event['data']['payload']])
    def consumed(n, input_ref, body, scope):
        used = {v['field']['id'] for v, _ in semantic_walk(body) if isinstance(v, dict) and v.get('tag') == 'input' and v['scope'] == scope}
        if any(not f['data']['optional'] and f['id'] not in used for f in fields(input_ref)):
            emit('FLOW_UNUSED', n, (), 'A required invocation input has no explicit consumer.')
    for n in nodes:
        d, kind = n['data'], n['kind']
        if kind == 'Command':
            context = base_context(n)
            resource = target(d['resource'])['data']
            immutable = resource['identity'] + ([resource['tenantField']] if 'tenantField' in resource else [])
            write_fields = d['writeFields']
            for f in write_fields:
                if target(f)['data']['owner'] != d['resource'] or f in immutable:
                    emit('FLOW_WRITE', n, (), 'Write fields must be mutable fields of the exact command root.')
            for i, effect in enumerate(d['assignments']):
                field = target(effect['field'])['data']
                if effect['resource'] != d['resource'] or field['owner'] != effect['resource'] or effect['resource'] not in d['writes'] or effect['field'] not in write_fields or effect['field'] in immutable:
                    emit('FLOW_WRITE', n, ('assignments', i), 'Assignment exceeds the exact mutable resource/field write boundary.')
                check_expr(n, effect['value'], {**context, 'post': d['resource']}, field['type'], ('assignments', i))
                check_classification(n, effect['value'], field, ('assignments', i))
            post = {**context, 'post': d['resource']}
            bindings(n, d['outputBindings'], d['output'], post, ('outputBindings',))
            emissions(n, d['emits'], d['eventBindings'], post)
            consumed(n, d['input'], d, 'OPERATION')
        if kind == 'Query':
            context = base_context(n)
            check_expr(n, d['predicate'], context, {'kind': 'Boolean'}, ('predicate',))
            consumed(n, d['input'], d['predicate'], 'OPERATION')
        if kind == 'Filter':
            field = target(d['inputField'])['data']
            if field['owner'] != target(d['query'])['data']['input'] or field['type'] != d['inputType']:
                emit('FLOW_BINDING', n, (), 'Filter input must bind an exact compatible member of its Query input.')
        if kind == 'Transition':
            command = target(d['command'])
            context = {**base_context(command), 'post': command['data']['resource']}
            emissions(n, d['effects'], d['eventBindings'], context)
            shared = {b['event']['id']: b for b in command['data']['eventBindings']}
            from execution_canonical import data as normalized_data
            if any(b['event']['id'] in shared and normalized_data(b, index, 'Transition', ('eventBindings', 0)) != normalized_data(shared[b['event']['id']], index, 'Command', ('eventBindings', 0)) for b in d['eventBindings']):
                emit('FLOW_EVENT', n, (), 'Shared command/transition emissions must have identical payload construction.')
        if kind == 'UseCase':
            context = {'USE_CASE': d['input'], 'results': {}}
            for step_ref in d['steps']:
                step = target(step_ref)
                sd = step['data']
                op = target(sd['operation'])
                check_expr(step, sd['resource'], context, {'kind': 'Identifier', 'entity': op['data']['resource']}, ('resource',))
                bindings(step, sd['inputBindings'], op['data']['input'], context, ('inputBindings',))
                context['results'][step['id']] = op['data']['output'] if op['kind'] == 'Command' else op['data']['result']['definition']
                if sd['onFailure'] == 'COMPENSATE':
                    if 'compensationBindings' not in sd:
                        emit('FLOW_COMPENSATION', step, (), 'Compensating command requires explicit invocation-input bindings.')
                    else:
                        compensator = target(sd['compensation'])
                        bindings(step, sd['compensationBindings'], compensator['data']['input'], {'USE_CASE': d['input']}, ('compensationBindings',))
                elif 'compensationBindings' in sd:
                    emit('FLOW_COMPENSATION', step, (), 'STOP steps cannot declare compensation bindings.')
            bindings(n, d['outputBindings'], d['output'], context, ('outputBindings',))
            body = [d['outputBindings'], *[target(s)['data'] for s in d['steps']]]
            consumed(n, d['input'], body, 'USE_CASE')
        if kind == 'Job':
            bindings(n, d['inputBindings'], target(d['useCase'])['data']['input'], {}, ('inputBindings',))
    return sorted(errors, key=lambda e: (e['subject'], e['path'], e['code']))
