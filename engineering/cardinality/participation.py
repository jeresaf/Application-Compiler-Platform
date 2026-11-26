"""Additive participation state owned by the migration principal."""

MIGRATION = 'V11__cardinality_participation.sql'

SQL = """CREATE TABLE acp_cardinality_participation (
    tenant bytea PRIMARY KEY,
    transaction_id xid8 NOT NULL UNIQUE
);
REVOKE ALL ON acp_cardinality_participation FROM PUBLIC;

CREATE FUNCTION acp_cardinality_enter(value bytea) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE key bigint := acp_cardinality_key(value);
        xid xid8 := pg_current_xact_id();
BEGIN
 IF value IS NULL OR octet_length(value) = 0
    OR current_setting('transaction_isolation') <> 'read committed' THEN
    RAISE EXCEPTION 'ACP_CARDINALITY_TRANSACTION_REQUIRED' USING ERRCODE='55000';
 END IF;
 IF EXISTS (SELECT FROM acp_cardinality_participation
            WHERE transaction_id=xid AND tenant<>value) THEN
    RAISE EXCEPTION 'ACP_CARDINALITY_MULTI_TENANT_UNSUPPORTED' USING ERRCODE='55000';
 END IF;
 PERFORM pg_advisory_xact_lock((key >> 32)::integer, (key & 4294967295)::bit(32)::integer);
 INSERT INTO acp_cardinality_participation(tenant,transaction_id) VALUES (value,xid)
 ON CONFLICT (tenant) DO UPDATE SET transaction_id=EXCLUDED.transaction_id
 WHERE acp_cardinality_participation.transaction_id<>EXCLUDED.transaction_id;
END
$$;

CREATE OR REPLACE FUNCTION acp_cardinality_require(value bytea) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
 IF current_setting('transaction_isolation') <> 'read committed'
    OR NOT EXISTS (SELECT FROM acp_cardinality_participation
                   WHERE tenant=value AND transaction_id=pg_current_xact_id_if_assigned()) THEN
    RAISE EXCEPTION 'ACP_CARDINALITY_COORDINATION_REQUIRED' USING ERRCODE='55000';
 END IF;
END
$$;

DO $$
DECLARE target_schema text := current_schema();
BEGIN
 EXECUTE format('ALTER FUNCTION %I.acp_cardinality_enter(bytea) SET search_path TO pg_catalog, %I, pg_temp', target_schema, target_schema);
 EXECUTE format('ALTER FUNCTION %I.acp_cardinality_require(bytea) SET search_path TO pg_catalog, %I, pg_temp', target_schema, target_schema);
END
$$;
REVOKE ALL ON FUNCTION acp_cardinality_enter(bytea) FROM PUBLIC;

"""
