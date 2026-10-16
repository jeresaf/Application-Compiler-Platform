"""Offline runner/launcher contracts. Fake process results are never physical proof."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'engineering/ci'))
import phase6_qualification as q
import phase6_postgresql as pg


class QualificationContractTests(unittest.TestCase):
    def test_bound_candidate_rejects_wrong_base_patch_manifest_and_source(self):
        manifest=ROOT/'engineering/ci/phase6-qualification-manifest.json'
        value=json.loads(manifest.read_text());candidate=q.source_digest(ROOT)
        previous=Path(os.environ['ACP_QUALIFICATION_VERIFIED_PATCH'])
        args=dict(expected_manifest=q.sha(manifest),expected_candidate=candidate)
        q.validate_candidate(ROOT,previous,manifest,**args)
        with self.assertRaises(ValueError):q.validate_candidate(ROOT,previous,manifest,baseline='wrong',**args)
        with self.assertRaises(ValueError):q.validate_candidate(ROOT,previous,manifest,**{**args,'expected_candidate':'0'*64})
        with tempfile.TemporaryDirectory() as temp:
            wrong=Path(temp)/'wrong.patch';wrong.write_text('bad')
            with self.assertRaises(ValueError):q.validate_candidate(ROOT,wrong,manifest,**args)
            wrong.write_text(manifest.read_text()+' ')
            with self.assertRaises(ValueError):q.validate_candidate(ROOT,previous,wrong,**args)
        files=q.source_files(ROOT);files.pop(next(iter(files)))
        with patch.object(q,'source_files',return_value=files),self.assertRaises(ValueError):q.validate_candidate(ROOT,previous,manifest,**args)

    def test_offline_runner_scrubs_env_and_selects_no_database(self):
        seen=[]
        def process(argv,**kwargs):
            seen.append((argv,kwargs))
            out=json.dumps(['3.14.4','CPython']) if '-I' in argv else 'Ran 32 tests in 1.0s\n\nOK\n'
            return subprocess.CompletedProcess(argv,0,out,'')
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'PGHOST':'ambient','PGPASSWORD':'fake-secret','ACP_TEST_DATABASE_URL':'ambient','ACP_WAVE2_ROOT':'ambient','DATABASE_URL':'ambient','SPRING_DATASOURCE_PASSWORD':'fake','JDBC_URL':'ambient','UNRELATED_SECRET':'fake','PYTHONPATH':'ambient'}):
            report=q.run_offline(ROOT,sys.executable,Path(temp)/'scratch',process=process)
        self.assertEqual('NOT_QUALIFIED',report['overall']);self.assertEqual('PASS',report['run']['counts']['status'])
        self.assertEqual(2,len(seen))
        self.assertEqual(list(q.SELECTORS),seen[1][0][4:-1])
        self.assertNotIn('PostgreSQL03MigrationTests',' '.join(seen[1][0]))
        for argv,options in seen:
            self.assertFalse(any(k.startswith(('PG','ACP','SPRING','JDBC')) or 'SECRET' in k or 'DATABASE' in k for k in options['env']))
            self.assertNotIn('PYTHONPATH',options['env']);self.assertEqual('1',options['env']['PYTHONDONTWRITEBYTECODE'])
            self.assertIn('timeout',options)
            self.assertTrue(all('psql' not in a and 'pg_ctl' not in a for a in argv))
        self.assertTrue(all(v=='NOT_RUN' for v in report['physicalMethods'].values()))

    def test_not_run_never_qualified_and_skip_cannot_pass(self):
        self.assertEqual('FAIL',q.test_outcome(0,'Ran 32 tests in 1s\nOK (skipped=1)\n')['status'])
        self.assertEqual('FAIL',q.test_outcome(0,'Ran 31 tests in 1s\nOK\n')['status'])
        self.assertEqual('FAIL',q.test_outcome(1,'Ran 32 tests in 1s\nFAILED (errors=1)\n')['status'])
        matrix=q.qualification_matrix({'status':'PASS'},'PINNED')
        self.assertEqual('NOT_QUALIFIED',matrix['overall'])
        for key in ('PHYSICAL_POSTGRESQL','GENERATED_APP_INTEGRATION'):self.assertEqual('NOT_RUN',matrix['matrix'][key]['status'])
        self.assertEqual('UNPROVEN',matrix['matrix']['ACCEPTED_DEPLOYED_HISTORY']['status'])
        self.assertEqual('BLOCKED',matrix['matrix']['RELEASE']['status'])

    def test_wrong_runtime_fails_before_suite(self):
        self.assertEqual('PINNED',q.runtime_status('3.14.7'))
        self.assertEqual('LOCAL_VERSION_NOT_PINNED',q.runtime_status('3.14.4'))
        for version,implementation in (('3.13.9','CPython'),('3.14.7','PyPy'),('3.15.0','CPython')):
            with self.assertRaises(ValueError):q.runtime_status(version,implementation)
        with tempfile.TemporaryDirectory() as temp,patch.object(q.subprocess,'run') as process:
            process.return_value=subprocess.CompletedProcess([],0,'["3.13.9","CPython"]','')
            with self.assertRaises(ValueError):q.run_offline(ROOT,sys.executable,Path(temp)/'scratch',process=process)
            self.assertEqual(1,process.call_count)

    def test_physical_plan_no_process_and_new_authorization_required(self):
        with patch('subprocess.run') as process:
            result=pg.physical_plan('/task/acp-phase6-wave2-new')
            self.assertEqual('PLANNED_NOT_EXECUTED',result['status'])
            with self.assertRaises(PermissionError):pg.execute_future({})
            process.assert_not_called()
        self.assertTrue(result['noTCP']);self.assertTrue(result['noServices'])
        self.assertEqual(4,len(q.PHYSICAL_METHODS))

    def test_binary_policy_rejects_missing_changed_default_and_existing_root(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);binaries={};hashes={}
            for name in pg.NAMES:
                file=base/name;file.write_text('NONEXECUTED_BINARY_FIXTURE');file.chmod(0o700)
                binaries[name]=str(file);hashes[name]=q.sha(file)
            policy={'root':str(base/'acp-phase6-wave2-new'),'port':55439,'role':'acp_wave2_role','database':'acp_wave2_db','binaries':binaries,'binaryHashes':hashes,'source':str(ROOT),'candidateDigest':q.source_digest(ROOT),'python':sys.executable,'pythonSHA256':q.sha(Path(sys.executable).resolve())}
            pg.validate_policy(policy)
            for key,value in (('port',0),('role','postgres'),('database','postgres'),('root',str(base)),('host','localhost')):
                invalid={**policy,key:value}
                with self.subTest(key=key),self.assertRaises(ValueError):pg.validate_policy(invalid)
            invalid=copy.deepcopy(policy);invalid['binaries']['psql']=str(base/'missing')
            with self.assertRaises(ValueError):pg.validate_policy(invalid)
            invalid=copy.deepcopy(policy);invalid['binaryHashes']['psql']='0'*64
            with self.assertRaises(ValueError):pg.validate_policy(invalid)
            invalid=copy.deepcopy(policy);invalid['binaries']['psql']='psql'
            with self.assertRaises(ValueError):pg.validate_policy(invalid)
        # Exercise the real launcher ordering with nonexecuting fake binaries,
        # process results and PID evidence. Wrong server identity blocks DDL
        # and refuses uncertain cleanup, rather than stopping another daemon.
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);binaries={};hashes={}
            for name in pg.NAMES:
                path=base/name;path.write_text('NONEXECUTED_FIXTURE');path.chmod(0o700)
                binaries[name]=str(path);hashes[name]=q.sha(path)
            root=base/'acp-phase6-wave2-future'
            policy={'root':str(root),'port':55439,'role':'acp_wave2_role','database':'acp_wave2_db','binaries':binaries,'binaryHashes':hashes,'source':str(ROOT),'candidateDigest':q.source_digest(ROOT),'python':sys.executable,'pythonSHA256':q.sha(Path(sys.executable).resolve())}
            calls=[]
            def process(argv,**options):
                calls.append((argv,options.get('input')))
                if '-I' in argv:out='CPython 3.14.7'
                elif '--version' in argv:out=Path(argv[0]).name+' (PostgreSQL) 18.6'
                elif Path(argv[0]).name=='initdb':
                    data=root/'pgdata';data.mkdir(mode=0o700)
                    (data/'postmaster.pid').write_text(f"42\n{data}\n0\n55439\n{root}/pgsocket\n\n")
                    out=''
                elif Path(argv[0]).name=='psql':out=json.dumps(['/wrong-data','',str(root/'pgsocket'),True,'180006','postgres','acp_wave2_role'])
                else:out=''
                return subprocess.CompletedProcess(argv,0,out,'')
            self.assertTrue(pg.socket_path_fits('/tmp/acp-phase6-wave2-q-a',55439))
            self.assertFalse(pg.socket_path_fits('/tmp/acp-phase6-wave2-'+('x'*150),55439))
            with patch.object(pg,'socket_path_fits',return_value=False):
                with self.assertRaisesRegex(ValueError,'PRIVATE_SOCKET_PATH_TOO_LONG'):
                    pg.execute_future(policy,authorize=lambda scope,digest:scope==pg.SCOPE,process=process)
            self.assertEqual([],calls)
            # These are fake filesystem/process fixtures, not a real socket.
            with patch.object(pg,'socket_path_fits',return_value=True),patch.object(pg,'process_identity',return_value='MOCK_START_TOKEN'):
                with self.assertRaisesRegex(RuntimeError,'BLOCKED_UNSAFE_TEARDOWN'):
                    pg.execute_future(policy,authorize=lambda scope,digest:scope==pg.SCOPE and len(digest)==64,process=process)
            start=next(argv for argv,_ in calls if Path(argv[0]).name=='pg_ctl' and 'start' in argv)
            self.assertEqual(policy['binaries']['postgres'],start[start.index('-p')+1])
            self.assertFalse(any(sql and 'CREATE DATABASE' in sql for _,sql in calls))
            self.assertFalse(any('stop' in argv or 'unittest' in argv for argv,_ in calls))
            self.assertEqual('BLOCKED_UNSAFE_TEARDOWN',json.loads((root/'pglogs/launcher-result.json').read_text())['physical'])
        pg.validate_version('psql (PostgreSQL) 18.6 (Ubuntu build)')
        for version in ('postgres (PostgreSQL) 18.5','postgres (PostgreSQL) 18.60','18.6'):
            with self.assertRaises(ValueError):pg.validate_version(version)

    def test_cluster_identity_rejects_wrong_data_socket_pid_db_version_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'acp-phase6-wave2-owned';root.mkdir(mode=0o700)
            for name in ('pgdata','pgsocket'):(root/name).mkdir(mode=0o700)
            identity={'pid':42,'port':55439,'database':'acp_wave2_db','role':'acp_wave2_role'}
            lines=['42',str(root/'pgdata'),'0','55439',str(root/'pgsocket'),'']
            observed=[str(root/'pgdata'),'',str(root/'pgsocket'),True,'180006','acp_wave2_db','acp_wave2_role']
            pg.verify_server(root,identity,observed,pid_lines=lines)
            for index,value in enumerate(('/other','localhost','/tmp',False,'180005','postgres','postgres')):
                wrong=observed.copy();wrong[index]=value
                with self.subTest(index=index),self.assertRaises(ValueError):pg.verify_server(root,identity,wrong,pid_lines=lines)
            with self.assertRaises(ValueError):pg.verify_server(root,identity,observed,pid_lines=['43',*lines[1:]])
            (root/'pgsocket').chmod(0o755)
            with self.assertRaises(ValueError):pg.verify_server(root,identity,observed,pid_lines=lines)

    def test_physical_capture_only_offline_interface_and_exact_method_inventory(self):
        from test_phase6_physical_capture import PhysicalCapturedTests
        from test_canonical03_migrations import PostgreSQL03MigrationTests
        methods={name for name in dir(PhysicalCapturedTests) if name.startswith('test_')}
        self.assertEqual(set(q.PHYSICAL_METHODS),methods)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'acp-phase6-wave2-capture';root.mkdir();(root/'pglogs').mkdir();log=root/'pglogs/observations.jsonl'
            with patch.dict(os.environ,{'ACP_WAVE2_ROOT':str(root),'ACP_PHYSICAL_EVIDENCE_LOG':str(log)}),patch.object(PostgreSQL03MigrationTests,'psql',return_value=subprocess.CompletedProcess([],0,'1|00\n','')):
                PhysicalCapturedTests().psql('SELECT synthetic_fixture;')
            entry=json.loads(log.read_text());self.assertEqual(hashlib.sha256(b'1|00\n').hexdigest(),entry['stdoutSHA256'])
            self.assertIn('NOT_AUTHENTICATED',entry['proofLevel'])
