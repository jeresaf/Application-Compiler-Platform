"""Bounded target evolution planning from accepted Phase 3 plans, never live diff.

An injected read-only port supplies accepted history and approved data bindings.
The target receives no journal mutation or semantic approval capability.
"""
import hashlib
import importlib.util
from pathlib import Path
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
    except (KeyError, PermissionError):
        raise MigrationBlocked("UNACCEPTED_HISTORY") from None
    try:
        if history.read_approved_bindings(digest, fingerprint(bindings, "migration-bindings")) != bindings:
            raise MigrationBlocked("UNAPPROVED_DATA_BINDINGS")
    except (KeyError, PermissionError):
        raise MigrationBlocked("UNAPPROVED_DATA_BINDINGS") from None
    before_version = before['content']['schemaVersion']
    after_version = after['content']['schemaVersion']
    # Semantic compatibility, persisted representation and relationship support
    # are independent decisions. Never reinterpret existing text as bytea.
    supported_versions = {'0.1.0', '0.2.0', '0.3.0'}
    semantic_transitions = {('0.1.0','0.1.0'),('0.2.0','0.2.0'),('0.3.0','0.3.0'),('0.2.0','0.3.0')}
    if before_version not in supported_versions or after_version not in supported_versions or (before_version,after_version) not in semantic_transitions:
        raise MigrationBlocked('SEMANTIC_VERSION_UNSUPPORTED')
    scalar_storage = {'0.1.0': 'legacy-text', '0.2.0': 'scalar-bytes', '0.3.0': 'scalar-bytes'}
    storage = scalar_storage[after_version]
    if scalar_storage[before_version] != storage:
        raise MigrationBlocked('INCOMPATIBLE_STORAGE_REPRESENTATION')
    relation_forms_supported = (before_version, after_version) == ('0.2.0', '0.2.0')
    backfill_encoding = 'utf-8-bytes' if storage == 'scalar-bytes' else 'sql-literal'
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
            if node['kind'] == 'Relation':
                if not relation_forms_supported:
                    raise MigrationBlocked('RELATION_STORAGE_VERSION')
                if any(node['data'][role + 'Cardinality']['min'] != 0 for role in ('source', 'target')):
                    raise MigrationBlocked('REQUIRED_RELATION_BACKFILL_BINDING')
                # Reuse the exact target DDL implementation, with no schema or
                # generic relationship inference in the semantic change model.
                path = Path(__file__).resolve().parents[1] / 'targets/spring-vue-postgres/worker/relations.py'
                spec = importlib.util.spec_from_file_location('acp_target_relation_ddl', path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                try:
                    sql.append(module.relation_sql(node, new))
                except module.RelationError as error:
                    raise MigrationBlocked(str(error)) from None
                changed.append({'id': id, 'revision': node['revision'], 'phases': ['EXPAND', 'VERIFY']})
                continue
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
        if storage == 'scalar-bytes':
            types = {'String': 'bytea', 'Boolean': 'boolean'}
        if typ["kind"] not in types:
            raise MigrationBlocked("FIELD_TYPE_UPGRADE_UNSUPPORTED")
        table, column = identifier(field["owner"]["id"], "e"), identifier(id, "f")
        sql.append(f"ALTER TABLE {table} ADD COLUMN {column} {types[typ['kind']]};")
        if storage == 'scalar-bytes' and field['optional'] and field['type']['kind'] == 'Nullable':
            presence = identifier(id, 'present')
            sql.append(f'ALTER TABLE {table} ADD COLUMN {presence} boolean NOT NULL DEFAULT false;')
            sql.append(f'ALTER TABLE {table} ADD CHECK ({presence} OR {column} IS NULL);')
        phases = ["EXPAND"]
        if not nullable:
            if plan["change"]["migration"]["mode"] != "REQUIRED" or id not in data.get("requiredFieldBackfills", {}):
                raise MigrationBlocked("REQUIRED_BACKFILL_BINDING")
            value = data["requiredFieldBackfills"][id]
            if ((typ["kind"] == "String" and type(value) is not str)
                    or (typ["kind"] == "Boolean" and type(value) is not bool)
                    or (typ["kind"] == "Integer" and type(value) is not int)):
                raise MigrationBlocked("BACKFILL_TYPE")
            encoded = "decode('" + value.encode('utf-8', 'strict').hex() + "','hex')" if backfill_encoding == 'utf-8-bytes' and type(value) is str else literal(value)
            sql += [f"UPDATE {table} SET {column}={encoded} WHERE {column} IS NULL;",
                    f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {table} WHERE {column} IS NULL) THEN RAISE EXCEPTION 'ACP_REQUIRED_BACKFILL_PRECONDITION'; END IF; END $$;",
                    f"ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL;"]
            phases += ["BACKFILL", "VERIFY", "SWITCH"]
        changed.append({"id": id, "revision": node["revision"], "phases": phases})
    if sql and storage == 'scalar-bytes':
        checks=[]
        for prior in old.values():
            if prior['kind'] != 'Field':continue
            field=prior['data'];typ=field['type']
            if typ['kind']=='Nullable':typ=typ['item']
            if typ['kind']!='String':continue
            table=identifier(field['owner']['id'],'e');column=identifier(prior['id'],'f')
            checks.append(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='{table}' AND column_name='{column}' AND udt_name<>'bytea') THEN RAISE EXCEPTION 'ACP_INCOMPATIBLE_STORAGE_REPRESENTATION'; END IF; END $$;")
        sql=checks+sql
    return Document.of({"version": "0.1.0", "phase3PlanDigest": digest,
        "previousSnapshot": before["contentDigest"], "nextSnapshot": after["contentDigest"],
        "bindingsDigest": fingerprint(bindings, "migration-bindings"), "changes": changed,
        "sql": "\n".join(sql) + ("\n" if sql else ""), "recovery": plan["change"]["migration"]["recovery"],
        "productionRollback": "NOT_CLAIMED"})
