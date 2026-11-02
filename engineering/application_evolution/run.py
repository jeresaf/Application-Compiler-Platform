"""Real R6→R7 stop/migrate/restart preview, using one retained disposable DB."""
import argparse,asyncio,json,os,platform,shutil,socket,subprocess,uuid
from pathlib import Path
from engineering.reference_application import lifecycle as life
from engineering.reference_application.evolution import api,offline_maven,DisposableSQL,SCHEMA
from engineering.demo import reference as demo
from engineering.documents import application as documents
from engineering.documents.inspection import Preview as DocumentPreview
from engineering.jobs.inspection import Preview as JobPreview
from engineering.documents.run import adapter_source as adapter6,inspect as inspect6,mcp_inspect as mcp6,journey
from engineering.jobs import application as jobs
from engineering.jobs.fixture import adapter_source as adapter7
from engineering.jobs.run import inspect as inspect7,mcp_inspect as mcp7
from engineering.jobs.scenarios import worker_env,wait
from engineering.jobs.fixture import PREFIX
from engineering.native_create.run import JOURNEY as CREATE
from engineering.source_intelligence.model import sha,encode,require,current,compare,impact
from engineering.verification.integration import seal,summary
from engineering.application_evolution.plan import preview,preconditions,verify_capture,CAPTURE_FILES
from compiler_contracts import fingerprint,wire
from filesystem_artifacts import FilesystemArtifactStore,StoreConflict
ROOT=life.ROOT

def build(root,logs,adapter):
 old=life.adapter_source
 try:life.adapter_source=adapter;life.build(root,logs)
 finally:life.adapter_source=old

def session(root,logs,sequence,workers=False):
 s=demo.Session(root,'case-management',logs);s.sequence=sequence;s.env.update(ACP_INTAKE_MODE='synthetic-preview',ACP_REPORTING_MODE='preview',ACP_DOCUMENTS_MODE='preview')
 if workers:worker_env(s,True)
 return s

def analyze(preview,folder,m2,modules):
 folder.mkdir();baseline=folder/'baseline.json';baseline.write_bytes(preview.document);model=preview.analyze(baseline,maven_repo=m2,node_modules=modules,scratch=folder);path=folder/'source-model.json';path.write_bytes(encode(model));return preview.session(baseline,path)

def launch(s,old_password=None):
 if old_password is None:return s.launch()
 # The existing owned-backend binder reads these host test credentials at
 # spawn time. Change only the two credentials, never the owned URL/container.
 keys=('ACP_TEST_DATABASE_USER','ACP_TEST_DATABASE_PASSWORD');previous={k:os.environ.get(k) for k in keys}
 try:
  os.environ.update(ACP_TEST_DATABASE_USER='r8_old_writer',ACP_TEST_DATABASE_PASSWORD=old_password);return s.launch()
 finally:
  for k,value in previous.items():
   if value is None:os.environ.pop(k,None)
   else:os.environ[k]=value

def restart_prior_writer(s,old_password):
 old=s.process.pid;exit_code=demo.stop(s.process);new=launch(s,old_password);require(old!=new,'EVOLUTION_NO_FRESH_PRIOR_JVM');return {'oldPid':old,'oldExit':exit_code,'newPid':new,'principal':'r8_old_writer'}

def identity(db):return db.data("SELECT json_build_object('database',current_database(),'systemIdentifier',(SELECT system_identifier::text FROM pg_control_system()),'postgres',current_setting('server_version_num'),'schemaOid',(SELECT oid FROM pg_namespace WHERE nspname='acp_browser_case_management'))")
def observe(db,container,plan):return {'databaseIdentity':identity(db),'schema':SCHEMA,'history':life.history(container),'populationDigest':sha(encode(demo.database_state(container,SCHEMA))),'source':plan['change']['base'],'target':plan['change']['candidate']}
def same_old(before,after):
 require(all(after.get(t)==rows for t,rows in before.items() if t!='flyway_schema_history'),'EVOLUTION_EXISTING_ROWS_CHANGED')
def migration_absent(db):return db.data("SELECT to_json(NOT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='"+SCHEMA+"' AND table_name='"+PREFIX+"_queue'))")

def faults(db,container,sql,before,logs):
 require(migration_absent(db),'EVOLUTION_START_SCHEMA');record={}
 record['failedMigration']=db.reject('BEGIN;'+sql+"SELECT decode('zz','hex');COMMIT;",'invalid hexadecimal digit');require(migration_absent(db) and demo.database_state(container,SCHEMA)==before,'EVOLUTION_PARTIAL_DDL')
 log=(logs/'interrupted-migration.log').open('wb');proc=subprocess.Popen(['docker','exec','-i',container,'psql','-X','-U','acp_runtime','-d','acp_runtime','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,text=True)
 try:
  proc.stdin.write('SET search_path TO '+SCHEMA+";SET application_name='r8-preview-interrupt';BEGIN;"+sql+'SELECT pg_sleep(60);COMMIT;\n');proc.stdin.flush()
  wait(lambda:db.data("SELECT to_json(EXISTS(SELECT 1 FROM pg_stat_activity WHERE application_name='r8-preview-interrupt' AND wait_event='PgSleep'))"),bool,'EVOLUTION_INTERRUPT_NOT_OBSERVED',15)
  require(db.data("SELECT to_json(bool_and(pg_terminate_backend(pid))) FROM pg_stat_activity WHERE application_name='r8-preview-interrupt'") is True,'EVOLUTION_INTERRUPT_NOT_TERMINATED');proc.wait(timeout=15);require(proc.returncode!=0 and migration_absent(db) and demo.database_state(container,SCHEMA)==before,'EVOLUTION_INTERRUPTED_DDL');record['interruptedMigration']={'exit':proc.returncode,'rollbackObserved':True}
 finally:
  if proc.poll() is None:proc.terminate();proc.wait(timeout=15)
  proc.stdin.close();log.close()
 return record

def worker_checks(s,logs):
 def state():
  code,value=api(s,'/__test/job-state');require(code==200,'EVOLUTION_JOB_STATE');return value
 initial=wait(state,lambda v:len(v['results'])==4 and all(r['status']=='VALID' for r in v['results']),'EVOLUTION_EXISTING_DOCUMENT_DISCOVERY')
 saved=json.loads((logs/'committed.json.documents').read_bytes());base={'resource':saved['resource'],'document':saved['document']['documentId'],'sha256':saved['document']['sha256']}
 def admin(action,**data):require(api(s,'/__test/job-admin',{'action':action,**data})[0]==200,'EVOLUTION_JOB_ADMIN')
 q=str(uuid.uuid4());admin('ENQUEUE_FAULT',queue=q,offset=1,mode='HOLD_FIRST',**base);held=wait(state,lambda v:any(c['queue']==q and c['entered'] for c in v['controls']),'EVOLUTION_LEASE_HELD');admin('EXPIRE',queue=q)
 wait(state,lambda v:any(r['queue']==q and r['token']==2 for r in v['results']),'EVOLUTION_LEASE_RECOVERY');admin('RELEASE',queue=q)
 fenced=wait(state,lambda v:any(a['queue']==q and a['token']==1 and a['state']=='FENCED_RESULT' for a in v['attempts']),'EVOLUTION_STALE_TOKEN')
 require(api(s,'/__test/document-tamper',{})[0]==200,'EVOLUTION_CORRUPT_SETUP');bad=str(uuid.uuid4());admin('ENQUEUE_FAULT',queue=bad,offset=2,**base)
 corrupt=wait(state,lambda v:any(r['queue']==bad and r['status']=='HASH_MISMATCH' for r in v['results']),'EVOLUTION_CORRUPTION_NOT_DETECTED');require(api(s,'/__test/document-tamper',{})[0]==200,'EVOLUTION_CORRUPT_RESTORE')
 require(len(corrupt['results'])==6 and len(corrupt['audits'])==6 and len({r['queue'] for r in corrupt['results']})==6,'EVOLUTION_DUPLICATE_JOB_EFFECT')
 return {'initial':initial,'held':held,'fenced':fenced,'corruption':corrupt}

def verify_append(before,after,commit_times):
 # Downloads append audited access. No existing row may change; business tables
 # and idempotency stay exact. Sessions/rate are excluded by the existing helper.
 original={r['id']:r for r in before['acp_audit']};added=[r for r in after['acp_audit'] if r['id'] not in original]
 require(len(added)==8 and sum(r['operation']=='JOB-INTEGRITY' for r in added)==6 and sum(r['operation']=='PERM-DOC-READ' for r in added)==2,'EVOLUTION_UNEXPECTED_AUDIT_EFFECT')
 adjusted={t:after[t] for t in before}
 for table,rows in before.items():
  if table in ('acp_idempotency','acp_classification_audit'):continue
  require(all(row in after[table] for row in rows),'EVOLUTION_ROW_LOST:'+table)
  if table in ('acp_audit','flyway_schema_history') or table.endswith('_audit'):adjusted[table]=rows
 demo.verify_replay_state(before,adjusted,commit_times)

def restore(w,root,plan,capture_pins):
 capture=w/'r6-database';pins=verify_capture(capture,capture_pins);active=[];s=None;logs=w/'restore';logs.mkdir()
 with demo.owned_database(active),demo.bind_owned_backend(active):
  container=active[0];db=DisposableSQL(container,logs);db_identity=identity(db);prior=json.loads((capture/'database-identity.json').read_bytes());require(db_identity['systemIdentifier']!=prior['systemIdentifier'],'EVOLUTION_RESTORE_NOT_NEW_CLUSTER')
  result=subprocess.run(['docker','exec','-i',container,'psql','-X','-U','acp_runtime','-d','acp_runtime','-v','ON_ERROR_STOP=1'],input=(capture/'database.sql').read_bytes(),capture_output=True,timeout=60);(logs/'restore.stdout').write_bytes(result.stdout);(logs/'restore.stderr').write_bytes(result.stderr);require(result.returncode==0,'EVOLUTION_RESTORE_FAILED')
  db_identity=identity(db);before=json.loads((capture/'database-state.json').read_bytes());require(demo.database_state(container,SCHEMA)==before and life.history(container)==json.loads((capture/'migration-history.json').read_bytes()),'EVOLUTION_RESTORE_STATE')
  observation=observe(db,container,plan);sql=(root/'backend/src/main/resources/db/migration/V5__integrity_jobs.sql').read_text();binding=preconditions(plan,observation,observation,sql)
  try:
   s=session(root,logs,600);s.env['ACP_INTEGRITY_MODE']='preview';s.launch();require(len(life.history(container))==len(json.loads((capture/'migration-history.json').read_bytes()))+1 and life.history(container)[-1]['version']=='5','EVOLUTION_RESTORE_MIGRATION');same_old(before,demo.database_state(container,SCHEMA))
   # Verify original bytes through the real generated download interface.
   import urllib.request
   saved=json.loads((w/'runtime/committed.json.documents').read_bytes());contract=json.loads((root/'backend/src/main/resources/acp-documents.json').read_bytes());body=json.dumps({'resourceId':saved['resource'],'documentId':saved['document']['documentId']}).encode()
   request=urllib.request.Request('http://127.0.0.1:18081'+contract['path']+'/download',data=body,headers={'Authorization':'Bearer browser-authorized','Content-Type':'application/json'})
   with urllib.request.urlopen(request,timeout=30) as response:raw=response.read();require(sha(raw)==saved['document']['sha256'],'EVOLUTION_RESTORED_DOCUMENT_BYTES')
   record={'scope':'QUALIFICATION_ONLY','databaseIdentity':db_identity,'originalCaptureSHA256':pins,'exactRowsBeforeMigration':True,'auditAndIdempotencyExact':True,'documentSHA256':sha(raw),'migrationReboundToNewDatabase':binding,'restart':'ACTUAL_R7_STARTUP','originalCommitClockContinuity':'NOT_CLAIMED_ACROSS_CLUSTERS'};s.close();s=None
  finally:
   if s:s.close()
 require(all(sha((capture/n).read_bytes())==h for n,h in pins.items()),'EVOLUTION_CAPTURE_CHANGED');record['cleanup']='OWN_NEW_DATABASE_REMOVED';life.save(logs/'result.json',record);return record

def qualify(workspace,*,maven_seed=None,npm_seed=None,browser_seed=None,offline=False):
 w=Path(workspace).absolute();require(not w.exists(),'WORKSPACE_COLLISION')
 for port in (18081,18082,4174):
  with socket.socket() as sock:sock.bind(('127.0.0.1',port))
 w.mkdir(mode=0o700);root=w/'application';record={'scope':'QUALIFICATION_ONLY','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'executorSHA256':sha(Path(__file__).read_bytes()),'semanticApproval':'NOT_APPROVED','acceptedHistory':'NOT_CONSTRUCTED','migrationApproval':'ENGINEERING_PREVIEW_ONLY_NO_PRODUCTION_AUTHORITY','releaseDisposition':'PHASE6_RELEASE_CLOSURE_BLOCKED'}
 c6,s6,r6,p6=documents.materialize(root);store=FilesystemArtifactStore(root);store.adopt_human(life.HUMAN);human=(root/life.HUMAN).read_bytes()+b'\n// R8 human-owned continuity marker.\n';(root/life.HUMAN).write_bytes(human);p6=c6.plan(s6,r6,store.inventory());store.apply(p6);c6.verify_materialized(root,p6,s6,r6);expected6=life.tree(root)
 c7=jobs.JobApplication();r7=c7.context.request;s7=c7.context.snapshots.read_exact(r7.application,r7.snapshot_digest)
 life.save(w/'r6-candidate.json',s6.read());life.save(w/'r7-candidate.json',s7.read());life.save(w/'r6-plan.json',wire(p6));preview6=DocumentPreview(c6,s6,r6,p6,c6.audit,root)
 with demo.dependencies(w,maven_seed,npm_seed,offline) as deps,offline_maven():
  demo.command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],root/'frontend',w/'npm.log')
  if browser_seed:shutil.copytree(browser_seed,Path(os.environ['PLAYWRIGHT_BROWSERS_PATH']))
  demo.command(['npx','--no-install','playwright','install','chromium'],root/'frontend',w/'chromium.log')
  old=analyze(preview6,w/'r6-inspection',deps/'m2',root/'frontend/node_modules');build(root,w/'r6-build',adapter6)
  active=[];s=None;browser=[]
  with demo.owned_database(active),demo.bind_owned_backend(active):
   container=active[0];runtime=w/'runtime';runtime.mkdir();db=DisposableSQL(container,runtime)
   try:
    old_password='R8-test-only-'+uuid.uuid4().hex;db.run("CREATE ROLE r8_old_writer LOGIN PASSWORD '"+old_password+"';GRANT CREATE ON DATABASE acp_runtime TO r8_old_writer;");s=session(root,runtime,0);s.env.update(ACP_DATABASE_USER='r8_old_writer',ACP_DATABASE_PASSWORD=old_password);launch(s,old_password);require(db.data("SELECT to_json(EXISTS(SELECT 1 FROM pg_stat_activity WHERE usename='r8_old_writer'))") is True,'EVOLUTION_PRIOR_WRITER_NOT_CONNECTED');record['priorWriter']={'principal':'r8_old_writer','actualPostgresConnectionVerified':True,'scope':'DISPOSABLE_CONTAINER_ONLY'};s.start_frontend();require(api(s,'/__test/reset',{})[0]==200,'EVOLUTION_SEED')
    create=CREATE.replace("page.locator('tbody')","page.locator('tbody').first()");reports=(ROOT/'engineering/reporting/journey.ts').read_text();docs=(ROOT/'engineering/documents/journey.ts').read_text()
    browser.append(journey(s,create,'commit'));record['priorWriter']['restart']=restart_prior_writer(s,old_password);require(db.data("SELECT to_json(EXISTS(SELECT 1 FROM pg_stat_activity WHERE usename='r8_old_writer'))") is True,'EVOLUTION_PRIOR_RESTART_ROLE');browser.append(journey(s,create,'replay'));require(api(s,'/__test/report-negative',{})[0]==200,'EVOLUTION_OWNER_FIXTURE');browser.append(journey(s,reports,'report-commit'));browser.append(journey(s,docs,'document-commit'));s.close();s=None
    before=demo.database_state(container,SCHEMA);history6=life.history(container);life.freeze(container,w/'r6-database');capture_pins={n:sha((w/'r6-database'/n).read_bytes()) for n in CAPTURE_FILES};verify_capture(w/'r6-database',capture_pins);life.save(w/'capture-manifest.json',{'scope':'ENGINEERING_PREVIEW_ONLY','files':capture_pins,'stateDigest':sha(encode(before))});life.save(w/'before.json',before)
    # Preserve the exact prior generated source and binaries before publishing.
    life.detach_outputs(root,expected6,w/'r6-outputs');c6.verify_materialized(root,p6,s6,r6);old_verification=old.evaluate();require(all(r['result']=='PASS' for r in old_verification['results'] if r['kind']=='ARTIFACT_VERIFICATION'),'EVOLUTION_OLD_ARTIFACT_VERIFICATION');asyncio.run(mcp6(old,w/'r6-inspection',old_verification));shutil.copytree(root,w/'r6-source')
    drift=root/'backend/src/main/java/acp/api/DocumentController.java';raw=drift.read_bytes();drift.write_bytes(raw+b'\n// rejected owner drift\n')
    try:
     try:store.inventory();raise AssertionError('EVOLUTION_UNDETECTED_CAS_DRIFT')
     except StoreConflict:pass
     try:current(old.model,root);raise AssertionError('EVOLUTION_UNDETECTED_SOURCE_DRIFT')
     except ValueError:pass
    finally:drift.write_bytes(raw)
    p7=c7.plan(s7,r7,store.inventory());manifest=preview(s6.read(),s7.read(),p6,p7,{'candidate':s6.read()['contentDigest'],'generator':c6.generator,'compiler':r6.compiler,'pipeline':r6.pipeline,'artifactPlan':fingerprint(p6)},{'candidate':s7.read()['contentDigest'],'generator':c7.generator,'compiler':r7.compiler,'pipeline':r7.pipeline,'artifactPlan':fingerprint(p7)})
    sql=next(a.content.read()['text'] for a in p7.artifacts if a.path.endswith('V5__integrity_jobs.sql'))
    life.save(w/'evolution-plan.json',manifest);expected=observe(db,container,manifest);life.save(w/'preconditions.json',expected);record['preflight']=preconditions(manifest,observe(db,container,manifest),expected,sql);record['faults']=faults(db,container,sql,before,runtime)
    # Only this container's dedicated old-writer role is fenced. No host IAM.
    db.run("ALTER ROLE r8_old_writer NOLOGIN;");require(db.data("SELECT to_json(count(*)=0) FROM pg_stat_activity WHERE usename='r8_old_writer'") is True,'EVOLUTION_OLD_CONNECTIONS_REMAIN')
    store.apply(p7);require((root/life.HUMAN).read_bytes()==human,'EVOLUTION_HUMAN_OVERWRITE');c7.verify_materialized(root,p7,s7,r7);expected7=life.tree(root);life.save(w/'r7-plan.json',wire(p7));preview7=JobPreview(c7,s7,r7,p7,c7.audit,root);life.restore_modules(root,w/'r6-outputs')
    new=analyze(preview7,w/'r7-inspection',deps/'m2',root/'frontend/node_modules');life.save(w/'source-impact.json',{'oldModelDigest':old.model['digest'],'newModelDigest':new.model['digest'],'crossBaselineComparison':'BLOCKED: native compare requires identical baseline; not rebound','artifactChanges':manifest['artifactImpact'],'oldDocumentImpact':impact(old.model,w/'r6-source',semantic='DOC-ATTACHMENTS'),'newJobImpact':impact(new.model,root,semantic='JOB-INTEGRITY')});build(root,w/'r7-build',adapter7)
    preconditions(manifest,observe(db,container,manifest),expected,sql)
    s=session(root,runtime,100);s.env['ACP_INTEGRITY_MODE']='preview';s.launch();s.start_frontend()
    migrated=demo.database_state(container,SCHEMA);same_old(before,migrated);history7=life.history(container);require(len(history7)==len(history6)+1 and history7[:-1]==history6 and history7[-1]['version']=='5','EVOLUTION_MIGRATION_HISTORY');record['migration']={'before':history6,'after':history7,'sourceDatabase':expected['databaseIdentity'],'targetDatabase':identity(db),'preexistingRowsExact':True,'sqlSHA256':sha(sql.encode())};require(record['migration']['sourceDatabase']==record['migration']['targetDatabase'],'EVOLUTION_REPLACED_DATABASE')
    require(api(s,'/__test/job-admin',{'action':'INIT'})[0]==200,'EVOLUTION_WORKER_FIXTURE');s.close();s=None
    # A separate old binary cannot authenticate as the fenced prior writer.
    oldroot=w/'r6-source';shutil.copytree(w/'r6-outputs/backend/target',oldroot/'backend/target');probe=session(oldroot,runtime,200);probe.backend_port=18082;probe.env.update(ACP_DATABASE_USER='r8_old_writer',ACP_DATABASE_PASSWORD=old_password)
    try:
     try:launch(probe,old_password)
     except ValueError:
      text=(runtime/f'demo-backend-{probe.sequence}.log').read_text();require('r8_old_writer' in text and ('password authentication failed' in text or 'not permitted to log in' in text),'EVOLUTION_WRONG_OLD_WRITER_FAILURE')
     else:raise AssertionError('EVOLUTION_OLD_WRITER_NOT_FENCED')
    finally:probe.close()
    record['compatibility']={'policy':'CONTROLLED_STOP_MIGRATE_RESTART','zeroDowntime':'NOT_CLAIMED','olderWriter':'FENCED_REAL_OLD_BINARY_STARTUP_REJECTED','earlierOperations':'VERIFIED_ON_R7'}
    s=session(root,runtime,300,True);s.launch();s.start_frontend();record['jobs']=worker_checks(s,runtime);s.close();s=None
    s=session(root,runtime,400);s.env['ACP_INTEGRITY_MODE']='preview';s.launch();s.start_frontend();browser.append(journey(s,docs,'document-replay'));job_journey=(ROOT/'engineering/jobs/journey.ts').read_text();browser.append(journey(s,job_journey,'jobs-commit'));s.restart();browser.append(journey(s,job_journey,'jobs-replay'));continuity=demo.database_state(container,SCHEMA);verify_append(before,continuity,life.commit_times(container));life.save(w/'after-continuity.json',continuity);fresh=(Path(__file__).parent/'journey.ts').read_text();browser.append(journey(s,fresh,'successor-commit'));committed=demo.database_state(container,SCHEMA);s.restart();browser.append(journey(s,fresh,'successor-replay'));replayed=demo.database_state(container,SCHEMA);demo.verify_replay_state(committed,replayed,life.commit_times(container));record['successorWrites']={'newWorkflowCommands':3,'newIdempotencyRows':4,'restartReplay':'NO_DUPLICATE_BUSINESS_EFFECTS','beforeRestartDigest':sha(encode(committed)),'afterRestartDigest':sha(encode(replayed))};life.save(w/'successor-committed.json',committed);life.save(w/'successor-replayed.json',replayed);s.close();s=None
    after=json.loads((w/'after-continuity.json').read_bytes());require(after[next(t for t in before if t.startswith('d_') and not t.endswith('_audit'))]==before[next(t for t in before if t.startswith('d_') and not t.endswith('_audit'))],'EVOLUTION_DOCUMENT_BYTES');record['continuity']={'originalRowCounts':{t:len(v) for t,v in before.items()},'afterRowCounts':{t:len(v) for t,v in after.items()},'originalRowsPreserved':True,'idempotencyRawExact':before['acp_idempotency']==after['acp_idempotency'],'idempotencyBusinessStatePreserved':True,'commitTimestampEnrichment':'ONLY_NATIVE_POSTGRES_ORACLE_VERIFIED_NULL_TO_COMMIT_NS','documentsExact':True};life.save(w/'after.json',after);life.freeze(container,w/'r7-database')
   finally:
    if s:s.close()
  record['restore']=restore(w,root,manifest,capture_pins);life.detach_outputs(root,expected7,w/'r7-outputs');c7.verify_materialized(root,p7,s7,r7)
  from engineering.application_evolution.execution import TransitionExecution
  files=[*sorted(runtime.glob('*-browser.json')),w/'before.json',w/'after.json',w/'evolution-plan.json',w/'capture-manifest.json',w/'r6-database/migration-history.json',w/'r7-database/migration-history.json',w/'restore/result.json',w/'successor-committed.json',w/'successor-replayed.json']
  observation={'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED','candidateDigest':s7.read()['contentDigest'],'artifactPlanDigest':fingerprint(p7),'generator':c7.generator,'sourceSHA256':{p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in [*Path(__file__).parent.glob('*.py'),Path(__file__).parent/'journey.ts']},'files':{p.relative_to(w).as_posix():sha(p.read_bytes()) for p in files}}
  life.save(w/'execution-observation.json',observation);verification=new.evaluate(execution=TransitionExecution(w/'execution-observation.json'));life.save(w/'verification.json',verification);record['mcp']=asyncio.run(mcp7(new,w/'r7-inspection',verification));record.update(sourceSHA256=observation['sourceSHA256'],beforeCandidate=s6.read()['contentDigest'],afterCandidate=s7.read()['contentDigest'],beforeGenerator=c6.descriptor(),afterGenerator=c7.descriptor(),planDigest=manifest['planDigest'],changeDigest=manifest['changeDigest'],browser=browser,sealed05=life.bundle_digest(),cleanup={'database':'REMOVED','processes':'REAPED'},tools={'python':platform.python_version(),'node':subprocess.check_output(['node','--version'],text=True).strip()},humanSHA256=sha(human))
  require(record['executorSHA256']==sha(Path(__file__).read_bytes()),'EVOLUTION_EXECUTOR_DRIFT');life.save(w/'result.json',record)
 return record

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True,type=Path);p.add_argument('--maven-seed',type=Path);p.add_argument('--npm-seed',type=Path);p.add_argument('--browser-seed',type=Path);p.add_argument('--offline',action='store_true');a=p.parse_args();qualify(a.workspace,maven_seed=a.maven_seed,npm_seed=a.npm_seed,browser_seed=a.browser_seed,offline=a.offline)
if __name__=='__main__':main()
