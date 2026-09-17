import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate import validate, strict_load, ROOT, PHASE1_SCHEMA, PHASE1_SHAPES
from phase1_contract import build_schema, KINDS
from reference_models import models, ref, add, literal, field_expr
from type_semantics import Types, quantize
from security_semantics import policy_decision, disposal_allowed
from execution_semantics import local_occurrence, retry_horizon
from design_bindings import validate_bindings
from evidence_semantics import evaluate_evidence
from phase1_cases import corpus
from test_contracts import apply_edits


def find(model, id):
    return next(n for n in model["nodes"] if n["id"] == id)


class Phase1Tests(unittest.TestCase):
    def test_portable_extended_corpus(self):
        cases = strict_load(ROOT / "test-corpus/phase1/cases.json")
        self.assertEqual(corpus(), cases)
        self.assertEqual(len(cases), len({c["name"] for c in cases}))
        covered = set()
        for case in cases:
            with self.subTest(case=case["name"]):
                model = strict_load(ROOT / "test-corpus/phase1" / case["base"])
                apply_edits(model, case["edits"])
                errors = validate(model, case["mode"])
                if not case["requiredDiagnostics"]:
                    self.assertEqual([], errors)
                else:
                    for expected in case["requiredDiagnostics"]:
                        self.assertIn((expected["code"], expected["subject"]), [(e["code"], e["subject"]) for e in errors], errors)
                    covered.update(case["covers"])
        self.assertEqual(set(KINDS), covered)

    def test_common_identity_basis_and_compile_approval_for_new_kinds(self):
        model = models()["case-management.json"]
        for n in model["nodes"]:
            n["lifecycle"] = "APPROVED"
            model["approvals"].append({"subject": ref(n["id"]), "reviewer": "fixture:reviewer", "evidence": "fixture:attestation"})
        self.assertEqual([], validate(model, "compile"))
        candidate = copy.deepcopy(model)
        find(candidate, "SCOPE-CASE")["lifecycle"] = "PROPOSED"
        self.assertIn(("ACP-LIFECYCLE", "SCOPE-CASE"), [(d["code"], d["subject"]) for d in validate(candidate, "compile")])
        find(candidate, "SCOPE-CASE")["basis"] = []
        self.assert_error(candidate, "BASIS", "SCOPE-CASE")

    def test_literal_value_records_are_not_semantic_nodes(self):
        model = models()["case-management.json"]
        for id in ("kind", "id", "revision"):
            add(model, id, "Field", {"owner": ref("VO-TITLE"), "type": {"kind": "String"}, "optional": False, "classification": "PUBLIC", "classificationRef": ref("CLASS-PUBLIC")})
        find(model, "PARAM-TITLE")["data"]["value"].update(kind="Identifier", id="row", revision="1")
        self.assertEqual([], validate(model))

    def test_generated_contract_and_fixtures_are_current(self):
        PHASE1_SHAPES.check_schema(PHASE1_SCHEMA)
        self.assertEqual(build_schema(), PHASE1_SCHEMA)
        for filename, model in models().items():
            self.assertEqual(model, strict_load(ROOT / "test-corpus/phase1" / filename))

    def test_both_domains(self):
        kinds = set()
        for filename, model in models().items():
            with self.subTest(domain=filename):
                before = copy.deepcopy(model)
                self.assertEqual([], validate(model))
                self.assertEqual(before, model)
                kinds.update(n["kind"] for n in model["nodes"])
        self.assertTrue(set(KINDS) <= kinds)

    def assert_error(self, model, code, subject):
        errors = validate(model)
        self.assertIn(("ACP-" + code, subject), [(e["code"], e["subject"]) for e in errors], errors)

    def test_domain_constraints(self):
        scenarios = [
            ("REL-CASE-DOCUMENT", "targetCardinality", {"min": 3, "max": 1}, "CARDINALITY"),
            ("REL-CASE-DOCUMENT", "sourceCardinality", {"min": 0, "max": 4}, "OWNERSHIP"),
            ("AGG-CASE", "root", ref("USER"), "AGGREGATE"),
            ("PARAM-TAGS", "value", ["review", "review"], "TYPE"),
            ("PARAM-CODE", "value", "", "TYPE"),
            ("PARAM-DATE", "value", "2026-02-30", "TYPE"),
            ("PARAM-INSTANT", "value", "2026-09-16T09:00:00", "TYPE"),
            ("PARAM-TITLE", "value", {"unknown": "unsafe"}, "TYPE"),
        ]
        for id, key, value, code in scenarios:
            with self.subTest(subject=id, key=key):
                model = models()["case-management.json"]
                find(model, id)["data"][key] = value
                self.assert_error(model, code, id)

    def test_precision_rounding_and_value_equality(self):
        typ = {"kind": "Decimal", "precision": 5, "scale": 2, "rounding": "HALF_EVEN"}
        self.assertEqual("1.24", quantize("1.245", typ))
        self.assertEqual("1.25", quantize("1.245", {**typ, "rounding": "HALF_UP"}))
        self.assertEqual("-1.24", quantize("-1.249", {**typ, "rounding": "DOWN"}))
        for value in ("1.245", "1000"):
            with self.assertRaises(ValueError):
                quantize(value, {**typ, "rounding": "REJECT"})
        model = models()["case-management.json"]
        types = Types({n["id"]: n for n in model["nodes"]}, lambda *args: None)
        self.assertEqual(types.value_key(typ, "1.20"), types.value_key(typ, "1.2"))
        self.assertNotEqual(types.value_key({"kind": "Identifier", "entity": ref("CASE")}, "1"), types.value_key({"kind": "Identifier", "entity": ref("USER")}, "1"))

    def test_presence_is_explicit(self):
        model = models()["case-management.json"]
        expression = {"tag": "binary", "op": "eq", "left": {"tag": "coalesce", "value": field_expr("FLD-NOTE"), "fallback": literal("String", "")}, "right": literal("String", "")}
        add(model, "INV-NOTE", "Invariant", {"resource": ref("CASE"), "predicate": expression, "enforcement": ["WRITE"]})
        self.assertEqual([], validate(model))
        expression["left"] = field_expr("FLD-NOTE")
        self.assert_error(model, "TYPE", "INV-NOTE")

    def test_security_and_privacy(self):
        scenarios = [
            ("SCOPE-CASE", "mode", "GLOBAL", "TENANT"),
            ("AUTH-ACT-REVIEWER", "mechanisms", ["KNOWLEDGE"], "SECURITY"),
            ("CLASS-SENSITIVE", "encryptAtRest", False, "PRIVACY"),
            ("CLASS-SECRET", "redaction", "MASK", "PRIVACY"),
            ("DELETE-CASE", "afterSeconds", 0, "PRIVACY"),
            ("DELETE-CASE", "fields", [ref("CASE-ID")], "PRIVACY"),
            ("SESSION-ACT-REVIEWER", "idleSeconds", 99999, "SECURITY"),
            ("RATE-CMD-REVIEW", "burst", 101, "SECURITY"),
        ]
        for id, key, value, code in scenarios:
            with self.subTest(subject=id):
                model = models()["case-management.json"]
                find(model, id)["data"][key] = value
                self.assert_error(model, code, "LIFECYCLE-CASE" if id == "DELETE-CASE" and key == "afterSeconds" else id)
        for outcomes in ([('ALLOW', True), ('DENY', True)], [('DENY', True), ('ALLOW', True)]):
            self.assertEqual("DENY", policy_decision(outcomes, True, True))
        self.assertEqual("DENY", policy_decision([('ALLOW', True)], True, False))
        self.assertEqual("DENY", policy_decision([('ALLOW', None)], True, True))
        self.assertEqual("ALLOW", policy_decision([('ALLOW', True), ('DENY', False)], True, True))
        self.assertFalse(disposal_allowed(999999, 86400, 172800, True))
        self.assertTrue(disposal_allowed(172800, 86400, 172800, False))

    def test_execution_boundaries(self):
        scenarios = [
            ("CMD-REVIEW", "writes", [ref("USER")], "AGGREGATE"),
            ("FAIL-BUSINESS", "retryable", True, "RETRY"),
            ("RETRY-TASK", "failures", [ref("FAIL-BUSINESS")], "RETRY"),
            ("IDEM-OPERATION", "windowSeconds", 1, "RETRY"),
            ("DELIVERY-EVT-REVIEW", "windowSeconds", 999999, "DELIVERY"),
            ("TX-TASK", "aggregate", ref("AGG-USER"), "EXECUTION"),
            ("STEP-CMD-REVIEW", "onFailure", "COMPENSATE", "EXECUTION"),
            ("SCHEDULE-TASK", "timezone", "No/Such_Zone", "SCHEDULE"),
        ]
        for id, key, value, code in scenarios:
            with self.subTest(subject=id):
                model = models()["case-management.json"]
                find(model, id)["data"][key] = value
                self.assert_error(model, code, "JOB-TASK" if id == "IDEM-OPERATION" else id)

    def test_dst_and_retry_horizon(self):
        model = models()["case-management.json"]
        schedule = {**find(model, "SCHEDULE-TASK")["data"], "timezone": "Europe/London"}
        self.assertIsNone(local_occurrence("2026-03-29T01:30:00", schedule))
        with self.assertRaises(ValueError):
            local_occurrence("2026-03-29T01:30:00", {**schedule, "gap": "REJECT"})
        early = local_occurrence("2026-10-25T01:30:00", schedule)
        late = local_occurrence("2026-10-25T01:30:00", {**schedule, "overlap": "LATER"})
        self.assertEqual(3600, (late - early).total_seconds())
        with self.assertRaises(ValueError):
            local_occurrence("2026-10-25T01:30:00", {**schedule, "overlap": "REJECT"})
        self.assertEqual(93, retry_horizon(find(model, "RETRY-TASK")["data"], 30))

    def test_task_ui_rejects_entity_bindings_and_missing_states(self):
        scenarios = [
            ("CONTROL-TEXT", "field", ref("CASE-ID")),
            ("TABLE-TASKS", "columns", [ref("CASE-ID")]),
            ("FILTER-TEXT", "field", ref("CASE-ID")),
            ("WSTEP-INPUT", "requiresPrevious", True),
            ("ACTION-TASK", "permissions", [ref("PERM-CMD-REVIEW")]),
        ]
        for id, key, value in scenarios:
            with self.subTest(subject=id):
                model = models()["case-management.json"]
                find(model, id)["data"][key] = value
                self.assert_error(model, "UI", "WIZARD-TASK" if id == "WSTEP-INPUT" else id)

    def test_independent_design_catalogues(self):
        model = models()["case-management.json"]
        before = copy.deepcopy(model)
        for catalogue in ("fixture:compact", "fixture:spacious"):
            binding = {"version": "0.1.0", "applicationId": model["applicationId"], "snapshotId": model["snapshotId"], "catalogue": catalogue, "catalogueVersion": "1", "bindings": [{"subject": ref("SCREEN-TASK"), "component": "task-page"}]}
            self.assertEqual([], validate_bindings(binding, model))
            binding["bindings"][0]["subject"] = ref("CASE")
            self.assertEqual(["ACP-DESIGN-KIND"], validate_bindings(binding, model))
            binding["css"] = "framework-leak"
            self.assertEqual(["ACP-DESIGN-SHAPE"], validate_bindings(binding, model))
        self.assertEqual(before, model)

    def test_quality_constraints(self):
        scenarios = [
            ("PERF-TASK", "threshold", "NaN", "QUALITY"),
            ("PERF-TASK", "comparison", "GTE", "QUALITY"),
            ("RELIABILITY-TASK", "threshold", "101", "QUALITY"),
            ("COMPATIBILITY-TASK", "currentVersion", "3", "QUALITY"),
            ("BACKUP-TASK", "retentionSeconds", 1, "RECOVERY"),
            ("RECOVERY-TASK", "rpoSeconds", 1, "RECOVERY"),
            ("APPLIES-ALL", "condition", literal("String", "yes"), "APPLICABILITY"),
        ]
        for id, key, value, code in scenarios:
            with self.subTest(subject=id):
                model = models()["case-management.json"]
                find(model, id)["data"][key] = value
                self.assert_error(model, code, id)

    def test_evidence_binding_freshness_and_measurement(self):
        model = models()["case-management.json"]
        context = {"snapshotId": model["snapshotId"], "artifactDigest": "sha256:" + "a" * 64, "configurationDigest": "sha256:" + "b" * 64, "toolDigest": "sha256:" + "c" * 64, "profileVersion": "fixture:1"}
        record = {"version": "0.1.0", "requirement": ref("EVID-PERF"), "obligation": ref("PERF-TASK"), "subjects": [ref("QUERY-TASKS")], **context, "method": "PERFORMANCE", "observedAt": "2026-09-16T00:00:00Z", "result": "PASS", "measurements": [{"metric": "P95_LATENCY_MS", "value": "450", "samples": 100}], "workload": find(model, "PERF-TASK")["data"]["workload"]}
        evaluate = lambda records: evaluate_evidence(model, "PERF-TASK", records, context, "2026-09-16T01:00:00Z")
        self.assertEqual("PASS", evaluate([record])["status"])
        for key, value, code in [("observedAt", "2026-09-14T00:00:00Z", "FRESHNESS"), ("observedAt", "2026-09-17T00:00:00Z", "FRESHNESS"), ("artifactDigest", "sha256:" + "d" * 64, "BINDING"), ("result", "NOT_RUN", "RESULT"), ("method", "UNIT", "METHOD"), ("measurements", [{"metric": "P95_LATENCY_MS", "value": "501", "samples": 100}], "MEASUREMENT")]:
            with self.subTest(key=key, value=value):
                self.assertIn("ACP-EVIDENCE-" + code, evaluate([{**record, key: value}])["diagnostics"])
        self.assertEqual("BLOCKED", evaluate([])["status"])
        find(model, "APPLIES-ALL")["data"]["condition"] = literal("Boolean", False)
        self.assertEqual("BLOCKED", evaluate([])["status"])
        self.assertEqual("NOT_APPLICABLE", evaluate_evidence(model, "PERF-TASK", [], context, "2026-09-16T01:00:00Z", applicability_approved=True)["status"])


if __name__ == "__main__":
    unittest.main()
