"""Actual SQLite process concurrency, restart, rollback and replay tests."""
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
import multiprocessing
import os
from pathlib import Path
import shutil
import sqlite3
import unittest

from lab_fixtures import Fixture, NOW
from engineering.evidence_admission.challenge import authenticate_challenge
from engineering.evidence_admission.execution_ledger import ExecutionLedger, STATES
from engineering.evidence_admission.signatures import LabVerificationError


def competing_reservation(path, checkpoint, raw, context, ready, start, output, identity):
    try:
        ledger=ExecutionLedger(path,expected_checkpoint=checkpoint)
        ready.put('ready');start.wait(15)
        try:
            ledger.reserve(raw,context,identity);output.put('reserved')
        except LabVerificationError:
            output.put('rejected')
        finally:ledger.close()
    except BaseException as error:
        ready.put('failed');output.put(repr(error))


def interrupted_transaction(path):
    db=sqlite3.connect(path,isolation_level=None)
    db.execute('BEGIN IMMEDIATE')
    db.execute("UPDATE operations SET state='VERIFIED'")
    os._exit(17)  # crash before commit: SQLite must roll back, not accept success


def interrupted_after_reservation(path, checkpoint, raw, context, pipe):
    ledger=ExecutionLedger(path,expected_checkpoint=checkpoint)
    ledger.reserve(raw,context,'33333333333333333333333333333333')
    pipe.send(ledger.checkpoint());pipe.close()
    os._exit(18)


class LedgerTests(unittest.TestCase):
    def setUp(self):self.f=Fixture(self)

    def reopen(self, checkpoint):
        ledger=ExecutionLedger(self.f.path,expected_checkpoint=checkpoint)
        self.addCleanup(ledger.close);return ledger

    def test_duplicate_challenge_digest(self):
        f=self.f;f.issue();before=f.ledger.checkpoint()
        with self.assertRaises(LabVerificationError):f.issue()
        self.assertEqual(before,f.ledger.checkpoint())

    def test_duplicate_nonce(self):
        f=self.f;f.issue();payload=dict(f.payload,recordId='22222222222222222222222222222222')
        with self.assertRaises(LabVerificationError):f.ledger.issue(f.sign(payload),f.context)

    def test_duplicate_record_identity(self):
        from engineering.evidence_admission.challenge import construct_challenge_payload
        f=self.f;f.issue();payload=construct_challenge_payload(f.context,f.payload['recordId'])
        with self.assertRaises(LabVerificationError):f.ledger.issue(f.sign(payload),f.context)

    def test_duplicate_execution_identity(self):
        from engineering.evidence_admission.challenge import construct_challenge_payload
        f=self.f;f.issue();f.ledger.reserve(f.raw,f.context,'44444444444444444444444444444444')
        payload=construct_challenge_payload(f.context,'22222222222222222222222222222222');raw=f.sign(payload)
        digest=f.ledger.issue(raw,f.context)
        with self.assertRaises(LabVerificationError):f.ledger.reserve(raw,f.context,'44444444444444444444444444444444')
        self.assertEqual(f.ledger.observe(digest)['state'],'ISSUED')

    def test_repeated_reservation(self):
        f=self.f;f.issue();f.ledger.reserve(f.raw,f.context,'44444444444444444444444444444444')
        for execution in ['44444444444444444444444444444444','55555555555555555555555555555555']:
            with self.assertRaises(LabVerificationError):f.ledger.reserve(f.raw,f.context,execution)
        with self.assertRaises(LabVerificationError):authenticate_challenge(f.raw,f.context,f.ledger)

    def test_expiry_is_durable(self):
        f=self.f;digest=f.issue()
        context=replace(f.context,trust=replace(f.context.trust,now=NOW+timedelta(minutes=10)))
        with self.assertRaises(LabVerificationError):f.ledger.reserve(f.raw,context,'66666666666666666666666666666666')
        self.assertEqual(f.ledger.observe(digest)['state'],'EXPIRED')
        with self.assertRaises(LabVerificationError):f.ledger.reserve(f.raw,f.context,'77777777777777777777777777777777')

    def test_concurrent_independent_process_reservations(self):
        f=self.f;digest=f.issue();checkpoint=f.ledger.checkpoint();f.ledger.close()
        ctx=multiprocessing.get_context('fork');ready=ctx.Queue();output=ctx.Queue();start=ctx.Event()
        processes=[ctx.Process(target=competing_reservation,args=(f.path,checkpoint,f.raw,f.context,ready,start,output,str(i+1)*32)) for i in range(2)]
        for process in processes:process.start()
        try:
            self.assertEqual([ready.get(timeout=20) for _ in processes],['ready','ready']);start.set()
            results=sorted(output.get(timeout=20) for _ in processes)
            self.assertEqual(results,['rejected','reserved'])
        finally:
            start.set()
            for process in processes:
                process.join(20)
                if process.is_alive():process.kill();process.join();self.fail('PROCESS_TIMEOUT')
                self.assertEqual(process.exitcode,0)
        # A stale external checkpoint cannot reopen the changed head.
        with self.assertRaises(LabVerificationError):self.reopen(checkpoint)

    def test_process_crash_rolls_back_uncommitted_transaction(self):
        f=self.f;digest=f.issue();checkpoint=f.ledger.checkpoint();f.ledger.close()
        process=multiprocessing.get_context('fork').Process(target=interrupted_transaction,args=(f.path,))
        process.start();process.join(20)
        if process.is_alive():process.kill();process.join();self.fail('PROCESS_TIMEOUT')
        self.assertEqual(process.exitcode,17)
        ledger=self.reopen(checkpoint);self.assertEqual(ledger.observe(digest)['state'],'ISSUED')

    def test_crash_after_reservation_requires_recovery(self):
        f=self.f;digest=f.issue();checkpoint=f.ledger.checkpoint();f.ledger.close()
        ctx=multiprocessing.get_context('fork');receiver,sender=ctx.Pipe(duplex=False)
        process=ctx.Process(target=interrupted_after_reservation,args=(f.path,checkpoint,f.raw,f.context,sender))
        process.start();sender.close()
        self.assertTrue(receiver.poll(20));committed=receiver.recv();receiver.close();process.join(20)
        if process.is_alive():process.kill();process.join();self.fail('PROCESS_TIMEOUT')
        self.assertEqual(process.exitcode,18)
        ledger=self.reopen(committed);self.assertEqual(ledger.observe(digest)['state'],'RESERVED')
        ledger.recover();self.assertEqual(ledger.observe(digest)['state'],'RECOVERY_REQUIRED')
        with self.assertRaises(LabVerificationError):ledger.reserve(f.raw,f.context,'99999999999999999999999999999999')
        ledger.transition(digest,'RECOVERY_REQUIRED','QUARANTINED')
        self.assertEqual(ledger.observe(digest)['state'],'QUARANTINED')

    def test_reopen_and_read_only_identity(self):
        f=self.f;digest=f.issue();checkpoint=f.ledger.checkpoint();f.ledger.close()
        ledger=self.reopen(checkpoint)
        self.assertEqual(ledger.checkpoint(),checkpoint)
        authenticate_challenge(f.raw,f.context,ledger)
        self.assertEqual(ledger.checkpoint(),checkpoint)
        self.assertIsNone(ledger.observe(digest)['resultDigest'])

    def test_truncated_database(self):
        f=self.f;f.issue();checkpoint=f.ledger.checkpoint();f.ledger.close();f.path.write_bytes(b'truncated')
        with self.assertRaises(LabVerificationError):self.reopen(checkpoint)

    def test_conflicting_materialized_state(self):
        f=self.f;f.issue();checkpoint=f.ledger.checkpoint();f.ledger.close()
        with closing(sqlite3.connect(f.path)) as db:db.execute("UPDATE operations SET state='VERIFIED',result_digest='fake'");db.commit()
        with self.assertRaises(LabVerificationError):self.reopen(checkpoint)

    def test_missing_event_and_altered_chain(self):
        f=self.f;f.issue();checkpoint=f.ledger.checkpoint();f.ledger.close()
        with closing(sqlite3.connect(f.path)) as db:db.execute('DELETE FROM events');db.commit()
        with self.assertRaises(LabVerificationError):self.reopen(checkpoint)

    def test_altered_event_digest_rejected(self):
        f=self.f;f.issue();checkpoint=f.ledger.checkpoint();f.ledger.close()
        with closing(sqlite3.connect(f.path)) as db:
            db.execute("UPDATE events SET digest=?",('sha256:'+'f'*64,));db.commit()
        with self.assertRaises(LabVerificationError):self.reopen(checkpoint)

    def test_wrong_checkpoint_head_and_state_digest(self):
        f=self.f;f.issue();checkpoint=f.ledger.checkpoint();f.ledger.close()
        for changed in [replace(checkpoint,head='sha256:'+'f'*64),replace(checkpoint,state_digest='sha256:'+'f'*64)]:
            with self.assertRaises(LabVerificationError):self.reopen(changed)

    def test_unauthorized_state_transitions(self):
        f=self.f;digest=f.issue();before=f.ledger.checkpoint()
        for target in STATES-{'FAILED','QUARANTINED','RECOVERY_REQUIRED'}:
            with self.subTest(target=target),self.assertRaises(LabVerificationError):f.ledger.transition(digest,'ISSUED',target)
        self.assertEqual(before,f.ledger.checkpoint())
        with self.assertRaises(LabVerificationError):f.ledger.transition(digest,'RESERVED','FAILED')

    def test_replay_after_failure(self):
        f=self.f;digest=f.issue();f.ledger.reserve(f.raw,f.context,'88888888888888888888888888888888');f.ledger.transition(digest,'RESERVED','FAILED')
        with self.assertRaises(LabVerificationError):f.ledger.reserve(f.raw,f.context,'99999999999999999999999999999999')
        with self.assertRaises(LabVerificationError):authenticate_challenge(f.raw,f.context,f.ledger)

    def test_missing_external_checkpoint(self):
        f=self.f;f.ledger.close()
        with self.assertRaises(LabVerificationError):ExecutionLedger(f.path)
        with self.assertRaises(LabVerificationError):ExecutionLedger(f.path,create=True,expected_checkpoint='expected')

    def test_missing_expected_database_never_recreated(self):
        f=self.f;checkpoint=f.ledger.checkpoint();f.ledger.close();f.path.unlink()
        with self.assertRaises(LabVerificationError):self.reopen(checkpoint)
        self.assertFalse(f.path.exists())

    def test_replaced_database_rejected(self):
        f=self.f;f.issue();checkpoint=f.ledger.checkpoint();f.ledger.close()
        other=f.path.with_suffix('.copy');shutil.copy2(f.path,other);other.replace(f.path)
        with self.assertRaises(LabVerificationError):self.reopen(checkpoint)

    def test_live_database_replacement_rejected(self):
        f=self.f;f.issue();other=f.path.with_suffix('.copy');shutil.copy2(f.path,other);other.replace(f.path)
        with self.assertRaises(LabVerificationError):f.ledger.checkpoint()

    def test_insecure_permissions_and_symlink(self):
        f=self.f;checkpoint=f.ledger.checkpoint();f.ledger.close();f.path.chmod(0o644)
        with self.assertRaises(LabVerificationError):self.reopen(checkpoint)
        f.path.chmod(0o600);link=f.path.with_suffix('.alias');link.symlink_to(f.path)
        with self.assertRaises(LabVerificationError):ExecutionLedger(link,expected_checkpoint=checkpoint)

    def test_exact_issuance_binding_and_no_result_api(self):
        f=self.f;digest=f.issue();row=f.ledger.observe(digest)
        self.assertEqual(row['issuance']['contractDigest'],f.context.expected_contract_digest)
        self.assertIsNone(row['resultDigest'])
        self.assertFalse(hasattr(f.ledger,'run'));self.assertFalse(hasattr(f.ledger,'verify_execution'))


if __name__=='__main__':unittest.main()
