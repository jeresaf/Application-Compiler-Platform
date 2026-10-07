"""Deterministic source planner. Templates are loaded before worker confinement."""
import hashlib
import json
from decimal import Decimal
from model import CapabilityError, encoded, identifier


def schema(model):
    tables = {t["origin"]["id"]: t for t in model["tables"]}
    nodes = {n["id"]: n for n in model["nodes"]}
    sql = []
    later = []
    for entity, table in sorted(tables.items()):
        data = table["semantic"]
        columns = {c["origin"]["id"]: c for c in table["columns"]}
        identity = [columns[r["id"]]["name"] for r in data["identity"]]
        tenant = columns[data["tenantField"]["id"]]["name"] if data["tenancy"] == "SCOPED" else None
        definitions = [f'{c["name"]} {c["sqlType"]}' + ("" if c["nullable"] else " NOT NULL") for c in table["columns"]]
        definitions += ["acp_version bigint NOT NULL DEFAULT 0 CHECK (acp_version >= 0)", "acp_state text", "PRIMARY KEY (" + ",".join(identity) + ")"]
        for invariant in (n for n in nodes.values() if n["kind"] == "Invariant" and n["data"]["resource"]["id"] == entity):
            predicate = invariant["data"]["predicate"]
            if (predicate.get("tag") == "binary" and predicate.get("op") in {"gt", "gte"}
                    and predicate["left"].get("tag") == "field" and predicate["right"].get("tag") == "parameter"):
                column = columns[predicate["left"]["ref"]["id"]]["name"]
                value = nodes[predicate["right"]["ref"]["id"]]["data"]["value"]
                literal = str(Decimal(value))
                definitions.append(f'CONSTRAINT {identifier(invariant["id"], "ck")} CHECK ({column} {">" if predicate["op"] == "gt" else ">="} {literal})')
        if tenant:
            definitions.append("UNIQUE (" + ",".join([tenant, *identity]) + ")")
        sql.append("CREATE TABLE " + table["name"] + " (\n  " + ",\n  ".join(definitions) + "\n);")
        if tenant:
            sql.append(f'CREATE INDEX {identifier(entity, "ix")} ON {table["name"]} ({tenant});')
        for c in table["columns"]:
            typ = c["type"]
            if typ["kind"] == "Nullable":
                typ = typ["item"]
            if typ["kind"] != "Identifier" or typ["entity"]["id"] == entity:
                continue
            referred = tables[typ["entity"]["id"]]
            target_ids = [identifier(ref["id"], "f") for ref in referred["semantic"]["identity"]]
            if len(target_ids) != 1:
                raise CapabilityError("COMPOSITE_REFERENCE")
            left, right = [c["name"]], target_ids
            if tenant and referred["semantic"]["tenancy"] == "SCOPED":
                left.insert(0, tenant)
                right.insert(0, identifier(referred["semantic"]["tenantField"]["id"], "f"))
            later.append(f'ALTER TABLE {table["name"]} ADD CONSTRAINT {identifier(c["origin"]["id"], "fk")} FOREIGN KEY ({",".join(left)}) REFERENCES {referred["name"]} ({",".join(right)}) ON DELETE RESTRICT;')
    sql.extend(later)
    sql += ["CREATE TABLE acp_audit (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, tenant text NOT NULL, subject text NOT NULL, operation text NOT NULL, resource text NOT NULL, occurred_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP);",
            "CREATE TABLE acp_outbox (id text PRIMARY KEY, tenant text NOT NULL, event text NOT NULL, resource text NOT NULL, aggregate_version bigint NOT NULL, delivered_at timestamptz, UNIQUE(tenant,event,resource,aggregate_version));"]
    return "\n".join(sql) + "\n"


def plan(model, templates, profile, inventory=()):
    all_ids = sorted(n["id"] for n in model["nodes"])
    artifacts = []
    human_paths = {item["path"] for item in inventory if item["owner"] == "HUMAN_OWNED"}

    def add(path, text, role, origins=None, owner="COMPILER_OWNED"):
        if path in human_paths:
            return
        if not text.endswith("\n"):
            text += "\n"
        artifacts.append({"path": path, "text": text, "role": role, "owner": owner,
                          "origins": origins or all_ids, "verification": ["target-source-integrity"]})

    for path, text in sorted(templates.items()):
        add(path, text, "PROJECT_SOURCE", owner="FRAMEWORK_OWNED" if path.endswith(("pom.xml", "package.json")) else "COMPILER_OWNED")
    add("backend/src/main/resources/acp-model.json", encoded(model), "RUNTIME_MODEL")
    add("contracts/target-ir.json", encoded(model), "TARGET_IR")
    add("acp/profile.json", encoded(profile), "PROFILE")
    sql = schema(model)
    add("backend/src/main/resources/db/migration/V1__initial.sql", sql, "MIGRATION")
    add("database/V1__initial.sql", sql, "MIGRATION")
    paths = {}
    for op in model["api"]:
        paths.setdefault(op["path"], {})[op["method"].lower()] = {
            "operationId": identifier(op["origin"]["id"], "op"),
            "security": [{"oidc": []}], "responses": {"200": {"description": "Successful operation"}, **{str(code): {"description": "Structured target error"} for code in op["errors"]}}}
    add("contracts/openapi.json", encoded({"openapi": "3.1.0", "info": {"title": "ACP generated API", "version": "0.1.0"}, "paths": paths,
        "components": {"securitySchemes": {"oidc": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}}}), "API_CONTRACT")
    add("frontend/src/model.ts", "export const model = " + encoded(model).strip() + " as const;\n", "TASK_UI_MODEL")
    sidecars = []
    for a in sorted(artifacts, key=lambda a: a["path"]):
        sidecars.append({"artifact": a["path"], "artifactDigest": "sha256:" + hashlib.sha256(a["text"].encode()).hexdigest(),
                         "generator": profile["generator"], "targetRole": a["role"], "ownership": a["owner"],
                         "origins": [{"id": n["id"], "revision": n["revision"]} for n in model["nodes"] if n["id"] in a["origins"]],
                         "targetObjects": [identifier(id, "target") for id in a["origins"]],
                         "locations": [], "locationConfidence": "ARTIFACT_ONLY"})
    add("acp/provenance.json", encoded({"version": "0.1.0", "artifacts": sidecars}), "PROVENANCE")
    return sorted(artifacts, key=lambda a: a["path"])


def validate_plan(artifacts):
    seen = set()
    allowed = {"COMPILER_OWNED", "FRAMEWORK_OWNED", "AI_MANAGED", "HUMAN_OWNED"}
    for a in artifacts:
        path = a["path"]
        if not isinstance(path, str) or any(part in {"", ".", ".."} for part in path.split("/")) or any(c in path for c in "\\:\x00") or any(ord(c) < 32 for c in path):
            raise CapabilityError("PATH")
        if path in seen or any(path.startswith(p + "/") or p.startswith(path + "/") for p in seen):
            raise CapabilityError("PATH_COLLISION")
        if a["owner"] not in allowed or not a["origins"] or not a["verification"] or "\r" in a["text"]:
            raise CapabilityError("ARTIFACT")
        seen.add(path)
    return {"accepted": True, "artifacts": len(artifacts)}
