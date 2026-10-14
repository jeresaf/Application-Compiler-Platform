"""Closed laboratory contracts. Data and verification only; no workload launch."""
from dataclasses import dataclass
from pathlib import Path
import json

from jsonschema import Draft202012Validator, ValidationError
from referencing import Registry, Resource

from .encoding import canonicalize, parse_canonical, utf16_key
from .registration import sha
from .signatures import require, LabVerificationError
from .trust import LabTrustContext
from .validation import FORMATS

SCHEMA = 'acp-phase6-lab-execution-contract/1'
DOMAIN = b'ACP-PHASE6-LAB-EXECUTION-CONTRACT\0'
COMMON = 'urn:acp-phase6-evidence:common:1#/$defs/'


def ref(name):
    return {'$ref': COMMON + name}


def closed(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def array(items):
    return {'type': 'array', 'items': items, 'minItems': 1, 'maxItems': 4096, 'uniqueItems': True}


TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 4096}
CONTRACT = closed({
    'schema': {'const': SCHEMA}, 'repository': ref('repository'), 'auditSessionId': ref('session'),
    'registrationDigest': ref('digest'), 'policyDigest': ref('digest'), 'binding': ref('binding'),
    'subjects': ref('subjects'), 'criteria': array(ref('criterion')),
    'cases': array(closed({'criterion': ref('criterion'), 'application': ref('caseApplication'),
                          'witnessId': ref('witnessId'), 'caseId': ref('caseId')})),
    'commands': array(closed({'commandId': TEXT, 'argv': array(TEXT), 'executablePath': ref('path'),
                             'executableDigest': ref('digest'), 'dependencyDigest': ref('digest'),
                             'workingDirectory': ref('path'), 'workingDirectoryDigest': ref('digest'),
                             'environment': {'type': 'object', 'maxProperties': 64,
                                 'propertyNames': {'pattern': r'^[A-Z][A-Z0-9_]{0,63}(?![\s\S])'},
                                 'additionalProperties': {'type': 'string', 'maxLength': 4096}}})),
    'artifacts': array(closed({'path': ref('path'), 'role': {'enum': ['LOG', 'JUNIT', 'ASSERTIONS', 'PACKAGE',
                      'SBOM', 'ENVIRONMENT', 'SOURCE', 'REVIEW', 'OTHER_REGISTERED']},
                      'mediaType': {'enum': ['application/json', 'application/xml', 'text/plain',
                                            'application/octet-stream', 'application/x-tar']},
                      'expectedDigest': {'oneOf': [{'type': 'null'}, ref('digest')]},
                      'maxBytes': {'type': 'integer', 'minimum': 1, 'maximum': 67108864}})),
    'limits': closed({'maxArtifacts': {'type': 'integer', 'minimum': 1, 'maximum': 4096},
                      'maxTotalBytes': {'type': 'integer', 'minimum': 1, 'maximum': 268435456},
                      'memoryBytes': ref('positive'), 'processes': ref('positive'),
                      'cpuSeconds': ref('positive'), 'executionTimeoutSeconds': ref('positive')}),
    'isolationProfileDigest': ref('digest'),
})
# argv is an ordered sequence and may legitimately repeat arguments.
CONTRACT['properties']['commands']['items']['properties']['argv'].pop('uniqueItems')


def execution_contract(raw):
    value = parse_canonical(raw)
    common = json.loads((Path(__file__).parent / 'schemas/common.schema.json').read_text())
    registry = Registry().with_resource('urn:acp-phase6-evidence:common:1', Resource.from_contents(common))
    try:
        Draft202012Validator(CONTRACT, registry=registry, format_checker=FORMATS).validate(value)
    except ValidationError as error:
        raise LabVerificationError('INVALID_EXECUTION_CONTRACT') from error
    def ordered(rows, key, reason):
        ids = [key(row) for row in rows]
        require(ids == sorted(set(ids)), reason)
    ordered(value['subjects'], lambda r: utf16_key(r['application']), 'AMBIGUOUS_SUBJECTS')
    ordered(value['criteria'], lambda r: r, 'AMBIGUOUS_CRITERIA')
    ordered(value['cases'], lambda r: (utf16_key(r['application']), utf16_key(r['witnessId']), utf16_key(r['caseId'])), 'AMBIGUOUS_CASES')
    require(len({r['commandId'] for r in value['commands']}) == len(value['commands']), 'DUPLICATE_COMMAND')
    ordered(value['artifacts'], lambda r: utf16_key(r['path']), 'AMBIGUOUS_ARTIFACTS')
    require({r['criterion'] for r in value['cases']} == set(value['criteria']), 'INCOMPLETE_CRITERIA')
    applications = {r['application'] for r in value['subjects']}
    require({r['application'] for r in value['cases']} - {'SHARED_HOST'} == applications, 'INCOMPLETE_APPLICATION_CASES')
    require(len(value['artifacts']) <= value['limits']['maxArtifacts'], 'ARTIFACT_LIMIT')
    for command in value['commands']:
        require(command['argv'][0] == command['executablePath'], 'EXECUTABLE_ARGV_MISMATCH')
        require(Path(command['executablePath']).name not in ('sh', 'bash', 'dash', 'zsh', 'ksh', 'fish', 'env'), 'SHELL_OR_DISPATCHER_FORBIDDEN')
        require(all('\0' not in arg for arg in command['argv']), 'NUL_ARGUMENT')
        require(not any('\0' in v for v in command['environment'].values()), 'NUL_ENVIRONMENT')
    require(all(a['expectedDigest'] is not None for a in value['artifacts'] if a['role'] == 'PACKAGE'), 'PACKAGE_DIGEST_REQUIRED')
    for subject in value['subjects']:
        key = {'PAYMENT': 'payment', 'CASE_MANAGEMENT': 'case-management'}[subject['application']]
        require(subject['snapshotDigest'] == value['binding']['canonicalDigests'][key], 'SUBJECT_CANONICAL_MISMATCH')
        require(any(a['role'] == 'PACKAGE' and a['expectedDigest'] == subject['packageDigest'] for a in value['artifacts']),
                'MISSING_KNOWN_PACKAGE_ARTIFACT')
    return value


def contract_digest(raw):
    execution_contract(raw)
    return sha(DOMAIN + raw)


@dataclass(frozen=True)
class LabExecutionContext:
    """Independent host input; constructing this object does not establish custody."""
    trust: LabTrustContext
    contract_raw: bytes
    expected_contract_digest: str
    issuer_id: str
    registration_raw: bytes
    policy_raw: bytes
    verifier_source_root: str
    laboratory: bool = True

    def __post_init__(self):
        require(type(self.trust) is LabTrustContext and self.laboratory is True, 'LAB_CONTEXT_REQUIRED')
        require(all(type(raw) is bytes for raw in (self.contract_raw, self.registration_raw, self.policy_raw)), 'IMMUTABLE_RECORDS_REQUIRED')
        require(all(type(s) is str for s in (self.expected_contract_digest, self.issuer_id, self.verifier_source_root)), 'IMMUTABLE_IDENTITIES_REQUIRED')
        require(contract_digest(self.contract_raw) == self.expected_contract_digest, 'UNPINNED_EXECUTION_CONTRACT')
        value = execution_contract(self.contract_raw)
        require(value['repository'] == self.trust.repository and value['policyDigest'] == self.trust.policy_digest, 'WRONG_CONTRACT_POLICY')
        require(self.issuer_id not in self.trust.candidate_authors, 'CANDIDATE_ISSUER_FORBIDDEN')
