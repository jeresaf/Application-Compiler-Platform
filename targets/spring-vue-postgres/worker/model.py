"""Pure lowering. Stable semantic identity drives SQL/API identifiers."""
import hashlib
import json
from capability_contract import capabilities, OBLIGATIONS, PENDING


def identifier(origin, role):
    return role + "_" + hashlib.sha256(origin.encode()).hexdigest()[:24]


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


class CapabilityError(ValueError):
    pass


METADATA = OBLIGATIONS
SUPPORTED = {k.split('/')[0] for k,v in capabilities().items() if v['status']=='SUPPORTED_WITH_CONSTRAINT' and k.endswith('/0.2.0')}


def manifest(profile):
    return {**profile, "releaseStatus": "INCOMPLETE", "capabilities": capabilities(),
            "semanticCompatibility": {"0.1.0": {"semanticModel":"0.2.0","policy":"legacy constrained subset"}, "0.2.0": {"semanticModel":"0.3.0","feature":"acp.execution.0.3","policy":"preserved legacy subset; paginated ordering remains blocked"}, "0.3.0": {"semanticModel":"0.4.0","feature":"acp.deterministic-execution.0.4","policy":"explicit deterministic invocation subset; unfinished families block full admission"}},
            "nodeCapabilityVersionMeaning":"0.2.0 denotes node-kind interface identity, not Canonical schema compatibility",
            "requiredDecisions": profile["decisions"],
            "ownership": ["COMPILER_OWNED", "FRAMEWORK_OWNED", "AI_MANAGED", "HUMAN_OWNED"],
            "migrations": ["flyway-versioned", "expand-backfill-switch-contract"],
            "verification": ["IMPLEMENTED_TARGET_SITE", "TEST_PLANNED", "OUTSTANDING"],
            "limits": {"inputBytes": 4000000, "outputBytes": 16000000, "nodes": 4000, "timeoutSeconds": 30}}


def negotiate(nodes, required, decisions, profile, canonical_version='0.1.0'):
    if (type(nodes) is not list or len(nodes) > 4000 or type(required) is not list
            or any(type(c) is not str for c in required)
            or any(type(n) is not dict or type(n.get("id")) is not str or type(n.get("kind")) is not str
                   or type(n.get("revision")) is not int or n["revision"] < 1 for n in nodes)
            or len({n["id"] for n in nodes}) != len(nodes)):
        raise CapabilityError("SEMANTIC_INPUT")
    known = capabilities(canonical_version)
    errors = []
    if canonical_version not in {'0.1.0', '0.2.0', '0.3.0'}:
        errors.append('CANONICAL_VERSION')
    if canonical_version!='0.3.0' and 'acp.deterministic-execution.0.4' in required:
        errors.append('CANONICAL_FEATURE_MISMATCH')
    if canonical_version=='0.3.0' and 'acp.deterministic-execution.0.4' not in required:
        errors.append('DETERMINISTIC_FEATURE_REQUIRED')
    if canonical_version in {'0.2.0', '0.3.0'}:
        if 'semantic.execution-dataflow/0.3' not in required:
            errors.append('EXPLICIT_EXECUTION_CAPABILITY_REQUIRED')
        from execution_codegen import ExecutionGenerator
        try:
            if any(n['kind'] in {'Command', 'Query', 'UseCase'} and 'input' not in n['data'] for n in nodes):
                raise CapabilityError('EXPLICIT_EFFECTS_REQUIRED')
            ExecutionGenerator(nodes, canonical_version).validate()
            if canonical_version=='0.3.0' and profile.get('targetIRVersion')=='0.2.0':
                from delivery_jobs import validate
                validate(nodes)
                from privacy_lifecycle import validate as validate_privacy
                validate_privacy(nodes)
                from task_ui import validate as validate_ui
                validate_ui(nodes)
                from delivery_jobs import generated_jobs
                generated_jobs(ExecutionGenerator(nodes,canonical_version))
        except (CapabilityError, KeyError, TypeError) as e:
            errors.append(str(e) if isinstance(e, CapabilityError) else 'EXPLICIT_EFFECTS_REQUIRED')
    elif any(n['kind'] == 'Command' and 'assignments' in n['data'] for n in nodes):
        errors.append('CANONICAL_VERSION')
    if canonical_version not in {'0.2.0', '0.3.0'} and (any(n['kind'] in {'Command', 'UseCase'} for n in nodes)
            or 'UseCase/0.2.0' in required or 'semantic.execution-dataflow/0.3' in required):
        errors.append('EXPLICIT_EFFECTS_REQUIRED')
    for capability in sorted(set(required) | {n["kind"] + "/0.2.0" for n in nodes}):
        if capability not in known or known[capability]["status"] == "UNSUPPORTED":
            errors.append("UNSUPPORTED:" + capability)
    if decisions != profile["decisions"]:
        errors.append("REQUIRED_DECISIONS")
    if canonical_version in {'0.2.0', '0.3.0'} and sum(n['kind'] == 'AuthenticationModel' for n in nodes) != 1:
        errors.append('AUTHENTICATION_ACTOR_CONSTRAINT')
    for n in nodes:
        if canonical_version in {'0.2.0', '0.3.0'} and n['kind'] == 'AuthenticationModel':
            if n['data'].get('assurance') != 'MULTI_FACTOR' or set(n['data'].get('mechanisms', [])) != {'KNOWLEDGE', 'POSSESSION'}:
                errors.append('AUTHENTICATION_ASSURANCE_CONSTRAINT:' + n['id'])
        if canonical_version in {'0.2.0', '0.3.0'} and n['kind'] == 'Relation':
            from relations import relation_sql, RelationError
            try:
                relation_sql(n, {node['id']: node for node in nodes})
            except RelationError as error:
                errors.append(str(error))
        if canonical_version == '0.2.0' and n['kind'] == 'Query' and n['data'].get('paginated'):
            errors.append('QUERY_ORDERING_REVIEW_REQUIRED:' + n['id'])
        if canonical_version == '0.2.0' and n['kind'] in {'Retention', 'DeletionPolicy'} and n['data'].get('trigger') == 'CLOSED':
            errors.append('CLOSED_TRIGGER_BINDING_REVIEW_REQUIRED:' + n['id'])
        if canonical_version == '0.2.0' and n['kind'] == 'DeletionPolicy' and n['data'].get('mode') == 'ANONYMIZE':
            errors.append('ANONYMIZATION_VALUES_REVIEW_REQUIRED:' + n['id'])
        if n["kind"] == "Field":
            try:
                sql_type(n["data"]["type"], {node["id"]: node for node in nodes})
            except CapabilityError:
                errors.append("TYPE:" + n["id"])
    if errors:
        raise CapabilityError(";".join(sorted(set(errors))))
    return {"accepted": True, "capabilities": sorted(set(required) | {n["kind"] + "/0.2.0" for n in nodes})}


def sql_type(t, nodes=None, seen=(), *, execution=False):
    kind = t["kind"]
    if kind == "Nullable":
        return sql_type(t["item"], nodes, seen, execution=execution)
    if execution and kind in {'Identifier', 'String', 'Value'}:
        # PostgreSQL text/jsonb cannot represent U+0000. UTF-8 bytea preserves
        # every semantic Unicode scalar without narrowing String/Value types.
        return 'bytea'
    simple = {"Identifier": "text", "String": "text", "Boolean": "boolean", "Integer": "bigint", "Date": "date", "Instant": "timestamptz", "Duration": "bigint"}
    if kind in simple:
        return simple[kind]
    if kind in {"Money", "Decimal", "Percentage"}:
        precision, scale = t.get("precision"), t.get("scale")
        if type(precision) is not int or type(scale) is not int or not 0 <= scale <= precision <= 38 or t.get("rounding") != "REJECT":
            raise CapabilityError("DECIMAL_CONSTRAINT")
        return f"numeric({precision},{scale})"
    if kind == "Value":
        return "jsonb"
    if kind == "Named":
        ref = t["definition"]["id"]
        if nodes is None or ref in seen or ref not in nodes:
            raise CapabilityError("TYPE_REQUIRES_RESOLUTION")
        return sql_type(nodes[ref]["data"]["base"], nodes, (*seen, ref), execution=execution)
    raise CapabilityError("TYPE:" + kind)


def lower(nodes, profile, canonical_version='0.1.0'):
    by_id = {n["id"]: n for n in nodes}
    grouped = lambda kind: [n for n in nodes if n["kind"] == kind]
    tables = []
    for entity in grouped("Entity"):
        fields = [n for n in grouped("Field") if n["data"]["owner"]["id"] == entity["id"]]
        columns = []
        for f in fields:
            t = f["data"]["type"]
            columns.append({"origin": {"id": f["id"], "revision": f["revision"]}, "name": identifier(f["id"], "f"),
                            "sqlType": sql_type(t, by_id, execution=canonical_version in {'0.2.0', '0.3.0'}), "type": t,
                            "nullable": bool(f["data"]["optional"] or t["kind"] == "Nullable"),
                            "optionalUpdate": bool(f["data"]["optional"]), "classification": f["data"]["classification"]})
            if canonical_version in {'0.2.0', '0.3.0'} and f['data']['optional'] and t['kind'] == 'Nullable':
                columns[-1]['presence'] = identifier(f['id'], 'present')
        tables.append({"origin": {"id": entity["id"], "revision": entity["revision"]},
                       "name": identifier(entity["id"], "e"), "columns": columns, "semantic": entity["data"]})
    api = []
    for n in grouped("Command") + grouped("Query") + grouped("UseCase"):
        permissions = [p["id"] for p in grouped("Permission") if p["data"]["action"]["id"] == n["id"]]
        api.append({"origin": {"id": n["id"], "revision": n["revision"]}, "path": "/api/" + identifier(n["id"], "op"),
                    "method": "GET" if n["kind"] == "Query" and canonical_version not in {'0.2.0', '0.3.0'} else "POST", "role": n["kind"],
                    "permissions": permissions, "semantic": n["data"],
                    "errors": [400, 401, 403, 404, 409, 422, 429],
                    "concurrency": "expectedVersion", "pagination": {"maximum": n["data"].get("maximumResults", 100)}})
    result = {"version": profile.get("targetIRVersion", "0.1.0"), "profile": profile["profile"], "generator": profile["generator"],
            "objects": [{"id": identifier(n["id"], "target"), "role": n["kind"],
                         "origin": {"id": n["id"], "revision": n["revision"]}} for n in nodes],
            "tables": tables, "api": api, "screens": grouped("Screen"),
            "nodes": nodes, "stack": profile["stack"], "design": profile["decisions"]["design"]}
    if canonical_version in {'0.2.0', '0.3.0'}:
        result['canonicalVersion'] = canonical_version
        result['requiredCapabilities'] = ['semantic.execution-dataflow/0.3'] + (['acp.deterministic-execution.0.4'] if canonical_version=='0.3.0' else [])
    return result
