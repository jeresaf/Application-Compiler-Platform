"""Separate authoring associations; no Design IR or renderer implementation."""
import json
from pathlib import Path
from jsonschema import Draft202012Validator

SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "contracts/design-bindings.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(SCHEMA)
VALIDATOR = Draft202012Validator(SCHEMA)
UI_KINDS = {"Screen", "Form", "InputControl", "Action", "Wizard", "WizardStep", "Table", "Search", "Filter", "ViewState"}


def validate_bindings(bindings, model):
    if not VALIDATOR.is_valid(bindings):
        return ["ACP-DESIGN-SHAPE"]
    if any(bindings[k] != model[k] for k in ("applicationId", "snapshotId")):
        return ["ACP-DESIGN-SNAPSHOT"]
    index = {n["id"]: n for n in model["nodes"]}
    errors, seen = set(), set()
    for binding in bindings["bindings"]:
        subject = binding["subject"]
        node = index.get(subject["id"])
        if node is None or node["revision"] != subject["revision"]:
            errors.add("ACP-DESIGN-REF")
        elif node["kind"] not in UI_KINDS:
            errors.add("ACP-DESIGN-KIND")
        if subject["id"] in seen:
            errors.add("ACP-DESIGN-DUPLICATE")
        seen.add(subject["id"])
    return sorted(errors)
