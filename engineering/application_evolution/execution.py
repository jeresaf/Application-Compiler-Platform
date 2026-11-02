"""Phase 8 execution-port adapter for retained R8 laboratory observations only."""
import json
from pathlib import Path
from engineering.source_intelligence.model import sha,require
from compiler_contracts import fingerprint
from engineering.application_evolution.plan import validate_plan
class TransitionExecution:
 def __init__(self,path):
  self.path=Path(path);self.pin=sha(self.path.read_bytes());self.context={'evolutionExecutionSHA256':self.pin,'evolutionExecutorSHA256':sha(Path(__file__).read_bytes()),'evolutionScope':'QUALIFICATION_ONLY'}
 def apply(self,session,rows):
  require(sha(self.path.read_bytes())==self.pin and sha(Path(__file__).read_bytes())==self.context['evolutionExecutorSHA256'],'EVOLUTION_STALE_EXECUTION')
  data=json.loads(self.path.read_bytes());require(data['scope']=='QUALIFICATION_ONLY' and data['semanticApproval']=='NOT_APPROVED','EVOLUTION_EVIDENCE_SCOPE')
  require(data['candidateDigest']==session.inputs['canonicalDigest'] and data['artifactPlanDigest']==fingerprint(session.plan) and data['generator']==session.inputs['generator'],'EVOLUTION_EVIDENCE_IDENTITY')
  root=Path(__file__).resolve().parents[2];own=Path(__file__).parent;expected={str(p.relative_to(root)) for p in [*own.glob('*.py'),own/'journey.ts']};require(set(data['sourceSHA256'])==expected,'EVOLUTION_EXECUTOR_INVENTORY')
  for p,h in data['sourceSHA256'].items():require(sha((root/p).read_bytes())==h,'EVOLUTION_EXECUTOR_SOURCE')
  for p,h in data['files'].items():
   file=self.path.parent/p;require(file.resolve().is_relative_to(self.path.parent.resolve()) and sha(file.read_bytes())==h,'EVOLUTION_EVIDENCE_FILE')
  browser=[p for p in data['files'] if p.endswith('-browser.json')];require(len(browser)==9,'EVOLUTION_BROWSER_COUNT')
  for name in browser:
   stat=json.loads((self.path.parent/name).read_bytes())['stats'];require(stat['expected']==1 and stat['unexpected']==stat['skipped']==stat['flaky']==0,'EVOLUTION_BROWSER_RESULT')
  plan=validate_plan(json.loads((self.path.parent/'evolution-plan.json').read_bytes()));require(plan['change']['candidate']==session.inputs['canonicalDigest'],'EVOLUTION_MIGRATION_TARGET')
  old=json.loads((self.path.parent/'r6-database/migration-history.json').read_bytes());new=json.loads((self.path.parent/'r7-database/migration-history.json').read_bytes());require(new[:-1]==old and new[-1]['version']=='5' and new[-1]['success'],'EVOLUTION_HISTORY_EVIDENCE')
  restore=json.loads((self.path.parent/'restore/result.json').read_bytes());capture=json.loads((self.path.parent/'capture-manifest.json').read_bytes());require(restore['originalCaptureSHA256']==capture['files'],'EVOLUTION_RESTORE_CAPTURE_BINDING');require(restore['exactRowsBeforeMigration'] and restore['auditAndIdempotencyExact'] and restore['cleanup']=='OWN_NEW_DATABASE_REMOVED','EVOLUTION_RESTORE_EVIDENCE')
  require(all(r['result']=='PASS' for r in rows if r['kind']=='ARTIFACT_VERIFICATION'),'EVOLUTION_UNVERIFIED_ARTIFACTS');session.check_fresh()
  extra=[{'id':'r8:'+category,'kind':'CANDIDATE_RUNTIME_OBSERVATION','result':'PASS','obligation':None,'origins':[{'application':session.request.application,'id':'JOB-INTEGRITY','revision':1}],'artifacts':['backend/src/main/java/acp/api/IntegrityWorker.java'],'reasons':[],'observation':{'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED','changeDigest':plan['changeDigest'],'migrationPlanDigest':plan['planDigest'],'executionSHA256':self.pin,'files':data['files']}} for category in ('DATABASE_CONTINUITY','WORKER_EVOLUTION','OWNERSHIP','RECOVERY','SUCCESSOR_WRITES')]
  return [*rows,*extra]
