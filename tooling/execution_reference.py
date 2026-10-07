"""Pure executable Authoring 0.3 reference algebra; not a production executor.

Returns a detached committed value, never mutates caller state or publishes events.
The caller supplies trusted authorization. No JSON field can grant authorization.
"""
import copy
from decimal import Decimal, localcontext
from canonical_ir import validate_snapshot
from type_semantics import Types, quantize

ABSENT = object()


class ExecutionFailure(ValueError):
    pass


class ReferenceExecution:
    def __init__(self, snapshot):
        snapshot = copy.deepcopy(snapshot)
        validate_snapshot(snapshot)
        if snapshot['content']['schemaVersion'] != '0.2.0':
            raise ExecutionFailure('EXPLICIT_EFFECTS_REQUIRED')
        self.index = {n['id']: n for n in snapshot['content']['nodes']}
        self.types = Types(self.index, lambda *args: None)

    def read_field(self, id, source):
        field = self.index[id]['data']
        value = source.get(id, ABSENT)
        if value is ABSENT and field['optional']:
            return ABSENT
        if value is ABSENT or not self.types.valid_value(field['type'], value):
            raise ExecutionFailure('RESOURCE_VALUE_TYPE')
        return value

    def value(self, expr, context):
        tag = expr['tag']
        if tag == 'literal':
            return copy.deepcopy(expr['value'])
        if tag == 'parameter':
            return copy.deepcopy(self.index[expr['ref']['id']]['data']['value'])
        if tag in {'field', 'present'}:
            source = context[expr['binding']]
            return expr['ref']['id'] in source if tag == 'present' else self.read_field(expr['ref']['id'], source)
        if tag == 'postField':
            return self.read_field(expr['field']['id'], context['post'])
        if tag == 'input':
            return context[expr['scope']].get(expr['field']['id'], ABSENT)
        if tag == 'stepResult':
            return context['results'][expr['step']['id']].get(expr['field']['id'], ABSENT)
        if tag == 'coalesce':
            value = self.value(expr['value'], context)
            return self.value(expr['fallback'], context) if value is ABSENT or value is None else value
        if tag == 'size':
            return str(len(self.value(expr['value'], context)))
        if tag == 'textContains':
            return self.value(expr['pattern'], context) in self.value(expr['value'], context)
        if tag == 'contains':
            collection = self.value(expr['collection'], context)
            value = self.value(expr['value'], context)
            typ = context['infer'](expr['collection'])['element']
            return any(self.types.value_key(typ, item) == self.types.value_key(typ, value) for item in collection)
        a, b = self.value(expr['left'], context), self.value(expr['right'], context)
        if a is ABSENT or b is ABSENT:
            raise ExecutionFailure('ABSENT_VALUE')
        op = expr['op']
        if op in {'eq', 'identityEq'}:
            typ = context['infer'](expr['left'])
            return self.types.value_key(typ, a) == self.types.value_key(typ, b)
        if op == 'and':
            return a is True and b is True
        # Static validation has already bound operand types; compare temporal
        # values lexically after canonical UTC normalization, numeric values exactly.
        # Runtime operand typing is supplied by the validated expression context.
        typ = context['infer'](expr['left'])
        if op == 'gt':
            if typ['kind'] in {'Integer', 'Duration', 'Decimal', 'Money'}:
                return Decimal(a) > Decimal(b)
            from datetime import datetime, date
            parser = date.fromisoformat if typ['kind'] == 'Date' else datetime.fromisoformat
            return parser(a) > parser(b)
        if op == 'add':
            if typ['kind'] in {'Integer', 'Duration'}:
                return str(int(a) + int(b))
            with localcontext() as precision:
                precision.prec = 160
                value = Decimal(a) + Decimal(b)
            return quantize(format(value, 'f'), typ) if typ['kind'] in {'Decimal', 'Money'} else str(int(value))
        raise ExecutionFailure('EXPRESSION')

    def construct(self, bindings, context):
        result = {}
        for b in bindings:
            value = self.value(b['value'], context)
            if value is ABSENT:
                raise ExecutionFailure('ABSENT_VALUE')
            result[b['field']['id']] = copy.deepcopy(value)
        return result

    def typed(self, owner, value):
        if not self.types.valid_value({'kind': 'Value', 'definition': owner}, value):
            raise ExecutionFailure('INPUT_OR_OUTPUT_TYPE')
        return value

    def execute(self, use_case, invocation, resources, *, actor=None, authorize=None, after_step=None):
        from execution_model import FlowTypes
        uc = self.index[use_case]
        invocation = copy.deepcopy(invocation)
        if any(self.index[s['id']]['data']['onFailure'] == 'COMPENSATE' for s in uc['data']['steps']):
            raise ExecutionFailure('COMPENSATION_EXECUTOR_REQUIRED')
        transactions = [self.index[s['id']]['data'].get('transaction') for s in uc['data']['steps']]
        if len(transactions) > 1 and (None in transactions or any(t != transactions[0] for t in transactions)):
            raise ExecutionFailure('MULTI_COMMIT_EXECUTOR_REQUIRED')
        self.typed(uc['data']['input'], invocation)
        committed = copy.deepcopy(resources)
        actor = copy.deepcopy(actor or {})
        results, events = {}, []
        transaction_resource = None
        context = {'USE_CASE': invocation, 'results': results}
        for step_ref in uc['data']['steps']:
            step = self.index[step_ref['id']]
            sd = step['data']
            op = self.index[sd['operation']['id']]
            d = op['data']
            resource_id = self.value(sd['resource'], context)
            key = (d['resource']['id'], resource_id)
            if sd.get('transaction') is not None:
                if transaction_resource is not None and transaction_resource != key:
                    raise ExecutionFailure('TRANSACTION_RESOURCE')
                transaction_resource = key
            if key not in committed:
                raise ExecutionFailure('RESOURCE_NOT_FOUND')
            resource = committed[key]
            entity = self.index[d['resource']['id']]['data']
            if len(entity['identity']) != 1 or resource.get(entity['identity'][0]['id']) != resource_id:
                raise ExecutionFailure('IDENTITY')
            if authorize is None or authorize(op['id'], copy.deepcopy(resource), copy.deepcopy(actor)) is not True:
                raise ExecutionFailure('DENIED')
            scopes = [n['data'] for n in self.index.values() if n['kind'] == 'Scope' and n['data']['resource'] == d['resource']]
            if entity['tenancy'] == 'SCOPED' and (not scopes or any(
                    not self.types.valid_value(self.index[s['actorTenant']['id']]['data']['type'], actor.get(s['actorTenant']['id'], ABSENT))
                    or not self.types.valid_value(self.index[s['resourceTenant']['id']]['data']['type'], resource.get(s['resourceTenant']['id'], ABSENT))
                    or actor[s['actorTenant']['id']] != resource[s['resourceTenant']['id']] for s in scopes)):
                raise ExecutionFailure('TENANT')
            operation_input = self.typed(d['input'], self.construct(sd['inputBindings'], context))
            before = copy.deepcopy(resource)
            runtime = {'OPERATION': operation_input, 'resource': before, 'post': resource, 'actor': actor}
            actor_owner = next((self.index[n['data']['actor']['id']]['data']['subject'] for n in self.index.values() if n['kind'] == 'Permission' and n['data']['action']['id'] == op['id']), None)
            type_context = {'resource': d['resource'], 'post': d['resource'], 'OPERATION': d['input'], 'actor': actor_owner}
            runtime['infer'] = lambda expr: FlowTypes(self.index, lambda *args: None).expression(op, expr, type_context, ())
            if op['kind'] == 'Query':
                if self.value(d['predicate'], runtime) is not True:
                    raise ExecutionFailure('QUERY_NO_RESULT')
                results[step['id']] = self.typed(d['result']['definition'], self.construct(d['projection'], runtime))
                continue
            transitions = [n for n in self.index.values() if n['kind'] == 'Transition' and n['data']['command']['id'] == op['id']]
            selected = []
            for transition in transitions:
                td = transition['data']
                state = resource.get('@state:' + td['machine']['id'])
                if state == td['from']['id'] and self.value(td['guard'], runtime) is True:
                    selected.append(transition)
            if transitions and len(selected) != 1:
                raise ExecutionFailure('WORKFLOW')
            for effect in d['assignments']:
                value = self.value(effect['value'], runtime)
                if not self.types.valid_value(self.index[effect['field']['id']]['data']['type'], value):
                    raise ExecutionFailure('ASSIGNMENT_TYPE')
                resource[effect['field']['id']] = copy.deepcopy(value)
            for inv in self.index.values():
                if inv['kind'] == 'Invariant' and inv['data']['resource'] == d['resource']:
                    if self.value(inv['data']['predicate'], {**runtime, 'resource': resource}) is not True:
                        raise ExecutionFailure('INVARIANT')
            emissions = {e['event']['id']: e for e in d['eventBindings']}
            for transition in selected:
                td = transition['data']
                resource['@state:' + td['machine']['id']] = td['to']['id']
                emissions.update({e['event']['id']: e for e in td['eventBindings']})
            results[step['id']] = self.typed(d['output'], self.construct(d['outputBindings'], runtime))
            for event_id, binding in sorted(emissions.items()):
                events.append({'event': binding['event'], 'resource': key, 'payload': self.construct(binding['payload'], runtime)})
            if after_step is not None:
                after_step(step['id'])  # Trusted test fault boundary, not a Canonical expression.
        output = self.typed(uc['data']['output'], self.construct(uc['data']['outputBindings'], context))
        return {'resources': committed, 'output': output, 'events': events}
