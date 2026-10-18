"""Reject incomplete outcomes; actual execution is the separate disposable runner."""
from copy import deepcopy
from pathlib import Path
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.recovery.qualify import EXPECTED,verify_observations,wait_until,stop,Lab,authenticated_database_ready
from engineering.recovery.fixtures import server,MIGRATOR

class RecoveryTests(unittest.TestCase):
    def records(self):
        rows={name:{'test':name,'status':'PASS'} for name in EXPECTED}
        for name in ('failedSchemaMigrationRollbackAndRecovery','migrationChecksumMismatch','incorrectMigrationOrdering','nonTransactionalMigrationRequiresCompensation','unavailableDatabaseFailsClosed','incompatibleRequiredSchemaFailsStartup'):rows[name]['failure']={'exit':1}
        rows['interruptedMigrationProcessTermination']['exit']=-signal.SIGKILL
        rows['crashBeforeCommit'].update(postgresTransactionStatus='aborted',databaseOutcome='ROLLED_BACK')
        rows['crashAfterCommitBeforeResponse'].update(databaseOutcome='COMMITTED',logicalWorkflows=4,counts={'acp_outbox':4})
        rows['restartPreservesAllCommittedRuntimeFamilies'].update(oldPid=100,newProcess={'pid':101})
        rows['securityAndRateAfterRecovery'].update(concurrentStatuses=[200]*4,overloadStatuses=[200,429])
        rows['revokedSessionRejected']['httpStatus']=403
        return list(rows.values())
    def test_complete_bounded_outcome_inventory(self):verify_observations(self.records(),1)
    def test_missing_duplicate_or_self_declared_pass_rejected(self):
        good=self.records()
        for bad in (good[:-1],good+[good[0]],[dict(test=n,status='PASS') for n in EXPECTED]):
            with self.assertRaises((ValueError,KeyError)):verify_observations(bad,1)
    def test_fault_without_failure_rejected(self):
        rows=self.records();next(r for r in rows if r['test']=='migrationChecksumMismatch')['failure']['exit']=0
        with self.assertRaisesRegex(ValueError,'FAULT_WAS_NOT_EXECUTED'):verify_observations(rows,1)
    def test_wrong_commit_effect_count_and_live_jvm_rejected(self):
        for name,key,value in (('crashAfterCommitBeforeResponse','counts',{'acp_outbox':5}),('restartPreservesAllCommittedRuntimeFamilies','oldPid',101)):
            rows=self.records();next(r for r in rows if r['test']==name)[key]=value
            with self.assertRaises(ValueError):verify_observations(rows,1)
    def test_indeterminate_cannot_be_called_rolled_back(self):
        rows=self.records();next(r for r in rows if r['test']=='crashBeforeCommit')['postgresTransactionStatus']='in progress'
        with self.assertRaisesRegex(ValueError,'MISSING_ROLLBACK_PROOF'):verify_observations(rows,1)
    def test_http500_or_missing_rate_denial_rejected(self):
        for statuses in ([200,500],[200]*20):
            rows=self.records();next(r for r in rows if r['test']=='securityAndRateAfterRecovery')['overloadStatuses']=statuses
            with self.assertRaisesRegex(ValueError,'SECURITY'):verify_observations(rows,1)
    def test_bounded_timeout_never_becomes_success(self):
        with self.assertRaisesRegex(TimeoutError,'held'):wait_until(lambda:False,'held',timeout=0)
        wait_until(lambda:True,'immediate')
    def test_cleanup_reaps_only_owned_process_group_and_escalates(self):
        process=Mock(pid=123);process.poll.side_effect=[None,-signal.SIGKILL];process.wait.side_effect=[subprocess.TimeoutExpired('test',15),-signal.SIGKILL];process.returncode=-signal.SIGKILL
        with patch('engineering.recovery.qualify.os.killpg') as kill:
            self.assertEqual(stop(process),-signal.SIGKILL)
            self.assertEqual(kill.call_args_list[0].args,(123,signal.SIGTERM));self.assertEqual(kill.call_args_list[1].args,(123,signal.SIGKILL))
    def test_final_database_readiness_requires_authenticated_tcp_query(self):
        states=[subprocess.CompletedProcess([],2,'','bootstrap socket gone'),subprocess.CompletedProcess([],0,'1\n','')]
        with patch('engineering.recovery.qualify.subprocess.run',side_effect=states) as execute,patch('engineering.recovery.qualify.time.sleep'):
            result=authenticated_database_ready('acp-06-runtime-owned','test-only')
        self.assertEqual([r['exit'] for r in result['attempts']],[2,0])
        for call in execute.call_args_list:
            argv=call.args[0];self.assertIn('PGPASSWORD=test-only',argv);self.assertIn('127.0.0.1',argv);self.assertEqual(argv[-1],'SELECT 1')
            self.assertNotIn('pg_isready',argv)
    def test_unavailable_final_server_fails_closed_at_deadline(self):
        state=subprocess.CompletedProcess([],2,'','connection refused')
        with patch('engineering.recovery.qualify.subprocess.run',return_value=state),patch('engineering.recovery.qualify.time.sleep'),patch('engineering.recovery.qualify.time.monotonic',side_effect=[0,0,61]):
            with self.assertRaisesRegex(TimeoutError,'POSTGRES_FINAL_TCP_READINESS'):authenticated_database_ready('acp-06-runtime-owned','test-only')

    def test_application_and_flyway_use_only_explicit_disposable_binding(self):
        lab=object.__new__(Lab);lab.cp='test';lab.schema='owned';lab.migrations=Path('/tmp/owned-migrations');lab.port=12345
        lab.env={'ACP_DATABASE_URL':'jdbc:postgresql://127.0.0.1:1234/owned','ACP_DATABASE_USER':'test-user','ACP_DATABASE_PASSWORD':'test-secret','SPRING_DATASOURCE_URL':'must-not-be-used'}
        argv=lab.application_argv()
        self.assertEqual(argv[:4],['java','-cp','test','acp.browser.BrowserServer'])
        self.assertIn('--spring.datasource.url='+lab.env['ACP_DATABASE_URL'],argv)
        self.assertIn('--spring.flyway.url='+lab.env['ACP_DATABASE_URL'],argv)
        self.assertNotIn('must-not-be-used',' '.join(argv))
        failed=dict(lab.env,ACP_DATABASE_URL='jdbc:postgresql://127.0.0.1:1/unavailable')
        self.assertIn('--spring.flyway.url='+failed['ACP_DATABASE_URL'],lab.application_argv(failed))

    def test_external_adapter_has_no_destructive_reset_and_keeps_authentication(self):
        for domain in ('payment','case-management'):
            text=server(domain)
            self.assertNotIn('f.repair()',MIGRATOR)
            self.assertNotIn('flyway.clean()',text);self.assertNotIn('/__test/reset',text)
            self.assertIn('throw new JwtException',text);self.assertIn('ACP_RECOVERY_AUTH_EVENT',text)
            self.assertIn('RecoveryResponseGate.class',text)

if __name__=='__main__':unittest.main()
