"""Actual signed HTTP journeys and independent PostgreSQL logical recovery."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from datetime import datetime,timezone
import json,os,secrets,subprocess,tempfile,time,uuid
from engineering.disaster_recovery import backup as db
from engineering.identity.issuer import Issuer
from engineering.identity.scenarios import configuration,call
from engineering.operations.lab import OperationalLab
from engineering.reliability.concurrency import upload,next_test_occurrence
from engineering.source_intelligence.model import require,sha,encode
from engineering.reference_application import lifecycle as life
from engineering.jobs.scenarios import wait
from engineering.jobs.fixture import PREFIX
from engineering.demo import reference as demo
from phase6_reference_tests import seed_sql

REQUIRED={'committedPopulation','workerInterruptedBeforeBackup','snapshotBackupDuringWrites','corruptionRejected','substitutionRejected','missingComponentRejected','sourceDatabaseTerminated','wrongTargetRejected','incompleteRestoreRejected','interruptedRestoreRolledBack','startupBeforeRestoreRejected','wrongSchemaRejected','invalidCredentialsRejected','independentRestore','freshAuthenticatedRecovery','documentsExact','auditAndOwnershipExact','idempotencyPreserved','crossTenantDenied','validLeasePreserved','expiredLeaseRecovered','repeatedTargetRejected','independentRepeatedRecovery','privateBackupRemoved'}

@contextmanager
def authenticated_lab(root,folder,container,issuers):
    folder.mkdir(mode=0o700,parents=True);issuer=Issuer();issuers.append(issuer)
    config,_=configuration(issuer,folder,('h5-k1','h5-k2'),'identity');keys=('ACP_IDENTITY_CONFIG','ACP_IDENTITY_CONFIG_SHA256');old={k:os.environ.get(k) for k in keys}
    os.environ.update(ACP_IDENTITY_CONFIG=str(config),ACP_IDENTITY_CONFIG_SHA256=sha(config.read_bytes()));issuer.tokens.append(os.environ['ACP_TEST_DATABASE_PASSWORD'])
    class OwnedLab(OperationalLab):
        def start(self,**kwargs):
            with demo.bind_owned_backend([self.container]):return super().start(**kwargs)
    lab=OwnedLab(root,folder/'runtime',container);lab.stall=300;issuer.tokens.append(lab.metrics_key)
    try:yield lab,issuer
    finally:
        lab.close();issuer.close()
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v

def checked(server,path,token,body=None,*,status=200,multipart=False):
    if token is None:
        from engineering.operations.scenarios import http
        response=http(server,path,body=body);code,value,elapsed=response['status'],response['value'],response['milliseconds']
    else:code,value,elapsed=call(server,path,token,body,multipart=multipart)
    require(code==status,'H7_HTTP:'+str(code)+':'+path);return value

def tokens(issuer,prefix):
    return [issuer.obtain(subject=subject,tenant=tenant,claims={'sid':prefix+'-'+str(i),'auth_time':int(time.time())}) for i,(subject,tenant) in enumerate((('fixture:operator','tenant-one'),('fixture:reporter-two','tenant-two')))]

def audit_counts(lab):
    return lab.db.data("SELECT json_build_object('cases',(SELECT count(*) FROM "+lab.table+"),'creates',(SELECT count(*) FROM acp_audit WHERE operation='CREATE-CASE'),'keys',(SELECT count(*) FROM acp_idempotency),'documents',(SELECT count(*) FROM "+lab.doc+"),'uploads',(SELECT count(*) FROM acp_audit WHERE operation='PERM-DOC-UPLOAD'))")

def exercise(root,folder,resources,issuers):
    folder=Path(folder).absolute();folder.mkdir(mode=0o700);proof=[];private_path=None
    def record(name,**actual):proof.append({'experiment':name,'actual':actual});life.save(folder/'observations.json',proof)
    active=[]
    try:
        with db.new_database(active,resources) as source,authenticated_lab(root,folder/'source',source,issuers) as (lab,issuer):
            server=lab.start();lab.db.run(';'.join(seed_sql('case-management')[:2]));auth=tokens(issuer,'source-'+uuid.uuid4().hex)
            checked(server,'/__test/reset',auth[0],{});checked(server,'/__test/report-negative',auth[0],{})
            ui=json.JSONDecoder().raw_decode((root/'frontend/src/task-ui-model.ts').read_text().split('=',1)[1].lstrip())[0];cases=[];documents=[]
            for i in range(4):
                who=i%2;payload={'title':'H7 case '+str(i),'summary':'Authorized synthetic recovery fixture','idempotencyKey':'h7-create-'+str(i)}
                made=checked(server,lab.create['path'],auth[who],payload);resource=made['resourceId'];require(checked(server,lab.create['path'],auth[who],payload)==made,'H7_INITIAL_REPLAY')
                workflow=None
                if i<2:
                    workflow={'expectedVersion':0,'idempotencyKey':'h7-workflow-'+str(i),'input':{ui['resourceInputField']:resource,ui['textInputField']:'H7 review'}}
                    require(checked(server,ui['actionPath'],auth[who],workflow)['version']==3,'H7_WORKFLOW')
                raw=b'H7 exact synthetic document\xc3\xa9\n'+str(i).encode();document=checked(server,lab.documents_path+'/upload',auth[who],upload(resource,'h7-upload-'+str(i),raw),multipart=True)
                cases.append({'tenant':who,'resource':resource,'payload':payload,'response':made,'workflow':workflow});documents.append({'resource':resource,'raw':raw,'key':'h7-upload-'+str(i),**document})
            checked(server,'/__test/job-admin',auth[0],{'action':'INIT'});server.close();server=lab.start(workers=True)
            def jobs():return checked(server,'/__test/job-state',auth[0])
            wait(jobs,lambda s:len(s['results'])==4 and all(q['state']=='COMPLETED' for q in s['queue']),'H7_INITIAL_JOBS',30)
            def enqueue(mode):
                q=str(uuid.uuid4());d=documents[0];checked(server,'/__test/job-admin',auth[0],{'action':'ENQUEUE_FAULT','queue':q,'resource':cases[0]['resource'],'document':d['documentId'],'sha256':d['sha256'],'occurrence':next_test_occurrence(lab),'mode':mode});return q
            held=enqueue('HOLD_FIRST');wait(jobs,lambda s:any(c['queue']==held and c['entered'] for c in s['controls']),'H7_HELD_WORKER',10)
            lab.db.run("UPDATE "+PREFIX+"_queue SET lease_until=clock_timestamp()+interval '3600 seconds' WHERE id='"+held+"'::uuid")
            old=next(q for q in jobs()['queue'] if q['id']==held);killed=lab.kill(server);server=lab.start();pending=enqueue('NONE')
            require(next(q for q in jobs()['queue'] if q['id']==pending)['state']=='PENDING','H7_PENDING_MISSING');record('workerInterruptedBeforeBackup',processKilled=killed,heldToken=old['token'],pending=1,leaseFault='EXTENDED_IN_DISPOSABLE_FIXTURE_ONLY; NATIVE_POLICY_UNCHANGED')
            # Existing authenticated PostgreSQL oracle cache enrichment, not
            # reconstruction of business rows or commit clocks in a new cluster.
            for xid,ns in life.commit_times(source).items():
                require(str(xid).isdigit() and str(ns).isdigit(),'H7_COMMIT_ORACLE')
                lab.db.run('UPDATE acp_idempotency SET commit_ns='+str(ns)+" WHERE commit_xid='"+str(xid)+"' AND commit_ns IS NULL AND status='COMMITTED_RESULT'")
            require(lab.db.data("SELECT to_json(count(*)) FROM acp_idempotency WHERE status='COMMITTED_RESULT' AND commit_ns IS NULL")==0,'H7_UNRESOLVED_ORIGINAL_COMMIT_CLOCK')
            record('committedPopulation',tenants=2,authorizedCases=4,documents=4,completedJobs=4,counts=audit_counts(lab))
            with tempfile.TemporaryDirectory(prefix='h7-private-backup-',dir=folder) as private:
                private_path=Path(private)
                def activity():
                    post=[]
                    for who in range(2):
                        row=checked(server,lab.create['path'],auth[who],{'title':'After snapshot '+str(who),'summary':'Not in logical recovery point','idempotencyKey':'h7-excluded-'+str(who)});post.append(row['resourceId']);require(lab.ownership(row['resourceId'])=={'tenant':('tenant-one','tenant-two')[who],'subject':('fixture:operator','fixture:reporter-two')[who]},'H7_POST_BOUNDARY_NOT_COMMITTED')
                    return {'authenticatedPostBoundaryCommits':len(post),'independentSQLConfirmed':True,'sourceCasesAfterBoundary':lab.db.data('SELECT to_json(count(*)) FROM '+lab.table),'excludedResourceSHA256':[sha(x.encode()) for x in post]}
                backup,expected,manifest=db.capture(source,private_path/'backup',activity);require(manifest['activity']['sourceCasesAfterBoundary']==len(expected[lab.table])+2,'H7_SNAPSHOT_EXCLUSION_BOUNDARY');life.save(folder/'backup-manifest.json',manifest)
                record('snapshotBackupDuringWrites',snapshot=backup.snapshot,dumpSHA256=backup.digest,size=backup.size,seconds=manifest['seconds'],overlappingWrites=2,expectedStateSHA256=manifest['capturedStateSHA256'])
                # All corruptions are private, owned files, never revised originals.
                corrupt=private_path/'corrupt';__import__('shutil').copytree(backup.directory,corrupt);p=corrupt/'database.dump';raw=p.read_bytes();p.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
                def reject(name,action,label):
                    try:action()
                    except ValueError as e:require(label in str(e),'H7_WRONG_REJECTION:'+name);record(name,rejected=True,code=label)
                    else:raise AssertionError('H7_NOT_REJECTED:'+name)
                reject('corruptionRejected',lambda:db.verify(replace(backup,directory=corrupt)),'H7_BACKUP_SUBSTITUTION')
                reject('substitutionRejected',lambda:db.verify(replace(backup,digest='0'*64)),'H7_BACKUP_SUBSTITUTION')
                missing=private_path/'missing';__import__('shutil').copytree(backup.directory,missing);(missing/'objects.list').unlink();reject('missingComponentRejected',lambda:db.verify(replace(backup,directory=missing)),'H7_BACKUP_COMPONENT_MISSING_OR_ESCAPE')
                # Incorrect external identifiers have no live target capability.
                reject('wrongTargetRejected',lambda:db.target_guard(db.Target(source,active[0],backup.source_system)),'H7_RESTORE_TARGET')
                failure_begin=time.monotonic()
                require(db.identity(source)['systemIdentifier']==backup.source_system,'H7_SOURCE_IDENTITY_CHANGED');demo.existing.docker('kill','--signal=KILL',source)
                require(demo.existing.docker('inspect','--format','{{.State.Running}}',source)=='false','H7_SOURCE_STILL_RUNNING');record('sourceDatabaseTerminated',running=False,sourceSystem=backup.source_system,snapshotAgeSeconds=(time.monotonic_ns()-manifest['snapshotObservedMonotonicNs'])/1e9)
                checked(server,'/actuator/health/readiness',None,status=503);checked(server,'/actuator/health/liveness',None);server.close()
                # Interrupted restore: real pg_restore transaction blocked in a
                # test-only CHECK function; terminate that exact PG backend.
                with db.restore_target([],resources) as target,db.Transaction(target.container) as gate:
                    gate.query('BEGIN;SELECT to_json(pg_advisory_xact_lock('+str(db.GATE)+') IS NULL)')
                    def interrupt(process,target):
                        pid=wait(lambda:db.sql(target.container,"SELECT coalesce(json_agg(a.pid),'[]') FROM pg_stat_activity a JOIN pg_locks l ON l.pid=a.pid WHERE a.application_name='pg_restore' AND l.locktype='advisory' AND NOT l.granted"),lambda p:len(p)==1,'H7_RESTORE_NOT_ACTUALLY_BLOCKED',20)[0]
                        reject('startupBeforeRestoreRejected',lambda:db.admit_application(backup,target),'H7_RESTORE_NOT_VERIFIED')
                        require(db.sql(target.container,'SELECT to_json(pg_terminate_backend('+str(pid)+'))') is True,'H7_RESTORE_TERMINATE')
                    reject('interruptedRestoreRolledBack',lambda:db.restore(backup,target,expected,gated=True,interrupt=interrupt),'H7_RESTORE_PROCESS_FAILED')
                    require(db.sql(target.container,"SELECT to_json(count(*)) FROM pg_namespace WHERE nspname='"+db.SCHEMA+"'")==0,'H7_PARTIAL_DDL_COMMITTED')
                # Complete restore followed by a missing-object fault cannot
                # satisfy independent comparison or application admission.
                with db.restore_target([],resources) as target:
                    db.restore(backup,target,expected);demo.existing.docker('exec',target.container,'psql','-X','-U','acp_runtime','-d','acp_runtime','-c','DROP TABLE '+db.SCHEMA+'.acp_rate')
                    reject('incompleteRestoreRejected',lambda:db.admit_application(backup,target),'H7_RESTORE_CHANGED_BEFORE_ACTIVATION')
                with db.restore_target([],resources) as target,authenticated_lab(root,folder/'wrong-schema',target.container,issuers) as (bad,_):
                    db.restore(backup,target,expected);bad.db.run("UPDATE flyway_schema_history SET version='999' WHERE version='5'")
                    reject('wrongSchemaRejected',lambda:bad.start(),'DEMO_BACKEND_EXIT')
                with db.restore_target([],resources) as target,authenticated_lab(root,folder/'restored',target.container,issuers) as (restored,new_issuer):
                    primary_begin=time.monotonic();receipt=db.restore(backup,target,expected);db.admit_application(backup,target);record('independentRestore',**receipt)
                    previous=os.environ['ACP_TEST_DATABASE_PASSWORD'];os.environ['ACP_TEST_DATABASE_PASSWORD']=secrets.token_urlsafe(32)
                    try:reject('invalidCredentialsRejected',lambda:restored.start(),'DEMO_BACKEND_EXIT')
                    finally:os.environ['ACP_TEST_DATABASE_PASSWORD']=previous
                    ready_begin=time.monotonic();fresh=restored.start();ready_seconds=time.monotonic()-ready_begin;fresh_auth=tokens(new_issuer,'restored-'+uuid.uuid4().hex);first=time.monotonic()
                    checked(fresh,'/actuator/health/readiness',None)
                    for who in range(2):require(checked(fresh,restored.report['path'],fresh_auth[who],{})['total']==2,'H7_REPORT_TOTAL')
                    record('freshAuthenticatedRecovery',newIssuer=True,freshSessions=True,readinessSeconds=ready_seconds,firstAuthenticatedSeconds=time.monotonic()-first,recoverySecondsIncludingFaultExperiments=time.monotonic()-failure_begin,primaryRestoreToFirstOperationSeconds=time.monotonic()-primary_begin,excludedAfterSnapshot=2)
                    for i,(case,doc) in enumerate(zip(cases,documents)):
                        who=case['tenant'];body={'resourceId':case['resource'],'documentId':doc['documentId']};require(checked(fresh,restored.documents_path+'/download',fresh_auth[who],body)==doc['raw'],'H7_DOCUMENT_BYTE_MISMATCH')
                        require(restored.ownership(case['resource'])=={'tenant':('tenant-one','tenant-two')[who],'subject':('fixture:operator','fixture:reporter-two')[who]},'H7_OWNERSHIP')
                        history=checked(fresh,restored.report['path']+'/history',fresh_auth[who],{'resourceId':case['resource'],'page':0,'size':20})
                        require([r['operation'] for r in history['items']]==(['CREATE-CASE','CMD-REVIEW','CMD-APPROVE','CMD-ARCHIVE'] if case['workflow'] else ['CREATE-CASE']),'H7_AUDIT_ORDER')
                        checked(fresh,restored.documents_path+'/metadata',fresh_auth[1-who],body,status=404);checked(fresh,restored.report['path']+'/history',fresh_auth[1-who],{'resourceId':case['resource']},status=404)
                    record('documentsExact',documents=4,hashes=[sha(d['raw']) for d in documents]);record('auditAndOwnershipExact',cases=4,tenants=2,workflowHistories=2);record('crossTenantDenied',negativeRequests=8)
                    before=audit_counts(restored)
                    for case in cases:require(checked(fresh,restored.create['path'],fresh_auth[case['tenant']],case['payload'])==case['response'],'H7_IDEMPOTENCY_RESULT')
                    require(audit_counts(restored)==before,'H7_DUPLICATE_BUSINESS_EFFECT');record('idempotencyPreserved',replays=4,duplicateEffects=0,counts=before,commitClock='SOURCE_AUTHENTICATED_CACHE; NO_CROSS_CLUSTER_XID_ORACLE_CLAIM')
                    fresh.close();fresh=restored.start(workers=True)
                    def target_jobs():return checked(fresh,'/__test/job-state',fresh_auth[0])
                    wait(target_jobs,lambda s:any(r['queue']==pending for r in s['results']),'H7_PENDING_NOT_RESUMED',30)
                    held_row=next(q for q in target_jobs()['queue'] if q['id']==held);require(held_row['token']==old['token'] and held_row['owner']==old['owner'] and held_row['state']=='RUNNING','H7_VALID_LEASE_RECLAIMED')
                    record('validLeasePreserved',token=held_row['token'],priorOwnerUnchanged=True,pendingRecovered=1)
                    checked(fresh,'/__test/job-admin',fresh_auth[0],{'action':'EXPIRE','queue':held});done=wait(target_jobs,lambda s:any(r['queue']==held and r['status']=='VALID' for r in s['results']),'H7_EXPIRED_LEASE_NOT_RECOVERED',30)
                    results=[r for r in done['results'] if r['queue']==held];winner=next(q for q in done['queue'] if q['id']==held);require(len(results)==1 and winner['token']==old['token']+1 and winner['owner']!=old['owner'],'H7_WORKER_FENCE');require(sum(a['id']==results[0]['audit_id'] for a in done['audits'])==1,'H7_JOB_AUDIT_LINK');record('expiredLeaseRecovered',winningToken=winner['token'],uniqueResult=1,uniqueAudit=1)
                    stable=sha(encode(db.state(lambda q:db.sql(target.container,q))));reject('repeatedTargetRejected',lambda:db.restore(backup,target,expected),'H7_RESTORE_TARGET_NOT_EMPTY');require(sha(encode(db.state(lambda q:db.sql(target.container,q))))==stable,'H7_REPEATED_RECOVERY_OVERWROTE_DATA')
                with db.restore_target([],resources) as target:
                    again=db.restore(backup,target,expected);db.admit_application(backup,target);record('independentRepeatedRecovery',**again)
                db.verify(backup);require(not demo.existing.docker('inspect','--format','{{.State.Running}}',source)=='true','H7_SOURCE_REUSED')
        require(private_path is not None and not private_path.exists(),'H7_RAW_BACKUP_LEAK');record('privateBackupRemoved',removed=True,encryption='NOT_ENCRYPTED; NO_SECURE_ERASURE_CLAIM')
        require({r['experiment'] for r in proof}==REQUIRED,'H7_INCOMPLETE_EXPERIMENTS')
        return {'scope':'QUALIFICATION_ONLY','experiments':proof,'backup':manifest,'PITR':{'status':'NOT_RUN','reason':'LOGICAL_EXPORTED_SNAPSHOT_ONLY; NO_PHYSICAL_BACKUP_OR_WAL_REPLAY'},'productionRPO_RTO':'NOT_APPROVED','G19':'NOT_SATISFIED','historicalCreate500':'UNRESOLVED','unmatchedResourceHTTP500':'RETAINED','rawBackupRemoved':True}
    finally:
        for issuer in issuers:issuer.close()
