"""Pure PROPOSED FailureBinding executor; never target execution or approval.

Reuses the accepted typed-expression algebra. The bounded single-boundary STOP
algorithm below preserves ADR-0015 pre-state guards, staged writes and rollback.
Portable faults are injected trusted facts, not exception strings or IR scripts.
"""
import copy
from canonical_ir import validate_snapshot
from execution_reference import ReferenceExecution, ExecutionFailure, ABSENT
from type_semantics import Types
from deterministic_failures import envelope, FAULTS


class SemanticFailure(ExecutionFailure):
    def __init__(self, occurrence):
        super().__init__('DECLARED_SEMANTIC_FAILURE')
        self.occurrence=occurrence


class FailureReferenceExecution(ReferenceExecution):
    def __init__(self,snapshot):
        validate_snapshot(snapshot)
        if snapshot['content']['schemaVersion']!='0.3.0':raise ValueError('Proposed Canonical 0.3 required')
        self.index={n['id']:copy.deepcopy(n) for n in snapshot['content']['nodes']}
        self.types=Types(self.index,lambda *a:None)

    def occurrence(self,op,binding,index,correlation):
        # Provenance is private reference evidence, never a client retry claim.
        raise SemanticFailure({**envelope(self.index,op,binding['failure'],correlation),
            'origin':'EXACT_FAILURE_BINDING','bindingIndex':index})

    def infrastructure(self,op,fault,correlation):
        if fault is None:return
        if fault not in FAULTS:raise ExecutionFailure('INTERNAL')
        for i,b in enumerate(op['data']['failureBindings']):
            if b['trigger']=={'kind':'INFRASTRUCTURE_CLASS','faultClass':fault}:
                self.occurrence(op,b,i,correlation)
        raise ExecutionFailure('INTERNAL')

    def stage(self,op,stage,runtime,selected,correlation):
        for i,b in enumerate(op['data']['failureBindings']):
            if b['stage']!=stage:continue
            tr=b['trigger'];kind=tr['kind'];matched=False
            if kind=='PREDICATE':matched=self.value(tr['condition'],runtime) is True
            elif kind=='WORKFLOW_NO_APPLICABLE_TRANSITION':
                matched=not any(t['data']['machine']==tr['machine'] for t in selected)
            elif kind=='INVARIANT_FAILURE':
                inv=self.index[tr['invariant']['id']]
                matched=self.value(inv['data']['predicate'],{**runtime,'resource':runtime['post']}) is not True
            if matched:self.occurrence(op,b,i,correlation)

    def execute(self, use_case, invocation, resources, *, actor=None, authorize=None, after_step=None, faults=None, correlation="reference-correlation"):
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
            self.infrastructure(op, (faults or {}).get(op['id']), correlation)
            transitions = [n for n in self.index.values() if n['kind'] == 'Transition' and n['data']['command']['id'] == op['id']]
            for transition in transitions:
                machine=transition['data']['machine']['id']
                state=self.index.get(resource.get('@state:'+machine))
                if state is None or state['kind']!='State' or state['data']['machine']!=transition['data']['machine']:
                    raise ExecutionFailure('INTERNAL_STATE')
            selected = []
            for transition in transitions:
                td = transition['data']
                state = resource.get('@state:' + td['machine']['id'])
                if state == td['from']['id'] and self.value(td['guard'], runtime) is True:
                    selected.append(transition)
            self.stage(op, 'PRE_STATE', runtime, selected, correlation)
            if transitions and len(selected) != 1:
                raise ExecutionFailure('WORKFLOW')
            for effect in d['assignments']:
                value = self.value(effect['value'], runtime)
                if not self.types.valid_value(self.index[effect['field']['id']]['data']['type'], value):
                    raise ExecutionFailure('ASSIGNMENT_TYPE')
                resource[effect['field']['id']] = copy.deepcopy(value)
            self.stage(op, 'POST_ASSIGNMENT', runtime, selected, correlation)
            self.stage(op, 'INVARIANT', runtime, selected, correlation)
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
            ordered_ids = [e['event']['id'] for e in d['eventBindings']]
            # Shared transition constructions are identical under ADR-0015.
            # This reference subset rejects additional transition-only emissions
            # rather than inventing a merge order beyond the declared operation.
            if set(emissions) != set(ordered_ids):
                raise ExecutionFailure('TRANSITION_ONLY_EMISSION_REFERENCE_SUBSET')
            for event_id in ordered_ids:
                binding = emissions[event_id]
                events.append({'event': binding['event'], 'resource': key, 'payload': self.construct(binding['payload'], runtime)})
            if after_step is not None:
                after_step(step['id'])  # Trusted test fault boundary, not a Canonical expression.
        output = self.typed(uc['data']['output'], self.construct(uc['data']['outputBindings'], context))
        return {'resources': committed, 'output': output, 'events': events}
