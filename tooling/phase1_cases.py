"""Portable authored negative/positive cases for the current semantic model."""
import json
from pathlib import Path
from phase1_contract import KINDS
from reference_models import models, ref, literal

ROOT = Path(__file__).resolve().parents[1]


def corpus():
    result = []
    def case(name, id, path, value, code, subject=None, covers=None, op="set"):
        result.append({"name": name, "base": "case-management.json", "mode": "draft", "covers": covers or [],
            "edits": [{"node": id, "op": op, "path": path, **({"value": value} if op != "delete" else {})}],
            "requiredDiagnostics": [{"code": "ACP-" + code, "subject": subject or id}]})
    sample = models()["case-management.json"]
    for kind in KINDS:
        n = next(n for n in sample["nodes"] if n["kind"] == kind)
        case("closed-shape-" + kind, n["id"], ["data", "frameworkImplementation"], "forbidden", "SHAPE", covers=[kind])
    scenarios = [
        ("ValueObject", "FLD-TITLE", "type", {"kind": "Value", "definition": ref("VO-TITLE")}, "DOMAIN", "VO-TITLE"),
        ("Relation", "REL-CASE-DOCUMENT", "targetCardinality", {"min": 2, "max": 1}, "CARDINALITY", None),
        ("Aggregate", "AGG-CASE", "root", ref("USER"), "AGGREGATE", None),
        ("TypeDefinition", "TYPE-CASE-CODE", "refinement", {"kind": "LENGTH", "min": 10, "max": 1}, "TYPE", None),
        ("AuthenticationModel", "AUTH-ACT-REVIEWER", "mechanisms", ["KNOWLEDGE"], "SECURITY", None),
        ("Permission", "PERM-CMD-REVIEW", "resource", ref("USER"), "SECURITY", None),
        ("Scope", "SCOPE-CASE", "mode", "GLOBAL", "TENANT", None),
        ("RoleAssignment", "ASSIGN-CASE", "actor", ref("CASE"), "KIND", None),
        ("PolicySet", "POLSET-CMD-REVIEW", "action", ref("CMD-ARCHIVE"), "SECURITY", None),
        ("DataClassification", "CLASS-SENSITIVE", "audit", "NONE", "PRIVACY", None),
        ("SessionPolicy", "SESSION-ACT-REVIEWER", "idleSeconds", 999999, "SECURITY", None),
        ("RatePolicy", "RATE-CMD-REVIEW", "burst", 101, "SECURITY", None),
        ("Retention", "RETENTION-CASE", "trigger", "CREATED", "PRIVACY", "LIFECYCLE-CASE"),
        ("DeletionPolicy", "DELETE-CASE", "fields", [ref("CASE-ID")], "PRIVACY", None),
        ("LegalHold", "HOLD-CASE", "condition", literal("String", "yes"), "TYPE", None),
        ("DataLifecycle", "LIFECYCLE-CASE", "retention", ref("CASE"), "KIND", None),
        ("Service", "SERVICE-TASKS", "operations", [ref("QUERY-TASKS")], "EXECUTION", "CMD-REVIEW"),
        ("Query", "QUERY-TASKS", "projection", [{"field": ref("OUTPUT-TASK-TEXT"), "value": literal("Boolean", True)}], "TYPE", None),
        ("UseCase", "UC-TASK", "input", ref("CASE"), "KIND", None),
        ("ExecutionStep", "STEP-CMD-REVIEW", "onFailure", "COMPENSATE", "EXECUTION", None),
        ("Transaction", "TX-TASK", "aggregate", ref("AGG-USER"), "EXECUTION", None),
        ("Failure", "FAIL-BUSINESS", "retryable", True, "RETRY", None),
        ("RetryPolicy", "RETRY-TASK", "failures", [ref("FAIL-BUSINESS")], "RETRY", None),
        ("IdempotencyPolicy", "IDEM-OPERATION", "keyType", {"kind": "Nullable", "item": {"kind": "String"}}, "RETRY", None),
        ("DeliveryPolicy", "DELIVERY-EVT-REVIEW", "windowSeconds", 999999, "DELIVERY", None),
        ("Schedule", "SCHEDULE-TASK", "timezone", "Unrecognized/Location", "SCHEDULE", None),
        ("Job", "JOB-TASK", "timeoutSeconds", 86400, "RETRY", None),
        ("Screen", "SCREEN-TASK", "accessibility", ref("TEST-TASK"), "KIND", None),
        ("Form", "FORM-TASK", "controls", [ref("FLD-TITLE")], "KIND", None),
        ("InputControl", "CONTROL-TEXT", "field", ref("CASE-ID"), "UI", None),
        ("Action", "ACTION-TASK", "permissions", [ref("PERM-CMD-REVIEW")], "UI", None),
        ("Wizard", "WIZARD-TASK", "steps", [ref("FORM-TASK")], "KIND", None),
        ("WizardStep", "WSTEP-INPUT", "requiresPrevious", True, "UI", "WIZARD-TASK"),
        ("Table", "TABLE-TASKS", "columns", [ref("CASE-ID")], "UI", None),
        ("Search", "SEARCH-TASKS", "filters", [ref("CASE")], "KIND", None),
        ("Filter", "FILTER-TEXT", "operator", "RANGE", "UI", None),
        ("ViewState", "VIEW-SUCCESS", "state", "ERROR", "UI", "SCREEN-TASK"),
        ("PermissionBoundary", "BOUNDARY-TASK", "denied", ref("VIEW-SUCCESS"), "UI", None),
        ("ResponsivePolicy", "RESPONSIVE-TASK", "preserveActions", False, "SHAPE", None),
        ("AccessibilityRequirement", "A11Y-TASK", "evidence", ref("EVID-TEST"), "QUALITY", None),
        ("Applicability", "APPLIES-ALL", "condition", literal("String", "yes"), "APPLICABILITY", None),
        ("EvidenceRequirement", "EVID-PERF", "methods", ["UNIT"], "QUALITY", "PERF-TASK"),
        ("TestRequirement", "TEST-TASK", "criterion", ref("CASE"), "KIND", None),
        ("PerformanceRequirement", "PERF-TASK", "threshold", "NaN", "QUALITY", None),
        ("ReliabilityRequirement", "RELIABILITY-TASK", "threshold", "101", "QUALITY", None),
        ("CompatibilityRequirement", "COMPATIBILITY-TASK", "currentVersion", "3", "QUALITY", None),
        ("ObservabilityRequirement", "OBSERVE-TASK", "subjects", [ref("CASE")], "KIND", None),
        ("Backup", "BACKUP-TASK", "retentionSeconds", 1, "RECOVERY", None),
        ("Recovery", "RECOVERY-TASK", "rpoSeconds", 1, "RECOVERY", None),
    ]
    for kind, id, key, value, code, subject in scenarios:
        case("contract-" + kind, id, ["data", key], value, code, subject, [kind])
    for filename in models():
        result.append({"name": "valid-" + filename, "base": filename, "mode": "draft", "covers": list(KINDS), "edits": [], "requiredDiagnostics": []})
    return result


if __name__ == "__main__":
    (ROOT / "test-corpus/phase1/cases.json").write_text(json.dumps(corpus(), indent=2) + "\n", encoding="utf-8")
