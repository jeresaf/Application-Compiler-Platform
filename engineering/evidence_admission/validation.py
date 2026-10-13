"""Pure structural checks. No trust store, clock, signature verification or I/O admission.

Schema formats and x-set-key constraints are part of the Stage 1 dialect.
Reference checking compares supplied bytes only; it never authenticates issuers.
"""
import base64
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from referencing import Registry, Resource

from .encoding import EncodingError, parse_canonical, payload_digest, utf16_key

PREFIX = 'acp-phase6-evidence/'
COMMON = 'urn:acp-phase6-evidence:common:1#/$defs/'
KINDS = ('engineering-envelope', 'verifier-registration', 'execution-attestation',
         'artifact-manifest', 'human-decision', 'human-registry', 'revocation',
         'admission-receipt', 'admission-rejection', 'trust-policy',
         'trust-snapshot', 'execution-challenge')
SCHEMAS = Path(__file__).parent / 'schemas'
FORMATS = FormatChecker()


@FORMATS.checks('acp-utc', raises=(ValueError, TypeError))
def _utc(value):
    if type(value) is not str:
        return False
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').isoformat(timespec='seconds') + 'Z' == value


def _base64(value, size):
    if type(value) is not str:
        return False
    try:
        raw = base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
    except (ValueError, UnicodeError):
        return False
    return len(raw) == size and base64.urlsafe_b64encode(raw).decode().rstrip('=') == value


FORMATS.checks('acp-signature')(lambda value: _base64(value, 64))
FORMATS.checks('acp-nonce')(lambda value: _base64(value, 32))
FORMATS.checks('acp-path')(lambda value: type(value) is str and all(part not in ('', '.', '..') for part in value.split('/')))


@dataclass(frozen=True)
class StructuralResult:
    status: str
    errors: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def _schemas():
    schemas = {kind: json.loads((SCHEMAS / (kind + '.schema.json')).read_text()) for kind in (*KINDS, 'common')}
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    registry = Registry().with_resource('urn:acp-phase6-evidence:common:1', Resource.from_contents(schemas['common']))
    return schemas, registry


def _sets(value, schema, validator, definitions):
    if '$ref' in schema:
        name = schema['$ref'].removeprefix(COMMON)
        if schema['$ref'] != COMMON + name or name not in definitions:
            raise ValueError('UNSUPPORTED_SCHEMA_REFERENCE')
        return _sets(value, definitions[name], validator, definitions)
    if 'oneOf' in schema:
        matching = [s for s in schema['oneOf'] if validator.evolve(schema=s).is_valid(value)]
        if len(matching) != 1:
            raise ValueError('AMBIGUOUS_UNION')
        return _sets(value, matching[0], validator, definitions)
    if type(value) is dict:
        for name, item in value.items():
            _sets(item, schema['properties'][name], validator, definitions)
    if type(value) is list:
        if 'x-set-key' in schema:
            keys = schema['x-set-key']
            def key(item):
                parts = [item[k] for k in keys] if keys else [item]
                return tuple(utf16_key(v) if type(v) is str else v for v in parts)
            identities = [key(item) for item in value]
            if len(set(identities)) != len(identities):
                raise ValueError('DUPLICATE_ARRAY_IDENTITY')
            if identities != sorted(identities):
                raise ValueError('UNORDERED_SET')
        for item in value:
            _sets(item, schema['items'], validator, definitions)


def _relationships(payload):
    if payload['issuedAt'] >= payload['expiresAt']:
        raise ValueError('INVALID_VALIDITY_INTERVAL')
    kind = payload['schema'].split('/')[1]
    if kind == 'execution-attestation':
        if not payload['startedAt'] <= payload['finishedAt'] <= payload['issuedAt']:
            raise ValueError('INVALID_EXECUTION_INTERVAL')
    if kind == 'human-registry':
        for grant in payload['grants']:
            if grant['validFrom'] >= grant['validUntil']:
                raise ValueError('INVALID_GRANT_INTERVAL')
    if kind in ('human-registry', 'trust-policy', 'trust-snapshot'):
        seq, pred = {'human-registry': ('sequence', 'predecessorRef'),
                     'trust-policy': ('sequence', 'predecessorPolicyRef'),
                     'trust-snapshot': ('snapshotSequence', 'predecessorRef')}[kind]
        if (payload[seq] == 0) != (payload[pred] is None):
            raise ValueError('INVALID_PREDECESSOR_SHAPE')
    if kind == 'human-registry':
        if (payload['revocationSequence'] == 0) != (payload['revocationHeadRef'] is None):
            raise ValueError('INVALID_REVOCATION_HEAD')
    if kind == 'trust-snapshot':
        for head in payload['revocationHeads']:
            if (head['sequence'] == 0) != (head['headRef'] is None):
                raise ValueError('INVALID_REVOCATION_HEAD')
    if kind == 'revocation':
        if (payload['sequence'] == 1) != (payload['predecessorRef'] is None):
            raise ValueError('INVALID_PREDECESSOR_SHAPE')
        if payload['action'] == 'REPLACE':
            old, new = payload['targetRef'], payload['replacementRef']
            if old['schema'] != new['schema'] or old == new:
                raise ValueError('INVALID_REPLACEMENT_REFERENCE')
    if kind == 'verifier-registration':
        if set(payload['criteria']) != {r['criterion'] for r in payload['witnessContracts']}:
            raise ValueError('INCOMPLETE_WITNESS_CRITERIA')
    if kind == 'admission-receipt':
        if payload['criteria'] != [r['criterion'] for r in payload['predicateResults']]:
            raise ValueError('INCOMPLETE_PREDICATE_CRITERIA')


def _decode(raw):
    value = parse_canonical(raw)
    schema_id = value.get('payload', {}).get('schema') if type(value) is dict and type(value.get('payload')) is dict else None
    matches = [k for k in KINDS if schema_id == PREFIX + k + '/1']
    if not matches:
        raise ValueError('UNSUPPORTED_SCHEMA_VERSION_OR_TYPE')
    schemas, registry = _schemas()
    schema = schemas[matches[0]]
    validator = Draft202012Validator(schema, registry=registry, format_checker=FORMATS)
    validator.validate(value)
    _sets(value, schema, validator, schemas['common']['$defs'])
    if value['payloadDigest'] != payload_digest(value['payload']):
        raise ValueError('PAYLOAD_DIGEST_MISMATCH')
    _relationships(value['payload'])
    return value


def validate_structure(raw):
    """Validate one canonical record. Signature bytes are never authenticated."""
    try:
        _decode(raw)
    except (EncodingError, ValidationError, ValueError) as error:
        reason = 'SCHEMA_VIOLATION' if isinstance(error, ValidationError) else str(error)
        return StructuralResult('STRUCTURE_INVALID', (reason,))
    return StructuralResult('STRUCTURE_VALID_UNTRUSTED')


def validate_bundle(records):
    """Check a closed supplied reference graph; no file/network/authority access."""
    try:
        if type(records) is not list or not 1 <= len(records) <= 128:
            raise ValueError('INVALID_BUNDLE_SIZE')
        values = [_decode(raw) for raw in records]
        by_digest = {v['payloadDigest']: v['payload'] for v in values}
        if len(by_digest) != len(values):
            raise ValueError('DUPLICATE_RECORD')
        ids = [v['payload']['recordId'] for v in values]
        if len(set(ids)) != len(ids):
            raise ValueError('DUPLICATE_RECORD_IDENTITY')
        def resolve(reference):
            target = by_digest.get(reference['payloadDigest'])
            if target is None:
                raise ValueError('MISSING_REFERENCE')
            if target['schema'] != reference['schema']:
                raise ValueError('REFERENCE_TYPE_MISMATCH')
            return target
        def walk(value):
            if type(value) is dict:
                if set(value) == {'schema', 'payloadDigest'}:
                    resolve(value)
                else:
                    for child in value.values():
                        walk(child)
            elif type(value) is list:
                for child in value:
                    walk(child)
        for payload in by_digest.values():
            walk(payload)
            for field in ('challengeRef', 'registrationRef', 'attestationRef', 'manifestRef', 'envelopeRef', 'verifierRegistrationRef'):
                if field not in payload:
                    continue
                target = resolve(payload[field])
                for binding in ('binding', 'subjects', 'policyRef', 'executionId'):
                    if binding in payload and binding in target and payload[binding] != target[binding]:
                        raise ValueError('REFERENCE_BINDING_MISMATCH')
    except (EncodingError, ValidationError, ValueError) as error:
        reason = 'SCHEMA_VIOLATION' if isinstance(error, ValidationError) else str(error)
        return StructuralResult('STRUCTURE_INVALID', (reason,))
    return StructuralResult('STRUCTURE_VALID_UNTRUSTED')
