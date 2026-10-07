"""Offline Phase 1 contract checker. Not a compiler or approval authority."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from jsonschema import Draft202012Validator
from referencing import Registry


ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 1_048_576
MAX_DEPTH = 48
INTENT = {"Fact", "Constraint", "Requirement", "Preference", "Goal", "Assumption", "Decision"}
ACTIVE = {"APPROVED", "DEPRECATED"}
REPAIR = {
    "INPUT": "Supply bounded strict UTF-8 JSON without duplicate keys or nonfinite numbers.",
    "SHAPE": "Use the declared authoring-model version's record shapes; propose unsupported semantics explicitly.",
    "ID": "Give each durable concept a unique semantic ID.",
    "REF": "Include the exact referenced semantic ID and revision.",
    "KIND": "Reference a concept of the required semantic kind.",
    "BASIS": "Provide noncircular requirement or decision justification.",
    "APPROVAL": "Provide an authority-backed attestation for the exact revision.",
    "LIFECYCLE": "Keep candidates isolated and use an explicit lifecycle change.",
    "ISSUE": "Resolve blocking uncertainty through an approved Decision.",
    "OWNER": "Align the field, actor, resource, and machine bindings.",
    "TYPE": "Use compatible semantic types and explicit presence handling.",
    "SECRET": "Use a symbolic SecretReference with SECRET classification.",
    "WORKFLOW": "Correct workflow topology or ambiguous triggers explicitly.",
    "ACCEPTANCE": "Make requirement and acceptance references reciprocal.",
    "DOMAIN": "Use a bounded domain definition with explicit value semantics.",
    "CARDINALITY": "Use consistent endpoint bounds and deletion behavior.",
    "AGGREGATE": "Keep writes and composition inside one root-owned consistency boundary.",
    "OWNERSHIP": "Remove cyclic or conflicting semantic ownership.",
    "SECURITY": "Bind authentication, permissions, roles and policies consistently; missing context denies.",
    "TENANT": "Preserve the resource and actor's mandatory tenant boundary.",
    "PRIVACY": "Satisfy classification, retention and legal-hold obligations explicitly.",
    "EXECUTION": "Declare consistent service, step, failure and transaction boundaries.",
    "RETRY": "Retry only declared transient failures within the idempotency horizon.",
    "DELIVERY": "Declare achievable delivery and deduplication windows.",
    "SCHEDULE": "Use a supported explicit schedule with pinned timezone and DST policy.",
    "UI": "Bind task UI to use-case inputs and query projections with complete states and permissions.",
    "ACCESSIBILITY": "Declare and verify labels, keyboard, focus and error-announcement obligations.",
    "QUALITY": "Bind measurable obligations to compatible methods and exact subjects.",
    "RECOVERY": "Align backup intervals, RPO/RTO and restore evidence freshness.",
    "APPLICABILITY": "Use an explicit Boolean applicability condition backed by a decision.",
}


def pointer(parts):
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def walk(value, path=()):
    """Iterative traversal also used to enforce a bounded validation workload."""
    stack = [(value, path)]
    while stack:
        item, at = stack.pop()
        if len(at) > MAX_DEPTH:
            raise ValueError("Input nesting exceeds the kernel limit.")
        yield item, at
        if isinstance(item, dict):
            stack.extend((v, at + (k,)) for k, v in item.items())
        elif isinstance(item, list):
            stack.extend((v, at + (i,)) for i, v in enumerate(item))


def semantic_walk(value, path=()):
    """Literal value-object payloads are data, not semantic references/types."""
    stack = [(value, path)]
    while stack:
        item, at = stack.pop()
        yield item, at
        if isinstance(item, dict):
            literal_payload = item.get("tag") == "literal" or set(item) == {"type", "value"}
            stack.extend((v, at + (k,)) for k, v in item.items() if not (literal_payload and k == "value"))
        elif isinstance(item, list):
            stack.extend((v, at + (i,)) for i, v in enumerate(item))


def strict_load(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate object key.")
            result[key] = value
        return result

    def nonfinite(_):
        raise ValueError("Nonfinite numeric literal.")

    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Input exceeds the kernel byte limit.")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
    # Also reject finite-looking exponent literals decoded to infinity.
    for item, _ in walk(value):
        if isinstance(item, float):
            raise ValueError("Numeric JSON literals must be integers; use strings for decimals.")
    return value


SCHEMA = strict_load(ROOT / "contracts/kernel.schema.json")
Draft202012Validator.check_schema(SCHEMA)
# No retrieval callback: only the repository's local schema is trusted.
SHAPES = Draft202012Validator(SCHEMA, registry=Registry())
PHASE1_SCHEMA = strict_load(ROOT / "contracts/phase1.schema.json")
Draft202012Validator.check_schema(PHASE1_SCHEMA)
PHASE1_SHAPES = Draft202012Validator(PHASE1_SCHEMA, registry=Registry())


def diagnostic(code, subject, path, message, stage="semantic"):
    return {"code": "ACP-" + code, "severity": "ERROR", "stage": stage,
            "subject": subject if isinstance(subject, str) else "", "path": pointer(path), "message": message,
            "remediation": REPAIR[code]}


def validate(document, mode="draft"):
    """Return deterministic diagnostics without mutating the supplied snapshot.

    compile means necessary kernel approval closure, not executable application
    semantics, trusted approvals, Canonical IR, or production readiness.
    """
    if mode not in {"draft", "compile"}:
        raise ValueError("Unknown validation mode.")
    if isinstance(document, dict) and document.get("modelVersion") == "0.3.0":
        from execution_model import validate_execution
        return validate_execution(document, mode)
    errors = []

    def emit(code, node, path, message, stage="semantic"):
        errors.append(diagnostic(code, node.get("id", "") if node else "", path, message, stage))

    def finish():
        return sorted(errors, key=lambda e: (e["subject"], e["path"], e["code"], e["message"]))

    try:
        for item, _ in walk(document):
            if isinstance(item, float):
                raise ValueError("Floating-point JSON values are unsupported.")
    except ValueError:
        emit("INPUT", None, (), "Input exceeds the supported structural/numeric limits.", "input")
        return finish()

    extended = isinstance(document, dict) and document.get("modelVersion") == "0.2.0"
    try:
        shape_errors = list((PHASE1_SHAPES if extended else SHAPES).iter_errors(document))
    except RecursionError:
        emit("INPUT", None, (), "Input exceeds the validator recursion budget.", "input")
        return finish()
    for error in shape_errors:
        path = tuple(error.absolute_path)
        node = None
        if len(path) >= 2 and path[0] == "nodes" and isinstance(document, dict):
            candidate = document["nodes"][path[1]]
            node = candidate if isinstance(candidate, dict) else None
        # Do not echo jsonschema.message: it may contain sensitive input values.
        emit("SHAPE", node, path, f"Value violates schema rule '{error.validator}'.", "shape")
    if errors:
        return finish()

    nodes = document["nodes"]
    semantic_items = semantic_walk if extended else walk
    index = {}
    paths = {}
    for i, node in enumerate(nodes):
        if node["id"] in index:
            emit("ID", node, ("nodes", i, "id"), "Semantic ID occurs more than once.")
        index[node["id"]] = node
        paths[node["id"]] = ("nodes", i)
    issue_ids = set(index)
    for i, issue in enumerate(document["issues"]):
        if issue["id"] in issue_ids:
            emit("ID", issue, ("issues", i, "id"), "Issue ID is not unique.")
        issue_ids.add(issue["id"])
    if errors:
        return finish()

    def at(node, *tail):
        return paths[node["id"]] + tail

    def subject_for(path):
        if len(path) > 1 and path[0] == "nodes":
            return nodes[path[1]]
        if len(path) > 1 and path[0] == "issues":
            return document["issues"][path[1]]
        return None

    # Resolve every reference before any code dereferences it.
    for item, path in semantic_items(document):
        if isinstance(item, dict) and set(item) == {"id", "revision"}:
            target = index.get(item["id"])
            if target is None or target["revision"] != item["revision"]:
                emit("REF", subject_for(path), path, "Referenced revision is absent from this snapshot.")
    if errors:
        return finish()

    def target(ref):
        return index[ref["id"]]

    def ref(node):
        return {"id": node["id"], "revision": node["revision"]}

    def expect(node, reference, kinds, path):
        if target(reference)["kind"] not in kinds:
            emit("KIND", node, path, "Reference requires kind " + "/".join(sorted(kinds)) + ".")

    links = {
        "Requirement": {"acceptance": {"AcceptanceCriterion"}},
        "Entity": {"identity": {"Field"}, "tenantField": {"Field"}},
        "Field": {"owner": {"Entity"}},
        "Invariant": {"resource": {"Entity"}},
        "Command": {"resource": {"Entity"}, "invariants": {"Invariant"}, "emits": {"Event"}},
        "Event": {"resource": {"Entity"}, "payload": {"Field"}},
        "Actor": {"subject": {"Entity"}}, "Role": {"actor": {"Actor"}},
        "Policy": {"actor": {"Actor"}, "roles": {"Role"}, "resource": {"Entity"}, "action": {"Command"}},
        "StateMachine": {"resource": {"Entity"}, "initial": {"State"}},
        "State": {"machine": {"StateMachine"}},
        "Transition": {"machine": {"StateMachine"}, "from": {"State"}, "to": {"State"}, "command": {"Command"}, "actor": {"Actor"}, "effects": {"Event"}},
        "AcceptanceCriterion": {"requirement": {"Requirement"}},
    }
    if extended:
        links["Field"]["owner"] = {"Entity", "ValueObject"}
        links["Policy"]["action"] = {"Command", "Query"}
    for node in nodes:
        for i, basis in enumerate(node["basis"]):
            expect(node, basis, {"Requirement", "Decision"}, at(node, "basis", i))
        if "supersededBy" in node:
            expect(node, node["supersededBy"], {node["kind"]}, at(node, "supersededBy"))
        for key, kinds in links.get(node["kind"], {}).items():
            if key not in node["data"]:
                continue
            value = node["data"][key]
            if isinstance(value, list):
                for i, item in enumerate(value):
                    expect(node, item, kinds, at(node, "data", key, i))
            else:
                expect(node, value, kinds, at(node, "data", key))
        for item, path in semantic_items(node["data"], at(node, "data")):
            if not isinstance(item, dict):
                continue
            if item.get("kind") == "Identifier":
                expect(node, item["entity"], {"Entity"}, path + ("entity",))
            if item.get("tag") in {"field", "parameter"}:
                expect(node, item["ref"], {"Field" if item["tag"] == "field" else "Parameter"}, path + ("ref",))
    if extended:
        from phase1_semantics import typed_references
        for node in nodes:
            defs = PHASE1_SCHEMA["$defs"]
            shape = defs.get(node["kind"])
            if shape:
                typed_references(node["data"], shape, defs, expect, node, at(node, "data"))
            for item, path in semantic_items(node["data"], at(node, "data")):
                if isinstance(item, dict) and item.get("kind") in {"Named", "Value"}:
                    expect(node, item["definition"], {"TypeDefinition" if item["kind"] == "Named" else "ValueObject"}, path + ("definition",))
                if isinstance(item, dict) and item.get("tag") == "present":
                    expect(node, item["ref"], {"Field"}, path + ("ref",))
    for i, issue in enumerate(document["issues"]):
        if "decision" in issue:
            expect(issue, issue["decision"], {"Decision"}, ("issues", i, "decision"))
    if errors:
        return finish()

    approved = {(a["subject"]["id"], a["subject"]["revision"]) for a in document["approvals"]}
    for node in nodes:
        life = node["lifecycle"]
        if node["kind"] not in INTENT and not node["basis"]:
            emit("BASIS", node, at(node, "basis"), "Derived semantic concept lacks justification.")
        if life in ACTIVE and (node["id"], node["revision"]) not in approved:
            emit("APPROVAL", node, at(node, "lifecycle"), "Current approved revision lacks an attestation.")
        if mode == "compile" and life not in ACTIVE:
            emit("LIFECYCLE", node, at(node, "lifecycle"), "Selected compile snapshot contains an unapproved or retired concept.")
        replacement = node.get("supersededBy")
        if life == "SUPERSEDED":
            if replacement is None or replacement == ref(node) or target(replacement)["lifecycle"] not in ACTIVE:
                emit("LIFECYCLE", node, at(node, "supersededBy"), "Supersession requires a different approved replacement.")
        elif replacement is not None:
            emit("LIFECYCLE", node, at(node, "supersededBy"), "Only a superseded record may declare a replacement.")

    # Basis must terminate at intent, not form a circular justification.
    for node in nodes:
        pending = [b["id"] for b in node["basis"]]
        seen = set()
        while pending:
            current = pending.pop()
            if current == node["id"]:
                emit("BASIS", node, at(node, "basis"), "Justification contains a cycle.")
                break
            if current not in seen:
                seen.add(current)
                pending.extend(b["id"] for b in index[current]["basis"])

    for i, issue in enumerate(document["issues"]):
        decision = issue.get("decision")
        if issue["resolution"] == "RESOLVED":
            if decision is None or target(decision)["lifecycle"] not in ACTIVE:
                emit("ISSUE", issue, ("issues", i), "Resolved issue requires an approved decision.")
        elif decision is not None:
            emit("ISSUE", issue, ("issues", i), "Open issue cannot claim a resolution decision.")
        if mode == "compile" and issue["blocking"] and issue["resolution"] == "OPEN":
            emit("ISSUE", issue, ("issues", i), "Blocking issue remains unresolved.")

    def literal(node, typ, value, path):
        kind = typ["kind"]
        valid = isinstance(value, bool) if kind == "Boolean" else isinstance(value, str)
        if valid and kind in {"Decimal", "Money"}:
            valid = re.fullmatch(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?", value) is not None
        if valid and kind == "Integer":
            valid = re.fullmatch(r"0|-?[1-9][0-9]*", value) is not None
        if valid and kind == "SecretReference":
            valid = re.fullmatch(r"secret:[A-Za-z][A-Za-z0-9._:/-]*", value) is not None
        if valid and kind in {"Email", "DateTime", "Identifier"}:
            valid = bool(value.strip())
        if not valid:
            emit("TYPE", node, path, "Literal does not conform to its semantic type.")
        return typ if valid else None

    def expression(node, expr, context, path):
        tag = expr["tag"]
        if tag == "literal":
            return literal(node, expr["type"], expr["value"], path + ("value",))
        if tag == "parameter":
            return target(expr["ref"])["data"]["type"]
        if tag == "field":
            field = target(expr["ref"])["data"]
            if context.get(expr["binding"]) != field["owner"]:
                emit("OWNER", node, path, "Field does not belong to the selected expression binding.")
                return None
            if field["optional"]:
                emit("TYPE", node, path, "Optional field requires explicit presence narrowing, unsupported in this kernel.")
                return None
            return field["type"]
        left = expression(node, expr["left"], context, path + ("left",))
        right = expression(node, expr["right"], context, path + ("right",))
        if left is None or right is None:
            return None
        op = expr["op"]
        same = left == right
        numeric = left["kind"] in {"Integer", "Decimal", "Money"}
        valid = same and ((op == "eq" and left["kind"] != "SecretReference")
                          or (op in {"gt", "add"} and numeric)
                          or (op == "and" and left["kind"] == "Boolean"))
        if not valid:
            emit("TYPE", node, path, "Operator operands have incompatible semantic types.")
            return None
        return left if op == "add" else {"kind": "Boolean"}

    def same_owner(node, reference, key, expected, path):
        if target(reference)["data"][key] != expected:
            emit("OWNER", node, path, "Referenced concept belongs to a different semantic owner.")

    if extended:
        from type_semantics import Types
        types = Types(index, emit)
        literal, expression = types.literal, types.expression
    for node in nodes:
        kind, data = node["kind"], node["data"]
        if kind == "Parameter":
            literal(node, data["type"], data["value"], at(node, "data", "value"))
        if kind == "Field" and ((data["classification"] == "SECRET") != (data["type"]["kind"] == "SecretReference")):
            emit("SECRET", node, at(node, "data"), "Secret fields require both SecretReference type and SECRET classification.")
        if kind == "Entity":
            fields = [(r, at(node, "data", "identity", i), True) for i, r in enumerate(data["identity"])]
            if "tenantField" in data:
                fields.append((data["tenantField"], at(node, "data", "tenantField"), False))
            for r, path, identity in fields:
                field = target(r)["data"]
                same_owner(node, r, "owner", ref(node), path)
                if field["optional"] or field["type"]["kind"] != "Identifier" or (identity and field["type"].get("entity") != ref(node)):
                    emit("TYPE", node, path, "Identity/tenant fields require nonoptional typed identifiers with the correct entity binding.")
        if kind == "Command":
            for key in ("invariants", "emits"):
                for i, r in enumerate(data[key]):
                    same_owner(node, r, "resource", data["resource"], at(node, "data", key, i))
        if kind == "Event":
            for i, r in enumerate(data["payload"]):
                same_owner(node, r, "owner", data["resource"], at(node, "data", "payload", i))
        if kind == "Policy":
            same_owner(node, data["action"], "resource", data["resource"], at(node, "data", "action"))
            for i, r in enumerate(data["roles"]):
                same_owner(node, r, "actor", data["actor"], at(node, "data", "roles", i))
        if kind in {"Invariant", "Policy", "Transition"}:
            resource = data["resource"] if kind != "Transition" else target(data["machine"])["data"]["resource"]
            context = {"resource": resource}
            if "actor" in data:
                context["actor"] = target(data["actor"])["data"]["subject"]
            key = "guard" if kind == "Transition" else "predicate"
            result = expression(node, data[key], context, at(node, "data", key))
            if result is not None and result != {"kind": "Boolean"}:
                emit("TYPE", node, at(node, "data", key), "Predicate or guard must have Boolean type.")
        if kind == "Requirement":
            for i, r in enumerate(data["acceptance"]):
                if target(r)["data"]["requirement"] != ref(node):
                    emit("ACCEPTANCE", node, at(node, "data", "acceptance", i), "Criterion belongs to another requirement.")
        if kind == "AcceptanceCriterion":
            if ref(node) not in target(data["requirement"])["data"]["acceptance"]:
                emit("ACCEPTANCE", node, at(node, "data", "requirement"), "Requirement does not include this criterion.")

    machines = [n for n in nodes if n["kind"] == "StateMachine"]
    transitions = [n for n in nodes if n["kind"] == "Transition"]
    for machine in machines:
        same_owner(machine, machine["data"]["initial"], "machine", ref(machine), at(machine, "data", "initial"))
        states = [n for n in nodes if n["kind"] == "State" and n["data"]["machine"] == ref(machine)]
        triggers, edges = {}, {}
        for transition in transitions:
            data = transition["data"]
            if data["machine"] != ref(machine):
                continue
            for key in ("from", "to"):
                same_owner(transition, data[key], "machine", ref(machine), at(transition, "data", key))
            same_owner(transition, data["command"], "resource", machine["data"]["resource"], at(transition, "data", "command"))
            for i, r in enumerate(data["effects"]):
                same_owner(transition, r, "resource", machine["data"]["resource"], at(transition, "data", "effects", i))
            if target(data["from"])["data"]["terminal"]:
                emit("WORKFLOW", transition, at(transition, "data", "from"), "A terminal state cannot have an outgoing transition.")
            trigger = (data["from"]["id"], data["command"]["id"])
            triggers.setdefault(trigger, []).append(transition)
            if all(target(data[k])["data"]["machine"] == ref(machine) for k in ("from", "to")):
                edges.setdefault(data["from"]["id"], set()).add(data["to"]["id"])
        for alternatives in triggers.values():
            if len(alternatives) > 1:
                for transition in alternatives:
                    emit("WORKFLOW", transition, at(transition, "data", "command"), "Machine has an ambiguous state/command trigger.")
        reached, pending = set(), [machine["data"]["initial"]["id"]]
        while pending:
            current = pending.pop()
            if current not in reached:
                reached.add(current)
                pending.extend(edges.get(current, ()))
        for state in states:
            if state["id"] not in reached:
                emit("WORKFLOW", state, at(state, "data", "machine"), "State is unreachable from the initial state.")
    if extended:
        from phase1_semantics import checks
        checks(index, at, emit, semantic_items)
    return finish()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--mode", choices=("draft", "compile"), default="draft")
    args = parser.parse_args(argv)
    try:
        errors = validate(strict_load(args.snapshot), args.mode)
    except (OSError, UnicodeError, ValueError, RecursionError):
        errors = [diagnostic("INPUT", "", (), "Cannot decode a bounded strict UTF-8 snapshot.", "input")]
        print(json.dumps({"valid": False, "scope": "kernel", "diagnostics": errors}, indent=2))
        return 2
    print(json.dumps({"valid": not errors, "scope": "kernel", "mode": args.mode, "diagnostics": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
