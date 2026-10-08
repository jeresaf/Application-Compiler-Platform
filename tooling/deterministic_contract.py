"""PROPOSED Authoring 0.4 / Canonical 0.3 / ChangeSet 0.3, never approval."""
import copy
import json
from execution_contract import authoring_schema as previous_authoring, canonical_schema as previous_canonical, change_schema as previous_change
from phase1_contract import ROOT, record, link, links, array, use, enum

FEATURE = 'acp.deterministic-execution.0.4'
RATE = {'kind': 'TOKEN_BUCKET', 'refill': 'CONTINUOUS_RATIONAL', 'initial': 'FULL',
        'charge': 'AUTHORIZED_INVOCATION', 'replay': 'CHARGE', 'clock': 'NONDECREASING'}
EXTENSIONS = {
    'Query': {'orderBy': array(record({'field': link('Field'), 'direction': enum('ASC','DESC')},
                                   {'nulls': enum('FIRST','LAST'), 'absent': enum('FIRST','LAST')}))},
    'DataLifecycle': {'anchor': {'oneOf': [record({'kind': enum('CREATED_COMMIT')}),
        record({'kind': enum('CLOSED_COMMIT'), 'machine': link('StateMachine'), 'states': links('State',minimum=1),
                'instant': {'const':'COMMITTED_ENTRY'}, 'terminal': {'const':True}})]}},
    'DeletionPolicy': {'anonymizationEffects': array({'oneOf': [
        record({'field': link('Field'), 'action': enum('REMOVE','NULL')}),
        record({'field': link('Field'), 'action': enum('REPLACE'),
                'replacement': record({'type': use('semanticType'), 'value': {}})})]})},
    'RatePolicy': {'algorithm': {'const': RATE}},
    'RetryPolicy': {'delayBasis': {'const':'AFTER_FAILURE_COMPLETION'}, 'jitter': {'const':'NONE'},
                    'attemptCounting': {'const':'INCLUDING_INITIAL'}},
}


def authoring_schema():
    s = copy.deepcopy(previous_authoring())
    s.update({'$id':'urn:acp:authoring:0.4.0', 'title':'PROPOSED ACP Authoring 0.4 deterministic execution'})
    s['properties']['modelVersion'] = {'const':'0.4.0'}
    for branch in s['$defs']['node']['allOf']:
        kind = branch['if']['properties']['kind']['const']
        if kind in EXTENSIONS:
            alias = branch['then']['properties']['data']['$ref'].split('/')[-1]
            for key in {kind, alias}:
                s['$defs'][key]['required'] += list(EXTENSIONS[kind])
                s['$defs'][key]['properties'].update(copy.deepcopy(EXTENSIONS[kind]))
    interval = s['$defs']['Schedule']['oneOf'][0]
    interval['required'].append('anchorInstant')
    interval['properties']['anchorInstant'] = use('text')
    return s


def canonical_schema():
    s = copy.deepcopy(previous_canonical())
    content = s['$defs']['content']
    s['$defs'] = copy.deepcopy(authoring_schema()['$defs'])
    s['$defs']['content'] = content
    s['$defs']['node']['properties']['lifecycle'] = {'enum':['APPROVED','DEPRECATED']}
    s['$defs']['node']['properties'].pop('supersededBy')
    content['properties']['schemaVersion'] = {'const':'0.3.0'}
    content['properties']['semanticModelVersion'] = {'const':'0.4.0'}
    content['properties']['requiredFeatures'] = {'const':[FEATURE]}
    s.update({'$id':'urn:acp:canonical:0.3.0', 'title':'PROPOSED Canonical Application 0.3 deterministic execution'})
    return s


def change_schema():
    s = copy.deepcopy(previous_change())
    s.update({'$id':'urn:acp:change:0.3.0','title':'PROPOSED ChangeSet 0.3'})
    s['properties']['changeVersion'] = {'const':'0.3.0'}
    s['properties']['canonicalVersion'] = {'const':'0.3.0'}
    s['$defs'].update(canonical_schema()['$defs'])
    return s


if __name__ == '__main__':
    for name, build in [('authoring-0.4',authoring_schema),('canonical-0.3',canonical_schema),('change-0.3',change_schema)]:
        (ROOT / ('contracts/' + name + '.schema.json')).write_text(json.dumps(build(),indent=2)+'\n')
