"""Full negotiated UI admission gate; Phase 6 closure is a separate audit."""
import argparse,json,os,subprocess,sys,time,urllib.request
from pathlib import Path
from dataclasses import replace
from compiler_core import compile_pipeline
from compiler_contracts import Success,Document,ArtifactPlan,Owner,fingerprint
from check_phase6_target import context_for
from filesystem_artifacts import FilesystemArtifactStore,StoreConflict
from deterministic_approval import approved_snapshot,header
from target_worker import ROOT,PROFILE,bundle_digest
from target_provenance import read_provenance,inspect_mapping
from task_ui_browser import server_source,IDENTITY,CONFIG,tests
from invocation_reference_tests import source,http_source,variants
from delivery_job_reference_tests import source as delivery_source
from privacy_lifecycle_reference_tests import source as privacy_source,http_source as privacy_http_source,variants as privacy_variants

def ui_context(domain):
    source,context=context_for(domain)
    # Explicit host execution policy: full source/provenance plans exceed the
    # synthetic adapter's default work allowance. Byte bounds and all compiler limits remain unchanged.
    resources=replace(context.request.resources,input_bytes=1_048_576,output_bytes=1_048_576,work=1_000_000,timeout_ms=120_000)
    return source,replace(context,request=replace(context.request,resources=resources))

def command(command,cwd,log,timeout=900):
    with log.open('wb') as stream:r=subprocess.run(command,cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
    if r.returncode:raise RuntimeError('COMMAND_FAILED:'+log.as_posix())

def browser(directory,domain,output):
    backend=directory/'backend';front=directory/'frontend'
    backend_port=18080 if domain=='payment' else 18081
    frontend_port=4173 if domain=='payment' else 4174
    p=backend/'src/test/java/acp/browser/BrowserServer.java';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(server_source(domain))
    command(['mvn','-B','-ntp','test-compile','dependency:build-classpath','-Dmdep.outputFile=target/browser-classpath'],backend,output/(domain+'-browser-compile.log'))
    identity=front/'src/extensions/identity.ts';production_identity=identity.read_text()
    identity.write_text(IDENTITY)
    (front/'playwright.config.ts').write_text(CONFIG.replace('4173',str(frontend_port)))
    p=front/'browser-tests/task.spec.ts';p.parent.mkdir(exist_ok=True);p.write_text(tests(domain))
    command(['npm','run','build'],front,output/(domain+'-browser-production-build.log'))
    # Test adapter is present only in this ephemeral test build, never release bytes.
    identity.write_text(production_identity)
    (front/'browser-server.mjs').write_text('''import http from 'node:http';import fs from 'node:fs';import path from 'node:path';
http.createServer((req,res)=>{if(req.url.startsWith('/api/')||req.url.startsWith('/__test/')){const upstream=http.request('http://127.0.0.1:18080'+req.url,{method:req.method,headers:req.headers},r=>{res.writeHead(r.statusCode,r.headers);r.pipe(res);});upstream.on('error',()=>{res.writeHead(502);res.end();});req.pipe(upstream);return;}
const name=path.resolve('dist','.'+decodeURIComponent(req.url.split('?')[0]));if(name!==path.resolve('dist')&&!name.startsWith(path.resolve('dist')+'/')){res.writeHead(400);res.end();return;}const file=fs.existsSync(name)&&fs.statSync(name).isFile()?name:'dist/index.html';res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');fs.createReadStream(file).pipe(res);}).listen(4173,'127.0.0.1');
''')
    server=front/'browser-server.mjs';server.write_text(server.read_text().replace('18080',str(backend_port)).replace("listen(4173",'listen('+str(frontend_port)))
    schema='acp_browser_'+domain.replace('-','_')
    env=os.environ.copy();url=env['ACP_TEST_DATABASE_URL'];env.update(ACP_DATABASE_URL=url+('?currentSchema=' if '?' not in url else '&currentSchema=')+schema,ACP_DATABASE_USER=env['ACP_TEST_DATABASE_USER'],ACP_DATABASE_PASSWORD=env['ACP_TEST_DATABASE_PASSWORD'],ACP_OIDC_ISSUER='https://test.invalid',ACP_OIDC_AUDIENCE='test')
    cp='target/test-classes:target/classes:'+(backend/'target/browser-classpath').read_text().strip()
    logs=[(output/(domain+'-browser-backend.log')).open('wb'),(output/(domain+'-browser-frontend.log')).open('wb')]
    processes=[]
    try:
        processes.append(subprocess.Popen(['java','-cp',cp,'acp.browser.BrowserServer','--server.address=127.0.0.1','--server.port='+str(backend_port),'--spring.flyway.schemas='+schema,'--spring.flyway.default-schema='+schema,'--spring.flyway.clean-disabled=false','--acp.runtime.mode=development','--acp.runtime.poll-enabled=false','--acp.jobs.JOB-TASK.revision-3.credential-handle=browser-test-only'],cwd=backend,env=env,stdout=logs[0],stderr=subprocess.STDOUT))
        processes.append(subprocess.Popen(['node','browser-server.mjs'],cwd=front,stdout=logs[1],stderr=subprocess.STDOUT))
        for _ in range(120):
            if any(p.poll() is not None for p in processes):raise RuntimeError('BROWSER_SERVER_EXIT')
            try:
                urllib.request.urlopen('http://127.0.0.1:'+str(backend_port)+'/actuator/health',timeout=1).close();break
            except Exception:time.sleep(.5)
        else:raise RuntimeError('BROWSER_SERVER_TIMEOUT')
        command(['npm','run','e2e'],front,output/(domain+'-browser-journeys.log'),1200)
        return json.loads((front/'browser-results.json').read_text())
    finally:
        for p in processes:p.terminate()
        for p in processes:
            try:p.wait(timeout=15)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for log in logs:log.close()

def run(output,builds):
    output.mkdir(parents=True,exist_ok=False)
    report={'mode':'FULL_TASK_INTERFACE_ADMISSION','approval':header(),'profile':PROFILE['profile'],'generator':PROFILE['generator'],'bundleDigest':bundle_digest(),'phase6':'IN_PROGRESS','phase7':'NOT_STARTED','closureGate':'BLOCKED_FINAL_AUDIT_REQUIRED','domains':{}}
    try:
        for domain in ('payment','case-management'):
            src,ctx=ui_context(domain);compilation=compile_pipeline(src,ctx)
            if not isinstance(compilation.result,Success):raise RuntimeError('ADMISSION_FAILED:'+str(compilation.result))
            src2,ctx2=ui_context(domain);repeat=compile_pipeline(src2,ctx2)
            if not isinstance(repeat.result,Success) or repeat.result.output_digest!=compilation.result.output_digest:raise RuntimeError('NONDETERMINISTIC_GENERATION')
            directory=output/domain;store=FilesystemArtifactStore(directory);store.apply(compilation.result.output)
            app=next(a for a in compilation.result.output.artifacts if a.path=='frontend/src/App.vue')
            original_app=(directory/app.path).read_text()
            # Uncoordinated edits fail closed; a declared compiler-owned revision
            # is replaced by deterministic regeneration, never preserved as an extension.
            (directory/app.path).write_text(original_app+'\n<!-- uncoordinated edit -->\n')
            try:store.inventory()
            except StoreConflict as error:
                if str(error)!='MANUAL_EDIT':raise
            else:raise RuntimeError('UNCOORDINATED_COMPILER_EDIT_ACCEPTED')
            (directory/app.path).write_text(original_app)
            changed_content=Document.of({'encoding':'UTF-8','text':original_app+'\n<!-- prior compiler revision -->\n'})
            changed=replace(app,content=changed_content,content_digest=fingerprint(changed_content,'artifact-content'),intent='UPDATE',expected_digest=app.content_digest)
            store.apply(ArtifactPlan((changed,),compilation.result.output.obligations))
            ai_content=Document.of({'encoding':'UTF-8','text':'// unapproved AI candidate\n'})
            ai=replace(app,path='frontend/src/extensions/ai-candidate.ts',owner=Owner.AI,content=ai_content,content_digest=fingerprint(ai_content,'artifact-content'))
            try:store.apply(ArtifactPlan((ai,),compilation.result.output.obligations))
            except StoreConflict as error:
                if str(error)!='AI_APPROVAL_REQUIRED':raise
            else:raise RuntimeError('UNAPPROVED_AI_ACCEPTED')
            extension='frontend/src/extensions/identity.ts';store.adopt_human(extension)
            original=(directory/extension).read_text();custom=original+'\n// deployment-owned customization must survive regeneration\n';(directory/extension).write_text(custom)
            regen=compile_pipeline(src,replace(ctx,inventory=store.inventory())).result
            if not isinstance(regen,Success):raise RuntimeError('REGENERATION_FAILED')
            store.apply(regen.output)
            if (directory/extension).read_text()!=custom:raise RuntimeError('HUMAN_EXTENSION_OVERWRITTEN')
            if (directory/app.path).read_text()!=original_app:raise RuntimeError('COMPILER_REVISION_PRESERVED')
            for mapping in read_provenance(directory/'acp/provenance.json')['artifacts']:
                if inspect_mapping(directory,mapping)['status']!='CURRENT':raise RuntimeError('PROVENANCE_MAPPING_STALE')
            evidence={'compilerOwnedRegeneration':'PASS','uncoordinatedCompilerEditRejected':'PASS','unapprovedAIRejected':'PASS','canonicalDigest':ctx.request.snapshot_digest,'admission':ctx.target.last_admission,'blockers':[],'determinism':'PASS','humanExtensionPreservation':'PASS','generatedProvenance':json.loads((directory/'acp/provenance.json').read_text())['build'],'checks':{}}
            report['domains'][domain]=evidence
            if builds:
                nodes=approved_snapshot(domain)['content']['nodes']
                for name,content in [('InvocationCoreTest',source(domain)),('InvocationHttpTest',http_source(domain)),('DeliveryJobTest',delivery_source(domain)),('PrivacyLifecycleTest',privacy_source(domain)),('PrivacyHttpTest',privacy_http_source(domain))]:
                    p=directory/('backend/src/test/java/acp/generated/'+name+'.java');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
                p=directory/'backend/src/test/resources/invocation-profile-V1.sql';p.parent.mkdir(parents=True,exist_ok=True);p.write_text((ROOT/'historical/invocation-0.1'/(domain+'-V1__initial.sql')).read_text())
                for path,content in (variants(domain,nodes)|privacy_variants(domain,nodes)).items():
                    p=directory/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
                for key,folder,cmd in [('backend','backend',['mvn','-B','-ntp','test']),('frontend-lock','frontend',['npm','ci','--ignore-scripts','--no-audit','--no-fund']),('frontend-types','frontend',['npm','run','typecheck']),('frontend-tests','frontend',['npm','test']),('frontend-build','frontend',['npm','run','build'])]:
                    command(cmd,directory/folder,output/(domain+'-'+key+'.log'));evidence['checks'][key]='PASS'
                command(['npx','--no-install','playwright','install',*(['--with-deps'] if os.environ.get('CI')=='true' else []),'chromium'],directory/'frontend',output/(domain+'-browser-install.log'))
                evidence['browser']=browser(directory,domain,output);evidence['checks']['real-browser']='PASS'
            evidence['result']='PASS' if builds else 'GENERATED_ONLY'
        report['result']='FULL_ADMISSION_PASS_PHASE6_NOT_CLOSED' if builds else 'GENERATION_PASS_NO_RUNTIME_CLAIM'
    except Exception as e:
        report['result']='FAIL';report['error']=str(e);raise
    finally:(output/'task-interface-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['result']);return 0

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--run-builds',action='store_true');a=p.parse_args();raise SystemExit(run(a.output.absolute(),a.run_builds))
