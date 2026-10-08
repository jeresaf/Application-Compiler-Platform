"""Relation edge storage with same-tenant FKs and deferred cardinality checks."""
import hashlib


class RelationError(ValueError):
    pass


def identifier(origin, role):
    return role + '_' + hashlib.sha256(origin.encode()).hexdigest()[:24]


def relation_sql(relation, nodes):
    d = relation['data']
    source, target = (nodes[d[role]['id']] for role in ('source', 'target'))
    for endpoint in (source, target):
        if endpoint['data']['tenancy'] != 'SCOPED' or len(endpoint['data']['identity']) != 1:
            raise RelationError('RELATION_ENDPOINT_CONSTRAINT:' + relation['id'])
    if d['onDelete'] != 'RESTRICT':
        raise RelationError('RELATION_DELETE_CONSTRAINT:' + relation['id'])
    tenants = [nodes[e['data']['tenantField']['id']]['data']['type'] for e in (source, target)]
    if tenants[0] != tenants[1]:
        raise RelationError('RELATION_TENANT_TYPE_CONSTRAINT:' + relation['id'])
    if any(d[role + 'Cardinality']['min'] not in {0, 1} or d[role + 'Cardinality']['max'] not in {1, 'UNBOUNDED'} for role in ('source', 'target')):
        raise RelationError('RELATION_CARDINALITY_CONSTRAINT:' + relation['id'])
    table = identifier(relation['id'], 'r')
    definitions = ['tenant bytea NOT NULL', 'source_id bytea NOT NULL', 'target_id bytea NOT NULL', 'PRIMARY KEY(tenant,source_id,target_id)']
    for role, endpoint in (('source', source), ('target', target)):
        key = identifier(endpoint['data']['identity'][0]['id'], 'f')
        tenant = identifier(endpoint['data']['tenantField']['id'], 'f')
        definitions.append(f'FOREIGN KEY(tenant,{role}_id) REFERENCES {identifier(endpoint["id"], "e")}({tenant},{key}) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED')
    # A source cardinality describes sources per target, and vice versa.
    for role, counterpart in (('source', 'target'), ('target', 'source')):
        if d[role + 'Cardinality']['max'] == 1:
            definitions.append(f'UNIQUE(tenant,{counterpart}_id) DEFERRABLE INITIALLY DEFERRED')
    sql = [f'CREATE TABLE {table} (' + ','.join(definitions) + ');']
    fn = identifier(relation['id'], 'cardinality')
    body = []
    for endpoint in sorted((source, target), key=lambda n: n['id']):
        key = identifier(endpoint['data']['identity'][0]['id'], 'f')
        body.append(f'PERFORM 1 FROM {identifier(endpoint["id"], "e")} ORDER BY {key} FOR UPDATE;')
    for role, counterpart, endpoint in (('source', 'target', target), ('target', 'source', source)):
        cardinality = d[role + 'Cardinality']
        key = identifier(endpoint['data']['identity'][0]['id'], 'f')
        tenant = identifier(endpoint['data']['tenantField']['id'], 'f')
        tests = [f'count(r.{role}_id) < {cardinality["min"]}']
        if cardinality['max'] != 'UNBOUNDED':
            tests.append(f'count(r.{role}_id) > {cardinality["max"]}')
        body.append(f'IF EXISTS (SELECT 1 FROM {identifier(endpoint["id"], "e")} e LEFT JOIN {table} r ON r.tenant=e.{tenant} AND r.{counterpart}_id=e.{key} GROUP BY e.{tenant},e.{key} HAVING ' + ' OR '.join(tests) + ") THEN RAISE EXCEPTION 'ACP_RELATION_CARDINALITY'; END IF;")
    sql.append(f'CREATE FUNCTION {fn}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN ' + ' '.join(body) + ' RETURN NULL; END $$;')
    for on in sorted({table, identifier(source['id'], 'e'), identifier(target['id'], 'e')}):
        sql.append(f'CREATE CONSTRAINT TRIGGER {identifier(relation["id"] + ":" + on, "check")} AFTER INSERT OR UPDATE OR DELETE ON {on} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {fn}();')
    return '\n'.join(sql) + '\n'
