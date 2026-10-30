"""Reproducible Phase 6 internal demonstration using existing target/test adapters.

Trusted generator, disposable PostgreSQL and loopback-only test identity. Never
production deployment, accepted history, hostile-code isolation or release proof.
"""
import argparse
import ast
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.demo.pipeline import PipelineCandidate,inputs,request
from engineering.generator_builds import runtime as existing
from engineering.dependency_resolution.inputs import seed_maven
from engineering.dependency_resolution.qualify import package
from engineering.recovery.qualify import authenticated_database_ready,stop
from filesystem_artifacts import FilesystemArtifactStore
from compiler_core import _ownership
from compiler_contracts import Owner,wire
from engineering.security.qualification import package_inventory


def require(ok,code):
    if not ok:raise ValueError(code)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(path,value):path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
def command(args,cwd,log):existing.browser_gate.command(args,cwd,log)

def proxy_source(domain):
    # Reuse the exact existing loopback fixture, not a new application server.
    tree=ast.parse((ROOT/'tooling/check_task_interface.py').read_text())
    source=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and type(n.value) is str and 'http.createServer' in n.value and '.listen(4173' in n.value]
    require(len(source)==1,'PROXY_FIXTURE_IDENTITY')
    return source[0].replace('18080',str(18080 if domain=='payment' else 18081)).replace('listen(4173','listen('+str(4173 if domain=='payment' else 4174))

def stable_server(source):
    before='var now=Instant.now();return Jwt';require(source.count(before)==1,'TEST_AUTH_EVENT_BINDING')
    return source.replace(before,'var now=Instant.parse(System.getenv("ACP_DEMO_AUTH_EVENT"));return Jwt')

@contextmanager
def dependencies(workspace,maven_seed=None,npm_seed=None,offline=False):
    root=workspace.parent/(workspace.name+'-inputs');root.mkdir(mode=0o700,exist_ok=False)
    save(root/'owner.json',{'owner':'ACP Phase 6 internal demonstration','sourceWorkspace':str(ROOT),'classification':'TEMPORARY_EXECUTION','cleanup':'RETAIN_REQUIRED_EVIDENCE_BEFORE_REMOVAL'})
    reference=json.loads((ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json').read_bytes())
    if maven_seed is None:
        maven_seed=root/'empty-m2';maven_seed.mkdir(mode=0o700)
    seed_maven(maven_seed,root/'m2',reference,online=not offline)
    if npm_seed:shutil.copytree(npm_seed,root/'npm')
    else:(root/'npm').mkdir(mode=0o700)
    keys=('MAVEN_OPTS','npm_config_cache','npm_config_offline','ACP_DEMO_AUTH_EVENT','PLAYWRIGHT_BROWSERS_PATH')
    before={k:os.environ.get(k) for k in keys}
    try:
        os.environ.update(MAVEN_OPTS='-Dmaven.repo.local='+str(root/'m2'),npm_config_cache=str(root/'npm'),npm_config_offline='true' if offline else 'false',ACP_DEMO_AUTH_EVENT=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'))
        os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(root/'browsers')
        yield root
    finally:
        for k,v in before.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v

@contextmanager
def bind_owned_backend(active):
    original=subprocess.Popen
    def launch(args,*a,**kw):
        if isinstance(args,(list,tuple)) and 'acp.browser.BrowserServer' in args:
            require(len(active)==1 and active[0].startswith('acp-06-runtime-'),'NO_OWNED_DATABASE')
            env=kw['env'];url=env['ACP_DATABASE_URL'];base=os.environ['ACP_TEST_DATABASE_URL']
            require(url in (base+'?currentSchema=acp_browser_payment',base+'?currentSchema=acp_browser_case_management'),'UNOWNED_DATABASE_BINDING')
            extra=['--spring.datasource.url='+url,'--spring.datasource.username='+os.environ['ACP_TEST_DATABASE_USER'],'--spring.datasource.password='+os.environ['ACP_TEST_DATABASE_PASSWORD'],'--spring.flyway.url='+url,'--spring.flyway.user='+os.environ['ACP_TEST_DATABASE_USER'],'--spring.flyway.password='+os.environ['ACP_TEST_DATABASE_PASSWORD']]
            require(not any(str(x).startswith(('--spring.datasource.','--spring.flyway.url=','--spring.flyway.user=','--spring.flyway.password=')) for x in args),'DATABASE_OVERRIDE_COLLISION')
            args=[*args,*extra]
        return original(args,*a,**kw)
    subprocess.Popen=launch
    try:yield
    finally:subprocess.Popen=original

@contextmanager
def owned_database(active):
    with existing.database() as container:
        readiness=authenticated_database_ready(container,os.environ['ACP_TEST_DATABASE_PASSWORD'])
        active.append(container)
        try:yield container
        finally:active.clear()

class Session:
    def __init__(self,project,domain,logs):
        self.project,self.domain,self.logs=Path(project),domain,Path(logs)
        self.backend=self.project/'backend';self.front=self.project/'frontend'
        self.backend_port=18080 if domain=='payment' else 18081;self.frontend_port=4173 if domain=='payment' else 4174
        self.schema='acp_browser_'+domain.replace('-','_');self.process=None;self.front_process=None;self.processes=[];self.handles=[];self.sequence=0
        self.env=os.environ.copy();self.env.update(ACP_DATABASE_URL=os.environ['ACP_TEST_DATABASE_URL']+'?currentSchema='+self.schema,ACP_DATABASE_USER=os.environ['ACP_TEST_DATABASE_USER'],ACP_DATABASE_PASSWORD=os.environ['ACP_TEST_DATABASE_PASSWORD'],ACP_OIDC_ISSUER='https://test.invalid',ACP_OIDC_AUDIENCE='test')
    def launch(self):
        self.sequence+=1;log=(self.logs/f'demo-backend-{self.sequence}.log').open('wb');self.handles.append(log)
        cp='target/test-classes:target/classes:'+(self.backend/'target/browser-classpath').read_text().strip()
        args=['java','-cp',cp,'acp.browser.BrowserServer','--server.address=127.0.0.1','--server.port='+str(self.backend_port),'--spring.flyway.schemas='+self.schema,'--spring.flyway.default-schema='+self.schema,'--spring.flyway.clean-disabled=false','--acp.runtime.mode=development','--acp.runtime.poll-enabled=false','--acp.jobs.JOB-TASK.revision-3.credential-handle=browser-test-only']
        self.process=subprocess.Popen(args,cwd=self.backend,env=self.env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);self.processes.append(self.process)
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            require(self.process.poll() is None,'DEMO_BACKEND_EXIT')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.backend_port}/actuator/health',timeout=1) as r:
                    if json.load(r).get('status')=='UP':return self.process.pid
            except (OSError,ValueError):time.sleep(.1)
        raise TimeoutError('DEMO_BACKEND_READINESS')
    def start_frontend(self):
        (self.front/'browser-server.mjs').write_text(proxy_source(self.domain))
        log=(self.logs/'demo-frontend.log').open('wb');self.handles.append(log)
        self.front_process=subprocess.Popen(['node','browser-server.mjs'],cwd=self.front,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);self.processes.append(self.front_process)
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            require(self.front_process.poll() is None,'DEMO_FRONTEND_EXIT')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.frontend_port}/',timeout=1) as r:
                    if r.status==200:return
            except OSError:time.sleep(.1)
        raise TimeoutError('DEMO_FRONTEND_READINESS')
    def restart(self):
        old=self.process.pid;exit=stop(self.process);new=self.launch();require(new!=old,'NO_FRESH_JVM');return {'oldPid':old,'oldExit':exit,'newPid':new}
    def close(self):
        for p in reversed(self.processes):
            if p.poll() is None:stop(p)
        for f in self.handles:f.close()

JOURNEY=r'''import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import {ui} from '../src/task-ui-model';
const headers={Authorization:'Bearer browser-authorized'};
const commit=process.env.ACP_DEMO_COMMIT!;
const events=EVENTS;
test('actual generated task UI and committed recovery',async({page})=>{
 if(process.env.ACP_DEMO_PHASE==='commit'){
  expect((await page.request.post('/__test/reset',{headers})).status()).toBe(200);
  await page.goto('/');await page.getByRole('button',{name:'Select fixture-resource',exact:true}).click();
  await page.getByLabel('Task note').fill('internal demo 🦋');
  await page.getByRole('button',{name:'Complete task',exact:true}).click();
  const observed=page.waitForRequest(r=>r.url().includes(ui.actionPath)&&r.method()==='POST');
  const response=page.waitForResponse(r=>r.url().includes(ui.actionPath)&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Confirm',exact:true}).click();
  const sent=(await observed).postDataJSON();const result=await response;expect(result.status()).toBe(200);
  await expect(page.getByText('Task view: success',{exact:true})).toBeVisible();
  const facts=await (await page.request.get('/__test/facts',{headers})).json();
  expect(facts.events).toBe(events);expect(facts.idempotency).toBe(events);expect(facts.rows[0].text).toBe('internal demo 🦋');
  fs.writeFileSync(commit,JSON.stringify({request:sent,result:await result.json(),facts}));
 }else{
  const before=JSON.parse(fs.readFileSync(commit,'utf8'));
  await page.goto('/');await expect(page.locator('tbody')).toContainText('internal demo 🦋');
  const replay=await page.request.post(ui.actionPath,{headers,data:before.request});expect(replay.status()).toBe(200);expect(await replay.json()).toEqual(before.result);
  expect(await (await page.request.get('/__test/facts',{headers})).json()).toEqual(before.facts);
  expect((await page.request.post(ui.actionPath,{headers:{Authorization:'Bearer browser-outsider'},data:before.request})).status()).toBe(403);
  expect(await (await page.request.get('/__test/facts',{headers})).json()).toEqual(before.facts);
 }
 await page.screenshot({path:process.env.ACP_DEMO_SCREENSHOT!,fullPage:true});
});
'''

def database_state(container,schema):
    require(container.startswith('acp-06-runtime-') and schema in ('acp_browser_payment','acp_browser_case_management'),'UNOWNED_DATABASE_STATE')
    def query(sql):return json.loads(subprocess.check_output(['docker','exec',container,'psql','-U','acp_runtime','-d','acp_runtime','-v','ON_ERROR_STOP=1','-Atq','-c','SET search_path TO '+schema+';'+sql],text=True,timeout=20))
    tables=query("SELECT jsonb_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='"+schema+"' AND tablename NOT IN ('acp_rate','acp_sessions')")
    return {t:query('SELECT coalesce(jsonb_agg(to_jsonb(r) ORDER BY to_jsonb(r)::text),\'[]\') FROM "'+t+'" r') for t in tables}

def journey(session,phase):
    front=session.front;folder=front/'demo-tests';folder.mkdir(exist_ok=True)
    (folder/'restart.spec.ts').write_text(JOURNEY.replace('EVENTS','1' if session.domain=='payment' else '3'))
    config="import {defineConfig} from '@playwright/test';export default defineConfig({testDir:'./demo-tests',workers:1,retries:0,timeout:60000,use:{baseURL:'http://127.0.0.1:PORT',browserName:'chromium',viewport:{width:1280,height:900}},reporter:[['list'],['json',{outputFile:OUTPUT}]]});"
    report=session.logs/(phase+'-browser.json');(front/'demo.config.ts').write_text(config.replace('PORT',str(session.frontend_port)).replace('OUTPUT',json.dumps(str(report))))
    env=os.environ.copy();env.update(ACP_DEMO_PHASE=phase,ACP_DEMO_COMMIT=str(session.logs/'committed.json'),ACP_DEMO_SCREENSHOT=str(session.logs/(phase+'.png')))
    with (session.logs/(phase+'-browser.log')).open('wb') as log:subprocess.run(['npx','--no-install','playwright','test','--config=demo.config.ts'],cwd=front,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    value=json.loads(report.read_bytes());existing.verify_report(value,1);return value['stats']

def verify_replay_state(before,after,commit_times=None):
    # A fresh UI query must append its classification READ audit. Preserve every
    # prior row and require all new rows to match an already observed read scope.
    table='acp_classification_audit'
    require(set(before)==set(after),'REPLAY_TABLE_INVENTORY_CHANGED')
    for name in before:
        if name=='acp_idempotency':
            original={r['identity']:r for r in before[name]};current={r['identity']:r for r in after[name]}
            require(len(current)==len(after[name]) and set(original)==set(current),'REPLAY_IDEMPOTENCY_INVENTORY_CHANGED')
            for key,old in original.items():
                new=dict(current[key])
                # Existing InvocationCore lazily records the independently observed
                # PostgreSQL commit timestamp on the first successful replay.
                if old['commit_ns'] is None and new['commit_ns'] is not None:
                    require(old['status']=='COMMITTED_RESULT' and (commit_times or {}).get(old['commit_xid'])==new['commit_ns'],'REPLAY_COMMIT_TIMESTAMP_UNVERIFIED')
                    new['commit_ns']=None
                require(new==old,'REPLAY_IDEMPOTENCY_CHANGED')
        elif name!=table:require(before[name]==after[name],'REPLAY_CHANGED_TABLE:'+name)
    original={r['id']:r for r in before[table]};current={r['id']:r for r in after[table]}
    require(len(current)==len(after[table]) and all(current.get(k)==v for k,v in original.items()),'REPLAY_CLASSIFICATION_HISTORY_CHANGED')
    shape=lambda r:{k:v for k,v in r.items() if k not in ('id','occurred_at')}
    known=[shape(r) for r in original.values() if r['mode']=='READ']
    added=[r for k,r in current.items() if k not in original]
    require(all(r['mode']=='READ' and shape(r) in known for r in added),'REPLAY_UNEXPECTED_CLASSIFICATION_EFFECT')
    return len(added)

def restart_journey(project,domain,logs,container):
    session=Session(project,domain,logs)
    try:
        old=session.launch();session.start_frontend();first=journey(session,'commit');before=database_state(container,session.schema)
        expected=1 if domain=='payment' else 3
        require(len(before['acp_audit'])==expected and len(before['acp_outbox'])==expected and len(before['acp_idempotency'])==expected,'DEMO_BUSINESS_EFFECT_COUNTS')
        transition=session.restart();after=database_state(container,session.schema);require(after==before,'COMMITTED_STATE_CHANGED_ON_RESTART')
        second=journey(session,'replay');replayed=database_state(container,session.schema)
        save(logs/'replay-state.json',{'before':before,'afterRestart':after,'afterReplay':replayed})
        sql="SET search_path TO "+session.schema+";SELECT coalesce(jsonb_object_agg(commit_xid,(extract(epoch FROM pg_xact_commit_timestamp((mod(commit_xid::numeric,4294967296)::text)::xid))*1000000000)::numeric(30,0)),'{}') FROM acp_idempotency WHERE status='COMMITTED_RESULT';"
        times=json.loads(subprocess.check_output(['docker','exec',container,'psql','-U','acp_runtime','-d','acp_runtime','-Atq','-v','ON_ERROR_STOP=1','-c',sql],text=True,timeout=20))
        save(logs/'commit-time-observations.json',times)
        reads=verify_replay_state(before,replayed,times)
        save(logs/'restart-state.json',{'database':container,'schema':session.schema,'scope':'QUALIFICATION_ONLY','processes':transition,'before':before,'after':after,'commitBrowser':first,'replayBrowser':second,'committedCommandEffects':expected,'additionalAuthorizedReadAudits':reads})
        return {'restart':transition,'businessEffects':expected,'auditRows':expected,'idempotencyRows':expected,'browserTests':2,'failures':0,'skipped':0,'committedStatePreserved':True,'duplicateBusinessEffects':0}
    finally:session.close()

def build(project,logs):
    backend=project/'backend';front=project/'frontend'
    command(['mvn','-B','-ntp','test-compile','org.apache.maven.plugins:maven-jar-plugin:3.5.1:jar','org.springframework.boot:spring-boot-maven-plugin:4.1.1:repackage'],backend,logs/'production-backend.log')
    for goal in ('typecheck','test','build'):command(['npm','run',goal],front,logs/('production-frontend-'+goal+'.log'))
    report=package_inventory(project);raw,contents=package(project);(logs/'production.tar').write_bytes(raw)
    require(all(('tomcat-embed-' not in p or '-11.0.26.jar' in p) for p in report['lockedDependencies']),'PACKAGED_TOMCAT_NOT_PATCHED')
    report['distributionSHA256']=sha(raw);save(logs/'production-package.json',report);return report

def qualify(workspace):
    source_files=[Path(__file__),ROOT/'engineering/demo/pipeline.py',ROOT/'engineering/generator_builds/runtime.py',ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json']
    source_hashes={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in source_files}
    source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    active=[];instances=[];records={};source=existing.browser_gate.server_source
    def factory():
        candidate=PipelineCandidate();instances.append(candidate);return candidate
    @contextmanager
    def db():
        with owned_database(active) as container:yield container
    def browser(project,domain,logs):
        command(['npx','--no-install','playwright','install','chromium'],project/'frontend',logs/'browser-install.log')
        package_report=build(project,logs)
        report=existing.browser_gate.browser(project,domain,logs)
        save(logs/'business-browser.json',report)
        recovery=restart_journey(project,domain,logs,active[0]);records[domain]={'package':package_report,'browserRestart':recovery}
        return report
    try:
        existing.browser_gate.server_source=lambda domain:stable_server(source(domain))
        with bind_owned_backend(active):result=existing.runtime(workspace,candidate_factory=factory,browser_runner=browser,database_factory=db,request_factory=request)
    finally:existing.browser_gate.server_source=source
    require(set(records)=={'payment','case-management'} and not active,'DEMO_APPLICATION_COVERAGE_OR_DATABASE_LEAK')
    require(source_hashes=={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in source_files},'DEMO_SOURCE_CHANGED_DURING_EXECUTION')
    result.update(sourceCommit=source_commit,sourceHashes=source_hashes,python=sys.version,scope='QUALIFICATION_ONLY',engineering='ENGINEERING_VERIFIED',internalDemonstration='INTERNAL_DEMONSTRATION_READY',formalRelease='NOT_ACCEPTED',phase6='IN_PROGRESS',phase7='NOT_STARTED',closure='PHASE6_CLOSURE_BLOCKED',compilerExecutions=[row for c in instances for row in c.executions],demonstrations=records)
    save(Path(workspace)/'demonstration-results.json',result);print('INTERNAL_DEMONSTRATION_READY; FORMAL_RELEASE_NOT_ACCEPTED',flush=True);return result

def serve(workspace,domain):
    workspace.mkdir(mode=0o700,exist_ok=False);candidate,snapshot,req,plan=inputs(domain)
    project=workspace/domain;store=FilesystemArtifactStore(project);store.apply(plan);store.adopt_human('frontend/src/extensions/identity.ts')
    plan=candidate.plan(snapshot,req,inventory=store.inventory());store.apply(plan);candidate.verify_materialized(project,plan,snapshot,req)
    save(workspace/'compiler.json',candidate.executions)
    logs=workspace/'logs';logs.mkdir();front=project/'frontend';backend=project/'backend'
    command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],front,logs/'npm.log');build(project,logs)
    p=backend/'src/test/java/acp/browser/BrowserServer.java';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(stable_server(existing.browser_gate.server_source(domain)))
    command(['mvn','-B','-ntp','test-compile','dependency:build-classpath','-Dmdep.outputFile=target/browser-classpath'],backend,logs/'test-adapter.log')
    identity=front/'src/extensions/identity.ts';original=identity.read_bytes();identity.write_text(existing.browser_gate.IDENTITY)
    try:command(['npm','run','build'],front,logs/'test-frontend.log')
    finally:identity.write_bytes(original)
    active=[]
    with existing.supervised_processes(),owned_database(active),bind_owned_backend(active):
        session=Session(project,domain,logs)
        try:
            session.launch();session.start_frontend()
            # Reset only the newly constructed, owned test schema once.
            req_http=urllib.request.Request(f'http://127.0.0.1:{session.backend_port}/__test/reset',data=b'',headers={'Authorization':'Bearer browser-authorized'},method='POST')
            urllib.request.urlopen(req_http,timeout=30).close()
            print(f'INTERNAL TEST ONLY: http://127.0.0.1:{session.frontend_port} ; backend http://127.0.0.1:{session.backend_port} ; database {active[0]} ; schema {session.schema}',flush=True)
            while True:
                try:value=input('r + Enter restarts the backend; q + Enter stops and removes the disposable database: ').strip()
                except EOFError:break
                if value=='q':break
                if value=='r':print(json.dumps(session.restart()),flush=True)
        finally:session.close()
    save(workspace/'cleanup.json',{'database':'REMOVED','processes':'REAPED','executionFiles':'RETAINED_PENDING_CUSTODY'})

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['qualify','serve']);parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--domain',choices=['payment','case-management'],default='payment');parser.add_argument('--maven-seed',type=Path);parser.add_argument('--npm-seed',type=Path);parser.add_argument('--offline',action='store_true');args=parser.parse_args();workspace=args.workspace.absolute()
    if workspace.exists() or workspace.is_symlink():raise FileExistsError(workspace)
    with dependencies(workspace,args.maven_seed,args.npm_seed,args.offline):
        if args.mode=='serve':serve(workspace,args.domain)
        else:qualify(workspace)
