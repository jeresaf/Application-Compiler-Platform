"""Actual reporting qualification: generated queries, existing fixtures, owned DB."""
import argparse,asyncio,json,os,platform,shutil,socket,subprocess,sys
from pathlib import Path
from engineering.documents import application as target
from engineering.documents.inspection import Preview,NAMESPACE
from engineering.documents.target import PACKAGE
from engineering.native_create.run import JOURNEY as CREATE_JOURNEY
from engineering.reference_application import lifecycle as life
from engineering.reference_application.evolution import api,offline_maven
from engineering.demo import reference as demo
from engineering.source_intelligence.model import sha,encode,require,current
from compiler_contracts import fingerprint,wire
from filesystem_artifacts import FilesystemArtifactStore,StoreConflict
from phase6_reference_tests import seed_sql
from engineering.verification.integration import seal,summary


from engineering.reporting.run import adapter_source as parent_adapter
TABLE='d_'+__import__('hashlib').sha256(b'DOC-ATTACHMENTS').hexdigest()[:24]
def adapter_source():
 source=parent_adapter();marker='@GetMapping("/__test/facts")';require(source.count(marker)==1,'DOCUMENT_FIXTURE_MARKER')
 facts='SELECT id::text,idempotency_key AS retry_key,convert_from(tenant,\'UTF8\') AS tenant,convert_from(resource,\'UTF8\') AS resource,filename,size,sha256,encode(content,\'hex\') AS content FROM '+TABLE+' ORDER BY id'
 tamper="UPDATE "+TABLE+" SET content=set_byte(content,0,get_byte(content,0)#1) WHERE filename='evidence.txt'"
 enable="CREATE FUNCTION acp_test_document_failure() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'CONTROLLED_DOCUMENT_FAILURE';END$$;CREATE TRIGGER acp_test_document_failure BEFORE INSERT ON acp_audit FOR EACH ROW WHEN (NEW.operation='PERM-DOC-UPLOAD') EXECUTE FUNCTION acp_test_document_failure()"
 disable="DROP TRIGGER IF EXISTS acp_test_document_failure ON acp_audit;DROP FUNCTION IF EXISTS acp_test_document_failure()"
 methods='@GetMapping("/__test/document-facts") Map<String,Object> documentFacts(){return Map.of("rows",jdbc.queryForList('+json.dumps(facts)+'),"uploads",jdbc.queryForObject("SELECT count(*) FROM acp_audit WHERE operation=\'PERM-DOC-UPLOAD\'",Integer.class),"links",jdbc.queryForObject("SELECT count(*) FROM '+TABLE+'_audit",Integer.class));}\n'
 methods+='@PostMapping("/__test/document-tamper") Map<String,Object> documentTamper(){jdbc.execute('+json.dumps(tamper)+');return Map.of("tampered",true);}\n'
 methods+='@PostMapping("/__test/document-fail") Map<String,Object> documentFail(@RequestBody Map<String,Boolean> body){jdbc.execute(Boolean.TRUE.equals(body.get("enabled"))?'+json.dumps(enable)+':'+json.dumps(disable)+');return Map.of("configured",true);}\n'
 return source.replace(marker,methods+marker)

def journey(session,source,phase):
 previous=demo.JOURNEY
 try:demo.JOURNEY=source;result=demo.journey(session,phase)
 finally:demo.JOURNEY=previous
 life.save(session.logs/(phase+'-source.json'),{'sha256':sha(source.encode()),'scope':'ACTUAL_HTTP_BROWSER_NOT_MOCKED'})
 return result

def inspect(c,s,r,p,root,folder,m2,modules):
 folder.mkdir(mode=0o700);preview=Preview(c,s,r,p,c.audit,root);baseline=folder/'baseline.json';baseline.write_bytes(preview.document)
 model=preview.analyze(baseline,maven_repo=m2,node_modules=modules,scratch=folder)
 path=folder/'source-model.json';path.write_bytes(encode(model));require(any(m['semantic']['id']=='REPORT-CASES' for m in model['semanticMappings']),'DOCUMENT_NATIVE_SOURCE_MAPPING')
 return preview.session(baseline,path)

async def mcp_inspect(session,folder,result):
 from mcp import Client
 from mcp.client.stdio import StdioServerParameters
 life.save(folder/'verification-result.json',result);life.save(folder/'snapshot.json',session.snapshot.read())
 plan={'schema':'acp-mcp-plan/1','inputs':session.inputs,'artifactPlanDigest':fingerprint(session.plan),'targetIdentity':session.target.target,'artifacts':[{'path':a.path,'sha256':session.b['files'][a.path]['sha256'],'ownership':str(a.owner),'origins':wire(a.mappings),'verification':list(a.verification)} for a in session.plan.artifacts]};life.save(folder/'plan.json',plan)
 cfg={'schema':'acp-document-mcp-host/1','namespace':NAMESPACE,'application':{'root':str(session.root),**{key:{'path':str(p.absolute()),'sha256':sha(p.read_bytes())} for key,p in [('baseline',session.baseline),('model',session.model_path),('verification',folder/'verification-result.json'),('plan',folder/'plan.json'),('snapshot',folder/'snapshot.json')]}}};life.save(folder/'mcp-host.json',cfg)
 params=StdioServerParameters(command=sys.executable,args=['-B','-m','engineering.documents.mcp','--host-config',str(folder/'mcp-host.json')],cwd=str(life.ROOT));rows=[]
 async with Client(params,read_timeout_seconds=120) as client:
  tools=await client.list_tools();require(len(tools.tools)==9,'DOCUMENT_MCP_TOOL_COUNT')
  for name,args in [('project.summary',{}),('spec.validate',{}),('spec.query',{'ids':['DOC-ATTACHMENTS','PERM-DOC-UPLOAD']}),('project.context',{'ids':['DOC-ATTACHMENTS']}),('source.symbol',{'ids':['DOC-ATTACHMENTS']}),('source.impact',{'ids':['DOC-ATTACHMENTS']}),('compiler.plan',{'ids':['DOC-ATTACHMENTS']}),('compiler.verify',{'ids':['DOC-ATTACHMENTS']}),('compiler.verify',{'status':'BLOCKED'})]:
   response=await client.call_tool(name,{'application':NAMESPACE,**args});require(not response.is_error,'DOCUMENT_MCP_CALL');rows.append({'tool':name,'result':response.structured_content})
  denied=await client.call_tool('spec.query',{'application':'case-management','ids':['DOC-ATTACHMENTS']});require(denied.is_error,'DOCUMENT_APPROVED_ALIAS')
 life.save(folder/'mcp-results.json',rows);return {'calls':len(rows),'approvedAliasRejected':True}

def qualify(workspace,*,maven_seed=None,npm_seed=None,browser_seed=None,offline=False):
 w=Path(workspace).absolute();require(not w.exists(),'WORKSPACE_COLLISION')
 for port in (18081,4174):
  with socket.socket() as sock:sock.bind(('127.0.0.1',port))
 sources={str(p.relative_to(life.ROOT)):sha(p.read_bytes()) for p in [*sorted(PACKAGE.rglob('*.py')),*sorted((PACKAGE/'templates').glob('*')),PACKAGE/'journey.ts',life.ROOT/'engineering/compiler_extensions/dispatch.py'] if p.is_file()}
 w.mkdir(mode=0o700);life.save(w/'execution-owner.json',{'scope':'UNAPPROVED_DOCUMENT_PREVIEW','workspace':str(w),'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'cleanup':'PLANNED_OWN_RESOURCES_ONLY','historyAccepted':False,'deploymentAuthorized':False})
 c,s,r,p=target.materialize(w/'application');root=w/'application';store=FilesystemArtifactStore(root);store.adopt_human(life.HUMAN);(root/life.HUMAN).write_bytes((root/life.HUMAN).read_bytes()+b'\n// R6 nonsemantic owner extension.\n');human=(root/life.HUMAN).read_bytes();p=c.plan(s,r,store.inventory());store.apply(p);c.verify_materialized(root,p,s,r);expected=life.tree(root)
 life.save(w/'candidate.json',s.read());life.save(w/'compilation-request.json',wire(r));life.save(w/'r0-audit.json',wire(c.audit));life.save(w/'r0-plan.json',wire(p))
 # Strict custody binding is captured before node_modules/build output exists.
 initial_preview=Preview(c,s,r,p,c.audit,root)
 with demo.dependencies(w,maven_seed,npm_seed,offline) as deps,offline_maven():
  demo.command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],root/'frontend',w/'npm.log')
  if browser_seed:shutil.copytree(browser_seed,Path(os.environ['PLAYWRIGHT_BROWSERS_PATH']))
  demo.command(['npx','--no-install','playwright','install','chromium'],root/'frontend',w/'chromium.log')
  folder=w/'r0-inspection';folder.mkdir();b=folder/'baseline.json';b.write_bytes(initial_preview.document);m=initial_preview.analyze(b,maven_repo=deps/'m2',node_modules=root/'frontend/node_modules',scratch=folder);mp=folder/'source-model.json';mp.write_bytes(encode(m));session0=initial_preview.session(b,mp)
  require(any(x['semantic']['id']=='REPORT-CASES' for x in m['semanticMappings']),'DOCUMENT_SOURCE_MAPPING')
  original=life.adapter_source
  try:life.adapter_source=adapter_source;life.build(root,w/'r0-build')
  finally:life.adapter_source=original
  active=[];session=None;results=[]
  with demo.owned_database(active),demo.bind_owned_backend(active):
   container=active[0];logs=w/'runtime';logs.mkdir()
   try:
    session=demo.Session(root,'case-management',logs);session.env.update(ACP_INTAKE_MODE='synthetic-preview',ACP_REPORTING_MODE='preview',ACP_DOCUMENTS_MODE='preview');session.launch();session.start_frontend();require(api(session,'/__test/reset',{})[0]==200,'DOCUMENT_PREREQUISITES')
    create=CREATE_JOURNEY.replace("page.locator('tbody')","page.locator('tbody').first()")
    results.append(journey(session,create,'commit'));session.restart();results.append(journey(session,create,'replay'));require(api(session,'/__test/report-negative',{})[0]==200,'DOCUMENT_NEGATIVE_FIXTURE')
    report=(life.ROOT/'engineering/reporting/journey.ts').read_text();results.append(journey(session,report,'report-commit'));results.append(journey(session,report,'report-replay'));documents=(PACKAGE/'journey.ts').read_text();results.append(journey(session,documents,'document-commit'));session.close();session=None
    before=demo.database_state(container,'acp_browser_case_management');history=life.history(container);life.save(w/'before-regeneration.json',before)
    life.detach_outputs(root,expected,w/'r0-outputs');c.verify_materialized(root,p,s,r)
    # A managed edit must invalidate source intelligence and publication.
    file=root/'backend/src/main/java/acp/api/DocumentController.java';raw=file.read_bytes();file.write_bytes(raw+b'\n// rejected drift\n')
    try:
     try:current(m,root);raise AssertionError('UNDETECTED_SOURCE_DRIFT')
     except ValueError:pass
     try:store.inventory();raise AssertionError('UNDETECTED_STORE_DRIFT')
     except StoreConflict:pass
    finally:file.write_bytes(raw)
    regenerated=c.plan(s,r,store.inventory());equivalence=life.generated_outputs_equivalent(p,regenerated);store.apply(regenerated);require((root/life.HUMAN).read_bytes()==human,'DOCUMENT_HUMAN_CHANGED');c.verify_materialized(root,regenerated,s,r)
    p=regenerated;expected=life.tree(root);preview=Preview(c,s,r,p,c.audit,root);folder1=w/'r1-inspection';folder1.mkdir();b1=folder1/'baseline.json';b1.write_bytes(preview.document)
    life.restore_modules(root,w/'r0-outputs');model=preview.analyze(b1,maven_repo=deps/'m2',node_modules=root/'frontend/node_modules',scratch=folder1);modelpath=folder1/'source-model.json';modelpath.write_bytes(encode(model));session1=preview.session(b1,modelpath)
    try:life.adapter_source=adapter_source;life.build(root,w/'r1-build')
    finally:life.adapter_source=original
    session=demo.Session(root,'case-management',logs);session.env.update(ACP_INTAKE_MODE='synthetic-preview',ACP_REPORTING_MODE='preview',ACP_DOCUMENTS_MODE='preview');session.launch();session.start_frontend();results.append(journey(session,documents,'document-replay'));session.close();session=None
    after=demo.database_state(container,'acp_browser_case_management');old={r['id']:r for r in before['acp_audit']};new={r['id']:r for r in after['acp_audit']};require(all(new.get(i)==r for i,r in old.items()),'DOCUMENT_AUDIT_MUTATION');extra=[r for i,r in new.items() if i not in old];require(len(extra)==2 and all(r['operation']=='PERM-DOC-READ' for r in extra),'DOCUMENT_UNEXPECTED_AUDIT');links=after[TABLE+'_audit'];prior=before[TABLE+'_audit'];require(all(r in links for r in prior) and len(links)==len(prior)+2 and {r['audit_id'] for r in links if r not in prior}=={r['id'] for r in extra},'DOCUMENT_AUDIT_LINKAGE');safe={**after,'acp_audit':before['acp_audit'],TABLE+'_audit':prior};demo.verify_replay_state(before,safe,life.commit_times(container));require(history==life.history(container),'DOCUMENT_MIGRATION_DRIFT');life.save(w/'after-regeneration.json',after);life.freeze(container,w/'database')
   finally:
    if session:session.close()
  life.detach_outputs(root,expected,w/'r1-outputs');c.verify_materialized(root,p,s,r)
  from engineering.documents.execution import CandidateExecution
  proof={'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED','canonicalDigest':s.read()['contentDigest'],'artifactPlanDigest':fingerprint(p),'generator':c.generator,'document':{'id':'DOC-ATTACHMENTS','revision':1},'sourceSHA256':sources,'files':[{'path':str(f.relative_to(w)),'sha256':sha(f.read_bytes())} for f in [*sorted(logs.glob('*-browser.json')),w/'before-regeneration.json',w/'after-regeneration.json'] if f.is_file()]}
  life.save(w/'execution-observation.json',proof);execution=CandidateExecution(w/'execution-observation.json');verification=session1.evaluate(execution=execution);require(all(x['result']=='PASS' for x in verification['results'] if x['kind']=='ARTIFACT_VERIFICATION'),'DOCUMENT_ARTIFACT_VERIFICATION')
  mcp=asyncio.run(mcp_inspect(session1,folder1,verification));require(all(sha((life.ROOT/n).read_bytes())==h for n,h in sources.items()),'DOCUMENT_EXECUTOR_DRIFT')
  life.save(w/'r1-audit.json',wire(c.audit));life.save(w/'r1-plan.json',wire(p));life.save(w/'verification.json',verification)
  record={'scope':'QUALIFICATION_ONLY','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'sourceSHA256':sources,'candidateDigest':s.read()['contentDigest'],'generator':c.descriptor(),'sealed05':life.bundle_digest(),'browser':results,'mcp':mcp,'regeneration':equivalence,'cleanup':{'database':'REMOVED','processes':'REAPED'},'tools':{'python':platform.python_version(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'java':subprocess.check_output(['java','--version'],text=True).strip()},'semanticApproval':'NOT_APPROVED','securityFindings':'UNCHANGED_NOT_RESCANNED','releaseDisposition':'PHASE6_RELEASE_CLOSURE_BLOCKED'};life.save(w/'result.json',record)
 return record

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True,type=Path);p.add_argument('--maven-seed',type=Path);p.add_argument('--npm-seed',type=Path);p.add_argument('--browser-seed',type=Path);p.add_argument('--offline',action='store_true');a=p.parse_args();qualify(a.workspace,maven_seed=a.maven_seed,npm_seed=a.npm_seed,browser_seed=a.browser_seed,offline=a.offline)
if __name__=='__main__':main()
