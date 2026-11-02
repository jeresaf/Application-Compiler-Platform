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
  self.path=Path(path);self.pin=sha(self.path.read_bytes());self.context={'documentExecutionSHA256':self.pin,'documentExecutorSHA256':sha(Path(__file__).read_bytes()),'documentExecutionScope':'QUALIFICATION_ONLY'}
 def apply(self,session,rows):
  require(sha(self.path.read_bytes())==self.pin,'STALE_DOCUMENT_EXECUTION');require(sha(Path(__file__).read_bytes())==self.context['documentExecutorSHA256'],'STALE_DOCUMENT_EXECUTOR');p=json.loads(self.path.read_bytes());require(p['scope']=='QUALIFICATION_ONLY' and p['semanticApproval']=='NOT_APPROVED','DOCUMENT_EXECUTION_SCOPE');require(p['canonicalDigest']==session.inputs['canonicalDigest'] and p['artifactPlanDigest']==fingerprint(session.plan) and p['generator']==session.inputs['generator'],'DOCUMENT_EXECUTION_IDENTITY');require(all(r['result']=='PASS' for r in rows if r['kind']=='ARTIFACT_VERIFICATION'),'DOCUMENT_UNVERIFIED_SOURCE')
  root=Path(__file__).resolve().parents[2]
  from engineering.documents.target import PACKAGE
  expected={str(f.relative_to(root)) for f in [*PACKAGE.rglob('*.py'),*sorted((PACKAGE/'templates').glob('*')),PACKAGE/'journey.ts',root/'engineering/compiler_extensions/dispatch.py'] if f.is_file()}
  require(set(p['sourceSHA256'])==expected,'DOCUMENT_SOURCE_INVENTORY')
  require({r['path'] for r in p['files']}=={'runtime/'+name+'-browser.json' for name in ('commit','replay','report-commit','report-replay','document-commit','document-replay')}|{'before-regeneration.json','after-regeneration.json'},'DOCUMENT_FILE_INVENTORY')
  node=next(n for n in session.snapshot.read()['content']['nodes'] if n['kind']=='DocumentDefinition');require(p['document']=={'id':node['id'],'revision':node['revision']},'DOCUMENT_EXECUTION_SUBJECT')
  for name,h in p['sourceSHA256'].items():require(sha((root/name).read_bytes())==h,'DOCUMENT_EXECUTOR_SOURCE_CHANGED')
  for row in p['files']:
   path=self.path.parent/row['path'];require(path.resolve().is_relative_to(self.path.parent.resolve()) and sha(path.read_bytes())==row['sha256'],'DOCUMENT_EXECUTION_FILE')
   if row['path'].endswith('-browser.json'):
    report=json.loads(path.read_bytes());stats=report['stats'];require(stats['expected']==1 and stats['unexpected']==0 and stats['skipped']==0 and stats['flaky']==0,'DOCUMENT_BROWSER_RESULT')
  require(len([r for r in p['files'] if r['path'].endswith('-browser.json')])==6,'DOCUMENT_BROWSER_INVENTORY');session.check_fresh()
  extra=[]
  for category in ('UPLOAD_DOWNLOAD','AUTHORIZATION','CONTENT_INTEGRITY','REGENERATION_RESTART'):
   extra.append({'id':'document:'+category,'kind':'CANDIDATE_RUNTIME_OBSERVATION','result':'PASS','origins':[{'application':session.request.application,'id':p['document']['id'],'revision':p['document']['revision']}],'artifacts':['backend/src/main/java/acp/api/DocumentController.java','frontend/src/DocumentPanel.vue'],'obligation':None,'reasons':[],'observation':{'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED','executionSHA256':self.pin,'category':category,'files':p['files']}})
  return [*rows,*extra]
