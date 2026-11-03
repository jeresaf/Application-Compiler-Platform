"""Narrow H2 Phase 8 observations; no release admission, signatures or approvals."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tooling'))
from engineering.source_intelligence.model import sha,require
from compiler_contracts import fingerprint

SCENARIOS=frozenset({'parallelCaseCreation','simultaneousDocumentUploads',
    'databaseConnectionLossBeforeDocumentCommit','processDeathBeforeCommit',
    'caseDeathAfterCommitBeforeAcknowledgement','documentDeathAfterCommitBeforeAcknowledgement',
    'databaseAndApplicationRestart','interruptedApplicationRestart','concurrentQueueClaims',
    'leaseExpiryAndStaleCompletion','workerDeathAfterClaim'})


def validate(record):
    require(record['scope']=='QUALIFICATION_ONLY' and record['semanticApproval']=='NOT_APPROVED' and record['releaseClosure']=='BLOCKED','H2_SCOPE')
    rows=record['scenarioResults'];require(len(rows)==len(SCENARIOS) and {r['scenario'] for r in rows}==SCENARIOS,'H2_MISSING_OR_DUPLICATE_SCENARIO')
    require(all(r['result']=='PASS' and r['database']==record['database'] for r in rows),'H2_FAILED_OR_WRONG_DATABASE')
    require(all(r.get('duplicateEffects',0)==0 for r in rows),'H2_DUPLICATE_EFFECTS')
    require(record['cleanup']=='VERIFIED' and record['resources'] and all(r['cleanup']=='OWN_CONTAINER_AND_VOLUME_REMOVED' for r in record['resources']),'H2_CLEANUP')
    by={r['scenario']:r for r in rows}
    for name in ('parallelCaseCreation','simultaneousDocumentUploads'):
        require(by[name]['overlap']['blockedBusinessTransactions']>=2 and by[name]['overlap']['submitted']==4,'H2_NO_CONCURRENCY_PROOF')
    require(len({(s['tenant'],s['subject'],s['sid']) for s in by['parallelCaseCreation']['sessions']})==4,'H2_SESSION_BINDING')
    require(len(by['concurrentQueueClaims']['queues'])==4 and len(set(by['concurrentQueueClaims']['processes']))==2,'H2_NO_INDEPENDENT_WORKERS')
    stale=by['leaseExpiryAndStaleCompletion'];require(stale['before']['owner']!=stale['winner']['owner'] and stale['winner']['token']==2,'H2_NO_RECLAIM')
    require(any(a['queue']==stale['before']['id'] and a['token']==1 and a['state']=='FENCED_RESULT' for a in stale['after']['attempts']),'H2_NO_STALE_FENCE')
    for name in ('processDeathBeforeCommit','caseDeathAfterCommitBeforeAcknowledgement','documentDeathAfterCommitBeforeAcknowledgement','workerDeathAfterClaim','interruptedApplicationRestart'):
        require(by[name]['killed']['exit']==-9,'H2_NO_PROCESS_DEATH')
    prior=record['evolution']
    require(prior['faults']['databaseRestartBetweenMigrationStages']['populationExact'] and prior['faults']['interruptedMigration']['rollbackObserved'],'H2_MIGRATION_RECOVERY')
    require(prior['restore']['exactRowsBeforeMigration'] and prior['restore']['auditAndIdempotencyExact'] and prior['restore']['cleanup']=='OWN_NEW_DATABASE_REMOVED','H2_MIGRATION_RESTORE')
    require({r['case'] for r in record['migrationPreflightRejections']}=={'source','populationDigest','schema'} and all(r['result']=='PASS' for r in record['migrationPreflightRejections']),'H2_MISSING_MIGRATION_PREFLIGHT')
    return record


class Execution:
    def __init__(self,path):
        self.path=Path(path);self.pin=sha(self.path.read_bytes());self.context={'h2ExecutionSHA256':self.pin,'h2Scope':'QUALIFICATION_ONLY'}
    def apply(self,session,rows):
        require(sha(self.path.read_bytes())==self.pin,'H2_STALE_EXECUTION');record=validate(json.loads(self.path.read_bytes()))
        require(record['generator']['generator']==session.inputs['generator'] and record['canonicalDigest']==session.inputs['canonicalDigest'] and record['artifactPlanDigest']==fingerprint(session.plan) and record['sourceModelDigest']==session.model['digest'],'H2_EXECUTION_IDENTITY')
        root=ROOT
        expected={p.relative_to(root).as_posix() for p in Path(__file__).parent.glob('*.py')}|{'engineering/application_evolution/plan.py','engineering/source_intelligence/model.py'}
        require(set(record['sourceSHA256'])==expected,'H2_SOURCE_INVENTORY')
        require(set(record['files'])=={'concurrency/runtime/observations.json','execution-resources.json','concurrency/database/database-state.json','concurrency/database/migration-history.json'}|{'evolution/'+n for n in ('result.json','evolution-plan.json','capture-manifest.json','r6-database/migration-history.json','r7-database/migration-history.json','restore/result.json','r6-candidate.json','r7-candidate.json','r7-plan.json')},'H2_EVIDENCE_INVENTORY')
        for name,h in record['sourceSHA256'].items():require(sha((root/name).read_bytes())==h,'H2_SOURCE_CHANGED')
        for name,h in record['files'].items():
            p=self.path.parent/name;require(p.resolve().is_relative_to(self.path.parent.resolve()) and sha(p.read_bytes())==h,'H2_EVIDENCE_CHANGED')
        observed=json.loads((self.path.parent/'concurrency/runtime/observations.json').read_bytes())
        require(observed['scenarios']==record['scenarioResults'],'H2_OBSERVATION_MISMATCH')
        require(json.loads((self.path.parent/'evolution/result.json').read_bytes())==record['evolution'],'H2_EVOLUTION_OBSERVATION_MISMATCH')
        prior=record['evolution']
        for name,h in prior['sourceSHA256'].items():require(sha((root/name).read_bytes())==h,'H2_EVOLUTION_SOURCE_CHANGED')
        old=json.loads((self.path.parent/'evolution/r6-database/migration-history.json').read_bytes());new=json.loads((self.path.parent/'evolution/r7-database/migration-history.json').read_bytes())
        require(new[:-1]==old and new[-1]['version']=='5' and new[-1]['success'],'H2_MIGRATION_HISTORY')
        state=json.loads((self.path.parent/'concurrency/database/database-state.json').read_bytes())
        for table,values in state.items():
            if table.startswith('d_') and not table.endswith('_audit'):
                for row in values:
                    raw=bytes.fromhex(row['content'][2:]);require(len(raw)==row['size'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'H2_STORED_CONTENT_INTEGRITY')
            if table.startswith('j_') and table.endswith('_result'):
                require(len({r['queue'] for r in values})==len(values),'H2_DUPLICATE_TERMINAL_RESULT')
                audits={r['id']:r for r in state['acp_audit']}
                require(all(r['audit_id'] in audits and audits[r['audit_id']]['operation']=='JOB-INTEGRITY' for r in values),'H2_RESULT_AUDIT_LINK')
        session.check_fresh()
        return [*rows,*[{'id':'h2:'+r['scenario'],'kind':'CANDIDATE_RUNTIME_OBSERVATION','result':'PASS','obligation':None,
            'origins':[{'application':session.request.application,'id':i,'revision':1} for i in ('CREATE-CASE','DOC-ATTACHMENTS','JOB-INTEGRITY')],
            'artifacts':['backend/src/main/java/acp/api/IntakeController.java','backend/src/main/java/acp/api/DocumentController.java','backend/src/main/java/acp/api/IntegrityWorker.java'],
            'reasons':[],'observation':{'scope':'QUALIFICATION_ONLY','executionSHA256':self.pin,'scenario':r['scenario']}} for r in record['scenarioResults']]]
