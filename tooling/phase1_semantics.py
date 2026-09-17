"""Graph constraints for Phase 1 authoring semantics, evaluated after references."""
from decimal import Decimal, InvalidOperation
from type_semantics import Types


def typed_references(value, shape, defs, expect, node, path):
    if "x-acp-targetKinds" in shape and shape["x-acp-targetKinds"]:
        expect(node, value, set(shape["x-acp-targetKinds"]), path)
    if "$ref" in shape:
        typed_references(value, defs[shape["$ref"].split("/")[-1]], defs, expect, node, path)
    if isinstance(value, dict):
        for key, child in shape.get("properties", {}).items():
            if key in value:
                typed_references(value[key], child, defs, expect, node, path + (key,))
    if isinstance(value, list) and "items" in shape:
        for i, child in enumerate(value):
            typed_references(child, shape["items"], defs, expect, node, path + (i,))
    for child in shape.get("oneOf", []):
        # Discriminated records: only the matching shape contributes references.
        props = child.get("properties", {})
        discriminators = [(k, v.get("enum", [v.get("const")])) for k, v in props.items() if "enum" in v or "const" in v]
        if isinstance(value, dict) and discriminators and all(value.get(k) in allowed for k, allowed in discriminators):
            typed_references(value, child, defs, expect, node, path)


def checks(index, at, emit, walk):
    types = Types(index, emit)
    by_kind = lambda kind: [n for n in index.values() if n["kind"] == kind]
    target = lambda r: index[r["id"]]
    ref = lambda n: {"id": n["id"], "revision": n["revision"]}
    def error(code, node, message, *path):
        emit(code, node, at(node, "data", *path), message)

    for node in index.values():
        for item, path in walk(node["data"], at(node, "data")):
            if isinstance(item, dict) and item.get("kind") in {"Named", "Value", "Nullable", "List", "Set", "Decimal", "Money"}:
                if not types.declaration(item):
                    emit("TYPE", node, path, "Invalid, cyclic, or inconsistent type declaration.")
        if node["kind"] == "ValueObject" and not types.declaration({"kind": "Value", "definition": ref(node)}):
            error("DOMAIN", node, "Value object requires a nonempty acyclic field definition.")
        if node["kind"] == "TypeDefinition":
            data = node["data"]
            r, base = data["refinement"], data["base"]
            valid = types.declaration({"kind": "Named", "definition": ref(node)})
            if r["kind"] == "LENGTH":
                valid &= base["kind"] == "String" and r["min"] <= r["max"]
            if r["kind"] == "RANGE":
                try:
                    valid &= base["kind"] in {"Integer", "Decimal", "Money", "Duration"} and types.valid_value(base, r["min"]) and types.valid_value(base, r["max"]) and Decimal(r["min"]) <= Decimal(r["max"])
                except (ValueError, InvalidOperation):
                    valid = False
            if data["semantics"] == "REFINED" and r["kind"] == "NONE":
                valid = False
            if not valid:
                error("TYPE", node, "Type definition has an unsupported base or inconsistent refinement.")

    owners = {}
    for aggregate in by_kind("Aggregate"):
        data = aggregate["data"]
        if data["root"] not in data["members"]:
            error("AGGREGATE", aggregate, "Aggregate root must be a member.")
        for member in data["members"]:
            owners.setdefault(member["id"], []).append(aggregate)
        for invariant in data["invariants"]:
            if target(invariant)["data"]["resource"] not in data["members"]:
                error("AGGREGATE", aggregate, "Aggregate invariant targets a nonmember.")
    for memberships in owners.values():
        if len(memberships) > 1:
            for aggregate in memberships:
                error("AGGREGATE", aggregate, "Entity cannot belong to multiple consistency owners.")
    edges = {}
    for relation in by_kind("Relation"):
        data = relation["data"]
        for key in ("sourceCardinality", "targetCardinality"):
            card = data[key]
            if card["max"] != "UNBOUNDED" and card["min"] > card["max"]:
                error("CARDINALITY", relation, "Cardinality minimum exceeds maximum.", key)
        if data["ownership"] == "COMPOSITION":
            if data["sourceCardinality"] != {"min": 1, "max": 1}:
                error("OWNERSHIP", relation, "A composed value has exactly one owning entity.")
            edges.setdefault(data["source"]["id"], set()).add(data["target"]["id"])
            source_owners, target_owners = owners.get(data["source"]["id"], []), owners.get(data["target"]["id"], [])
            if len(source_owners) != 1 or source_owners != target_owners:
                error("AGGREGATE", relation, "Composition must stay inside one aggregate.")
        elif data["onDelete"] == "DELETE_OWNED":
            error("OWNERSHIP", relation, "Reference relations cannot delete the referenced entity.")
        if data["onDelete"] == "DETACH" and data["sourceCardinality"]["min"] > 0:
            error("CARDINALITY", relation, "Detach would violate the surviving endpoint minimum.")
    for relation in by_kind("Relation"):
        data = relation["data"]
        if data["ownership"] != "COMPOSITION":
            continue
        seen, pending = set(), [data["target"]["id"]]
        while pending:
            current = pending.pop()
            if current == data["source"]["id"]:
                error("OWNERSHIP", relation, "Composition contains a cycle.")
                break
            if current not in seen:
                seen.add(current)
                pending.extend(edges.get(current, ()))
    from security_semantics import checks as security_checks
    security_checks(index, at, emit, types)
    from execution_semantics import checks as execution_checks
    execution_checks(index, at, emit, types)
    from ui_semantics import checks as ui_checks
    ui_checks(index, at, emit)
    from quality_semantics import checks as quality_checks
    quality_checks(index, at, emit, types)
