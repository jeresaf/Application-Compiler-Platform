"""Ed25519 verification only. Key ownership and roles are injected, not discovered."""
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .encoding import parse_canonical, signature_input
from .validation import validate_structure


class LabVerificationError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise LabVerificationError(reason)


def utc(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def fingerprint(public_key):
    require(type(public_key) is bytes and len(public_key) == 32, 'INVALID_PUBLIC_KEY')
    return 'sha256:' + hashlib.sha256(public_key).hexdigest()


@dataclass(frozen=True)
class LabKey:
    key_id: str
    principal_id: str
    public_key: bytes
    roles: frozenset[str]
    valid_from: datetime
    valid_until: datetime

    def __post_init__(self):
        object.__setattr__(self, 'roles', frozenset(self.roles))
        require(type(self.key_id) is str and re.fullmatch(r'key:[a-z0-9][a-z0-9-]{0,63}', self.key_id), 'INVALID_KEY_IDENTITY')
        require(type(self.principal_id) is str and re.fullmatch(r'principal:[a-z0-9][a-z0-9-]{0,63}', self.principal_id), 'INVALID_PRINCIPAL_IDENTITY')
        require(all(type(r) is str for r in self.roles), 'INVALID_SIGNER_ROLE')
        fingerprint(self.public_key)
        require(self.valid_from.tzinfo == timezone.utc and self.valid_until.tzinfo == timezone.utc,
                'UTC_KEY_VALIDITY_REQUIRED')
        require(self.valid_from < self.valid_until, 'INVALID_KEY_VALIDITY')


def verify_ed25519(public_key, signature, message):
    """Primitive verification; success alone confers no authorization."""
    fingerprint(public_key)
    require(type(signature) is bytes and len(signature) == 64, 'INVALID_SIGNATURE_ENCODING')
    require(type(message) is bytes, 'MESSAGE_BYTES_REQUIRED')
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
    except (InvalidSignature, UnsupportedAlgorithm, ValueError) as error:
        raise LabVerificationError('INVALID_SIGNATURE') from error


def validate_keys(keys):
    require(type(keys) is tuple and all(type(k) is LabKey for k in keys), 'IMMUTABLE_KEYS_REQUIRED')
    require(len({k.key_id for k in keys}) == len(keys), 'DUPLICATE_KEY_ID')
    require(len({fingerprint(k.public_key) for k in keys}) == len(keys), 'AMBIGUOUS_KEY_ALIAS')


def verify_record_signatures(raw, keys, role, threshold, now, revoked_keys, revoked_principals):
    """Verify every supplied signature under externally supplied laboratory roles."""
    require(validate_structure(raw).status == 'STRUCTURE_VALID_UNTRUSTED', 'INVALID_STRUCTURE')
    validate_keys(keys)
    require(type(threshold) is int and threshold > 0, 'INVALID_THRESHOLD')
    require(now.tzinfo == timezone.utc, 'TRUSTED_UTC_REQUIRED')
    record = parse_canonical(raw)
    message = signature_input(record['payload'])
    supplied = record['signatures']
    require(len({s['signerId'] for s in supplied}) == len(supplied), 'DUPLICATE_SIGNER_PRINCIPAL')
    by_id = {k.key_id: k for k in keys}
    verified = []
    for signature in supplied:
        key = by_id.get(signature['keyId'])
        require(key is not None, 'UNKNOWN_SIGNING_KEY')
        require(key.principal_id == signature['signerId'], 'WRONG_SIGNER_IDENTITY')
        require(role in key.roles, 'WRONG_SIGNER_ROLE')
        require(key.key_id not in revoked_keys and key.principal_id not in revoked_principals, 'REVOKED_SIGNER')
        require(key.valid_from <= now < key.valid_until, 'EXPIRED_SIGNING_KEY')
        require(key.valid_from <= utc(record['payload']['issuedAt']) < key.valid_until, 'KEY_NOT_VALID_AT_ISSUE')
        encoded = signature['signature']
        decoded = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))
        verify_ed25519(key.public_key, decoded, message)
        verified.append(key.principal_id)
    require(len(verified) >= threshold, 'INSUFFICIENT_SIGNATURE_THRESHOLD')
    return tuple(verified)
