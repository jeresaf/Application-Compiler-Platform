"""Explicitly synthetic Phase 2 fixtures; never an approval service."""
import copy
import json

from canonical_ir import normalize_candidate
from canonical_json import PROFILE, digest
from reference_models import models
from validate import ROOT

CORPUS = ROOT / "test-corpus/canonical"


def synthetic_approved(model):
    result = copy.deepcopy(model)
    result["approvals"] = []
    for node in result["nodes"]:
        node["lifecycle"] = "APPROVED"
        result["approvals"].append({"subject": {"id": node["id"], "revision": node["revision"]},
                                    "reviewer": "fixture:reviewer", "evidence": "fixture:not-real-approval"})
    return result


def byte_vectors():
    # Expected byte strings are deliberately specified, not produced by the encoder.
    pairs = [
        ("object-key-order", '{ "z": 1, "a": 2 }', '{"a":2,"z":1}'),
        ("integer-key-order", '{"2":2,"10":10,"1":1}', '{"1":1,"10":10,"2":2}'),
        ("safe-integers", '[9007199254740991,-9007199254740991,-0]', '[9007199254740991,-9007199254740991,0]'),
        ("primitives", '[true,false,null,"1.00"]', '[true,false,null,"1.00"]'),
        ("escaped-controls", r'{"s":"\u000f\b\t\n\f\r\"\\\/"}', r'{"s":"\u000f\b\t\n\f\r\"\\/"}'),
        ("utf16-order", '{"\ue000":1,"\U0001f600":2,"a":3}', '{"a":3,"\U0001f600":2,"\ue000":1}'),
        ("unicode-preserved", r'{"s":"\u00e9","t":"e\u0301"}', '{"s":"é","t":"é"}'),
        ("unicode-separators", r'["\u2028","\u2029"]', '["\u2028","\u2029"]'),
        ("nested-order", '{"b":[{"z":0,"a":1},2,1],"a":{}}', '{"a":{},"b":[{"a":1,"z":0},2,1]}'),
    ]
    import hashlib
    prefix = ("ACP\x00" + PROFILE + "\x00vector\x00").encode("ascii")
    positive = [{"name": name, "input": raw, "canonical": expected,
                 "digest": "sha256:" + hashlib.sha256(prefix + expected.encode("utf-8")).hexdigest()}
                for name, raw, expected in pairs]
    negative = [
        ("duplicate", '{"a":1,"a":2}'), ("escaped-duplicate", r'{"a":1,"\u0061":2}'),
        ("unsafe-integer", '9007199254740992'), ("float-token", '1.0'), ("exponent-token", '1e0'),
        ("nonfinite", 'NaN'), ("infinite", '1e9999'), ("surrogate-value", r'"\ud800"'),
        ("surrogate-key", r'{"\udfff":1}'), ("bom", '\ufeff{}'), ("trailing", '{}{}'),
        ("depth", '[' * 49 + '0' + ']' * 49), ("leading-zero", '01'),
    ]
    return {"profile": PROFILE, "positive": positive,
            "negative": [{"name": name, "input": raw} for name, raw in negative]}


def main():
    CORPUS.mkdir(exist_ok=True)
    manifest = {"profile": PROFILE, "examples": []}
    for name, model in models().items():
        snapshot = normalize_candidate(synthetic_approved(model))
        (CORPUS / name).write_text(json.dumps(snapshot, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        manifest["examples"].append({"file": name, "contentDigest": snapshot["contentDigest"],
                                     "sourceDigest": digest(synthetic_approved(model), "authoring")})
    for name, value in (("manifest.json", manifest), ("byte-vectors.json", byte_vectors())):
        (CORPUS / name).write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
