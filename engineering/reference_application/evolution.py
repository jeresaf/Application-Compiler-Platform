"""Exact R2 proposal preview. Never an accepted plan or retained-population executor.

The pure successor API supplies lowering/DDL/artifacts; this lab exposes the one
required field as separate SQL phases. No fake AcceptedMigrationHistory is used.
"""
import argparse,json,os,platform,shutil,socket,subprocess,sys,urllib.request,urllib.error,uuid
from pathlib import Path
from contextlib import contextmanager
from engineering.reference_application import lifecycle as life
from engineering.reference_application.inspection import HUMAN
from engineering.demo import reference as demo
from engineering.demo.pipeline import inputs,request as candidate_request
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
from engineering.generator_candidates.spring_vue_postgres_0_6.migrations import identifier
from engineering.source_intelligence.model import encode,sha,require,impact
from engineering.verification.integration import outcome,seal,summary,validate_result
from compiler_core import _ownership
from compiler_contracts import Document,fingerprint,wire,COMPILER,PIPELINE
from filesystem_artifacts import FilesystemArtifactStore
from changes import prepare
from deterministic_approval import approved_snapshot
from phase6_reference_tests import seed_sql,symbol

ROOT=life.ROOT;FIELD='EVOLVE-REFERENCE-NOTE';TABLE=symbol('CASE','e');COLUMN=identifier(FIELD,'f')
SCHEMA='acp_browser_case_management'
PREVIEW_VALUE="e\u0301\x00🦋'"  # Explicit synthetic test vector, NOT a retained-population binding.

def proposal():
 directory=ROOT/'proposals/phase6-evolution-review'
 manifest=json.loads((directory/'manifest.json').read_bytes())['domains']['case-management']
 values={}
 for kind in ('change','canonical-candidate','plan'):
  p=directory/('case-management-'+kind+'.json');raw=p.read_bytes()
  require('sha256:'+sha(raw)==manifest['files'][kind],'PROPOSAL_SUBSTITUTION:'+kind);values[kind]=json.loads(raw)
 base=approved_snapshot('case-management');plan=prepare(base,values['change'])
 require(plan==values['plan'] and plan['candidate']==values['canonical-candidate'],'PREVIEW_ANCESTRY')
 require(plan['candidate']['contentDigest']==manifest['candidateDigest'],'CANDIDATE_DIGEST')
 require(plan['change']['migration']['compatibility']=='BREAKING','COMPATIBILITY')
 return Document.of(base),Document.of(plan['candidate']),plan

def statements(candidate,snapshot):
 """Only expose the exact column emitted by native lowering, not inferred types."""
 target=candidate.lower(snapshot,compiler=COMPILER,pipeline=PIPELINE)
 ddl=candidate._generation.schema(target.target_model.read())
 require(COLUMN+' bytea NOT NULL' in ddl,'NATIVE_REQUIRED_STORAGE')
 return {'EXPAND':f'ALTER TABLE {TABLE} ADD COLUMN {COLUMN} bytea;',
 'VERIFY':f"SET CONSTRAINTS ALL IMMEDIATE;DO $$ BEGIN IF EXISTS(SELECT 1 FROM {TABLE} WHERE {COLUMN} IS NULL) THEN RAISE EXCEPTION 'R2_INCOMPLETE_BACKFILL'; END IF; END $$;",
 'CONTRACT':f'ALTER TABLE {TABLE} ALTER COLUMN {COLUMN} SET NOT NULL;'}

def backfill(rows,mapping):
 require(type(mapping) is dict and len(mapping)==len(rows) and set(mapping)=={(r['tenant'],r['resource']) for r in rows},'EXACT_SYNTHETIC_POPULATION')
 for row in rows:
  require(all(type(row[k]) is str and bytes.fromhex(row[k]).hex()==row[k] for k in ('tenant','resource')),'ROW_IDENTITY_ENCODING')
 sql=[]
 for r in rows:
  v=mapping[(r['tenant'],r['resource'])];require(type(v) is str,'EXPLICIT_STRING_VALUE')
  sql.append(f"UPDATE {TABLE} SET {COLUMN}=decode('{v.encode('utf8','strict').hex()}','hex') WHERE {symbol('CASE-TENANT','f')}=decode('{r['tenant']}','hex') AND {symbol('CASE-ID','f')}=decode('{r['resource']}','hex') AND {COLUMN} IS NULL;")
 return '\n'.join(sql)

def explicit_value_insert(seed,value):
 """Existing trusted fixture INSERT plus an explicit typed value, never default."""
 require(type(value) is str,'EXPLICIT_NEW_RECORD_STRING')
 require(seed.count(') VALUES')==1 and seed.endswith(')'),'FIXTURE_INSERT_DRIFT')
 return seed.replace(') VALUES',','+COLUMN+') VALUES').removesuffix(')')+",decode('"+value.encode('utf8','strict').hex()+"','hex'))"


class DisposableSQL:
 """No caller-provided URL. Can address only the container allocated by this run."""
 def __init__(self,container,logs):
  require(container.startswith('acp-06-runtime-'),'UNOWNED_DATABASE');self.container=container;self.logs=logs;self.index=0
 def run(self,sql,*,check=True):
  self.index+=1
  result=subprocess.run(['docker','exec','-i',self.container,'psql','-X','-U','acp_runtime','-d','acp_runtime','-Atq','-v','ON_ERROR_STOP=1'],input='SET search_path TO '+SCHEMA+';'+sql,text=True,capture_output=True,timeout=30)
  life.save(self.logs/f'sql-{self.index:03d}.json',{'sql':sql,'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
  if check:require(result.returncode==0,'DISPOSABLE_SQL_FAILED:'+result.stderr)
  return result
 def data(self,sql):return json.loads(self.run(sql).stdout)
 def reject(self,sql,expected):
  r=self.run(sql,check=False);require(r.returncode!=0 and expected in r.stderr,'EXPECTED_SQL_REJECTION:'+expected);return {'exit':r.returncode,'error':expected}
 def rows(self):return self.data(f"SELECT coalesce(json_agg(json_build_object('tenant',encode({symbol('CASE-TENANT','f')},'hex'),'resource',encode({symbol('CASE-ID','f')},'hex'),'row',to_jsonb(t)) ORDER BY {symbol('CASE-ID','f')}),'[]') FROM {TABLE} t")

def api(session,path,data=None,token='browser-authorized'):
 body=None if data is None else json.dumps(data).encode()
 req=urllib.request.Request(f'http://127.0.0.1:{session.backend_port}'+path,data=body,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=30) as r:return r.status,json.load(r)
 except urllib.error.HTTPError as e:return e.code,e.read().decode()

@contextmanager
def offline_maven():
 previous=os.environ.get('MAVEN_ARGS');os.environ['MAVEN_ARGS']='-o'
 try:yield
 finally:
  if previous is None:os.environ.pop('MAVEN_ARGS',None)
  else:os.environ['MAVEN_ARGS']=previous


def qualify(workspace,*,maven_seed=None,npm_seed=None,offline=False,restore=None):
 w=Path(workspace).absolute();require(not w.exists() and not w.is_symlink(),'WORKSPACE_COLLISION')
 with socket.socket() as listener:listener.bind(('127.0.0.1',18081))
 w.mkdir(mode=0o700)
 life.save(w/'execution-owner.json',{'scope':'SYNTHETIC_R2_PREVIEW_ONLY','workspace':str(w),'inputs':str(w.parent/(w.name+'-inputs')),'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'cleanup':'OWN_DATABASE_AND_PROCESSES_REMOVED_FILES_RETAINED','retainedR1MigrationAuthorized':False})
 old,new,plan=proposal();c=SuccessorCandidate();r0=candidate_request(c,old);r1=candidate_request(c,new)
 p0=c.plan(old,r0);root=w/'application';store=FilesystemArtifactStore(root);store.apply(p0)
 old_source=w/'old-source';shutil.copytree(root,old_source)
 store.adopt_human(HUMAN);(root/HUMAN).write_bytes((root/HUMAN).read_bytes()+b'\n// R2 preview HUMAN seam retained.\n');human=(root/HUMAN).read_bytes()
 inventory=store.inventory();p1=_ownership(c.plan(new,r1,inventory=inventory),inventory);store.apply(p1);c.verify_materialized(root,p1,new,r1)
 require((root/HUMAN).read_bytes()==human,'HUMAN_OWNERSHIP_LOST')
 before=life.tree(old_source);after=life.tree(root)
 changes=[{'path':n,'oldSHA256':before.get(n),'newSHA256':after.get(n)} for n in sorted(set(before)|set(after)) if before.get(n)!=after.get(n)]
 phases=statements(c,new)
 life.save(w/'semantic-preview.json',{'scope':'QUALIFICATION_ONLY_NOT_ACCEPTED_HISTORY','base':old.read()['contentDigest'],'candidate':new.read()['contentDigest'],'plan':plan,'targetIRDigest':fingerprint(c.lower(new,compiler=COMPILER,pipeline=PIPELINE)),'artifactPlan':wire(p1),'changedArtifacts':changes,'humanSHA256':sha(human),'sqlPhases':phases})
 for name,sql in phases.items():(w/(name+'.sql')).write_text(sql+'\n')
 record={'scope':'QUALIFICATION_ONLY','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'python':platform.python_version(),'tools':{name:subprocess.check_output(args,text=True,stderr=subprocess.STDOUT).strip() for name,args in {'node':['node','--version'],'java':['java','--version'],'maven':['mvn','--version']}.items()},'executorSHA256':sha(Path(__file__).read_bytes()),'sealedParent':life.bundle_digest(),'candidate':c.descriptor(),'checks':{},'acceptedTransition':False,'retainedR1Migrated':False}
 with demo.dependencies(w,maven_seed,npm_seed,offline) as deps,offline_maven():
  demo.command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],root/'frontend',w/'npm.log')
  # Analyze unchanged approved source with Phase 7, retaining Phase 8's genuine
  # baseline evidence. New candidate origins are NOT grafted onto this model.
  from engineering.source_intelligence import analysis
  from engineering.reference_application.inspection import inspect
  baseline=analysis.prepare(w/'approved-analysis','case-management')
  _,model,verification=inspect(Path(baseline['application']),Path(baseline['binding']),w/'source-impact',maven_repo=deps/'m2',node_modules=root/'frontend/node_modules')
  affected=set(plan['impact']['semanticIds'])|{'CASE','UC-TASK'}  # Storage owner included separately from exact-reference semantic closure.
  impacts={}
  for id in sorted(affected & {n['id'] for n in old.read()['content']['nodes']}):
   state,value,errors=outcome(lambda:impact(model,Path(baseline['application']),semantic=id))
   impacts[id]={'result':state if state=='PASS' else 'BLOCKED','impact':value,'reasons':errors}
  require(any(v['result']=='PASS' for v in impacts.values()),'NO_SOURCE_IMPACT_BOUND')
  life.save(w/'source-impact/semantic-impact.json',{'impact':impacts,'newNodes':[x['id'] for x in plan['diff'] if x['operation']=='ADD'],'candidateModel':'BLOCKED: Phase7 binding requires an approved original reference; no forged baseline','candidateVerification':'BLOCKED: Phase8 Session requires original approved compilation ancestry','originalVerification':verification['summary'],'artifactChanges':changes,'securityFindings':'HISTORICAL_FINDINGS_RETAINED_NOT_RESCANNED_OR_CLEARED'})
  life.build(root,w/'build')
  migrations=w/'initial-migrations';shutil.copytree(old_source/'backend/src/main/resources/db/migration',migrations)
  active=[]
  with demo.owned_database(active),demo.bind_owned_backend(active):
   container=active[0];logs=w/'database';logs.mkdir();db=DisposableSQL(container,logs)
   record['database']={'container':container,'image':demo.existing.IMAGE,'identity':db.data("SELECT json_build_object('database',current_database(),'systemIdentifier',(SELECT system_identifier::text FROM pg_control_system()),'postgres',version())")}
   require(db.data("SELECT to_json(current_setting('server_version_num')::int)")==180006,'POSTGRES_VERSION')
   session=None
   try:
    rt=w/'runtime';rt.mkdir();session=demo.Session(root,'case-management',rt)
    # Generated candidate V1 is a fresh-schema artifact. Existing V1 must retain
    # its original checksum: external test configuration keeps it immutable.
    session.env['SPRING_FLYWAY_LOCATIONS']='filesystem:'+str(migrations)
    first=session.launch();require(api(session,'/__test/reset',{})[0]==200,'SYNTHETIC_SEED')
    db.run('BEGIN;'+phases['EXPAND']+'COMMIT;')
    db.run(seed_sql('case-management')[1].replace('fixture:operator','fixture:other').replace('tenant-one','tenant-two')+';')
    old_insert=seed_sql('case-management')[2].replace('fixture-resource','old-writer-resource').replace('tenant-one','tenant-two').replace('fixture:operator','fixture:other')
    db.run(old_insert+';');population=db.rows();life.save(w/'synthetic-population.json',population)
    mappings={(x['tenant'],x['resource']):PREVIEW_VALUE for x in population}
    fill=backfill(population,mappings);(w/'BACKFILL.sql').write_text(fill+'\n')
    record['checks']['prematureContract']=db.reject('BEGIN;'+phases['VERIFY']+phases['CONTRACT']+'COMMIT;','R2_INCOMPLETE_BACKFILL')
    record['checks']['transactionRollback']=db.reject('BEGIN;'+fill+"SELECT decode('zz','hex');COMMIT;",'invalid hexadecimal digit')
    require(all(x['row'][COLUMN] is None for x in db.rows()),'FAILED_TRANSACTION_PARTIAL_BACKFILL')
    # Kill a real backend owning an open migration transaction. Observe its
    # server-side lock before termination; no sleeps determine test success.
    from engineering.recovery.qualify import wait_until
    interrupt_log=(logs/'interrupted.log').open('wb')
    proc=subprocess.Popen(['docker','exec','-i',container,'psql','-X','-U','acp_runtime','-d','acp_runtime','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=interrupt_log,stderr=subprocess.STDOUT,text=True)
    try:
     proc.stdin.write('SET search_path TO '+SCHEMA+";SET application_name='r2-preview-interrupt';BEGIN;"+fill+'SELECT pg_advisory_xact_lock(9124701);SELECT pg_sleep(60);COMMIT;\n');proc.stdin.flush()
     wait_until(lambda:db.data("SELECT to_json(EXISTS(SELECT 1 FROM pg_stat_activity WHERE application_name='r2-preview-interrupt' AND wait_event='PgSleep'))"),'MIGRATION_TRANSACTION_NOT_OBSERVED',15)
     require(db.data("SELECT to_json(bool_and(pg_terminate_backend(pid))) FROM pg_stat_activity WHERE application_name='r2-preview-interrupt'") is True,'NO_MIGRATION_TERMINATION');proc.wait(timeout=15)
     require(proc.returncode!=0 and all(x['row'][COLUMN] is None for x in db.rows()),'INTERRUPTED_MIGRATION_NOT_ROLLED_BACK')
     record['checks']['interruptedRollback']={'exit':proc.returncode,'rowsUnchanged':True}
    finally:
     if proc.poll() is None:proc.terminate();proc.wait(timeout=15)
     proc.stdin.close();interrupt_log.close()
    # Switch: a separately restricted old-writer role loses INSERT before NOT
    # NULL. Only this new container's role is changed, never host/application IAM.
    db.run(f'CREATE ROLE r2_old_writer NOLOGIN;GRANT USAGE ON SCHEMA {SCHEMA} TO r2_old_writer;GRANT INSERT ON {TABLE} TO r2_old_writer;')
    db.run(f'REVOKE INSERT ON {TABLE} FROM r2_old_writer;')
    record['checks']['writerFenced']=db.reject('SET ROLE r2_old_writer;'+old_insert.replace('old-writer-resource','fenced-resource')+';','permission denied')
    db.run('BEGIN;'+fill+phases['VERIFY']+phases['CONTRACT']+'COMMIT;')
    for row in db.rows():require(row['row'][COLUMN]=='\\x'+PREVIEW_VALUE.encode().hex() and {k:v for k,v in row['row'].items() if k!=COLUMN}=={k:v for k,v in next(x for x in population if x['resource']==row['resource'])['row'].items() if k!=COLUMN},'EXACT_BACKFILL_ORIGINAL_BYTES')
    record['checks']['repeatExpandRejected']=db.reject('BEGIN;'+phases['EXPAND']+'COMMIT;','already exists')
    original_backfill=db.rows();db.run('BEGIN;'+fill+phases['VERIFY']+'COMMIT;');require(db.rows()==original_backfill,'BACKFILL_RETRY_CHANGED_VALUES')
    record['checks']['repeatBackfill']={'unchanged':True}
    record['checks']['oldWriterRejected']=db.reject(old_insert.replace('old-writer-resource','missing-value')+';','not-null constraint')
    null_insert=old_insert.replace('old-writer-resource','null-value').replace(') VALUES',','+COLUMN+') VALUES').removesuffix(')')+',NULL)'
    record['checks']['nullRejected']=db.reject(null_insert+';','not-null constraint')
    new_insert=explicit_value_insert(old_insert.replace('old-writer-resource','new-explicit').replace('tenant-two','tenant-one').replace('fixture:other','fixture:operator'),'')
    db.run(new_insert+';');require(db.data(f"SELECT to_json(encode({COLUMN},'hex')) FROM {TABLE} WHERE {symbol('CASE-ID','f')}=decode('{b'new-explicit'.hex()}','hex')")=='','EMPTY_EXPLICIT_STRING')
    contract=db.data(f"SELECT json_build_object('type',udt_name,'nullable',is_nullable,'default',column_default) FROM information_schema.columns WHERE table_schema='{SCHEMA}' AND table_name='{TABLE}' AND column_name='{COLUMN}'")
    require(contract=={'type':'bytea','nullable':'NO','default':None},'REQUIRED_FIELD_CONSTRAINTS');record['checks']['columnContract']=contract
    ui=json.loads((root/'frontend/src/task-ui-model.ts').read_text().removeprefix('export const ui = ').strip().removesuffix(' as const;'))
    payload={'expectedVersion':0,'idempotencyKey':str(uuid.uuid4()),'input':{ui['resourceInputField']:'fixture-resource',ui['textInputField']:'R2 preview update 🦋'}}
    code,result=api(session,ui['actionPath'],payload);require(code==200,'EVOLVED_GENERATED_ACTION:'+str(result))
    require(result['version']==3 and result['state']=='STATE-ARCHIVED','EVOLVED_WORKFLOW_LINKAGE')
    expected_notes={x['resource']:x['row'][COLUMN] for x in db.rows()}
    record['checks']['authorization']={'outsider':api(session,ui['actionPath'],payload,'browser-outsider')[0],'expired':api(session,ui['actionPath'],payload,'browser-expired')[0]}
    require(record['checks']['authorization']=={'outsider':403,'expired':401},'AUTHENTICATION_BOUNDARY')
    code,other=api(session,ui['queryPath'],{'QUERY-TEXT':''},'browser-wrong-tenant');require(code==200 and type(other) is list and len(other)==1 and other[0]['resourceId']=='old-writer-resource' and other[0]['output'][ui['outputField']]=='old','TENANT_BOUNDARY:'+str((code,other)))
    record['checks']['wrongTenant']={'status':code,'rows':other}
    committed=demo.database_state(container,SCHEMA);history=life.history(container)
    require(len(committed['acp_audit'])==3 and len(committed['acp_idempotency'])==3,'WORKFLOW_EFFECTS')
    old_pid=session.process.pid;session.close();session.processes=[];new_pid=session.launch()
    require(old_pid!=new_pid and api(session,ui['actionPath'],payload)==(200,result),'RESTART_REPLAY')
    after_state=demo.database_state(container,SCHEMA)
    demo.verify_replay_state(committed,after_state,life.commit_times(container))
    require(history==life.history(container) and expected_notes=={x['resource']:x['row'][COLUMN] for x in db.rows()},'RESTART_VALUE_OR_HISTORY_DRIFT')
    record['checks']['application']={'oldPid':old_pid,'newPid':new_pid,'result':result,'auditEvents':len(after_state['acp_audit']),'idempotency':len(after_state['acp_idempotency']),'exactNotes':expected_notes,'replay':'PASS','originalFlywayHistoryUnchanged':True}
    session.close();session=None
    life.freeze(container,w/'preview-final-database')
    life.save(w/'authorization-package.json',authorization_package(w,plan,population,record))
   finally:
    if session:session.close()
  record['cleanup']={'databaseRemoved':True,'processesReaped':True}
  if restore:record['restore']=restore_database(Path(restore),w/'restore')
  package=authorization_package(w,plan,population,record)
  package['measuredRetainedR1']=record.get('restore',{}).get('originalPopulation',{'status':'NOT_MEASURED_IN_THIS_EXECUTION'})
  life.save(w/'authorization-package.json',package)
 require(record['executorSHA256']==sha(Path(__file__).read_bytes()),'EXECUTOR_CHANGED_DURING_EXECUTION')
 require(all(sha((root/name).read_bytes())==digest for name,digest in after.items()),'GENERATED_SOURCE_CHANGED_DURING_EXECUTION')
 life.detach_outputs(root,after,w/'build-outputs')
 c.verify_materialized(root,p1,new,r1)
 record['generatedSourcePreserved']=True
 record['evidenceSHA256']={p.relative_to(w).as_posix():sha(p.read_bytes()) for p in sorted(w.rglob('*')) if p.is_file() and ('node_modules' not in p.parts) and not p.name=='result.json'}
 rows=[{'id':'preview:'+key,'kind':'SYNTHETIC_RUNTIME_OBSERVATION','result':'PASS','observation':value} for key,value in sorted(record['checks'].items())]
 rows += [{'id':'candidate-source-model','kind':'SOURCE_BINDING','result':'BLOCKED','reason':'Existing Phase7/8 admission binds original approved references only'},{'id':'accepted-R2-migration','kind':'SEMANTIC_OBLIGATION','result':'NOT_RUN','reason':'No accepted history, population binding or execution approval'}]
 verification=seal({'schema':'acp-verification-result/1','scope':'QUALIFICATION_ONLY','inputs':{'sourceCommit':record['sourceCommit'],'executorSHA256':record['executorSHA256'],'candidateDigest':new.read()['contentDigest'],'evidenceDigest':sha(encode(record))},'results':rows,'summary':summary(rows),'releaseDisposition':'PHASE6_RELEASE_CLOSURE_BLOCKED'})
 validate_result(verification);life.save(w/'preview-verification-result.json',verification)
 life.save(w/'result.json',record);return record


def authorization_package(workspace,plan,population,record):
 return {'scope':'REVIEW_REQUEST_ONLY_NOT_APPROVAL','semanticContent':'APPROVED_CONTENT','authenticatedProof':'PENDING_HUMAN_SIGNING','baseCanonical':plan['change']['base']['digest'],'candidateCanonical':plan['candidate']['contentDigest'],'changeSetSHA256':sha((ROOT/'proposals/phase6-evolution-review/case-management-change.json').read_bytes()),'previewPlanDigest':plan['planDigest'],'history':'SYNTHETIC_PREVIEW_ANCHOR_NOT_ACCEPTED_HISTORY','semanticDecisionSHA256':sha((ROOT/'targets/spring-vue-postgres/evidence/semantic-content-decisions/2026-10-12/case-management.json').read_bytes()),'sqlSHA256':{p.name:sha(p.read_bytes()) for p in sorted(workspace.glob('*.sql'))},'previewPopulationSHA256':sha(encode(population)),'binding':'TEST_VECTOR_ONLY_NOT_INDEPENDENTLY_APPROVED','retainedR1Population':'Requires fresh identity and inventory binding from retained custody evidence; preview population is NOT interchangeable','newRecordDefault':False,'writers':{'existingProvisioning':'seed_sql omits required field; fenced before contract, final schema rejects','cloneImport':'no generic supported create/clone/import API; external writers not inventoried','existingUpdates':'generated Commands preserve unrelated note','newProvisioning':'explicit non-null String bytes, no default'},'recovery':'Transactional failure/interruption rolls back; restart reconciles state; no destructive rollback','decisions':[{'owner':'semantic/history project authority','required':'authenticated exact approved content proof; genuine accepted history and rebased plan, not preview anchor'},{'owner':'independent data-binding reviewer','required':'exact values for each retained tenant/resource bound to current inventory and database identity'},{'owner':'migration/security owner','required':'exact SQL hashes, writer fence/switch, preconditions, forward recovery or verified restore, isolated execution scope'}],'acceptedMigrationPlan':'NOT_APPROVED','retainedMigrationExecution':'NOT_AUTHORIZED','deployment':'NOT_AUTHORIZED','candidateModel':'UNSUPPORTED_BY_ORIGINAL_APPROVED_REFERENCE_BINDING','verification':'Preview runtime observations do not become registered Phase8 semantic PASS','release':'PHASE6_RELEASE_CLOSURE_BLOCKED'}


def restore_database(archive,output):
 """Read preserved custody archive; restore ONLY into a second newly owned DB."""
 import zipfile
 require(sha(archive.read_bytes())=='4d423b70bf57042aa1441add414cfdbfa9019de463ba61d9b0148226ccfdae61','CUSTODY_ARCHIVE_DIGEST')
 output.mkdir(mode=0o700,exist_ok=False)
 with zipfile.ZipFile(archive) as z:
  require(z.testzip() is None,'CUSTODY_CORRUPTION');inventory=json.loads(z.read('CUSTODY-CONTENT-INVENTORY.json'))
  dumps=[n for n in inventory if n.endswith('r1-new-case-database/database.sql')]
  require(len(dumps)==1,'CUSTODY_DUMP_IDENTITY');name=dumps[0];prefix=name.removesuffix('database.sql')
  members={}
  for suffix in ('database.sql','database-state.json','migration-history.json','database-identity.json'):
   raw=z.read(prefix+suffix);require(sha(raw)==inventory[prefix+suffix]['sha256'],'CUSTODY_MEMBER_DIGEST');members[suffix]=raw
 original=sha(archive.read_bytes());active=[]
 with demo.owned_database(active):
  db=DisposableSQL(active[0],output)
  # pg_dump is supplied as input only to the owned container, never executed on
  # an existing database or the host. The exact dump includes psql guard tokens.
  r=subprocess.run(['docker','exec','-i',active[0],'psql','-X','-U','acp_runtime','-d','acp_runtime','-v','ON_ERROR_STOP=1'],input=members['database.sql'],capture_output=True,timeout=60)
  (output/'restore.stdout').write_bytes(r.stdout);(output/'restore.stderr').write_bytes(r.stderr);require(r.returncode==0,'RESTORE_FAILED')
  actual=demo.database_state(active[0],SCHEMA);require(actual==json.loads(members['database-state.json']),'RESTORED_ROWS_MISMATCH');require(life.history(active[0])==json.loads(members['migration-history.json']),'RESTORED_MIGRATION_MISMATCH')
  identity=db.data("SELECT json_build_object('systemIdentifier',(SELECT system_identifier::text FROM pg_control_system()),'postgres',version())")
  require(identity['systemIdentifier']!=json.loads(members['database-identity.json'])['systemIdentifier'],'RESTORE_NOT_IN_NEW_CLUSTER')
  result={'archiveSHA256':original,'dumpSHA256':sha(members['database.sql']),'rowsAndTenantBytesExact':True,'auditAndIdempotencyExact':True,'limitations':['Original frozen JSON excludes volatile acp_sessions/acp_rate; dump restores those tables but does not provide independent pre-dump row equality evidence'],'historyExact':True,'rowCounts':{t:len(rows) for t,rows in actual.items()},'newDatabase':identity,'exit':r.returncode,'originalPopulation':{'databaseIdentitySHA256':sha(members['database-identity.json']),'populationSHA256':sha(members['database-state.json']),'caseRows':actual[TABLE],'caseCount':len(actual[TABLE]),'bindingValue':None,'bindingStatus':'NOT_APPROVED','provenance':'EXACT_IMMUTABLE_PHASE10_R1_CAPTURE_RESTORED_IN_DISPOSABLE_DB'}}
 require(sha(archive.read_bytes())==original,'CUSTODY_CHANGED');result['cleanup']='OWN_CONTAINER_REMOVED';life.save(output/'result.json',result);return result


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True,type=Path);p.add_argument('--maven-seed',type=Path);p.add_argument('--npm-seed',type=Path);p.add_argument('--offline',action='store_true');p.add_argument('--restore',type=Path);a=p.parse_args();qualify(a.workspace,maven_seed=a.maven_seed,npm_seed=a.npm_seed,offline=a.offline,restore=a.restore)
if __name__=='__main__':main()
