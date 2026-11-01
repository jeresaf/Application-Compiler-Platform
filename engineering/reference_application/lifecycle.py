"""Real Case Management R0 → R1 lifecycle; no semantic/release approval authority."""
import argparse,asyncio,copy,json,os,platform,shutil,socket,subprocess,sys
from contextlib import contextmanager
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.demo import reference as demo
from engineering.demo.pipeline import inputs
from engineering.generator_builds.runtime import supervised_processes,verify_report
from engineering.mcp_adapter.prepare import host as prepare_host
from engineering.source_intelligence.model import encode,sha,require,current,compare
from engineering.source_intelligence.analysis import analyze
from engineering.reference_application.inspection import HUMAN,extension_baseline,inspect,mcp_inspect
from compiler_contracts import fingerprint,Owner,wire
from filesystem_artifacts import FilesystemArtifactStore,StoreConflict
from target_worker import bundle_digest

DOMAIN='case-management'

def save(p,value):Path(p).write_bytes(encode(value))
def tree(root):return {p.relative_to(root).as_posix():sha(p.read_bytes()) for p in sorted(Path(root).rglob('*')) if p.is_file()}

def detach_outputs(project,expected,destination):
 """Retain declared build outputs and external fixtures before native publication."""
 destination=Path(destination);destination.mkdir(mode=0o700,exist_ok=False)
 for name in ('backend/target','frontend/node_modules','frontend/dist'):
  p=project/name
  if p.exists():
   q=destination/name;q.parent.mkdir(parents=True,exist_ok=True);p.rename(q)
 for p in sorted(project.rglob('*')):
  if p.is_file() and p.relative_to(project).as_posix() not in {*expected,'.acp-store.json'}:
   q=destination/'external'/p.relative_to(project);q.parent.mkdir(parents=True,exist_ok=True);p.rename(q)


def generated_outputs_equivalent(original,regenerated):
 values=[]
 for plan in (original,regenerated):
  value=wire(plan)
  for artifact in value['artifacts']:
   artifact.pop('expected_digest');artifact.pop('intent')
  values.append(value)
 require(values[0]==values[1],'REGENERATION_OUTPUT_BINDING_CHANGED')
 return {'originalPublicationPlanDigest':fingerprint(original),'regenerationPlanDigest':fingerprint(regenerated),'generatedOutputsEquivalent':True,'differenceScope':'CAS_EXPECTED_DIGEST_AND_PUBLICATION_INTENT_ONLY; EACH_FULL_PLAN_VERIFIED_SEPARATELY'}


def restore_modules(project,outputs):
 for name in ('frontend/node_modules',):
  p=Path(outputs)/name;q=project/name;require(p.is_dir() and not q.exists(),'BUILD_INPUT_RESTORE');p.rename(q)


def adapter_source():
 source=demo.stable_server(demo.existing.browser_gate.server_source(DOMAIN))
 from phase6_reference_tests import symbol
 marker='reset(){flyway.clean();'
 require(source.count(marker)==1,'RESET_FIXTURE_DRIFT')
 guard='reset(){if(jdbc.queryForObject("SELECT count(*) FROM '+symbol('CASE','e')+'",Integer.class)>0)throw new IllegalStateException("REFERENCE_ALREADY_INITIALIZED");flyway.clean();'
 source=source.replace(marker,guard,1)
 for endpoint in ('unicode','terminal','revoke'):
  needle='@PostMapping("/__test/'+endpoint+'")'
  require(source.count(needle)==1,'TEST_FIXTURE_ENDPOINT_DRIFT')
  source=''.join(line for line in source.splitlines(keepends=True) if needle not in line)
 return source


def build(project,logs):
 with supervised_processes():return build_inputs(project,logs)


def build_inputs(project,logs):
 logs.mkdir(mode=0o700,exist_ok=False)
 demo.build(project,logs)
 p=project/'backend/src/test/java/acp/browser/BrowserServer.java';require(not p.exists(),'ADAPTER_COLLISION');p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(adapter_source())
 demo.command(['mvn','-B','-ntp','test-compile','dependency:build-classpath','-Dmdep.outputFile=target/browser-classpath'],project/'backend',logs/'adapter-compile.log')
 original=(project/HUMAN).read_bytes()
 try:
  (project/HUMAN).write_text(demo.existing.browser_gate.IDENTITY);demo.command(['npm','run','build'],project/'frontend',logs/'disposable-identity-build.log')
 finally:(project/HUMAN).write_bytes(original)
 save(logs/'consumed-build.json',{'backendMainClasses':tree(project/'backend/target/classes'),'backendTestClasses':tree(project/'backend/target/test-classes'),'frontendDist':tree(project/'frontend/dist'),'externalAdapterSHA256':sha(p.read_bytes())})
 save(logs/'identity-adapter.json',{'scope':'DISPOSABLE_TRUSTED_JWT_COMPONENT_ADAPTER_NOT_CRYPTOGRAPHIC_AUTHENTICATION','sha256':sha(demo.existing.browser_gate.IDENTITY.encode())})


def journey(session,phase):
 original=demo.JOURNEY
 marker=' await page.screenshot'
 require(original.count(marker)==1,'LIFECYCLE_BROWSER_FIXTURE_DRIFT')
 extra="""
 if(process.env.ACP_DEMO_PHASE==='replay'){
  const committed=JSON.parse(fs.readFileSync(commit,'utf8'));
  expect((await page.request.post('/__test/reset',{headers})).status()).not.toBe(200);
  for(const token of ['invalid','browser-expired']){
   expect((await page.request.post(ui.queryPath,{headers:{Authorization:'Bearer '+token},data:{'QUERY-TEXT':''}})).status()).toBe(401);
  }
  expect(await (await page.request.get('/__test/facts',{headers})).json()).toEqual(committed.facts);
 }
"""
 try:
  demo.JOURNEY=original.replace(marker,extra+marker,1);result=demo.journey(session,phase)
  shutil.copyfile(session.front/'demo-tests/restart.spec.ts',session.logs/(phase+'-browser-source.spec.ts'));return result
 finally:demo.JOURNEY=original


def provision_reviewer(container,output):
 from phase6_reference_tests import seed_sql
 statements=[q.replace('fixture-resource','reviewer-resource') for q in seed_sql(DOMAIN)[2:]]
 require(statements,'REVIEWER_FIXTURE_EMPTY')
 demo.existing.docker('exec',container,'psql','-U','acp_runtime','-d','acp_runtime','-v','ON_ERROR_STOP=1','-c','SET search_path TO acp_browser_case_management;BEGIN;'+';'.join(statements)+';COMMIT;')
 save(output,{'scope':'EXPLICIT_SYNTHETIC_TEST_PROVISIONING_NOT_APPLICATION_CREATE_API','resource':'reviewer-resource','sqlSHA256':sha(';'.join(statements).encode())})


def reviewer_journey(session):
 source=r'''import {test,expect} from '@playwright/test';
import {ui} from '../src/task-ui-model';
const headers={Authorization:'Bearer browser-authorized'};
test('new authorized workflow after regeneration preserves the original case',async({page})=>{
 await page.goto('/');await page.getByRole('button',{name:'Select reviewer-resource',exact:true}).click();
 await page.getByLabel('Task note').fill('new case after regeneration');
 await page.getByRole('button',{name:'Complete task',exact:true}).click();
 const result=page.waitForResponse(r=>r.url().includes(ui.actionPath)&&r.request().method()==='POST');
 await page.getByRole('button',{name:'Confirm',exact:true}).click();expect((await result).status()).toBe(200);
 await expect(page.getByText('Task view: success',{exact:true})).toBeVisible();
 const facts=await (await page.request.get('/__test/facts',{headers})).json();
 expect(facts.events).toBe(6);expect(facts.idempotency).toBe(6);expect(facts.rows).toHaveLength(2);
 expect(facts.rows).toContainEqual({text:'internal demo 🦋',version:3,state:'STATE-ARCHIVED'});
 expect(facts.rows).toContainEqual({text:'new case after regeneration',version:3,state:'STATE-ARCHIVED'});
 await page.screenshot({path:process.env.ACP_DEMO_SCREENSHOT!,fullPage:true});
});
'''
 original=demo.JOURNEY
 try:
  demo.JOURNEY=source;result=demo.journey(session,'reviewer');shutil.copyfile(session.front/'demo-tests/restart.spec.ts',session.logs/'reviewer-browser-source.spec.ts');return result
 finally:demo.JOURNEY=original


def original_rows_preserved(before,after):
 require(set(before)==set(after),'POST_REGENERATION_TABLE_INVENTORY_CHANGED')
 for name,rows in before.items():require(all(row in after[name] for row in rows),'POST_REGENERATION_LOST_OR_CHANGED_ORIGINAL_ROW:'+name)


def history(container):
 sql="SELECT json_agg(t ORDER BY installed_rank) FROM (SELECT installed_rank,version,description,type,script,checksum,success FROM acp_browser_case_management.flyway_schema_history) t"
 return json.loads(demo.existing.docker('exec',container,'psql','-U','acp_runtime','-d','acp_runtime','-Atq','-v','ON_ERROR_STOP=1','-c',sql))


def freeze(container,folder):
 folder=Path(folder);folder.mkdir(mode=0o700,exist_ok=False)
 identity=json.loads(demo.existing.docker('exec',container,'psql','-U','acp_runtime','-d','acp_runtime','-Atqc',"SELECT json_build_object('database',current_database(),'databaseOid',(SELECT oid FROM pg_database WHERE datname=current_database()),'systemIdentifier',(SELECT system_identifier::text FROM pg_control_system()),'postgres',version(),'schema','acp_browser_case_management','schemaOid',(SELECT oid FROM pg_namespace WHERE nspname='acp_browser_case_management'))"));save(folder/'database-identity.json',identity)
 state=demo.database_state(container,'acp_browser_case_management');save(folder/'database-state.json',state);save(folder/'migration-history.json',history(container))
 with (folder/'database.sql').open('xb') as out:
  subprocess.run(['docker','exec',container,'pg_dump','-U','acp_runtime','-d','acp_runtime','--schema=acp_browser_case_management','--no-owner','--no-privileges'],stdout=out,check=True,timeout=60)
 return state


def commit_times(container):
 sql="SET search_path TO acp_browser_case_management;SELECT coalesce(jsonb_object_agg(commit_xid,(extract(epoch FROM pg_xact_commit_timestamp((mod(commit_xid::numeric,4294967296)::text)::xid))*1000000000)::numeric(30,0)),'{}') FROM acp_idempotency WHERE status='COMMITTED_RESULT';"
 return json.loads(demo.existing.docker('exec',container,'psql','-U','acp_runtime','-d','acp_runtime','-Atq','-v','ON_ERROR_STOP=1','-c',sql))


def evolution_request(population,output):
 directory=ROOT/'proposals/phase6-evolution-review';decision=ROOT/'targets/spring-vue-postgres/evidence/semantic-content-decisions/2026-10-12/case-management.json'
 d=json.loads(decision.read_bytes());manifest=json.loads((directory/'manifest.json').read_bytes())['domains'][DOMAIN]
 for suffix in ('change','canonical-candidate'):
  p=directory/f'case-management-{suffix}.json';require('sha256:'+sha(p.read_bytes())==manifest['files'][suffix],'R2_PROPOSAL_SUBSTITUTION')
 candidate=json.loads((directory/'case-management-canonical-candidate.json').read_bytes())
 from canonical_ir import validate_snapshot
 validate_snapshot(candidate);require(candidate['contentDigest']==d['candidateDigest']==manifest['candidateDigest'],'R2_CANDIDATE_BINDING')
 require(d['changeSetFileDigest']=='sha256:'+sha((directory/'case-management-change.json').read_bytes()),'R2_CHANGESET_BINDING')
 from phase6_reference_tests import symbol
 population_value=json.loads(Path(population).read_bytes());rows=population_value.get(symbol('CASE','e'))
 require(type(rows) is list,'R2_CASE_POPULATION_REQUIRED')
 inventory=[{'resourceStoredBytes':r[symbol('CASE-ID','f')],'tenantStoredBytes':r[symbol('CASE-TENANT','f')],'rowSHA256':sha(encode(r))} for r in rows]
 writer_paths=('tooling/phase6_reference_tests.py','tooling/invocation_reference_tests.py','engineering/reference_application/lifecycle.py')
 request={'schema':'acp-reference-evolution-request/1','status':'BLOCKED','semanticContent':d['status'],'previousDigest':d['previousDigest'],'candidateDigest':d['candidateDigest'],'changeSetFileDigest':d['changeSetFileDigest'],'semanticDecisionSHA256':sha(decision.read_bytes()),'populationSHA256':sha(Path(population).read_bytes()),'rowInventory':inventory,'rowCount':len(rows),'tenantCount':len({r['tenantStoredBytes'] for r in inventory}),'storageRepresentation':'EXACT_POSTGRESQL_JSON_BYTEA_REPRESENTATION_NO_NORMALIZATION','knownWriterSHA256':{p:sha((ROOT/p).read_bytes()) for p in writer_paths},'writerCoverage':'BOUNDED_REFERENCE_PROVISIONING_ONLY_EXTERNAL_WRITERS_NOT_INVENTORIED','population':'NEW_PHASE10_DISPOSABLE_REFERENCE_NOT_HISTORICAL_BINDING_POPULATION','populationIdentitySHA256':sha((Path(population).parent/'database-identity.json').read_bytes()) if (Path(population).parent/'database-identity.json').exists() else None,'requirement':d['requirement'],'field':d['field'],'compatibility':'REVIEW_REQUIRED_BREAKING_FINAL_SCHEMA','missing':['AUTHENTICATED_CONTENT_PROOF','GENUINE_ACCEPTED_HISTORY_AND_EXACT_REBASED_PLAN','INDEPENDENT_CURRENT_POPULATION_DATA_BINDING','EXACT_WRITER_ROLLOUT_SQL_RECOVERY_AND_EXECUTION_APPROVAL'],'compilerBoundary':'PipelineCandidate admits only the two original approved snapshots; accepting an evolved snapshot requires an authorized exact authority binding, not a whitelist bypass.','historicalBindingReusable':False,'newRecordDefault':False,'migrationExecuted':False,'responsibleAuthorities':['project semantic/history authority','independent data-binding reviewer','migration execution/security owner'],'nextDecision':'Supply authenticated proof for the exact existing approved-content ChangeSet and authorize genuine history plus a freshly measured population-specific binding and exact migration. No synthetic anchor or prior three-row population may be reused.'}
 save(output,request);return request


def qualify(workspace,*,phase7,phase8,maven_repo,browser_seed=None,reuse=None,serve=False):
 w=Path(workspace).absolute();require(not w.exists(),'WORKSPACE_COLLISION')
 # Fail before sending any fixture request if an existing service owns a port.
 for port in (18081,4174):
  with socket.socket() as sock:sock.bind(('127.0.0.1',port))
 require(subprocess.check_output(['node','--version'],text=True).strip()=='v24.21.0','WRONG_NODE_VERSION')
 w.mkdir(mode=0o700)
 save(w/'execution-owner.json',{'scope':'DISPOSABLE_PHASE10_QUALIFICATION_ONLY','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'paths':[str(w),str(w.parent/(w.name+'-inputs'))],'cleanup':'PROCESSES_AND_OWNED_DATABASE_REMOVED; EXECUTION_FILES_RETAINED','phase10':'IN_PROGRESS','release':'PHASE6_RELEASE_CLOSURE_BLOCKED'})
 foundation=prepare_host(w/'foundation',phase7,phase8,reuse);foundation_cfg=json.loads(foundation.read_bytes());cfg=foundation_cfg['applications'][DOMAIN]
 project=w/'application';shutil.copytree(Path(cfg['root']),project);store=FilesystemArtifactStore(project);candidate,snapshot,request,_=inputs(DOMAIN)
 original_baseline=Path(cfg['baseline']['path']);original_pin=sha(original_baseline.read_bytes())
 # An explicitly owned extension comment introduces no executable business rule.
 before=(project/HUMAN).read_bytes();(project/HUMAN).write_bytes(before+b'\n// Phase 10 reviewer-owned extension: preserve through regeneration.\n')
 plan=candidate.plan(snapshot,request,inventory=store.inventory());store.apply(plan);candidate.verify_materialized(project,plan,snapshot,request)
 baseline=w/'source-baseline.json';extension_baseline(original_baseline,project,baseline);expected=tree(project);human=(project/HUMAN).read_bytes()
 shutil.copytree(project,w/'r0-original-source');save(w/'canonical.json',snapshot.read());save(w/'r0-compiler.json',candidate.executions)
 demo.command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],project/'frontend',w/'npm.log')
 if browser_seed:
  target=Path(os.environ['PLAYWRIGHT_BROWSERS_PATH']);require(not target.exists(),'BROWSER_CACHE_COLLISION');shutil.copytree(browser_seed,target)
 demo.command(['npx','--no-install','playwright','install','chromium'],project/'frontend',w/'chromium.log')
 shared_modules=project/'frontend/node_modules';r0_outputs=w/'r0-analysis-build-inputs';r0_outputs.mkdir()
 # Native source scanning excludes only the declared dependency output.
 shared_modules.rename(r0_outputs/'node_modules')
 try:s0,m0,v0=inspect(project,baseline,w/'r0-inspection',maven_repo=maven_repo,node_modules=r0_outputs/'node_modules')
 finally:(r0_outputs/'node_modules').rename(shared_modules)
 asyncio.run(mcp_inspect(foundation,s0,w/'r0-inspection'))
 active=[];record={'toolchain':{'python':platform.python_version(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'java':subprocess.check_output(['java','--version'],text=True).strip()},'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'executionSources':{p.name:sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')},'scope':'QUALIFICATION_ONLY','canonicalDigest':snapshot.read()['contentDigest'],'generator':candidate.descriptor(),'sealedParent':bundle_digest(),'r2':None}
 with demo.owned_database(active),demo.bind_owned_backend(active):
  container=active[0];record['database']={'container':container,'schema':'acp_browser_case_management','image':demo.existing.IMAGE}
  session=None
  try:
   build(project,w/'r0-build');logs=w/'runtime/r0';logs.mkdir(parents=True);session=demo.Session(project,DOMAIN,logs)
   first=session.launch();session.start_frontend();journey(session,'commit');session.close();session=None;state0=freeze(container,w/'r0-database')
   require(len(state0['acp_audit'])==3 and len(state0['acp_idempotency'])==3 and len(state0['acp_outbox'])==3,'R0_BUSINESS_EFFECTS')
   old_history=history(container)
   detach_outputs(project,expected,w/'r0-build-outputs')
   # Prove unmanaged edits invalidate both native source observations and CAS.
   managed=project/'frontend/src/App.vue';original=managed.read_bytes();root_identity=project.stat().st_ino
   try:
    managed.write_bytes(original+b'\n<!-- unauthorized drift -->\n')
    try:current(m0,project)
    except ValueError:source_rejected=True
    else:raise ValueError('SOURCE_DRIFT_ACCEPTED')
    try:store.inventory()
    except StoreConflict as e:require(str(e)=='MANUAL_EDIT','WRONG_DRIFT_REJECTION')
    else:raise ValueError('MANAGED_EDIT_ACCEPTED')
    drift=analyze(project,baseline,sha(baseline.read_bytes()),maven_repo=Path(maven_repo),node_modules=w/'r0-build-outputs/frontend/node_modules',scratch=w)
    require(any(d['code']=='MODIFIED_GENERATED_FILE' for d in drift['drift']),'DRIFT_NOT_REPORTED');save(w/'rejected-drift.json',drift)
    require(project.stat().st_ino==root_identity,'REJECTED_DRIFT_PUBLISHED')
   finally:managed.write_bytes(original)
   plan1=candidate.plan(snapshot,request,inventory=store.inventory());save(w/'r1-artifact-plan.json',wire(plan1));store.apply(plan1)
   require(project.stat().st_ino!=root_identity,'NO_REAL_REGENERATION_PUBLICATION')
   candidate.verify_materialized(project,plan1,snapshot,request);require((project/HUMAN).read_bytes()==human,'HUMAN_EXTENSION_LOST')
   require(tree(project)==expected,'REGENERATION_SOURCE_CHANGED');require(sha(original_baseline.read_bytes())==original_pin,'ORIGINAL_BASELINE_CHANGED')
   s1,m1,v1=inspect(project,baseline,w/'r1-inspection',maven_repo=maven_repo,node_modules=w/'r0-build-outputs/frontend/node_modules')
   save(w/'source-comparison.json',compare(m0,m1));asyncio.run(mcp_inspect(foundation,s1,w/'r1-inspection'))
   equivalence=generated_outputs_equivalent(s1.plan,plan1);save(w/'plan-equivalence.json',equivalence)
   restore_modules(project,w/'r0-build-outputs');build(project,w/'r1-build')
   logs=w/'runtime/r1';logs.mkdir();shutil.copyfile(w/'runtime/r0/committed.json',logs/'committed.json')
   session=demo.Session(project,DOMAIN,logs);second=session.launch();session.start_frontend();require(second!=first,'BACKEND_NOT_RESTARTED')
   require(demo.database_state(container,session.schema)==state0,'RESTART_OR_MIGRATION_CHANGED_COMMITTED_DATA');require(history(container)==old_history,'MIGRATION_HISTORY_CHANGED')
   journey(session,'replay');session.close();session=None;state1=freeze(container,w/'r1-database');times=commit_times(container);save(w/'commit-times.json',times)
   read_audits=demo.verify_replay_state(state0,state1,times)
   require((w/'r0-database/database-identity.json').read_bytes()==(w/'r1-database/database-identity.json').read_bytes(),'DATABASE_IDENTITY_CHANGED')
   require(len(state1['acp_audit'])==3 and len(state1['acp_outbox'])==3 and len(state1['acp_idempotency'])==3,'DUPLICATE_BUSINESS_EFFECTS')
   record['retainedSecurityFindings']={'scope':'HISTORICAL_NOT_RESCANNED_NOT_A_CURRENT_PASS','fileSHA256':cfg['verification']['sha256'],'source':json.loads(Path(cfg['verification']['path']).read_bytes())['inputs'],'findings':[r for r in json.loads(Path(cfg['verification']['path']).read_bytes())['results'] if r['result']=='FAIL']}
   record['verificationScope']='Phase 8 current offline artifact integrity plus separately retained actual lifecycle execution; unregistered semantic behavior obligations remain NOT_RUN/BLOCKED.'
   record.update(r0={'sourceSHA256':sha(encode(expected)),'phase8':v0['summary'],'browserTests':1,'committedCommandEffects':3,'productionPackageSHA256':json.loads((w/'r0-build/production-package.json').read_bytes())['distributionSHA256'],'consumedBuildSHA256':sha((w/'r0-build/consumed-build.json').read_bytes())},r1={'kind':'UNCHANGED_SPECIFICATION_REGENERATION_NOT_SEMANTIC_EVOLUTION','originalPublicationPlanDigest':s1.b['artifactPlanDigest'],'artifactPlanDigest':fingerprint(plan1),'atomicPublication':True,'humanSHA256':sha(human),'phase8':v1['summary'],'browserTests':1,'restart':{'oldPid':first,'newPid':second},'businessEffects':3,'duplicates':0,'additionalAuthorizedReadAudits':read_audits,'migrationHistoryUnchanged':True,'databaseIdentityPreserved':True,'productionPackageSHA256':json.loads((w/'r1-build/production-package.json').read_bytes())['distributionSHA256'],'consumedBuildSHA256':sha((w/'r1-build/consumed-build.json').read_bytes())},r2=evolution_request(w/'r1-database/database-state.json',w/'r2-approval-request.json'))
   save(w/'compiler-executions.json',candidate.executions);save(w/'lifecycle-results.json',record)
   provision_reviewer(container,w/'reviewer-fixture.json')
   logs=w/'runtime/r1-new-case';logs.mkdir();session=demo.Session(project,DOMAIN,logs);new_case_pid=session.launch();session.start_frontend()
   if not serve:
    reviewer_journey(session);session.close();session=None;new_state=freeze(container,w/'r1-new-case-database');original_rows_preserved(state1,new_state)
    require(len(new_state['acp_audit'])==6 and len(new_state['acp_idempotency'])==6 and len(new_state['acp_outbox'])==6,'NEW_CASE_BUSINESS_EFFECT_COUNTS')
    record['r1']['newCaseWorkflow']={'browserTests':1,'processPid':new_case_pid,'newCommandEffects':3,'totalCommandEffects':6,'originalRowsPreserved':True,'scope':'EXISTING_SUPPORTED_UPDATE_WORKFLOW_AFTER_EXPLICIT_TEST_PROVISIONING'}
    record['r2']=evolution_request(w/'r1-new-case-database/database-state.json',w/'r2-new-population-approval-request.json')
    save(w/'lifecycle-results.json',record)
   if serve:
    print('DISPOSABLE CASE MANAGEMENT: http://127.0.0.1:4174 ; backend http://127.0.0.1:18081 ; r restarts, q stops and removes this database only.',flush=True)
    while True:
     try:choice=input().strip()
     except EOFError:break
     if choice=='q':break
     if choice=='r':print(json.dumps(session.restart()),flush=True)
    session.close();session=None;freeze(container,w/'serve-final-database');evolution_request(w/'serve-final-database/database-state.json',w/'serve-r2-approval-request.json')
  finally:
   if session:session.close()
 detach_outputs(project,expected,w/'r1-build-outputs');candidate.verify_materialized(project,plan1,snapshot,request);current(m1,project)
 record['cleanup']={'database':'REMOVED','processes':'REAPED','files':'RETAINED'};save(w/'lifecycle-results.json',record);return record


def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['qualify','serve']);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--phase7-archive',type=Path,required=True);p.add_argument('--phase8-archive',type=Path,required=True);p.add_argument('--maven-seed',type=Path);p.add_argument('--npm-seed',type=Path);p.add_argument('--browser-seed',type=Path);p.add_argument('--reuse-applications',type=Path);p.add_argument('--offline',action='store_true');a=p.parse_args();w=a.workspace.absolute()
 require(not w.exists() and not w.is_symlink(),'WORKSPACE_COLLISION')
 with demo.dependencies(w,a.maven_seed,a.npm_seed,a.offline) as dep:
  previous=os.environ.get('MAVEN_ARGS');os.environ['MAVEN_ARGS']='-o'
  try:result=qualify(w,phase7=a.phase7_archive,phase8=a.phase8_archive,maven_repo=dep/'m2',browser_seed=a.browser_seed,reuse=a.reuse_applications,serve=a.mode=='serve');print(json.dumps(result,sort_keys=True))
  finally:
   if previous is None:os.environ.pop('MAVEN_ARGS',None)
   else:os.environ['MAVEN_ARGS']=previous
if __name__=='__main__':main()
