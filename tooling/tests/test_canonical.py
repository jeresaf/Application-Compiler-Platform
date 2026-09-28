import copy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_contract import build_schema
from canonical_fixtures import CORPUS, byte_vectors, synthetic_approved
from canonical_ir import (CanonicalError, MAP_ARRAYS, ORDERED_ARRAYS, ORDERED_REFS,
                          SCHEMA, SET_ARRAYS, SHAPES, admit, migrate_authoring,
                          normalize_candidate, validate_snapshot)
from canonical_json import MAX_BYTES, canonical_bytes, digest, load, loads
from reference_models import models
from validate import PHASE1_SCHEMA, ROOT


def node(id, kind, data):
    return {"id": id, "revision": 1, "kind": kind, "name": id, "lifecycle": "APPROVED",
            "steward": "fixture:team", "origins": [{"source": "fixture", "locator": id,
            "actor": "fixture:author", "actorType": "HUMAN"}],
            "basis": [] if kind == "Decision" else [{"id": "DEC-ROOT", "revision": 1}], "data": data}


def base_model(*nodes):
    decision = node("DEC-ROOT", "Decision", {"statement": "Synthetic canonical test",
        "strength": "REQUIRED", "rationale": "Test only", "alternatives": ["first", "second"]})
    return synthetic_approved({"modelVersion": "0.2.0", "applicationId": "APP-TEST",
                              "snapshotId": "SNAP-TEST", "nodes": [decision, *nodes], "issues": [], "approvals": []})


def parameter(id, typ, value):
    return node(id, "Parameter", {"type": typ, "value": value})


def find(snapshot, id):
    return next(n for n in snapshot["content"]["nodes"] if n["id"] == id)


class CanonicalTests(unittest.TestCase):
    def assert_ir_error(self, code, operation, *args):
        with self.assertRaises(CanonicalError) as caught:
            operation(*args)
        self.assertEqual("ACP-IR-" + code, caught.exception.code)

    def test_closed_schema_and_every_array_has_an_order_policy(self):
        SHAPES.check_schema(SCHEMA)
        self.assertEqual(SCHEMA, build_schema())
        defs = PHASE1_SCHEMA["$defs"]
        for kind in defs["node"]["properties"]["kind"]["enum"]:
            for name, prop in defs[kind].get("properties", {}).items():
                if prop.get("$ref") in {"#/$defs/refs", "#/$defs/nonemptyRefs"}:
                    continue
                if prop.get("type") == "array":
                    if prop["items"].get("$ref") == "#/$defs/ref":
                        continue
                    self.assertIn((kind, name), SET_ARRAYS | MAP_ARRAYS | ORDERED_ARRAYS | ORDERED_REFS)

    def test_portable_bytes_and_domain_separation(self):
        vectors = load(CORPUS / "byte-vectors.json")
        self.assertEqual(byte_vectors(), vectors)
        for case in vectors["positive"]:
            with self.subTest(case=case["name"]):
                value = loads(case["input"].encode("utf-8"))
                self.assertEqual(case["canonical"].encode("utf-8"), canonical_bytes(value))
                self.assertEqual(case["digest"], digest(value, "vector"))
                self.assertEqual(value, loads(canonical_bytes(value)))
        for case in vectors["negative"]:
            with self.subTest(case=case["name"]):
                with self.assertRaises((ValueError, UnicodeError, RecursionError)):
                    loads(case["input"].encode("utf-8"))
        self.assertEqual(3, len({digest({}, d) for d in ("canonical", "authoring", "vector")}))
        with self.assertRaises(ValueError):
            digest({}, "unregistered")

    def test_resource_and_in_memory_input_rejection(self):
        for raw in (b"\xff", b" " * (MAX_BYTES + 1)):
            with self.assertRaises((ValueError, UnicodeError)):
                loads(raw)
        for value in ({1: "value"}, {"s": "\ud800"}, {"n": 1.0}, {"n": 9007199254740992},
                      {"a": (1, 2)}, {"s": "x" * MAX_BYTES}):
            self.assert_ir_error("INPUT", normalize_candidate, value)
        cyclic = []
        cyclic.append(cyclic)
        self.assert_ir_error("INPUT", normalize_candidate, cyclic)

    def test_reference_domains_and_golden_hashes(self):
        manifest = load(CORPUS / "manifest.json")
        examples = {e["file"]: e for e in manifest["examples"]}
        kinds = set()
        for name, model in models().items():
            with self.subTest(domain=name):
                authoring = synthetic_approved(model)
                before = copy.deepcopy(authoring)
                actual = normalize_candidate(authoring)
                expected = load(CORPUS / name)
                self.assertEqual(expected, actual)
                self.assertEqual(examples[name]["contentDigest"], actual["contentDigest"])
                self.assertEqual(examples[name]["sourceDigest"], digest(authoring, "authoring"))
                validate_snapshot(loads(canonical_bytes(actual)))
                self.assertEqual(before, authoring)
                kinds.update(n["kind"] for n in actual["content"]["nodes"])
        self.assertEqual(set(PHASE1_SCHEMA["$defs"]["node"]["properties"]["kind"]["enum"]), kinds)

    def test_unordered_graph_and_attestation_reordering(self):
        model = synthetic_approved(models()["case-management.json"])
        expected = normalize_candidate(model)
        rng = random.Random(7001)
        for _ in range(3):
            rng.shuffle(model["nodes"])
            rng.shuffle(model["approvals"])
            for n in model["nodes"]:
                rng.shuffle(n["basis"])
                rng.shuffle(n["origins"])
                for key, value in n["data"].items():
                    if isinstance(value, list) and key != "value" and (n["kind"], key) not in ORDERED_REFS | ORDERED_ARRAYS:
                        rng.shuffle(value)
            model = {k: model[k] for k in reversed(model)}
            self.assertEqual(expected, normalize_candidate(model))

    def test_exact_values_nested_types_and_literal_key_safety(self):
        decimal = {"kind": "Decimal", "precision": 38, "scale": 18, "rounding": "REJECT"}
        collection = {"kind": "Set", "element": decimal, "minItems": 0, "maxItems": 10}
        named = node("TYPE-NUMBER", "TypeDefinition", {"base": decimal, "semantics": "REFINED",
                    "refinement": {"kind": "RANGE", "min": "-2.000", "max": "2.000"}})
        model = base_model(named,
            parameter("P-NUM", decimal, "1.230000000000000001"),
            parameter("P-ZERO", decimal, "-0.000"),
            parameter("P-SET", collection, ["1.00", "-0.0"]),
            parameter("P-LIST", {**collection, "kind": "List"}, ["1.00", "0.0"]),
            parameter("P-NAMED", {"kind": "Named", "definition": {"id": "TYPE-NUMBER", "revision": 1}}, "1.00"),
            parameter("P-TIME", {"kind": "Instant"}, "2026-09-28T10:00:00.000000Z"),
            parameter("P-NULL", {"kind": "Nullable", "item": decimal}, None))
        result = normalize_candidate(model)
        self.assertEqual("1.230000000000000001", find(result, "P-NUM")["data"]["value"])
        self.assertEqual("0", find(result, "P-ZERO")["data"]["value"])
        self.assertEqual(["0", "1"], find(result, "P-SET")["data"]["value"])
        self.assertEqual(["1", "0"], find(result, "P-LIST")["data"]["value"])
        self.assertEqual("1", find(result, "P-NAMED")["data"]["value"])
        self.assertEqual("2026-09-28T10:00:00Z", find(result, "P-TIME")["data"]["value"])
        self.assertEqual("-2", find(result, "TYPE-NUMBER")["data"]["refinement"]["min"])
        validate_snapshot(result)
        changed = copy.deepcopy(model)
        next(n for n in changed["nodes"] if n["id"] == "P-SET")["data"]["value"] = ["0", "1"]
        self.assertEqual(result, normalize_candidate(changed))
        next(n for n in changed["nodes"] if n["id"] == "P-LIST")["data"]["value"].reverse()
        self.assertNotEqual(result["contentDigest"], normalize_candidate(changed)["contentDigest"])
        next(n for n in changed["nodes"] if n["id"] == "P-SET")["data"]["value"] = ["1", "1.0"]
        self.assert_ir_error("SEMANTIC", normalize_candidate, changed)

    def test_value_records_preserve_absence_null_and_metadata_like_keys(self):
        cls = node("CLASS-PUBLIC", "DataClassification", {"level": "PUBLIC", "audit": "NONE",
            "encryptAtRest": False, "encryptInTransit": False, "export": "DENY", "redaction": "NONE"})
        vo = node("VO-RECORD", "ValueObject", {"equality": "STRUCTURAL"})
        fields = [node(key, "Field", {"owner": {"id": "VO-RECORD", "revision": 1},
            "type": {"kind": "Nullable", "item": {"kind": "String"}}, "optional": True,
            "classification": "PUBLIC", "classificationRef": {"id": "CLASS-PUBLIC", "revision": 1}})
                  for key in ("type", "value", "tag", "id", "revision")]
        value = {"tag": "literal", "type": "Set", "value": "ordinary text", "id": "missing", "revision": "99"}
        model = base_model(cls, vo, *fields, parameter("P-RECORD", {"kind": "Value",
                           "definition": {"id": "VO-RECORD", "revision": 1}}, value))
        original = normalize_candidate(model)
        self.assertEqual(value, find(original, "P-RECORD")["data"]["value"])
        model["nodes"][-1]["data"]["value"].pop("id")
        missing = normalize_candidate(model)
        model["nodes"][-1]["data"]["value"]["id"] = None
        self.assertNotEqual(missing["contentDigest"], normalize_candidate(model)["contentDigest"])

    def test_ordered_steps_and_operands_change_digest(self):
        model = synthetic_approved(models()["case-management.json"])
        original = normalize_candidate(model)
        usecase = next(n for n in model["nodes"] if n["kind"] == "UseCase")
        self.assertGreater(len(usecase["data"]["steps"]), 1)
        usecase["data"]["steps"].reverse()
        self.assertNotEqual(original["contentDigest"], normalize_candidate(model)["contentDigest"])
        expr = {"tag": "binary", "op": "gt", "left": {"tag": "literal", "type": {"kind": "Integer"}, "value": "1"},
                "right": {"tag": "literal", "type": {"kind": "Integer"}, "value": "2"}}
        model = base_model(node("APPLICABLE", "Applicability", {"condition": expr, "rationale": "Fixture",
                           "decision": {"id": "DEC-ROOT", "revision": 1}}))
        before = normalize_candidate(model)
        expr["left"], expr["right"] = expr["right"], expr["left"]
        model["nodes"][-1]["data"]["condition"] = expr
        self.assertNotEqual(before["contentDigest"], normalize_candidate(model)["contentDigest"])

    def test_quality_threshold_equivalence_and_bounded_expansion(self):
        model = synthetic_approved(models()["case-management.json"])
        n = next(n for n in model["nodes"] if n["kind"] == "PerformanceRequirement")
        n["data"]["threshold"] = "100"
        expected = normalize_candidate(model)
        n["data"]["threshold"] = "1e2"
        self.assertEqual(expected, normalize_candidate(model))
        n["data"]["threshold"] = "1e9999999"
        self.assert_ir_error("NORMAL", normalize_candidate, model)

    def test_tampering_unknown_fields_versions_features_and_invalid_refs(self):
        snapshot = normalize_candidate(base_model())
        cases = [
            (["content", "schemaVersion"], "0.1.1", "VERSION"),
            (["content", "semanticModelVersion"], "0.3.0", "VERSION"),
            (["content", "canonicalProfile"], "other", "VERSION"),
            (["content", "requiredFeatures"], ["unknown"], "FEATURE"),
            (["content", "database"], "framework", "SHAPE"),
            (["content", "nodes", 0, "data", "framework"], "unsafe", "SHAPE"),
            (["content", "nodes", 0, "lifecycle"], "PROPOSED", "SHAPE"),
            (["content", "nodes", 0, "basis"], [{"id": "MISSING", "revision": 1}], "SEMANTIC"),
            (["content", "nodes", 0, "name"], "Different", "DIGEST"),
        ]
        for path, value, code in cases:
            with self.subTest(path=path):
                candidate = copy.deepcopy(snapshot)
                at = candidate
                for key in path[:-1]:
                    at = at[key]
                at[path[-1]] = value
                self.assert_ir_error(code, validate_snapshot, candidate)
        candidate = copy.deepcopy(snapshot)
        candidate["content"]["nodes"].append(copy.deepcopy(candidate["content"]["nodes"][0]))
        self.assert_ir_error("SHAPE", validate_snapshot, candidate)

    def test_non_normal_content_cannot_be_resigned_into_acceptance(self):
        snapshot = normalize_candidate(base_model(parameter("P-NUM", {"kind": "Decimal", "precision": 5,
            "scale": 2, "rounding": "REJECT"}, "1")))
        for change in (lambda s: s["content"]["nodes"].reverse(),
                       lambda s: find(s, "P-NUM")["data"].update(value="1.00")):
            candidate = copy.deepcopy(snapshot)
            change(candidate)
            candidate["contentDigest"] = digest(candidate["content"], "canonical")
            self.assert_ir_error("NORMAL", validate_snapshot, candidate)

    def test_approval_closure_issues_and_untrusted_attestations(self):
        model = base_model()
        for mutate in (lambda m: m.update(approvals=[]), lambda m: m["nodes"][0].update(lifecycle="PROPOSED"),
                       lambda m: m["issues"].append({"id": "ISSUE-1", "kind": "AMBIGUITY", "question": "Unresolved",
                           "subjects": [{"id": "DEC-ROOT", "revision": 1}], "blocking": True, "resolution": "OPEN"})):
            candidate = copy.deepcopy(model)
            mutate(candidate)
            self.assert_ir_error("SEMANTIC", normalize_candidate, candidate)
        snapshot = normalize_candidate(model)
        self.assert_ir_error("AUTHORITY", admit, snapshot)
        for response in (False, None, 1, "APPROVED", {"approved": True}):
            self.assert_ir_error("AUTHORITY", admit, snapshot, lambda request: response)
        def unavailable(request):
            raise RuntimeError("private backend failure")
        self.assert_ir_error("AUTHORITY", admit, snapshot, unavailable)
        model["approvals"][0]["reviewer"] = "different:fixture-reviewer"
        model["snapshotId"] = "ANOTHER-EXPORT"
        self.assertEqual(snapshot, normalize_candidate(model))

    def test_digest_bound_admission_is_immutable_and_reapproval_is_required(self):
        model = base_model()
        snapshot = normalize_candidate(model)
        approved_digest = snapshot["contentDigest"]
        authority = lambda request: request["contentDigest"] == approved_digest
        admitted = admit(snapshot, authority)
        with self.assertRaises(FrozenInstanceError):
            admitted.content_digest = "different"
        before = admitted.content_bytes
        snapshot["content"]["nodes"][0]["name"] = "Mutation outside immutable result"
        self.assertEqual(before, admitted.content_bytes)
        model["nodes"][0]["data"]["statement"] = "Changed with same ID and revision"
        changed = normalize_candidate(model)
        self.assertNotEqual(approved_digest, changed["contentDigest"])
        self.assert_ir_error("AUTHORITY", admit, changed, authority)
        validate_snapshot(changed)

    def test_migration_is_explicit_nonmutating_and_never_carries_approval(self):
        source = base_model()
        before = copy.deepcopy(source)
        migration = migrate_authoring(source)
        self.assertEqual(before, source)
        self.assertTrue(migration["requiresApproval"])
        self.assertEqual(digest(source, "authoring"), migration["sourceDigest"])
        self.assertEqual([{"id": "DEC-ROOT", "revision": 1}], migration["preservedSubjects"])
        self.assertNotIn("approvals", migration["candidate"]["content"])
        self.assert_ir_error("AUTHORITY", admit, migration["candidate"])
        self.assert_ir_error("VERSION", migrate_authoring, source, "0.2.0")
        source["modelVersion"] = "0.1.0"
        self.assert_ir_error("VERSION", migrate_authoring, source)

    def test_unicode_identity_and_rename_continuity(self):
        model = base_model()
        model["nodes"][0]["name"] = "é"
        first = normalize_candidate(model)
        model["nodes"][0]["name"] = "é"
        second = normalize_candidate(model)
        self.assertNotEqual(first["contentDigest"], second["contentDigest"])
        self.assertEqual(first["content"]["nodes"][0]["id"], second["content"]["nodes"][0]["id"])
        self.assertEqual(first["content"]["nodes"][0]["kind"], second["content"]["nodes"][0]["kind"])

    def test_cli_is_explicit_about_authority_and_redacts_invalid_input(self):
        script = ROOT / "tooling/canonical_ir.py"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.json"
            for operation, raw, exit_code in (
                ("normalize", json.dumps(base_model()), 0),
                ("migrate", json.dumps(base_model()), 0),
                ("validate", json.dumps(normalize_candidate(base_model())), 0),
                ("validate", '{"secret":"DO-NOT-ECHO",}', 2),
                ("normalize", '{"modelVersion":"future"}', 1)):
                path.write_text(raw, encoding="utf-8")
                result = subprocess.run([sys.executable, str(script), operation, str(path)], capture_output=True, text=True)
                self.assertEqual(exit_code, result.returncode, result.stderr)
                output = json.loads(result.stdout)
                if operation == "validate" and exit_code == 0:
                    self.assertIs(False, output["authorityVerified"])
                self.assertNotIn("DO-NOT-ECHO", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
