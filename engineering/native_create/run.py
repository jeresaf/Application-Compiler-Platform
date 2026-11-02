"""Native CREATE browser/restart qualification, fresh synthetic database only."""
import argparse,json,os,shutil,socket,subprocess,platform
from pathlib import Path
from engineering.native_create import application as target
from engineering.reference_application import lifecycle as life
from engineering.native_create.preview import Preview
from engineering.reference_application.evolution import api,offline_maven
from engineering.demo import reference as demo
from engineering.source_intelligence import native
from engineering.source_intelligence.model import encode,sha,require
from engineering.verification.integration import seal,summary,validate_result
from compiler_contracts import fingerprint,wire
from phase6_reference_tests import seed_sql,symbol

JOURNEY=r'''import {test,expect} from '@playwright/test';
import fs from 'node:fs';import {ui} from '../src/task-ui-model';
const headers={Authorization:'Bearer browser-authorized'},path='/api/create_0a45ec9f1fe282a282b6a21f';
const saved=process.env.ACP_DEMO_COMMIT!;
test('generated intake through workflow and restart without duplicate creation',async({page})=>{
 await page.goto('/');
 if(process.env.ACP_DEMO_PHASE==='commit'){
  let sent=0;page.on('request',r=>{if(r.url().endsWith(path))sent++;});
  await page.getByRole('button',{name:'Create case',exact:true}).click();expect(sent).toBe(0);
  await page.getByLabel('title',{exact:true}).fill('x'.repeat(201));await page.getByLabel('summary',{exact:true}).fill('intake é 🦋');
  await page.getByRole('button',{name:'Create case',exact:true}).click();await expect(page.getByText('Invalid intake input',{exact:true})).toBeVisible();expect(sent).toBe(0);
  await page.getByLabel('title',{exact:true}).fill('R4 case 🦋');
  await page.evaluate(()=>(window as any).testIdentity('expired'));const denied=page.waitForResponse(r=>r.url().endsWith(path));
  await page.getByRole('button',{name:'Create case',exact:true}).click();expect((await denied).status()).toBe(401);await expect(page.getByText('Creation failed',{exact:true})).toBeVisible();
  await page.evaluate(()=>(window as any).testIdentity('authorized'));
  const pending=page.waitForResponse(r=>r.url().endsWith(path)&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Create case',exact:true}).click();const response=await pending;expect(response.status()).toBe(200);
  const result=await response.json(),request=response.request().postDataJSON();expect(result.version).toBe(0);expect(result.state).toBe('STATE-OPEN');
  await expect(page.getByText('Case created',{exact:true})).toBeVisible();
  const replay=await page.request.post(path,{headers,data:request});expect(replay.status()).toBe(200);expect(await replay.json()).toEqual(result);
  const peers=await Promise.all([page.request.post(path,{headers,data:request}),page.request.post(path,{headers,data:request})]);for(const peer of peers){expect(peer.status()).toBe(200);expect(await peer.json()).toEqual(result);}
  expect((await page.request.post(path,{headers,data:{...request,summary:'changed'}})).status()).toBe(409);
  for(const data of [{idempotencyKey:'bad'}, {...request,title:null},{...request,title:23},{...request,title:'x'.repeat(201)},{...request,tenant:'tenant-two'}])expect((await page.request.post(path,{headers,data})).status()).toBe(400);
  for(const [token,status] of [['browser-outsider',403],['browser-wrong-tenant',403],['invalid',401],['browser-expired',401]])expect((await page.request.post(path,{headers:{Authorization:'Bearer '+token},data:{...request,idempotencyKey:token}})).status()).toBe(status);
  const originalRows=await (await page.request.post(ui.queryPath,{headers,data:{'QUERY-TEXT':''}})).json();expect(originalRows).toHaveLength(1);expect(originalRows[0].resourceId).toBe(result.resourceId);expect(originalRows[0].output[ui.outputField]).toBe('intake é 🦋');
  await page.getByRole('button',{name:'Search',exact:true}).click();await page.getByRole('button',{name:'Select '+result.resourceId,exact:true}).click();
  await page.getByLabel('Task note').fill('reviewed after intake');await page.getByRole('button',{name:'Complete task',exact:true}).click();
  const action=page.waitForResponse(r=>r.url().includes(ui.actionPath)&&r.request().method()==='POST');await page.getByRole('button',{name:'Confirm',exact:true}).click();expect((await action).status()).toBe(200);
  await expect(page.getByText('Task view: success',{exact:true})).toBeVisible();
  const facts=await (await page.request.get('/__test/facts',{headers})).json();expect(facts.rows).toEqual([{text:'reviewed after intake',version:3,state:'STATE-ARCHIVED'}]);expect(facts.events).toBe(3);expect(facts.idempotency).toBe(4);
  fs.writeFileSync(saved,JSON.stringify({request,result,facts}));
 }else{
  const before=JSON.parse(fs.readFileSync(saved,'utf8'));await expect(page.locator('tbody')).toContainText('reviewed after intake');
  const replay=await page.request.post(path,{headers,data:before.request});expect(replay.status()).toBe(200);expect(await replay.json()).toEqual(before.result);
  expect(await (await page.request.get('/__test/facts',{headers})).json()).toEqual(before.facts);
 }
 await page.screenshot({path:process.env.ACP_DEMO_SCREENSHOT!,fullPage:true});
});'''

def qualify(workspace,*,maven_seed=None,npm_seed=None,browser_seed=None,offline=False):
 executor_sources={str(p.relative_to(life.ROOT)):sha(p.read_bytes()) for p in [Path(__file__),*sorted(Path(target.__file__).parent.glob('*.py')),*target.TEMPLATES.iterdir()]}
 w=Path(workspace).absolute();require(not w.exists(),'WORKSPACE_COLLISION')
 for port in (18081,4174):
  with socket.socket() as sock:sock.bind(('127.0.0.1',port))
 w.mkdir(mode=0o700);life.save(w/'execution-owner.json',{'scope':'UNAPPROVED_NATIVE_CREATE_PREVIEW','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'workspace':str(w),'inputs':str(w.parent/(w.name+'-inputs')),'acceptedTransition':False,'retainedR2Migration':False,'cleanup':'PLANNED_OWN_RESOURCES_ONLY; FINAL_RESULT_RECORD_REQUIRED'})
 c,s,r,p=target.materialize(w/'application');root=w/'application';store=target.FilesystemArtifactStore(root);store.adopt_human(life.HUMAN);(root/life.HUMAN).write_bytes((root/life.HUMAN).read_bytes()+b'\n// R4 native preview extension retained.\n');human=(root/life.HUMAN).read_bytes();p=c.plan(s,r,store.inventory());store.apply(p);c.verify_materialized(root,p,s,r);require((root/life.HUMAN).read_bytes()==human,'INTAKE_HUMAN_LOST');expected=life.tree(root)
 life.save(w/'compilation-request.json',wire(r));life.save(w/'compilation-audit.json',wire(c.audit));life.save(w/'artifact-plan.json',wire(p));life.save(w/'candidate.json',s.read());life.save(w/'target-ir.json',wire(c.lower(s,r)))
 preview=Preview(c,s,r,p,c.audit,root)
 with demo.dependencies(w,maven_seed,npm_seed,offline) as deps,offline_maven():
  demo.command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],root/'frontend',w/'npm.log')
  if browser_seed:shutil.copytree(browser_seed,Path(os.environ['PLAYWRIGHT_BROWSERS_PATH']))
  demo.command(['npx','--no-install','playwright','install','chromium'],root/'frontend',w/'chromium.log')
  # Exact compiled native preview; original approved admission stays unchanged.
  facts=w/'source-facts';facts.mkdir()
  baseline=facts/'baseline.json';baseline.write_bytes(preview.document)
  model=preview.analyze(baseline,maven_repo=deps/'m2',node_modules=root/'frontend/node_modules',scratch=facts)
  model_path=facts/'source-model.json';model_path.write_bytes(encode(model))
  verification_session=preview.session(baseline,model_path)
  require(any(m['semantic']['id']=='CREATE-CASE' for m in model['semanticMappings']),'CREATE_SOURCE_SYMBOL_MAPPING')
  life.save(facts/'binding.json',{'scope':'UNAPPROVED_NATIVE_CREATE_PREVIEW','canonicalDigest':s.read()['contentDigest'],'sourceModelDigest':model['digest'],'files':expected,'limitations':['Vue SFC bodies remain partial in the existing analyzer','Inherited dependency/security findings remain unresolved; no rescan, suppression or production acceptance']})
  original=life.adapter_source;source=original();needle='jdbc.execute('+json.dumps(seed_sql('case-management')[2])+');';require(source.count(needle)==1,'INTAKE_PREREQUISITE_FIXTURE_DRIFT');source=source.replace(needle,'')
  try:life.adapter_source=lambda:source;life.build(root,w/'build')
  finally:life.adapter_source=original
  active=[];session=None;record={'scope':'QUALIFICATION_ONLY','tools':{'python':platform.python_version(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'java':subprocess.check_output(['java','--version'],text=True).strip()},'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'sourceSHA256':executor_sources,'candidateDigest':s.read()['contentDigest'],'generator':c.descriptor(),'sealed05':life.bundle_digest(),'acceptedSemanticTransition':False}
  with demo.owned_database(active),demo.bind_owned_backend(active):
   container=active[0];logs=w/'runtime';logs.mkdir();session=demo.Session(root,'case-management',logs);session.env['ACP_INTAKE_MODE']='synthetic-preview'
   try:
    first=session.launch();session.start_frontend();require(api(session,'/__test/reset',{})[0]==200,'INTAKE_PREREQUISITES');require(api(session,'/__test/facts')[1]['rows']==[],'FIXTURE_CREATED_BUSINESS_ROW')
    previous=demo.JOURNEY
    try:
     demo.JOURNEY=JOURNEY;a=demo.journey(session,'commit');state=demo.database_state(container,'acp_browser_case_management');history=life.history(container)
     restart=session.restart();b=demo.journey(session,'replay');after=demo.database_state(container,'acp_browser_case_management');demo.verify_replay_state(state,after,life.commit_times(container));require(history==life.history(container),'INTAKE_HISTORY_CHANGED')
    finally:demo.JOURNEY=previous
    require(len(after['acp_audit'])==4 and len(after['acp_outbox'])==3 and len(after['acp_idempotency'])==4,'INTAKE_AUDIT_OUTBOX_IDEMPOTENCY_COUNTS')
    saved=json.loads((logs/'committed.json').read_bytes());require(len([a for a in after['acp_audit'] if a['operation']=='CREATE-CASE' and a['resource']==chr(92)+'x'+saved['result']['resourceId'].encode().hex()])==1,'INTAKE_CREATION_AUDIT_LINKAGE');record.update(database=container,browser=[a,b],restart=restart,created=saved['result'],facts=saved['facts'])
    rows=after[symbol('CASE','e')];require(len(rows)==1,'INTAKE_ROW_COUNT');row=rows[0]
    decode=lambda name:bytes.fromhex(row[symbol(name,'f')].removeprefix('\\x')).decode('utf8')
    require(decode('CASE-ID')==saved['result']['resourceId'] and decode('CASE-TENANT')=='tenant-one' and decode('CASE-ASSIGNEE')=='fixture:operator','INTAKE_STORED_IDENTITY_BINDING')
    require(json.loads(decode('FLD-CASE-TITLE'))=={'FLD-TITLE':'R4 case 🦋'} and decode('FLD-TASK-SUMMARY')=='reviewed after intake' and row[symbol('FLD-NOTE','f')] is None and not row[symbol('FLD-NOTE','present')],'INTAKE_STORED_VALUES')
    record['storedValuesVerified']=True
    # Durable SessionGate revocation remains active for creation after restart.
    demo.existing.docker('exec',container,'psql','-U','acp_runtime','-d','acp_runtime','-v','ON_ERROR_STOP=1','-c','SET search_path TO acp_browser_case_management;UPDATE acp_sessions SET revoked=true;')
    require(api(session,'/api/create_0a45ec9f1fe282a282b6a21f',{**saved['request'],'idempotencyKey':'revoked'})[0]==403,'INTAKE_REVOCATION_BYPASS');record['revokedStatus']=403
    session.close();session=None;life.freeze(container,w/'database')
   finally:
    if session:session.close()
  require(all(sha((root/n).read_bytes())==h for n,h in expected.items()),'INTAKE_SOURCE_DRIFT')
  life.detach_outputs(root,expected,w/'build-outputs');c.verify_materialized(root,p,s,r)
  require(record['sourceSHA256']=={n:sha((life.ROOT/n).read_bytes()) for n in record['sourceSHA256']},'INTAKE_EXECUTOR_DRIFT');record['cleanup']={'database':'REMOVED','processes':'REAPED'};life.save(w/'cleanup.json',record['cleanup'])
  record['semanticApproval']='NOT_APPROVED'
  record['securityAssessment']='NOT_RERUN; EXISTING_FINDINGS_REMAIN_UNRESOLVED'
  result=verification_session.evaluate()
  require(all(row['result']=='PASS' for row in result['results'] if row['kind']=='ARTIFACT_VERIFICATION'),'CREATE_ARTIFACT_VERIFICATION')
  rows=result['results']+[{'id':'native-create-runtime','kind':'SYNTHETIC_RUNTIME','result':'PASS','origins':[{'application':r.application,'id':'CREATE-CASE','revision':1}],'artifacts':['backend/src/main/java/acp/api/IntakeController.java','frontend/src/IntakeForm.vue'],'obligation':None,'reasons':[],'observation':{'sourceCommit':record['sourceCommit'],'sourceSHA256':record['sourceSHA256'],'browser':record['browser'],'created':record['created'],'restart':record['restart'],'cleanup':record['cleanup']}}]
  v=seal({**{k:value for k,value in result.items() if k!='digest'},'results':rows,'summary':summary(rows)})
  validate_result(v);life.save(facts/'verification-result.json',v)
  plan={'schema':'acp-mcp-plan/1','inputs':verification_session.inputs,'artifactPlanDigest':fingerprint(p),'targetIdentity':verification_session.target.target,'artifacts':[{'path':a.path,'sha256':expected[a.path],'ownership':str(a.owner),'origins':wire(a.mappings),'verification':list(a.verification)} for a in p.artifacts]}
  life.save(facts/'plan.json',plan);life.save(facts/'snapshot.json',s.read())
  cfg={'schema':'acp-native-create-mcp-host/1','namespace':'case-management-create-preview','application':{'root':str(root),**{key:{'path':str(path.absolute()),'sha256':sha(path.read_bytes())} for key,path in [('baseline',baseline),('model',model_path),('verification',facts/'verification-result.json'),('plan',facts/'plan.json'),('snapshot',facts/'snapshot.json')]}}}
  life.save(facts/'mcp-host.json',cfg)
  record['mcp']=life.asyncio.run(inspect_mcp(facts/'mcp-host.json',facts))
  life.save(w/'verification.json',v);life.save(w/'result.json',record)
 return record

async def inspect_mcp(config,folder):
 from mcp import Client
 from mcp.client.stdio import StdioServerParameters
 import sys
 parameters=StdioServerParameters(command=sys.executable,args=['-B','-m','engineering.native_create.mcp','--host-config',str(config)],cwd=str(life.ROOT))
 rows=[]
 async with Client(parameters,read_timeout_seconds=120) as client:
  listing=await client.list_tools();require(len(listing.tools)==9,'CREATE_MCP_TOOL_DISCOVERY')
  for operation,args in [('project.summary',{}),('spec.validate',{}),('spec.query',{'ids':['CREATE-CASE']}),('project.context',{'ids':['CREATE-CASE']}),('source.symbol',{'ids':['CREATE-CASE']}),('source.impact',{'ids':['CREATE-CASE']}),('compiler.plan',{'ids':['CREATE-CASE']}),('compiler.verify',{'ids':['CREATE-CASE']}),('compiler.verify',{'status':'BLOCKED'})]:
   result=await client.call_tool(operation,{'application':'case-management-create-preview',**args})
   require(not result.is_error,'CREATE_MCP_INSPECTION');rows.append({'operation':operation,'result':result.structured_content})
  denied=await client.call_tool('spec.query',{'application':'case-management','ids':['CREATE-CASE']})
  require(denied.is_error,'CREATE_MCP_APPROVED_ALIAS_REJECTED')
 life.save(folder/'mcp-results.json',rows)
 return {'calls':len(rows),'approvedAliasRejected':True,'scope':'UNAPPROVED_SYNTHETIC_CREATE_PREVIEW'}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True,type=Path);p.add_argument('--maven-seed',type=Path);p.add_argument('--npm-seed',type=Path);p.add_argument('--browser-seed',type=Path);p.add_argument('--offline',action='store_true');a=p.parse_args();qualify(a.workspace,maven_seed=a.maven_seed,npm_seed=a.npm_seed,browser_seed=a.browser_seed,offline=a.offline)
if __name__=='__main__':main()
