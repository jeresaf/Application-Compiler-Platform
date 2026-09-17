"""Task UI validation; no visual design, renderer, database binding or codegen."""


def checks(index, at, emit):
    nodes = list(index.values())
    target = lambda r: index[r["id"]]
    ref = lambda n: {"id": n["id"], "revision": n["revision"]}
    def error(node, message, code="UI"):
        emit(code, node, at(node, "data"), message)
    def projection(query):
        typ = target(query)["data"]["result"]
        return typ.get("definition") if typ["kind"] == "Value" else None
    def actions(usecase):
        return {target(s)["data"]["operation"]["id"] for s in target(usecase)["data"]["steps"]}

    for node in nodes:
        kind, d = node["kind"], node["data"]
        if kind == "Action":
            granted = {target(p)["data"]["action"]["id"] for p in d["permissions"]}
            if not actions(d["useCase"]) <= granted:
                error(node, "Action permissions must cover all invoked operations.")
        if kind == "Form":
            if target(d["submit"])["data"]["useCase"] != d["useCase"]:
                error(node, "Form submit action must invoke the form's use case.")
            if any(target(c)["data"]["form"] != ref(node) for c in d["controls"]):
                error(node, "Form controls must belong to that form.")
            fields = [target(c)["data"]["field"] for c in d["controls"]]
            required = [ref(f) for f in nodes if f["kind"] == "Field" and f["data"]["owner"] == target(d["useCase"])["data"]["input"] and not f["data"]["optional"]]
            if any(f not in fields for f in required) or len({f["id"] for f in fields}) != len(fields):
                error(node, "Form must cover required task inputs exactly once.")
        if kind == "InputControl":
            form = target(d["form"])
            field = target(d["field"])["data"]
            usecase = target(form["data"]["useCase"])["data"]
            if field["owner"] != usecase["input"] or target(field["owner"])["kind"] != "ValueObject" or ref(node) not in form["data"]["controls"]:
                error(node, "Controls bind to their form's task input, never entity fields.")
            if d["required"] != (not field["optional"]):
                error(node, "Control requiredness must match the task input.")
        if kind == "Wizard":
            screen = target(d["screen"])["data"]
            if ref(node) not in screen["content"]:
                error(node, "Wizard must be part of its screen.")
            for i, step in enumerate(d["steps"]):
                sd = target(step)["data"]
                if sd["wizard"] != ref(node) or sd["requiresPrevious"] != (i > 0) or target(sd["form"])["data"]["useCase"] != screen["task"]:
                    error(node, "Wizard steps must preserve ownership, task and prerequisites.")
        if kind == "WizardStep" and ref(node) not in target(d["wizard"])["data"]["steps"]:
            error(node, "Wizard step is absent from its owner.")
        if kind == "Table":
            if any(target(c)["data"]["owner"] != projection(d["query"]) for c in d["columns"]):
                error(node, "Table columns must belong to the query's value projection.")
        if kind == "Search" and any(target(f)["data"]["query"] != d["query"] for f in d["filters"]):
            error(node, "Search filters must belong to the same query.")
        if kind == "Filter":
            field = target(d["field"])["data"]
            if field["owner"] != projection(d["query"]) or field["type"] != d["inputType"]:
                error(node, "Filter type and field must match the query projection.")
            if d["operator"] == "CONTAINS" and d["inputType"]["kind"] != "String" or d["operator"] == "RANGE" and d["inputType"]["kind"] not in {"Integer", "Decimal", "Money", "Date", "Instant"}:
                error(node, "Filter operator is incompatible with its input type.")
        if kind == "PermissionBoundary":
            if any(target(p)["data"]["actor"] != d["actor"] for p in d["permissions"]):
                error(node, "Boundary permissions belong to another actor.")
            if target(d["denied"])["data"]["state"] != "ERROR":
                error(node, "Permission denial needs an explicit error state.")
        if kind == "Screen":
            states = [target(r)["data"] for r in d["states"]]
            if {s["state"] for s in states} != {"EMPTY", "LOADING", "ERROR", "SUCCESS"} or len(states) != 4 or any(s["screen"] != ref(node) for s in states):
                error(node, "Screen requires exactly one owned state for each outcome.")
            boundary = target(d["boundary"])["data"]
            if boundary["denied"] not in d["states"]:
                error(node, "Boundary denial state must belong to this screen.")
            needed = {p["id"] for a in d["actions"] for p in target(a)["data"]["permissions"]}
            for content in d["content"]:
                item = target(content)
                if item["kind"] in {"Table", "Search"}:
                    needed.update(p["id"] for p in nodes if p["kind"] == "Permission" and p["data"]["action"] == item["data"]["query"] and p["data"]["actor"] == boundary["actor"])
            if not needed <= {p["id"] for p in boundary["permissions"]} or any(target(a)["data"]["useCase"] != d["task"] for a in d["actions"]):
                error(node, "Screen boundary must cover its task actions and query views.")
            if target(d["responsive"])["data"]["screen"] != ref(node):
                error(node, "Responsive policy belongs to another screen.")
            if ref(node) not in target(d["accessibility"])["data"]["subjects"]:
                error(node, "Accessibility requirement must cover this screen.", "ACCESSIBILITY")
        if kind == "ViewState":
            screen = target(d["screen"])["data"]
            if ref(node) not in screen["states"] or (d["state"] == "ERROR" and "recovery" not in d):
                error(node, "View state must belong to its screen and errors need recovery.")
            if "recovery" in d and d["recovery"] not in screen["actions"]:
                error(node, "Recovery action must belong to the screen.")
        if kind == "ResponsivePolicy" and target(d["screen"])["data"]["responsive"] != ref(node):
            error(node, "Responsive policy is not selected by its screen.")
