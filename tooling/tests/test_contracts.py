import copy
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate import MAX_DEPTH, ROOT, SCHEMA, SHAPES, strict_load, validate


CORPUS = ROOT / "test-corpus" / "semantic"


def apply_edits(snapshot, edits):
    """Portable corpus edit notation, deliberately separate from ACP changes."""
    for edit in edits:
        obj = snapshot if edit["node"] is None else next(n for n in snapshot["nodes"] if n["id"] == edit["node"])
        for key in edit["path"][:-1]:
            obj = obj[key]
        key = edit["path"][-1]
        if edit["op"] == "set":
            obj[key] = copy.deepcopy(edit["value"])
        elif edit["op"] == "delete":
            del obj[key]
        elif edit["op"] == "append":
            obj[key].append(copy.deepcopy(edit["value"]))
        else:
            raise AssertionError("Unknown corpus edit operation")


class ContractTests(unittest.TestCase):
    def test_schema_and_kind_coverage(self):
        SHAPES.check_schema(SCHEMA)
        kinds = set(SCHEMA["$defs"]["node"]["properties"]["kind"]["enum"])
        sample = strict_load(CORPUS / "reference.json")
        self.assertEqual(kinds, {n["kind"] for n in sample["nodes"]})

    def test_portable_corpus(self):
        cases = strict_load(CORPUS / "cases.json")
        self.assertEqual(len(cases), len({c["name"] for c in cases}))
        for case in cases:
            with self.subTest(case=case["name"]):
                sample = strict_load(CORPUS / case["base"])
                apply_edits(sample, case["edits"])
                before = copy.deepcopy(sample)
                errors = validate(sample, case["mode"])
                pairs = lambda items: sorted((e["code"], e["subject"]) for e in items)
                self.assertEqual(pairs(case["expected"]), pairs(errors), errors)
                self.assertEqual(sample, before, "Validation mutated the authoring snapshot")
                self.assertEqual(errors, validate(sample, case["mode"]))

    def test_order_invariance(self):
        sample = strict_load(CORPUS / "approved.json")
        rng = random.Random(413)
        for _ in range(20):
            rng.shuffle(sample["nodes"])
            rng.shuffle(sample["approvals"])
            sample = {k: sample[k] for k in reversed(list(sample))}
            self.assertEqual([], validate(sample, "compile"))

    def test_invalid_graph_reordering_preserves_semantic_diagnostics(self):
        sample = strict_load(CORPUS / "reference.json")
        case = next(c for c in strict_load(CORPUS / "cases.json") if c["name"] == "ambiguous-transition")
        apply_edits(sample, case["edits"])
        meaning = lambda errors: sorted((e["code"], e["subject"], e["message"]) for e in errors)
        expected = meaning(validate(sample))
        self.assertEqual(2, len(expected))
        rng = random.Random(731)
        for _ in range(10):
            rng.shuffle(sample["nodes"])
            self.assertEqual(expected, meaning(validate(sample)))

    def test_diagnostic_locations_are_actionable(self):
        sample = strict_load(CORPUS / "reference.json")
        index = next(i for i, n in enumerate(sample["nodes"]) if n["id"] == "PARAM-ZERO")
        sample["nodes"][index]["data"]["value"] = "DO-NOT-ECHO-THIS"
        errors = validate(sample)
        self.assertEqual(1, len(errors))
        self.assertEqual("ACP-TYPE", errors[0]["code"])
        self.assertEqual("PARAM-ZERO", errors[0]["subject"])
        self.assertEqual(f"/nodes/{index}/data/value", errors[0]["path"])
        self.assertNotIn("DO-NOT-ECHO-THIS", json.dumps(errors))

    def test_rename_preserves_identity_and_requires_revision_updates(self):
        sample = strict_load(CORPUS / "reference.json")
        entity = next(n for n in sample["nodes"] if n["id"] == "ENT-MEMBER")
        entity["name"] = "Account holder"
        entity["revision"] = 2
        errors = validate(sample)
        self.assertTrue(errors)
        self.assertEqual({"ACP-REF"}, {e["code"] for e in errors})

        def update(value):
            if isinstance(value, dict):
                if set(value) == {"id", "revision"} and value["id"] == "ENT-MEMBER":
                    value["revision"] = 2
                for item in value.values():
                    update(item)
            elif isinstance(value, list):
                for item in value:
                    update(item)
        update(sample)
        self.assertEqual([], validate(sample))
        self.assertEqual("ENT-MEMBER", entity["id"])

    def test_missing_fields_and_unknown_properties_fail_closed(self):
        sample = strict_load(CORPUS / "reference.json")
        for node in sample["nodes"]:
            for field in ("origins", "basis", "data", "lifecycle", "revision"):
                candidate = copy.deepcopy(sample)
                current = next(n for n in candidate["nodes"] if n["id"] == node["id"])
                del current[field]
                with self.subTest(kind=node["kind"], missing=field):
                    self.assertEqual({"ACP-SHAPE"}, {e["code"] for e in validate(candidate)})
            candidate = copy.deepcopy(sample)
            next(n for n in candidate["nodes"] if n["id"] == node["id"])["data"]["targetCode"] = "DO-NOT-ECHO-THIS"
            with self.subTest(kind=node["kind"], unexpected="targetCode"):
                errors = validate(candidate)
                self.assertEqual({"ACP-SHAPE"}, {e["code"] for e in errors})
                self.assertNotIn("DO-NOT-ECHO-THIS", json.dumps(errors))

    def test_strict_input_and_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":1e9999}', '[' * (MAX_DEPTH + 1) + '0' + ']' * (MAX_DEPTH + 1)):
                path.write_text(raw, encoding="utf-8")
                with self.subTest(raw=raw[:20]):
                    with self.assertRaises(ValueError):
                        strict_load(path)
            path.write_text('{"password":"DO-NOT-ECHO-THIS",}', encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "tooling" / "validate.py"), str(path)], capture_output=True, text=True)
            self.assertEqual(2, result.returncode, result.stderr)
            self.assertEqual("ACP-INPUT", json.loads(result.stdout)["diagnostics"][0]["code"])
            self.assertNotIn("DO-NOT-ECHO-THIS", result.stdout + result.stderr)
        for mode, expected in (("draft", 0), ("compile", 1)):
            result = subprocess.run([sys.executable, str(ROOT / "tooling" / "validate.py"), str(CORPUS / "reference.json"), "--mode", mode], capture_output=True, text=True)
            self.assertEqual(expected, result.returncode, result.stderr)
            self.assertEqual("kernel", json.loads(result.stdout)["scope"])


if __name__ == "__main__":
    unittest.main()
