"""RFC 8785 serialization for the contract's null/bool/string/safe-integer subset.

Fractions, exponents, floats and non-finite numbers are deliberately outside the
permitted numeric domain. No ACP Canonical serializer is changed or reused.
"""
import hashlib
import json

MAX_INTEGER = 2**53 - 1
MAX_BYTES = 4 * 1024 * 1024
MAX_DEPTH = 64


class EncodingError(ValueError):
    pass


def utf16_key(value):
    if type(value) is not str:
        raise EncodingError('STRING_REQUIRED')
    try:
        return value.encode('utf-16-be')
    except UnicodeError as error:
        raise EncodingError('INVALID_UNICODE') from error


def canonicalize(value):
    """Return exact JCS bytes for permitted types, preserving Unicode as supplied."""
    def encode(item, depth):
        if depth > MAX_DEPTH:
            raise EncodingError('DEPTH_LIMIT')
        if item is None:
            return 'null'
        if type(item) is bool:
            return 'true' if item else 'false'
        if type(item) is int:
            if abs(item) > MAX_INTEGER:
                raise EncodingError('UNSAFE_INTEGER')
            return str(item)
        if type(item) is str:
            utf16_key(item)
            return json.dumps(item, ensure_ascii=False)
        if type(item) is list:
            return '[' + ','.join(encode(v, depth + 1) for v in item) + ']'
        if type(item) is dict:
            keys = sorted(item, key=utf16_key)
            return '{' + ','.join(encode(k, depth + 1) + ':' + encode(item[k], depth + 1) for k in keys) + '}'
        raise EncodingError('UNSUPPORTED_VALUE_TYPE')

    try:
        raw = encode(value, 0).encode('utf-8')
    except RecursionError as error:
        raise EncodingError('DEPTH_LIMIT') from error
    if len(raw) > MAX_BYTES:
        raise EncodingError('SIZE_LIMIT')
    return raw


def parse_canonical(raw):
    """Parse bytes only; reject equivalent but noncanonical serialized inputs."""
    if type(raw) is not bytes:
        raise EncodingError('BYTES_REQUIRED')
    if len(raw) > MAX_BYTES:
        raise EncodingError('SIZE_LIMIT')

    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise EncodingError('DUPLICATE_KEY')
            result[key] = value
        return result

    def unsupported(_):
        raise EncodingError('UNSUPPORTED_NUMBER')

    def integer(token):
        if len(token.lstrip('-')) > 16:
            raise EncodingError('UNSAFE_INTEGER')
        value = int(token)
        if abs(value) > MAX_INTEGER:
            raise EncodingError('UNSAFE_INTEGER')
        return value

    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_int=integer, parse_float=unsupported, parse_constant=unsupported)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise EncodingError('INVALID_JSON') from error
    if canonicalize(value) != raw:
        raise EncodingError('NONCANONICAL_INPUT')
    return value


def payload_digest(payload):
    """Content identity only. A matching digest conveys no authority."""
    return 'sha256:' + hashlib.sha256(canonicalize(payload)).hexdigest()


def signature_input(payload):
    """Prepare proposed signing bytes, without signing or authenticating anything."""
    schema = payload.get('schema') if type(payload) is dict else None
    if type(schema) is not str or not schema.isascii() or '\0' in schema:
        raise EncodingError('INVALID_SCHEMA_ID')
    return ('ACP-PHASE6-EVIDENCE\0' + schema + '\0').encode('ascii') + canonicalize(payload)
