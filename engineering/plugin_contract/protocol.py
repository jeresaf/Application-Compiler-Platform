"""Data validation for a proposed plugin port. This module has no launch or publication API."""

import hashlib
import re

from engineering.evidence_admission.encoding import MAX_BYTES, parse_canonical, payload_digest

PROTOCOL = 'acp-plugin-foundation/1'
HOSTILE_EXECUTION_ENABLED = False
IDENTITY_FIELDS = {
    'plugin', 'sourceDigest', 'dependencyDigest', 'compilerAPI', 'protocol',
    'capabilities', 'target', 'profile', 'limits', 'provenanceDigest',
}
LIMITS = {'memoryBytes': 536870912, 'cpuSeconds': 20, 'wallSeconds': 30, 'tasks': 8}
DIGEST_FIELDS = ('sourceDigest', 'dependencyDigest', 'provenanceDigest')


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def is_digest(value):
    return type(value) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', value) is not None


def closed(value, fields, reason):
    require(type(value) is dict and set(value) == fields, reason)


def validate_identity(raw, *, expected, source, dependencies, provenance,
                      compiler_api, profiles, capabilities, target):
    """Check a host-selected exact descriptor. Success establishes identity only."""
    value = parse_canonical(raw)
    closed(value, IDENTITY_FIELDS, 'PLUGIN_IDENTITY_FIELDS')
    require(type(expected) is bytes and raw == expected, 'UNKNOWN_OR_CHANGED_PLUGIN')
    for key in ('plugin', 'compilerAPI', 'target', 'profile'):
        require(type(value[key]) is str and bool(value[key]), 'PLUGIN_IDENTIFIER')
    for key, content in zip(DIGEST_FIELDS, (source, dependencies, provenance), strict=True):
        require(type(content) is bytes and bool(content) and is_digest(value[key])
                and digest(content) == value[key], 'PLUGIN_INPUT_IDENTITY')
    require(value['protocol'] == PROTOCOL and value['compilerAPI'] == compiler_api
            and value['target'] == target and value['profile'] in profiles, 'PLUGIN_COMPATIBILITY')
    declared = value['capabilities']
    require(type(declared) is list and all(type(c) is str for c in declared)
            and declared == sorted(set(declared)) and set(declared) <= capabilities,
            'PLUGIN_CAPABILITIES')
    limits = value['limits']
    closed(limits, set(LIMITS), 'PLUGIN_LIMIT_FIELDS')
    require(all(type(limits[k]) is int and 0 < limits[k] <= cap for k, cap in LIMITS.items()),
            'PLUGIN_LIMITS')
    return value


def frame(data):
    require(type(data) is bytes and 0 < len(data) <= MAX_BYTES, 'PLUGIN_FRAME_SIZE')
    return len(data).to_bytes(4, 'big') + data


def decode(raw):
    require(type(raw) is bytes and 4 < len(raw) <= MAX_BYTES + 4, 'PLUGIN_FRAME_SIZE')
    require(int.from_bytes(raw[:4], 'big') == len(raw) - 4, 'PLUGIN_FRAME_LENGTH')
    return parse_canonical(raw[4:])


def validate_request(raw, *, identity, canonical_digest, target_ir_digest):
    value = decode(raw)
    closed(value, {'protocol', 'execution', 'nonce', 'identityDigest',
                   'canonicalDigest', 'targetIR'}, 'PLUGIN_REQUEST_FIELDS')
    require(value['protocol'] == PROTOCOL and value['identityDigest'] == payload_digest(identity),
            'PLUGIN_REQUEST_IDENTITY')
    require(all(type(value[k]) is str and re.fullmatch(r'[0-9a-f]{32}', value[k])
                for k in ('execution', 'nonce')), 'PLUGIN_EXECUTION_ID')
    require(is_digest(canonical_digest) and value['canonicalDigest'] == canonical_digest
            and is_digest(target_ir_digest) and payload_digest(value['targetIR']) == target_ir_digest,
            'PLUGIN_SEMANTIC_IDENTITY')
    return value


def validate_response(raw, *, request, expected_artifacts):
    """Check proposed records against host-owned paths, origins and obligation IDs."""
    value = decode(raw)
    common = {'protocol', 'execution', 'requestDigest', 'outcome'}
    require(type(value) is dict and value.get('outcome') in ('SUCCESS', 'ERROR'), 'PLUGIN_OUTCOME')
    success = value['outcome'] == 'SUCCESS'
    closed(value, common | ({'artifacts'} if success else {'error'}), 'PLUGIN_RESPONSE_FIELDS')
    require(value['protocol'] == PROTOCOL and value['execution'] == request['execution']
            and value['requestDigest'] == payload_digest(request), 'PLUGIN_RESPONSE_BINDING')
    if not success:
        require(value['error'] in ('UNSUPPORTED', 'GENERATION_FAILED'), 'PLUGIN_ERROR')
        return value
    seen = set()
    require(type(value['artifacts']) is list and len(value['artifacts']) == len(expected_artifacts),
            'PLUGIN_ARTIFACT_COUNT')
    for row in value['artifacts']:
        closed(row, {'path', 'content', 'contentDigest', 'origins', 'obligations'}, 'PLUGIN_ARTIFACT_FIELDS')
        path = row['path']
        require(type(path) is str and path.isascii() and re.fullmatch(r'[A-Za-z0-9._/-]+', path)
                and not set(path.split('/')) & {'', '.', '..'}
                and path not in seen and path in expected_artifacts, 'PLUGIN_ARTIFACT_PATH')
        require(not any(path.startswith(p + '/') or p.startswith(path + '/') for p in seen),
                'PLUGIN_ARTIFACT_COLLISION')
        seen.add(path)
        require(type(row['content']) is str and digest(row['content'].encode()) == row['contentDigest'],
                'PLUGIN_ARTIFACT_DIGEST')
        require((row['origins'], row['obligations']) == expected_artifacts[path],
                'PLUGIN_ARTIFACT_SEMANTICS')
    return value


def admission_status():
    """The foundation has no registry, approval or execution authority."""
    return 'BLOCKED_PENDING_OWNER_APPROVAL'
