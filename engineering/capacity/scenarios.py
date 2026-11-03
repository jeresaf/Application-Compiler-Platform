"""Explicit resource/fault experiments. Their latency is not normal service latency."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import hashlib,json,signal,time,uuid
from engineering.capacity.workload import request,token,principal,PROFILE
from engineering.capacity.metrics import aggregate,Sampler
from engineering.reliability import concurrency as h2
from engineering.reliability.fixture import BEFORE
from engineering.jobs.fixture import PREFIX
from engineering.jobs.scenarios import wait
from engineering.reference_application.evolution import api
from engineering.reference_application import lifecycle as life
from engineering.source_intelligence.model import require


def documents(lab,key):
    return lab.db.data("SELECT coalesce(json_agg(json_build_object('id',id::text,'sha256',sha256,'size',size,'resource',convert_from(resource,'UTF8'),'tenant',convert_from(tenant,'UTF8'))),'[]') FROM "+lab.doc+" WHERE idempotency_key LIKE '"+key+"%'")


def invalid_inputs(lab,session):
    before=lab.counts();observed=[];resource=lab.resources[0]
    cases=[('oversized',lab.documents_path+'/upload',h2.upload(resource,'h3-invalid-large',b'x'*65537),True,0,413),
           ('invalidFilename',lab.documents_path+'/upload',h2.upload(resource,'h3-invalid-name',b'x','../escape.txt'),True,0,400),
           ('invalidUTF8',lab.documents_path+'/upload',h2.upload(resource,'h3-invalid-utf8',b'\xff'),True,0,415),
           ('missingCreateField',lab.create['path'],{'idempotencyKey':'h3-invalid-create'},False,0,400),
           ('invalidReportPage',lab.report['path'],{'size':21},False,0,400),
           ('wrongTenantDocument',lab.documents_path+'/metadata',{'resourceId':resource,'documentId':lab.seeds[0]['documentId']},False,1,404),
           ('wrongTenantHistory',lab.report['path']+'/history',{'resourceId':resource},False,1,404)]
    for name,path,payload,multipart,i,expected in cases:
        r=request(session,path,payload,token(i),multipart=multipart);require(r['status']==expected,'H3_INVALID_INPUT_ACCEPTED:'+name+':'+str(r));observed.append({'case':name,'status':r['status'],'milliseconds':r['milliseconds']})
    for identity,status in [('invalid',401),('browser-expired',401),('browser-outsider',403),('browser-h3-99',401)]:
        r=request(session,lab.report['path'],{},identity);require(r['status']==status,'H3_AUTHORIZATION_BYPASS');observed.append({'case':identity,'status':r['status'],'milliseconds':r['milliseconds']})
    require(lab.counts()==before,'H3_REJECTED_INPUT_PUBLISHED')
    maximum=b'x'*65536;value=lab.checked(session,lab.documents_path+'/upload',h2.upload(resource,'h3-at-document-limit',maximum),multipart=True)
    require(value['size']==65536 and value['sha256']==hashlib.sha256(maximum).hexdigest(),'H3_EXACT_DOCUMENT_LIMIT')
    return {'scenario':'invalidAndBoundedInputs','result':'PASS','rejections':observed,'maximumDocumentBytes':65536,'maximumAccepted':value,'rejectedOperationsPublished':False}


def workers(lab,session):
    def admin(action,**values):
        code,value=api(session,'/__test/job-admin',{'action':action,**values});require(code==200,'H3_QUEUE_SETUP');return value
    seeds=[];enqueue=[]
    for i in range(2):seeds.append((lab.resources[i],lab.seeds[i]['documentId'],lab.seeds[i]['sha256']))
    for index in range(PROFILE['explicitQueueOccurrences']):
        i=index%2;resource,document,sha=seeds[i];q=str(uuid.uuid4());admin('ENQUEUE_FAULT',queue=q,resource=resource,document=document,sha256=sha,tenant=principal(i)[0],offset=index+100,mode='NONE');enqueue.append({'queue':q,'tenant':principal(i)[0],'started':time.monotonic()})
    pending=lab.db.data("SELECT to_json(count(*)) FROM "+PREFIX+"_queue WHERE state='PENDING'");require(pending>=len(enqueue),'H3_QUEUE_GROWTH_NOT_OBSERVED')
    history=life.history(lab.container);session.close();begin=time.monotonic();session=lab.start(workers=True)
    with Sampler(lab,session,PROFILE['samplerIntervalSeconds']) as sampler:
        def state():
            code,value=api(session,'/__test/job-state');require(code==200,'H3_JOB_STATE');return value
        ids={q['queue'] for q in enqueue}
        final=wait(state,lambda s:all(any(r['queue']==q and r['status']=='VALID' for r in s['results']) for q in ids),'H3_QUEUE_NOT_DRAINED',PROFILE['workerTimeoutSeconds'])
    elapsed=time.monotonic()-begin
    rows=lab.db.data("SELECT json_agg(json_build_object('queue',q.id::text,'tenant',convert_from(q.tenant,'UTF8'),'state',q.state,'attempts',q.attempts,'started',extract(epoch FROM q.started_at),'finished',extract(epoch FROM q.finished_at),'secondsFromClaim',extract(epoch FROM(q.finished_at-q.started_at)),'result',r.status,'audit',r.audit_id,'auditTenant',convert_from(a.tenant,'UTF8'))) FROM "+PREFIX+"_queue q JOIN "+PREFIX+"_result r ON r.queue=q.id JOIN acp_audit a ON a.id=r.audit_id WHERE q.id IN ("+','.join("'"+q+"'::uuid" for q in sorted(ids))+")")
    require(len(rows)==len(ids) and len({r['audit'] for r in rows})==len(ids) and all(r['tenant']==r['auditTenant'] and r['state']=='COMPLETED' and r['result']=='VALID' for r in rows),'H3_QUEUE_EFFECT_OR_TENANT_VIOLATION')
    events=sorted([(float(r['started']),1) for r in rows]+[(float(r['finished']),-1) for r in rows]);active=0;peak=0
    for _,change in events:active+=change;peak=max(peak,active)
    require(0<peak<=2,'H3_WORKER_CONCURRENCY_UNBOUNDED')
    failures=[]
    for offset,mode in enumerate(('ONCE','ALWAYS_FAIL','TIMEOUT'),200):
        q=str(uuid.uuid4());resource,document,sha=seeds[0];code,_=api(session,'/__test/job-admin',{'action':'ENQUEUE_FAULT','queue':q,'resource':resource,'document':document,'sha256':sha,'offset':offset,'mode':mode,'failures':1});require(code==200,'H3_FAILURE_SETUP')
        value=wait(lambda:next(r for r in state()['queue'] if r['id']==q),lambda r:r['state'] in ('COMPLETED','FAILED'),'H3_RETRY_EXHAUSTION_NOT_BOUNDED',30)
        require(value['attempts']==(2 if mode=='ONCE' else 3) and value['state']==('COMPLETED' if mode=='ONCE' else 'FAILED'),'H3_RETRY_POLICY')
        failures.append({'mode':mode,'queue':value})
    restart=session.restart();after=state();require(all(any(r['queue']==q for r in after['results']) for q in ids) and life.history(lab.container)==history,'H3_RESTART_LOST_WORKER_RESULTS')
    proof={'scenario':'workerCapacity','result':'PASS','initialPending':pending,'explicitOccurrences':len(ids),'elapsedIncludingStartupSeconds':elapsed,'observedCompletionsPerSecond':len(ids)/elapsed,'rows':rows,'maximumObservedConcurrentClaims':peak,'retryExperiments':failures,'restart':restart,'resources':sampler.result(),'executionModel':'AT_LEAST_ONCE; UNIQUE_FENCED_TERMINAL_EFFECT','queueLimit':'NO_APPROVED_PENDING_OCCURRENCE_BOUND; NOT_CLAIMED_BOUNDED'}
    session.close()
    # Exercise the existing two-JVM H2 assertions without reimplementing them.
    web=lab.start();h2.workers(lab,web,lab.resources[0]);require(len(lab.rows)==3,'H3_MISSING_H2_FENCING')
    return lab.start(),proof


def admitted_create(lab,session):
    profile=PROFILE['admittedCreate'];rows=[];before=lab.counts();results=[];start=time.monotonic()
    for round in range(profile['rounds']):
        scheduled=start+round*profile['roundIntervalSeconds'];remaining=scheduled-time.monotonic()
        if remaining>0:time.sleep(remaining) # Declared offered-load pacing, outside measured latency.
        def call(i):
            key='h3-paced-'+str(round)+'-'+str(i);payload={'title':'H3 policy-admitted '+key,'summary':'H3 paced native rate policy','idempotencyKey':key}
            r=request(session,lab.create['path'],payload,token(i));require(r['status']==200,'H3_PACED_CREATE_NOT_ADMITTED:'+str(r));return i,key,r
        with ThreadPoolExecutor(max_workers=4) as pool:
            for i,key,r in pool.map(call,range(4)):
                rows.append({k:v for k,v in r.items() if k!='value'}|{'operation':'create','disposition':'SUCCESS','round':round,'client':i,'scheduled':scheduled});results.append({'resource':r['value']['resourceId'],'key':key,'client':i})
    after=lab.counts();require(after[lab.table]==before[lab.table]+len(rows) and after['acp_audit']==before['acp_audit']+len(rows) and after['acp_idempotency']==before['acp_idempotency']+len(rows),'H3_PACED_DUPLICATE_EFFECT')
    for result in results:require(lab.ownership(result['resource'])==dict(zip(('tenant','subject'),principal(result['client']))),'H3_PACED_OWNER')
    return {'scenario':'policyAdmittedCreate','result':'PASS','raw':rows,'summary':aggregate(rows,time.monotonic()-start),'correctness':{'cases':len(rows),'duplicates':0,'tenantOwnership':'EXACT'},'pacing':profile}


def pool_pressure(lab,session):
    session.close();session=lab.start(pool=2);before=lab.counts();key='h3-pool-';lab.trigger(lab.doc,True)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            with lab.gate(BEFORE):
                futures=[pool.submit(request,session,lab.documents_path+'/upload',h2.upload(lab.resources[i],key+str(i),lab.raw),token(i),multipart=True) for i in range(4)]
                lab.blocked(BEFORE,2)
                rejected=wait(lambda:[f.result() for f in futures if f.done()],lambda r:len(r)>=2,'H3_POOL_ACQUISITION_NOT_BOUNDED',6)
                require(all(r['status'] in (500,503) for r in rejected),'H3_WRONG_POOL_REJECTION:'+str(rejected))
                with __import__('urllib.request',fromlist=['urlopen']).urlopen(__import__('urllib.request',fromlist=['Request']).Request('http://127.0.0.1:'+str(session.backend_port)+'/__test/h3-resources',headers={'Authorization':'Bearer browser-authorized'}),timeout=2) as response:resources=json.load(response)
                require(resources['maximum']==2 and resources['active']==2 and resources['acquisitionTimeoutMs']==750,'H3_POOL_CONFIGURATION')
            responses=[f.result(timeout=12) for f in futures]
        require(sum(r['status']==200 for r in responses)==2 and lab.counts()[lab.doc]==before[lab.doc]+2,'H3_POOL_PARTIAL_PUBLICATION')
    finally:lab.trigger(lab.doc,False)
    # Explicit recovery, never hidden retry: one replay per declared operation.
    recovered=[lab.checked(session,lab.documents_path+'/upload',h2.upload(lab.resources[i],key+str(i),lab.raw),i,multipart=True) for i in range(4)]
    require(len({r['documentId'] for r in recovered})==4 and lab.counts()[lab.doc]==before[lab.doc]+4 and lab.counts()['acp_audit']==before['acp_audit']+4,'H3_POOL_RECOVERY_DUPLICATION')
    proof={'scenario':'poolPressure','result':'PASS','configuration':resources,'responses':[{k:v for k,v in r.items() if k!='value'} for r in responses],'explicitRecoveryRequests':4,'duplicates':0,'limitation':'CURRENT_RESOURCE_EXHAUSTION_RESPONSE_IS_GENERIC_500; NO_APPROVED_503_RETRY_CONTRACT'}
    session.close();return lab.start(),proof


def interrupted_uploads(lab,session,*,kill):
    label='kill' if kill else 'shutdown';key='h3-'+label+'-';before=lab.counts();history=life.history(lab.container);lab.trigger(lab.doc,True)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            with lab.gate(BEFORE):
                futures=[pool.submit(request,session,lab.documents_path+'/upload',h2.upload(lab.resources[i],key+str(i),lab.raw),token(i),multipart=True) for i in range(4)]
                lab.blocked(BEFORE,4)
                pid=session.process.pid
                if kill:death=lab.kill(session)
                else:session.process.terminate();death={'pid':pid,'signal':'SIGTERM'}
            responses=[f.result(timeout=15) for f in futures]
        code=session.process.wait(timeout=20);require(code==-9 if kill else code in (0,143,-15),'H3_SHUTDOWN_EXIT')
        committed=documents(lab,key);require(len({r['id'] for r in committed})==len(committed)<=4,'H3_INTERRUPTION_DUPLICATE')
        outcomes=[{'client':i,'status':r['status'],'transport':r['error'],'databaseOutcome':'COMMITTED' if any(d['resource']==lab.resources[i] for d in committed) else 'ROLLED_BACK','acknowledged':r['status']==200} for i,r in enumerate(responses)]
        require(all(not o['acknowledged'] or o['databaseOutcome']=='COMMITTED' for o in outcomes),'H3_ACK_WITHOUT_COMMIT')
    finally:lab.trigger(lab.doc,False)
    session.close();begin=time.monotonic();session=lab.start();recovered=[lab.checked(session,lab.documents_path+'/upload',h2.upload(lab.resources[i],key+str(i),lab.raw),i,multipart=True) for i in range(4)]
    require(lab.counts()[lab.doc]==before[lab.doc]+4 and len({r['documentId'] for r in recovered})==4 and life.history(lab.container)==history and lab.counts()['acp_audit']==before['acp_audit']+4,'H3_RESTART_DUPLICATION_OR_MIGRATION_DRIFT')
    for r in recovered:require(r['sha256']==hashlib.sha256(lab.raw).hexdigest(),'H3_RESTART_DOCUMENT_CORRUPTION')
    return session,{'scenario':'processKillUnderLoad' if kill else 'shutdownUnderLoad','result':'PASS','death':death,'exit':code,'outcomes':outcomes,'explicitRecoveryRequests':4,'duplicates':0,'recoverySeconds':time.monotonic()-begin,'migrationHistoryExact':True}


def client_timeout(lab,session):
    key='h3-client-timeout';before=lab.counts();lab.trigger(lab.doc,True)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            with lab.gate(BEFORE):
                future=pool.submit(request,session,lab.documents_path+'/upload',h2.upload(lab.resources[0],key,lab.raw),token(0),multipart=True,timeout=.5)
                lab.blocked(BEFORE);pid=lab.db.data("SELECT to_json(pid) FROM pg_locks WHERE locktype='advisory' AND objid="+str(BEFORE)+" AND NOT granted");value=future.result(timeout=3);require(value['error'] is not None and value['status'] is None,'H3_CLIENT_TIMEOUT_NOT_OBSERVED')
        wait(lambda:lab.db.data("SELECT to_json(count(*)) FROM pg_stat_activity WHERE pid="+str(pid)+" AND xact_start IS NOT NULL"),lambda n:n==0,'H3_TIMEOUT_TRANSACTION_NOT_FINISHED',5)
        observed=documents(lab,key);require(len(observed)<=1,'H3_TIMEOUT_DUPLICATE_EFFECT')
    finally:lab.trigger(lab.doc,False)
    replay=lab.checked(session,lab.documents_path+'/upload',h2.upload(lab.resources[0],key,lab.raw),multipart=True)
    require((not observed or replay['documentId']==observed[0]['id']) and lab.counts()[lab.doc]==before[lab.doc]+1,'H3_TIMEOUT_REPLAY_DUPLICATE')
    return {'scenario':'clientTimeout','result':'PASS','response':{k:v for k,v in value.items() if k!='value'},'outcomeAfterIndependentObservation':'COMMITTED_ACK_LOST' if observed else 'ROLLED_BACK','replayedDocument':replay,'duplicates':0,'interpretation':'CLIENT_TIMEOUT_DOES_NOT_PROVE_SERVER_CANCELLATION'}


def scope_limit(lab,session):
    limit=json.loads((lab.root/'backend/src/main/resources/acp-background-job.json').read_bytes())['maximumDocuments']
    for i in (0,1):
        tenant=principal(i)[0];count=lab.db.data("SELECT to_json(count(*)) FROM "+lab.doc+" WHERE tenant=convert_to('"+tenant+"','UTF8')")
        for index in range(max(0,limit+1-count)):lab.checked(session,lab.documents_path+'/upload',h2.upload(lab.resources[i],'h3-over-scope-'+str(i)+'-'+str(index),lab.raw),i,multipart=True)
    # The earlier capacity run advanced next_slot. Use the existing disposable
    # MISSED provisioning hook so this test actually exercises a due schedule.
    require(api(session,'/__test/job-admin',{'action':'MISSED'})[0]==200,'H3_LIMIT_SCHEDULE_SETUP')
    session.close();session=lab.start(workers=True)
    try:
        def state():
            code,value=api(session,'/__test/job-state');require(code==200,'H3_LIMIT_STATE');return value
        result=wait(state,lambda s:len(s['schedule'])==2 and all(r['error']=='SCOPE_LIMIT_EXCEEDED' for r in s['schedule']),'H3_SUPPORTED_SCOPE_NOT_ENFORCED',10)
        return {'scenario':'workerScopeLimit','result':'PASS','unchangedMaximumDocumentsPerTenant':limit,'schedule':result['schedule'],'disposition':'UNSUPPORTED_POPULATION_REJECTED; CAPACITY_NOT_EXPANDED'}
    finally:session.close()


def query_plans(lab):
    report=lab.report;d=lab.documents_meta
    where=report['whereSQL'].replace('?',"convert_to('tenant-one','UTF8')",1).replace('?',"convert_to('fixture:operator','UTF8')",1)
    queries={'tenantReport':"SELECT "+report['selectSQL']+' FROM '+report['table']+' WHERE '+where+' ORDER BY '+report['defaultOrderSQL']+' LIMIT 20 OFFSET 0',
             'documentMetadata':"SELECT id,sha256,size FROM "+lab.doc+" WHERE tenant=convert_to('tenant-one','UTF8') AND resource=convert_to('"+lab.resources[0]+"','UTF8') AND id='"+lab.seeds[0]['documentId']+"'::uuid",
             'queueCandidate':"SELECT id FROM "+PREFIX+"_queue WHERE job='JOB-INTEGRITY' AND tenant=convert_to('tenant-one','UTF8') AND occurrence<=floor(extract(epoch FROM clock_timestamp()))::bigint AND attempts<3 AND ((state IN ('PENDING','RETRY') AND available_at<=clock_timestamp()) OR (state='RUNNING' AND lease_until<clock_timestamp())) ORDER BY available_at,id FOR UPDATE SKIP LOCKED LIMIT 1"}
    return {name:{'sql':sql,'sqlSHA256':hashlib.sha256(sql.encode()).hexdigest(),'plan':lab.db.data('EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON) '+sql)} for name,sql in queries.items()}
