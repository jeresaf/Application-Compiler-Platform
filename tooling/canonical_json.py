"""ACP's safe-integer JCS profile. Contract tooling, not a general JCS library."""
import hashlib
import json

MAX_BYTES = 1_048_576
MAX_DEPTH = 48
MAX_INTEGER = 9007199254740991
PROFILE = "acp-jcs-safe-v1"
DOMAINS = {"canonical", "authoring", "vector"}


def canonical_bytes(value):
    """RFC 8785 bytes for JSON values restricted to safe integer number tokens."""
    def encode(item, depth):
        if depth > MAX_DEPTH:
            raise ValueError("Nesting limit exceeded")
        if item is None:
            return "null"
        if type(item) is bool:
            return "true" if item else "false"
        if type(item) is int and abs(item) <= MAX_INTEGER:
            return str(item)
        if type(item) is str:
            item.encode("utf-8", errors="strict")
            return json.dumps(item, ensure_ascii=False)
        if type(item) is list:
            return "[" + ",".join(encode(v, depth + 1) for v in item) + "]"
        if type(item) is dict and all(type(k) is str for k in item):
            # JCS orders UTF-16 code units, not Python Unicode code points.
            keys = sorted(item, key=lambda k: k.encode("utf-16-be", errors="strict"))
            return "{" + ",".join(encode(k, depth + 1) + ":" + encode(item[k], depth + 1) for k in keys) + "}"
        raise ValueError("Unsupported JSON value or unsafe integer")

    result = encode(value, 0).encode("utf-8")
    if len(result) > MAX_BYTES:
        raise ValueError("Byte limit exceeded")
    return result


def loads(raw):
    """Strict wire ingestion; duplicates and non-integer tokens fail before hashing."""
    if type(raw) is not bytes or len(raw) > MAX_BYTES or raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("Invalid or oversized UTF-8 input")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate object key")
            result[key] = value
        return result

    def reject(_):
        raise ValueError("Non-integer numeric token")

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                       parse_float=reject, parse_constant=reject)
    canonical_bytes(value)
    return value


def load(path):
    with path.open("rb") as stream:
        return loads(stream.read(MAX_BYTES + 1))


def digest(value, domain):
    if domain not in DOMAINS:
        raise ValueError("Unknown digest domain")
    prefix = ("ACP\x00" + PROFILE + "\x00" + domain + "\x00").encode("ascii")
    return "sha256:" + hashlib.sha256(prefix + canonical_bytes(value)).hexdigest()
