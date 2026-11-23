"""Real H5 HTTP boundaries and finite, one-submit CREATE observations."""
import json,time,uuid,urllib.request,urllib.error,concurrent.futures,re,threading
from pathlib import Path
from engineering.disaster_recovery.scenarios import authenticated_lab,tokens,audit_counts
from engineering.disaster_recovery import backup as db
from engineering.reliability.concurrency import upload
from engineering.source_intelligence.model import require,sha,encode
from engineering.reference_application import lifecycle as life
from phase6_reference_tests import seed_sql
from engineering.http_reliability import diagnostics as causal
WORKLOAD=json.loads((Path(__file__).parent/'workload.json').read_bytes())

def request(server,path,token=None,body=None,*,method=None,content_type='application/json',headers=None):
    h=dict(headers or {});raw=body if isinstance(body,bytes) else None if body is None else json.dumps(body).encode()
    if token is not None:h['Authorization']='Bearer '+token
    if raw is not None:h['Content-Type']=content_type
    started=time.monotonic_ns()
    try:
        response=urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(server.backend_port)+path,data=raw,headers=h,method=method),timeout=20)
    except urllib.error.HTTPError as error:response=error
    except (OSError,TimeoutError) as error:return {'status':None,'value':None,'correlation':None,'startedMonotonicNs':started,'finishedMonotonicNs':time.monotonic_ns(),'transportErrorClass':type(error).__name__}
    with response:
        data=response.read();value=json.loads(data) if 'json' in response.headers.get('Content-Type','') else data
        return {'status':response.status,'value':value,'correlation':response.headers.get('X-ACP-Correlation'),'startedMonotonicNs':started,'finishedMonotonicNs':time.monotonic_ns()}

def public_response(r):
    value=r['value'];safe={k:value[k] for k in ('code','category','retryable') if k in value} if isinstance(value,dict) else None
    return {k:v for k,v in r.items() if k!='value'}|{'envelope':safe,'responseSHA256':sha(encode(value)) if not isinstance(value,bytes) else sha(value)}

def observations(logs):
    events=[];exceptions=[];diagnostics=[]
    for p in Path(logs).glob('demo-backend-*.log'):
        for line in p.read_text().splitlines():
            if 'H9_EXCEPTION:' in line:
                value=line.split('H9_EXCEPTION:',1)[1].strip().split(':');require(len(value)==3 and re.fullmatch('[0-9a-f-]{36}',value[0]) is not None,'H9_EXCEPTION_CORRELATION');exceptions.append({'correlation':value[0],'exceptionClass':value[1],'sqlState':None if value[2] in ('','null') else value[2]})
            if 'H9_DIAGNOSTIC:' in line:diagnostics.append(json.loads(line.split('H9_DIAGNOSTIC:',1)[1]))
            try:
                parsed=json.loads(line);message=parsed.get('message','')
                if 'ACP_OPERATIONAL ' in message:events.append(json.loads(message.split('ACP_OPERATIONAL ',1)[1]))
            except ValueError:pass
    return {'events':events,'exceptions':exceptions,'requests':diagnostics}

def check_no_business_writes(before,after):
    require(before==after,'H9_NEGATIVE_BUSINESS_WRITE')

def exercise(root,folder,resources,issuers,*,successor,diagnostics=True):
    folder=Path(folder);folder.mkdir(mode=0o700);rows=[];attempts=[];boundary=time.monotonic();active=[]
    with db.new_database(active,resources) as container,authenticated_lab(root,folder/'signed',container,issuers) as (lab,issuer):
        server=lab.start();lab.db.run(';'.join(seed_sql('case-management')[:2]));auth=tokens(issuer,'h9-'+uuid.uuid4().hex)
        def check(name,path,token=auth[0],body=None,expected=200,**kwargs):
            before=audit_counts(lab);r=request(server,path,token,body,**kwargs);require(r['status']==expected,'H9_HTTP:'+name+':'+str(r['status']));require(re.fullmatch('[0-9a-f-]{36}',r['correlation'] or '') is not None,'H9_MISSING_CORRELATION');after=audit_counts(lab)
            if expected>=400:check_no_business_writes(before,after)
            rows.append({'case':name,'expected':expected,'response':public_response(r),'businessBefore':before,'businessAfter':after});life.save(folder/'http-results.json',rows);return r['value']
        check('initialize','/__test/reset',body={});check('secondTenant','/__test/report-negative',body={})
        missing=404 if successor else 500
        untrusted=str(uuid.uuid4());check('unknownAPI','/api/h9-unknown',expected=missing,headers={'X-ACP-Correlation':untrusted});require(rows[-1]['response']['correlation']!=untrusted,'H9_CLIENT_CORRELATION_TRUSTED')
        check('unknownStatic','/assets/h9-missing.js',expected=missing)
        check('anonymousUnknown','/api/h9-unknown',token=None,expected=401)
        if not successor:
            seen=observations(lab.logs);require(any(x['exceptionClass']=='org.springframework.web.servlet.resource.NoResourceFoundException' for x in seen['exceptions']),'H9_BASELINE_EXCEPTION_MISSING')
            require(all(r['response']['envelope']=={'code':'INTERNAL_ERROR','category':'INTERNAL','retryable':False} for r in rows if r['case'] in ('unknownAPI','unknownStatic')),'H9_BASELINE_ENVELOPE')
            life.save(folder/'diagnostics.json',seen);return {'scope':'QUALIFICATION_ONLY','REL02':'BASELINE_REPRODUCED','http':rows,'observations':seen,'database':lab.identity}
        check('wrongMethod',lab.create['path'],expected=500,method='GET')
        check('malformedJSON',lab.create['path'],body=b'{',expected=422)
        check('invalidBusinessPayload',lab.create['path'],body={'idempotencyKey':'h9-invalid'},expected=400)
        check('unsupportedMedia',lab.create['path'],body=b'no json',content_type='text/plain',expected=500)
        check('missingParameter','/__test/h9-required',expected=500)
        check('anonymousCreate',lab.create['path'],token=None,body={},expected=401)
        check('roleWithoutPermission',lab.create['path'],token=issuer.obtain(subject='other-owner',claims={'roles':['ADMIN']}),body={'title':'Denied','summary':'None','idempotencyKey':'h9-denied'},expected=403)
        check('unexpectedException','/__test/h9-unexpected',expected=500)
        check('wrappedMissingException','/__test/h9-wrapped',expected=500)
        check('unregisteredMissingSubclass','/__test/h9-subclass',expected=500)
        case=check('authorizedCreate',lab.create['path'],body={'title':'H9 synthetic case','summary':'H9 synthetic bounded input','idempotencyKey':'h9-positive'})
        case2=check('otherTenantCreate',lab.create['path'],token=auth[1],body={'title':'H9 synthetic case','summary':'H9 synthetic bounded input','idempotencyKey':'h9-positive-two'})
        raw,kind=upload(case['resourceId'],'h9-document',b'H9 exact document\n');document=check('uploadDocument',lab.documents_path+'/upload',body=raw,content_type=kind)
        require(check('downloadDocument',lab.documents_path+'/download',body={'resourceId':case['resourceId'],'documentId':document['documentId']})==b'H9 exact document\n','H9_DOCUMENT_BYTES')
        absent=check('missingBusinessResource',lab.documents_path+'/metadata',body={'resourceId':str(uuid.uuid4()),'documentId':str(uuid.uuid4())},expected=404)
        check('crossTenantResource',lab.report['path']+'/history',body={'resourceId':case2['resourceId']},expected=404)
        foreign=check('crossTenantDocument',lab.documents_path+'/metadata',token=auth[1],body={'resourceId':case['resourceId'],'documentId':document['documentId']},expected=404);require(absent==foreign,'H9_RESOURCE_EXISTENCE_DISCLOSURE')
        require(all(r['response']['envelope']=={'code':'RESOURCE_NOT_FOUND','category':'HTTP','retryable':False} for r in rows if r['case'] in ('unknownAPI','unknownStatic')),'H9_ROUTE_CLASSIFICATION')
        require(next(r for r in rows if r['case']=='unexpectedException')['response']['envelope']=={'code':'INTERNAL_ERROR','category':'INTERNAL','retryable':False},'H9_UNEXPECTED_NORMALIZED')
        require(lab.ownership(case['resourceId'])=={'tenant':'tenant-one','subject':'fixture:operator'},'H9_OWNER')
        variants=[];submissions=0
        if diagnostics:
            auth_epoch=int(time.time());pool=34
            for variant in WORKLOAD['variants']:
                require(time.monotonic()-boundary<WORKLOAD['maximumSeconds'],'H9_STUDY_TIMEOUT')
                if variant['restart']:server.close();server=lab.start(pool=variant['pool']);pool=variant['pool']
                require(pool==variant['pool'],'H9_WORKLOAD_PROFILE')
                identities=[issuer.obtain(subject='fixture:operator' if variant.get('singleTenant') or i%2==0 else 'fixture:reporter-two',tenant='tenant-one' if variant.get('singleTenant') or i%2==0 else 'tenant-two',claims={'sid':'h9-'+variant['id']+'-'+str(i),'auth_time':auth_epoch}) for i in range(variant['clients'])]
                if variant['identity']=='SHARED_AUTH_EVENT':identities=[identities[0]]*variant['clients']
                before=audit_counts(lab);batch=[];mutex=threading.Lock();barrier=threading.Barrier(variant['clients'])
                def one(i):
                    if i<variant['clients']:barrier.wait(timeout=10)
                    who=i%variant['clients'];tenant=0 if variant.get('singleTenant') or variant['identity']=='SHARED_AUTH_EVENT' else who%2
                    key='h9-'+variant['id']+'-'+(str(tenant) if variant['keys']=='REUSE_PER_TENANT' else str(i));payload={'title':'H9 synthetic diagnostic','summary':'H9 bounded input','idempotencyKey':key}
                    r=request(server,lab.create['path'],identities[who],payload);record={'variant':variant['id'],'attempt':i,'tenantSHA256':sha(('tenant-one' if tenant==0 else 'tenant-two').encode()),'idempotencyKeySHA256':sha(key.encode()),'response':public_response(r),'resourceSHA256':sha(str(r['value'].get('resourceId')).encode()) if r['status']==200 else None}
                    key_identity=causal.identity(lab.create['operation'],lab.create['revision'],'tenant-one' if tenant==0 else 'tenant-two','fixture:operator' if tenant==0 else 'fixture:reporter-two',key);record['idempotencyIdentitySHA256']=key_identity
                    if r['status']==200:require(lab.ownership(r['value']['resourceId'])=={'tenant':'tenant-one' if tenant==0 else 'tenant-two','subject':'fixture:operator' if tenant==0 else 'fixture:reporter-two'},'H9_DIAGNOSTIC_OWNERSHIP')
                    with mutex:batch.append(record)
                    return record
                # One submission per attempt, no retry or success replacement.
                with causal.database_samples(container) as samples:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=variant['clients']) as executor:list(executor.map(one,range(variant['requests'])))
                submissions+=len(batch);require(submissions<=WORKLOAD['maximumAttempts'],'H9_ATTEMPT_BOUND');after=audit_counts(lab)
                committed=set()
                for attempt in batch:
                    tenant=0 if variant.get('singleTenant') or variant['identity']=='SHARED_AUTH_EVENT' else attempt['attempt']%variant['clients']%2
                    proof=causal.ledger(lab,attempt['idempotencyIdentitySHA256'],'tenant-one' if tenant==0 else 'tenant-two','fixture:operator' if tenant==0 else 'fixture:reporter-two');attempt['database']=proof
                    if attempt['response']['status']==200:require(proof['outcome']=='COMMITTED' and proof['resourceSHA256']==attempt['resourceSHA256'],'H9_ACK_WITHOUT_COMMIT')
                    if proof['outcome']=='COMMITTED':committed.add(attempt['idempotencyIdentitySHA256'])
                new=after['cases']-before['cases'];require(new==len(committed) and after['creates']-before['creates']==new and after['documents']==before['documents'],'H9_DIAGNOSTIC_EFFECTS')
                attempts.extend(sorted(batch,key=lambda r:r['attempt']));variants.append({'workload':variant,'before':before,'after':after,'uniqueCommittedKeys':len(committed),'postgresSamples':samples,'workersEnabled':False,'newCases':new,'unexpectedStatuses':[r['response']['status'] for r in batch if r['response']['status'] not in (200,202,409,429)]});life.save(folder/'create-attempts.json',attempts)
        final=audit_counts(lab);require(final['cases']<=WORKLOAD['maximumNewCases']+3,'H9_DATA_BOUND');seen=observations(lab.logs);correlations={r['response']['correlation'] for r in attempts if r['response']['correlation'] is not None};require(correlations<={r['correlation'] for r in seen['requests']},'H9_DIAGNOSTIC_REQUEST_MISSING')
        result={'scope':'QUALIFICATION_ONLY','REL02':'CORRECTED_IN_H9_ONLY','REL01':'UNRESOLVED_NOT_CAUSALLY_ATTRIBUTED',**causal.classify(attempts,WORKLOAD['variants']),'attempts':attempts,'variants':variants,'maximumAttempts':WORKLOAD['maximumAttempts'],'submissions':submissions,'workloadSHA256':sha(encode(WORKLOAD)),'elapsedSeconds':time.monotonic()-boundary,'http':rows,'observations':seen,'database':lab.identity,'finalCounts':final,'diagnosticLimitations':['Connection acquisition is observed through aggregate Hikari timing/counts and exceptions; not an exact per-connection trace.','H6 transaction/idempotency events plus independent PostgreSQL committed rows; clock/session/DB confounders not eliminated.','No attribution of original H3 execution from later success or analogous failure.','Worker fencing remains independently qualified H2/H7; this study does not alter worker policy.']}
        life.save(folder/'diagnostics.json',seen);life.save(folder/'result.json',result);return result
