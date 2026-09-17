"""Authoring helpers for the closed Phase 1 0.2 schema, not a DSL or core runtime."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def use(name):
    return {"$ref": "#/$defs/" + name}


def enum(*values):
    return {"enum": list(values)}


def integer(minimum=0, maximum=9007199254740991):
    return {"type": "integer", "minimum": minimum, "maximum": maximum}


def array(item, minimum=0, unique=True):
    return {"type": "array", "items": item, "minItems": minimum, "uniqueItems": unique}


def link(*kinds):
    return {**use("ref"), "x-acp-targetKinds": list(kinds)}


def links(*kinds, minimum=0):
    return array(link(*kinds), minimum)


def record(required, optional=None):
    return {"type": "object", "additionalProperties": False,
            "required": list(required), "properties": {**required, **(optional or {})}}


TEXT = use("text")
BOOL = {"type": "boolean"}
TYPE = use("semanticType")
EXPR = use("expression")
CARD = record({"min": integer(), "max": {"oneOf": [integer(), {"const": "UNBOUNDED"}]}})
NUMERIC = {"precision": integer(1, 38), "scale": integer(0, 18), "rounding": enum("REJECT", "HALF_EVEN", "HALF_UP", "DOWN")}
KINDS = {
    "ValueObject": record({"equality": enum("STRUCTURAL")}),
    "Relation": record({"source": link("Entity"), "target": link("Entity"),
        "sourceCardinality": CARD, "targetCardinality": CARD,
        "ownership": enum("REFERENCE", "COMPOSITION"), "onDelete": enum("RESTRICT", "DETACH", "DELETE_OWNED")}),
    "Aggregate": record({"root": link("Entity"), "members": links("Entity", minimum=1),
        "invariants": links("Invariant"), "consistency": enum("ATOMIC")}),
    "TypeDefinition": record({"base": TYPE, "semantics": enum("NOMINAL", "REFINED"),
        "refinement": {"oneOf": [record({"kind": enum("NONE")}),
            record({"kind": enum("RANGE"), "min": TEXT, "max": TEXT}),
            record({"kind": enum("LENGTH"), "min": integer(), "max": integer()})]}}),
}
KINDS.update({
    "AuthenticationModel": record({"actor": link("Actor"), "assurance": enum("SINGLE_FACTOR", "MULTI_FACTOR"), "mechanisms": array(enum("KNOWLEDGE", "POSSESSION", "EXTERNAL_ASSERTION"), 1)}),
    "Permission": record({"actor": link("Actor"), "resource": link("Entity"), "action": link("Command", "Query")}),
    "Scope": record({"actor": link("Actor"), "resource": link("Entity"), "mode": enum("GLOBAL", "SAME_TENANT")}, {"actorTenant": link("Field"), "resourceTenant": link("Field")}),
    "RoleAssignment": record({"role": link("Role"), "actor": link("Actor"), "scope": link("Scope"), "principal": TEXT}),
    "PolicySet": record({"resource": link("Entity"), "action": link("Command", "Query"), "policies": links("Policy", minimum=1), "combining": enum("DENY_OVERRIDES"), "default": enum("DENY")}),
    "DataClassification": record({"level": enum("PUBLIC", "INTERNAL", "SENSITIVE", "SECRET"), "audit": enum("NONE", "WRITE", "READ_WRITE"), "encryptAtRest": BOOL, "encryptInTransit": BOOL, "export": enum("DENY", "PERMISSION_REQUIRED"), "redaction": enum("NONE", "MASK", "OMIT")}),
    "SessionPolicy": record({"authentication": link("AuthenticationModel"), "idleSeconds": integer(1), "absoluteSeconds": integer(1), "reauthSeconds": integer(1)}),
    "RatePolicy": record({"permission": link("Permission"), "requests": integer(1), "windowSeconds": integer(1), "burst": integer(1), "partition": enum("ACTOR", "TENANT")}),
    "Retention": record({"resource": link("Entity"), "trigger": enum("CREATED", "CLOSED"), "minimumSeconds": integer()}),
    "DeletionPolicy": record({"resource": link("Entity"), "trigger": enum("CREATED", "CLOSED"), "mode": enum("DELETE", "ANONYMIZE", "PRESERVE"), "afterSeconds": integer(), "fields": links("Field"), "holdBehavior": enum("BLOCK")}),
    "LegalHold": record({"resource": link("Entity"), "condition": EXPR, "release": link("Permission")}),
    "DataLifecycle": record({"resource": link("Entity"), "retention": link("Retention"), "deletion": link("DeletionPolicy"), "holds": links("LegalHold")}),
})
KINDS.update({
    "Service": record({"operations": links("Command", "Query", minimum=1)}),
    "Query": record({"resource": link("Entity"), "scope": link("Scope"), "result": TYPE, "projection": array(record({"field": link("Field"), "value": EXPR}), 1), "paginated": BOOL, "maximumResults": integer(1, 10000)}),
    "UseCase": record({"service": link("Service"), "steps": links("ExecutionStep", minimum=1), "input": link("ValueObject"), "output": link("ValueObject")}),
    "ExecutionStep": record({"owner": link("UseCase"), "operation": link("Command", "Query"), "onFailure": enum("STOP", "COMPENSATE")}, {"compensation": link("Command"), "transaction": link("Transaction")}),
    "Transaction": record({"aggregate": link("Aggregate"), "commands": links("Command", minimum=1), "consistency": enum("ATOMIC"), "onFailure": enum("ROLLBACK")}),
    "Failure": record({"code": TEXT, "category": enum("BUSINESS", "TRANSIENT", "SECURITY"), "retryable": BOOL}),
    "RetryPolicy": record({"failures": links("Failure", minimum=1), "maxAttempts": integer(1, 20), "initialSeconds": integer(1, 86400), "maxDelaySeconds": integer(1, 604800), "multiplier": integer(1, 4)}),
    "IdempotencyPolicy": record({"scope": link("Entity"), "keyType": TYPE, "windowSeconds": integer(1), "replay": enum("RETURN_RESULT"), "conflict": enum("REJECT_DIFFERENT_INPUT")}),
    "DeliveryPolicy": record({"event": link("Event"), "guarantee": enum("AT_MOST_ONCE", "AT_LEAST_ONCE"), "ordering": enum("NONE", "PER_AGGREGATE"), "windowSeconds": integer(1)}, {"deduplication": link("IdempotencyPolicy")}),
    "Schedule": {"oneOf": [record({"mode": enum("INTERVAL"), "intervalSeconds": integer(1)}), record({"mode": enum("LOCAL_DAILY"), "localTime": TEXT, "timezone": TEXT, "tzdbVersion": TEXT, "gap": enum("SKIP", "REJECT"), "overlap": enum("EARLIER", "LATER", "REJECT")})]},
    "Job": record({"useCase": link("UseCase"), "schedule": link("Schedule"), "retry": link("RetryPolicy"), "idempotency": link("IdempotencyPolicy"), "timeoutSeconds": integer(1)}),
})
UI_CHECKS = array(enum("LABELS", "KEYBOARD", "FOCUS", "ERROR_ANNOUNCEMENT"), 4)
KINDS.update({
    "Screen": record({"task": link("UseCase"), "content": links("Form", "Wizard", "Table", "Search", minimum=1), "actions": links("Action", minimum=1), "states": links("ViewState", minimum=4), "boundary": link("PermissionBoundary"), "responsive": link("ResponsivePolicy"), "accessibility": link("AccessibilityRequirement")}),
    "Form": record({"useCase": link("UseCase"), "controls": links("InputControl", minimum=1), "submit": link("Action")}),
    "InputControl": record({"form": link("Form"), "field": link("Field"), "label": TEXT, "errorMessage": TEXT, "required": BOOL, "purpose": enum("TEXT", "MULTILINE", "DATE", "CHOICE")}),
    "Action": record({"useCase": link("UseCase"), "permissions": links("Permission", minimum=1), "label": TEXT, "confirmation": enum("NONE", "REQUIRED")}),
    "Wizard": record({"screen": link("Screen"), "steps": links("WizardStep", minimum=1)}),
    "WizardStep": record({"wizard": link("Wizard"), "form": link("Form"), "requiresPrevious": BOOL}),
    "Table": record({"query": link("Query"), "columns": links("Field", minimum=1), "emptyMessage": TEXT}),
    "Search": record({"query": link("Query"), "filters": links("Filter", minimum=1), "label": TEXT}),
    "Filter": record({"query": link("Query"), "field": link("Field"), "operator": enum("EQ", "CONTAINS", "RANGE"), "inputType": TYPE}),
    "ViewState": record({"screen": link("Screen"), "state": enum("EMPTY", "LOADING", "ERROR", "SUCCESS"), "message": TEXT}, {"recovery": link("Action")}),
    "PermissionBoundary": record({"actor": link("Actor"), "permissions": links("Permission", minimum=1), "denied": link("ViewState")}),
    "ResponsivePolicy": record({"screen": link("Screen"), "modes": array(enum("COMPACT", "EXPANDED"), 2), "preserveActions": {"const": True}, "preserveReadingOrder": {"const": True}}),
    "AccessibilityRequirement": record({"subjects": links("Screen", "Form", "InputControl", "Action", minimum=1), "checks": UI_CHECKS, "method": enum("AUTOMATED_AND_MANUAL")}),
})
METHODS = enum("UNIT", "INTEGRATION", "AUTHORIZATION", "E2E", "MIGRATION", "PERFORMANCE", "AUTO_A11Y", "MANUAL_A11Y", "RELIABILITY", "COMPATIBILITY", "OBSERVABILITY", "BACKUP", "RECOVERY")
KINDS.update({
    "Applicability": record({"condition": EXPR, "rationale": TEXT, "decision": link("Decision")}),
    "EvidenceRequirement": record({"subjects": links(minimum=1), "methods": array(METHODS, 1), "maxAgeSeconds": integer(1), "applicability": link("Applicability")}),
    "TestRequirement": record({"criterion": link("AcceptanceCriterion"), "subjects": links(minimum=1), "level": enum("UNIT", "INTEGRATION", "AUTHORIZATION", "E2E", "MIGRATION"), "evidence": link("EvidenceRequirement")}),
    "PerformanceRequirement": record({"subject": link("Query", "UseCase"), "metric": enum("P95_LATENCY_MS", "MAX_MEMORY_MB", "THROUGHPUT_PER_SECOND"), "comparison": enum("LTE", "GTE"), "threshold": TEXT, "workload": record({"concurrency": integer(1), "records": integer(), "durationSeconds": integer(1), "minimumSamples": integer(1)}), "evidence": link("EvidenceRequirement")}),
    "ReliabilityRequirement": record({"subject": link("Service", "UseCase", "Job"), "metric": enum("AVAILABILITY_PERCENT", "FAILURE_PERCENT"), "threshold": TEXT, "windowSeconds": integer(60), "evidence": link("EvidenceRequirement")}),
    "CompatibilityRequirement": record({"subject": link("Command", "Query", "Event", "UseCase"), "policy": enum("BACKWARD"), "supportedVersions": array(TEXT, 2), "currentVersion": TEXT, "windowSeconds": integer(1), "evidence": link("EvidenceRequirement")}),
    "ObservabilityRequirement": record({"subjects": links("Command", "Query", "Service", "Job", minimum=1), "signals": array(enum("LOG", "METRIC", "TRACE", "AUDIT", "HEALTH", "READINESS"), 1), "correlation": enum("REQUIRED"), "redaction": enum("CLASSIFICATION"), "evidence": link("EvidenceRequirement")}),
    "Backup": record({"resources": links("Entity", minimum=1), "intervalSeconds": integer(1), "retentionSeconds": integer(1), "encrypted": {"const": True}, "evidence": link("EvidenceRequirement")}),
    "Recovery": record({"backup": link("Backup"), "rpoSeconds": integer(), "rtoSeconds": integer(1), "restoreTestIntervalSeconds": integer(1), "evidence": link("EvidenceRequirement")}),
})
KINDS["AccessibilityRequirement"]["required"].append("evidence")
KINDS["AccessibilityRequirement"]["properties"]["evidence"] = link("EvidenceRequirement")


def build_schema():
    schema = json.loads((ROOT / "contracts/kernel.schema.json").read_text(encoding="utf-8"))
    schema["$id"] = "urn:acp:phase1:0.2.0"
    schema["title"] = "ACP Phase 1 complete bounded authoring model (not Canonical IR)"
    schema["properties"]["modelVersion"] = {"const": "0.2.0"}
    defs = schema["$defs"]
    scalar = record({"kind": enum("Boolean", "String", "Integer", "Email", "SecretReference", "Date", "Instant", "LocalDateTime", "Duration")})
    defs["semanticType"] = {"oneOf": [scalar,
        record({"kind": enum("Decimal"), **NUMERIC}),
        record({"kind": enum("Money"), "currency": {"type": "string", "pattern": "^[A-Z]{3}(?![\\s\\S])"}, **NUMERIC}),
        record({"kind": enum("Identifier"), "entity": link("Entity")}),
        record({"kind": enum("Value"), "definition": link("ValueObject")}),
        record({"kind": enum("Named"), "definition": link("TypeDefinition")}),
        record({"kind": enum("Nullable"), "item": TYPE}),
        record({"kind": enum("List", "Set"), "element": TYPE, "minItems": integer(0, 10000), "maxItems": integer(0, 10000)})]}
    defs["literalValue"] = {"oneOf": [{"type": ["string", "boolean", "null"]},
        {"type": "array", "items": use("literalValue")},
        {"type": "object", "additionalProperties": use("literalValue")}]}
    defs["expression"]["oneOf"][-1]["properties"]["op"] = enum("eq", "identityEq", "gt", "add", "and")
    defs["expression"]["oneOf"] += [
        record({"tag": enum("present"), "binding": enum("resource", "actor"), "ref": link("Field")}),
        record({"tag": enum("coalesce"), "value": EXPR, "fallback": EXPR}),
        record({"tag": enum("size"), "value": EXPR}),
        record({"tag": enum("contains"), "collection": EXPR, "value": EXPR})]
    defs["field"]["properties"]["owner"] = link("Entity", "ValueObject")
    extensions = {
        "entity": ({"tenancy": enum("GLOBAL", "TENANT_ROOT", "SCOPED")}, {}),
        "field": ({"classificationRef": link("DataClassification")}, {"exportPermission": link("Permission")}),
        "actor": ({"authentication": link("AuthenticationModel")}, {}),
        "role": ({"permissions": links("Permission", minimum=1)}, {}),
        "policy": ({"permission": link("Permission"), "scope": link("Scope")}, {}),
        "command": ({"aggregate": link("Aggregate"), "writes": links("Entity", minimum=1), "failures": links("Failure", minimum=1), "idempotency": link("IdempotencyPolicy")}, {}),
        "event": ({"delivery": link("DeliveryPolicy")}, {}),
    }
    for key, (required, optional) in extensions.items():
        defs[key]["required"] += list(required)
        defs[key]["properties"].update(required)
        defs[key]["properties"].update(optional)
    defs["policy"]["properties"]["action"] = link("Command", "Query")
    for kind, shape in KINDS.items():
        defs[kind] = copy.deepcopy(shape)
        defs["node"]["properties"]["kind"]["enum"].append(kind)
        defs["node"]["allOf"].append({"if": {"properties": {"kind": {"const": kind}}},
                                     "then": {"properties": {"data": use(kind)}}})
    # Keep direct data-schema lookup available for every kind's typed references.
    for branch in defs["node"]["allOf"]:
        kind = branch["if"]["properties"]["kind"]["const"]
        data_name = branch["then"]["properties"]["data"]["$ref"].split("/")[-1]
        if kind not in defs:
            defs[kind] = copy.deepcopy(defs[data_name])
    return schema


if __name__ == "__main__":
    (ROOT / "contracts/phase1.schema.json").write_text(json.dumps(build_schema(), indent=2) + "\n", encoding="utf-8")
