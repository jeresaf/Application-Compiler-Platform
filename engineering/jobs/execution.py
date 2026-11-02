"""Candidate-only binding of actual retained browser/DB observations to Phase 8.

This adapter supplies no semantic approval, signature or release admission.
"""
import json
from pathlib import Path
from engineering.source_intelligence.model import sha,require
from compiler_contracts import fingerprint
from engineering.verification.integration import digest
class CandidateExecution:
 def __init__(self,path):
  self.path=Path(path);self.pin=sha(self.path.read_bytes());self.context={'jobExecutionSHA256':self.pin,'jobExecutorSHA256':sha(Path(__file__).read_bytes()),'jobExecutionScope':'QUALIFICATION_ONLY'}
 def apply(self,session,rows):
  require(sha(self.path.read_bytes())==self.pin,'STALE_JOB_EXECUTION');require(sha(Path(__file__).read_bytes())==self.context['jobExecutorSHA256'],'STALE_JOB_EXECUTOR');p=json.loads(self.path.read_bytes());require(p['scope']=='QUALIFICATION_ONLY' and p['semanticApproval']=='NOT_APPROVED','JOB_EXECUTION_SCOPE');require(p['canonicalDigest']==session.inputs['canonicalDigest'] and p['artifactPlanDigest']==fingerprint(session.plan) and p['generator']==session.inputs['generator'],'JOB_EXECUTION_IDENTITY');require(all(r['result']=='PASS' for r in rows if r['kind']=='ARTIFACT_VERIFICATION'),'JOB_UNVERIFIED_SOURCE')
  root=Path(__file__).resolve().parents[2]
  from engineering.jobs.target import PACKAGE
  expected={str(f.relative_to(root)) for f in [*PACKAGE.rglob('*.py'),*sorted((PACKAGE/'templates').glob('*')),PACKAGE/'journey.ts',root/'engineering/compiler_extensions/dispatch.py'] if f.is_file()}
  require(set(p['sourceSHA256'])==expected,'JOB_SOURCE_INVENTORY')
  require({r['path'] for r in p['files']}=={'runtime/'+name+'-browser.json' for name in ('commit','replay','report-commit','report-replay','document-commit','document-replay','jobs-commit','jobs-replay')}|{'before-regeneration.json','after-regeneration.json','job-execution.json','job-state.json'},'JOB_FILE_INVENTORY')
  node=next(n for n in session.snapshot.read()['content']['nodes'] if n['kind']=='IntegrityJob');require(p['document']=={'id':node['id'],'revision':node['revision']},'JOB_EXECUTION_SUBJECT')
  for name,h in p['sourceSHA256'].items():require(sha((root/name).read_bytes())==h,'JOB_EXECUTOR_SOURCE_CHANGED')
  for row in p['files']:
   path=self.path.parent/row['path'];require(path.resolve().is_relative_to(self.path.parent.resolve()) and sha(path.read_bytes())==row['sha256'],'JOB_EXECUTION_FILE')
   if row['path'].endswith('-browser.json'):
    report=json.loads(path.read_bytes());stats=report['stats'];require(stats['expected']==1 and stats['unexpected']==0 and stats['skipped']==0 and stats['flaky']==0,'JOB_BROWSER_RESULT')
  require(len([r for r in p['files'] if r['path'].endswith('-browser.json')])==8,'JOB_BROWSER_INVENTORY');session.check_fresh()
  observed=json.loads((self.path.parent/'job-execution.json').read_bytes());state=json.loads((self.path.parent/'job-state.json').read_bytes())
  require(len(observed['authorityRejections'])==3,'JOB_AUTHORITY_EVIDENCE')
  require(len(observed['scheduled']['results'])==4 and all(r['status']=='VALID' for r in observed['scheduled']['results']),'JOB_SCHEDULE_EVIDENCE')
  require(observed['transient']['attempts']==2 and observed['exhaustion']['attempts']==3 and observed['timeout']['attempts']==3,'JOB_RETRY_EVIDENCE')
  for name,error in (('invalid','INVALID_PAYLOAD'),('missing','MISSING_DOCUMENT'),('foreign','MISSING_DOCUMENT'),('corrupt','HASH_MISMATCH')):require(observed[name]['state']=='FAILED' and observed[name]['error']==error,'JOB_NEGATIVE_EVIDENCE')
  require(observed['crash']['after']['attempts']==2 and observed['crash']['before']['owner']!=observed['crash']['after']['owner'],'JOB_CRASH_EVIDENCE')
  require(any(a['state']=='FENCED_RESULT' for a in observed['fenced']['after']['attempts']),'JOB_FENCE_EVIDENCE')
  require(len({r['queue'] for r in state['results']})==len(state['results'])==len(state['audits']),'JOB_DEDUPLICATION_EVIDENCE')

  extra=[]
  for category in ('SCHEDULED_EXECUTION','SERVICE_AUTHORITY','FENCED_RECOVERY','CONTENT_INTEGRITY','REGENERATION_RESTART'):
   extra.append({'id':'job:'+category,'kind':'CANDIDATE_RUNTIME_OBSERVATION','result':'PASS','origins':[{'application':session.request.application,'id':p['document']['id'],'revision':p['document']['revision']}],'artifacts':['backend/src/main/java/acp/api/IntegrityWorker.java','frontend/src/JobPanel.vue'],'obligation':None,'reasons':[],'observation':{'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED','executionSHA256':self.pin,'category':category,'files':p['files']}})
  return [*rows,*extra]
