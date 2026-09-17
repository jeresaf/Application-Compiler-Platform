"""Reference evaluation of evidence bindings, not trust or production certification."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from type_semantics import Types

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "contracts/evidence.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)
CONTEXT_KEYS = ("snapshotId", "artifactDigest", "configurationDigest", "toolDigest", "profileVersion")


def closed_expression(expr, index):
    """Evaluate only closed applicability expressions, after model validation."""
    tag = expr["tag"]
    if tag in {"literal", "parameter"}:
        data = expr if tag == "literal" else index[expr["ref"]["id"]]["data"]
        typ, value = data["type"], data["value"]
        if typ["kind"] in {"Integer", "Decimal", "Money", "Duration"}:
            return Decimal(value)
        if typ["kind"] in {"Date", "Instant", "LocalDateTime"}:
            return datetime.fromisoformat(value)
        return value
    if tag == "coalesce":
        value = closed_expression(expr["value"], index)
        return closed_expression(expr["fallback"], index) if value is None else value
    if tag == "size":
        return Decimal(len(closed_expression(expr["value"], index)))
    if tag == "contains":
        return closed_expression(expr["value"], index) in closed_expression(expr["collection"], index)
    if tag != "binary":
        raise ValueError("Applicability requires closed expressions")
    left, right = closed_expression(expr["left"], index), closed_expression(expr["right"], index)
    op = expr["op"]
    if op == "and":
        return left and right
    if op in {"eq", "identityEq"}:
        types = Types(index, lambda *args: None)
        typ = types.expression({}, expr["left"], {}, ())
        if typ and typ["kind"] in {"Value", "Set", "List", "Named"}:
            return types.value_key(typ, left) == types.value_key(typ, right)
        return left == right
    if op == "gt":
        return left > right
    if op == "add":
        return left + right
    raise ValueError("Unsupported expression")


def evaluate_evidence(model, obligation_id, records, context, evaluated_at, applicability_approved=False):
    """Caller verifies authority separately. Return status + stable failure codes."""
    index = {n["id"]: n for n in model["nodes"]}
    node = index[obligation_id]
    obligation = {"id": node["id"], "revision": node["revision"]}
    d = node["data"]
    requirement = index[d["evidence"]["id"]]
    er = requirement["data"]
    application = index[er["applicability"]["id"]]
    errors = set()
    try:
        applicable = closed_expression(application["data"]["condition"], index)
        if type(applicable) is not bool:
            raise ValueError()
        if not applicable:
            return {"status": "NOT_APPLICABLE" if applicability_approved else "BLOCKED", "diagnostics": [] if applicability_approved else ["ACP-EVIDENCE-APPLICABILITY"]}
        if not evaluated_at.endswith("Z"):
            raise ValueError()
        now = datetime.fromisoformat(evaluated_at)
    except (ValueError, TypeError, KeyError):
        return {"status": "BLOCKED", "diagnostics": ["ACP-EVIDENCE-APPLICABILITY"]}
    if context.get("snapshotId") != model["snapshotId"] or not all(k in context for k in CONTEXT_KEYS):
        return {"status": "BLOCKED", "diagnostics": ["ACP-EVIDENCE-BINDING"]}
    methods = set()
    for record in records:
        if not VALIDATOR.is_valid(record):
            errors.add("ACP-EVIDENCE-SHAPE")
            continue
        bound = record["obligation"] == obligation and record["requirement"] == d["evidence"] and all(record[k] == context[k] for k in CONTEXT_KEYS)
        bound &= {(r["id"], r["revision"]) for r in record["subjects"]} == {(r["id"], r["revision"]) for r in er["subjects"]}
        if not bound:
            errors.add("ACP-EVIDENCE-BINDING")
            continue
        try:
            if not record["observedAt"].endswith("Z"):
                raise ValueError()
            age = (now - datetime.fromisoformat(record["observedAt"])).total_seconds()
            if not 0 <= age <= er["maxAgeSeconds"]:
                raise ValueError()
        except (ValueError, TypeError):
            errors.add("ACP-EVIDENCE-FRESHNESS")
            continue
        if record["result"] != "PASS":
            errors.add("ACP-EVIDENCE-RESULT")
            continue
        metric = d.get("metric")
        thresholds = []
        if metric:
            comparison = d.get("comparison", "GTE" if metric == "AVAILABILITY_PERCENT" else "LTE")
            thresholds = [(metric, comparison, Decimal(d["threshold"]))]
        if node["kind"] == "Recovery":
            thresholds = [("RESTORE_SECONDS", "LTE", Decimal(d["rtoSeconds"])), ("DATA_LOSS_SECONDS", "LTE", Decimal(d["rpoSeconds"]))]
        valid = True
        for name, comparison, threshold in thresholds:
            measurements = [m for m in record["measurements"] if m["metric"] == name]
            try:
                if len(measurements) != 1:
                    raise ValueError()
                value = Decimal(measurements[0]["value"])
                if not value.is_finite() or value < 0 or (comparison == "LTE" and value > threshold) or (comparison == "GTE" and value < threshold):
                    raise ValueError()
                if node["kind"] == "PerformanceRequirement" and (record.get("workload") != d["workload"] or measurements[0]["samples"] < d["workload"]["minimumSamples"]):
                    raise ValueError()
                if node["kind"] == "ReliabilityRequirement" and (value > 100 or record.get("windowSeconds") != d["windowSeconds"]):
                    raise ValueError()
            except (InvalidOperation, ValueError):
                valid = False
        if not valid:
            errors.add("ACP-EVIDENCE-MEASUREMENT")
            continue
        methods.add(record["method"])
    if not set(er["methods"]) <= methods:
        errors.add("ACP-EVIDENCE-METHOD")
    return {"status": "PASS" if not errors else "BLOCKED", "diagnostics": sorted(errors)}
