"""Offline integration witnesses; all histories/bindings are synthetic, not approvals."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys
import hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'engineering/ci'))
import phase6_postgresql as pg
from unittest.mock import patch
from test_core_wave1 import cross_version, migration_artifact
from test_canonical03_migrations import owned_psql
from compiler_contracts import ArtifactPlan, Owner
from compiler_core import CompilerFault
from filesystem_artifacts import FilesystemArtifactStore, StoreConflict, byte_digest
from target_migrations import plan_upgrade, identifier
from target_provenance import inspect_mapping


class Wave2IntegrationTests(unittest.TestCase):
    def test_both_domains_exact_bytes_ownership_and_trace(self):
        for domain in ('payment', 'case-management'):
            for value in ('e\u0301\x00🦋\'', '', "'\\"):
                with self.subTest(domain=domain,value=value):
                    args=cross_version(value,domain=domain)
                    migration=plan_upgrade(*args).read()
                    self.assertEqual(('0.2.0','0.3.0'),tuple(a.read()['content']['schemaVersion'] for a in args[:2]))
                    self.assertIn("decode('"+value.encode().hex()+"','hex')",migration['sql'])
                    self.assertNotIn('DEFAULT',migration['sql'])
                    item=migration_artifact(args)
                    with tempfile.TemporaryDirectory() as temp:
                        root=Path(temp)/'app'; store=FilesystemArtifactStore(root)
                        manual=migration_artifact(args,text='human original\n',path='frontend/src/extensions/manual.txt')
                        store.apply(ArtifactPlan((item,manual),()))
                        store.adopt_human(manual.path)
                        (root/manual.path).write_text('human retained\n')
                        inventory={a.path:a for a in store.inventory()}
                        keep=migration_artifact(args,text='human retained\n',prior=inventory[manual.path],owner=Owner.HUMAN,path=manual.path)
                        current=migration_artifact(args,prior=inventory[item.path])
                        store.apply(ArtifactPlan((current,keep),()))
                        self.assertEqual('human retained\n',(root/manual.path).read_text())
                        self.assertEqual(item.content.read()['text'].encode(),(root/item.path).read_bytes())
                        mapping={'artifact':item.path,'artifactDigest':byte_digest((root/item.path).read_bytes()),'origins':[{'id':o.id,'revision':o.revision} for o in item.mappings], 'locations':[{'line':next(i for i,line in enumerate(item.content.read()['text'].splitlines(),1) if identifier('EVOLUTION-required-field','f')+' bytea;' in line)}], 'locationConfidence':'EXACT_TEST_FIXTURE'}
                        revisions={o.id:o.revision for o in item.mappings}
                        self.assertEqual('CURRENT',inspect_mapping(root,mapping,semantic_revisions=revisions)['status'])
                        print('WAVE2_TRACE '+json.dumps({'domain':domain,'fixtureAuthority':'SYNTHETIC_TEST_ONLY',
                            'beforeSnapshot':migration['previousSnapshot'],'afterSnapshot':migration['nextSnapshot'],
                            'planDigest':migration['phase3PlanDigest'],'bindingsDigest':migration['bindingsDigest'],
                            'sqlArtifactDigest':mapping['artifactDigest'],'origins':mapping['origins'],
                            'testIdentity':self.id(),'retainedRows':'DB_NOT_RUN','newValueHex':value.encode().hex()}),flush=True)
                        self.assertEqual('STALE_SEMANTICS',inspect_mapping(root,mapping,semantic_revisions={k:v+1 for k,v in revisions.items()})['status'])
                        ai=migration_artifact(args,owner=Owner.AI,path='backend/ai.sql')
                        with self.assertRaisesRegex(StoreConflict,'AI_APPROVAL_REQUIRED'):store.apply(ArtifactPlan((ai,),()))
                        forbidden=migration_artifact(args,text='overwrite',prior=inventory[manual.path],owner=Owner.HUMAN,path=manual.path)
                        with self.assertRaises(CompilerFault):store.apply(ArtifactPlan((forbidden,),()))
                        self.assertFalse((root/ai.path).exists())
                        (root/item.path).write_text('tampered\n')
                        self.assertEqual('STALE_ARTIFACT',inspect_mapping(root,mapping)['status'])


class OwnedConnectionTests(unittest.TestCase):
    def setUp(self):
        # The local interpreter has an unapproved observed owner. Model an
        # approved UID only for this interpreter fixture, never in production
        # policy or for PostgreSQL fixture files; no file is chowned.
        python=Path(sys.executable).resolve();original=Path.stat;uid=os.getuid()
        def fixture_stat(path,*args,**kwargs):
            observed=original(path,*args,**kwargs)
            if str(path)==str(python):
                values=list(observed);values[4]=uid
                return os.stat_result(values)
            return observed
        handle=patch.object(Path,'stat',fixture_stat);handle.start();self.addCleanup(handle.stop)

    def context(self,temp):
        root=Path(temp)/'acp-phase6-wave2-fixture';root.mkdir(mode=0o700)
        for name in ('pgdata','pgsocket'):(root/name).mkdir(mode=0o700)
        binaries={};hashes={}
        for name in ('psql','postgres'):
            path=root/name;path.write_text('NONEXECUTED_BINARY_FIXTURE');path.chmod(0o700)
            binaries[name]=str(path);hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        identity={'pid':12345,'port':55439,'database':'acp_wave2_test','role':'acp_wave2_role'}
        policy={'python':str(Path(sys.executable).resolve()),'pythonSHA256':hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),
            'binaries':binaries,'binaryHashes':hashes,'candidateDigest':'a'*64}
        context=pg.build_test_context(policy,identity,'123456','b'*64)
        handoff=pg.write_test_context(root,context)
        self.assertEqual({**handoff,'ACP_WAVE2_ROOT':str(root)},self.environment(root))
        (root/'pgdata/postmaster.pid').write_text(f"12345\n{root}/pgdata\n0\n55439\n{root}/pgsocket\n\n")
        expected=[str(root/'pgdata'),'',str(root/'pgsocket'),True,'180006',identity['database'],identity['role']]
        return root,expected

    def environment(self,root):
        path=root/'owned-postgresql.json';context=json.loads(path.read_text())
        return {'ACP_WAVE2_ROOT':str(root),'ACP_QUALIFICATION_CONTEXT_SHA256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'ACP_QUALIFICATION_PSQL':context['executables']['psql']['path'],
                'ACP_QUALIFICATION_PSQL_SHA256':context['executables']['psql']['sha256']}

    def test_no_default_or_legacy_url_connection(self):
        with patch.dict(os.environ,{'ACP_TEST_DATABASE_URL':'postgresql://unrelated'},clear=True),patch('subprocess.run') as run:
            with self.assertRaises(KeyError):owned_psql('CREATE SCHEMA forbidden;')
            run.assert_not_called()

    def test_explicit_private_connection_and_scrubbed_environment(self):
        with tempfile.TemporaryDirectory() as temp:
            root,expected=self.context(temp)
            with patch.dict(os.environ,{**self.environment(root),'PGPASSWORD':'unrelated','PGOPTIONS':'unsafe','ACP_TEST_DATABASE_URL':'unrelated'},clear=True),patch.object(pg,'process_identity',return_value='123456'),patch('subprocess.run',side_effect=[subprocess.CompletedProcess([],0,json.dumps(expected),''),subprocess.CompletedProcess([],0,'ok','')]) as run:
                self.assertEqual('ok',owned_psql('SELECT 1;').stdout)
                for call in run.call_args_list:
                    self.assertIn(str(root/'pgsocket'),call.args[0]);self.assertIn('acp_wave2_test',call.args[0])
                    self.assertNotIn('PGPASSWORD',call.kwargs['env']);self.assertNotIn('PGOPTIONS',call.kwargs['env'])
                    self.assertNotIn('ACP_TEST_DATABASE_URL',call.kwargs['env'])
                    self.assertIn('timeout',call.kwargs)
                    self.assertEqual(str(root/'psql'),call.args[0][0])

        with tempfile.TemporaryDirectory() as temp:
            root,expected=self.context(temp);environment=self.environment(root)
            original=(root/'owned-postgresql.json').read_bytes();binary=(root/'psql').read_bytes()
            alternate=root/'not-approved-psql';alternate.write_bytes(binary);alternate.chmod(0o700)
            for changed in ({'ACP_QUALIFICATION_PSQL':str(alternate)}, {'ACP_QUALIFICATION_PSQL_SHA256':'0'*64},
                            {'ACP_QUALIFICATION_CONTEXT_SHA256':'0'*64}, {'ACP_QUALIFICATION_PSQL':''}):
                with self.subTest(changed=changed),patch.dict(os.environ,{**environment,**changed},clear=True),patch.object(pg,'process_identity',return_value='123456'),patch('subprocess.run') as run:
                    with self.assertRaises(ValueError):owned_psql('CREATE SCHEMA forbidden;')
                    run.assert_not_called()
            for key in ('ACP_QUALIFICATION_PSQL','ACP_QUALIFICATION_PSQL_SHA256','ACP_QUALIFICATION_CONTEXT_SHA256'):
                missing=environment.copy();missing.pop(key)
                with self.subTest(missing=key),patch.dict(os.environ,missing,clear=True),patch('subprocess.run') as run:
                    with self.assertRaises(ValueError):owned_psql('SELECT 1;')
                    run.assert_not_called()
            (root/'psql').write_text('changed bytes')
            with patch.dict(os.environ,environment,clear=True),patch('subprocess.run') as run:
                with self.assertRaises(ValueError):owned_psql('SELECT 1;')
                run.assert_not_called()
            (root/'psql').write_bytes(binary)
            for mutation in ('mode','owner','symlink','python','token','record-permission'):
                context=json.loads(original)
                if mutation=='mode':(root/'psql').chmod(0o720)
                elif mutation=='owner':context['executables']['psql']['uid']+=1
                elif mutation=='symlink':
                    link=root/'psql-link';link.symlink_to(root/'psql');context['executables']['psql']['path']=str(link)
                elif mutation=='python':context['executables']['python']=context['executables']['psql'].copy()
                elif mutation=='token':context['postmasterStartToken']='654321'
                (root/'owned-postgresql.json').write_text(json.dumps(context));(root/'owned-postgresql.json').chmod(0o644 if mutation=='record-permission' else 0o600)
                with self.subTest(mutation=mutation),patch.dict(os.environ,self.environment(root),clear=True),patch.object(pg,'process_identity',return_value='123456'),patch('subprocess.run') as run:
                    with self.assertRaises(ValueError):owned_psql('CREATE SCHEMA forbidden;')
                    run.assert_not_called()
                (root/'psql').chmod(0o700);(root/'owned-postgresql.json').write_bytes(original);(root/'owned-postgresql.json').chmod(0o600)
            # A substitution after the server probe must still block DDL.
            def probe(*args,**kwargs):
                (root/'psql').write_text('replaced after probe')
                return subprocess.CompletedProcess([],0,json.dumps(expected),'')
            with patch.dict(os.environ,environment,clear=True),patch.object(pg,'process_identity',return_value='123456'),patch('subprocess.run',side_effect=probe) as run:
                with self.assertRaises(ValueError):owned_psql('CREATE SCHEMA forbidden;')
                self.assertEqual(1,run.call_count)

    def test_all_wrong_server_identities_reject_before_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root,expected=self.context(temp)
            for index,replacement in enumerate(('/elsewhere','localhost','/tmp',False,'170000','other','other')):
                observed=expected.copy();observed[index]=replacement
                with self.subTest(index=index),patch.dict(os.environ,self.environment(root),clear=True),patch.object(pg,'process_identity',return_value='123456'),patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,json.dumps(observed),'')) as run:
                    with self.assertRaisesRegex(ValueError,'OWNED_SERVER_MISMATCH'):owned_psql('CREATE SCHEMA forbidden;')
                    self.assertEqual(1,run.call_count)

    def test_changed_pid_and_public_socket_rejected_without_connection(self):
        with tempfile.TemporaryDirectory() as temp:
            root,_=self.context(temp)
            with patch.dict(os.environ,self.environment(root),clear=True),patch.object(pg,'process_identity',return_value='123456'),patch('subprocess.run') as run:
                pid=root/'pgdata/postmaster.pid';original=pid.read_text();pid.write_text(original.replace('12345','99999'))
                with self.assertRaisesRegex(ValueError,'OWNED_POSTMASTER_REQUIRED'):owned_psql('SELECT 1;')
                pid.write_text(original);(root/'pgsocket').chmod(0o755)
                with self.assertRaisesRegex(ValueError,'PRIVATE_DIRECTORY_REQUIRED'):owned_psql('SELECT 1;')
                run.assert_not_called()
