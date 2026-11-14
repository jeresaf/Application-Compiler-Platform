"""Bounded logical recovery for newly owned laboratory PostgreSQL only."""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import hashlib,json,os,re,selectors,subprocess,time,uuid
from engineering.reliability.database import owned_database
from engineering.generator_builds.runtime import docker
from engineering.source_intelligence.model import require,encode,sha
SCHEMA='acp_browser_case_management';AUX='h7_backup_control';GATE=62425177
_LIVE={};_TARGET_CAPABILITIES=set();_VERIFIED_TARGETS={}


def sql(container,statement):
    require(container in _LIVE,'H7_UNOWNED_DATABASE')
    raw=docker('exec',container,'psql','-X','-U','acp_runtime','-d','acp_runtime','-Atq','-v','ON_ERROR_STOP=1','-c',statement)
    return json.loads(raw)

class Transaction:
    def __init__(self,container):
        self.process=subprocess.Popen(['docker','exec','-i',container,'psql','-X','-U','acp_runtime','-d','acp_runtime','-Atq','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    def query(self,statement):
        self.process.stdin.write(statement+';\n');self.process.stdin.flush()
        selector=selectors.DefaultSelector();selector.register(self.process.stdout,selectors.EVENT_READ)
        try:require(bool(selector.select(15)),'H7_SQL_TIMEOUT');line=self.process.stdout.readline();require(bool(line),'H7_SQL_PROCESS_EXIT');return json.loads(line)
        finally:selector.close()
    def close(self):
        if self.process.poll() is None:
            self.process.stdin.write('ROLLBACK;\n\\q\n');self.process.stdin.flush()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=10)
        for p in (self.process.stdin,self.process.stdout,self.process.stderr):p.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()

def identity(container):
    return sql(container,"SELECT json_build_object('systemIdentifier',(SELECT system_identifier::text FROM pg_control_system()),'database',current_database(),'postgres',current_setting('server_version'),'postgresVersionNum',current_setting('server_version_num')::int,'started',pg_postmaster_start_time())")

def state(query):
    tables=query("SELECT coalesce(json_agg(tablename ORDER BY tablename),'[]') FROM pg_tables WHERE schemaname='"+SCHEMA+"'")
    require(tables,'H7_SCHEMA_MISSING');rows={}
    for name in tables:
        require(re.fullmatch('[a-z0-9_]+',name) is not None,'H7_SQL_IDENTIFIER')
        rows[name]=query('SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),\'[]\'::jsonb) FROM '+SCHEMA+'.'+name+' t')
    return rows

def schema_identity(container):
    return sql(container,"SELECT json_build_object('tables',(SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='"+SCHEMA+"'),'history',(SELECT json_agg(t ORDER BY installed_rank) FROM "+SCHEMA+".flyway_schema_history t))")

def install_control(container):
    require(container in _LIVE,'H7_UNOWNED_DATABASE')
    docker('exec',container,'psql','-X','-U','acp_runtime','-d','acp_runtime','-v','ON_ERROR_STOP=1','-c',"CREATE SCHEMA "+AUX+";CREATE FUNCTION "+AUX+".allow_row(n int) RETURNS boolean LANGUAGE plpgsql AS $$BEGIN IF current_setting('acp.h7_restore_gate',true)='on' THEN PERFORM pg_advisory_xact_lock("+str(GATE)+");END IF;RETURN TRUE;END$$;CREATE TABLE "+AUX+".barrier(n int CHECK("+AUX+".allow_row(n)));INSERT INTO "+AUX+".barrier VALUES(1)")

@contextmanager
def table_gate(container):
    with Transaction(container) as tx:
        tx.query('BEGIN;LOCK TABLE '+AUX+'.barrier IN ACCESS EXCLUSIVE MODE;SELECT to_json(true)')
        yield

@dataclass(frozen=True)
class Backup:
    directory:Path
    digest:str
    manifest_digest:str
    toc_digest:str
    size:int
    snapshot:str
    source_system:str

def verify(backup):
    require(type(backup) is Backup,'H7_BACKUP_BINDING')
    require(backup.directory.is_dir() and not backup.directory.is_symlink(),'H7_BACKUP_DIRECTORY')
    for name,pin in [('database.dump',backup.digest),('manifest.json',backup.manifest_digest),('objects.list',backup.toc_digest)]:
        p=backup.directory/name;require(p.is_file() and not p.is_symlink() and p.resolve().parent==backup.directory.resolve(),'H7_BACKUP_COMPONENT_MISSING_OR_ESCAPE');require(p.stat().st_size<=32*1024*1024,'H7_BACKUP_SIZE');require(sha(p.read_bytes())==pin,'H7_BACKUP_SUBSTITUTION')
    require((backup.directory/'database.dump').stat().st_size==backup.size and 0<backup.size<=32*1024*1024,'H7_BACKUP_INCOMPLETE')
    manifest=json.loads((backup.directory/'manifest.json').read_bytes());require(manifest.get('schema')=='acp-lab-logical-backup/1' and manifest.get('scope')=='QUALIFICATION_ONLY' and manifest.get('type')=='PG_DUMP_CUSTOM_EXPORTED_SNAPSHOT','H7_BACKUP_PROFILE');require(manifest['dumpSHA256']==backup.digest and manifest['objectsSHA256']==backup.toc_digest and manifest['size']==backup.size and manifest['boundary']['snapshot']==backup.snapshot and manifest['source']['systemIdentifier']==backup.source_system,'H7_BACKUP_CONTEXT');return manifest

def capture(container,directory,activity):
    """pg_dump uses an exported snapshot while real application commits overlap it."""
    directory=Path(directory).absolute();require(not directory.exists(),'H7_BACKUP_COLLISION');directory.mkdir(mode=0o700)
    install_control(container);source=identity(container);schema=schema_identity(container);begin=time.monotonic()
    with Transaction(container) as gate,Transaction(container) as tx:
        gate.query('BEGIN;LOCK TABLE '+AUX+'.barrier IN ACCESS EXCLUSIVE MODE;SELECT to_json(true)')
        boundary=tx.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;SELECT json_build_object('snapshot',pg_export_snapshot(),'visibility',pg_current_snapshot()::text,'time',clock_timestamp())")
        snapshot_observed=time.monotonic_ns();expected=state(tx.query);require(re.fullmatch('[0-9A-Fa-f-]+',boundary['snapshot']) is not None,'H7_SNAPSHOT_ID')
        dump=directory/'database.dump'
        with dump.open('xb') as output,(directory/'dump.stderr').open('xb') as error:
            dump.chmod(0o600)
            process=subprocess.Popen(['docker','exec',container,'pg_dump','-U','acp_runtime','-d','acp_runtime','--format=custom','--no-owner','--no-privileges','--schema='+SCHEMA,'--schema='+AUX,'--snapshot='+boundary['snapshot']],stdout=output,stderr=error)
            try:
                from engineering.jobs.scenarios import wait
                waiting=wait(lambda:sql(container,"SELECT json_build_object('waiters',count(*)) FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid WHERE a.application_name='pg_dump' AND NOT l.granted AND l.relation='"+AUX+".barrier'::regclass"),lambda x:x['waiters']==1,'H7_DUMP_NOT_IN_REAL_LOCK_WAIT',15)
                after_boundary=activity();require(process.poll() is None,'H7_ACTIVITY_NOT_OVERLAPPING_DUMP')
                gate.query('COMMIT;SELECT to_json(true)');require(process.wait(timeout=60)==0,'H7_DUMP_FAILED')
                require(state(tx.query)==expected,'H7_SNAPSHOT_NOT_REPEATABLE')
            except BaseException:
                process.terminate();process.wait(timeout=20);raise
    require(0<dump.stat().st_size<=32*1024*1024,'H7_BACKUP_SIZE')
    with dump.open('rb') as data:
        toc=subprocess.run(['docker','exec','-i',container,'pg_restore','--list'],stdin=data,capture_output=True,timeout=30,check=True).stdout
    (directory/'objects.list').write_bytes(toc)
    manifest={'schema':'acp-lab-logical-backup/1','scope':'QUALIFICATION_ONLY','type':'PG_DUMP_CUSTOM_EXPORTED_SNAPSHOT','postgres':source['postgres'],'source':source,'schemaIdentity':SCHEMA,'schemaState':schema,'boundary':boundary,'snapshotObservedMonotonicNs':snapshot_observed,'seconds':time.monotonic()-begin,'size':dump.stat().st_size,'dumpSHA256':sha(dump.read_bytes()),'objectsSHA256':sha(toc),'includedSchemas':[SCHEMA,AUX],'auxiliarySchema':'TEST_ONLY_LOCK_AND_INTERRUPTION_CONTROLS; NO_BUSINESS_SEMANTICS','capturedStateSHA256':sha(encode(expected)),'rowCounts':{k:len(v) for k,v in expected.items()},'activity':after_boundary,'dumpObservedWaiting':waiting,'encryption':'NOT_ENCRYPTED; PRIVATE_DISPOSABLE_SYNTHETIC_DATA_ONLY','productionCustody':'NOT_APPROVED','PITR':'NOT_RUN; NO_PHYSICAL_BACKUP_OR_WAL_REPLAY'}
    raw=encode(manifest);(directory/'manifest.json').write_bytes(raw)
    return Backup(directory,manifest['dumpSHA256'],sha(raw),sha(toc),manifest['size'],boundary['snapshot'],source['systemIdentifier']),expected,manifest

@dataclass(frozen=True)
class Target:
    container:str
    owner:str
    system:str

@contextmanager
def new_database(active,resources):
    with owned_database(active,resources) as container:
        row=resources[-1];require(row['container']==container,'H7_DATABASE_OWNER');_LIVE[container]=row['owner']
        try:
            require(docker('inspect','--format','{{index .Config.Labels "acp.h2.owner"}}',container)==row['owner'],'H7_DATABASE_OWNER')
            require(identity(container)['postgresVersionNum']==180006,'H7_POSTGRES_VERSION')
            yield container
        finally:_LIVE.pop(container,None)

@contextmanager
def restore_target(active,resources):
    with new_database(active,resources) as container:
        target=Target(container,_LIVE[container],identity(container)['systemIdentifier']);_TARGET_CAPABILITIES.add(id(target))
        try:yield target
        finally:_TARGET_CAPABILITIES.discard(id(target));_VERIFIED_TARGETS.pop(id(target),None)

def target_guard(target,*,empty=True):
    require(type(target) is Target and id(target) in _TARGET_CAPABILITIES and target.container in _LIVE and target.container=='acp-06-runtime-h2-'+target.owner,'H7_RESTORE_TARGET')
    require(docker('inspect','--format','{{index .Config.Labels "acp.h2.owner"}}',target.container)==target.owner,'H7_RESTORE_OWNER')
    require(identity(target.container)['systemIdentifier']==target.system,'H7_RESTORE_IDENTITY')
    if empty:require(sql(target.container,"SELECT to_json(count(*)) FROM pg_namespace WHERE nspname IN ('"+SCHEMA+"','"+AUX+"')")==0,'H7_RESTORE_TARGET_NOT_EMPTY')

def restore(backup,target,expected,*,gated=False,interrupt=None):
    manifest=verify(backup);target_guard(target);require(target.system!=backup.source_system,'H7_RESTORE_NOT_INDEPENDENT');begin=time.monotonic()
    command=['docker','exec','-i']
    if gated:command+=['-e','PGOPTIONS=-c acp.h7_restore_gate=on']
    command += [target.container,'pg_restore','-U','acp_runtime','-d','acp_runtime','--single-transaction','--exit-on-error','--no-owner','--no-privileges']
    with (backup.directory/'database.dump').open('rb') as data:
        process=subprocess.Popen(command,stdin=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            if interrupt:interrupt(process,target)
            output,error=process.communicate(timeout=90)
        except BaseException:
            if process.poll() is None:
                try:sql(target.container,"SELECT coalesce(json_agg(pg_terminate_backend(pid)),'[]') FROM pg_stat_activity WHERE application_name='pg_restore' AND pid<>pg_backend_pid()")
                finally:
                    process.terminate()
                    try:process.communicate(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=10)
            raise
    require(process.returncode==0,'H7_RESTORE_PROCESS_FAILED');actual=state(lambda q:sql(target.container,q));require(actual==expected,'H7_RESTORED_STATE_MISMATCH');require(schema_identity(target.container)==manifest['schemaState'],'H7_RESTORED_SCHEMA_MISMATCH')
    _VERIFIED_TARGETS[id(target)]=(backup.digest,sha(encode(actual)))
    return {'seconds':time.monotonic()-begin,'stateSHA256':sha(encode(actual)),'rowCounts':{k:len(v) for k,v in actual.items()},'schemaSHA256':sha(encode(manifest['schemaState'])),'target':identity(target.container),'exit':process.returncode}

def admit_application(backup,target):
    verify(backup);target_guard(target,empty=False)
    receipt=_VERIFIED_TARGETS.get(id(target));require(receipt is not None and receipt[0]==backup.digest,'H7_RESTORE_NOT_VERIFIED')
    require(sha(encode(state(lambda q:sql(target.container,q))))==receipt[1],'H7_RESTORE_CHANGED_BEFORE_ACTIVATION')
    return True
