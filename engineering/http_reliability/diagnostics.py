"""Read-only PostgreSQL observations; no outcome inferred solely from HTTP."""
from contextlib import contextmanager
import threading,time
from canonical_json import canonical_bytes
from engineering.disaster_recovery import backup as db
from engineering.jobs.fixture import PREFIX
from engineering.source_intelligence.model import sha,encode,require

def identity(operation,revision,tenant,subject,key):
    typed=canonical_bytes({'type':{'kind':'String'},'value':key}).decode()
    return sha(canonical_bytes([operation+'-IDEMPOTENCY',revision,tenant,'NEW:'+subject,operation,revision,typed]))

def ledger(lab,key_identity,tenant,subject):
    require(len(key_identity)==64 and all(c in '0123456789abcdef' for c in key_identity),'H9_LEDGER_IDENTITY')
    rows=lab.db.data("SELECT coalesce(json_agg(json_build_object('status',status,'resourceId',convert_from(result,'UTF8')::jsonb->>'resourceId','commitXid',commit_xid)),'[]') FROM acp_idempotency WHERE identity=decode('"+key_identity+"','hex')")
    require(len(rows)<=1,'H9_DUPLICATE_LEDGER');row=rows[0] if rows else None
    if row and row['status']=='COMMITTED_RESULT':
        require(row['resourceId'] and row['commitXid'],'H9_INCOMPLETE_COMMIT');require(lab.ownership(row['resourceId'])=={'tenant':tenant,'subject':subject},'H9_COMMIT_OWNERSHIP')
        return {'outcome':'COMMITTED','resourceSHA256':sha(row['resourceId'].encode()),'commitXid':row['commitXid']}
    return {'outcome':'INDETERMINATE' if row else 'NO_COMMITTED_EFFECT_OBSERVED','ledgerState':row['status'] if row else None}

@contextmanager
def database_samples(container):
    stop=threading.Event();samples=[];errors=[]
    statement="SELECT json_build_object('active',count(*) FILTER(WHERE state='active'),'transactions',count(*) FILTER(WHERE xact_start IS NOT NULL),'lockWaiters',count(*) FILTER(WHERE wait_event_type='Lock'),'advisoryWaiters',(SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted),'pendingJobs',(SELECT count(*) FROM "+db.SCHEMA+'.'+PREFIX+"_queue WHERE state IN ('PENDING','RETRY','RUNNING')),'processes',coalesce(json_agg(json_build_object('pid',pid,'state',state,'waitType',wait_event_type,'transaction',backend_xid::text,'queryId',query_id)), '[]')) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"
    def sample():
        try:
            while not stop.is_set():
                require(len(samples)<1024,'H9_SAMPLE_BOUND');samples.append({'monotonicNs':time.monotonic_ns(),'postgres':db.sql(container,statement)})
                stop.wait(.1)
        except Exception as error:errors.append(type(error).__name__)
    thread=threading.Thread(target=sample,name='h9-readonly-database-observer');thread.start()
    try:yield samples
    finally:
        stop.set();thread.join(timeout=10);require(not thread.is_alive() and not errors,'H9_DATABASE_SAMPLER_FAILED');require(samples,'H9_MISSING_DATABASE_OBSERVATION')

def classify(attempts,variants):
    by={v['id']:v for v in variants};ordinary=[];pressure=[]
    for row in attempts:
        if row['response']['status']!=500:continue
        (pressure if by[row['variant']]['pool']<34 else ordinary).append(row['response']['correlation'])
    return {'studyOutcome':'CURRENT_PROFILE_FAILURE_CAUSE_UNRESOLVED' if ordinary else 'INJECTED_ANALOGOUS_FAILURE' if pressure else 'NO_REPRODUCTION_OBSERVED','normalProfile500s':len(ordinary),'resourceVariant500s':len(pressure),'historicalCause':'UNRESOLVED_NOT_CAUSALLY_ATTRIBUTED','causalScope':'Current controlled profile only; no identity with original H3 failure inferred.'}
