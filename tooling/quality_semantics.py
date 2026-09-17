"""Quality contract analysis. No production gate or evidence executor."""
from decimal import Decimal, InvalidOperation


METHOD_BY_KIND = {"PerformanceRequirement": {"PERFORMANCE"}, "AccessibilityRequirement": {"AUTO_A11Y", "MANUAL_A11Y"}, "ReliabilityRequirement": {"RELIABILITY"}, "CompatibilityRequirement": {"COMPATIBILITY"}, "ObservabilityRequirement": {"OBSERVABILITY"}, "Backup": {"BACKUP"}, "Recovery": {"RECOVERY"}}


def subjects(node, index):
    d = node["data"]
    if "subject" in d:
        return [d["subject"]]
    if "subjects" in d:
        return d["subjects"]
    if node["kind"] == "Backup":
        return d["resources"]
    if node["kind"] == "Recovery":
        return index[d["backup"]["id"]]["data"]["resources"]
    return []


def checks(index, at, emit, types):
    target = lambda r: index[r["id"]]
    def error(code, node, message):
        emit(code, node, at(node, "data"), message)
    for node in index.values():
        kind, d = node["kind"], node["data"]
        if kind == "Applicability":
            result = types.expression(node, d["condition"], {}, at(node, "data", "condition"))
            if result != {"kind": "Boolean"}:
                error("APPLICABILITY", node, "Applicability must be a closed Boolean expression with no actor/resource binding.")
        methods = METHOD_BY_KIND.get(kind)
        if kind == "TestRequirement":
            methods = {d["level"]}
        if methods:
            evidence = target(d["evidence"])["data"]
            if not methods <= set(evidence["methods"]) or any(s not in evidence["subjects"] for s in subjects(node, index)):
                error("QUALITY", node, "Evidence requirement must cover subjects and all verification methods.")
        if kind in {"PerformanceRequirement", "ReliabilityRequirement"}:
            try:
                threshold = Decimal(d["threshold"])
                if not threshold.is_finite() or threshold <= 0 or (kind == "ReliabilityRequirement" and threshold > 100):
                    raise ValueError()
            except (InvalidOperation, ValueError):
                error("QUALITY", node, "Metric threshold is outside its finite positive unit domain.")
            if kind == "PerformanceRequirement" and d["comparison"] != ("GTE" if d["metric"] == "THROUGHPUT_PER_SECOND" else "LTE"):
                error("QUALITY", node, "Metric comparison direction does not match its defined units.")
        if kind == "CompatibilityRequirement" and d["currentVersion"] not in d["supportedVersions"]:
            error("QUALITY", node, "Compatibility window must include the current version.")
        if kind == "Backup" and d["retentionSeconds"] < d["intervalSeconds"]:
            error("RECOVERY", node, "Backup retention cannot be shorter than its interval.")
        if kind == "Recovery":
            backup = target(d["backup"])["data"]
            evidence = target(d["evidence"])["data"]
            if d["rpoSeconds"] < backup["intervalSeconds"] or evidence["maxAgeSeconds"] > d["restoreTestIntervalSeconds"]:
                error("RECOVERY", node, "RPO must cover backup spacing and restore evidence must remain fresh.")
