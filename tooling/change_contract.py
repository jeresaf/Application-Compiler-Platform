"""Closed, storage-neutral Phase 3 input contracts."""
import json
from canonical_contract import build_schema as canonical_schema
from phase1_contract import ROOT, array, integer, record, use


def build_schema():
    defs = canonical_schema()["$defs"]
    text = use("text")
    digest = {"type": "string", "pattern": r"^sha256:[0-9a-f]{64}(?![\s\S])"}
    defs["base"] = record({"sequence": integer(), "digest": digest, "journalDigest": digest})
    defs["migration"] = record({"id": use("id"), "mode": {"enum": ["NONE", "REQUIRED"]},
        "compatibility": {"enum": ["BACKWARD", "BREAKING", "UNKNOWN"]}, "irreversible": {"type": "boolean"},
        "steps": array(text), "preconditions": array(text), "verification": array(text),
        "recovery": text, "observations": array(digest)})
    defs["operation"] = {"oneOf": [
        record({"op": {"const": "ADD"}, "node": use("node")}),
        record({"op": {"const": "REVISE"}, "id": use("id"), "expectedRevision": integer(1), "node": use("node")}),
        record({"op": {"const": "DEPRECATE"}, "id": use("id"), "expectedRevision": integer(1)}),
        record({"op": {"const": "SUPERSEDE"}, "id": use("id"), "expectedRevision": integer(1), "replacement": use("ref")}),
    ]}
    # Source and receipt shapes are checked against the existing Phase 2 importer.
    defs["sourceReceipt"] = record({"source": {"type": "object"}, "receipt": {"type": "object"}})
    defs["observation"] = record({"id": use("id"), "snapshotDigest": digest, "subjects": array(use("ref"), 1),
        "result": {"enum": ["PASS", "FAIL", "BLOCKED", "NOT_RUN"]}, "artifactDigest": digest})
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "urn:acp:change:0.1.0",
        "title": "ACP ChangeSet 0.1.0 proposal input; no storage or authority implementation",
        **record({"changeVersion": {"const": "0.1.0"}, "id": use("id"), "author": text,
            "intent": text, "branch": use("id"), "base": use("base"),
            "operations": array(use("operation"), 1), "reads": array(use("ref")),
            "migration": use("migration"), "sources": array(use("sourceReceipt")),
            "parents": array(digest), "rollbackOf": {"oneOf": [integer(), {"type": "null"}]}}), "$defs": defs}


if __name__ == "__main__":
    (ROOT / "contracts/change.schema.json").write_text(json.dumps(build_schema(), indent=2) + "\n", encoding="utf-8")
