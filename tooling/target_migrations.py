"""Bounded target evolution planning from accepted Phase 3 plans, never live diff.

An injected read-only port supplies accepted history and approved data bindings.
The target receives no journal mutation or semantic approval capability.
"""
import hashlib
from typing import Protocol

from canonical_ir import validate_snapshot
from changes import fingerprint as change_fingerprint, rewrite
from compiler_contracts import Document, fingerprint


class AcceptedMigrationHistory(Protocol):
    def read_accepted_plan(self, plan_digest: str) -> Document: ...
    def read_approved_bindings(self, plan_digest: str, bindings_digest: str) -> Document: ...


class MigrationBlocked(ValueError):
    pass


def identifier(origin, role):
    return role + "_" + hashlib.sha256(origin.encode()).hexdigest()[:24]


def literal(value):
    if type(value) is str:
        if "\x00" in value:
            raise MigrationBlocked("BACKFILL_VALUE")
        return "'" + value.replace("'", "''") + "'"
    if type(value) is bool:
        return "TRUE" if value else "FALSE"
    if type(value) is int:
        return str(value)
    raise MigrationBlocked("BACKFILL_VALUE")


def plan_upgrade(previous, current, accepted_plan, bindings, history):
    """Return SQL only after exact history, snapshot and data-binding admission."""
    before, after, plan, data = previous.read(), current.read(), accepted_plan.read(), bindings.read()
    validate_snapshot(before)
    validate_snapshot(after)
    digest = plan.get("planDigest")
    body = {key: value for key, value in plan.items() if key != "planDigest"}
    if digest != change_fingerprint(body, "plan") or plan.get("kind") != "CHANGE":
        raise MigrationBlocked("PHASE3_PLAN_DIGEST")
    if (plan["candidate"] != after or plan["change"]["base"]["digest"] != before["contentDigest"]
            or before["content"]["applicationId"] != after["content"]["applicationId"]):
        raise MigrationBlocked("SNAPSHOT_BINDING")
    try:
        if history.read_accepted_plan(digest) != accepted_plan:
            raise MigrationBlocked("UNACCEPTED_HISTORY")
        if history.read_approved_bindings(digest, fingerprint(bindings, "migration-bindings")) != bindings:
            raise MigrationBlocked("UNAPPROVED_DATA_BINDINGS")
    except (KeyError, PermissionError):
        raise MigrationBlocked("UNACCEPTED_HISTORY") from None
    old = {node["id"]: node for node in before["content"]["nodes"]}
    new = {node["id"]: node for node in after["content"]["nodes"]}
    revisions = {id: (old[id]["revision"], new[id]["revision"]) for id in set(old) & set(new)}
    removed = set(old) - set(new)
    if removed or plan["tombstones"] or plan["change"]["migration"]["irreversible"]:
        # A future explicit reviewed contract artifact may extend this profile;
        # no destructive SQL is inferred even from an approved semantic removal.
        raise MigrationBlocked("DESTRUCTIVE_CONTRACT_UNSUPPORTED")
    sql = []
    changed = []
    for id in sorted(new):
        node = new[id]
        prior = old.get(id)
        if prior is not None:
            if node["kind"] != prior["kind"]:
                raise MigrationBlocked("SEMANTIC_KIND_CHANGED")
            if node["data"] != rewrite(prior["data"], revisions, {}) and node["kind"] in {"Entity", "Field", "Relation", "TypeDefinition", "ValueObject", "Constraint", "Invariant"}:
                raise MigrationBlocked("STRUCTURAL_UPGRADE_UNSUPPORTED:" + id)
            continue
        if node["kind"] != "Field":
            if node["kind"] in {"Entity", "Relation", "TypeDefinition", "ValueObject", "Constraint", "Invariant"}:
                raise MigrationBlocked("STRUCTURAL_UPGRADE_UNSUPPORTED:" + id)
            continue
        field = node["data"]
        if field["owner"]["id"] not in old or old[field["owner"]["id"]]["kind"] != "Entity":
            raise MigrationBlocked("FIELD_OWNER_UNSUPPORTED")
        typ = field["type"]
        nullable = field["optional"] or typ["kind"] == "Nullable"
        if typ["kind"] == "Nullable":
            typ = typ["item"]
        types = {"String": "text", "Boolean": "boolean", "Integer": "bigint", "Date": "date", "Instant": "timestamptz"}
        if typ["kind"] not in types:
            raise MigrationBlocked("FIELD_TYPE_UPGRADE_UNSUPPORTED")
        table, column = identifier(field["owner"]["id"], "e"), identifier(id, "f")
        sql.append(f"ALTER TABLE {table} ADD COLUMN {column} {types[typ['kind']]};")
        phases = ["EXPAND"]
        if not nullable:
            if plan["change"]["migration"]["mode"] != "REQUIRED" or id not in data.get("requiredFieldBackfills", {}):
                raise MigrationBlocked("REQUIRED_BACKFILL_BINDING")
            value = data["requiredFieldBackfills"][id]
            if ((typ["kind"] == "String" and type(value) is not str)
                    or (typ["kind"] == "Boolean" and type(value) is not bool)
                    or (typ["kind"] == "Integer" and type(value) is not int)):
                raise MigrationBlocked("BACKFILL_TYPE")
            sql += [f"UPDATE {table} SET {column}={literal(value)} WHERE {column} IS NULL;",
                    f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {table} WHERE {column} IS NULL) THEN RAISE EXCEPTION 'ACP_REQUIRED_BACKFILL_PRECONDITION'; END IF; END $$;",
                    f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL;"]
            phases += ["BACKFILL", "VERIFY", "SWITCH"]
        changed.append({"id": id, "revision": node["revision"], "phases": phases})
    return Document.of({"version": "0.1.0", "phase3PlanDigest": digest,
        "previousSnapshot": before["contentDigest"], "nextSnapshot": after["contentDigest"],
        "bindingsDigest": fingerprint(bindings, "migration-bindings"), "changes": changed,
        "sql": "\n".join(sql) + ("\n" if sql else ""), "recovery": plan["change"]["migration"]["recovery"],
        "productionRollback": "NOT_CLAIMED"})
