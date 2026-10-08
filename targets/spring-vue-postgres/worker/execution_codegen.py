"""Compile explicit Canonical 0.2 effects to typed Java source, not a runtime DSL.

Unsupported expression/coordination forms reject negotiation before generation.
No IDs or names select application effects.
"""
from model import CapabilityError, identifier
from typed_contracts import Contracts, member, name, quoted


class ExecutionGenerator:
    def __init__(self, nodes):
        self.c = Contracts(nodes)
        self.nodes = self.c.nodes

    def field(self, source, id):
        f = self.nodes[id]
        value = source + '.' + member(id) + '()'
        return value + '.value()' if f['data']['optional'] else value

    def expression(self, e, *, pre='pre', staged='staged', operation='input', usecase='invocation'):
        rec = lambda x: self.expression(x, pre=pre, staged=staged, operation=operation, usecase=usecase)
        tag = e['tag']
        if tag == 'input':
            return self.field(operation if e['scope'] == 'OPERATION' else usecase, e['field']['id'])
        if tag == 'stepResult':
            return self.field(member(e['step']['id']) + '.output()', e['field']['id'])
        if tag == 'field':
            if e['binding'] == 'actor':
                raise CapabilityError('COMPILED_ACTOR_EXPRESSION_REQUIRED')
            return self.field(pre, e['ref']['id'])
        if tag == 'postField':
            return self.field(staged, e['field']['id'])
        if tag == 'parameter':
            d = self.nodes[e['ref']['id']]['data']
            return self.literal(d['type'], d['value'])
        if tag == 'literal':
            return self.literal(e['type'], e['value'])
        if tag == 'textContains':
            return '(' + rec(e['value']) + '.contains(' + rec(e['pattern']) + '))'
        if tag == 'binary':
            l, r = rec(e['left']), rec(e['right'])
            op = e['op']
            if op in ('eq', 'identityEq'):
                return f'java.util.Objects.equals({l}, {r})'
            if op in ('and', 'or'):
                return f'(Boolean.TRUE.equals({l}) {"&&" if op == "and" else "||"} Boolean.TRUE.equals({r}))'
            if op in ('gt', 'gte', 'lt', 'lte'):
                symbol = {'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<='}[op]
                return f'(ExecutionStore.number({l}).compareTo(ExecutionStore.number({r})) {symbol} 0)'
        if tag == 'coalesce':
            return f'({rec(e["value"])} != null ? {rec(e["value"])} : {rec(e["fallback"])})'
        if tag == 'present':
            if e['binding'] != 'resource':
                raise CapabilityError('COMPILED_ACTOR_EXPRESSION_REQUIRED')
            f = self.nodes[e['ref']['id']]
            return pre + '.' + member(f['id']) + '().present()' if f['data']['optional'] else 'true'
        raise CapabilityError('COMPILED_EXPRESSION_REQUIRED:' + tag)

    def literal(self, t, value):
        if t['kind'] == 'Nullable':
            return 'null' if value is None else self.literal(t['item'], value)
        typ = self.c.type(t)
        if t['kind'] in ('String',):
            return quoted(value)
        if t['kind'] in ('Identifier', 'Named'):
            return f'new {typ}({quoted(value)})'
        if t['kind'] in ('Money', 'Decimal', 'Percentage'):
            return f'new {typ}(new java.math.BigDecimal({quoted(value)}))'
        if t['kind'] == 'Boolean':
            return 'true' if value else 'false'
        if t['kind'] in ('Integer', 'Duration'):
            return str(value) + 'L'
        if t['kind'] in ('Date', 'Instant'):
            return f'{typ}.parse({quoted(value)})'
        raise CapabilityError('COMPILED_LITERAL_REQUIRED:' + t['kind'])

    def construct(self, owner, bindings, **context):
        return self.c.construct(owner, bindings, lambda e: self.expression(e, **context))

    def query_sql(self, e):
        """Parameterized scalar-preserving UTF-8 bytes, including U+0000."""
        tag = e['tag']
        if tag == 'field' and e['binding'] == 'resource':
            return identifier(e['ref']['id'], 'f'), []
        if tag == 'input' and e['scope'] == 'OPERATION':
            return '?', ['ExecutionStore.bytes(' + self.field('input', e['field']['id']) + ')']
        if tag == 'textContains':
            left, lp = self.query_sql(e['value']); right, rp = self.query_sql(e['pattern'])
            return '(position(' + right + ' IN ' + left + ') > 0)', rp + lp
        raise CapabilityError('SQL_PREDICATE_REQUIRED:' + tag)

    def validate(self):
        for n in self.nodes.values():
            d, k = n['data'], n['kind']
            if k == 'UseCase':
                steps = [self.nodes[r['id']]['data'] for r in d['steps']]
                if any(s['onFailure'] != 'STOP' for s in steps):
                    raise CapabilityError('COORDINATION_COMPENSATION_UNSUPPORTED:' + n['id'])
                txs = {s.get('transaction', {}).get('id') for s in steps}
                if len(steps) > 1 and (len(txs) != 1 or None in txs):
                    raise CapabilityError('COORDINATION_MULTI_COMMIT_UNSUPPORTED:' + n['id'])
                for s in steps:
                    self.expression(s['resource'])
                    for b in s['inputBindings']:
                        self.expression(b['value'])
                for b in d['outputBindings']:
                    self.expression(b['value'])
            elif k == 'Command':
                for key in ('assignments', 'outputBindings'):
                    for b in d[key]:
                        self.expression(b['value'])
                for b in d['eventBindings']:
                    for p in b['payload']:
                        self.expression(p['value'])
                for ref in d['invariants']:
                    self.expression(self.nodes[ref['id']]['data']['predicate'], pre='staged')
            elif k == 'Query':
                self.query_sql(d['predicate'])
                for b in d['projection']:
                    self.expression(b['value'])
            elif k == 'Transition':
                self.expression(d['guard'])
        self.c.source()  # Resolve every persisted/DTO field and refinement.
        self.controller()
        self.frontend()

    def row_reader(self, entity):
        args = []
        for f in self.c.fields(entity):
            d, key = f['data'], quoted(identifier(f['id'], 'f'))
            t = d['type']; typ = t['item'] if t['kind'] == 'Nullable' else t
            java = self.c.type(typ)
            if typ['kind'] in ('Identifier', 'Named'):
                value = f'new {java}(ExecutionStore.text(rs.getBytes({key})))'
            elif typ['kind'] in ('Money', 'Decimal', 'Percentage'):
                value = f'new {java}(rs.getBigDecimal({key}))'
            elif typ['kind'] == 'Value':
                value = f'{java}.read(store.json(ExecutionStore.text(rs.getBytes({key}))))'
            elif typ['kind'] == 'String':
                value = f'ExecutionStore.text(rs.getBytes({key}))'
            elif typ['kind'] in ('Boolean', 'Integer', 'Duration'):
                value = f'rs.getObject({key}, {java}.class)'
            elif typ['kind'] == 'Date':
                value = f'rs.getObject({key}, java.time.LocalDate.class)'
            elif typ['kind'] == 'Instant':
                value = f'rs.getTimestamp({key}).toInstant()'
            else:
                raise CapabilityError('ROW_TYPE_REQUIRED:' + typ['kind'])
            if t['kind'] == 'Nullable' or d['optional']:
                value = f'(rs.getObject({key}) == null ? null : {value})'
            if d['optional']:
                value = (f'(rs.getBoolean({quoted(identifier(f["id"], "present"))}) ? Slot.of({value}) : Slot.absent())' if t['kind'] == 'Nullable' else
                         f'(rs.getObject({key}) == null ? Slot.absent() : Slot.of({value}))')
            args.append(value)
        return f'(rs, rowIndex) -> new ExecutionStore.Row<>(new {name(entity)}(' + ','.join(args) + '), rs.getLong("acp_version"), rs.getString("acp_state"))'

    def semantic(self, entity, var):
        entries = ','.join(f'new Object[]{{{quoted(f["id"])}, {self.field(var, f["id"])}}}' for f in self.c.fields(entity))
        return 'ExecutionStore.semantic(' + entries + ')'

    def db_value(self, t, value):
        if t['kind'] == 'Nullable':
            return f'({value} == null ? null : {self.db_value(t["item"], value)})'
        if t['kind'] in ('Identifier', 'Named'):
            return 'ExecutionStore.bytes(' + value + '.value())'
        if t['kind'] in ('Money', 'Decimal', 'Percentage'):
            return value + '.value()'
        if t['kind'] == 'Value':
            return 'ExecutionStore.bytes(store.encode(' + value + '))'
        if t['kind'] == 'String':
            return 'ExecutionStore.bytes(' + value + ')'
        return value

    def command(self, n):
        d, id = n['data'], n['id']; entity = d['resource']['id']; e = self.nodes[entity]['data']
        inp, out = name(d['input']['id']), name(d['output']['id'])
        table = identifier(entity, 'e'); identity = identifier(e['identity'][0]['id'], 'f'); tenant = identifier(e['tenantField']['id'], 'f')
        transitions = sorted((t for t in self.nodes.values() if t['kind'] == 'Transition' and t['data']['command']['id'] == id), key=lambda n: n['id'])
        lines = [f'var row = store.lock({quoted(table)}, {quoted(identity)}, {quoted(tenant)}, resourceId.value(), jwt, {self.row_reader(entity)});',
                 'var pre = row.value(); var staged = pre;',
                 f'store.authorize({quoted(id)}, {self.semantic(entity, "pre")}, jwt);',
                 'if (row.version() != expectedVersion) throw new IllegalStateException("VERSION_CONFLICT");',
                 'String state = row.state();']
        if transitions:
            lines.append('boolean transitionFound = false;')
            for t in transitions:
                td = t['data']; machine = self.nodes[td['machine']['id']]['data']
                lines.append(f'if (!transitionFound && {quoted(td["from"]["id"])}.equals(state == null ? {quoted(machine["initial"]["id"])} : state) && Boolean.TRUE.equals({self.expression(td["guard"])})) {{ state={quoted(td["to"]["id"])}; transitionFound=true; }}')
            lines.append('if (!transitionFound) throw new IllegalStateException("TRANSITION_DENIED");')
        written = set()
        for a in d['assignments']:
            target = a['field']['id']; written.add(target)
            args = [self.expression(a['value']) if f['id'] == target else 'staged.' + member(f['id']) + '()' for f in self.c.fields(entity)]
            if self.nodes[target]['data']['optional']:
                args = ['Slot.of(' + self.expression(a['value']) + ')' if f['id'] == target else 'staged.' + member(f['id']) + '()' for f in self.c.fields(entity)]
            lines.append(f'staged = new {name(entity)}(' + ','.join(args) + ');')
        for inv in d['invariants']:
            expr = self.nodes[inv['id']]['data']['predicate']
            lines.append(f'if (!Boolean.TRUE.equals({self.expression(expr, pre="staged")})) throw new IllegalArgumentException("INVARIANT");')
        lines.append('var output = ' + self.construct(d['output']['id'], d['outputBindings']) + ';')
        setters, values = [], []
        for f in sorted(written):
            typ = self.nodes[f]['data']['type']
            setters.append(identifier(f, 'f') + '=?')
            values.append(self.db_value(typ, self.field('staged', f)))
            if self.nodes[f]['data']['optional'] and typ['kind'] == 'Nullable':
                setters.append(identifier(f, 'present') + '=?')
                values.append('staged.' + member(f) + '().present()')
        update = f'UPDATE {table} SET ' + ','.join([*setters, 'acp_state=?', 'acp_version=acp_version+1']) + f' WHERE {identity}=? AND {tenant}=? AND acp_version=?'
        lines.append(f'store.update({quoted(update)}, ' + ','.join([*values, 'state', 'ExecutionStore.bytes(resourceId.value())', 'ExecutionStore.bytes(jwt.getClaimAsString("tenant"))', 'row.version()']) + ');')
        lines.append(f'store.audit({quoted(id)}, resourceId.value(), jwt);')
        for b in d['eventBindings']:
            event = b['event']['id']; fields = [self.nodes[r['id']] for r in self.nodes[event]['data']['payload']]
            by = {p['field']['id']: p['value'] for p in b['payload']}
            payload = 'new ' + name(event) + '(' + ','.join(self.expression(by[f['id']]) for f in fields) + ')'
            lines.append(f'store.event({quoted(id)}, {quoted(event)}, resourceId.value(), row.version()+1, {payload}, jwt);')
        lines.append('return new ExecutionStore.Completion<>(output, resourceId.value(), row.version()+1, state);')
        return f'''@org.springframework.transaction.annotation.Transactional
    public ExecutionStore.Completion<{out}> {member(id)}({name(entity)}Id resourceId, long expectedVersion, {inp} input, org.springframework.security.oauth2.jwt.Jwt jwt) {{
        java.util.Objects.requireNonNull(input); java.util.Objects.requireNonNull(resourceId);
        {' '.join(lines)}
    }}'''

    def usecase(self, n):
        d = n['data']; inp, out = name(d['input']['id']), name(d['output']['id'])
        lines = ['String boundary = null;', 'long version = expectedVersion;']
        for ref in d['steps']:
            step = self.nodes[ref['id']]; s = step['data']; op = self.nodes[s['operation']['id']]
            resource = self.expression(s['resource'])
            lines += [f'var resource_{member(step["id"])} = {resource};',
                      f'var selected_{member(step["id"])} = {quoted(op["data"]["resource"]["id"] + ":")} + resource_{member(step["id"])}.value();',
                      f'if (boundary != null && !boundary.equals(selected_{member(step["id"])})) throw new IllegalArgumentException("TRANSACTION_RESOURCE");',
                      f'boundary = selected_{member(step["id"])};']
            constructed = self.construct(op['data']['input']['id'], s['inputBindings'])
            method = member(op['id']) + ('One' if op['kind'] == 'Query' else '')
            lines.append(f'var {member(step["id"])} = {method}(resource_{member(step["id"])}, version, {constructed}, jwt);')
            lines.append(f'version = {member(step["id"])}.version();')
        lines.append('var output = ' + self.construct(d['output']['id'], d['outputBindings']) + ';')
        last = member(d['steps'][-1]['id'])
        lines.append(f'return new ExecutionStore.Completion<>(output, {last}.resourceId(), version, {last}.state());')
        return f'''@org.springframework.transaction.annotation.Transactional
    public ExecutionStore.Completion<{out}> {member(n['id'])}(long expectedVersion, {inp} invocation, org.springframework.security.oauth2.jwt.Jwt jwt) {{
        java.util.Objects.requireNonNull(invocation); {' '.join(lines)}
    }}'''

    def query(self, n):
        d, id = n['data'], n['id']; entity = d['resource']['id']; e = self.nodes[entity]['data']
        inp, out = name(d['input']['id']), name(d['result']['definition']['id'])
        table = identifier(entity, 'e'); identity = identifier(e['identity'][0]['id'], 'f'); tenant = identifier(e['tenantField']['id'], 'f')
        predicate, params = self.query_sql(d['predicate'])
        projection = self.construct(d['result']['definition']['id'], d['projection'])
        # Ordering is not declared by the approved model. Do not invent it.
        # Full paginated admission remains blocked pending authoritative order.
        sql = f'SELECT * FROM {table} WHERE {tenant}=? AND {predicate} LIMIT ? OFFSET ?'
        return f'''
    @org.springframework.transaction.annotation.Transactional(readOnly=true)
    public java.util.List<ExecutionStore.Completion<{out}>> {member(id)}({inp} input, int offset, int limit, org.springframework.security.oauth2.jwt.Jwt jwt) {{
        java.util.Objects.requireNonNull(input);
        store.authenticate(jwt);
        if (offset<0 || limit<1 || limit>{d['maximumResults']}) throw new IllegalArgumentException("PAGINATION");
        var rows = store.query({quoted(sql)}, {self.row_reader(entity)}, ExecutionStore.bytes(jwt.getClaimAsString("tenant")), {', '.join(params)}, limit, offset);
        var result = new java.util.ArrayList<ExecutionStore.Completion<{out}>>();
        for (var row : rows) {{ var pre=row.value(); store.authorize({quoted(id)}, {self.semantic(entity, 'pre')}, jwt);
            result.add(new ExecutionStore.Completion<>({projection}, {self.field('pre', e['identity'][0]['id'])}.value(), row.version(), row.state())); }}
        return java.util.List.copyOf(result);
    }}
    @org.springframework.transaction.annotation.Transactional(readOnly=true)
    public ExecutionStore.Completion<{out}> {member(id)}One({name(entity)}Id resourceId, long expectedVersion, {inp} input, org.springframework.security.oauth2.jwt.Jwt jwt) {{
        var row=store.lock({quoted(table)}, {quoted(identity)}, {quoted(tenant)}, resourceId.value(), jwt, {self.row_reader(entity)});
        var pre=row.value(); store.authorize({quoted(id)}, {self.semantic(entity, 'pre')}, jwt);
        if (!Boolean.TRUE.equals({self.expression(d['predicate'])})) throw new IllegalArgumentException("QUERY_NO_RESULT");
        return new ExecutionStore.Completion<>({projection}, resourceId.value(), row.version(), row.state());
    }}'''

    def source(self):
        self.validate()
        methods = []
        for n in sorted(self.nodes.values(), key=lambda n: n['id']):
            if n['kind'] == 'Command': methods.append(self.command(n))
            elif n['kind'] == 'UseCase': methods.append(self.usecase(n))
            elif n['kind'] == 'Query': methods.append(self.query(n))
        # Contracts source runs last so all decimal types encountered above exist.
        return {'backend/src/main/java/acp/generated/Contracts.java': self.c.source(),
                'backend/src/main/java/acp/generated/TypedController.java': self.controller(),
                'frontend/src/task-contract.ts': self.frontend(),
                'backend/src/main/java/acp/generated/TypedTasks.java': '''package acp.generated;
import static acp.generated.Contracts.*;
import acp.infrastructure.ExecutionStore;
@org.springframework.stereotype.Service
public class TypedTasks {
    private final ExecutionStore store;
    public TypedTasks(ExecutionStore store) { this.store=store; }
''' + '\n'.join(methods) + '\n}\n'}

    def controller(self):
        methods = []
        for n in sorted(self.nodes.values(), key=lambda n: n['id']):
            d, id = n['data'], n['id']
            if n['kind'] not in {'Command', 'Query', 'UseCase'}:
                continue
            method = member(id); inp = name(d['input']['id'])
            path = '/api/' + identifier(id, 'op')
            if n['kind'] == 'Query':
                out = name(d['result']['definition']['id'])
                methods.append(f'''@PostMapping({quoted(path)})
    public java.util.List<ExecutionStore.Completion<{out}>> {method}(@RequestBody {inp} input, @RequestParam(defaultValue="0") int offset, @RequestParam(defaultValue="25") int limit, @AuthenticationPrincipal Jwt jwt) {{
        return tasks.{method}(input, offset, limit, jwt);
    }}''')
            else:
                out = name(d['output']['id'])
                resource = '' if n['kind'] == 'UseCase' else name(d['resource']['id']) + 'Id resourceId, '
                call = '' if n['kind'] == 'UseCase' else 'request.resourceId(), '
                request = name(id) + 'Request'
                methods.append(f'''public record {request}({resource}long expectedVersion, {inp} input) {{
        public {request} {{ java.util.Objects.requireNonNull(input); if (expectedVersion<0) throw new IllegalArgumentException("VERSION"); }}
    }}
    @PostMapping({quoted(path)})
    public ExecutionStore.Completion<{out}> {method}(@RequestBody {request} request, @AuthenticationPrincipal Jwt jwt) {{
        return tasks.{method}({call}request.expectedVersion(), request.input(), jwt);
    }}''')
        return '''package acp.generated;
import static acp.generated.Contracts.*;
import acp.infrastructure.ExecutionStore;
import org.springframework.web.bind.annotation.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
@RestController
public final class TypedController {
    private final TypedTasks tasks;
    public TypedController(TypedTasks tasks) { this.tasks=tasks; }
''' + '\n'.join(methods) + '\n}\n'

    def frontend(self):
        screens = [n for n in self.nodes.values() if n['kind'] == 'Screen']
        if len(screens) != 1:
            raise CapabilityError('TASK_SCREEN_CONSTRAINT')
        task = self.nodes[screens[0]['data']['task']['id']]
        fields = self.c.fields(task['data']['input']['id'])
        steps = [self.nodes[r['id']] for r in task['data']['steps']]
        resources = [s['data']['resource'] for s in steps]
        if not resources:
            raise CapabilityError('TASK_RESOURCE_CONTROL_CONSTRAINT')
        r = resources[0]
        if r['tag'] != 'input' or r['scope'] != 'USE_CASE':
            raise CapabilityError('TASK_RESOURCE_CONTROL_CONSTRAINT')
        resource_field = r['field']['id']
        query = next((n for n in self.nodes.values() if n['kind'] == 'Query'), None)
        if query is None:
            raise CapabilityError('TASK_QUERY_CONSTRAINT')
        if query['data']['result']['definition'] != task['data']['output']:
            raise CapabilityError('TASK_QUERY_OUTPUT_CONSTRAINT')
        filters = [n for n in self.nodes.values() if n['kind'] == 'Filter' and n['data']['query']['id'] == query['id']]
        if len(filters) != 1:
            raise CapabilityError('TASK_FILTER_CONSTRAINT')
        input_field = filters[0]['data']['inputField']['id']
        props, values = [], []
        for f in fields:
            if f['data']['type']['kind'] not in {'String', 'Identifier'} or f['data']['optional']:
                raise CapabilityError('TASK_FORM_INPUT_CONSTRAINT:' + f['id'])
            props.append(quoted(f['id']) + ': string;')
            values.append(quoted(f['id']) + ': ' + ('resourceId' if f['id'] == resource_field else 'required(values[' + quoted(f['id']) + '])'))
        output = self.c.fields(task['data']['output']['id'])
        if any(f['data']['type']['kind'] != 'String' or f['data']['optional'] for f in output):
            raise CapabilityError('TASK_OUTPUT_CONSTRAINT')
        return '''import { call } from './api';
export type TaskInput = { ''' + ' '.join(props) + ''' };
export type TaskOutput = { ''' + ' '.join(quoted(f['id']) + ': string;' for f in output) + ''' };
export type TaskCompletion = { output: TaskOutput; resourceId: string; version: number; state: string | null };
function required(value: string | undefined): string { if (value === undefined) throw new Error('Required task input.'); return value; }
export const resourceInputField = ''' + quoted(resource_field) + ''';
export function taskInput(values: Record<string,string>, resourceId: string): TaskInput { return { ''' + ','.join(values) + ''' }; }
export type QueryInput = { ''' + quoted(input_field) + ''': string };
export function queryInput(text: string): QueryInput { return { ''' + quoted(input_field) + ''': text }; }
export async function queryTasks(text: string): Promise<TaskCompletion[]> {
    return call<TaskCompletion[]>(''' + quoted('/api/' + identifier(query['id'], 'op')) + ''', queryInput(text));
}
export async function submitTask(values: Record<string,string>, resourceId: string, expectedVersion: number): Promise<TaskCompletion> {
    return call<TaskCompletion>(''' + quoted('/api/' + identifier(task['id'], 'op')) + ''', { expectedVersion, input: taskInput(values,resourceId) });
}
'''
