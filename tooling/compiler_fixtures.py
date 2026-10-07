"""Small synthetic authoring fixture for compiler boundary tests; not business approval."""
from canonical_fixtures import synthetic_approved


def small_model():
    def node(id, kind, data):
        return {"id": id, "revision": 1, "kind": kind, "name": id,
                "lifecycle": "APPROVED", "steward": "fixture:team",
                "origins": [{"source": "fixture", "locator": id, "actor": "fixture:author", "actorType": "HUMAN"}],
                "basis": [] if kind == "Decision" else [{"id": "DEC-ROOT", "revision": 1}], "data": data}
    return synthetic_approved({"modelVersion": "0.2.0", "applicationId": "APP-COMPILER-TEST",
        "snapshotId": "SNAP-COMPILER-TEST", "nodes": [
            node("DEC-ROOT", "Decision", {"statement": "Synthetic compiler test only", "strength": "REQUIRED", "rationale": "Boundary tests", "alternatives": ["first", "second"]}),
            node("PARAM-A", "Parameter", {"type": {"kind": "Integer"}, "value": "1"}),
            node("PARAM-B", "Parameter", {"type": {"kind": "Integer"}, "value": "2"}),
            node("REQ-TEST", "Requirement", {"statement": "Synthetic test obligation", "priority": "MUST", "acceptance": [{"id": "AC-TEST", "revision": 1}]}),
            node("AC-TEST", "AcceptanceCriterion", {"requirement": {"id": "REQ-TEST", "revision": 1}, "scenario": "Synthetic acceptance"}),
        ], "issues": [], "approvals": []})


def build_vectors():
    """Regenerate ONLY Phase 4 synthetic target vectors; never canonical fixtures."""
    from canonical_json import load
    from compiler_core import compile_pipeline
    from compiler_contracts import Success, VERSION, TARGET
    from compiler_reference import fixture_context
    from validate import ROOT
    result = {"version": VERSION, "target": TARGET, "domains": {}}
    for name in ("payment.json", "case-management.json"):
        source, context = fixture_context(synthetic_approved(load(ROOT / "test-corpus/phase1" / name)))
        compilation = compile_pipeline(source, context)
        if not isinstance(compilation.result, Success):
            raise ValueError("Synthetic vector compilation failed")
        result["domains"][name] = {"artifactPlanDigest": compilation.result.output_digest,
            "obligations": len(compilation.result.obligations), "artifacts": len(compilation.result.output.artifacts)}
    return result


if __name__ == "__main__":
    import json
    from validate import ROOT
    (ROOT / "test-corpus/compiler/vectors.json").write_text(json.dumps(build_vectors(), indent=2) + "\n", encoding="utf-8")
