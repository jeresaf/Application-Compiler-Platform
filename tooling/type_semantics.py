"""Bounded, framework-neutral type algebra for authoring model 0.2.0."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_DOWN
import json
import re

DECIMAL = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?\Z")
INTEGER = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")
ROUNDING = {"HALF_EVEN": ROUND_HALF_EVEN, "HALF_UP": ROUND_HALF_UP, "DOWN": ROUND_DOWN}


def quantize(value, typ):
    """Explicit decimal operation; REJECT never silently rounds."""
    if not isinstance(value, str) or not DECIMAL.fullmatch(value) or len(value) > 128:
        raise ValueError("Invalid bounded decimal")
    with localcontext() as context:
        context.prec = 160
        number = Decimal(value)
        quantum = Decimal(1).scaleb(-typ["scale"])
        result = number.quantize(quantum, rounding=ROUNDING.get(typ["rounding"], ROUND_HALF_EVEN))
        if typ["rounding"] == "REJECT" and number != result:
            raise ValueError("Rounding required")
        if abs(result) >= Decimal(10) ** (typ["precision"] - typ["scale"]):
            raise ValueError("Precision overflow")
        return format(result, "f")


class Types:
    def __init__(self, index, emit):
        self.index, self.emit = index, emit

    def target(self, ref):
        return self.index[ref["id"]]

    def owned_fields(self, ref):
        return [n for n in self.index.values() if n["kind"] == "Field" and n["data"]["owner"] == ref]

    def declaration(self, typ, seen=()):
        kind = typ["kind"]
        if kind in {"Decimal", "Money"}:
            return typ["scale"] <= typ["precision"]
        if kind == "Nullable":
            return typ["item"]["kind"] != "Nullable" and self.declaration(typ["item"], seen)
        if kind in {"List", "Set"}:
            return typ["minItems"] <= typ["maxItems"] and self.declaration(typ["element"], seen)
        if kind in {"Named", "Value"}:
            key = typ["definition"]["id"]
            if key in seen:
                return False
            if kind == "Named":
                base = self.target(typ["definition"])["data"]["base"]
                return base["kind"] in {"String", "Integer", "Decimal", "Money", "Date", "Instant", "Duration"} and self.declaration(base, seen + (key,))
            fields = self.owned_fields(typ["definition"])
            return bool(fields) and all(self.declaration(f["data"]["type"], seen + (key,)) for f in fields)
        return True

    def valid_value(self, typ, value):
        if not self.declaration(typ):
            return False
        kind = typ["kind"]
        try:
            if kind == "Nullable":
                return value is None or self.valid_value(typ["item"], value)
            if kind == "Boolean":
                return type(value) is bool
            if kind in {"List", "Set"}:
                if not isinstance(value, list) or not typ["minItems"] <= len(value) <= typ["maxItems"]:
                    return False
                if not all(self.valid_value(typ["element"], v) for v in value):
                    return False
                keys = [self.value_key(typ["element"], v) for v in value]
                return kind == "List" or len(set(keys)) == len(keys)
            if kind == "Value":
                if not isinstance(value, dict):
                    return False
                fields = {f["id"]: f["data"] for f in self.owned_fields(typ["definition"])}
                return set(value) <= set(fields) and all(
                    (key not in value and f["optional"]) or
                    (key in value and self.valid_value(f["type"], value[key])) for key, f in fields.items())
            if kind == "Named":
                definition = self.target(typ["definition"])["data"]
                if not self.valid_value(definition["base"], value):
                    return False
                refinement = definition["refinement"]
                if refinement["kind"] == "NONE":
                    return True
                if refinement["kind"] == "LENGTH":
                    return isinstance(value, str) and refinement["min"] <= len(value) <= refinement["max"]
                return Decimal(refinement["min"]) <= Decimal(value) <= Decimal(refinement["max"])
            if not isinstance(value, str):
                return False
            if kind == "String":
                return True
            if kind in {"Decimal", "Money"}:
                exact = {**typ, "rounding": "REJECT"}
                quantize(value, exact)
                return True
            if kind in {"Integer", "Duration"}:
                return bool(INTEGER.fullmatch(value)) and (kind != "Duration" or not value.startswith("-"))
            if kind == "Identifier":
                return bool(value.strip())
            if kind == "SecretReference":
                return bool(re.fullmatch(r"secret:[A-Za-z][A-Za-z0-9._:/-]*", value))
            if kind == "Email":
                return bool(re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value))
            if kind == "Date":
                return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)) and date.fromisoformat(value) is not None
            if kind in {"Instant", "LocalDateTime"}:
                suffix = "Z" if kind == "Instant" else ""
                pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?" + suffix
                return bool(re.fullmatch(pattern, value)) and datetime.fromisoformat(value) is not None
        except (ValueError, InvalidOperation, TypeError):
            return False
        return False

    def value_key(self, typ, value):
        """Typed value equality, independent of serialization/map order."""
        kind = typ["kind"]
        if value is None:
            return ("null",)
        if kind == "Nullable":
            return self.value_key(typ["item"], value)
        if kind == "Named":
            return (json.dumps(typ, sort_keys=True), self.value_key(self.target(typ["definition"])["data"]["base"], value))
        if kind in {"Integer", "Duration", "Decimal", "Money"}:
            return (json.dumps(typ, sort_keys=True), Decimal(value))
        if kind in {"List", "Set"}:
            items = [self.value_key(typ["element"], v) for v in value]
            return (kind, tuple(items) if kind == "List" else frozenset(items))
        if kind == "Value":
            fields = {f["id"]: f["data"] for f in self.owned_fields(typ["definition"])}
            return (typ["definition"]["id"], tuple((k, self.value_key(fields[k]["type"], value[k])) for k in sorted(value)))
        if kind in {"Instant", "LocalDateTime"}:
            return (kind, datetime.fromisoformat(value))
        return (json.dumps(typ, sort_keys=True), value)

    def literal(self, node, typ, value, path):
        if not self.valid_value(typ, value):
            self.emit("TYPE", node, path, "Literal violates its declared semantic type or bounds.")
            return None
        return typ

    def expression(self, node, expr, context, path):
        tag = expr["tag"]
        if tag == "literal":
            return self.literal(node, expr["type"], expr["value"], path + ("value",))
        if tag == "parameter":
            return self.target(expr["ref"])["data"]["type"]
        if tag in {"field", "present"}:
            field = self.target(expr["ref"])["data"]
            if context.get(expr["binding"]) != field["owner"]:
                self.emit("OWNER", node, path, "Field does not belong to its expression binding.")
                return None
            if tag == "present":
                return {"kind": "Boolean"}
            return {"kind": "Optional", "item": field["type"]} if field["optional"] else field["type"]
        if tag in {"coalesce", "size"}:
            value = self.expression(node, expr["value"], context, path + ("value",))
            if value is None:
                return None
            if tag == "size" and value["kind"] in {"List", "Set"}:
                return {"kind": "Integer"}
            if tag == "coalesce":
                fallback = self.expression(node, expr["fallback"], context, path + ("fallback",))
                if value["kind"] in {"Optional", "Nullable"}:
                    unwrapped = value["item"]
                    if unwrapped["kind"] == "Nullable":
                        unwrapped = unwrapped["item"]
                    if fallback == unwrapped:
                        return fallback
            self.emit("TYPE", node, path, "Collection or presence operation has incompatible operands.")
            return None
        if tag == "contains":
            collection = self.expression(node, expr["collection"], context, path + ("collection",))
            value = self.expression(node, expr["value"], context, path + ("value",))
            if collection and value and collection["kind"] in {"List", "Set"} and collection["element"] == value:
                return {"kind": "Boolean"}
            self.emit("TYPE", node, path, "Membership requires a collection with a matching element type.")
            return None
        left = self.expression(node, expr["left"], context, path + ("left",))
        right = self.expression(node, expr["right"], context, path + ("right",))
        if left is None or right is None:
            return None
        kind, op = left["kind"], expr["op"]
        valid = left == right and (
            (op == "identityEq" and kind == "Identifier") or
            (op == "eq" and kind not in {"Identifier", "SecretReference", "Optional", "Nullable"}) or
            (op in {"gt", "add"} and kind in {"Integer", "Decimal", "Money", "Duration"}) or
            (op == "gt" and kind in {"Date", "Instant", "LocalDateTime"}) or
            (op == "and" and kind == "Boolean"))
        if not valid:
            self.emit("TYPE", node, path, "Operator requires matching nonnullable types and explicit identity/value semantics.")
            return None
        return left if op == "add" else {"kind": "Boolean"}
