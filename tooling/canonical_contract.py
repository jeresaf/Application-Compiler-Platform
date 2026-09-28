"""Generate the closed Phase 2 envelope using the pinned Phase 1 semantic types."""
import copy
import json

from phase1_contract import ROOT, array, record, use
from canonical_json import PROFILE


def build_schema():
    source = json.loads((ROOT / "contracts/phase1.schema.json").read_text(encoding="utf-8"))
    defs = copy.deepcopy(source["$defs"])
    defs["node"]["properties"]["lifecycle"] = {"enum": ["APPROVED", "DEPRECATED"]}
    defs["node"]["properties"].pop("supersededBy")
    defs["content"] = record({
        "irKind": {"const": "CanonicalApplication"},
        "schemaVersion": {"const": "0.1.0"},
        "semanticModelVersion": {"const": "0.2.0"},
        "canonicalProfile": {"const": PROFILE},
        "applicationId": use("id"),
        "requiredFeatures": {"const": ["acp.phase1.0.2"]},
        "nodes": array(use("node"), 1),
        "issues": array(use("issue")),
    })
    return {
        "$schema": source["$schema"], "$id": "urn:acp:canonical:0.1.0",
        "title": "ACP Canonical Application 0.1.0 content candidate; authority is external",
        **record({"content": use("content"), "contentDigest": {
            "type": "string", "pattern": r"^sha256:[0-9a-f]{64}(?![\s\S])"}}),
        "$defs": defs,
    }


if __name__ == "__main__":
    (ROOT / "contracts/canonical.schema.json").write_text(
        json.dumps(build_schema(), indent=2) + "\n", encoding="utf-8")
