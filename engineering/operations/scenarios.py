"""Actual H5 authentication plus H6 operational experiments; no expected-state stubs."""
import concurrent.futures,json,os,re,secrets,signal,time,types,urllib.request,urllib.error,uuid
from pathlib import Path
from engineering.identity import scenarios as h5
from engineering.operations.lab import OperationalLab
from engineering.operations.fixture import PRESSURE
from engineering.source_intelligence.model import require,sha,encode
from engineering.reference_application import lifecycle as life
from engineering.jobs.scenarios import wait
from engineering.jobs.fixture import PREFIX
from engineering.capacity import workload,metrics as h3metrics
from engineering.reliability.concurrency import upload
from engineering.generator_builds.runtime import docker

REQUIRED={'healthyStartup','normalAuthenticatedOperations','readOnlyHealth','metricsProtected','postgresUnavailable','postgresRestored','poolExhausted','poolRecovered','identityMaterialMissing','identityMaterialSubstituted','identityRecovered','optionalWorkerDisabled','workerDraining','workerStopped','queueNotDraining','workerRecovered','liveWorkerStall','workerStallRecovered','invalidConfiguration','boundedTelemetry','secretChange','applicationRestart','cleanShutdown','h5AuthenticationPreserved'}

def http(server,path,token=None,body=None,headers=None):
    h=dict(headers or {})
    if token is not None:h['Authorization']='Bearer '+token
    raw=None if body is None else json.dumps(body).encode()
    if raw is not None:h['Content-Type']='application/json'
    begin=time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(server.backend_port)+path,data=raw,headers=h),timeout=5) as r:
            data=r.read();value=json.loads(data) if 'json' in r.headers.get('Content-Type','') else data;return {'status':r.status,'value':value,'correlation':r.headers.get('X-ACP-Correlation'),'milliseconds':(time.monotonic()-begin)*1000}
    except urllib.error.HTTPError as e:
        raw=e.read()
        try:value=json.loads(raw)
        except ValueError:value=None
        return {'status':e.code,'value':value,'correlation':e.headers.get('X-ACP-Correlation'),'milliseconds':(time.monotonic()-begin)*1000}
    except (OSError,TimeoutError):return {'status':None,'value':None,'correlation':None,'milliseconds':(time.monotonic()-begin)*1000}

def telemetry(logs):
    events=[]
    for p in Path(logs).glob('demo-backend-*.log'):
        for line in p.read_text().splitlines():
            try:record=json.loads(line);message=record.get('message','')
            except ValueError:continue
            if 'ACP_OPERATIONAL ' in message:
                event=json.loads(message.split('ACP_OPERATIONAL ',1)[1]);require(set(event)=={'contract','classificationContract','event','correlation','outcome','origin','originRevision'},'H6_TELEMETRY_SCHEMA');require(re.fullmatch('[0-9a-f-]{36}',event['correlation']) is not None,'H6_CORRELATION');events.append(event)
    return events

def exercise(root,folder,container,issuer):
    folder.mkdir(mode=0o700);proof=[]
    class BoundLab(OperationalLab):
        def __init__(self,*args):super().__init__(*args);issuer.tokens.append(self.metrics_key)
    # Execute the unchanged H5 cryptographic suite against the H6 generated app.
    h5run=types.FunctionType(h5.exercise.__code__,{**vars(h5),'Lab':BoundLab},'h5_on_h6');crypto=h5run(root,folder/'identity',container,issuer)
    config,keyfile=h5.configuration(issuer,folder,('h5-k1','h5-k2'),'operational-identity');previous={k:os.environ.get(k) for k in ('ACP_IDENTITY_CONFIG','ACP_IDENTITY_CONFIG_SHA256')};os.environ.update(ACP_IDENTITY_CONFIG=str(config),ACP_IDENTITY_CONFIG_SHA256=sha(config.read_bytes()))
    lab=BoundLab(root,folder/'operations',container);server=None;paused=False;original_keys=keyfile.read_bytes();counter=0
    def record(name,**actual):proof.append({'experiment':name,'actual':actual});life.save(folder/'experiments.json',proof)
    def checked(path,token=None,body=None,status=200,headers=None):
        r=http(server,path,token,body,headers);require(r['status']==status,'H6_HTTP:'+path+':'+str(r['status']));return r
    def health(group='readiness',status=200):
        r=checked('/actuator/health/'+group,status=status);require(set(r['value'])=={'status'} and r['value']['status']==('UP' if status==200 else 'DOWN'),'H6_HEALTH_DETAIL_OR_FALSE_STATE');return {k:v for k,v in r.items() if k!='value'}|{'health':r['value']['status']}
    def observe(group,up):return wait(lambda:http(server,'/actuator/health/'+group),lambda r:r['status']==(200 if up else 503),'H6_HEALTH_TRANSITION:'+group,12)
    def metric(token_override=None,key_override=None):
        return checked('/internal/operations/metrics',token if token_override is None else token_override,headers={'X-ACP-Metrics-Key':lab.metrics_key if key_override is None else key_override})['value']
    def admin(action,**extra):return checked('/__test/job-admin',token,{'action':action,**extra})['value']
    def state():return checked('/__test/job-state',token)['value']
    def enqueue(mode='NONE'):
        nonlocal counter
        counter+=1;q=str(uuid.uuid4());admin('ENQUEUE_FAULT',queue=q,resource=resources[0],document=documents[0]['documentId'],sha256=documents[0]['sha256'],offset=600+counter,mode=mode);return q
    try:
        server=lab.start();token=issuer.obtain(claims={'sid':'h6-interactive-one','auth_time':int(time.time())});other=issuer.obtain(subject='fixture:reporter-two',tenant='tenant-two',claims={'sid':'h6-interactive-two','auth_time':int(time.time())})
        record('h5AuthenticationPreserved',requiredNegatives=len(crypto['requiredNegatives']),cases=len(crypto['outcomes']),nativeSessions=crypto['sessionRegressions']);record('healthyStartup',pid=server.process.pid,readiness=health(),liveness=health('liveness'),database=lab.identity)
        record('optionalWorkerDisabled',worker=health('worker'),metricsWorkersEnabled=metric()['workersEnabled'])
        before=lab.state()
        for _ in range(16):health();health('dependencies');health('identity');health('worker')
        require(lab.state()==before,'H6_HEALTH_MUTATED_DATABASE');record('readOnlyHealth',probes=64,beforeSHA256=sha(encode(before)),afterSHA256=sha(encode(lab.state())))
        denied=[http(server,'/internal/operations/metrics'),http(server,'/internal/operations/metrics',token),http(server,'/internal/operations/metrics',token,headers={'X-ACP-Metrics-Key':'wrong'})];require([r['status'] for r in denied]==[401,403,403],'H6_METRICS_PUBLIC_OR_UNPROTECTED');record('metricsProtected',denials=[r['status'] for r in denied],authenticated=200)
        # New business fixtures use genuine issuer credentials and native handlers.
        resources=[];documents=[];raw=('H6-private-document-'+secrets.token_hex(32)).encode();issuer.tokens.append(raw.decode())
        for i,t in enumerate((token,other,token,other)):
            made=checked(lab.create['path'],t,{'title':'H6 operational '+str(i),'summary':'H6 bounded fixture','idempotencyKey':'h6-seed-'+str(i)})['value'];resources.append(made['resourceId'])
            status,d,_=h5.call(server,lab.documents_path+'/upload',t,upload(made['resourceId'],'h6-doc-'+str(i),raw),multipart=True);require(status==200,'H6_DOCUMENT_SETUP');documents.append(d)
        record('normalAuthenticatedOperations',newCases=4,documents=4,tenants=2,source='NATIVE_CRYPTOGRAPHIC_HTTP')
        # Actual service freeze: no database is replaced, recreated or fabricated.
        committed=lab.state();docker('pause',container);paused=True
        try:
            require(docker('inspect','--format','{{.State.Paused}}',container)=='true','H6_DATABASE_NOT_PAUSED');observe('readiness',False);record('postgresUnavailable',containerPaused=True,readiness=health(status=503),liveness=health('liveness'))
        finally:docker('unpause',container);paused=False
        observe('readiness',True);require(lab.state()==committed,'H6_DATABASE_FAILURE_CORRUPTION');record('postgresRestored',readiness=health(),reportStatus=checked(lab.report['path'],token,{})['status'])
        # Exhaust the actual Hikari pool with bounded test-only SELECT locks.
        stable=lab.state()
        with lab.gate(PRESSURE):
            require(checked('/__test/h6-pressure',token,{})['value']['submitted']==34,'H6_PRESSURE_SETUP');lab.blocked(PRESSURE,34)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                request=pool.submit(http,server,lab.report['path'],token,{})
                observe('readiness',False);probe=health(status=503);live=health('liveness');rejected=request.result(timeout=5);require(rejected['status']==500,'H6_ACQUISITION_FAILURE_NOT_OBSERVED')
            require(lab.state()==stable,'H6_PRESSURE_PUBLISHED_EFFECT');record('poolExhausted',actualWaitingPostgresLocks=lab.lock_count(PRESSURE,False),readiness=probe,liveness=live,requestStatus=rejected['status'])
        observe('readiness',True);recovered=metric();require(recovered['poolActivePeak']==34,'H6_POOL_PRESSURE_NOT_MEASURED');require(lab.state()==stable,'H6_POOL_RECOVERY_CHANGED_DATA');record('poolRecovered',readiness=health(),poolActivePeak=recovered['poolActivePeak'],poolAwaitingPeak=recovered['poolAwaitingPeak'])
        keyfile.rename(keyfile.with_suffix('.withheld'))
        try:observe('readiness',False);record('identityMaterialMissing',readiness=health(status=503),liveness=health('liveness'),requestStatus=checked(lab.report['path'],token,{},status=401)['status'])
        finally:keyfile.with_suffix('.withheld').rename(keyfile)
        keyfile.write_bytes(encode(issuer.jwks(('untrusted',))))
        try:record('identityMaterialSubstituted',readiness=health(status=503),requestStatus=checked(lab.report['path'],token,{},status=401)['status'])
        finally:keyfile.write_bytes(original_keys)
        observe('readiness',True);record('identityRecovered',readiness=health(),report=checked(lab.report['path'],token,{})['status'])
        admin('INIT');server.close();server=lab.start(workers=True);observe('readiness',True)
        drained=wait(state,lambda s:len(s['results'])>=len(documents)+2 and all(q['state']=='COMPLETED' for q in s['queue']),'H6_REAL_WORKER_DRAIN',30);require(len({r['audit_id'] for r in drained['results']})==len(drained['results']),'H6_DUPLICATE_JOB_EFFECT');record('workerDraining',worker=health('worker'),completed=len(drained['results']),uniqueAudits=len(drained['results']))
        checked('/__test/h2-pause-claims',token,{})
        observe('worker',False);record('workerStopped',worker=health('worker',503),readiness=health(status=503),running=metric()['workerRunning'])
        q=enqueue();wait(lambda:metric()['queue']['oldestSeconds'],lambda age:age>=lab.stall,'H6_PENDING_AGE',8);s=next(x for x in state()['queue'] if x['id']==q);require(s['state']=='PENDING' and s['attempts']==0,'H6_QUEUED_WORK_NOT_STALLED');record('queueNotDraining',pendingAttempts=0,oldestSeconds=metric()['queue']['oldestSeconds'],readiness=health(status=503))
        server.close();lab.stall=1;server=lab.start(workers=True);wait(state,lambda s:any(r['queue']==q for r in s['results']),'H6_WORKER_RECOVERY',20);observe('readiness',True);record('workerRecovered',readiness=health(),workerRunning=metric()['workerRunning'])
        q=enqueue('HOLD_FIRST');wait(state,lambda s:any(c['queue']==q and c['entered'] for c in s['controls']),'H6_LIVE_WORKER_GATE',10)
        try:
            observe('worker',False);m=metric();require(m['workerRunning'] and m['queue']['oldestSeconds']>=1,'H6_LIVE_STALL_NOT_REAL');record('liveWorkerStall',workerRunning=True,oldestSeconds=m['queue']['oldestSeconds'],worker=health('worker',503))
        finally:admin('RELEASE',queue=q)
        wait(state,lambda s:any(r['queue']==q and r['status']=='VALID' for r in s['results']),'H6_STALL_RECOVERY',20);observe('readiness',True);record('workerStallRecovered',readiness=health())
        # H3's existing real mixed workload, with genuine signed client tokens.
        server.close();lab.stall=3;server=lab.start();lab.resources=resources;lab.raw=raw
        class SignedSampler(h3metrics.Sampler):pass
        def signed_request(*args,**kwargs):kwargs['headers']={'Authorization':'Bearer '+token};return urllib.request.Request(*args,**kwargs)
        proxy=types.SimpleNamespace(request=types.SimpleNamespace(Request=signed_request,urlopen=urllib.request.urlopen))
        SignedSampler.collect=types.FunctionType(h3metrics.Sampler.collect.__code__,{**vars(h3metrics),'urllib':proxy},'signed_resource_collect')
        profile={**workload.PROFILE,'measuredCyclesPerClient':1};run=types.FunctionType(workload.run_level.__code__,{**vars(workload),'PROFILE':profile,'token':lambda i:(token,other)[i%2],'Sampler':SignedSampler},'h3_signed_operational_level')
        event_before=metric()['eventEmissionNanos'];measurements=run(lab,server,4,'h6');event_after=metric()['eventEmissionNanos'];require(event_after>event_before,'H6_EVENT_TIMING_NOT_OBSERVED');life.save(folder/'mixed-workload.json',measurements)
        before=metric();keys=set(before)
        for i in range(96):checked('/h6-test-unmatched-'+str(i),token,status=404)
        after=metric();require(set(after)==keys and len(keys)<=256,'H6_UNBOUNDED_METRIC_LABELS');record('boundedTelemetry',metricNames=len(keys),requests=measurements['summary']['population'],maxRSSBytes=measurements['resources']['maxRSSBytes'],requestLatency=measurements['summary'],logRateLimit=after['logEventsPerSecondLimit'],droppedEvents=after['droppedOperationalEvents'],measuredEventEmissionNanos=event_after-event_before,overheadScope='SUM_OF_EVENT_EMISSION_WALL_TIMES_INCLUDING_LOG_SINK; NOT_BASELINE_SPEEDUP_OR_SLO')
        # Secret reference stays fixed while actual secret possession changes.
        old_key=lab.metrics_key;server.close();lab.metrics_key=secrets.token_urlsafe(32);issuer.tokens.append(lab.metrics_key);server=lab.start();checked('/internal/operations/metrics',token,status=403,headers={'X-ACP-Metrics-Key':old_key});metric();record('secretChange',oldCapabilityStatus=403,newCapabilityStatus=200,semanticIdentityChanged=False)
        # No invalid configuration may become ready.
        server.close();rejections=[]
        for label,changes,extra,badpin in [('production',{'runtimeMode':'production'},{},False),('poolZero',{'poolConnections':0},{},False),('workerConcurrency',{'workerConcurrency':3},{},False),('sessionOverride',{'sessionPolicy':'DISABLED'},{},False),('profileHash',{}, {},True),('traceLogging',{}, {'LOGGING_LEVEL_ORG_SPRINGFRAMEWORK_SECURITY':'TRACE'},False),('productionEnvironment',{}, {'ACP_RUNTIME_MODE':'production'},False)]:
            lab.profile_changes=changes;lab.extra_environment=extra;lab.bad_profile_pin=badpin
            try:lab.start()
            except ValueError as e:require(str(e)=='DEMO_BACKEND_EXIT','H6_STARTUP_REJECTION_KIND');rejections.append(label)
            else:raise AssertionError('H6_UNSAFE_STARTUP:'+label)
        require(len(rejections)==7,'H6_MISSING_CONFIGURATION_REJECTION');record('invalidConfiguration',rejected=rejections)
        lab.profile_changes={};lab.extra_environment={};lab.bad_profile_pin=False;server=lab.start();before=lab.state();pid=server.process.pid;server.close();require(server.process.poll() is not None,'H6_OLD_PROCESS_SURVIVED');server=lab.start();require(server.process.pid!=pid and lab.state()==before,'H6_RESTART_CHANGED_COMMITTED_DATA');checked(lab.report['path'],token,{});record('applicationRestart',oldPid=pid,newPid=server.process.pid,committedStatePreserved=True,readiness=health())
        server.close();require(server.process.poll() is not None and http(server,'/actuator/health/liveness')['status'] is None,'H6_SHUTDOWN_STILL_ACCEPTING');events=telemetry(lab.logs);require(any(e['event']=='SHUTDOWN' and e['outcome']=='STOPPED' for e in events),'H6_SHUTDOWN_TELEMETRY_MISSING');record('cleanShutdown',processExit=server.process.returncode,portNoLongerServing=True,shutdownEvents=sum(e['event']=='SHUTDOWN' for e in events))
        required_events={'AUTHENTICATION','AUTHORIZATION','DATABASE','TRANSACTION','IDEMPOTENCY','DOCUMENT','WORKFLOW','WORKER','READINESS','STARTUP','MIGRATION','RECOVERY','SHUTDOWN'}
        # H5's negative cases provide authorization-denial telemetry separately.
        all_events=events+telemetry(folder/'identity/runtime');require(required_events<={e['event'] for e in all_events},'H6_MISSING_OPERATIONAL_EVENT');life.save(folder/'structured-events.json',all_events)
        require(REQUIRED=={p['experiment'] for p in proof},'H6_MISSING_EXPERIMENT')
        return {'experiments':proof,'h5':crypto,'configurationRejections':rejections,'structuredEvents':len(all_events),'eventKinds':sorted({e['event'] for e in all_events}),'businessWorkload':measurements['summary'],'workerIdentity':'EXISTING_EXPLICIT_SERVICE_CONTEXT; NO_INTERACTIVE_JWT; CRYPTOGRAPHIC_SERVICE_ENROLLMENT_NOT_APPROVED','historicalCreate500':'UNRESOLVED_NOT_CLAIMED_FIXED','scope':'QUALIFICATION_ONLY'}
    finally:
        if paused:docker('unpause',container)
        if keyfile.exists():keyfile.write_bytes(original_keys)
        lab.close()
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
