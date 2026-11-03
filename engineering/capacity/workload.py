"""Real client-side timings. Normal workloads never hold H2 synchronization gates."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from contextlib import contextmanager
from collections import Counter
from pathlib import Path
import hashlib,json,os,threading,time,urllib.request,urllib.error,uuid
from engineering.reliability import concurrency as h2
from engineering.demo import reference as demo
from engineering.jobs.scenarios import worker_env
from engineering.reference_application import lifecycle as life
from engineering.reference_application.evolution import api
from engineering.source_intelligence.model import require
from engineering.capacity.metrics import Sampler,aggregate

PROFILE=json.loads((Path(__file__).parent/'profile.json').read_bytes())
OPERATIONS=tuple(PROFILE['operations'])


def token(i):return 'browser-h3-'+str(i)
def principal(i):return ('tenant-one','fixture:operator') if i%2==0 else ('tenant-two','fixture:reporter-two')


def request(session,path,payload,identity,*,multipart=False,timeout=None):
    headers={'Authorization':'Bearer '+identity}
    if multipart:body,kind=payload;headers['Content-Type']=kind
    else:body=json.dumps(payload).encode();headers['Content-Type']='application/json'
    begin=time.monotonic();value=None;status=None;error=None
    try:
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(session.backend_port)+path,data=body,headers=headers),timeout=timeout or PROFILE['requestTimeoutSeconds']) as response:
            raw=response.read();status=response.status
            value=json.loads(raw) if 'json' in response.headers.get('Content-Type','') else raw
    except urllib.error.HTTPError as exc:
        status=exc.code;raw=exc.read()
        try:value=json.loads(raw)
        except ValueError:value=raw.decode(errors='replace')[:1000]
    except (OSError,ConnectionError) as exc:error=type(exc).__name__
    end=time.monotonic()
    return {'status':status,'value':value,'error':error,'started':begin,'finished':end,'milliseconds':(end-begin)*1000}


class Lab(h2.Lab):
    def __init__(self,*args):
        super().__init__(*args);self.report=json.loads((self.root/'backend/src/main/resources/acp-report.json').read_bytes())
        text=(self.root/'frontend/src/task-ui-model.ts').read_text();self.query=json.JSONDecoder().raw_decode(text.split('=',1)[1].lstrip())[0]['queryPath']
        self.profile=PROFILE;self.resources=[];self.created=[];self.uploads={};self.reported=[];self.lock=threading.Lock()
    def start(self,*,workers=False,port=18081,pool=None):
        session=demo.Session(self.root,'case-management',self.logs);self.sequence+=10;session.sequence=self.sequence;session.backend_port=port
        session.env.update(ACP_INTAKE_MODE='synthetic-preview',ACP_REPORTING_MODE='preview',ACP_DOCUMENTS_MODE='preview',ACP_INTEGRITY_MODE='preview')
        worker_env(session,workers)
        session.env['JAVA_TOOL_OPTIONS']+=' -Xmx512m -XX:MaxDirectMemorySize=128m -XX:ActiveProcessorCount=2'
        maximum=PROFILE['applicationPoolConnections'] if pool is None else pool
        timeout=PROFILE['applicationPoolAcquisitionTimeoutMs'] if pool is None else PROFILE['pressureAcquisitionTimeoutMs']
        session.env['JAVA_TOOL_OPTIONS']+=' -Dspring.datasource.hikari.maximum-pool-size='+str(maximum)+' -Dspring.datasource.hikari.minimum-idle=1 -Dspring.datasource.hikari.connection-timeout='+str(timeout)
        self.sessions.append(session);session.launch();return session
    def checked(self,session,path,payload,i=0,*,expected=(200,),multipart=False):
        r=request(session,path,payload,token(i),multipart=multipart)
        require(r['status'] in expected,'H3_SETUP_STATUS:'+str(r));return r['value']
    def prepare(self,session):
        require(api(session,'/__test/reset',{})[0]==200,'H3_RESET')
        require(api(session,'/__test/report-negative',{})[0]==200,'H3_SECOND_TENANT')
        sessions=[]
        for i in range(16):sessions.extend(self.checked(session,'/__test/h2-session',{},i)['sessions'])
        require(len({(r['tenant'],r['subject'],r['sid']) for r in sessions})==16,'H3_SESSION_BINDING')
        for i in range(16):
            payload={'title':'H3 seed '+str(i),'summary':'H3 authorized capacity fixture','idempotencyKey':'h3-seed-'+str(i)}
            result=self.checked(session,self.create['path'],payload,i);self.resources.append(result['resourceId'])
        self.raw=b'H3 bounded document\n'+b'x'*(PROFILE['payloadBytes']-20)
        require(len(self.raw)==PROFILE['payloadBytes'],'H3_PAYLOAD_SIZE')
        self.seeds=[]
        for i in range(2):
            d=self.checked(session,self.documents_path+'/upload',h2.upload(self.resources[i],'h3-seed-document-'+str(i),self.raw),i,multipart=True);self.seeds.append(d)
        # Reserved only for the unchanged H2 worker-fencing helper.
        self.checked(session,self.documents_path+'/upload',h2.upload(self.resources[0],'h2-upload'),0,multipart=True)
        require(api(session,'/__test/job-admin',{'action':'INIT'})[0]==200,'H3_JOB_FIXTURE')
        return sessions
    @property
    def documents_path(self):return json.loads((self.root/'backend/src/main/resources/acp-documents.json').read_bytes())['path']
    def ownership(self,resource):
        return self.db.data("SELECT json_build_object('tenant',convert_from("+self.documents_meta['resourceTenant']+",'UTF8'),'subject',convert_from("+self.documents_meta['resourceOwner']+",'UTF8')) FROM "+self.table+" WHERE "+self.documents_meta['resourceIdentity']+"=convert_to('"+resource+"','UTF8')")
    @property
    def documents_meta(self):return json.loads((self.root/'backend/src/main/resources/acp-documents.json').read_bytes())


def run_level(lab,session,clients,phase):
    cycles=PROFILE['warmupCyclesPerClient'] if phase=='warmup' else PROFILE['measuredCyclesPerClient']
    deadline=time.monotonic()+PROFILE['levelTimeoutSeconds'];rows=[];mutex=threading.Lock();live=0;peak=0
    def call(i,cycle,operation,path,payload,multipart=False):
        nonlocal live,peak
        require(time.monotonic()<deadline,'H3_LEVEL_TIMEOUT')
        with mutex:live+=1;peak=max(peak,live)
        try:r=request(session,path,payload,token(i),multipart=multipart)
        finally:
            with mutex:live-=1
        expected=(200,429) if operation in ('create','query') else (200,)
        disposition='SUCCESS' if r['status']==200 else 'EXPECTED_REJECTION' if r['status']==429 and operation in ('create','query') else 'UNEXPECTED_ERROR'
        row={k:v for k,v in r.items() if k!='value'}|{'operation':operation,'phase':phase,'clients':clients,'client':i,'cycle':cycle,'disposition':disposition}
        if r['status']!=200:row['rejectionBody']=r['value']
        with mutex:rows.append(row)
        require(r['status'] in expected and r['error'] is None,'H3_UNEXPECTED_HTTP:'+str(row))
        return r
    def worker(i):
        resource=lab.resources[i];tenant,subject=principal(i)
        for cycle in range(cycles):
            key='h3-'+phase+'-'+str(clients)+'-'+str(i)+'-'+str(cycle)
            payload={'title':'H3 '+key,'summary':'H3 measured authorized case','idempotencyKey':key}
            # Warmup uses the existing seed key; it is recorded, never timed as measured work.
            if phase=='warmup':payload={'title':'H3 seed '+str(i),'summary':'H3 authorized capacity fixture','idempotencyKey':'h3-seed-'+str(i)}
            r=call(i,cycle,'create',lab.create['path'],payload)
            if r['status']==200:
                with lab.lock:lab.created.append({'key':payload['idempotencyKey'],'resource':r['value']['resourceId'],'tenant':tenant,'subject':subject,'seedReplay':phase=='warmup'})
            r=call(i,cycle,'query',lab.query,{'QUERY-TEXT':'H3'})
            if r['status']==200:
                require(type(r['value']) is list and len(r['value'])<=25,'H3_QUERY_PAGE_BOUND')
                with lab.lock:lab.reported.extend({'resource':item['resourceId'],'tenant':tenant,'subject':subject} for item in r['value'])
            r=call(i,cycle,'report',lab.report['path'],{'page':0,'size':20})
            require(len(r['value']['items'])<=20,'H3_REPORT_PAGE_BOUND')
            with lab.lock:lab.reported.extend({'resource':item['resourceId'],'tenant':tenant,'subject':subject} for item in r['value']['items'])
            history=call(i,cycle,'history',lab.report['path']+'/history',{'resourceId':resource,'page':0,'size':20})
            require(history['value']['total']==1 and history['value']['items'][0]['operation']=='CREATE-CASE','H3_HISTORY_CONTENT')
            if phase=='warmup':upload_resource=lab.resources[i%2];upload_key='h3-seed-document-'+str(i%2)
            else:upload_resource=resource;upload_key='h3-document-'+str(clients)+'-'+str(i)
            d=call(i,cycle,'upload',lab.documents_path+'/upload',h2.upload(upload_resource,upload_key,lab.raw),True)['value']
            with lab.lock:
                entry=(tenant,upload_resource,upload_key)
                if entry in lab.uploads:require(lab.uploads[entry]['documentId']==d['documentId'],'H3_DUPLICATE_DOCUMENT_REPLAY')
                lab.uploads[entry]=d
            downloaded=call(i,cycle,'download',lab.documents_path+'/download',{'resourceId':upload_resource,'documentId':d['documentId']})
            require(downloaded['value']==lab.raw,'H3_DOWNLOADED_BYTES')
            meta=call(i,cycle,'metadata',lab.documents_path+'/metadata',{'resourceId':upload_resource,'documentId':d['documentId']})
            require(meta['value']==d,'H3_METADATA')
    begin=time.monotonic()
    with Sampler(lab,session,PROFILE['samplerIntervalSeconds']) as sampler:
        with ThreadPoolExecutor(max_workers=clients) as pool:
            futures=[pool.submit(worker,i) for i in range(clients)]
            try:
                for future in as_completed(futures,timeout=PROFILE['levelTimeoutSeconds']):future.result()
            finally:life.save(lab.logs/('raw-'+phase+'-'+str(clients)+'.json'),rows)
    elapsed=time.monotonic()-begin;require(len(rows)==clients*cycles*len(OPERATIONS),'H3_INCOMPLETE_WORKLOAD')
    require(peak>=min(clients,4),'H3_NO_REAL_OVERLAP')
    return {'clients':clients,'phase':phase,'cyclesPerClient':cycles,'raw':rows,'maximumObservedInFlight':peak,
            'summary':aggregate(rows,elapsed),'perOperation':{op:aggregate([r for r in rows if r['operation']==op],elapsed) for op in OPERATIONS},
            'resources':sampler.result(),'synchronizedLatency':'NONE; NORMAL_REQUESTS_HAVE_NO_HELD_GATES'}


def correctness(lab,session,before,levels,tag):
    state=lab.state();created={r['resource']:r for r in lab.created if not r['seedReplay']}
    require(len(state[lab.table])==len(before[lab.table])+len(created),'H3_BUSINESS_ROW_COUNT')
    audits=state['acp_audit'];old_audits={r['id'] for r in before['acp_audit']};added=[r for r in audits if r['id'] not in old_audits]
    require(sum(r['operation']=='CREATE-CASE' for r in added)==len(created),'H3_CREATE_AUDIT_COUNT')
    d=lab.documents_meta;owners=lab.db.data("SELECT coalesce(json_object_agg(convert_from("+d['resourceIdentity']+",'UTF8'),json_build_object('tenant',convert_from("+d['resourceTenant']+",'UTF8'),'subject',convert_from("+d['resourceOwner']+",'UTF8'))),'{}') FROM "+lab.table)
    for r in [*created.values(),*lab.reported]:require(owners[r['resource']]=={'tenant':r['tenant'],'subject':r['subject']},'H3_STORED_OR_REPORTED_OWNER')
    unique=[k for k in lab.uploads if not k[2].startswith('h3-seed-document')]
    require(len(state[lab.doc])==len(before[lab.doc])+len(unique),'H3_DOCUMENT_COUNT')
    uploads=sum(r['operation']=='PERM-DOC-UPLOAD' for r in added);require(uploads==len(unique),'H3_UPLOAD_AUDIT_DUPLICATE')
    downloads=sum(row['operation']=='download' for level in levels for row in level['raw']);require(sum(r['operation']=='PERM-DOC-READ' for r in added)==downloads,'H3_DOWNLOAD_AUDIT_COUNT')
    for row in state[lab.doc]:
        raw=bytes.fromhex(row['content'][2:]);require(len(raw)==row['size'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'H3_DOCUMENT_STORAGE_INTEGRITY')
    for i in (0,1):
        tenant,subject=principal(i);expected=lab.db.data("SELECT to_json(count(*)) FROM "+lab.table+" WHERE "+lab.documents_meta['resourceTenant']+"=convert_to('"+tenant+"','UTF8') AND "+lab.documents_meta['resourceOwner']+"=convert_to('"+subject+"','UTF8')")
        report=lab.checked(session,lab.report['path'],{'page':0,'size':20},i);require(report['total']==expected,'H3_REPORT_TOTAL')
    old_idem={r['identity']:r for r in before['acp_idempotency']};current={r['identity']:r for r in state['acp_idempotency']};clocks=life.commit_times(lab.container)
    for key,old in old_idem.items():
        row=dict(current[key])
        if old['commit_ns'] is None and row['commit_ns'] is not None:
            require(clocks.get(old['commit_xid'])==row['commit_ns'],'H3_UNVERIFIED_COMMIT_CLOCK');row['commit_ns']=None
        require(row==old,'H3_OLD_IDEMPOTENCY_CHANGED')
    writes=[r for r in state['acp_classification_audit'] if r['operation']=='CREATE-CASE' and r['mode']=='WRITE'];oldwrites=[r for r in before['acp_classification_audit'] if r['operation']=='CREATE-CASE' and r['mode']=='WRITE']
    require(len(writes)==len(oldwrites)+len(created)*len(lab.create['writtenFields']),'H3_CLASSIFICATION_WRITE_COUNT')
    require(len(state['acp_idempotency'])==len(before['acp_idempotency'])+len(created),'H3_IDEMPOTENCY_COUNT')
    life.save(lab.logs/('after-level-'+str(tag)+'.json'),state)
    return {'result':'PASS','newCases':len(created),'newDocuments':len(unique),'downloadAudits':downloads,'duplicates':0,'tenantOwnership':'EXACT','documentHashes':'EXACT','reportTotals':'EXACT','idempotencyRows':'PRESERVED_AND_EXACT_COUNT'}
