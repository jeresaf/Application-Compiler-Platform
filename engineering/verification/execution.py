"""Adapters for existing Phase 6 execution outputs, never release admission.

GitHub is queried independently through authenticated gh API calls. A local JSON
claim, ZIP checksum, or test name by itself cannot establish hosted execution.
"""
from datetime import datetime,timezone
from pathlib import Path,PurePosixPath
from types import SimpleNamespace
import hashlib,json,re,subprocess,zipfile
from engineering.verification.integration import ROOT,require,digest,sha,encode,wire,fingerprint
from filesystem_artifacts import source_bytes
from engineering.dependency_resolution.inputs import file_hash
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate

REPOSITORY='jeresaf/Application-Compiler-Platform'
PRODUCER='9fd0fe07249fc1b23e9850175c478d303e1e06c8'
RUN=41098093388
ASSETS={
 'demonstration':{'id':12997816106,'job':124208979890,'name':'successor-reference-demonstration','sha256':'94be926a6131f270643cc02b1279ffe496c73f4375d42c16e18526113d08a99f','step':'Compile build browse restart and replay both approved applications','root':'acp-demo','report':'demonstration-results.json'},
 'recovery':{'id':12997421297,'job':124208979702,'name':'successor-deployment-recovery','sha256':'60ec092b29b85409690f4a08a4bc97cf364e01634396a9f7015b8b5d09c2f17d','step':'Exercise migration failures and fresh JVM committed-state recovery','root':'acp-recovery','report':'recovery-results.json'},
 'security':{'id':12996254772,'job':124208979760,'name':'successor-security-readiness','sha256':'4e55c4253b305dea65bf686f8f3700db1958af20e6f3267abda888c86e2c0e86','step':'Exercise real worker limits and generated package startup contracts','root':'acp-security','report':'security-results.json'},
}
FAMILIES=('backend-build','frontend-typecheck','frontend-build','frontend-tests','backend-tests','runtime-api','authentication','browser-e2e','postgres-migrations','restart-committed-state','idempotency-audit','authorization-tenant-boundary','migration-failure-recovery','dependency-security-assessment')
CLOSURE=('tooling','targets','contracts','test-corpus','fixtures/deployment-oidc','engineering/demo','engineering/generator_builds','engineering/recovery','engineering/security','engineering/traceability','engineering/dependency_resolution','.github/workflows/phase6-v3-offline.yml')

def instant(value):
 require(isinstance(value,str),'EVIDENCE_TIME');dt=datetime.fromisoformat(value.replace('Z','+00:00'));require(dt.utcoffset() is not None and dt.utcoffset().total_seconds()==0,'EVIDENCE_UTC');return dt

def api(path):
 require(path.startswith('repos/'+REPOSITORY+'/actions/'),'GITHUB_API_SCOPE')
 try:raw=subprocess.check_output(['gh','api','--hostname','github.com',path],stderr=subprocess.PIPE,timeout=120)
 except (subprocess.SubprocessError,OSError) as e:raise ValueError('AUTHENTICATED_GITHUB_API_UNAVAILABLE') from e
 require(len(raw)<=8*1024*1024,'API_RESPONSE_BOUND');return json.loads(raw)

def fresh(observed,evaluated,maximum):
 age=(instant(evaluated)-instant(observed)).total_seconds();require(0<=age<=maximum,'EXPIRED_OR_FUTURE_EXECUTION_EVIDENCE')

def source_closure():
 # Compare working bytes, not merely HEAD or self-declared sourceHashes.
 require(not subprocess.check_output(['git','diff','--name-only',PRODUCER,'--',*CLOSURE],cwd=ROOT,text=True).strip(),'CHANGED_EXECUTOR_OR_LOCK_TREE')
 rows=subprocess.check_output(['git','ls-tree','-r',PRODUCER,'--',*CLOSURE],cwd=ROOT,text=True).splitlines();require(rows,'EXECUTOR_CLOSURE_MISSING')
 for row in rows:
  metadata,name=row.split('\t',1);expected=metadata.split()[2]
  actual=subprocess.check_output(['git','hash-object','--path='+name,name],cwd=ROOT,text=True).strip();require(actual==expected,'CHANGED_EXECUTOR_OR_DEPENDENCY_LOCK:'+name)
 require(not subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*CLOSURE],cwd=ROOT,text=True).strip(),'UNREGISTERED_EXECUTOR_SOURCE')
 return digest(rows)

def stats(report,expected):
 s=report['stats'];require(s['expected']==expected and all(s[k]==0 for k in ('unexpected','skipped','flaky')),'FAILED_OR_INCOMPLETE_BROWSER_EXECUTION')
 def walk(suites):
  for suite in suites:
   yield from suite.get('specs',[]);yield from walk(suite.get('suites',[]))
 specs=list(walk(report['suites']));count=0
 for spec in specs:
  require(spec['ok'] is True,'FAILED_BROWSER_SPEC')
  for test in spec['tests']:
   require(test['status']=='expected' and test['expectedStatus']=='passed' and len(test['results'])==1,'RETRY_SKIP_OR_MISSING_BROWSER_RESULT')
   r=test['results'][0];require(r['status']=='passed' and not r.get('errors'),'FAILED_BROWSER_RESULT');count+=1
 require(count==expected,'BROWSER_RESULT_INVENTORY');return specs

class HostedExecutions:
 """One bounded observation of real GitHub API authority, not cached authority."""
 def __init__(self,directory,evaluated_at):
  self.directory=Path(directory);self.evaluated_at=evaluated_at;instant(evaluated_at);self.assets={};self.errors={};self.observations={};self.witnesses={}
  try:
   self.closure=source_closure();run=api(f'repos/{REPOSITORY}/actions/runs/{RUN}')
   require(run['head_sha']==PRODUCER and run['repository']['full_name']==REPOSITORY and run['status']=='completed' and run['conclusion']=='success','WRONG_OR_INCOMPLETE_HOSTED_RUN')
   self.observations['run']=run
  except ValueError as e:
   self.closure=None;self.errors={k:str(e) for k in ASSETS};run=None
  for kind,asset in ASSETS.items():
   if run is None:continue
   try:
    job=api(f'repos/{REPOSITORY}/actions/jobs/{asset["job"]}');meta=api(f'repos/{REPOSITORY}/actions/artifacts/{asset["id"]}')
    self.observations[kind]={'job':job,'artifact':meta}
    require(job['run_id']==RUN and job['name']==asset['name'] and job['status']=='completed' and job['conclusion']=='success','WRONG_OR_FAILED_HOSTED_JOB')
    require(any(s['name']==asset['step'] and s['status']=='completed' and s['conclusion']=='success' for s in job['steps']),'EXECUTOR_STEP_NOT_PERFORMED')
    require(meta['name']==asset['name'] and meta['digest']=='sha256:'+asset['sha256'] and meta['workflow_run']['head_sha']==PRODUCER and meta['workflow_run']['id']==RUN and not meta['expired'],'WRONG_OR_EXPIRED_HOSTED_ARTIFACT')
    p=self.directory/(kind+'.zip');require(file_hash(p)==asset['sha256'],'EXECUTION_ARCHIVE_DIGEST')
    with zipfile.ZipFile(p) as z:
     members=z.infolist();require(0<len(members)<=6000 and len({m.filename for m in members})==len(members) and sum(m.file_size for m in members)<=512*1024*1024,'ARCHIVE_INVENTORY_BOUND')
     for m in members:
      n=PurePosixPath(m.filename);require(not n.is_absolute() and '..' not in n.parts and '\\' not in m.filename and ((m.external_attr>>16)&0o170000)!=0o120000,'UNSAFE_EXECUTION_ARCHIVE_MEMBER')
     raw=z.read(asset['root']+'/'+asset['report']);report=json.loads(raw)
    require(report['sourceCommit']==PRODUCER and report['scope']=='QUALIFICATION_ONLY','EXECUTION_REPORT_IDENTITY')
    for name,h in report['sourceHashes'].items():require(file_hash(ROOT/name)==h,'EXECUTOR_SOURCE_SUBSTITUTED:'+name)
    self.assets[kind]={'path':p,'report':report,'job':job,'memberSHA256':sha(raw),'environment':{'runner':job['runner_name'],'labels':job['labels'],'python':report.get('python'),'image':report.get('image'),'workflow':'.github/workflows/phase6-v3-offline.yml@'+PRODUCER}}
   except (ValueError,OSError,KeyError,zipfile.BadZipFile) as e:self.errors[kind]=str(e)
  self.context={'executionAdapterSHA256':file_hash(Path(__file__)),'executionEvidence':{'authority':'AUTHENTICATED_GITHUB_API' if self.assets else 'UNAVAILABLE','repository':REPOSITORY,'sourceCommit':PRODUCER,'run':RUN,'evaluatedAt':evaluated_at,'executorClosureDigest':self.closure,'archives':{k:v['sha256'] for k,v in ASSETS.items()},'available':sorted(self.assets),'errors':self.errors}}
 def member(self,kind,path):
  asset=self.assets[kind]
  with zipfile.ZipFile(asset['path']) as z:
   name=ASSETS[kind]['root']+'/'+path;info=z.getinfo(name);require(info.file_size<=32*1024*1024,'RESULT_MEMBER_BOUND');return z.read(name)
 def json(self,kind,path):return json.loads(self.member(kind,path))
 def check(self,s,kind):
  require(kind in self.assets,self.errors.get(kind,'MISSING_EXECUTION_EVIDENCE'))
  a=self.assets[kind];require(file_hash(a['path'])==ASSETS[kind]['sha256'],'EXECUTION_ARCHIVE_CHANGED_AFTER_AUTHENTICATION')
  raw=self.member(kind,ASSETS[kind]['report']);require(sha(raw)==a['memberSHA256'] and json.loads(raw)==a['report'],'EXECUTION_REPORT_CHANGED_AFTER_AUTHENTICATION')
  report=a['report'];maximum=min(n['data']['maxAgeSeconds'] for n in s.snapshot.read()['content']['nodes'] if n['kind']=='EvidenceRequirement')
  fresh(a['job']['completed_at'],self.evaluated_at,maximum)
  candidate=report.get('candidate',report['applications'][s.b['domain']].get('candidate'))
  require(candidate==s.candidate.descriptor(),'WRONG_EXECUTION_GENERATOR')
  app=report['applications'][s.b['domain']];require(app.get('snapshot',app.get('canonical'))==s.b['canonicalDigest'],'WRONG_EXECUTION_APPLICATION_OR_SNAPSHOT')
  return report,app,maximum
 def witness(self,s):
  """Existing direct test compiler differs in metadata; prove executable equality."""
  key=s.b['domain']
  if key not in self.witnesses:
   from engineering.traceability.qualification import inputs
   candidate,snapshot,request,plan=inputs(key)
   target=candidate.lower(snapshot,compiler=request.compiler,pipeline=request.pipeline)
   require(target.target_model==s.target.target_model,'DIFFERENT_EXECUTABLE_TARGET_MODEL')
   hashes={a.path:sha(source_bytes(a.content)) for a in plan.artifacts}
   self.witnesses[key]={'compiler':request.compiler,'pipeline':request.pipeline,'targetIRDigest':fingerprint(target),'artifactPlanDigest':fingerprint(plan),'targetModelDigest':fingerprint(target.target_model),'generatedArtifacts':hashes}
  return self.witnesses[key]
 def apply(self,s,rows):
  rows=json.loads(encode(rows));d=s.b['domain'];facts={};out=[]
  def add(family,status,origins=(),details=None,reason=None,kind='demonstration'):
   a=self.assets.get(kind);out.append({'id':'execution:'+family,'kind':'EXECUTION_OBLIGATION','result':status,'origins':list(origins),'artifacts':[],'obligation':None,'reasons':[reason] if reason else [],'observation':{'authority':'AUTHENTICATED_GITHUB_API' if a else 'UNAVAILABLE','execution':{'repository':REPOSITORY,'run':RUN,'job':ASSETS[kind]['job'],'sourceCommit':PRODUCER,'archiveSHA256':ASSETS[kind]['sha256'],'reportSHA256':a['memberSHA256'] if a else None,'environment':a['environment'] if a else None},'consumerInputs':s.inputs,'evidence':details}})
  try:
   r,a,maximum=self.check(s,'demonstration');require(self.json('demonstration','runtime-results.json')['applications']==r['applications'],'CONFLICTING_EXECUTION_RESULTS');require([x for x in r['compilerExecutions'] if x['domain']==d]==s.b['compilerExecutions'],'DIFFERENT_EXECUTION_COMPILATION_OR_ARTIFACT_PLAN')
   require(all(a['sourceHashes'].get(p)==f['sha256'] for p,f in s.b['files'].items()),'MODIFIED_EXECUTED_GENERATED_ARTIFACT')
   require(a['health']=='UP' and a['databaseCleanup']=='REMOVED' and a['provenance']=='VERIFIED','INCOMPLETE_RUNTIME_OR_CLEANUP')
   demos=r['demonstrations'][d];logs=d+'-runtime/'
   for label,filename,needle in [('backend-build','production-backend.log','BUILD SUCCESS'),('frontend-typecheck','production-frontend-typecheck.log','vue-tsc'),('frontend-build','production-frontend-build.log','built in'),('frontend-tests','production-frontend-test.log','passed')]:
    raw=self.member('demonstration',logs+filename);require(needle in raw.decode(),'MISSING_EXECUTED_BUILD_RESULT');add(label,'PASS',details={'member':logs+filename,'sha256':sha(raw),'package':demos['package']['distributionSHA256']})
   browser=self.json('demonstration',logs+'business-browser.json');specs=stats(browser,14)
   oidc=self.json('demonstration',d+'-runtime-outputs/frontend/browser-results.json');stats(oidc,2)
   for label,details in [('runtime-api',{'health':a['health'],'tests':14}),('authentication',{'issuer':'DISPOSABLE_RS256_JWKS_PKCE_ADAPTER','tests':2}),('browser-e2e',{'member':logs+'business-browser.json','sha256':sha(encode(browser))})]:add(label,'PASS',details=details)
   expected=[p.split('/')[-1].split('__')[0][1:] for p in s.b['files'] if p.startswith('database/V') and p.endswith('.sql')]
   require(a['successfulMigrations']==sorted(expected),'MIGRATION_HISTORY_MISMATCH');add('postgres-migrations','PASS',details={'versions':a['successfulMigrations'],'postgres':a['postgres']})
   recovery=demos['browserRestart'];require(recovery['failures']==0 and recovery['skipped']==0 and recovery['committedStatePreserved'] and recovery['duplicateBusinessEffects']==0 and recovery['idempotencyRows']==recovery['businessEffects']==recovery['auditRows'],'FAILED_IDEMPOTENCY_AUDIT_OR_RESTART')
   from engineering.demo.reference import verify_replay_state
   replay=self.json('demonstration',logs+'replay-state.json');require(replay['before']==replay['afterRestart'],'RESTART_CHANGED_COMMITTED_STATE');verify_replay_state(replay['before'],replay['afterReplay'],self.json('demonstration',logs+'commit-time-observations.json'))
   for label in ('restart-committed-state','idempotency-audit'):add(label,'PASS',details=recovery)
   from engineering.traceability.qualification import STEPS
   from engineering.generator_builds import runtime
   source=runtime.browser_gate.tests(d);needle,identities=STEPS['boundary'];require(needle in source,'CHANGED_BOUNDARY_ASSERTION_SOURCE')
   boundary=[p for p in specs if p['title']=='permissions, forged calls, wrong tenant and identity change clear protected state'];require(sum(len(p['tests']) for p in boundary)==2,'MISSING_PERMISSION_BOUNDARY_TESTS')
   origins=[{'id':id,'revision':s.revisions[id]} for id in identities];add('authorization-tenant-boundary','PASS',origins,{'assertionSourceSHA256':sha(source.encode()),'existingTraceabilityStep':'boundary','scope':'GENERATED_PERMISSION_BOUNDARY_ONLY'})
   facts['boundary']=set(identities)
  except (ValueError,KeyError,OSError,zipfile.BadZipFile) as e:add('application-execution','BLOCKED',reason=str(e))
  try:
   r,a,_=self.check(s,'recovery');w=self.witness(s);require(a['generatedSources']==w['generatedArtifacts'],'RECOVERY_EXECUTED_ARTIFACT_IDENTITY')
   scope={p for p in s.b['files'] if p.startswith(('backend/','database/'))}|{'frontend/src/task-ui-model.ts'}
   require(all(a['generatedSources'].get(p)==s.b['files'][p]['sha256'] for p in scope),'DIFFERENT_MIGRATION_OR_BACKEND_EXECUTABLE')
   from engineering.recovery.qualify import verify_observations
   verify_observations(a['observations'],1 if d=='payment' else 3);require(a['failures']==a['skipped']==0 and a['database']['cleanup']=='REMOVED' and a['processCleanup']=='REAPED','RECOVERY_FAILURE_OR_LEAK')
   add('migration-failure-recovery','PASS',details={'producerInputs':w,'bindingScope':'EXACT_BACKEND_AND_MIGRATION_EXECUTABLE_INPUTS','observations':a['observations'],'database':a['database']},kind='recovery')
  except (ValueError,KeyError,OSError) as e:add('migration-failure-recovery','BLOCKED',reason=str(e),kind='recovery')
  try:
   r,a,maximum=self.check(s,'security');assessment=a['security']
   require(r['sourceHashes']['engineering/dependency_resolution/maven-artifacts.lock.json']==file_hash(ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json'),'SCANNED_DEPENDENCY_LOCK_MISMATCH')
   require(a['sourcePreserved'] is True,'SCANNED_GENERATED_SOURCE_CHANGED')
   demo=self.assets.get('demonstration');require(demo is not None,'MISSING_PACKAGED_DEPENDENCY_COMPARISON')
   require(a['package']['lockedDependencies']==demo['report']['demonstrations'][d]['package']['lockedDependencies'],'MISMATCHED_PACKAGED_DEPENDENCY_LOCK')
   import xml.etree.ElementTree as ET
   with zipfile.ZipFile(self.assets['security']['path']) as z:
    names=[n for n in z.namelist() if n.startswith('acp-security/'+d+'/backend/target/surefire-reports/TEST-') and n.endswith('.xml')]
    suites=[ET.fromstring(z.read(n)) for n in names]
   cases=[c for root in suites for c in root.iter('testcase')];require(len(cases)==10 and all(not any(c.find(tag) is not None for tag in ('failure','error','skipped')) for c in cases),'FAILED_OR_INCOMPLETE_BACKEND_TEST_RESULTS')
   require(a['tests']=={'tests':10,'failures':0,'errors':0,'skipped':0},'BACKEND_TEST_INVENTORY')
   add('backend-tests','PASS',details={'purpose':'EXISTING_PACKAGE_READINESS_TESTS_ONLY','tests':10,'members':names,'producerInputs':self.witness(s)},kind='security')
   fresh(assessment['scannedAt'],self.evaluated_at,maximum)
   require(assessment['osvStatus']=='COMPLETED' and assessment['npm']['status']=='COMPLETED','INCOMPLETE_SCANNER_COVERAGE')
   findings=[{k:f.get(k) for k in ('component','severityLabel','severityStatus','disposition','affectedIdentityStatus')}|{'advisory':f.get('advisory',{}).get('id')} for f in assessment['findings']]
   status='FAIL' if findings or assessment['npm']['vulnerabilities'].get('total',0) else 'BLOCKED' if assessment['unknown'] or assessment['unresolvedEmbeddedBuildArtifacts'] else 'PASS'
   add('dependency-security-assessment',status,details={'coverage':assessment['coverage'],'findings':findings,'unknown':assessment['unknown'],'unresolvedEmbeddedBuildArtifacts':assessment['unresolvedEmbeddedBuildArtifacts'],'npm':assessment['npm'],'scannedAt':assessment['scannedAt'],'originalStatus':assessment['status'],'scope':'BOUNDED_SCANNED_IDENTITIES_NOT_OPERATIONAL_SECURITY'},kind='security')
  except (ValueError,KeyError,OSError) as e:add('dependency-security-assessment','BLOCKED',reason=str(e),kind='security')
  # Reuse the existing assertion-to-object mapping. Never discharge policies,
  # acceptance criteria, accessibility/manual review, or backups by inference.
  for row in rows:
   if row['kind']=='SEMANTIC_OBLIGATION' and {o['id'] for o in row['origins']}<=facts.get('boundary',set()) and row['origins'] and row['result']=='NOT_RUN':
    row['result']='PASS';row['reasons']=[];row['observation']={'executionResult':'execution:authorization-tenant-boundary','scope':'QUALIFICATION_ONLY'}
  for family in FAMILIES:
   if not any(r['id']=='execution:'+family for r in out):add(family,'BLOCKED',reason='MISSING_OR_INCOMPLETE_EXECUTION_RESULT',kind='security' if family in ('backend-tests','dependency-security-assessment') else 'demonstration')
  return rows+out
