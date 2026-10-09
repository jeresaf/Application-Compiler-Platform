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


@unittest.skipUnless(os.environ.get('ACP_TEST_DATABASE_URL'),'requires explicit disposable PostgreSQL')
class PostgreSQL03MigrationTests(unittest.TestCase):
    def psql(self,sql,check=True):
        env=os.environ.copy();env['PGUSER']=env['ACP_TEST_DATABASE_USER'];env['PGPASSWORD']=env['ACP_TEST_DATABASE_PASSWORD']
        url=env['ACP_TEST_DATABASE_URL'].removeprefix('jdbc:')
        return subprocess.run(['psql','-X','-A','-t','-v','ON_ERROR_STOP=1',url],input=sql,text=True,capture_output=True,env=env,check=check)

    def test_real_postgresql_storage_presence_required_and_rollback(self):
        self.assertEqual('180006',self.psql('SHOW server_version_num;').stdout.strip())
        for optional,nullable in [(False,False),(True,False),(False,True),(True,True)]:
            args=fixture(optional,nullable);migration=plan_upgrade(*args).read()
            field=next(n for n in args[1].read()['content']['nodes'] if n['id']=='EVOLUTION-required-field')
            table=identifier(field['data']['owner']['id'],'e');column=identifier(field['id'],'f');presence=identifier(field['id'],'present')
            schema='acp_migration_'+uuid.uuid4().hex
            setup=f'CREATE SCHEMA {schema}; SET search_path={schema}; CREATE TABLE {table}(id integer PRIMARY KEY); INSERT INTO {table} VALUES(1);'
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
            self.psql(f'CREATE SCHEMA {schema};SET search_path={schema};CREATE TABLE {old_table}({old_column} text);')
            result=self.psql(f'SET search_path={schema};BEGIN;'+plan_upgrade(*args).read()['sql']+'COMMIT;',False)
            self.assertNotEqual(0,result.returncode);self.assertIn('ACP_INCOMPATIBLE_STORAGE_REPRESENTATION',result.stderr)
        finally:self.psql(f'DROP SCHEMA {schema} CASCADE;')
        args=fixture();sql=plan_upgrade(*args).read()['sql'];field=args[2].read()['change']['operations'][0]['node'];table=identifier(field['data']['owner']['id'],'e');column=identifier(field['id'],'f')
        schema='acp_migration_'+uuid.uuid4().hex
        try:
            self.psql(f'CREATE SCHEMA {schema};SET search_path={schema};CREATE TABLE {table}(id integer);INSERT INTO {table} VALUES(1);')
            # Force a real database backfill failure, then verify transactional DDL rollback.
            broken=sql.replace("decode('65cc8100f09fa68b27','hex')","decode('zz','hex')")
            self.assertNotEqual(0,self.psql(f'SET search_path={schema};BEGIN;'+broken+'COMMIT;',False).returncode)
            self.assertEqual('0',self.psql(f"SELECT count(*) FROM information_schema.columns WHERE table_schema='{schema}' AND column_name='{column}';").stdout.strip())
        finally:self.psql(f'DROP SCHEMA {schema} CASCADE;')


if __name__=='__main__':unittest.main()
