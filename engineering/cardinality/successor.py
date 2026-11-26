"""Opt-in, unsealed cardinality qualification generator."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from engineering.generator_candidates.spring_vue_postgres_0_6.candidate import SuccessorCandidate
from compiler_contracts import Document
from engineering.cardinality import participation

ROOT = Path(__file__).resolve().parent
JAVA = 'backend/src/main/java/acp/infrastructure/'
MIGRATION = 'V10__tenant_cardinality.sql'


def sha(value):
    return hashlib.sha256(value).hexdigest()


def identifier(origin, prefix):
    return prefix + '_' + sha(origin.encode())[:24]


def sql_literal(value):
    if '\x00' in value:
        raise ValueError('CARDINALITY_APPLICATION_ID')
    return "'" + value.replace("'", "''") + "'"


def migration(application, nodes):
    index = {node['id']: node for node in nodes}
    relations = sorted((node for node in nodes if node['kind'] == 'Relation'), key=lambda node: node['id'])
    if not relations:
        return None, []
    guards = {}
    statements = [f"""CREATE FUNCTION acp_cardinality_key(value bytea) RETURNS bigint
LANGUAGE sql IMMUTABLE STRICT SET search_path = pg_catalog AS $$
 SELECT ('x' || substr(encode(sha256(
   convert_to('ACP','UTF8') || decode('00','hex') ||
   convert_to('CARDINALITY-TENANT/1','UTF8') || decode('00','hex') ||
   int4send(octet_length(convert_to({sql_literal(application)},'UTF8'))) ||
   convert_to({sql_literal(application)},'UTF8') || int4send(octet_length(value)) || value
 ),'hex'),1,16))::bit(64)::bigint
$$;
CREATE FUNCTION acp_cardinality_require(value bytea) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE key bigint := acp_cardinality_key(value);
BEGIN
 IF value IS NULL OR current_setting('transaction_isolation') <> 'read committed' OR NOT EXISTS (
   SELECT 1 FROM pg_locks WHERE pid=pg_backend_pid() AND locktype='advisory'
     AND database=(SELECT oid FROM pg_database WHERE datname=current_database())
     AND classid::bigint = ((key >> 32) & 4294967295)
     AND objid::bigint = (key & 4294967295)
     AND objsubid=2 AND mode='ExclusiveLock' AND granted
 ) THEN RAISE EXCEPTION 'ACP_CARDINALITY_COORDINATION_REQUIRED' USING ERRCODE='55000'; END IF;
 PERFORM pg_advisory_xact_lock((key >> 32)::integer, (key & 4294967295)::bit(32)::integer);
END
$$;
CREATE FUNCTION acp_cardinality_write_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE prior bytea; next_value bytea;
BEGIN
 IF TG_OP <> 'INSERT' THEN
   prior := (to_jsonb(OLD)->>TG_ARGV[0])::bytea;
   PERFORM acp_cardinality_require(prior);
 END IF;
 IF TG_OP <> 'DELETE' THEN
   next_value := (to_jsonb(NEW)->>TG_ARGV[0])::bytea;
   IF TG_OP = 'UPDATE' AND prior IS DISTINCT FROM next_value THEN
     RAISE EXCEPTION 'ACP_CARDINALITY_TENANT_IMMUTABLE' USING ERRCODE='55000';
   END IF;
   PERFORM acp_cardinality_require(next_value);
 END IF;
 RETURN NULL;
END
$$;
CREATE FUNCTION acp_cardinality_no_truncate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'ACP_CARDINALITY_TRUNCATE_UNSUPPORTED' USING ERRCODE='55000'; END
$$;"""]
    validations = []
    for relation in relations:
        data = relation['data']
        edge = identifier(relation['id'], 'r')
        guards[edge] = 'tenant'
        attached = {edge: 'tenant'}
        checks = []
        for role, counterpart in [('source', 'target'), ('target', 'source')]:
            endpoint = index[data[counterpart]['id']]
            entity = identifier(endpoint['id'], 'e')
            tenant = identifier(endpoint['data']['tenantField']['id'], 'f')
            key = identifier(endpoint['data']['identity'][0]['id'], 'f')
            attached[entity] = guards[entity] = tenant
            cardinality = data[role + 'Cardinality']
            invalid = [f"count(r.{role}_id) < {cardinality['min']}"]
            if cardinality['max'] != 'UNBOUNDED':
                invalid.append(f"count(r.{role}_id) > {cardinality['max']}")
            checks.append((f'SELECT 1 FROM {entity} e LEFT JOIN {edge} r '
                           f'ON r.tenant=e.{tenant} AND r.{counterpart}_id=e.{key}',
                           f'GROUP BY e.{tenant},e.{key} HAVING ' + ' OR '.join(invalid), tenant))
        fn = identifier(relation['id'], 'cardinality')
        branches = []
        for table, field in sorted(attached.items()):
            branches.append(f"WHEN '{table}' THEN column_name := '{field}';")
        scoped = '\n'.join(
            f"IF EXISTS ({query} WHERE e.{tenant} = affected {group}) THEN "
            "RAISE EXCEPTION 'ACP_RELATION_CARDINALITY' USING ERRCODE='23514'; END IF;"
            for query, group, tenant in checks)
        statements.append(f"""CREATE OR REPLACE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE affected bytea; column_name text;
BEGIN
 CASE TG_TABLE_NAME {' '.join(branches)} ELSE RAISE EXCEPTION 'ACP_CARDINALITY_TABLE'; END CASE;
 IF TG_OP = 'DELETE' THEN affected := (to_jsonb(OLD)->>column_name)::bytea;
 ELSE affected := (to_jsonb(NEW)->>column_name)::bytea; END IF;
 PERFORM acp_cardinality_require(affected);
 {scoped}
 RETURN NULL;
END
$$;""")
        validations.extend(
            f"IF EXISTS ({query} {group}) THEN "
            "RAISE EXCEPTION 'ACP_EXISTING_RELATION_CARDINALITY' USING ERRCODE='23514'; END IF;"
            for query, group, _ in checks)
    # Flyway holds these locks to transaction completion. Reject invalid retained
    # rows before admission and prevent changes between the check and install.
    statements.insert(0, 'LOCK TABLE ' + ','.join(sorted(guards)) + ' IN ACCESS EXCLUSIVE MODE;')
    statements.append('DO $$ BEGIN ' + ' '.join(validations) + ' END $$;')
    for table, column in sorted(guards.items()):
        statements.append(f"CREATE TRIGGER acp_cardinality_write AFTER INSERT OR UPDATE OR DELETE ON {table} "
                          f"FOR EACH ROW EXECUTE FUNCTION acp_cardinality_write_guard('{column}');")
        statements.append(f"CREATE TRIGGER acp_cardinality_truncate BEFORE TRUNCATE ON {table} "
                          'FOR EACH STATEMENT EXECUTE FUNCTION acp_cardinality_no_truncate();')
    return '\n'.join(statements) + '\n', [node['id'] for node in relations]


class CardinalityCandidate(SuccessorCandidate):
    """Experimental writer contract, independently fingerprinted from 0.6.0."""

    def __init__(self):
        super().__init__()
        self.cardinality_bundle = self._cardinality_digest()
        self.generator = 'acp-spring-vue-generator/0.6.0-cardinality+sha256:' + self.cardinality_bundle

    def _cardinality_digest(self):
        return sha(json.dumps({
            'parent': self.bundle,
            'overlay': sha(Path(__file__).read_bytes()),
            'participation': sha(Path(participation.__file__).read_bytes()),
            'coordination': sha((ROOT / 'templates/TenantCoordination.java').read_bytes()),
        }, sort_keys=True).encode())

    def descriptor(self):
        self._verify()
        if self._cardinality_digest() != self.cardinality_bundle:
            raise ValueError('CARDINALITY_OVERLAY_CHANGED')
        return {'profile': self.profile['profile'], 'generator': self.generator,
                'status': 'UNSEALED_CANDIDATE', 'scope': 'QUALIFICATION_ONLY',
                'sourceDigest': self.cardinality_bundle, 'parentSourceDigest': self.bundle,
                'productionAdmission': 'NOT_AUTHORIZED'}

    def plan_upgrade(self, previous, current, accepted_plan, bindings, history):
        # The inherited planner verifies actual history and separately approved
        # bindings. A bulk backfill on a guarded table needs its own stopped,
        # tenant-partitioned write plan and is outside this DDL-only path.
        result = super().plan_upgrade(previous, current, accepted_plan, bindings, history)
        old = previous.read()['content']
        new = current.read()['content']
        if old['schemaVersion'] != '0.3.0' or new['schemaVersion'] != '0.3.0':
            raise ValueError('CARDINALITY_UPGRADE_VERSION_UNSUPPORTED')
        old_nodes = {node['id']: node for node in old['nodes']}
        relations = [node for node in old['nodes'] if node['kind'] == 'Relation']
        endpoints = {node['data'][role]['id'] for node in relations for role in ('source', 'target')}
        nodes = {node['id']: node for node in new['nodes']}
        body = result.read()
        guarded = set()
        for operation in body['changes']:
            node = nodes[operation['id']]
            if node['kind'] != 'Field':
                raise ValueError('CARDINALITY_UPGRADE_RELATION_CHANGE_UNSUPPORTED')
            if 'BACKFILL' in operation['phases'] and node['data']['owner']['id'] in endpoints:
                guarded.add(node['data']['owner']['id'])
        if not guarded:
            return result
        # This value is part of the same independently approved bindings digest
        # verified by the inherited planner. No review or identity is inferred.
        tenant = bindings.read().get('cardinalityBackfillTenant')
        if type(tenant) is not str or not tenant:
            raise ValueError('CARDINALITY_UPGRADE_COORDINATED_BACKFILL_REQUIRED')
        tenant_sql = "decode('" + tenant.encode('utf-8').hex() + "','hex')"
        tables = {identifier(node, 'e') for node in endpoints}
        tables.update(identifier(node['id'], 'r') for node in relations)
        preflight = ['LOCK TABLE ' + ','.join(sorted(tables)) + ' IN ACCESS EXCLUSIVE MODE NOWAIT;']
        for endpoint in sorted(guarded):
            field = identifier(old_nodes[endpoint]['data']['tenantField']['id'], 'f')
            table = identifier(endpoint, 'e')
            preflight.append(f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM {table} WHERE {field} IS DISTINCT FROM {tenant_sql}) "
                             "THEN RAISE EXCEPTION 'ACP_CARDINALITY_BACKFILL_POPULATION'; END IF; END $$;")
        preflight.append(f'SELECT acp_cardinality_enter({tenant_sql});')
        # PostgreSQL prevents ALTER TABLE while this transaction has queued
        # trigger events. Validate the completed field update before sealing
        # its nullability, then restore the transaction's deferred mode.
        statements = []
        guarded_tables = {identifier(endpoint, 'e') for endpoint in guarded}
        for line in body['sql'].splitlines():
            parts = line.split()
            if len(parts) > 3 and parts[:2] == ['ALTER', 'TABLE'] and parts[2] in guarded_tables and line.endswith(' SET NOT NULL;'):
                statements.extend(['SET CONSTRAINTS ALL IMMEDIATE;', line, 'SET CONSTRAINTS ALL DEFERRED;'])
            else:
                statements.append(line)
        body['sql'] = '\n'.join(preflight + statements) + '\n'
        return Document.of(body)

    def lower(self, snapshot, *, compiler, pipeline):
        target = super().lower(snapshot, compiler=compiler, pipeline=pipeline)
        model = target.target_model.read()
        model['cardinalityApplication'] = snapshot.read()['content']['applicationId']
        return replace(target, target_model=Document.of(model))

    def _call(self, operation, payload):
        if self._cardinality_digest() != self.cardinality_bundle:
            raise ValueError('CARDINALITY_OVERLAY_CHANGED')
        rows = super()._call(operation, payload)
        if operation != 'plan':
            return rows
        model = payload['model']
        application = model['cardinalityApplication']
        sql, origins = migration(application, model['nodes'])
        if sql is None:
            return rows
        by = {row['path']: row for row in rows}
        source = by[JAVA + 'ExecutionStore.java']
        original = source['text']
        anchor = '    private final JdbcTemplate jdbc;'
        wiring = '        this.jdbc=jdbc; this.policy=policy; this.privacy=privacy;'
        locking = '        var rows=jdbc.query("SELECT * FROM " + table'
        if any(original.count(point) != 1 for point in (anchor, wiring, locking)):
            raise ValueError('CARDINALITY_RUNTIME_ANCESTRY')
        source['text'] = original.replace(anchor, anchor + '\n    private final TenantCoordination coordination;').replace(
            wiring, wiring + '\n        this.coordination=new TenantCoordination(jdbc,' + json.dumps(application, ensure_ascii=True) + ');').replace(
            locking, '        coordination.acquire(jwt.getClaimAsString("tenant"));\n' + locking)
        runtime = (ROOT / 'templates/TenantCoordination.java').read_text()
        anchor = '"SELECT pg_advisory_xact_lock(?, ?)"'
        binding = 'statement.setInt(1, (int) (key >>> 32));\n                statement.setInt(2, (int) key);'
        if runtime.count(anchor) != 1 or runtime.count(binding) != 1:
            raise ValueError('CARDINALITY_COMPONENT_ANCESTRY')
        runtime = runtime.replace(anchor, '"SELECT acp_cardinality_enter(?)"').replace(
            binding, 'statement.setBytes(1, authorizedTenant.getBytes(StandardCharsets.UTF_8));')
        additions = {
            JAVA + 'TenantCoordination.java': (runtime, 'CARDINALITY_RUNTIME'),
            'database/' + participation.MIGRATION: (participation.SQL, 'MIGRATION'),
            'backend/src/main/resources/db/migration/' + participation.MIGRATION: (participation.SQL, 'MIGRATION'),
            'database/' + MIGRATION: (sql, 'MIGRATION'),
            'backend/src/main/resources/db/migration/' + MIGRATION: (sql, 'MIGRATION'),
        }
        human = {item['path'] for item in payload['inventory'] if item['owner'] == 'HUMAN_OWNED'}
        if (set(additions) | {source['path'], 'acp/provenance.json', 'acp/target-upgrade.json'}) & human:
            raise ValueError('CARDINALITY_HUMAN_OWNERSHIP_CONFLICT')
        for path, (text, role) in additions.items():
            if path in by:
                raise ValueError('CARDINALITY_ARTIFACT_COLLISION')
            by[path] = {'path': path, 'text': text, 'role': role, 'owner': 'COMPILER_OWNED',
                        'origins': origins, 'verification': ['target-source-integrity']}
        provenance = json.loads(by['acp/provenance.json']['text'])
        build = provenance['build']
        generator = self.generator.split('+sha256:', 1)[0]
        build.update(generator=generator, bundleDigest='sha256:' + self.cardinality_bundle)
        for path, (text, role) in additions.items():
            if path.startswith('database/'):
                build['migrationDigests'][path] = sha(text.encode())
        upgrade = json.loads(by['acp/target-upgrade.json']['text'])
        upgrade.update(to=build, migrations=build['migrationDigests'], databaseChange='ADDITIVE_CARDINALITY_QUALIFICATION_ONLY')
        by['acp/target-upgrade.json']['text'] = json.dumps(upgrade, sort_keys=True, separators=(',', ':')) + '\n'
        for path in additions:
            row = by[path]
            provenance['artifacts'].append({
                'artifact': path, 'targetRole': row['role'], 'ownership': row['owner'],
                'originSet': 'canonical-model', 'targetObjects': [identifier(origin, 'target') for origin in origins],
                'locations': [], 'locationConfidence': 'ARTIFACT_ONLY',
            })
        for item in provenance['artifacts']:
            item.update(generator=generator, artifactDigest='sha256:' + sha(by[item['artifact']]['text'].encode()))
        provenance['artifacts'].sort(key=lambda item: item['artifact'])
        by['acp/provenance.json']['text'] = json.dumps(provenance, sort_keys=True, separators=(',', ':')) + '\n'
        return [by[path] for path in sorted(by)]
