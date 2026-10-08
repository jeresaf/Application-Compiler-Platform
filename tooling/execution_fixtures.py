"""AI-proposed reference semantics, explicitly human-approved on 2026-10-08.

Proposal origins/bytes remain unchanged. Fresh approval is recorded separately
by execution_approval; fixture lifecycle markers alone never confer authority.
"""
import copy
import json
from pathlib import Path
from canonical_json import digest, PROFILE
from canonical_ir import normalize_candidate
from canonical_fixtures import synthetic_approved, byte_vectors
from change_fixtures import change, migration, revise
from changes import prepare, index
from reference_models import node
from validate import ROOT

DEST = ROOT / 'test-corpus/execution-v03'


def evolution(domain, base_head=None):
    old = json.loads((ROOT / ('test-corpus/canonical/' + domain + '.json')).read_text())
    original = index(old)
    root = 'ENT-PAYMENT' if domain == 'payment' else 'CASE'
    r = lambda id: {'id': id, 'revision': original.get(id, {}).get('revision', 1)}
    inp = lambda scope, field: {'tag': 'input', 'scope': scope, 'field': r(field)}
    post = lambda field: {'tag': 'postField', 'field': r(field)}
    bind = lambda field, value: {'field': r(field), 'value': value}
    result = lambda step: {'tag': 'stepResult', 'step': r(step), 'field': r('RESULT-TEXT')}
    commands = ['CMD-RECORD'] if domain == 'payment' else ['CMD-REVIEW', 'CMD-APPROVE', 'CMD-ARCHIVE']
    operations = []
    requirement = next(n['id'] for n in original.values() if n['kind'] == 'Requirement')
    def add(id, kind, data):
        n = node(id, kind, data, requirement)
        n['lifecycle'] = 'APPROVED'  # Structural fixture witness only.
        n['origins'] = [{'source': 'fixture:execution-v03-proposal', 'locator': id,
                         'actor': 'assistant:fixture-draft', 'actorType': 'AI'}]
        n['basis'].append(r('DEC-EXECUTION-V03')) if id != 'DEC-EXECUTION-V03' else None
        operations.append({'op': 'ADD', 'node': n})
    add('DEC-EXECUTION-V03', 'Decision', {
        'statement': 'Proposed fixture behavior: explicit root selection; summary-only assignments; prior-step text flow; explicit output and event payloads.',
        'strength': 'REQUIRED', 'rationale': 'New test semantics, authored explicitly for review; no inferred migration and no real approval.',
        'alternatives': ['Keep old incomplete operation behavior and block execution admission']})
    def field(id, owner, typ, optional=False):
        add(id, 'Field', {'owner': r(owner), 'type': typ, 'optional': optional,
                          'classification': 'INTERNAL', 'classificationRef': r('CLASS-INTERNAL')})
    add('OPERATION-INPUT', 'ValueObject', {'equality': 'STRUCTURAL'})
    add('OPERATION-RESULT', 'ValueObject', {'equality': 'STRUCTURAL'})
    add('QUERY-INPUT', 'ValueObject', {'equality': 'STRUCTURAL'})
    field('OPERATION-TEXT', 'OPERATION-INPUT', {'kind': 'String'})
    field('RESULT-TEXT', 'OPERATION-RESULT', {'kind': 'String'})
    field('QUERY-TEXT', 'QUERY-INPUT', {'kind': 'String'})
    field('INPUT-TASK-RESOURCE', 'INPUT-TASK', {'kind': 'Identifier', 'entity': r(root)})
    add('CONTROL-TASK-RESOURCE', 'InputControl', {'form': r('FORM-TASK'), 'field': r('INPUT-TASK-RESOURCE'),
        'label': 'Resource identity', 'errorMessage': 'Select the authorized resource identity.', 'required': True, 'purpose': 'TEXT'})
    for n in original.values():
        d = copy.deepcopy(n['data'])
        kind = n['kind']
        if kind == 'Command':
            d.update(input=r('OPERATION-INPUT'), output=r('OPERATION-RESULT'), writeFields=[r('FLD-TASK-SUMMARY')],
                     assignments=[{'resource': d['resource'], 'field': r('FLD-TASK-SUMMARY'), 'value': inp('OPERATION', 'OPERATION-TEXT')}],
                     outputBindings=[bind('RESULT-TEXT', post('FLD-TASK-SUMMARY'))])
            d['eventBindings'] = [{'event': event, 'payload': [bind(f['id'], post(f['id'])) for f in original[event['id']]['data']['payload']]} for event in d['emits']]
        elif kind == 'Query':
            d.update(input=r('QUERY-INPUT'), predicate={'tag': 'textContains',
                'value': {'tag': 'field', 'binding': 'resource', 'ref': r('FLD-TASK-SUMMARY')}, 'pattern': inp('OPERATION', 'QUERY-TEXT')})
        elif kind == 'Filter':
            d['inputField'] = r('QUERY-TEXT')
        elif kind == 'ExecutionStep':
            position = commands.index(d['operation']['id'])
            value = inp('USE_CASE', 'INPUT-TASK-TEXT') if position == 0 else result('STEP-' + commands[position - 1])
            d.update(resource=inp('USE_CASE', 'INPUT-TASK-RESOURCE'), inputBindings=[bind('OPERATION-TEXT', value)])
        elif kind == 'UseCase':
            d['outputBindings'] = [bind('OUTPUT-TASK-TEXT', result('STEP-' + commands[-1]))]
        elif kind == 'Transition':
            d['eventBindings'] = [{'event': event, 'payload': [bind(f['id'], post(f['id'])) for f in original[event['id']]['data']['payload']]} for event in d['effects']]
        elif kind == 'Job':
            d['inputBindings'] = [bind('INPUT-TASK-TEXT', {'tag': 'literal', 'type': {'kind': 'String'}, 'value': 'Explicit scheduled fixture text'}),
                                  bind('INPUT-TASK-RESOURCE', {'tag': 'literal', 'type': {'kind': 'Identifier', 'entity': r(root)}, 'value': 'fixture-resource'})]
        elif kind == 'Form' and n['id'] == 'FORM-TASK':
            d['controls'].append(r('CONTROL-TASK-RESOURCE'))
        elif kind == 'AccessibilityRequirement':
            d['subjects'].append(r('CONTROL-TASK-RESOURCE'))
        elif kind == 'EvidenceRequirement' and any(a['kind'] == 'AccessibilityRequirement' and a['data']['evidence']['id'] == n['id'] for a in original.values()):
            d['subjects'].append(r('CONTROL-TASK-RESOURCE'))
        else:
            continue
        new = revise(old, n['id'], data=d, basis=[*n['basis'], r('DEC-EXECUTION-V03')])
        new['node']['origins'].append({'source': 'fixture:execution-v03-proposal', 'locator': n['id'], 'actor': 'assistant:fixture-draft', 'actorType': 'AI'})
        operations.append(new)
    head = base_head or {'sequence': 0, 'digest': old['contentDigest'], 'journalDigest': 'sha256:' + '0' * 64}
    proposal = change('CHANGE-EXECUTION-V03', head, operations, migration_plan=migration())
    proposal.update(changeVersion='0.2.0', canonicalVersion='0.2.0', intent='Explicit proposed fixture business effects; requires independent review and exact new approval')
    return old, proposal


def model(domain):
    old, proposal = evolution(domain)
    candidate = prepare(old, proposal)['candidate']
    c = candidate['content']
    return synthetic_approved({'modelVersion': '0.3.0', 'applicationId': c['applicationId'],
                               'snapshotId': 'FIXTURE-EXECUTION-V03', 'nodes': c['nodes'], 'issues': c['issues'], 'approvals': []})


def main():
    DEST.mkdir(exist_ok=True)
    manifest = {'profile': PROFILE, 'status': 'APPROVED_REFERENCE_SEMANTICS', 'examples': [], 'approval': 'human-approval.json'}
    for domain in ('payment', 'case-management'):
        old, proposal = evolution(domain)
        plan = prepare(old, proposal)
        authoring = model(domain)
        snapshot = normalize_candidate(authoring)
        for suffix, value in [('authoring', authoring), ('canonical', snapshot), ('change', proposal), ('plan', plan)]:
            (DEST / (domain + '-' + suffix + '.json')).write_text(json.dumps(value, indent=2) + '\n')
        manifest['examples'].append({'file': domain + '-canonical.json', 'contentDigest': snapshot['contentDigest'],
                                     'sourceDigest': digest(authoring, 'authoring'), 'historicalDigest': old['contentDigest'], 'planDigest': plan['planDigest']})
    (DEST / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (DEST / 'byte-vectors.json').write_text(json.dumps(byte_vectors(), indent=2) + '\n')


if __name__ == '__main__':
    main()
