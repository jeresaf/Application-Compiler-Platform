"""Actual JVM/Flyway/PostgreSQL recovery, exclusively in newly owned databases."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.generator_builds.runtime import database, IMAGE
from engineering.generator_builds.qualify import run
from engineering.traceability.qualification import inputs, sha, require
from engineering.recovery.fixtures import MIGRATOR,FILTER,RUNTIME_PROBE,server
from filesystem_artifacts import FilesystemArtifactStore
from phase6_reference_tests import seed_sql,symbol
from target_worker import bundle_digest

BEFORE=62425001
AFTER=62425002
INTERRUPT=62425003

EXPECTED=frozenset(('restartPreservesAllCommittedRuntimeFamilies','crashBeforeCommit','crashAfterCommitBeforeResponse','securityAndRateAfterRecovery','revokedSessionRejected','initialApplicationMigrations','repeatedMigrationInvocation','failedSchemaMigrationRollbackAndRecovery','migrationChecksumMismatch','incorrectMigrationOrdering','interruptedMigrationProcessTermination','nonTransactionalMigrationRequiresCompensation','applicationStartsAfterMigrationRecovery','unavailableDatabaseFailsClosed','incompatibleRequiredSchemaFailsStartup'))

def verify_observations(rows, events):
    require(len(rows)==len(EXPECTED) and {r['test'] for r in rows}==EXPECTED,'RECOVERY_TEST_INVENTORY')
    require(all(r['status']=='PASS' for r in rows),'RECOVERY_TEST_FAILURE')
    by={r['test']:r for r in rows}
    for name in ('failedSchemaMigrationRollbackAndRecovery','migrationChecksumMismatch','incorrectMigrationOrdering','nonTransactionalMigrationRequiresCompensation','unavailableDatabaseFailsClosed','incompatibleRequiredSchemaFailsStartup'):
        require(by[name]['failure']['exit']!=0,'FAULT_WAS_NOT_EXECUTED')
    require(by['interruptedMigrationProcessTermination']['exit']==-signal.SIGKILL,'MIGRATION_NOT_KILLED')
    require(by['crashBeforeCommit']['postgresTransactionStatus']=='aborted' and by['crashBeforeCommit']['databaseOutcome']=='ROLLED_BACK','MISSING_ROLLBACK_PROOF')
    after=by['crashAfterCommitBeforeResponse']
    require(after['databaseOutcome']=='COMMITTED' and after['logicalWorkflows']==4 and after['counts']['acp_outbox']==events*4,'MISSING_COMMITTED_EFFECT_PROOF')
    first=by['restartPreservesAllCommittedRuntimeFamilies']
    require(first['oldPid']!=first['newProcess']['pid'],'NO_FRESH_JVM')
    security=by['securityAndRateAfterRecovery']
    require(security['concurrentStatuses']==[200]*4 and set(security['overloadStatuses'])<= {200,429} and 429 in security['overloadStatuses'],'RECOVERY_SECURITY_REGRESSION')
    require(by['revokedSessionRejected']['httpStatus']==403,'REVOCATION_NOT_ENFORCED')


def wait_until(predicate, label, timeout=30):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if predicate():return
        time.sleep(.05)  # bounded observation polling, never a success retry
    raise TimeoutError(label)


def authenticated_database_ready(container, password):
    require(container.startswith('acp-06-runtime-'),'NOT_OWNED_DISPOSABLE_DATABASE')
    attempts=[]
    def ready():
        result=subprocess.run(['docker','exec','--env','PGPASSWORD='+password,container,'psql','-h','127.0.0.1','-p','5432','-U','acp_runtime','-d','acp_runtime','-v','ON_ERROR_STOP=1','-Atqc','SELECT 1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=5)
        attempts.append({'exit':result.returncode,'stdout':result.stdout.strip(),'stderr':result.stderr.strip()})
        return result.returncode==0 and result.stdout.strip()=='1'
    # initdb's temporary server accepts Unix sockets only. A real authenticated
    # TCP query establishes readiness of the final server and requested database.
    wait_until(ready,'POSTGRES_FINAL_TCP_READINESS',60)
    return {'mechanism':'AUTHENTICATED_TCP_SELECT','attempts':attempts}


def stop(process, *, crash=False):
    if process.poll() is None:
        os.killpg(process.pid,signal.SIGKILL if crash else signal.SIGTERM)
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=10)
    require(process.poll() is not None,'PROCESS_NOT_REAPED')
    return process.returncode


class Lab:
    def __init__(self,container,schema,backend,migrations,logs,domain):
        require(container.startswith('acp-06-runtime-'),'NOT_OWNED_DISPOSABLE_DATABASE')
        self.container,self.schema,self.backend,self.migrations,self.logs,self.domain=container,schema,backend,migrations,logs,domain
        self.cp='target/test-classes:target/classes:'+(backend/'target/recovery-classpath').read_text().strip()
        self.env=os.environ.copy();url=self.env['ACP_TEST_DATABASE_URL']
        self.env.update(ACP_DATABASE_URL=url+'?currentSchema='+schema+'&ApplicationName=acp-recovery',ACP_DATABASE_USER=self.env['ACP_TEST_DATABASE_USER'],ACP_DATABASE_PASSWORD=self.env['ACP_TEST_DATABASE_PASSWORD'],ACP_OIDC_ISSUER='https://test.invalid',ACP_OIDC_AUDIENCE='test',ACP_RECOVERY_AUTH_EVENT=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
        self.process=None;self.processes=[];self.observations=[];self.sequence=0
        self.identity=self.data("SELECT jsonb_build_object('name',current_database(),'oid',(SELECT oid FROM pg_database WHERE datname=current_database()),'systemIdentifier',(SELECT system_identifier::text FROM pg_control_system()))")

    def sql(self,query):
        return subprocess.check_output(['docker','exec',self.container,'psql','-U','acp_runtime','-d','acp_runtime','-v','ON_ERROR_STOP=1','-Atq','-c','SET search_path TO '+self.schema+';'+query],text=True,timeout=20).strip()

    def data(self,query):return json.loads(self.sql(query))
    def history(self):return self.data("SELECT coalesce(jsonb_agg(jsonb_build_object('version',version,'checksum',checksum,'success',success,'script',script) ORDER BY installed_rank),'[]') FROM flyway_schema_history WHERE type='SQL'")
    def schema_state(self):
        schema=self.schema
        return self.data("SELECT jsonb_build_object('columns', (SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY table_name,ordinal_position),'[]') FROM information_schema.columns c WHERE table_schema='"+schema+"'), 'constraints', (SELECT coalesce(jsonb_agg(jsonb_build_object('table',r.relname,'name',c.conname,'definition',pg_get_constraintdef(c.oid),'validated',c.convalidated) ORDER BY r.relname,c.conname),'[]') FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname='"+schema+"'), 'indexes', (SELECT coalesce(jsonb_agg(to_jsonb(i) ORDER BY tablename,indexname),'[]') FROM pg_indexes i WHERE schemaname='"+schema+"'))")
    def state(self):
        tables=self.data("SELECT coalesce(jsonb_agg(tablename ORDER BY tablename),'[]') FROM pg_tables WHERE schemaname='"+self.schema+"' AND (left(tablename,2) IN ('e_','r_') OR left(tablename,4)='acp_' OR tablename='recovery_transport') AND tablename NOT IN ('acp_rate','acp_sessions')")
        return {table:self.data('SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\') FROM "'+table+'" t') for table in tables}
    def admission(self):
        return {table:self.data('SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\') FROM '+table+' t') for table in ('acp_sessions','acp_rate')}
    def record(self,name,**facts):
        self.observations.append({'test':name,'status':'PASS','at':datetime.now(timezone.utc).isoformat(),**facts})
        (self.logs/'observations.json').write_text(json.dumps({'database':self.container,'schema':self.schema,'observations':self.observations},sort_keys=True,indent=2)+'\n')

    def capture_inputs(self,label):
        destination=self.logs/('inputs-'+label);destination.mkdir(exist_ok=False)
        values={}
        for path in sorted(self.migrations.iterdir()):
            require(path.is_file() and not path.is_symlink(),'MIGRATION_INPUT_TYPE')
            data=path.read_bytes();(destination/path.name).write_bytes(data);values[path.name]=sha(data)
        (destination/'manifest.json').write_text(json.dumps(values,sort_keys=True,indent=2)+'\n')
        return values

    def migration(self,operation, *, ok=True):
        self.sequence+=1;path=self.logs/f'migration-{self.sequence}-{operation}.log';inputs=self.capture_inputs('migration-'+str(self.sequence))
        with path.open('wb') as out:
            p=subprocess.run(['java','-cp',self.cp,'acp.recovery.MigrationProbe',operation,str(self.migrations),self.schema],cwd=self.backend,env=self.env,stdout=out,stderr=subprocess.STDOUT,timeout=90)
        require(inputs=={p.name:sha(p.read_bytes()) for p in self.migrations.iterdir()},'MIGRATION_INPUT_CHANGED')
        require((p.returncode==0)==ok,'UNEXPECTED_MIGRATION_RESULT:'+str(path))
        return {'exit':p.returncode,'log':path.name,'sha256':sha(path.read_bytes())}

    def application_argv(self,env=None):
        values=self.env if env is None else env
        database=['--spring.datasource.url='+values['ACP_DATABASE_URL'],'--spring.datasource.username='+values['ACP_DATABASE_USER'],'--spring.datasource.password='+values['ACP_DATABASE_PASSWORD'],'--spring.flyway.url='+values['ACP_DATABASE_URL'],'--spring.flyway.user='+values['ACP_DATABASE_USER'],'--spring.flyway.password='+values['ACP_DATABASE_PASSWORD']]
        return ['java','-cp',self.cp,'acp.browser.BrowserServer',*database,'--server.address=127.0.0.1','--server.port='+str(self.port),'--spring.flyway.schemas='+self.schema,'--spring.flyway.default-schema='+self.schema,'--spring.flyway.locations=filesystem:'+str(self.migrations),'--spring.flyway.clean-disabled=true','--acp.runtime.mode=development','--acp.runtime.poll-enabled=false','--acp.jobs.JOB-TASK.revision-3.credential-handle=browser-test-only']

    def failed_startup(self,label,env=None):
        self.sequence+=1;path=self.logs/f'application-{self.sequence}-{label}.log';self.capture_inputs('rejected-start-'+str(self.sequence))
        with path.open('wb') as out:
            process=subprocess.Popen(self.application_argv(env)+['--spring.flyway.connect-retries=0','--spring.datasource.hikari.connection-timeout=1000'],cwd=self.backend,env=self.env if env is None else env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
            self.processes.append(process)
            try:code=process.wait(timeout=45)
            finally:stop(process,crash=True)
        require(code!=0,'INVALID_DEPLOYMENT_STARTED')
        return {'exit':code,'log':path.name,'sha256':sha(path.read_bytes())}

    def launch(self):
        self.sequence+=1;path=self.logs/f'application-{self.sequence}.log';self.capture_inputs('application-'+str(self.sequence))
        with path.open('wb') as out:
            p=subprocess.Popen(self.application_argv(),cwd=self.backend,env=self.env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
        self.process=p;self.processes.append(p)
        def ready():
            require(p.poll() is None,'APPLICATION_START_FAILED:'+path.name)
            try:
                with urllib.request.urlopen('http://127.0.0.1:'+str(self.port)+'/actuator/health',timeout=1) as r:return r.status==200 and json.load(r)['status']=='UP'
            except (urllib.error.URLError,TimeoutError,ConnectionError):return False
        wait_until(ready,'APPLICATION_READINESS',90)
        return {'pid':p.pid,'log':path.name,'ready':True}

    def http(self,path,payload=None,token='browser-authorized',after=False):
        headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
        if after:headers['X-ACP-Test-After-Commit']='hold'
        request=urllib.request.Request('http://127.0.0.1:'+str(self.port)+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=40) as response:return response.status,json.loads(response.read() or b'null')
        except urllib.error.HTTPError as error:return error.code,json.loads(error.read() or b'null')

    @contextmanager
    def gate(self,key):
        p=subprocess.Popen(['docker','exec','-i',self.container,'psql','-U','acp_runtime','-d','acp_runtime','-Atq','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:
            p.stdin.write('SELECT pg_advisory_lock('+str(key)+');\n\\echo ACP_GATE_HELD\n');p.stdin.flush()
            # Observe the real database lock, independent of stdio buffering.
            wait_until(lambda:self.sql('SELECT count(*) FROM pg_locks WHERE locktype=\'advisory\' AND objid='+str(key)+' AND granted')=='1','GATE_NOT_HELD')
            yield
        finally:
            if p.poll() is None:
                try:p.stdin.write('SELECT pg_advisory_unlock('+str(key)+');\n\\q\n');p.stdin.flush();p.wait(timeout=10)
                except (BrokenPipeError,subprocess.TimeoutExpired):stop(p,crash=True)
            wait_until(lambda:self.sql('SELECT count(*) FROM pg_locks WHERE locktype=\'advisory\' AND objid='+str(key))=='0','GATE_LEAK')

    def blocked(self,key):
        wait_until(lambda:int(self.sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND objid="+str(key)+' AND NOT granted'))==1,'WORKER_NEVER_REACHED_DATABASE_BARRIER')

    def close(self):
        for p in reversed(self.processes):stop(p)


def migration_matrix(lab):
    original=lab.state();history=lab.history()
    require([r['version'] for r in history]==['1','2','3'],'BASELINE_MIGRATION_VERSIONS')
    lab.record('initialApplicationMigrations',history=history,schema=lab.schema_state(),state=original)
    before_schema=lab.schema_state();lab.migration('migrate');require(lab.history()==history and lab.state()==original and lab.schema_state()==before_schema,'REPEATED_MIGRATION_MUTATION')
    lab.record('repeatedMigrationInvocation',history=history)
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1',0));env=dict(lab.env)
        env['ACP_DATABASE_URL']='jdbc:postgresql://127.0.0.1:'+str(reserved.getsockname()[1])+'/acp_runtime?connectTimeout=2&socketTimeout=5'
        failed=lab.failed_startup('unavailable-database',env)
    require(lab.state()==original and lab.history()==history,'UNAVAILABLE_DATABASE_MUTATION')
    lab.record('unavailableDatabaseFailsClosed',failure=failed,recovery='restore only original disposable database URL; restart after complete matrix')

    p=lab.migrations/'V4__recovery_probe.sql'
    good='CREATE TABLE recovery_probe(value text PRIMARY KEY); INSERT INTO recovery_probe VALUES(\'retained\');\n'
    p.write_text(good+'SELECT 1/0;\n');failed=lab.migration('migrate',ok=False)
    require(lab.sql("SELECT to_regclass('recovery_probe') IS NULL")=='t','TRANSACTIONAL_DDL_LEAK')
    require(lab.state()==original and lab.history()==history and lab.schema_state()==before_schema,'FAILED_MIGRATION_CORRUPTION')
    p.write_text(good);lab.migration('migrate');lab.migration('validate')
    lab.record('failedSchemaMigrationRollbackAndRecovery',failure=failed,rollback='DDL_AND_DATA_ROLLED_BACK',recoveredHistory=lab.history())
    stable=lab.history();p.write_text(good+'-- checksum fault in synthetic V4 only\n');failed=lab.migration('validate',ok=False)
    require(lab.history()==stable and lab.state()==original,'CHECKSUM_FAILURE_MUTATION')
    p.write_text(good);lab.migration('validate');lab.record('migrationChecksumMismatch',failure=failed,recovery='restore exact synthetic V4; validate; no repair')
    (lab.migrations/'V6__later_probe.sql').write_text('CREATE TABLE recovery_later(value integer);\n');lab.migration('migrate');ordered=lab.history()
    wrong=lab.migrations/'V5__late_arrival.sql';wrong.write_text('CREATE TABLE recovery_out_of_order(value integer);\n');failed=lab.migration('migrate',ok=False)
    require(lab.history()==ordered and lab.sql("SELECT to_regclass('recovery_out_of_order') IS NULL")=='t','OUT_OF_ORDER_APPLIED')
    wrong.unlink();lab.migration('validate');lab.record('incorrectMigrationOrdering',failure=failed,recovery='withdraw unexecuted synthetic V5; no outOfOrder override')
    p=lab.migrations/'V7__interrupted_probe.sql';p.write_text('CREATE TABLE recovery_interrupted(value integer); INSERT INTO recovery_interrupted VALUES(1); SELECT pg_advisory_xact_lock('+str(INTERRUPT)+');\n')
    before=lab.history();path=lab.logs/'interrupted-migration.log';lab.capture_inputs('interrupted-migration')
    with lab.gate(INTERRUPT),path.open('wb') as out:
        process=subprocess.Popen(['java','-cp',lab.cp,'acp.recovery.MigrationProbe','migrate',str(lab.migrations),lab.schema],cwd=lab.backend,env=lab.env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
        try:lab.blocked(INTERRUPT);code=stop(process,crash=True)
        finally:stop(process,crash=True)
    wait_until(lambda:lab.sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND objid="+str(INTERRUPT)+' AND NOT granted')=='0','MIGRATION_BACKEND_LEAK')
    require(code==-signal.SIGKILL and lab.history()==before and lab.sql("SELECT to_regclass('recovery_interrupted') IS NULL")=='t','INTERRUPTED_MIGRATION_NOT_ROLLED_BACK')
    require(lab.state()==original,'INTERRUPTED_MIGRATION_DATA_LOSS');lab.migration('migrate');lab.migration('validate')
    lab.record('interruptedMigrationProcessTermination',exit=code,rollback='TRANSACTION_ABORTED',history=lab.history())
    # PostgreSQL/Flyway keeps partial nontransactional DDL, but rolls back
    # its metadata transaction. Absence of a failed history row is NOT rollback.
    p=lab.migrations/'V8__non_atomic_probe.sql';conf=lab.migrations/'V8__non_atomic_probe.sql.conf';conf.write_text('executeInTransaction=false\n')
    good='CREATE TABLE recovery_nonatomic(value integer); INSERT INTO recovery_nonatomic VALUES(1);\n';p.write_text(good+'SELECT 1/0;\n')
    previous=lab.history();failed=lab.migration('migrate',ok=False)
    require(lab.sql('SELECT count(*) FROM recovery_nonatomic')=='1','NONATOMIC_PARTIAL_WORK_NOT_OBSERVED')
    failed_history=lab.history();require(failed_history==previous,'UNEXPECTED_NONATOMIC_HISTORY')
    require(lab.state()==original,'NONATOMIC_BUSINESS_CORRUPTION')
    lab.sql('DROP TABLE recovery_nonatomic');p.write_text(good)
    require(lab.history()==previous,'RECOVERY_CHANGED_SUCCESSFUL_HISTORY')
    lab.migration('migrate');lab.migration('validate');require(lab.state()==original and lab.history()[:-1]==previous,'RECOVERY_LOST_COMMITTED_DATA')
    lab.record('nonTransactionalMigrationRequiresCompensation',failure=failed,atomicRollback=False,partialRows=1,failureMetadata='NO_FAILED_HISTORY_ROW',failedHistory=failed_history,recovery=['drop only recovery_nonatomic','restore exact successful V8 input','assert successful history unchanged; no repair','migrate with native validation enabled','validate'],history=lab.history())
    stable=lab.history();schema_before=lab.schema_state();p=lab.migrations/'V9__incompatible_required.sql'
    table=symbol('ENT-PAYMENT' if lab.domain=='payment' else 'CASE','e')
    p.write_text('ALTER TABLE '+table+' ADD COLUMN recovery_required text NOT NULL;\n')
    failed=lab.failed_startup('incompatible-required-schema')
    require(lab.history()==stable and lab.schema_state()==schema_before and lab.state()==original,'INCOMPATIBLE_SCHEMA_CORRUPTION')
    p.unlink();lab.migration('validate')
    lab.record('incompatibleRequiredSchemaFailsStartup',failure=failed,recovery='withdraw unexecuted synthetic V9; validate unchanged successful migrations; restart compatible candidate')



def request_input(resource,key,ui):return {'expectedVersion':0,'idempotencyKey':key,'input':{ui['resourceInputField']:resource,ui['textInputField']:'recovery note 🦋'}}


def runtime_matrix(lab,ui,domain):
    events=1 if domain=='payment' else 3
    root='ENT-PAYMENT' if domain=='payment' else 'CASE';table=symbol(root,'e');idfield=symbol('FLD-PAYMENT-ID' if domain=='payment' else 'CASE-ID','f')
    payload=request_input('original-committed','committed-before-restart',ui)
    code,result=lab.http(ui['actionPath'],payload);require(code==200,'INITIAL_ACTION_FAILED:'+str((code,result)))
    require(lab.http(ui['actionPath'],payload)==(200,result),'INITIAL_REPLAY_FAILED')
    code,observation=lab.http('/__test/recovery-observe',{});require(code==200 and observation['jobCompleted']==1,'JOB_OR_DELIVERY_PROVISION_FAILED:'+str((code,observation)))
    require(lab.sql("SELECT count(*) FROM acp_job_invocation_attempt WHERE outcome='COMMITTED'")=='1','MISSING_COMMITTED_JOB_ATTEMPT')
    require(int(lab.sql('SELECT count(*) FROM acp_lifecycle_anchor'))>=2 and int(lab.sql('SELECT count(*) FROM acp_delivery_attempt'))==events*2,'EMPTY_RUNTIME_FAMILY')
    before=lab.state();admission=lab.admission();pid=lab.process.pid;stop(lab.process);fresh=lab.launch();require(fresh['pid']!=pid and lab.state()==before and lab.admission()==admission,'RESTART_CHANGED_COMMITTED_STATE')
    require(lab.http(ui['actionPath'],payload)==(200,result),'POST_RESTART_REPLAY_FAILED')
    require(lab.state()==before,'REPLAY_DUPLICATED_EFFECTS')
    lab.record('restartPreservesAllCommittedRuntimeFamilies',oldPid=pid,newProcess=fresh,state=before,admissionState=admission)
    def counts():return {t:int(lab.sql('SELECT count(*) FROM '+t)) for t in ('acp_outbox','acp_audit','acp_classification_audit','acp_idempotency','acp_lifecycle_anchor','acp_lifecycle_release_audit')}
    trigger='CREATE FUNCTION recovery_hold() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_advisory_xact_lock('+str(BEFORE)+'); RETURN NEW; END $$; CREATE TRIGGER recovery_hold AFTER UPDATE ON '+table+" FOR EACH ROW WHEN (NEW."+idfield+"=convert_to('crash-before','UTF8')) EXECUTE FUNCTION recovery_hold();"
    lab.sql(trigger);baseline=lab.state();base_counts=counts()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with lab.gate(BEFORE):
            pending=pool.submit(lab.http,ui['actionPath'],request_input('crash-before','before-commit',ui));lab.blocked(BEFORE)
            require(not pending.done(),'PRECOMMIT_REQUEST_NOT_BLOCKED');crashed_pid=lab.process.pid;crashed_exit=stop(lab.process,crash=True);require(crashed_exit==-signal.SIGKILL,'APPLICATION_NOT_KILLED')
            try:pending.result(timeout=10);raise AssertionError('KILLED_REQUEST_RETURNED')
            except (urllib.error.URLError,ConnectionError,TimeoutError):pass
        wait_until(lambda:lab.sql("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND objid="+str(BEFORE)+' AND NOT granted')=='0','APPLICATION_DATABASE_TRANSACTION_LEAK')
    # Native reservation survives, but actual aborted xid proves no business commit.
    fact=lab.sql("SELECT pg_xact_status(attempt_xid::xid8) FROM acp_idempotency WHERE status='IN_FLIGHT'")
    require(fact=='aborted','MISSING_POSTGRES_ROLLBACK_PROOF')
    after=lab.state();require({k:v for k,v in after.items() if k!='acp_idempotency'}=={k:v for k,v in baseline.items() if k!='acp_idempotency'},'PRECOMMIT_BUSINESS_EFFECT_LEAK')
    lab.sql('DROP TRIGGER recovery_hold ON '+table+'; DROP FUNCTION recovery_hold()');lab.launch()
    payload_before=request_input('crash-before','before-commit',ui)
    recovered=lab.http(ui['actionPath'],payload_before);require(recovered[0]==200,'ABORTED_TRANSACTION_RECOVERY_FAILED')
    require(lab.http(ui['actionPath'],payload_before)==recovered,'RECOVERED_REPLAY_FAILED')
    require(counts()['acp_outbox']==base_counts['acp_outbox']+events,'DUPLICATE_RECOVERED_EFFECTS')
    lab.record('crashBeforeCommit',pid=crashed_pid,exit=crashed_exit,clientOutcome='INDETERMINATE_RESPONSE',databaseOutcome='ROLLED_BACK',postgresTransactionStatus=fact,counts=counts())
    before_after=counts();payload_after=request_input('crash-after','after-commit',ui)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with lab.gate(AFTER):
            pending=pool.submit(lab.http,ui['actionPath'],payload_after,after=True);lab.blocked(AFTER)
            require(not pending.done(),'RESPONSE_NOT_HELD_AFTER_COMMIT')
            require(counts()['acp_outbox']==before_after['acp_outbox']+events,'NO_INDEPENDENT_COMMIT_PROOF')
            committed=lab.state();admission=lab.admission();crashed_pid=lab.process.pid;crashed_exit=stop(lab.process,crash=True);require(crashed_exit==-signal.SIGKILL,'APPLICATION_NOT_KILLED')
            try:pending.result(timeout=10);raise AssertionError('KILLED_RESPONSE_RETURNED')
            except (urllib.error.URLError,ConnectionError,TimeoutError):pass
    fresh=lab.launch();require(lab.state()==committed and lab.admission()==admission,'POSTCOMMIT_RESTART_STATE_LOSS')
    recovered=lab.http(ui['actionPath'],payload_after);require(recovered[0]==200,'LOST_RESPONSE_REPLAY_FAILED')
    code,observation=lab.http('/__test/recovery-observe',{});require(code==200 and observation['jobCompleted']==1,'JOB_RESTART_DUPLICATION')
    primed=lab.state();require(counts()['acp_outbox']==before_after['acp_outbox']+events,'POSTCOMMIT_DUPLICATION')
    require(lab.http(ui['actionPath'],payload_after)==recovered and lab.state()==primed,'SECOND_REPLAY_DUPLICATION')
    require(len(primed['acp_idempotency'])==events*4 and all(r['status']=='COMMITTED_RESULT' for r in primed['acp_idempotency']),'UNRESOLVED_IDEMPOTENCY')
    require(counts()['acp_outbox']==events*4,'WRONG_LOGICAL_BUSINESS_EFFECT_COUNT')
    lab.record('crashAfterCommitBeforeResponse',pid=crashed_pid,exit=crashed_exit,admissionState=admission,clientOutcome='INDETERMINATE_RESPONSE',databaseOutcome='COMMITTED',newProcess=fresh,counts=counts(),state=primed,logicalWorkflows=4,expectedBusinessEvents=events*4)
    # Unchanged records are checked individually, including tenant and exact bytes.
    require(len(primed[table])==4 and all(r['acp_version']==events for r in primed[table]),'COMMITTED_RECORD_LOSS')
    require(len(primed['recovery_transport'])==events*4 and len(primed['acp_delivery_attempt'])==events*4,'DELIVERY_DUPLICATED_OR_LOST')
    require(lab.sql('SELECT count(*) FROM recovery_transport t JOIN acp_outbox o ON o.id=t.identity WHERE o.payload<>t.payload')=='0','DELIVERY_PAYLOAD_CHANGED')
    require(len(primed['acp_lifecycle_anchor'])==4 and len(primed['acp_job_occurrence'])==1,'RUNTIME_FAMILY_LOST')
    require(len(primed['acp_lifecycle_release_audit'])==0,'UNAUTHORIZED_LIFECYCLE_RELEASE')
    protected=lab.state()
    for token,expected in (('browser-outsider',403),('browser-expired',401),('unknown',401)):
        code,_=lab.http(ui['actionPath'],request_input('fixture-resource','forged',ui),token);require(code==expected,'AUTH_BOUNDARY_CHANGED:'+str((token,code)))
    code,wrong=lab.http(ui['queryPath'],{'QUERY-TEXT':''},'browser-wrong-tenant');require(code==200 and wrong==[],'TENANT_LEAK')
    require(lab.state()==protected,'DENIED_REQUEST_PUBLISHED_EFFECTS')
    # Exact shared actor partition: four requests, no CLOCK_REVERSED; overfill is 429.
    lab.sql('DELETE FROM acp_rate')
    with ThreadPoolExecutor(max_workers=4) as pool:
        replies=list(pool.map(lambda _:lab.http(ui['queryPath'],{'QUERY-TEXT':''}),range(4)))
    require(all(code==200 for code,_ in replies),'RECOVERY_CONCURRENT_QUERY_FAILED')
    overload=[lab.http(ui['queryPath'],{'QUERY-TEXT':''})[0] for _ in range(20)];require(set(overload)<= {200,429} and 429 in overload,'RATE_LIMIT_NOT_ENFORCED')
    lab.record('securityAndRateAfterRecovery',authorization=403,expired=401,unknown=401,tenantRows=0,concurrentStatuses=[c for c,_ in replies],overloadStatuses=overload)
    lab.sql('UPDATE acp_sessions SET revoked=true');code,_=lab.http(ui['queryPath'],{'QUERY-TEXT':''});require(code==403,'REVOKED_SESSION_ACCEPTED')
    lab.record('revokedSessionRejected',httpStatus=code)


def qualify(workspace):
    workspace=Path(workspace).absolute();workspace.mkdir(mode=0o700,exist_ok=False)
    source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    bindings={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted((ROOT/'engineering/recovery').glob('*.py'))}
    result={'scope':'QUALIFICATION_ONLY','sourceCommit':source_commit,'image':IMAGE,'applications':{},'releaseClosure':'BLOCKED','phase6':'IN_PROGRESS','phase7':'NOT_STARTED','authority':'NOT_GRANTED'}
    for domain in ('payment','case-management'):
        candidate,snapshot,request,plan=inputs(domain);project=workspace/domain;FilesystemArtifactStore(project).apply(plan)
        generated={a.path:sha((project/a.path).read_bytes()) for a in plan.artifacts}
        backend=project/'backend';logs=workspace/(domain+'-logs');logs.mkdir();migration_dir=workspace/(domain+'-migration-inputs');shutil.copytree(backend/'src/main/resources/db/migration',migration_dir)
        originals={p.name:sha(p.read_bytes()) for p in migration_dir.iterdir() if p.is_file()}
        external={'backend/src/test/java/acp/browser/BrowserServer.java':server(domain),'backend/src/test/java/acp/browser/RecoveryResponseGate.java':FILTER,'backend/src/test/java/acp/recovery/MigrationProbe.java':MIGRATOR,'backend/src/test/java/acp/browser/RecoveryRuntimeProbe.java':RUNTIME_PROBE}
        for path,text in external.items():
            p=project/path;require(not p.exists(),'EXTERNAL_SOURCE_COLLISION');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        with (logs/'compile.log').open('wb') as out:subprocess.run(['mvn','-B','-ntp','test-compile','dependency:build-classpath','-Dmdep.outputFile=target/recovery-classpath'],cwd=backend,stdout=out,stderr=subprocess.STDOUT,check=True,timeout=900)
        text=(project/'frontend/src/task-ui-model.ts').read_text();ui=json.loads(text.split('=',1)[1].rsplit(' as const;',1)[0])
        with database() as container:
            readiness=authenticated_database_ready(container,os.environ['ACP_TEST_DATABASE_PASSWORD'])
            lab=Lab(container,'acp_recovery_'+domain.replace('-','_'),backend,migration_dir,logs,domain)
            try:
                first=lab.launch()
                statements=list(seed_sql(domain))
                for resource in ('original-committed','crash-before','crash-after'):
                    statements.extend(statement.replace('fixture-resource',resource) for statement in seed_sql(domain)[2:])
                lab.sql('BEGIN;'+ ';'.join(statements)+';CREATE TABLE recovery_transport(identity text PRIMARY KEY,payload bytea NOT NULL);COMMIT;')
                runtime_matrix(lab,ui,domain)
                # Use committed application state for every migration fault.
                stop(lab.process);migration_matrix(lab);before=lab.state();fresh=lab.launch();require(lab.state()==before,'RECOVERED_STARTUP_CHANGED_DATA')
                lab.migration('validate');require(lab.http(ui['queryPath'],{'QUERY-TEXT':''})[0]==403,'REVOCATION_LOST_DURING_MIGRATION_RECOVERY');require(lab.http(ui['actionPath'],request_input('original-committed','committed-before-restart',ui),'browser-competing')[0]==200,'POST_MIGRATION_REPLAY_FAILED');require(lab.state()==before,'POST_MIGRATION_REPLAY_DUPLICATION');lab.record('applicationStartsAfterMigrationRecovery',process=fresh,history=lab.history(),state=before,revokedSessionStatus=403)
                version=lab.sql('SHOW server_version;');observations=lab.observations;verify_observations(observations,1 if domain=='payment' else 3)
            except BaseException as error:
                (logs/'failure.json').write_text(json.dumps({'scope':'QUALIFICATION_ONLY','sourceCommit':source_commit,'database':container,'schema':lab.schema,'error':type(error).__name__+':'+str(error),'observations':lab.observations},sort_keys=True,indent=2)+'\n')
                raise
            finally:lab.close()
        require(generated=={p:sha((project/p).read_bytes()) for p in generated},'GENERATED_SOURCE_CHANGED')
        require(originals=={p:sha((migration_dir/p).read_bytes()) for p in originals},'HISTORICAL_MIGRATION_CHANGED')
        result['applications'][domain]={'candidate':candidate.descriptor(),'snapshot':snapshot.read()['contentDigest'],'database':{'container':container,'schema':lab.schema,'postgres':version,'identity':lab.identity,'readiness':readiness,'cleanup':'REMOVED'},'generatedSources':generated,'externalSources':{p:sha(v.encode()) for p,v in external.items()},'observations':observations,'tests':len(observations),'failures':0,'skipped':0,'migrationInputs':{p.name:sha(p.read_bytes()) for p in migration_dir.iterdir() if p.is_file()},'processCleanup':'REAPED','artifacts':{p.relative_to(workspace).as_posix():sha(p.read_bytes()) for p in sorted(logs.rglob('*')) if p.is_file()}}
        (workspace/(domain+'-results.json')).write_text(json.dumps(result['applications'][domain],sort_keys=True,indent=2)+'\n')
    require(bindings=={p:sha((ROOT/p).read_bytes()) for p in bindings},'QUALIFICATION_SOURCE_CHANGED')
    result['sourceHashes']=bindings;result['sealedParent']='sha256:'+bundle_digest();result['criteria']={'24':'QUALIFICATION_ONLY','25':'QUALIFICATION_ONLY'}
    result['resultSHA256']=sha(json.dumps(result,sort_keys=True,separators=(',',':')).encode());(workspace/'recovery-results.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);qualify(parser.parse_args().workspace)
