"""Actual signed-token journeys and negative tests; tokens never enter evidence."""
import base64,json,time,urllib.request,urllib.error,hashlib
from pathlib import Path
from engineering.reference_application import lifecycle as life
from engineering.capacity.workload import Lab
from engineering.reliability.concurrency import upload
from engineering.source_intelligence.model import sha,require
from engineering.performance.measure import summarize
from phase6_reference_tests import seed_sql

NEGATIVES={'unsigned','signatureSubstitution','payloadSubstitution','algorithmConfusion','unknownKid','wrongIssuer','wrongAudience','expired','notYetValid','missingTenant','malformedTenant','malformedSubject','missingExpiry','missingNotBefore','malformedAuthTime','malformedAudience','wrongTokenType','idToken','tokenProvidedURL','trustedShortcut','wrongTenantSubject','roleEscalation','subjectUnknown','crossTenantHistory','crossTenantDocument','crossTenantJob','forgedTenantHeader','ownershipOverride','tenantOverride','keySourceOutage','keySourceSubstitution','retiredKey','revokedSession','staleAuthentication','insufficientMFA'}

def configuration(issuer,folder,kids,name):
    public=folder/(name+'.jwks');public.write_text(json.dumps(issuer.jwks(kids),sort_keys=True)+'\n')
    value={'profile':'acp-bound-jwt/1','issuer':issuer.url,'audience':'acp-h5','algorithm':'RS256','clockSkewSeconds':0,'tenantClaim':'tenant','roleMapping':'CANONICAL_ROLE_ASSIGNMENT','keySetPath':str(public.absolute()),'keySetSHA256':sha(public.read_bytes()),'tokenType':'JWT','tokenUse':'access'}
    file=folder/(name+'.json');life.save(file,value);return file,public


def call(session,path,token,body=None,*,multipart=False,headers=None):
    h={'Authorization':'Bearer '+token,**(headers or {})}
    if multipart:data,h['Content-Type']=body
    else:data=None if body is None else json.dumps(body).encode();h['Content-Type']='application/json'
    start=time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(session.backend_port)+path,data=data,headers=h),timeout=15) as r:
            raw=r.read();value=json.loads(raw) if 'json' in r.headers.get('Content-Type','') else raw;status=r.status
    except urllib.error.HTTPError as error:
        status=error.code;raw=error.read()
        try:value=json.loads(raw)
        except ValueError:value=None
    return status,value,(time.monotonic()-start)*1000


def exercise(root,folder,container,issuer):
    folder.mkdir(mode=0o700);config,keyfile=configuration(issuer,folder,('h5-k1','h5-k2'),'overlap');retired,retired_keys=configuration(issuer,folder,('h5-k2',),'retired')
    prior={k:__import__('os').environ.get(k) for k in ('ACP_IDENTITY_CONFIG','ACP_IDENTITY_CONFIG_SHA256')}
    import os
    os.environ.update(ACP_IDENTITY_CONFIG=str(config),ACP_IDENTITY_CONFIG_SHA256=sha(config.read_bytes()))
    # Also deny export of the disposable database credential; never issue it as a JWT.
    issuer.tokens.append(os.environ['ACP_TEST_DATABASE_PASSWORD'])
    lab=Lab(root,folder/'runtime',container);events=[];sessions=[]
    def check(label,path,token,body=None,status=200,**options):
        code,value,ms=call(server,path,token,body,**options);events.append({'case':label,'status':code,'expected':status,'milliseconds':ms});life.save(folder/'outcomes.json',events);require(code==status,'H5_HTTP:'+label+':'+str(code));return value
    try:
        # Native trusted-JWT component regressions remain a distinct test scope.
        # They use a separate schema in this newly owned disposable database.
        from engineering.demo import reference as demo
        import xml.etree.ElementTree as ET
        demo.command(['mvn','-B','-ntp','-Dtest=SessionGateTest','test'],root/'backend',folder/'session-regression.log')
        native=ET.parse(root/'backend/target/surefire-reports/TEST-acp.domain.SessionGateTest.xml').getroot()
        require(int(native.get('tests','0'))==3 and all(int(native.get(k,'0'))==0 for k in ('failures','errors','skipped')),'H5_NATIVE_SESSION_REGRESSION')
        session_regression={'profile':'TRUSTED_JWT_COMPONENT_TEST','tests':int(native.get('tests')),'failures':0,'errors':0,'skipped':0}
        server=lab.start();sessions.append(server)
        # Only the existing supported fixture prerequisites in the newly owned DB.
        lab.db.run(';'.join(seed_sql('case-management')[:2]))
        operator=issuer.obtain();check('signedBootstrap','/__test/reset',operator,{})
        check('secondTenantPrerequisites','/__test/report-negative',operator,{})
        other=issuer.obtain(subject='fixture:reporter-two',tenant='tenant-two')
        # Verify HTTPS publication using the fixture-specific trusted CA.
        with urllib.request.urlopen(issuer.url+'/jwks',context=issuer.context,timeout=5) as response:require(json.load(response)==issuer.jwks(),'H5_PUBLICATION')
        ids=[];docs=[];tokens=[operator,other];raw=b'H5 genuinely authenticated document\n'
        ui=json.JSONDecoder().raw_decode((root/'frontend/src/task-ui-model.ts').read_text().split('=',1)[1].lstrip())[0]
        jobs=json.loads((root/'backend/src/main/resources/acp-background-job.json').read_bytes())
        for i,token in enumerate(tokens):
            payload={'title':'H5 case '+str(i),'summary':'H5 signed identity journey','idempotencyKey':'h5-create-'+str(i)}
            made=check('tenant'+str(i)+'Create',lab.create['path'],token,payload);resource=made['resourceId'];ids.append(resource)
            require(lab.ownership(resource)=={'tenant':'tenant-one' if i==0 else 'tenant-two','subject':'fixture:operator' if i==0 else 'fixture:reporter-two'},'H5_OWNER_BINDING')
            replay=check('tenant'+str(i)+'CreateReplay',lab.create['path'],token,payload);require(replay==made,'H5_CREATE_REPLAY')
            result=check('tenant'+str(i)+'ReviewApproveArchive',ui['actionPath'],token,{'expectedVersion':0,'idempotencyKey':'h5-workflow-'+str(i),'input':{ui['resourceInputField']:resource,ui['textInputField']:'H5 reviewed'}})
            require(result['state']=='STATE-ARCHIVED' and result['version']==3,'H5_WORKFLOW_RESULT')
            d=check('tenant'+str(i)+'Upload',lab.documents_path+'/upload',token,upload(resource,'h5-upload-'+str(i),raw),multipart=True);docs.append(d)
            body={'resourceId':resource,'documentId':d['documentId']};require(check('tenant'+str(i)+'Download',lab.documents_path+'/download',token,body)==raw,'H5_DOCUMENT_BYTES')
            history=check('tenant'+str(i)+'History',lab.report['path']+'/history',token,{'resourceId':resource,'page':0,'size':20});life.save(folder/('tenant'+str(i)+'-history.json'),history);require([e['operation'] for e in history['items']]==['CREATE-CASE','CMD-REVIEW','CMD-APPROVE','CMD-ARCHIVE'],'H5_EXECUTION_ORDER')
            report=check('tenant'+str(i)+'Report',lab.report['path'],token,{});require(report['total']==1 and report['items'][0]['resourceId']==resource,'H5_REPORT_ISOLATION')
            check('tenant'+str(i)+'JobStatus',jobs['path']+'/results',token,{'resourceId':resource})
        before=lab.state();before_hash=sha(json.dumps(before,sort_keys=True).encode())
        now=int(time.time());bad={
          'unsigned':issuer.mint(algorithm='none'),'signatureSubstitution':issuer.mint(kid='untrusted',headers={'kid':'h5-k1'}),
          'algorithmConfusion':issuer.mint(algorithm='HS256'),'unknownKid':issuer.mint(kid='untrusted'),
          'wrongIssuer':issuer.mint(claims={'iss':'https://untrusted.invalid'}),'wrongAudience':issuer.mint(claims={'aud':'other'}),
          'expired':issuer.mint(claims={'exp':now-20,'nbf':now-100,'iat':now-100}),'notYetValid':issuer.mint(claims={'nbf':now+60}),
          'missingTenant':issuer.mint(claims={'tenant':None}),'malformedTenant':issuer.mint(claims={'tenant':3}),
          'malformedSubject':issuer.mint(claims={'sub':['fixture:operator']}),'missingExpiry':issuer.mint(claims={'exp':None}),
          'missingNotBefore':issuer.mint(claims={'nbf':None}),'malformedAuthTime':issuer.mint(claims={'auth_time':True}),
          'malformedAudience':issuer.mint(claims={'aud':['acp-h5',3]}),'wrongTokenType':issuer.mint(headers={'typ':'id_token'}),
          'idToken':issuer.mint(claims={'token_use':'id'}),'tokenProvidedURL':issuer.mint(headers={'jku':issuer.url+'/untrusted-jwks'}),
          'trustedShortcut':'browser-authorized'}
        parts=operator.split('.');payload=json.loads(base64.urlsafe_b64decode(parts[1]+'=='));payload['sub']='fixture:reporter-two';parts[1]=base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=');bad['payloadSubstitution']='.'.join(parts);issuer.tokens.append(bad['payloadSubstitution'])
        for label,token in bad.items():check(label,lab.create['path'],token,{'title':'Denied','summary':'No effect','idempotencyKey':'denied-'+label},status=401)
        check('staleAuthentication',lab.report['path'],issuer.mint(claims={'auth_time':issuer.auth_epoch-1}),{},status=403)
        check('insufficientMFA',lab.report['path'],issuer.mint(claims={'amr':['pwd']}),{},status=403)
        check('wrongTenantSubject',lab.report['path'],issuer.mint(tenant='tenant-two'),{},status=403)
        check('subjectUnknown',lab.report['path'],issuer.mint(subject='unknown'),{},status=403)
        check('roleEscalation',lab.create['path'],issuer.mint(subject='other-owner',claims={'roles':['ROLE-REVIEWER','ADMIN'],'scope':'all'}),{'title':'Denied','summary':'No effect','idempotencyKey':'denied-roles'},status=403)
        for label,path,body in [('crossTenantHistory',lab.report['path']+'/history',{'resourceId':ids[1]}),('crossTenantDocument',lab.documents_path+'/download',{'resourceId':ids[1],'documentId':docs[1]['documentId']}),('crossTenantJob',jobs['path']+'/results',{'resourceId':ids[1]})]:check(label,path,operator,body,status=404)
        check('forgedTenantHeader',lab.documents_path+'/metadata',operator,{'resourceId':ids[1],'documentId':docs[1]['documentId']},status=404,headers={'X-Tenant':'tenant-two','X-Trusted-JWT':'true'})
        for label,extra in [('ownershipOverride',{'assignee':'other-owner'}),('tenantOverride',{'tenant':'tenant-two'})]:check(label,lab.create['path'],operator,{'title':'Denied','summary':'No effect','idempotencyKey':label,**extra},status=400)
        require(lab.state()==before,'H5_NEGATIVE_PUBLISHED_BUSINESS_EFFECT')
        # A source outage must reject even an already verified token.
        original=keyfile.read_bytes();keyfile.rename(keyfile.with_suffix('.withheld'))
        try:check('keySourceOutage',lab.report['path'],operator,{},status=401)
        finally:keyfile.with_suffix('.withheld').rename(keyfile)
        keyfile.write_text(json.dumps(issuer.jwks(('untrusted',))))
        try:check('keySourceSubstitution',lab.report['path'],operator,{},status=401)
        finally:keyfile.write_bytes(original)
        issuer.available=False
        try:
            try:urllib.request.urlopen(issuer.url+'/jwks',context=issuer.context,timeout=5);raise AssertionError('H5_PUBLISHER_OUTAGE_NOT_OBSERVED')
            except urllib.error.HTTPError as outage:require(outage.code==503,'H5_PUBLISHER_OUTAGE_STATUS')
            check('offlinePinnedKeyStillVerified',lab.report['path'],operator,{})
            check('unknownKeyDuringIssuerOutage',lab.report['path'],issuer.mint(kid='untrusted'),{},status=401)
        finally:issuer.available=True
        require('/untrusted-jwks' not in issuer.paths,'H5_TOKEN_CONTROLLED_FETCH')
        issuer.active='h5-k2';rotated=issuer.obtain();check('prepublishedKeyRotation',lab.report['path'],rotated,{})
        check('overlapOldKeyStillValid',lab.report['path'],operator,{})
        # Exercise a real fresh process; configuration and public keys are host-pinned.
        server.close();os.environ.update(ACP_IDENTITY_CONFIG=str(retired),ACP_IDENTITY_CONFIG_SHA256=sha(retired.read_bytes()));server=lab.start();sessions.append(server)
        check('retiredKey',lab.report['path'],operator,{},status=401);check('restartSignedOperation',lab.report['path'],rotated,{})
        for i,token in enumerate([rotated,issuer.obtain(subject='fixture:reporter-two',tenant='tenant-two')]):
            require(check('restartTenant'+str(i)+'Document',lab.documents_path+'/download',token,{'resourceId':ids[i],'documentId':docs[i]['documentId']})==raw,'H5_RESTART_BYTES')
        # Real second verification of an already authenticated bearer, measured separately.
        decode=[];http=[]
        for _ in range(24):
            code,value,ms=call(server,'/__test/h5-decode',rotated);require(code==200 and value['sameSubject'] and value['nanoseconds']>0,'H5_VERIFICATION_TIMING');decode.append(value['nanoseconds']/1e6);http.append(ms)
        for label,changes,bad_pin in [('unsupportedAlgorithm',{'algorithm':'HS256'},False),('configurationHashMismatch',{},True),('overflowClockSkew',{'clockSkewSeconds':4294967296},False),('nonStringAudience',{'audience':3},False)]:
            server.close();bad_file=folder/(label+'.json');cfg=json.loads(retired.read_bytes());cfg.update(changes);life.save(bad_file,cfg)
            os.environ.update(ACP_IDENTITY_CONFIG=str(bad_file),ACP_IDENTITY_CONFIG_SHA256='0'*64 if bad_pin else sha(bad_file.read_bytes()))
            rejected=False
            try:lab.start()
            except ValueError as error:
                require(str(error)=='DEMO_BACKEND_EXIT','H5_CONFIGURATION_FAILURE_KIND');rejected=True
            require(rejected,'H5_UNSAFE_CONFIGURATION_STARTED');events.append({'case':label,'result':'STARTUP_REJECTED'})
            os.environ.update(ACP_IDENTITY_CONFIG=str(retired),ACP_IDENTITY_CONFIG_SHA256=sha(retired.read_bytes()));server=lab.start();sessions.append(server)
            check(label+'Recovered',lab.report['path'],rotated,{})
        lab.db.run("UPDATE acp_sessions SET revoked=true WHERE subject=convert_to('fixture:operator','UTF8')")
        check('revokedSession',lab.report['path'],rotated,{},status=403)
        # Signature validity never overrides durable session revocation.
        require(lab.counts()[lab.table]==before[lab.table].__len__(),'H5_BUSINESS_ROW_DRIFT')
        require(NEGATIVES.issubset({x['case'] for x in events}),'H5_MISSING_NEGATIVE')
        final=lab.state();require(len(final[lab.doc])==2 and all(bytes.fromhex(d['content'][2:])==raw and d['sha256']==hashlib.sha256(raw).hexdigest() for d in final[lab.doc]),'H5_STORED_DOCUMENT_BYTES')
        result={'sessionRegressions':session_regression,'profile':'CRYPTOGRAPHIC_JWT_VALIDATION_TEST','outcomes':events,'requiredNegatives':sorted(NEGATIVES),'negativeBusinessStateSHA256':before_hash,'negativeBusinessEffects':0,'tenants':2,'authorizedSubjects':2,'publicKeys':issuer.jwks(),'issuer':issuer.url,'issuerPaths':issuer.paths,'keySource':'LOCAL_HASH_PINNED_PUBLIC_JWKS; NO_TOKEN_DISCOVERY','rotation':'PREPUBLISHED_OVERLAP; EXPLICIT_CONFIG_RESTART_RETIREMENT','overhead':{'nativeDecoderMilliseconds':summarize(decode),'httpMilliseconds':summarize(http),'scope':'24_WARM_OBSERVATIONS; NOT_PRODUCTION_SLO'},'workerIdentity':'EXISTING_EXPLICIT_HOST_SERVICE_CONTEXT; CRYPTOGRAPHIC_SERVICE_ENROLLMENT_UNSUPPORTED; NO_INTERACTIVE_JWT','businessRows':len(final[lab.table]),'documentRows':len(final[lab.doc]),'restart':'FRESH_PROCESS_VERIFIED','authenticationFailuresPublished':False}
        life.save(folder/'security-results.json',result);return result
    finally:
        lab.close()
        for k,v in prior.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
