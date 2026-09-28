"""Portable, synthetic evolution scenarios. No application source is generated."""
import copy
import json
from pathlib import Path

from changes import index, prepare
from canonical_fixtures import synthetic_approved
from canonical_ir import normalize_candidate
from reference_models import models


def no_migration():
    return {"id": "MIG-NONE", "mode": "NONE", "compatibility": "BACKWARD", "irreversible": False,
            "steps": [], "preconditions": [], "verification": [], "recovery": "No data operation", "observations": []}


def migration(irreversible=False):
    return {"id": "MIG-FORWARD", "mode": "REQUIRED", "compatibility": "BREAKING" if irreversible else "BACKWARD",
            "irreversible": irreversible, "steps": ["Expand", "Backfill", "Verify", "Contract after client retirement"],
            "preconditions": ["Review data observations and active clients"],
            "verification": ["Verify required values and retained constraints"],
            "recovery": "Forward repair; restore only after verified recovery review", "observations": []}


def change(id, base, operations, author="author", migration_plan=None):
    return {"changeVersion": "0.1.0", "id": id, "author": author, "intent": "Synthetic semantic evolution " + id,
            "branch": "BRANCH-" + id, "base": copy.deepcopy(base), "operations": operations, "reads": [],
            "migration": migration_plan or no_migration(), "sources": [], "parents": [], "rollbackOf": None}


def revise(snapshot, id, **updates):
    n = copy.deepcopy(index(snapshot)[id])
    prior = n["revision"]
    n.update(updates)
    n["revision"] = prior + 1
    return {"op": "REVISE", "id": id, "expectedRevision": prior, "node": n}


STEPS = ["stable-id-rename", "optional-relationship", "required-field", "security-tightening", "workflow-change"]


def evolution_change(snapshot, base, step):
    nodes = list(index(snapshot).values())
    entity = next(n for n in nodes if n["kind"] == "Entity")
    requirement = next(n for n in nodes if n["kind"] == "Requirement")
    reference = lambda n: {"id": n["id"], "revision": n["revision"]}
    mig = no_migration()
    if step == "stable-id-rename":
        op = revise(snapshot, entity["id"], name="Renamed " + entity["name"])
    elif step in {"optional-relationship", "required-field"}:
        n = {**copy.deepcopy(entity), "id": "EVOLUTION-" + step, "revision": 1,
             "name": step, "basis": [reference(requirement)]}
        if step == "optional-relationship":
            other = next(n for n in nodes if n["kind"] == "Entity" and n["id"] != entity["id"])
            n.update(kind="Relation", data={"source": reference(entity), "target": reference(other),
                "sourceCardinality": {"min": 0, "max": "UNBOUNDED"}, "targetCardinality": {"min": 0, "max": "UNBOUNDED"},
                "ownership": "REFERENCE", "onDelete": "RESTRICT"})
        else:
            cls = next(n for n in nodes if n["kind"] == "DataClassification" and n["data"]["level"] == "PUBLIC")
            n.update(kind="Field", data={"owner": reference(entity), "type": {"kind": "String"}, "optional": False,
                                          "classification": "PUBLIC", "classificationRef": reference(cls)})
            mig = migration()
        op = {"op": "ADD", "node": n}
    elif step == "security-tightening":
        n = next(n for n in nodes if n["kind"] == "SessionPolicy")
        op = revise(snapshot, n["id"], data={**n["data"], "idleSeconds": n["data"]["idleSeconds"] // 2})
    else:
        n = next(n for n in nodes if n["kind"] == "Transition")
        guard = {"tag": "binary", "op": "and", "left": n["data"]["guard"],
                 "right": {"tag": "literal", "type": {"kind": "Boolean"}, "value": False}}
        op = revise(snapshot, n["id"], data={**n["data"], "guard": guard})
    return change("CHANGE-" + step, base, [op], migration_plan=mig)


def vectors():
    result = {"scenarioVersion": "0.1.0", "domains": []}
    for name, model in models().items():
        snapshot = normalize_candidate(synthetic_approved(model))
        steps = [{"step": "initial-release", "contentDigest": snapshot["contentDigest"]}]
        for seq, step in enumerate(STEPS):
            base = {"sequence": seq, "digest": snapshot["contentDigest"], "journalDigest": "sha256:" + "0" * 64}
            plan = prepare(snapshot, evolution_change(snapshot, base, step))
            snapshot = plan["candidate"]
            steps.append({"step": step, "contentDigest": snapshot["contentDigest"], "writeSet": plan["writeSet"],
                          "risk": plan["risk"], "compatibility": plan["compatibility"]})
        result["domains"].append({"base": name, "steps": steps})
    return result


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[1] / "test-corpus/change/evolution.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(vectors(), indent=2) + "\n", encoding="utf-8")
