"""Canonical Application 0.2; existing canonical byte profile, new semantic contract."""
import copy
from jsonschema import Draft202012Validator
from referencing import Registry
from canonical_json import PROFILE, digest
from canonical_ir import CanonicalError, _check_input, _literal, _threshold, ordered, _normalize_issues
from execution_contract import canonical_schema
from execution_model import validate_execution

SHAPES = Draft202012Validator(canonical_schema(), registry=Registry())


def data(value, index, kind, path=()):
    from canonical_ir import ORDERED_REFS, ORDERED_ARRAYS, SET_ARRAYS, MAP_ARRAYS
    if isinstance(value, dict):
        if value.get('tag') == 'literal' or set(value) == {'type', 'value'}:
            return {**copy.deepcopy(value), 'value': _literal(value['type'], value['value'], index)}
        return {k: data(v, index, kind, path + (k,)) for k, v in value.items()}
    if isinstance(value, list):
        items = [data(v, index, kind, path + (i,)) for i, v in enumerate(value)]
        key = (kind, path[0]) if len(path) == 1 else None
        if key in ORDERED_REFS | ORDERED_ARRAYS or path == ('assignments',):
            return items
        if key in SET_ARRAYS | MAP_ARRAYS or (path and path[-1] in {'inputBindings', 'outputBindings', 'compensationBindings', 'eventBindings', 'payload', 'writeFields'}) or all(isinstance(v, dict) and set(v) == {'id', 'revision'} for v in value):
            return ordered(items)
        raise CanonicalError('NORMAL', 'Array has no declared successor ordering policy.')
    return copy.deepcopy(value)


def nodes_normal(nodes):
    index = {n['id']: n for n in nodes}
    result = []
    for source in nodes:
        n = copy.deepcopy(source)
        n['basis'], n['origins'] = ordered(n['basis']), ordered(n['origins'])
        n['data'] = data(n['data'], index, n['kind'])
        if n['kind'] == 'TypeDefinition' and n['data']['refinement']['kind'] == 'RANGE':
            for k in ('min', 'max'):
                n['data']['refinement'][k] = _literal(source['data']['base'], source['data']['refinement'][k], index)
        if n['kind'] in {'PerformanceRequirement', 'ReliabilityRequirement'}:
            n['data']['threshold'] = _threshold(source['data']['threshold'])
        result.append(n)
    return sorted(result, key=lambda n: n['id'])


def normalize(authoring):
    _check_input(authoring)
    if validate_execution(authoring, 'compile'):
        raise CanonicalError('SEMANTIC', 'Authoring 0.3 fails execution/dataflow validation.')
    content = {'irKind': 'CanonicalApplication', 'schemaVersion': '0.2.0', 'semanticModelVersion': '0.3.0',
               'canonicalProfile': PROFILE, 'applicationId': authoring['applicationId'],
               'requiredFeatures': ['acp.execution.0.3'], 'nodes': nodes_normal(authoring['nodes']),
               'issues': _normalize_issues(authoring['issues'])}
    return {'content': content, 'contentDigest': digest(content, 'canonical')}


def validate(snapshot):
    _check_input(snapshot)
    if not SHAPES.is_valid(snapshot):
        raise CanonicalError('SHAPE', 'Canonical 0.2 violates its closed exact-version schema.')
    c = snapshot['content']
    authoring = {'modelVersion': '0.3.0', 'applicationId': c['applicationId'], 'snapshotId': 'STRUCTURAL-ONLY',
                 'nodes': c['nodes'], 'issues': c['issues'], 'approvals': [
                     {'subject': {'id': n['id'], 'revision': n['revision']}, 'reviewer': 'structural-only', 'evidence': 'not-authority'} for n in c['nodes']]}
    candidate = normalize(authoring)
    if candidate != snapshot:
        raise CanonicalError('NORMAL', 'Canonical successor content or digest is not normalized.')


def migration_review(source):
    """No guessed effects: identify all operation/invocation decisions to author."""
    from validate import validate as historical_validate
    if source.get('modelVersion') != '0.2.0' or historical_validate(source, 'compile'):
        raise CanonicalError('SEMANTIC', 'Migration source must be valid Authoring 0.2.')
    blockers = [{'subject': {'id': n['id'], 'revision': n['revision']}, 'code': 'ACP-FLOW-REVIEW-REQUIRED',
                 'missing': sorted(__import__('execution_contract').EXTENSIONS[n['kind']])}
                for n in source['nodes'] if n['kind'] in __import__('execution_contract').EXTENSIONS]
    if blockers:
        return {'sourceDigest': digest(source, 'authoring'), 'targetModelVersion': '0.3.0',
                'status': 'REVIEW_REQUIRED', 'blockers': sorted(blockers, key=lambda b: b['subject']['id']), 'candidate': None}
    candidate = copy.deepcopy(source)
    candidate['modelVersion'] = '0.3.0'
    candidate['approvals'] = []
    return {'sourceDigest': digest(source, 'authoring'), 'targetModelVersion': '0.3.0',
            'status': 'REQUIRES_NEW_APPROVAL', 'blockers': [], 'candidate': candidate}
