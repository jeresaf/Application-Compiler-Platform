"""Canonical 0.3 storage regression. Evolution authority here is TEST ONLY."""
import copy
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
from change_fixtures import evolution_change
from changes import prepare
from compiler_contracts import Document
from deterministic_approval import approved_snapshot
from target_migrations import MigrationBlocked, identifier, plan_upgrade
from test_target_migrations import FixtureAcceptedHistory


def fixture(optional=False,nullable=False,value="e\u0301\x00🦋'",typ=None):
    before=approved_snapshot('payment')
    proposal=evolution_change(before,{'sequence':0,'digest':before['contentDigest'],'journalDigest':'sha256:'+'0'*64},'required-field')
    proposal.update(changeVersion='0.3.0',canonicalVersion='0.3.0')
    field=proposal['operations'][0]['node']
    field['data']['optional']=optional
    field['data']['type']=typ or ({'kind':'Nullable','item':{'kind':'String'}} if nullable else {'kind':'String'})
    plan=Document.of(prepare(before,proposal))
    bindings=Document.of({'requiredFieldBackfills':{'EVOLUTION-required-field':value}})
    after=Document.of(plan.read()['candidate'])
    history=FixtureAcceptedHistory(plan,bindings)
    return Document.of(before),after,plan,bindings,history


class Canonical03MigrationTests(unittest.TestCase):
    def test_storage_matches_actual_target_lowering(self):
        # Execute the exact DDL lowering used by the target, no duplicate type map.
        worker=Path(__file__).resolve().parents[2]/'targets/spring-vue-postgres/worker'
        for optional,nullable in [(False,False),(True,False),(False,True),(True,True)]:
            args=fixture(optional,nullable);sql=plan_upgrade(*args).read()['sql']
            code="import sys,json;sys.path.insert(0,sys.argv[1]);from model import lower;from generation import schema;x=json.load(sys.stdin);print(schema(lower(x['content']['nodes'],json.load(open(sys.argv[2])),x['content']['schemaVersion'])))"
            import json
            ddl=subprocess.check_output([sys.executable,'-c',code,str(worker),str(worker.parent/'profile.json')],input=json.dumps(args[1].read()),text=True)
            column=identifier('EVOLUTION-required-field','f')
            self.assertIn(column+' bytea',ddl);self.assertIn(column+' bytea',sql)
            self.assertEqual(optional and nullable,'ADD CHECK' in sql)
            self.assertEqual(not optional and not nullable,'SET NOT NULL' in sql)
            if not optional and not nullable:self.assertIn('65cc8100f09fa68b27',sql)

    def test_authority_and_types_fail_closed(self):
        args=list(fixture());args[-1].revoked=True
        with self.assertRaisesRegex(MigrationBlocked,'UNACCEPTED_HISTORY'):plan_upgrade(*args)
        args=list(fixture());args[3]=Document.of({'requiredFieldBackfills':{'EVOLUTION-required-field':'edited'}})
        with self.assertRaisesRegex(MigrationBlocked,'UNAPPROVED_DATA_BINDINGS'):plan_upgrade(*args)
        with self.assertRaisesRegex(MigrationBlocked,'BACKFILL_TYPE'):plan_upgrade(*fixture(value=True))
        with self.assertRaisesRegex(MigrationBlocked,'FIELD_TYPE_UPGRADE_UNSUPPORTED'):plan_upgrade(*fixture(typ={'kind':'Integer'}))


def assert_encoded_rows(output, expected):
    """Parse complete tuples-only id|hex output, never headings or sliced rows."""
    import re
    rows = {}
    for line in output.splitlines():
        parts = line.split('|')
        if len(parts) != 2 or not re.fullmatch(r'[1-9][0-9]*', parts[0]):
            raise ValueError('INVALID_ROW')
        key = int(parts[0]); value = parts[1]
        if key in rows:
            raise ValueError('DUPLICATE_ROW')
        if value == '<NULL>':
            value = None
        elif not re.fullmatch(r'(?:[0-9a-f]{2})*', value):
            raise ValueError('INVALID_HEX')
        rows[key] = value
    if not expected or rows != expected:
        raise ValueError('ROW_POPULATION_OR_BYTES_MISMATCH')
    return rows


def owned_psql(sql, check=True):
    """Test-only fence: no URL/default connection or inherited libpq credentials.

    The launcher must have created the private root/cluster and recorded its PID.
    This is a local laboratory safety check, not authenticated runtime evidence.
    """
    import json
    root = Path(os.environ['ACP_WAVE2_ROOT']).resolve(strict=True)
    if not root.name.startswith('acp-phase6-wave2-'):
        raise ValueError('TASK_ROOT_REQUIRED')
    data = root / 'pgdata'; socket = root / 'pgsocket'
    for directory in (data, socket):
        if directory.is_symlink() or directory.resolve(strict=True).parent != root:
            raise ValueError('PRIVATE_DIRECTORY_REQUIRED')
        if directory.stat().st_mode & 0o077 or directory.stat().st_uid != os.getuid():
            raise ValueError('PRIVATE_DIRECTORY_REQUIRED')
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'engineering/ci'))
    from phase6_postgresql import test_client_context, verify_executable
    identity = test_client_context(root,os.environ)
    if (not isinstance(identity['pid'], int) or identity['pid'] <= 0
        or not isinstance(identity['port'], int) or not 1024 <= identity['port'] <= 65535
        or not all(isinstance(identity[k], str) and identity[k].startswith('acp_wave2_')
                   and identity[k].replace('_', '').isalnum() for k in ('database', 'role'))):
        raise ValueError('OWNED_IDENTITY_REQUIRED')
    pid = (data / 'postmaster.pid').read_text().splitlines()
    if len(pid) < 6 or pid[0] != str(identity['pid']) or pid[1] != str(data) or pid[3] != str(identity['port']) or pid[4] != str(socket) or pid[5] != '':
        raise ValueError('OWNED_POSTMASTER_REQUIRED')
    env = {k:v for k,v in os.environ.items() if k in {'PATH','LANG','LC_ALL','TZ'}}
    env.update(PGHOST=str(socket), PGPORT=str(identity['port']), PGDATABASE=identity['database'],
               PGUSER=identity['role'], PGPASSFILE='/dev/null', PGSERVICEFILE='/dev/null', PGCONNECT_TIMEOUT='5')
    command = [verify_executable(identity['executables']['psql']), '-X', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
               '-h', str(socket), '-p', str(identity['port']), '-U', identity['role'], '-d', identity['database']]
    probe = "SELECT json_build_array(current_setting('data_directory'),current_setting('listen_addresses'),current_setting('unix_socket_directories'),inet_server_addr() IS NULL,current_setting('server_version_num'),current_database(),current_user);"
    observed = subprocess.run(command, input=probe, text=True, capture_output=True, env=env, check=True, timeout=15)
    expected = [str(data), '', str(socket), True, '180006', identity['database'], identity['role']]
    if json.loads(observed.stdout.strip()) != expected:
        raise ValueError('OWNED_SERVER_MISMATCH')
    # Recheck after the identity probe; do not run DDL after an executable/context substitution.
    test_client_context(root,os.environ)
    verify_executable(identity['executables']['psql'])
    return subprocess.run(command, input=sql, text=True, capture_output=True, env=env, check=check, timeout=60)


@unittest.skipUnless(os.environ.get('ACP_WAVE2_ROOT'), 'requires newly owned Wave 2 PostgreSQL')
class PostgreSQL03MigrationTests(unittest.TestCase):
    def psql(self, sql, check=True):
        return owned_psql(sql, check)

    def storage_setup(self, snapshot, schema, incompatible=None):
        # Model the complete pre-existing String storage, not just the table
        # receiving the new field. Missing old columns must fail admission.
        nodes = {n['id']: n for n in snapshot['content']['nodes']}
        # Existing Entity tables remain real even if they have no old String fields.
        columns = {identifier(n['id'], 'e'): []
                   for n in nodes.values() if n['kind'] == 'Entity'}
        for node in nodes.values():
            if node['kind'] != 'Field':
                continue
            field = node['data']; typ = field['type']
            if nodes[field['owner']['id']]['kind'] != 'Entity':
                continue
            if typ['kind'] == 'Nullable':
                typ = typ['item']
            if typ['kind'] != 'String':
                continue
            table = identifier(field['owner']['id'], 'e')
            column = identifier(node['id'], 'f')
            storage = 'text' if incompatible == (table, column) else 'bytea'
            columns.setdefault(table, []).append(column + ' ' + storage)
        sql = f'CREATE SCHEMA {schema}; SET search_path={schema};'
        for table, fields in sorted(columns.items()):
            sql += f'CREATE TABLE {table}(id integer PRIMARY KEY' + (',' + ','.join(fields) if fields else '') + ');'
            sql += f'INSERT INTO {table}(id) VALUES(1);'
        return sql

    def test_real_postgresql_storage_presence_required_and_rollback(self):
        self.assertEqual('180006',self.psql('SHOW server_version_num;').stdout.strip())
        for optional,nullable in [(False,False),(True,False),(False,True),(True,True)]:
            args=fixture(optional,nullable);migration=plan_upgrade(*args).read()
            field=next(n for n in args[1].read()['content']['nodes'] if n['id']=='EVOLUTION-required-field')
            table=identifier(field['data']['owner']['id'],'e');column=identifier(field['id'],'f');presence=identifier(field['id'],'present')
            schema='acp_migration_'+uuid.uuid4().hex
            setup=self.storage_setup(args[0].read(),schema)
            try:
                self.psql(setup+'BEGIN;'+migration['sql']+'COMMIT;')
                prefix=f'SET search_path={schema};'
                if not optional and not nullable:
                    self.assertEqual('65cc8100f09fa68b27',self.psql(prefix+f"SELECT encode({column},'hex') FROM {table};").stdout.splitlines()[-1])
                    self.assertNotEqual(0,self.psql(prefix+f'INSERT INTO {table}(id) VALUES(2);',False).returncode)
                else:self.assertEqual('t',self.psql(prefix+f'SELECT {column} IS NULL FROM {table};').stdout.splitlines()[-1])
                if optional and nullable:
                    self.assertEqual('f',self.psql(prefix+f'SELECT {presence} FROM {table};').stdout.splitlines()[-1])
                    self.psql(prefix+f'UPDATE {table} SET {presence}=true;')
                    self.assertEqual('t',self.psql(prefix+f'SELECT {presence} AND {column} IS NULL FROM {table};').stdout.splitlines()[-1])
                    self.assertNotEqual(0,self.psql(prefix+f"UPDATE {table} SET {presence}=false,{column}=decode('00','hex');",False).returncode)
            finally:self.psql(f'DROP SCHEMA {schema} CASCADE;')
        args=fixture();before=args[0].read()
        prior=next(n for n in before['content']['nodes'] if n['kind']=='Field' and n['data']['type']['kind']=='String' and next(o for o in before['content']['nodes'] if o['id']==n['data']['owner']['id'])['kind']=='Entity')
        old_table=identifier(prior['data']['owner']['id'],'e');old_column=identifier(prior['id'],'f');schema='acp_migration_'+uuid.uuid4().hex
        try:
            self.psql(self.storage_setup(before,schema,incompatible=(old_table,old_column)))
            result=self.psql(f'SET search_path={schema};BEGIN;'+plan_upgrade(*args).read()['sql']+'COMMIT;',False)
            self.assertNotEqual(0,result.returncode);self.assertIn('ACP_INCOMPATIBLE_STORAGE_REPRESENTATION',result.stderr)
        finally:self.psql(f'DROP SCHEMA {schema} CASCADE;')
        args=fixture();sql=plan_upgrade(*args).read()['sql'];field=args[2].read()['change']['operations'][0]['node'];table=identifier(field['data']['owner']['id'],'e');column=identifier(field['id'],'f')
        schema='acp_migration_'+uuid.uuid4().hex
        try:
            self.psql(self.storage_setup(args[0].read(),schema))
            # Force a real database backfill failure, then verify transactional DDL rollback.
            broken=sql.replace("decode('65cc8100f09fa68b27','hex')","decode('zz','hex')")
            self.assertNotEqual(0,self.psql(f'SET search_path={schema};BEGIN;'+broken+'COMMIT;',False).returncode)
            self.assertEqual('0',self.psql(f"SELECT count(*) FROM information_schema.columns WHERE table_schema='{schema}' AND column_name='{column}';").stdout.strip())
        finally:self.psql(f'DROP SCHEMA {schema} CASCADE;')

    def test_missing_persisted_column_rejects_before_expand(self):
        args=fixture(); before=args[0].read(); nodes={n['id']:n for n in before['content']['nodes']}
        old=next(n for n in nodes.values() if n['kind']=='Field' and n['data']['type']['kind']=='String' and nodes[n['data']['owner']['id']]['kind']=='Entity')
        table=identifier(old['data']['owner']['id'],'e'); column=identifier(old['id'],'f')
        schema='acp_migration_'+uuid.uuid4().hex
        try:
            self.psql(self.storage_setup(before,schema)+f'ALTER TABLE {table} DROP COLUMN {column};')
            prefix=f'SET search_path={schema};'
            catalog=f"SELECT column_name,udt_name,is_nullable,column_default FROM information_schema.columns WHERE table_schema='{schema}' ORDER BY table_name,ordinal_position;"
            prior=self.psql(catalog).stdout
            result=self.psql(prefix+'BEGIN;'+plan_upgrade(*args).read()['sql']+'COMMIT;',False)
            self.assertNotEqual(0,result.returncode)
            self.assertIn('ACP_INCOMPATIBLE_STORAGE_REPRESENTATION',result.stderr)
            self.assertEqual(prior,self.psql(catalog).stdout)
        finally:self.psql(f'DROP SCHEMA {schema} CASCADE;')

    def test_wrong_text_storage_rejects_without_catalog_change(self):
        args=fixture(); before=args[0].read(); nodes={n['id']:n for n in before['content']['nodes']}
        old=next(n for n in nodes.values() if n['kind']=='Field' and n['data']['type']['kind']=='String' and nodes[n['data']['owner']['id']]['kind']=='Entity')
        table=identifier(old['data']['owner']['id'],'e'); column=identifier(old['id'],'f')
        schema='acp_migration_'+uuid.uuid4().hex
        try:
            self.psql(self.storage_setup(before,schema,incompatible=(table,column)))
            catalog=f"SELECT column_name,udt_name,is_nullable,column_default FROM information_schema.columns WHERE table_schema='{schema}' ORDER BY table_name,ordinal_position;"
            prior=self.psql(catalog).stdout
            result=self.psql(f'SET search_path={schema};BEGIN;'+plan_upgrade(*args).read()['sql']+'COMMIT;',False)
            self.assertNotEqual(0,result.returncode)
            self.assertIn('ACP_INCOMPATIBLE_STORAGE_REPRESENTATION',result.stderr)
            self.assertEqual(prior,self.psql(catalog).stdout)
        finally:self.psql(f'DROP SCHEMA {schema} CASCADE;')

    def test_cross_version_retained_bytes_and_rollback_both_domains(self):
        from test_core_wave1 import cross_version
        for domain in ('payment','case-management'):
            args=cross_version(domain=domain); sql=plan_upgrade(*args).read()['sql']
            nodes={n['id']:n for n in args[0].read()['content']['nodes']}
            fields=[n for n in nodes.values() if n['kind']=='Field' and n['data']['type']['kind']=='String' and nodes[n['data']['owner']['id']]['kind']=='Entity']
            schema='acp_migration_'+uuid.uuid4().hex
            try:
                self.psql(self.storage_setup(args[0].read(),schema))
                prefix=f'SET search_path={schema};'; probes=[]
                for field in fields:
                    table=identifier(field['data']['owner']['id'],'e'); column=identifier(field['id'],'f')
                    self.psql(prefix+f"UPDATE {table} SET {column}=decode('65cc8100f09fa68b27','hex');INSERT INTO {table}(id,{column}) VALUES(2,decode('','hex')),(3,decode('27','hex'));") if not any(p[0]==table for p in probes) else self.psql(prefix+f"UPDATE {table} SET {column}=CASE id WHEN 1 THEN decode('65cc8100f09fa68b27','hex') WHEN 2 THEN decode('','hex') ELSE decode('27','hex') END;")
                    probes.append((table,column))
                # If the upgrade targets an Entity with no old String column,
                # populate its existing table with the same three IDs as other tables.
                target_field=next(n for n in args[1].read()['content']['nodes']
                                  if n['id']=='EVOLUTION-required-field')
                target_table=identifier(target_field['data']['owner']['id'],'e')
                if not any(existing_table==target_table for existing_table,_ in probes):
                    self.psql(prefix+f'INSERT INTO {target_table}(id) VALUES(2),(3);')
                observation=''.join(f"SELECT id,encode({column},'hex') FROM {table} ORDER BY id;" for table,column in probes)
                prior=self.psql(prefix+observation).stdout
                broken=sql.replace("decode('65cc8100f09fa68b27','hex')","decode('zz','hex')")
                self.assertNotEqual(sql,broken)
                self.assertNotEqual(0,self.psql(prefix+'BEGIN;'+broken+'COMMIT;',False).returncode)
                self.assertEqual(prior,self.psql(prefix+observation).stdout)
                newcolumn=identifier('EVOLUTION-required-field','f')
                self.assertEqual('0',self.psql(f"SELECT count(*) FROM information_schema.columns WHERE table_schema='{schema}' AND column_name='{newcolumn}';").stdout.strip())
                self.psql(prefix+'BEGIN;'+sql+'COMMIT;')
                self.assertEqual(prior,self.psql(prefix+observation).stdout)
                self.assertEqual('bytea|NO|',self.psql(f"SELECT udt_name,is_nullable,column_default FROM information_schema.columns WHERE table_schema='{schema}' AND column_name='{newcolumn}';").stdout.strip())
                newfield=next(n for n in args[1].read()['content']['nodes'] if n['id']=='EVOLUTION-required-field')
                table=identifier(newfield['data']['owner']['id'],'e')
                # Keep SET's command tag out of the tuples-only observation.
                query=f"SELECT id,COALESCE(encode({newcolumn},'hex'),'<NULL>') FROM {schema}.{table} ORDER BY id;"
                assert_encoded_rows(self.psql(query).stdout,{1:'65cc8100f09fa68b27',2:'65cc8100f09fa68b27',3:'65cc8100f09fa68b27'})
                self.assertNotEqual(0,self.psql(prefix+f'INSERT INTO {table}(id) VALUES(4);',False).returncode)
            finally:self.psql(f'DROP SCHEMA {schema} CASCADE;')


if __name__=='__main__':unittest.main()
