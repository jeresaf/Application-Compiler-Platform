"""Separate Authoring 0.3 / Canonical 0.2 schemas; historical builders are untouched."""
import copy
import json
from phase1_contract import ROOT, record, link, links, array, use
from canonical_contract import build_schema as old_canonical
from change_contract import build_schema as old_change

EXTENSIONS = {
    'Command': {'input': link('ValueObject'), 'output': link('ValueObject'),
                'writeFields': links('Field'),
                'assignments': array(record({'resource': link('Entity'), 'field': link('Field'), 'value': use('expression')}), unique=False),
                'outputBindings': use('bindings'), 'eventBindings': use('emissions')},
    'Query': {'input': link('ValueObject'), 'predicate': use('expression')},
    'ExecutionStep': {'resource': use('expression'), 'inputBindings': use('bindings')},
    'UseCase': {'outputBindings': use('bindings')},
    'Transition': {'eventBindings': use('emissions')},
    'Job': {'inputBindings': use('bindings')},
    'Filter': {'inputField': link('Field')},
}


def authoring_schema():
    schema = json.loads((ROOT / 'contracts/phase1.schema.json').read_text())
    schema['$id'] = 'urn:acp:authoring:0.3.0'
    schema['title'] = 'ACP Authoring 0.3.0 explicit execution and dataflow'
    schema['properties']['modelVersion'] = {'const': '0.3.0'}
    defs = schema['$defs']
    defs['bindings'] = array(record({'field': link('Field'), 'value': use('expression')}))
    defs['emissions'] = array(record({'event': link('Event'), 'payload': use('bindings')}))
    defs['expression']['oneOf'] += [
        record({'tag': {'const': 'input'}, 'scope': {'enum': ['OPERATION', 'USE_CASE']}, 'field': link('Field')}),
        record({'tag': {'const': 'stepResult'}, 'step': link('ExecutionStep'), 'field': link('Field')}),
        record({'tag': {'const': 'postField'}, 'field': link('Field')}),
        record({'tag': {'const': 'textContains'}, 'value': use('expression'), 'pattern': use('expression')}),
    ]
    for branch in defs['node']['allOf']:
        kind = branch['if']['properties']['kind']['const']
        if kind not in EXTENSIONS:
            continue
        name = branch['then']['properties']['data']['$ref'].split('/')[-1]
        for key in {kind, name}:
            defs[key]['required'] += list(EXTENSIONS[kind])
            defs[key]['properties'].update(copy.deepcopy(EXTENSIONS[kind]))
    defs['ExecutionStep']['properties']['compensationBindings'] = use('bindings')
    return schema


def canonical_schema():
    schema = old_canonical()
    schema['$id'] = 'urn:acp:canonical:0.2.0'
    schema['title'] = 'ACP Canonical Application 0.2.0 / semantic model 0.3.0'
    content = schema['$defs']['content']
    defs = copy.deepcopy(authoring_schema()['$defs'])
    defs['content'] = content
    schema['$defs'] = defs
    defs['node']['properties']['lifecycle'] = {'enum': ['APPROVED', 'DEPRECATED']}
    defs['node']['properties'].pop('supersededBy')
    content['properties']['schemaVersion'] = {'const': '0.2.0'}
    content['properties']['semanticModelVersion'] = {'const': '0.3.0'}
    content['properties']['requiredFeatures'] = {'const': ['acp.execution.0.3']}
    return schema


def change_schema():
    schema = old_change()
    schema['$id'] = 'urn:acp:change:0.2.0'
    schema['properties']['changeVersion'] = {'const': '0.2.0'}
    schema['properties']['canonicalVersion'] = {'const': '0.2.0'}
    schema['required'].append('canonicalVersion')
    # Keep history proposal definitions; substitute the successor semantic shapes.
    schema['$defs'].update(canonical_schema()['$defs'])
    return schema


if __name__ == '__main__':
    for name, builder in [('authoring-0.3', authoring_schema), ('canonical-0.2', canonical_schema), ('change-0.2', change_schema)]:
        (ROOT / ('contracts/' + name + '.schema.json')).write_text(json.dumps(builder(), indent=2) + '\n')
