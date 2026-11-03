"""Real HTTP operations, independent PG barriers and process failures. No result mocks."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib,json,os,signal,subprocess,threading,time,urllib.request,urllib.error,uuid
import statistics
from pathlib import Path
from engineering.source_intelligence.model import require,encode,sha
from engineering.demo import reference as demo
from engineering.reference_application import lifecycle as life
from engineering.reference_application.evolution import api,DisposableSQL,SCHEMA
from engineering.jobs.scenarios import wait,worker_env
from engineering.jobs.fixture import PREFIX
from engineering.reliability.fixture import BEFORE,AFTER
from engineering.reliability.database import ready,renew_connection

TOKENS=('browser-authorized','browser-competing','browser-report-tenant-two','browser-report-tenant-two-peer')


def http(session,path,payload,token='browser-authorized',*,multipart=False,after=False):
    headers={'Authorization':'Bearer '+token}
    if multipart:body,kind=payload;headers['Content-Type']=kind
    else:body=json.dumps(payload).encode();headers['Content-Type']='application/json'
    if after:headers['X-H2-After-Commit']='hold'
    start=time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(session.backend_port)+path,data=body,headers=headers),timeout=25) as response:
            raw=response.read();kind=response.headers.get('Content-Type','');value=json.loads(raw) if 'json' in kind else raw
            return {'status':response.status,'value':value,'seconds':time.monotonic()-start}
    except urllib.error.HTTPError as error:return {'status':error.code,'value':error.read().decode(),'seconds':time.monotonic()-start}


def upload(resource,key,raw=b'H2 exact committed document\n',filename='h2.txt'):
    boundary='ACP-H2-'+uuid.uuid4().hex
    parts=[]
    for name,value in {'resourceId':resource,'idempotencyKey':key,'sha256':hashlib.sha256(raw).hexdigest()}.items():
        parts.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+name+'"\r\n\r\n'+value+'\r\n').encode())
    parts.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="content"; filename="'+filename+'"\r\nContent-Type: text/plain\r\n\r\n').encode()+raw+b'\r\n')
    return b''.join(parts)+('--'+boundary+'--\r\n').encode(),'multipart/form-data; boundary='+boundary


class Lab:
    def __init__(self,root,folder,container):
        self.root,self.logs,self.container=Path(root),Path(folder),container
        self.logs.mkdir(mode=0o700)
        self.db=DisposableSQL(container,self.logs);self.sessions=[];self.rows=[];self.sequence=1000
        self.create=json.loads((self.root/'backend/src/main/resources/acp-intake-preview.json').read_bytes())
        self.documents=json.loads((self.root/'backend/src/main/resources/acp-documents.json').read_bytes())
        self.table=self.documents['resourceTable'];self.doc=self.documents['table']
        self.identity=self.db.data("SELECT json_build_object('database',current_database(),'systemIdentifier',(SELECT system_identifier::text FROM pg_control_system()),'postgres',current_setting('server_version'),'started',pg_postmaster_start_time())")

    def start(self,*,workers=False,port=18081):
        session=demo.Session(self.root,'case-management',self.logs);self.sequence+=10;session.sequence=self.sequence;session.backend_port=port
        session.env.update(ACP_INTAKE_MODE='synthetic-preview',ACP_REPORTING_MODE='preview',ACP_DOCUMENTS_MODE='preview',ACP_INTEGRITY_MODE='preview')
        worker_env(session,workers);self.sessions.append(session);session.launch();return session

    def state(self):return demo.database_state(self.container,SCHEMA)
    def record(self,name,**facts):
        self.rows.append({'scenario':name,'result':'PASS','database':self.identity,**facts})
        life.save(self.logs/'observations.json',{'scope':'QUALIFICATION_ONLY','scenarios':self.rows})
    def counts(self):
        return {t:self.db.data('SELECT to_json(count(*)) FROM '+t) for t in (self.table,self.doc,'acp_audit','acp_classification_audit','acp_idempotency')}
    def lock_count(self,key,granted):
        return self.db.data("SELECT to_json(count(*)) FROM pg_locks WHERE locktype='advisory' AND objid="+str(key)+' AND '+('granted' if granted else 'NOT granted'))
    @contextmanager
    def gate(self,key):
        process=subprocess.Popen(['docker','exec','-i',self.container,'psql','-X','-U','acp_runtime','-d','acp_runtime','-Atq','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            process.stdin.write('SELECT pg_advisory_lock('+str(key)+');\n');process.stdin.flush()
            wait(lambda:self.lock_count(key,True),lambda n:n==1,'H2_GATE_NOT_HELD')
            yield
        finally:
            if process.poll() is None:
                process.stdin.write('SELECT pg_advisory_unlock('+str(key)+');\n\\q\n');process.stdin.flush()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
            for stream in (process.stdin,process.stdout,process.stderr):stream.close()
    def blocked(self,key,n=1):return wait(lambda:self.lock_count(key,False),lambda value:value>=n,'H2_NO_REAL_CONTENTION')
    def trigger(self,table,enabled):
        if enabled:self.db.run("CREATE FUNCTION h2_before() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN PERFORM pg_advisory_xact_lock("+str(BEFORE)+");RETURN NEW;END$$;CREATE TRIGGER h2_before BEFORE INSERT ON "+table+' FOR EACH ROW EXECUTE FUNCTION h2_before()')
        else:self.db.run('DROP TRIGGER h2_before ON '+table+';DROP FUNCTION h2_before()')
    def restart(self,session):
        session.close();start=time.monotonic();fresh=self.start(port=session.backend_port)
        return fresh,time.monotonic()-start
    def kill(self,session):
        pid=session.process.pid;session.process.kill();code=session.process.wait(timeout=10);require(code==-signal.SIGKILL,'H2_NOT_PROCESS_KILL');return {'pid':pid,'exit':code}
    def close(self):
        for session in self.sessions:session.close()


def concurrent(lab,session,path,payloads,*,multipart=False):
    started=time.monotonic()
    barrier=threading.Barrier(len(payloads)+1)
    def call(item):
        token,payload=item;barrier.wait(timeout=10);return http(session,path,payload,token,multipart=multipart)
    with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
        with lab.gate(BEFORE):
            pending=[pool.submit(call,p) for p in payloads];barrier.wait(timeout=10)
            blocked=lab.blocked(BEFORE,2)
            require(sum(not p.done() for p in pending)>=2,'H2_SEQUENTIAL_COUNTEREXAMPLE')
            connections=lab.db.data("SELECT to_json(count(*)) FROM pg_stat_activity WHERE datname=current_database() AND state='active'")
        results=[p.result(timeout=25) for p in pending]
    elapsed=time.monotonic()-started;durations=[r['seconds'] for r in results]
    return results,{'blockedBusinessTransactions':blocked,'activeConnections':connections,'submitted':len(payloads),
                    'completed':len(results),'failures':sum(r['status']>=400 for r in results),'seconds':elapsed,
                    'observedRequestsPerSecond':len(results)/elapsed,'latencySeconds':{'minimum':min(durations),'median':statistics.median(durations),'maximum':max(durations)},
                    'measurementScope':'FOUR_REQUESTS; INCLUDES_CONTROLLED_BARRIER_TIME; NO_PRODUCTION_SLO_OR_TAIL_ESTIMATE'}


def run(lab):
    session=lab.start();history=life.history(lab.container)
    authenticated=[]
    for token in TOKENS:
        status,value=api(session,'/__test/h2-session',{},token);require(status==200 and len(value['sessions'])==1,'H2_SESSION_INIT');authenticated.extend(value['sessions'])
    require(len({(r['tenant'],r['subject'],r['sid']) for r in authenticated})==4,'H2_SHARED_SESSION')
    payload={'title':'H2 concurrent creation','summary':'H2 isolated data','idempotencyKey':'h2-parallel-create'}
    before=lab.counts();lab.trigger(lab.table,True)
    try:responses,overlap=concurrent(lab,session,lab.create['path'],[(t,payload) for t in TOKENS])
    finally:lab.trigger(lab.table,False)
    require(all(r['status'] in (200,202) for r in responses),'H2_CREATE_CONCURRENT_STATUS')
    a=http(session,lab.create['path'],payload,TOKENS[0]);b=http(session,lab.create['path'],payload,TOKENS[2]);require(a['status']==b['status']==200,'H2_CREATE_REPLAY')
    resources=[a['value']['resourceId'],b['value']['resourceId']];require(len(set(resources))==2,'H2_TENANT_IDEMPOTENCY_COLLISION')
    after=lab.counts();require(after[lab.table]==before[lab.table]+2 and after['acp_audit']==before['acp_audit']+2 and after['acp_classification_audit']==before['acp_classification_audit']+2*len(lab.create['writtenFields']) and after['acp_idempotency']==before['acp_idempotency']+2,'H2_DUPLICATE_CREATE_EFFECT')
    classified=[]
    for resource,tenant,subject in zip(resources,('tenant-one','tenant-two'),('fixture:operator','fixture:reporter-two')):
        fields=lab.db.data("SELECT coalesce(json_agg(json_build_object('field',field,'mode',mode,'tenant',convert_from(tenant,'UTF8'),'subject',convert_from(subject,'UTF8'))),'[]') FROM acp_classification_audit WHERE operation='CREATE-CASE' AND resource=convert_to('"+resource+"','UTF8')")
        require(len(fields)==len(lab.create['writtenFields']) and {f['field'] for f in fields}==set(lab.create['writtenFields']) and all(f['mode']=='WRITE' and f['tenant']==tenant and f['subject']==subject for f in fields),'H2_CLASSIFICATION_AUDIT_COVERAGE')
        classified.append(fields)
    lab.record('parallelCaseCreation',sessions=authenticated,overlap=overlap,responses=responses,resources=resources,before=before,after=after,classifiedFields=classified,replays=[a,b],duplicateEffects=0)

    before=lab.counts();lab.trigger(lab.doc,True)
    inputs=[(t,upload(resources[0 if i<2 else 1],'h2-upload')) for i,t in enumerate(TOKENS)]
    try:responses,overlap=concurrent(lab,session,lab.documents['path']+'/upload',inputs,multipart=True)
    finally:lab.trigger(lab.doc,False)
    require(all(r['status']==200 for r in responses),'H2_UPLOAD_CONCURRENT_STATUS')
    require(responses[0]['value']==responses[1]['value'] and responses[2]['value']==responses[3]['value'],'H2_UPLOAD_REPLAY_MISMATCH')
    after=lab.counts();require(after[lab.doc]==before[lab.doc]+2 and after['acp_audit']==before['acp_audit']+2,'H2_PARTIAL_OR_DUPLICATE_UPLOAD')
    for i in (0,2):
        resource=resources[i//2];document=responses[i]['value']['documentId'];r=http(session,lab.documents['path']+'/download',{'resourceId':resource,'documentId':document},TOKENS[i]);require(r['status']==200 and r['value']==b'H2 exact committed document\n','H2_DOCUMENT_LOSS')
        denied=http(session,lab.documents['path']+'/metadata',{'resourceId':resource,'documentId':document},TOKENS[2 if i==0 else 0]);require(denied['status'] in (403,404),'H2_TENANT_ESCAPE')
    lab.record('simultaneousDocumentUploads',overlap=overlap,before=before,after=after,documents=[r['value'] for r in responses],duplicateEffects=0,tenantDenials=2)

    # A real backend connection is lost inside an uncommitted document insert.
    before=lab.counts();lab.trigger(lab.doc,True)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with lab.gate(BEFORE):
                future=pool.submit(http,session,lab.documents['path']+'/upload',upload(resources[0],'h2-db-loss'),multipart=True)
                lab.blocked(BEFORE)
                victims=lab.db.data("SELECT coalesce(json_agg(a.pid),'[]') FROM pg_stat_activity a JOIN pg_locks l ON l.pid=a.pid WHERE l.locktype='advisory' AND l.objid="+str(BEFORE)+' AND NOT l.granted')
                require(len(victims)==1,'H2_WRONG_CONNECTION_FAILURE_TARGET');lab.db.run('SELECT pg_terminate_backend('+str(victims[0])+')')
                failed=future.result(timeout=25);require(failed['status']>=500,'H2_LOST_CONNECTION_REPORTED_SUCCESS')
        require(lab.counts()==before,'H2_PARTIAL_DOCUMENT_ON_CONNECTION_LOSS')
    finally:lab.trigger(lab.doc,False)
    retry=http(session,lab.documents['path']+'/upload',upload(resources[0],'h2-db-loss'),multipart=True);require(retry['status']==200,'H2_CONNECTION_RECOVERY')
    lab.record('databaseConnectionLossBeforeDocumentCommit',terminatedBackends=victims,failedStatus=failed['status'],before=before,recovered=lab.counts(),duplicateEffects=0)

    # Kill the JVM with a business transaction demonstrably blocked before commit.
    payload={'title':'H2 crash before commit','summary':'recovered once','idempotencyKey':'h2-crash-before'}
    before=lab.counts();lab.trigger(lab.table,True)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with lab.gate(BEFORE):
                pending=pool.submit(http,session,lab.create['path'],payload);lab.blocked(BEFORE)
                xid=lab.db.data("SELECT to_json(attempt_xid::text) FROM acp_idempotency WHERE status='IN_FLIGHT'")
                killed=lab.kill(session)
                try:pending.result(timeout=15);raise AssertionError('H2_KILLED_CLIENT_SUCCEEDED')
                except (OSError,ConnectionError):pass
            status=wait(lambda:lab.db.data("SELECT to_json(pg_xact_status('"+xid+"'::xid8))"),lambda s:s=='aborted','H2_NO_TRANSACTION_ABORT')
        current=lab.counts();require(all(current[t]==before[t] for t in before if t!='acp_idempotency'),'H2_CRASH_BEFORE_PARTIAL_EFFECT')
    finally:lab.trigger(lab.table,False)
    session,duration=lab.restart(session);replayed=http(session,lab.create['path'],payload);require(replayed['status']==200,'H2_ABORT_RECOVERY');require(http(session,lab.create['path'],payload)['value']==replayed['value'],'H2_ABORT_REPLAY_DUPLICATE')
    require(lab.counts()[lab.table]==before[lab.table]+1,'H2_ABORT_DUPLICATE_EFFECT')
    lab.record('processDeathBeforeCommit',killed=killed,xid=xid,databaseOutcome=status,recoverySeconds=duration,duplicateEffects=0,counts=lab.counts())

    # Buffer the response outside the real controller transaction, observe commit,
    # then terminate the JVM before the response is copied to the HTTP socket.
    for kind,path,payload,is_multipart in (
        ('case',lab.create['path'],{'title':'H2 lost acknowledgement','summary':'committed once','idempotencyKey':'h2-after-commit'},False),
        ('document',lab.documents['path']+'/upload',upload(resources[0],'h2-after-commit'),True)):
        before=lab.counts()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with lab.gate(AFTER):
                pending=pool.submit(http,session,path,payload,multipart=is_multipart,after=True);lab.blocked(AFTER)
                committed=lab.counts();table=lab.table if kind=='case' else lab.doc
                require(committed[table]==before[table]+1 and committed['acp_audit']==before['acp_audit']+1 and not pending.done(),'H2_NO_INDEPENDENT_COMMIT_BEFORE_ACK')
                killed=lab.kill(session)
                try:pending.result(timeout=15);raise AssertionError('H2_ACK_NOT_LOST')
                except (OSError,ConnectionError):pass
        session,duration=lab.restart(session);first=http(session,path,payload,multipart=is_multipart);second=http(session,path,payload,multipart=is_multipart)
        require(first['status']==second['status']==200 and first['value']==second['value'] and lab.counts()==committed,'H2_POSTCOMMIT_DUPLICATION')
        lab.record(kind+'DeathAfterCommitBeforeAcknowledgement',killed=killed,committed=committed,recoverySeconds=duration,replay=first['value'],duplicateEffects=0)

    # The DB restarts with the same owned volume, not a new empty tmpfs database.
    state=lab.state();started=lab.db.data('SELECT to_json(pg_postmaster_start_time())');begin=time.monotonic()
    subprocess.run(['docker','restart',lab.container],check=True,capture_output=True,timeout=40);ready(lab.container)
    binding=renew_connection(lab.container);after_started=lab.db.data('SELECT to_json(pg_postmaster_start_time())')
    require(after_started!=started,'H2_DB_NOT_RESTARTED')
    require(lab.state()==state and life.history(lab.container)==history,'H2_DATABASE_RESTART_LOSS')
    session,duration=lab.restart(session);require(life.history(lab.container)==history,'H2_REPEATED_MIGRATION_MUTATION')
    lab.record('databaseAndApplicationRestart',beforeStarted=started,afterStarted=after_started,ownedBinding=binding,recoverySeconds=time.monotonic()-begin,history=history,stateDigest=sha(encode(state)))
    # Terminate a fresh startup before its readiness observer can complete.
    session.close();before=lab.state();prior=len(lab.sessions)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending=pool.submit(lab.start)
        probe=wait(lambda:lab.sessions[prior] if len(lab.sessions)>prior else None,
                   lambda s:s is not None and s.process is not None,'H2_RESTART_NOT_SPAWNED')
        require(not pending.done(),'H2_RESTART_ALREADY_READY');killed=lab.kill(probe)
        try:pending.result(timeout=15);raise AssertionError('H2_INTERRUPTED_RESTART_SUCCEEDED')
        except ValueError:pass
    session=lab.start();require(lab.state()==before and life.history(lab.container)==history,'H2_INTERRUPTED_RESTART_STATE_LOSS')
    lab.record('interruptedApplicationRestart',killed=killed,freshPid=session.process.pid,history=history,stateDigest=sha(encode(before)))
    return session,resources


def workers(lab,session,resource):
    session.close()
    first=lab.start(workers=True,port=18081);second=lab.start(workers=True,port=18082)
    pair=[first,second]
    def state():
        code,value=api(pair[0],'/__test/job-state');require(code==200,'H2_WORKER_STATE');return value
    def admin(action,**values):
        code,value=api(pair[0],'/__test/job-admin',{'action':action,**values});require(code==200,'H2_WORKER_ADMIN');return value
    document=lab.db.data("SELECT json_build_object('id',id::text,'sha',sha256) FROM "+lab.doc+" WHERE resource=convert_to('"+resource+"','UTF8') AND idempotency_key='h2-upload'")
    offset=1
    def enqueue():
        nonlocal offset
        q=str(uuid.uuid4());admin('ENQUEUE_FAULT',queue=q,resource=resource,document=document['id'],sha256=document['sha'],offset=offset,mode='HOLD_FIRST');offset+=1;return q
    def qrow(q):return next(r for r in state()['queue'] if r['id']==q)
    def entered(queues):
        return wait(state,lambda s:all(any(c['queue']==q and c['entered'] for c in s['controls']) for q in queues),'H2_WORKERS_NOT_SIMULTANEOUS',1.8)
    def finished(q):return wait(lambda:qrow(q),lambda r:r['state']=='COMPLETED','H2_WORKER_NOT_RECOVERED',20)
    def single(q):
        s=state();rows=[r for r in s['results'] if r['queue']==q];require(len(rows)==1 and rows[0]['status']=='VALID','H2_DUPLICATE_OR_INVALID_TERMINAL')
        require(sum(a['id']==rows[0]['audit_id'] for a in s['audits'])==1,'H2_MISSING_RESULT_AUDIT');return s
    try:
        started=time.monotonic();queues=[enqueue() for _ in range(4)];held=entered(queues)
        running=[r for r in held['queue'] if r['id'] in queues]
        require(len(running)==4 and all(r['state']=='RUNNING' and r['token']==1 for r in running) and len({r['owner'] for r in running})==2,'H2_QUEUE_CLAIMS_SERIALIZED')
        for q in queues:admin('RELEASE',queue=q)
        for q in queues:finished(q);single(q)
        lab.record('concurrentQueueClaims',held=held,queues=queues,processes=[s.process.pid for s in pair],seconds=time.monotonic()-started,terminalResults=4,duplicateEffects=0)

        q=enqueue();held=entered([q]);old=qrow(q);owners={api(s,'/__test/worker-owner')[1]['owner']:s for s in pair};holder=owners[old['owner']]
        code,_=api(holder,'/__test/h2-pause-claims',{});require(code==200,'H2_POLLING_NOT_PAUSED')
        admin('EXPIRE',queue=q);winner=finished(q);require(winner['token']==2 and winner['owner']!=old['owner'],'H2_RECLAIM_NOT_INDEPENDENT')
        admin('RELEASE',queue=q);proof=wait(state,lambda s:any(a['queue']==q and a['token']==1 and a['state']=='FENCED_RESULT' for a in s['attempts']),'H2_STALE_RESULT_NOT_REJECTED')
        single(q);lab.record('leaseExpiryAndStaleCompletion',held=held,before=old,winner=winner,after=proof,duplicateEffects=0)
        holder.close();pair[pair.index(holder)]=lab.start(workers=True,port=holder.backend_port)

        q=enqueue();held=entered([q]);old=qrow(q);owners={api(s,'/__test/worker-owner')[1]['owner']:s for s in pair};victim=owners[old['owner']];killed=lab.kill(victim)
        survivor=next(s for s in pair if s is not victim);pair[:]=[survivor,victim]
        begin=time.monotonic();winner=finished(q);require(winner['owner']!=old['owner'] and winner['token']==2,'H2_DEAD_WORKER_NOT_RECLAIMED');proof=single(q)
        lab.record('workerDeathAfterClaim',held=held,before=old,killed=killed,winner=winner,after=proof,recoverySeconds=time.monotonic()-begin,duplicateEffects=0,executionModel='AT_LEAST_ONCE; FENCED_SINGLE_TERMINAL_EFFECT')
    finally:
        for s in pair:s.close()
