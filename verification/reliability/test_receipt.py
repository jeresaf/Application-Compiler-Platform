"""Synthetic unit receipts only; never runtime evidence or authority."""
import copy,json,tempfile,unittest
from pathlib import Path
from engineering.reliability.verification import SCENARIOS,validate,Execution


def receipt():
    rows=[{'scenario':n,'result':'PASS','database':{'unit':'SYNTHETIC_NOT_RUNTIME'},'duplicateEffects':0} for n in sorted(SCENARIOS)]
    by={r['scenario']:r for r in rows}
    for n in ('parallelCaseCreation','simultaneousDocumentUploads'):by[n]['overlap']={'blockedBusinessTransactions':2,'submitted':4}
    by['parallelCaseCreation']['sessions']=[{'tenant':'unit','subject':'user','sid':str(i)} for i in range(4)]
    by['concurrentQueueClaims'].update(queues=['a','b','c','d'],processes=[101,102])
    by['leaseExpiryAndStaleCompletion'].update(before={'id':'q','owner':'a'},winner={'owner':'b','token':2},after={'attempts':[{'queue':'q','token':1,'state':'FENCED_RESULT'}]})
    for n in ('processDeathBeforeCommit','caseDeathAfterCommitBeforeAcknowledgement','documentDeathAfterCommitBeforeAcknowledgement','workerDeathAfterClaim','interruptedApplicationRestart'):by[n]['killed']={'exit':-9}
    return {'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED','releaseClosure':'BLOCKED','scenarioResults':rows,'database':{'unit':'SYNTHETIC_NOT_RUNTIME'},'cleanup':'VERIFIED','resources':[{'cleanup':'OWN_CONTAINER_AND_VOLUME_REMOVED'}],
            'evolution':{'faults':{'databaseRestartBetweenMigrationStages':{'populationExact':True},'interruptedMigration':{'rollbackObserved':True}},'restore':{'exactRowsBeforeMigration':True,'auditAndIdempotencyExact':True,'cleanup':'OWN_NEW_DATABASE_REMOVED'}},
            'migrationPreflightRejections':[{'case':n,'result':'PASS'} for n in ('source','populationDigest','schema')]}


class Receipt(unittest.TestCase):
    def setUp(self):self.r=receipt();self.by={r['scenario']:r for r in self.r['scenarioResults']}
    def reject(self):
        with self.assertRaises((ValueError,KeyError)):validate(self.r)
    def test_closed_synthetic_positive(self):self.assertIs(validate(self.r),self.r)
    def test_release_scope_rejected(self):self.r['scope']='RELEASE';self.reject()
    def test_semantic_approval_rejected(self):self.r['semanticApproval']='APPROVED';self.reject()
    def test_closed_release_rejected(self):self.r['releaseClosure']='PASS';self.reject()
    def test_missing_scenario(self):self.r['scenarioResults'].pop();self.reject()
    def test_duplicate_scenario(self):self.r['scenarioResults'][-1]=copy.deepcopy(self.r['scenarioResults'][0]);self.reject()
    def test_skipped_scenario(self):self.r['scenarioResults'][0]['result']='SKIP';self.reject()
    def test_failed_scenario(self):self.r['scenarioResults'][0]['result']='FAIL';self.reject()
    def test_wrong_database(self):self.r['scenarioResults'][0]['database']={'unit':'other'};self.reject()
    def test_duplicate_effect(self):self.r['scenarioResults'][0]['duplicateEffects']=1;self.reject()
    def test_cleanup_not_verified(self):self.r['cleanup']='UNKNOWN';self.reject()
    def test_missing_resource_inventory(self):self.r['resources']=[];self.reject()
    def test_leaked_volume(self):self.r['resources'][0]['cleanup']='PENDING';self.reject()
    def test_serialized_counterexample_rejected(self):self.by['parallelCaseCreation']['overlap']['blockedBusinessTransactions']=0;self.reject()
    def test_sequential_upload_counterexample_rejected(self):self.by['simultaneousDocumentUploads']['overlap']['blockedBusinessTransactions']=0;self.reject()
    def test_shared_sessions_rejected(self):self.by['parallelCaseCreation']['sessions']=[{'tenant':'t','subject':'s','sid':'same'}]*4;self.reject()
    def test_single_process_workers_rejected(self):self.by['concurrentQueueClaims']['processes']=[1,1];self.reject()
    def test_missing_queue_claim(self):self.by['concurrentQueueClaims']['queues'].pop();self.reject()
    def test_same_owner_reclaim(self):self.by['leaseExpiryAndStaleCompletion']['winner']['owner']='a';self.reject()
    def test_old_token_reclaim(self):self.by['leaseExpiryAndStaleCompletion']['winner']['token']=1;self.reject()
    def test_missing_stale_fence(self):self.by['leaseExpiryAndStaleCompletion']['after']['attempts']=[];self.reject()
    def test_graceful_exit_is_not_crash(self):self.by['processDeathBeforeCommit']['killed']['exit']=0;self.reject()
    def test_stale_receipt(self):
        with tempfile.TemporaryDirectory(prefix='h2-receipt-unit-') as d:
            p=Path(d)/'synthetic.json';p.write_text(json.dumps(self.r));executor=Execution(p);p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'H2_STALE_EXECUTION'):executor.apply(None,[])
