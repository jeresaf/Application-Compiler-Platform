"""Execution contract validation and deterministic schedule reference semantics."""
from datetime import datetime, timezone
from importlib.resources import files
import re
from zoneinfo import ZoneInfo
from functools import lru_cache
import tzdata


@lru_cache(maxsize=1024)
def zone(name):
    # Resolve only the pinned package, never the host's possibly different tzdb.
    if not re.fullmatch(r"[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*", name):
        raise ValueError("Invalid timezone")
    with files("tzdata.zoneinfo").joinpath(*name.split("/")).open("rb") as stream:
        return ZoneInfo.from_file(stream, key=name)


def local_occurrence(local_datetime, schedule):
    """Return UTC instant or None (gap skip); reject ambiguous missing policy."""
    local = datetime.fromisoformat(local_datetime)
    if local.tzinfo is not None or schedule["tzdbVersion"] != tzdata.IANA_VERSION:
        raise ValueError("Schedule version/local time mismatch")
    tz = zone(schedule["timezone"])
    candidates = set()
    for fold in (0, 1):
        instant = local.replace(tzinfo=tz, fold=fold).astimezone(timezone.utc)
        if instant.astimezone(tz).replace(tzinfo=None) == local:
            candidates.add(instant)
    if not candidates:
        if schedule["gap"] == "SKIP":
            return None
        raise ValueError("Nonexistent local time")
    if len(candidates) > 1 and schedule["overlap"] == "REJECT":
        raise ValueError("Ambiguous local time")
    return max(candidates) if schedule["overlap"] == "LATER" else min(candidates)


def retry_horizon(policy, timeout):
    return policy["maxAttempts"] * timeout + sum(min(policy["initialSeconds"] * policy["multiplier"] ** n, policy["maxDelaySeconds"]) for n in range(policy["maxAttempts"] - 1))


def checks(index, at, emit, types):
    nodes = list(index.values())
    by_kind = lambda kind: [n for n in nodes if n["kind"] == kind]
    target = lambda r: index[r["id"]]
    ref = lambda n: {"id": n["id"], "revision": n["revision"]}
    def error(code, node, message):
        emit(code, node, at(node, "data"), message)

    operations = {}
    for service in by_kind("Service"):
        for op in service["data"]["operations"]:
            operations.setdefault(op["id"], []).append(service["id"])
    compensation_edges = {}
    for node in nodes:
        kind, d = node["kind"], node["data"]
        if kind in {"Command", "Query"} and len(operations.get(node["id"], [])) != 1:
            error("EXECUTION", node, "Each operation belongs to one logical service.")
        if kind == "Command":
            aggregate = target(d["aggregate"])["data"]
            if aggregate["root"] != d["resource"] or any(w not in aggregate["members"] for w in d["writes"]):
                error("AGGREGATE", node, "Commands enter at the aggregate root and write only its members.")
            if target(d["idempotency"])["data"]["scope"] != d["resource"]:
                error("RETRY", node, "Command idempotency must cover its resource.")
        if kind == "Query":
            if target(d["scope"])["data"]["resource"] != d["resource"]:
                error("TENANT", node, "Query scope must cover its resource.")
            if not types.declaration(d["result"]):
                error("TYPE", node, "Query result type is invalid.")
            result_owner = d["result"].get("definition") if d["result"]["kind"] == "Value" else None
            scope_actor = target(d["scope"])["data"]["actor"]
            context = {"resource": d["resource"], "actor": target(scope_actor)["data"]["subject"]}
            outputs = []
            for i, binding in enumerate(d["projection"]):
                field = target(binding["field"])["data"]
                inferred = types.expression(node, binding["value"], context, at(node, "data", "projection", i, "value"))
                if field["owner"] != result_owner or inferred != field["type"]:
                    error("TYPE", node, "Query projection must type-check into its declared value result.")
                outputs.append(binding["field"])
            required = [ref(f) for f in nodes if f["kind"] == "Field" and f["data"]["owner"] == result_owner and not f["data"]["optional"]]
            if result_owner is None or any(f not in outputs for f in required) or len({r["id"] for r in outputs}) != len(outputs):
                error("EXECUTION", node, "Query projection must cover required output fields without duplicates.")
        if kind == "UseCase":
            declared = target(d["service"])["data"]["operations"]
            for step in d["steps"]:
                s = target(step)["data"]
                if s["owner"] != ref(node) or s["operation"] not in declared:
                    error("EXECUTION", node, "Step ownership/service operation is inconsistent.")
                if "compensation" in s and s["compensation"] not in declared:
                    error("EXECUTION", node, "Compensation must belong to the use case's service.")
        if kind == "ExecutionStep":
            if ref(node) not in target(d["owner"])["data"]["steps"]:
                error("EXECUTION", node, "Step is absent from its owning use case.")
            if (d["onFailure"] == "COMPENSATE") != ("compensation" in d):
                error("EXECUTION", node, "Compensation failure mode requires an explicit compensating command.")
            if "compensation" in d:
                if target(d["compensation"])["data"]["resource"] != target(d["operation"])["data"]["resource"] or d["compensation"] == d["operation"]:
                    error("EXECUTION", node, "Compensation must be a distinct operation on the same resource.")
                compensation_edges.setdefault(d["operation"]["id"], set()).add(d["compensation"]["id"])
            if "transaction" in d and d["operation"] not in target(d["transaction"])["data"]["commands"]:
                error("EXECUTION", node, "Transactional step is not in its declared transaction.")
        if kind == "Transaction":
            if any(target(c)["data"]["aggregate"] != d["aggregate"] for c in d["commands"]):
                error("EXECUTION", node, "Atomic transactions cannot span aggregates.")
        if kind == "Failure" and d["retryable"] and d["category"] != "TRANSIENT":
            error("RETRY", node, "Only transient failures can be retried automatically.")
        if kind == "RetryPolicy":
            if d["initialSeconds"] > d["maxDelaySeconds"] or any(not target(f)["data"]["retryable"] or target(f)["data"]["category"] != "TRANSIENT" for f in d["failures"]):
                error("RETRY", node, "Retry policy has invalid delay bounds or nonretryable failures.")
        if kind == "IdempotencyPolicy":
            if d["keyType"]["kind"] not in {"String", "Identifier", "Named"} or not types.declaration(d["keyType"]):
                error("RETRY", node, "Idempotency key must have a stable nonnullable scalar identity.")
        if kind == "Event" and target(d["delivery"])["data"]["event"] != ref(node):
            error("DELIVERY", node, "Event and delivery policy must refer to each other.")
        if kind == "DeliveryPolicy":
            event = target(d["event"])
            if event["data"]["delivery"] != ref(node):
                error("DELIVERY", node, "Delivery policy belongs to another event.")
            dedup = target(d["deduplication"])["data"] if "deduplication" in d else None
            if d["guarantee"] == "AT_LEAST_ONCE" and (dedup is None or dedup["windowSeconds"] < d["windowSeconds"] or dedup["scope"] != event["data"]["resource"]):
                error("DELIVERY", node, "At-least-once delivery requires resource-scoped deduplication for the delivery window.")
        if kind == "Schedule" and d["mode"] == "LOCAL_DAILY":
            try:
                if d["tzdbVersion"] != tzdata.IANA_VERSION or not re.fullmatch(r"\d{2}:\d{2}:\d{2}", d["localTime"]):
                    raise ValueError()
                datetime.strptime(d["localTime"], "%H:%M:%S")
                zone(d["timezone"])
            except (ValueError, OSError, ModuleNotFoundError):
                error("SCHEDULE", node, "Unsupported timezone database version, zone or local time.")
        if kind == "Job":
            retry, idem = target(d["retry"])["data"], target(d["idempotency"])["data"]
            commands = [target(target(s)["data"]["operation"]) for s in target(d["useCase"])["data"]["steps"]]
            commands = [c for c in commands if c["kind"] == "Command"]
            if retry_horizon(retry, d["timeoutSeconds"]) > idem["windowSeconds"]:
                error("RETRY", node, "Retry horizon exceeds job idempotency retention.")
            for command in commands:
                cd = command["data"]
                if cd["resource"] != idem["scope"] or any(f not in cd["failures"] for f in retry["failures"]) or target(cd["idempotency"])["data"]["windowSeconds"] < retry_horizon(retry, d["timeoutSeconds"]):
                    error("RETRY", node, "Retried commands must declare the failure, matching scope and sufficient idempotency window.")
    for step in by_kind("ExecutionStep"):
        d = step["data"]
        seen, pending = set(), list(compensation_edges.get(d["operation"]["id"], []))
        while pending:
            current = pending.pop()
            if current == d["operation"]["id"]:
                error("EXECUTION", step, "Compensation graph contains a cycle.")
                break
            if current not in seen:
                seen.add(current)
                pending.extend(compensation_edges.get(current, []))
