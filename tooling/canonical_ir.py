"""Phase 2 canonical contract reference harness; no production approval authority."""
import argparse
import copy
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry

from canonical_json import PROFILE, canonical_bytes, digest, load
from validate import ROOT, validate

SCHEMA = load(ROOT / "contracts/canonical.schema.json")
SHAPES = Draft202012Validator(SCHEMA, registry=Registry())
ORDERED_REFS = {("UseCase", "steps"), ("Wizard", "steps")}
# Non-reference arrays are explicitly classified. New arrays require a decision.
SET_ARRAYS = {
    ("Invariant", "enforcement"), ("AuthenticationModel", "mechanisms"),
    ("ResponsivePolicy", "modes"), ("AccessibilityRequirement", "checks"),
    ("EvidenceRequirement", "methods"),
    ("CompatibilityRequirement", "supportedVersions"),
    ("ObservabilityRequirement", "signals"),
}
ORDERED_ARRAYS = {("Decision", "alternatives")}
MAP_ARRAYS = {("Query", "projection")}


class CanonicalError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = "ACP-IR-" + code


def ordered(values):
    return sorted(values, key=canonical_bytes)


def _threshold(value):
    _, digits, exponent = Decimal(value).as_tuple()
    digits = list(digits)
    while digits and digits[-1] == 0:
        digits.pop()
        exponent += 1
    # Bound expansion BEFORE constructing a plain-decimal string.
    point = len(digits) + exponent
    if max(point, len(digits), 2 - exponent) > 128:
        raise CanonicalError("NORMAL", "Quality threshold exceeds the canonical 128-character numeric bound.")
    text = "".join(map(str, digits))
    if point <= 0:
        return "0." + "0" * -point + text
    if point < len(text):
        return text[:point] + "." + text[point:]
    return text + "0" * exponent


def _literal(typ, value, index):
    kind = typ["kind"]
    if kind == "Nullable":
        return None if value is None else _literal(typ["item"], value, index)
    if kind == "Named":
        return _literal(index[typ["definition"]["id"]]["data"]["base"], value, index)
    if kind in {"Decimal", "Money"}:
        # Input has already passed exact precision/scale validation. Never round.
        result = value.rstrip("0").rstrip(".") if "." in value else value
        return "0" if result in {"-0", "0"} else result
    if kind in {"Instant", "LocalDateTime"} and "." in value:
        suffix = "Z" if kind == "Instant" else ""
        body = value[:-1] if suffix else value
        return body.rstrip("0").rstrip(".") + suffix
    if kind in {"Set", "List"}:
        items = [_literal(typ["element"], v, index) for v in value]
        return ordered(items) if kind == "Set" else items
    if kind == "Value":
        return {key: _literal(index[key]["data"]["type"], v, index) for key, v in value.items()}
    return copy.deepcopy(value)


def _data(value, index, kind, path=()):
    if isinstance(value, dict):
        # Do not interpret keys inside user ValueObject literals as semantic nodes.
        if value.get("tag") == "literal" or set(value) == {"type", "value"}:
            return {**copy.deepcopy(value), "value": _literal(value["type"], value["value"], index)}
        return {k: _data(v, index, kind, path + (k,)) for k, v in value.items()}
    if isinstance(value, list):
        items = [_data(v, index, kind, path + (i,)) for i, v in enumerate(value)]
        key = (kind, path[0]) if len(path) == 1 else None
        if key in ORDERED_REFS | ORDERED_ARRAYS:
            return items
        if key in SET_ARRAYS | MAP_ARRAYS or all(isinstance(v, dict) and set(v) == {"id", "revision"} for v in value):
            return ordered(items)
        raise CanonicalError("NORMAL", "Array has no declared canonical ordering policy.")
    return copy.deepcopy(value)


def _normalize_nodes(nodes):
    index = {n["id"]: n for n in nodes}
    result = []
    for source in nodes:
        node = copy.deepcopy(source)
        node["basis"] = ordered(node["basis"])
        # Origin records are a sorted multiset: no evidence is discarded.
        node["origins"] = ordered(node["origins"])
        node["data"] = _data(source["data"], index, source["kind"])
        if source["kind"] == "TypeDefinition" and source["data"]["refinement"]["kind"] == "RANGE":
            for key in ("min", "max"):
                node["data"]["refinement"][key] = _literal(source["data"]["base"], source["data"]["refinement"][key], index)
        if source["kind"] in {"PerformanceRequirement", "ReliabilityRequirement"}:
            node["data"]["threshold"] = _threshold(source["data"]["threshold"])
        result.append(node)
    return sorted(result, key=lambda n: n["id"])


def _normalize_issues(issues):
    result = copy.deepcopy(issues)
    for issue in result:
        issue["subjects"] = ordered(issue["subjects"])
    return sorted(result, key=lambda issue: issue["id"])


def _check_input(value):
    try:
        canonical_bytes(value)
    except (ValueError, UnicodeError, RecursionError):
        raise CanonicalError("INPUT", "Input violates the bounded JSON profile.") from None


def normalize_candidate(authoring):
    """Import compile-eligible authoring content, never authenticate its attestations."""
    _check_input(authoring)
    if not isinstance(authoring, dict) or authoring.get("modelVersion") != "0.2.0":
        raise CanonicalError("VERSION", "Only authoring model 0.2.0 has an import contract.")
    if validate(authoring, "compile"):
        raise CanonicalError("SEMANTIC", "Authoring input fails compile-eligibility validation.")
    content = {
        "irKind": "CanonicalApplication", "schemaVersion": "0.1.0",
        "semanticModelVersion": "0.2.0", "canonicalProfile": PROFILE,
        "applicationId": authoring["applicationId"], "requiredFeatures": ["acp.phase1.0.2"],
        "nodes": _normalize_nodes(authoring["nodes"]),
        "issues": _normalize_issues(authoring["issues"]),
    }
    return {"content": content, "contentDigest": digest(content, "canonical")}


def validate_snapshot(snapshot):
    """Validate content, normalized form and digest. Does not establish approval."""
    _check_input(snapshot)
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("content"), dict):
        raise CanonicalError("SHAPE", "Expected a closed canonical envelope.")
    content = snapshot["content"]
    versions = {"irKind": "CanonicalApplication", "schemaVersion": "0.1.0",
                "semanticModelVersion": "0.2.0", "canonicalProfile": PROFILE}
    if any(content.get(k) != v for k, v in versions.items()):
        raise CanonicalError("VERSION", "Unsupported canonical kind, version or profile.")
    if content.get("requiredFeatures") != ["acp.phase1.0.2"]:
        raise CanonicalError("FEATURE", "Required semantic feature set is not supported.")
    if not SHAPES.is_valid(snapshot):
        raise CanonicalError("SHAPE", "Canonical envelope violates its closed schema.")
    # These structural witnesses let the existing checker test ACTIVE eligibility.
    # They are NEVER passed to the authority port or represented as real approvals.
    authoring = {"modelVersion": "0.2.0", "applicationId": content["applicationId"],
                 "snapshotId": "IR-STRUCTURAL-CHECK", "nodes": content["nodes"], "issues": content["issues"],
                 "approvals": [{"subject": {"id": n["id"], "revision": n["revision"]},
                                "reviewer": "structural-check-only", "evidence": "not-an-approval"}
                               for n in content["nodes"]]}
    if validate(authoring, "compile"):
        raise CanonicalError("SEMANTIC", "Canonical content fails semantic validation.")
    if (content["nodes"] != _normalize_nodes(content["nodes"]) or
            content["issues"] != _normalize_issues(content["issues"])):
        raise CanonicalError("NORMAL", "Canonical content is not in normal form.")
    if snapshot["contentDigest"] != digest(content, "canonical"):
        raise CanonicalError("DIGEST", "Canonical content does not match its declared digest.")


@dataclass(frozen=True)
class AdmittedSnapshot:
    """Immutable bytes returned only after the caller's trusted authority accepts."""
    content_bytes: bytes
    content_digest: str


def admit(snapshot, authority=None):
    """Authority is a trusted host port, never supplied by imported JSON.

    The port checks principal/scope/revocation externally and returns literal True
    only for this exact content request. Exceptions and absent ports fail closed.
    """
    candidate = copy.deepcopy(snapshot)
    validate_snapshot(candidate)
    body = canonical_bytes(candidate["content"])
    request = {"applicationId": candidate["content"]["applicationId"],
               "contentDigest": candidate["contentDigest"], "contentBytes": body}
    try:
        accepted = authority(request) if authority is not None else False
    except Exception:
        accepted = False
    if accepted is not True:
        raise CanonicalError("AUTHORITY", "Exact-content approval authority is unavailable or did not approve.")
    return AdmittedSnapshot(body, candidate["contentDigest"])


def migrate_authoring(source, target_version="0.1.0"):
    """Only registered migration: authoring 0.2.0 -> canonical candidate 0.1.0."""
    if target_version != "0.1.0":
        raise CanonicalError("VERSION", "No migration is registered for this target version.")
    snapshot = normalize_candidate(source)
    return {"migration": "authoring-0.2-to-canonical-0.1-v1",
            "sourceDigest": digest(source, "authoring"), "targetDigest": snapshot["contentDigest"],
            "requiresApproval": True,
            "preservedSubjects": [{"id": n["id"], "revision": n["revision"]} for n in snapshot["content"]["nodes"]],
            "candidate": snapshot}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("normalize", "validate", "migrate"))
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        document = load(args.input)
        if args.operation == "validate":
            validate_snapshot(document)
            output = {"valid": True, "authorityVerified": False, "contentDigest": document["contentDigest"]}
        elif args.operation == "normalize":
            output = normalize_candidate(document)
        else:
            output = migrate_authoring(document)
        print(json.dumps(output, ensure_ascii=True, indent=2))
        return 0
    except CanonicalError as error:
        print(json.dumps({"valid": False, "code": error.code, "message": str(error)}))
        return 1
    except (OSError, ValueError, UnicodeError, RecursionError):
        print(json.dumps({"valid": False, "code": "ACP-IR-INPUT", "message": "Cannot decode bounded strict UTF-8 input."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
