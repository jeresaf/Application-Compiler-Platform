"""Synthetic semantic corpus authorship, never application generation."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "test-corpus/phase1"


def ref(id):
    return {"id": id, "revision": 1}


def scalar(kind):
    return {"kind": kind}


def literal(kind, value):
    return {"tag": "literal", "type": scalar(kind), "value": value}


def field_expr(id, binding="resource"):
    return {"tag": "field", "binding": binding, "ref": ref(id)}


def node(id, kind, data, requirement="REQ-CASE"):
    return {"id": id, "revision": 1, "kind": kind, "name": id, "lifecycle": "PROPOSED",
        "steward": "fixture:authors", "origins": [{"source": "fixture:synthetic", "locator": id,
        "actor": "fixture:author", "actorType": "HUMAN"}],
        "basis": [] if kind == "Requirement" else [ref(requirement)], "data": data}


def add(snapshot, id, kind, data):
    requirement = next(n["id"] for n in snapshot["nodes"] if n["kind"] == "Requirement")
    result = node(id, kind, data, requirement)
    snapshot["nodes"].append(result)
    return result


def entity(snapshot, id, tenant=None):
    data = {"identity": [ref(id + "-ID")]}
    if tenant:
        data["tenantField"] = ref(id + "-TENANT")
    add(snapshot, id, "Entity", data)
    add(snapshot, id + "-ID", "Field", {"owner": ref(id), "type": {"kind": "Identifier", "entity": ref(id)}, "optional": False, "classification": "INTERNAL"})
    if tenant:
        add(snapshot, id + "-TENANT", "Field", {"owner": ref(id), "type": {"kind": "Identifier", "entity": ref(tenant)}, "optional": False, "classification": "INTERNAL"})


def payment():
    result = json.loads((ROOT / "test-corpus/semantic/reference.json").read_text(encoding="utf-8"))
    result["modelVersion"] = "0.2.0"
    result["snapshotId"] = "SNAP-PAYMENT-PHASE1"
    def convert(value):
        if isinstance(value, dict):
            if value.get("kind") in {"Decimal", "Money"}:
                value.update(precision=18, scale=2, rounding="REJECT")
            if value.get("tag") == "binary" and value.get("op") == "eq":
                value["op"] = "identityEq"
            for child in list(value.values()):
                convert(child)
        elif isinstance(value, list):
            for child in value:
                convert(child)
    convert(result)
    for id in ("ENT-TENANT", "ENT-MEMBER", "ENT-PAYMENT"):
        add(result, "AGG-" + id, "Aggregate", {"root": ref(id), "members": [ref(id)], "invariants": [ref("INV-POSITIVE")] if id == "ENT-PAYMENT" else [], "consistency": "ATOMIC"})
    add(result, "REL-MEMBER-PAYMENT", "Relation", {"source": ref("ENT-MEMBER"), "target": ref("ENT-PAYMENT"), "sourceCardinality": {"min": 1, "max": 1}, "targetCardinality": {"min": 0, "max": "UNBOUNDED"}, "ownership": "REFERENCE", "onDelete": "RESTRICT"})
    return result


def cases():
    result = {"modelVersion": "0.2.0", "applicationId": "APP-CASE-MANAGEMENT", "snapshotId": "SNAP-CASE-PHASE1", "nodes": [], "approvals": [], "issues": []}
    result["nodes"].append(node("REQ-CASE", "Requirement", {"statement": "Synthetic organization case intake, document review, assignment, approval, comments and archival tasks.", "priority": "MUST", "acceptance": [ref("AC-CASE")]}))
    add(result, "AC-CASE", "AcceptanceCriterion", {"requirement": ref("REQ-CASE"), "scenario": "An assigned reviewer in the same organization reviews documents; an authorized approver approves; only approved cases archive."})
    entity(result, "ORG")
    for id in ("USER", "CASE", "DOCUMENT", "ASSIGNMENT", "REVIEW", "APPROVAL", "COMMENT"):
        entity(result, id, "ORG")
    for id in ("ORG", "USER", "CASE"):
        members = [id] if id != "CASE" else ["CASE", "DOCUMENT", "ASSIGNMENT", "REVIEW", "APPROVAL", "COMMENT"]
        add(result, "AGG-" + id, "Aggregate", {"root": ref(id), "members": [ref(m) for m in members], "invariants": [], "consistency": "ATOMIC"})
    for id in ("DOCUMENT", "ASSIGNMENT", "REVIEW", "APPROVAL", "COMMENT"):
        add(result, "REL-CASE-" + id, "Relation", {"source": ref("CASE"), "target": ref(id), "sourceCardinality": {"min": 1, "max": 1}, "targetCardinality": {"min": 0, "max": "UNBOUNDED"}, "ownership": "COMPOSITION", "onDelete": "RESTRICT"})
    add(result, "REL-ASSIGNEE", "Relation", {"source": ref("USER"), "target": ref("ASSIGNMENT"), "sourceCardinality": {"min": 1, "max": 1}, "targetCardinality": {"min": 0, "max": "UNBOUNDED"}, "ownership": "REFERENCE", "onDelete": "RESTRICT"})
    add(result, "VO-TITLE", "ValueObject", {"equality": "STRUCTURAL"})
    add(result, "FLD-TITLE", "Field", {"owner": ref("VO-TITLE"), "type": scalar("String"), "optional": False, "classification": "PUBLIC"})
    add(result, "FLD-CASE-TITLE", "Field", {"owner": ref("CASE"), "type": {"kind": "Value", "definition": ref("VO-TITLE")}, "optional": False, "classification": "PUBLIC"})
    add(result, "FLD-NOTE", "Field", {"owner": ref("CASE"), "type": {"kind": "Nullable", "item": scalar("String")}, "optional": True, "classification": "SENSITIVE"})
    add(result, "CASE-ASSIGNEE", "Field", {"owner": ref("CASE"), "type": {"kind": "Identifier", "entity": ref("USER")}, "optional": False, "classification": "INTERNAL"})
    for owner, name in (("DOCUMENT", "title"), ("ASSIGNMENT", "task"), ("REVIEW", "outcome"), ("APPROVAL", "reason"), ("COMMENT", "body")):
        add(result, owner + "-" + name, "Field", {"owner": ref(owner), "type": scalar("String"), "optional": False, "classification": "INTERNAL"})
    add(result, "TYPE-CASE-CODE", "TypeDefinition", {"base": scalar("String"), "semantics": "NOMINAL", "refinement": {"kind": "LENGTH", "min": 1, "max": 40}})
    add(result, "PARAM-CODE", "Parameter", {"type": {"kind": "Named", "definition": ref("TYPE-CASE-CODE")}, "value": "CASE-001"})
    add(result, "PARAM-TITLE", "Parameter", {"type": {"kind": "Value", "definition": ref("VO-TITLE")}, "value": {"FLD-TITLE": "Review request"}})
    add(result, "PARAM-TAGS", "Parameter", {"type": {"kind": "Set", "element": scalar("String"), "minItems": 0, "maxItems": 8}, "value": ["review", "archive"]})
    add(result, "PARAM-DATE", "Parameter", {"type": scalar("Date"), "value": "2026-09-16"})
    add(result, "PARAM-INSTANT", "Parameter", {"type": scalar("Instant"), "value": "2026-09-16T09:00:00Z"})
    add(result, "PARAM-NULL", "Parameter", {"type": {"kind": "Nullable", "item": scalar("String")}, "value": None})
    add(result, "ACT-REVIEWER", "Actor", {"subject": ref("USER")})
    add(result, "ROLE-REVIEWER", "Role", {"actor": ref("ACT-REVIEWER")})
    add(result, "WF-CASE", "StateMachine", {"resource": ref("CASE"), "initial": ref("STATE-OPEN")})
    states = ["OPEN", "REVIEWED", "APPROVED", "ARCHIVED"]
    for i, state in enumerate(states):
        add(result, "STATE-" + state, "State", {"machine": ref("WF-CASE"), "terminal": i == 3})
    for i, task in enumerate(("REVIEW", "APPROVE", "ARCHIVE")):
        add(result, "CMD-" + task, "Command", {"resource": ref("CASE"), "invariants": [], "emits": [ref("EVT-" + task)]})
        add(result, "EVT-" + task, "Event", {"resource": ref("CASE"), "payload": [ref("FLD-CASE-TITLE")]})
        add(result, "POL-" + task, "Policy", {"actor": ref("ACT-REVIEWER"), "roles": [ref("ROLE-REVIEWER")], "resource": ref("CASE"), "action": ref("CMD-" + task), "effect": "ALLOW", "predicate": {"tag": "binary", "op": "identityEq", "left": field_expr("CASE-TENANT"), "right": field_expr("USER-TENANT", "actor")}})
        add(result, "TRANS-" + task, "Transition", {"machine": ref("WF-CASE"), "from": ref("STATE-" + states[i]), "to": ref("STATE-" + states[i + 1]), "command": ref("CMD-" + task), "actor": ref("ACT-REVIEWER"), "guard": literal("Boolean", True), "effects": [ref("EVT-" + task)]})
    review_policy = next(n for n in result["nodes"] if n["id"] == "POL-REVIEW")
    review_policy["data"]["predicate"] = {"tag": "binary", "op": "and", "left": review_policy["data"]["predicate"], "right": {"tag": "binary", "op": "identityEq", "left": field_expr("CASE-ASSIGNEE"), "right": field_expr("USER-ID", "actor")}}
    return result


def security(model):
    for level in ("PUBLIC", "INTERNAL", "SENSITIVE", "SECRET"):
        sensitive = level in {"SENSITIVE", "SECRET"}
        add(model, "CLASS-" + level, "DataClassification", {"level": level, "audit": "READ_WRITE" if sensitive else "WRITE", "encryptAtRest": True, "encryptInTransit": True, "export": "DENY", "redaction": "OMIT" if level == "SECRET" else "MASK" if sensitive else "NONE"})
    for n in list(model["nodes"]):
        if n["kind"] == "Entity":
            n["data"]["tenancy"] = "SCOPED" if "tenantField" in n["data"] else "TENANT_ROOT"
        if n["kind"] == "Field":
            n["data"]["classificationRef"] = ref("CLASS-" + n["data"]["classification"])
        if n["kind"] == "Actor":
            n["data"]["authentication"] = ref("AUTH-" + n["id"])
            add(model, "AUTH-" + n["id"], "AuthenticationModel", {"actor": ref(n["id"]), "assurance": "MULTI_FACTOR", "mechanisms": ["KNOWLEDGE", "POSSESSION"]})
            add(model, "SESSION-" + n["id"], "SessionPolicy", {"authentication": ref("AUTH-" + n["id"]), "idleSeconds": 900, "absoluteSeconds": 28800, "reauthSeconds": 3600})
    actor = next(n for n in model["nodes"] if n["kind"] == "Actor")
    role = next(n for n in model["nodes"] if n["kind"] == "Role")
    role["data"]["permissions"] = []
    scopes = set()
    for action in [n for n in model["nodes"] if n["kind"] in {"Command", "Query"}]:
        resource = next(n for n in model["nodes"] if n["id"] == action["data"]["resource"]["id"])
        actor_entity = next(n for n in model["nodes"] if n["id"] == actor["data"]["subject"]["id"])
        scope_id = "SCOPE-" + resource["id"]
        if scope_id not in scopes:
            data = {"actor": ref(actor["id"]), "resource": ref(resource["id"]), "mode": "SAME_TENANT"}
            data.update(actorTenant=actor_entity["data"]["tenantField"], resourceTenant=resource["data"]["tenantField"])
            add(model, scope_id, "Scope", data)
            add(model, "ASSIGN-" + resource["id"], "RoleAssignment", {"role": ref(role["id"]), "actor": ref(actor["id"]), "scope": ref(scope_id), "principal": "fixture:operator"})
            scopes.add(scope_id)
        permission_id = "PERM-" + action["id"]
        add(model, permission_id, "Permission", {"actor": ref(actor["id"]), "resource": ref(resource["id"]), "action": ref(action["id"])})
        role["data"]["permissions"].append(ref(permission_id))
        policies = [n for n in model["nodes"] if n["kind"] == "Policy" and n["data"]["action"] == ref(action["id"])]
        if not policies:
            policies = [add(model, "POL-" + action["id"], "Policy", {"actor": ref(actor["id"]), "roles": [ref(role["id"])], "resource": ref(resource["id"]), "action": ref(action["id"]), "effect": "ALLOW", "predicate": literal("Boolean", True)})]
        for policy in policies:
            policy["data"].update(permission=ref(permission_id), scope=ref(scope_id))
        add(model, "POLSET-" + action["id"], "PolicySet", {"resource": ref(resource["id"]), "action": ref(action["id"]), "policies": [ref(n["id"]) for n in policies], "combining": "DENY_OVERRIDES", "default": "DENY"})
        add(model, "RATE-" + action["id"], "RatePolicy", {"permission": ref(permission_id), "requests": 100, "windowSeconds": 60, "burst": 10, "partition": "ACTOR"})
    for resource in [n for n in model["nodes"] if n["kind"] == "Entity"]:
        fields = [n for n in model["nodes"] if n["kind"] == "Field" and n["data"]["owner"] == ref(resource["id"]) and n["data"]["classification"] == "SENSITIVE"]
        if not fields:
            continue
        permission = next(n for n in model["nodes"] if n["kind"] == "Permission" and n["data"]["resource"] == ref(resource["id"]))
        suffix = resource["id"]
        add(model, "RETENTION-" + suffix, "Retention", {"resource": ref(suffix), "trigger": "CLOSED", "minimumSeconds": 86400})
        add(model, "DELETE-" + suffix, "DeletionPolicy", {"resource": ref(suffix), "trigger": "CLOSED", "mode": "ANONYMIZE", "afterSeconds": 172800, "fields": [ref(n["id"]) for n in fields], "holdBehavior": "BLOCK"})
        add(model, "HOLD-" + suffix, "LegalHold", {"resource": ref(suffix), "condition": literal("Boolean", True), "release": ref(permission["id"])})
        add(model, "LIFECYCLE-" + suffix, "DataLifecycle", {"resource": ref(suffix), "retention": ref("RETENTION-" + suffix), "deletion": ref("DELETE-" + suffix), "holds": [ref("HOLD-" + suffix)]})
    return model


def models():
    return {"payment.json": quality(interface(security(execution(payment())))), "case-management.json": quality(interface(security(execution(cases()))))}


def quality(model):
    add(model, "DEC-APPLICABILITY", "Decision", {"statement": "All declared fixture quality obligations apply.", "strength": "REQUIRED", "rationale": "Exercise the complete bounded quality model.", "alternatives": ["Omit verification"]})
    add(model, "APPLIES-ALL", "Applicability", {"condition": literal("Boolean", True), "rationale": "Synthetic reference obligations are applicable.", "decision": ref("DEC-APPLICABILITY")})
    criteria = [n for n in model["nodes"] if n["kind"] == "AcceptanceCriterion"]
    resource = next(n for n in model["nodes"] if n["kind"] == "Command")["data"]["resource"]
    def evidence(id, subjects, methods):
        add(model, id, "EvidenceRequirement", {"subjects": subjects, "methods": methods, "maxAgeSeconds": 86400, "applicability": ref("APPLIES-ALL")})
        return ref(id)
    for n in model["nodes"]:
        if n["kind"] == "AccessibilityRequirement":
            n["data"]["evidence"] = evidence("EVID-A11Y", n["data"]["subjects"], ["AUTO_A11Y", "MANUAL_A11Y"])
            break
    add(model, "TEST-TASK", "TestRequirement", {"criterion": ref(criteria[0]["id"]), "subjects": [ref("UC-TASK")], "level": "AUTHORIZATION", "evidence": evidence("EVID-TEST", [ref("UC-TASK")], ["AUTHORIZATION"])})
    add(model, "PERF-TASK", "PerformanceRequirement", {"subject": ref("QUERY-TASKS"), "metric": "P95_LATENCY_MS", "comparison": "LTE", "threshold": "500", "workload": {"concurrency": 10, "records": 10000, "durationSeconds": 60, "minimumSamples": 100}, "evidence": evidence("EVID-PERF", [ref("QUERY-TASKS")], ["PERFORMANCE"])})
    add(model, "RELIABILITY-TASK", "ReliabilityRequirement", {"subject": ref("SERVICE-TASKS"), "metric": "AVAILABILITY_PERCENT", "threshold": "99.5", "windowSeconds": 86400, "evidence": evidence("EVID-RELIABILITY", [ref("SERVICE-TASKS")], ["RELIABILITY"])})
    add(model, "COMPATIBILITY-TASK", "CompatibilityRequirement", {"subject": ref("QUERY-TASKS"), "policy": "BACKWARD", "supportedVersions": ["1", "2"], "currentVersion": "2", "windowSeconds": 86400, "evidence": evidence("EVID-COMPATIBILITY", [ref("QUERY-TASKS")], ["COMPATIBILITY"])})
    add(model, "OBSERVE-TASK", "ObservabilityRequirement", {"subjects": [ref("SERVICE-TASKS"), ref("JOB-TASK")], "signals": ["LOG", "METRIC", "TRACE", "AUDIT", "HEALTH", "READINESS"], "correlation": "REQUIRED", "redaction": "CLASSIFICATION", "evidence": evidence("EVID-OBSERVE", [ref("SERVICE-TASKS"), ref("JOB-TASK")], ["OBSERVABILITY"])})
    add(model, "BACKUP-TASK", "Backup", {"resources": [resource], "intervalSeconds": 3600, "retentionSeconds": 604800, "encrypted": True, "evidence": evidence("EVID-BACKUP", [resource], ["BACKUP"])})
    add(model, "RECOVERY-TASK", "Recovery", {"backup": ref("BACKUP-TASK"), "rpoSeconds": 3600, "rtoSeconds": 1800, "restoreTestIntervalSeconds": 86400, "evidence": evidence("EVID-RECOVERY", [resource], ["RECOVERY"])})
    return model


def interface(model):
    permissions = [ref(n["id"]) for n in model["nodes"] if n["kind"] == "Permission"]
    actor = next(n for n in model["nodes"] if n["kind"] == "Actor")
    add(model, "ACTION-TASK", "Action", {"useCase": ref("UC-TASK"), "permissions": [p for p in permissions if p["id"] != "PERM-QUERY-TASKS"], "label": "Complete task", "confirmation": "REQUIRED"})
    add(model, "FORM-TASK", "Form", {"useCase": ref("UC-TASK"), "controls": [ref("CONTROL-TEXT")], "submit": ref("ACTION-TASK")})
    add(model, "CONTROL-TEXT", "InputControl", {"form": ref("FORM-TASK"), "field": ref("INPUT-TASK-TEXT"), "label": "Task note", "errorMessage": "Enter a task note.", "required": True, "purpose": "MULTILINE"})
    add(model, "WIZARD-TASK", "Wizard", {"screen": ref("SCREEN-TASK"), "steps": [ref("WSTEP-INPUT")]})
    add(model, "WSTEP-INPUT", "WizardStep", {"wizard": ref("WIZARD-TASK"), "form": ref("FORM-TASK"), "requiresPrevious": False})
    add(model, "TABLE-TASKS", "Table", {"query": ref("QUERY-TASKS"), "columns": [ref("OUTPUT-TASK-TEXT")], "emptyMessage": "No tasks are available."})
    add(model, "FILTER-TEXT", "Filter", {"query": ref("QUERY-TASKS"), "field": ref("OUTPUT-TASK-TEXT"), "operator": "CONTAINS", "inputType": scalar("String")})
    add(model, "SEARCH-TASKS", "Search", {"query": ref("QUERY-TASKS"), "filters": [ref("FILTER-TEXT")], "label": "Find a task"})
    for state in ("EMPTY", "LOADING", "ERROR", "SUCCESS"):
        data = {"screen": ref("SCREEN-TASK"), "state": state, "message": "Task view: " + state.lower()}
        if state == "ERROR":
            data["recovery"] = ref("ACTION-TASK")
        add(model, "VIEW-" + state, "ViewState", data)
    add(model, "BOUNDARY-TASK", "PermissionBoundary", {"actor": ref(actor["id"]), "permissions": permissions, "denied": ref("VIEW-ERROR")})
    add(model, "RESPONSIVE-TASK", "ResponsivePolicy", {"screen": ref("SCREEN-TASK"), "modes": ["COMPACT", "EXPANDED"], "preserveActions": True, "preserveReadingOrder": True})
    add(model, "A11Y-TASK", "AccessibilityRequirement", {"subjects": [ref("SCREEN-TASK"), ref("FORM-TASK"), ref("CONTROL-TEXT"), ref("ACTION-TASK")], "checks": ["LABELS", "KEYBOARD", "FOCUS", "ERROR_ANNOUNCEMENT"], "method": "AUTOMATED_AND_MANUAL"})
    add(model, "SCREEN-TASK", "Screen", {"task": ref("UC-TASK"), "content": [ref("WIZARD-TASK"), ref("TABLE-TASKS"), ref("SEARCH-TASKS")], "actions": [ref("ACTION-TASK")], "states": [ref("VIEW-" + s) for s in ("EMPTY", "LOADING", "ERROR", "SUCCESS")], "boundary": ref("BOUNDARY-TASK"), "responsive": ref("RESPONSIVE-TASK"), "accessibility": ref("A11Y-TASK")})
    return model


def execution(model):
    import tzdata
    commands = [n for n in model["nodes"] if n["kind"] == "Command"]
    resource = commands[0]["data"]["resource"]
    add(model, "FAIL-TRANSIENT", "Failure", {"code": "DEPENDENCY_UNAVAILABLE", "category": "TRANSIENT", "retryable": True})
    add(model, "FAIL-BUSINESS", "Failure", {"code": "INVALID_STATE", "category": "BUSINESS", "retryable": False})
    add(model, "IDEM-OPERATION", "IdempotencyPolicy", {"scope": resource, "keyType": scalar("String"), "windowSeconds": 86400, "replay": "RETURN_RESULT", "conflict": "REJECT_DIFFERENT_INPUT"})
    for command in commands:
        aggregate = next(n for n in model["nodes"] if n["kind"] == "Aggregate" and n["data"]["root"] == command["data"]["resource"])
        command["data"].update(aggregate=ref(aggregate["id"]), writes=aggregate["data"]["members"], failures=[ref("FAIL-TRANSIENT"), ref("FAIL-BUSINESS")], idempotency=ref("IDEM-OPERATION"))
    for event in [n for n in model["nodes"] if n["kind"] == "Event"]:
        event["data"]["delivery"] = ref("DELIVERY-" + event["id"])
        add(model, "DELIVERY-" + event["id"], "DeliveryPolicy", {"event": ref(event["id"]), "guarantee": "AT_LEAST_ONCE", "ordering": "PER_AGGREGATE", "windowSeconds": 3600, "deduplication": ref("IDEM-OPERATION")})
    for id in ("INPUT-TASK", "OUTPUT-TASK"):
        add(model, id, "ValueObject", {"equality": "STRUCTURAL"})
        add(model, id + "-TEXT", "Field", {"owner": ref(id), "type": scalar("String"), "optional": False, "classification": "INTERNAL"})
    add(model, "FLD-TASK-SUMMARY", "Field", {"owner": resource, "type": scalar("String"), "optional": False, "classification": "INTERNAL"})
    add(model, "QUERY-TASKS", "Query", {"resource": resource, "scope": ref("SCOPE-" + resource["id"]), "result": {"kind": "Value", "definition": ref("OUTPUT-TASK")}, "projection": [{"field": ref("OUTPUT-TASK-TEXT"), "value": field_expr("FLD-TASK-SUMMARY")}], "paginated": True, "maximumResults": 100})
    add(model, "SERVICE-TASKS", "Service", {"operations": [ref(c["id"]) for c in commands] + [ref("QUERY-TASKS")]})
    add(model, "TX-TASK", "Transaction", {"aggregate": commands[0]["data"]["aggregate"], "commands": [ref(c["id"]) for c in commands], "consistency": "ATOMIC", "onFailure": "ROLLBACK"})
    add(model, "UC-TASK", "UseCase", {"service": ref("SERVICE-TASKS"), "steps": [ref("STEP-" + c["id"]) for c in commands], "input": ref("INPUT-TASK"), "output": ref("OUTPUT-TASK")})
    for command in commands:
        add(model, "STEP-" + command["id"], "ExecutionStep", {"owner": ref("UC-TASK"), "operation": ref(command["id"]), "onFailure": "STOP", "transaction": ref("TX-TASK")})
    add(model, "RETRY-TASK", "RetryPolicy", {"failures": [ref("FAIL-TRANSIENT")], "maxAttempts": 3, "initialSeconds": 1, "maxDelaySeconds": 10, "multiplier": 2})
    add(model, "SCHEDULE-TASK", "Schedule", {"mode": "LOCAL_DAILY", "localTime": "09:00:00", "timezone": "Africa/Nairobi", "tzdbVersion": tzdata.IANA_VERSION, "gap": "SKIP", "overlap": "EARLIER"})
    add(model, "JOB-TASK", "Job", {"useCase": ref("UC-TASK"), "schedule": ref("SCHEDULE-TASK"), "retry": ref("RETRY-TASK"), "idempotency": ref("IDEM-OPERATION"), "timeoutSeconds": 30})
    return model


if __name__ == "__main__":
    DEST.mkdir(parents=True, exist_ok=True)
    for filename, model in models().items():
        (DEST / filename).write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
