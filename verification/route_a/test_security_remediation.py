"""Independent security regressions. NON_AUTHORITATIVE_TEST_ONLY; temporary stores only."""
import copy
from contextlib import closing
from dataclasses import replace
import multiprocessing
import os
import signal
from pathlib import Path
import sqlite3
import unittest
import test_gateway_integration as baseline
from canonical_json import canonical_bytes
from engineering.route_a_gateway.security import Host, Denied, decode, Context, Authority, hashed
from engineering.route_a_gateway.freshness import FreshnessClient
from engineering.route_a_gateway.storage import Fence
from engineering.route_a_gateway.gateway import Gateway, event_ref
from engineering.route_a_gateway.evidence import WitnessClient, WitnessConflict, verify_receipt, commit_evidence
from engineering.route_a_gateway.archive import audit, export, restore, HistoricalAuthority
from lab_provider import RemoteWitness
from changes import request
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64


def lock_holder(path, queue):
    with Fence(path):
        queue.put('LOCKED')
        # Parent explicitly terminates this disposable process.
        signal.pause()


def concurrent_gateway(directory, raw, registration, root, port, key_raw, now, session, action, payload, ready, go, result):
    remote=RemoteWitness(port)
    freshness=FreshnessClient(remote,str(Path(directory).parent/('authority-observer-'+hashed(raw)[7:]+'.sqlite')))
    host=Host(raw,registration,root,freshness)
    key=Ed25519PrivateKey.from_private_bytes(key_raw)
    def signer(version,body):
        b={'classification':'NON_AUTHORITATIVE_TEST_ONLY','algorithm':'Ed25519','issuer':host.config['issuer'],
           'audience':host.config['audience'],'keyId':'LAB-KEY-receipt',**body}
        return canonical_bytes({'proofVersion':version,'body':b,'signature':base64.b64encode(key.sign(version.encode()+b'\0'+canonical_bytes(b))).decode()})
    witness=WitnessClient(host,remote,lambda:now,Path(directory).parent/'reader-checkpoints.sqlite')
    gateway=Gateway(directory,host,witness,signer,lambda:now)
    ready.put(action)
    if not go.wait(15):raise RuntimeError('test barrier timed out')
    try:
        if action=='approve':gateway.approve(*payload,session)
        else:gateway.apply(*payload,session)
        result.put((action,'UNEXPECTED_ACCEPT'))
    except Denied as error:
        result.put((action,str(error)))


class SecurityRemediationTests(unittest.TestCase):
    # Reuse only setup/helpers, not the baseline test class or its test discovery.
    setUp=baseline.IntegrationTests.setUp
    gateway=baseline.IntegrationTests.gateway
    bootstrap=baseline.IntegrationTests.bootstrap
    proposal=baseline.IntegrationTests.proposal
    approved=baseline.IntegrationTests.approved
    denied=baseline.IntegrationTests.denied
    attest_archive=baseline.IntegrationTests.attest_archive

    def status(self, **changes):
        self.lab.authority_overrides.update(changes)

    def revoke(self, area, identity, value, invalid_from=1005):
        self.lab.now=1010
        self.status(authorityRevision=2, **{area:[{identity:value,'effectiveAt':1010,'invalidFrom':invalid_from}]})

    def test_fresh_authority_loopback_positive_and_provider_outage_no_cache(self):
        remote=RemoteWitness(self.lab.server.server_port)
        host=replace(self.lab.host,freshness=FreshnessClient(remote,self.lab.host.freshness.observer_path))
        self.assertEqual(1,host.current_authority(self.lab.now).body['authorityRevision'])
        self.bootstrap()
        self.lab.authority_outage=True
        with self.assertRaisesRegex(Denied,'provider unavailable'):
            host.authenticate(self.lab.session(),self.lab.now,'APPLY')
        self.denied(lambda:self.g.genesis_subject(self.source,'author','OTHER','R',self.lab.session()))
        self.lab.authority_outage=False
        self.assertEqual(1,host.current_authority(self.lab.now).body['authorityRevision'])
        self.assertEqual(0,self.g._repo.head()['sequence'])

    def test_new_reviewer_revocation_blocks_existing_approval_apply(self):
        self.bootstrap();self.approved()
        self.revoke('revokedPrincipals','principal','LAB-REVIEWER')
        with self.assertRaisesRegex(Denied,'revoked principal'):
            self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.assertEqual(0,self.g._repo.head()['sequence'])
        self.assertEqual('RESERVED',self.g.ledger.get('OP-LAB-CHANGE')['state'])

    def test_new_signing_key_revocation_blocks_existing_approval(self):
        self.bootstrap();self.approved()
        self.revoke('revokedKeys','keyId','LAB-KEY-approval')
        with self.assertRaisesRegex(Denied,'revoked signing key'):
            self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.assertEqual(0,self.g._repo.head()['sequence'])

    def test_expired_configuration_rejects_valid_session_and_proof(self):
        self.bootstrap();self.approved()
        self.status(authorityRevision=2,configurationExpiresAt=1000)
        with self.assertRaisesRegex(Denied,'configuration expired'):
            self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.assertEqual(0,self.g._repo.head()['sequence'])

    def test_conflicting_configuration_cannot_be_hidden_by_older_status(self):
        self.status(authorityRevision=2,configurationDigest='sha256:'+'f'*64)
        with self.assertRaisesRegex(Denied,'conflicting authority configuration'):
            self.lab.host.current_authority(self.lab.now)
        self.lab.authority_overrides={}
        with self.assertRaisesRegex(Denied,'version rollback'):
            self.lab.host.current_authority(self.lab.now)

    def test_conflicting_signed_version_quarantines_observer_across_restart(self):
        self.lab.authority_overrides={'configurationExpiresAt':99999}
        with self.assertRaisesRegex(Denied,'conflicting signed authority version'):
            self.lab.host.current_authority(self.lab.now)
        self.lab.authority_overrides={}
        with self.assertRaisesRegex(Denied,'observer quarantined'):
            self.gateway()

    def test_observed_expiry_cannot_be_hidden_by_replaying_older_signed_status(self):
        self.status(authorityRevision=2,configurationExpiresAt=1000)
        with self.assertRaisesRegex(Denied,'configuration expired'):
            self.lab.host.current_authority(self.lab.now)
        self.lab.authority_overrides={}
        with self.assertRaisesRegex(Denied,'version rollback'):
            self.lab.host.current_authority(self.lab.now)

    def test_receipt_read_requires_independent_grant_even_for_original_author(self):
        config=self.lab.host.config
        next(g for g in config['grants'] if g['principal']=='author')['actions'].remove('RECEIPT_READ')
        self.lab.host=self.lab.authenticated_host(config)
        self.witness=WitnessClient(self.lab.host,self.lab,lambda:self.lab.now,self.root/'no-read-reader.sqlite')
        self.g=Gateway(self.root/'no-read',self.lab.host,self.witness,self.lab.service_sign,lambda:self.lab.now)
        self.bootstrap();_,_,_,s,proof=self.approved()
        self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        operation=self.g.ledger.get('OP-LAB-CHANGE')
        with self.assertRaisesRegex(Denied,'missing or revoked exact action grant'):
            self.g.retrieve('OP-LAB-CHANGE',s,proof,operation['bindings']['approvedEvent'],'R',self.lab.session())
        self.assertEqual('PUBLISHED',operation['state'])

    def test_stale_signed_authority_and_replayed_challenge_rejected(self):
        for changes in ({'observedAt':900},{'challenge':'REPLAYED'},{'observedAt':1001}):
            with self.subTest(changes=changes):
                self.lab.authority_overrides=changes
                self.denied(lambda:self.lab.host.current_authority(self.lab.now))
        self.lab.authority_overrides={}
        self.assertEqual(1,self.lab.host.current_authority(self.lab.now).body['authorityRevision'])

    def test_durable_authority_rollback_and_revocation_erasure_rejected_after_restart(self):
        self.revoke('revokedPrincipals','principal','LAB-REVIEWER')
        self.lab.host.current_authority(self.lab.now)
        host=replace(self.lab.host,freshness=FreshnessClient(self.lab.host.freshness.provider,self.lab.host.freshness.observer_path))
        self.lab.authority_overrides={}
        with self.assertRaisesRegex(Denied,'version rollback'):host.current_authority(self.lab.now)
        self.status(authorityRevision=3,revokedPrincipals=[])
        with self.assertRaisesRegex(Denied,'revocation history erased'):host.current_authority(self.lab.now)

    def test_later_revocation_preserves_prior_history_but_compromise_invalidates_it(self):
        self.bootstrap()
        self.revoke('revokedKeys','keyId','LAB-KEY-approval')
        self.assertEqual(1,audit(self.g,self.lab.session())['entries'])
        self.lab.authority_overrides['authorityRevision']=3
        self.lab.authority_overrides['revokedKeys'][0]['invalidFrom']=0
        with self.assertRaisesRegex(Denied,'revoked signing key'):audit(self.g,self.lab.session())
        self.assertEqual(0,self.g._repo.head()['sequence'])

    def test_missing_historical_configuration_key_and_grant_versions_fail_closed(self):
        self.bootstrap()
        original=self.lab.host.current_authority(self.lab.now).body
        for field,value in [('historicalConfigurations',[]),
                            ('historicalKeys',[k for k in original['historicalKeys'] if k!='LAB-KEY-approval']),
                            ('historicalGrants',[g for g in original['historicalGrants'] if g!='LAB-GRANT-LAB-REVIEWER'])]:
            with self.subTest(field=field):
                self.lab.authority_overrides={field:value,'authorityRevision':self.lab.authority_overrides.get('authorityRevision',1)+1}
                self.denied(lambda:audit(self.g,self.lab.session()))
        self.assertEqual(1,self.g._repo.audit()['entries'])

    def test_invalid_historical_reviewer_grant_is_not_structural_admission(self):
        self.bootstrap()
        self.revoke('revokedGrants','grantId','LAB-GRANT-LAB-REVIEWER',invalid_from=0)
        with self.assertRaisesRegex(Denied,'revoked grant'):audit(self.g,self.lab.session())
        self.assertEqual(1,self.g._repo.audit()['entries'])

    def test_status_signature_tamper_unknown_key_and_repository_substitution(self):
        original=self.lab.host.freshness.provider
        for case in ('signature','repository','key','policy'):
            class Adversary:
                def status(inner,challenge):
                    wire=decode(original.status(challenge))
                    if case=='signature':wire['signature']='AAAA'
                    elif case=='repository':wire['body']['repositoryId']='OTHER'
                    elif case=='key':wire['body']['keyId']='OTHER'
                    else:wire['body']['policyVersion']='OTHER'
                    return canonical_bytes(wire)
            host=replace(self.lab.host,freshness=FreshnessClient(Adversary(),str(self.root/('bad-'+case+'.sqlite'))))
            with self.subTest(case=case):self.denied(lambda:host.current_authority(self.lab.now))

    def test_provider_outage_after_native_commit_blocks_publication_then_recovers(self):
        self.bootstrap();self.approved()
        def fault(stage):
            if stage=='after_commit':self.lab.authority_outage=True
        self.g.failpoint=fault
        self.denied(lambda:self.g.apply('OP-LAB-CHANGE','R',self.lab.session()))
        self.assertEqual('RECOVERY_REQUIRED',self.g.ledger.get('OP-LAB-CHANGE')['state'])
        self.assertEqual(1,self.g._repo.head()['sequence'])
        self.lab.authority_outage=False;self.g.failpoint=lambda _:None
        self.assertEqual('PUBLISHED',self.g.recover('OP-LAB-CHANGE',self.lab.session())['status'])
        self.assertEqual(2,audit(self.g,self.lab.session())['entries'])

    def test_sigterm_lock_holder_releases_kernel_lock(self):
        ctx=multiprocessing.get_context('spawn');q=ctx.Queue()
        process=ctx.Process(target=lock_holder,args=(self.g.lock_path,q));process.start()
        self.addCleanup(lambda:process.kill() if process.is_alive() else None)
        self.assertEqual('LOCKED',q.get(timeout=10))
        with self.assertRaisesRegex(Denied,'competing writer'):
            with Fence(self.g.lock_path):self.fail('second process lock admitted')
        process.terminate();process.join(10);self.assertFalse(process.is_alive())
        self.assertLess(process.exitcode,0)
        with Fence(self.g.lock_path) as fence:fence.assert_owned()
        q.close();q.join_thread()

    def test_lock_file_replacement_detected_at_fence_boundary(self):
        with Fence(self.g.lock_path) as fence:
            os.unlink(self.g.lock_path)
            self.g.lock_path.write_bytes(b'')
            with self.assertRaisesRegex(Denied,'replaced fence inode'):fence.assert_owned()
        # A privileged/same-UID adversary can replace the file and acquire a NEW
        # inode. Detection is tested; confinement against that adversary is unsupported.
        with Fence(self.g.lock_path) as replacement:replacement.assert_owned()

    def test_concurrent_independent_approval_and_apply_are_fenced(self):
        self.bootstrap();pending=self.proposal('SECOND');self.approved('FIRST')
        ctx=multiprocessing.get_context('spawn');ready=ctx.Queue();result=ctx.Queue();go=ctx.Event()
        processes=[]
        for action,payload,session in [('approve',('OP-SECOND','SECOND',pending[2],pending[4]),self.lab.session('LAB-REVIEWER')),
                                       ('apply',('OP-FIRST','R'),self.lab.session())]:
            process=ctx.Process(target=concurrent_gateway,args=(self.root/'repository',self.lab.host.raw,
                self.lab.host.registration,self.lab.host.registration_root,self.lab.server.server_port,
                self.lab.keys['receipt'].private_bytes_raw(),self.lab.now,session,action,payload,ready,go,result))
            process.start();processes.append(process)
            # Serialize construction only; actual API attempts start concurrently.
            self.assertEqual(action,ready.get(timeout=15))
        with Fence(self.g.lock_path):
            go.set()
            results=[result.get(timeout=15) for _ in processes]
            self.assertEqual({'approve','apply'},{r[0] for r in results})
            self.assertTrue(all(r[1]=='competing writer' for r in results),results)
        for process in processes:
            process.join(10)
            if process.is_alive():process.kill();process.join();self.fail('competing process hung')
            self.assertEqual(0,process.exitcode)
        for q in (ready,result):q.close();q.join_thread()
        self.assertEqual(0,self.g._repo.head()['sequence'])
        self.g.apply('OP-FIRST','R',self.lab.session())
        self.assertEqual(1,self.g._repo.head()['sequence'])

    def test_stale_writer_epoch_cannot_mutate_reserved_operation(self):
        self.bootstrap();self.approved()
        with Fence(self.g.lock_path) as fence:
            old=self.g.ledger.epoch(fence);self.g.ledger.epoch(fence)
            operation=self.g.ledger.get('OP-LAB-CHANGE')
            with self.assertRaisesRegex(Denied,'stale writer epoch'):
                self.g.ledger.transition('OP-LAB-CHANGE','RECOVERY_REQUIRED',operation['version'],old,{'reason':'stale'},fence)
        self.assertEqual('RESERVED',self.g.ledger.get('OP-LAB-CHANGE')['state'])

    def test_rejected_authority_cannot_allocate_operation_epochs_or_reservations(self):
        plan,s=self.g.genesis_subject(self.source,'author','G','R',self.lab.session())
        proof=self.lab.approval(s);before=self.g.ledger.export()
        self.denied(lambda:self.g.bootstrap(self.source,'author','G','R',proof,self.lab.session('other')))
        self.assertEqual(before,self.g.ledger.export())
        self.bootstrap();_,_,reviewed,s,proof=self.proposal()
        before=self.g.ledger.export()
        self.denied(lambda:self.g.approve('OP-LAB-CHANGE','LAB-CHANGE',reviewed,proof,self.lab.session()))
        corrupt=decode(proof);corrupt['signature']='AAAA'
        self.denied(lambda:self.g.approve('OP-LAB-CHANGE','LAB-CHANGE',reviewed,canonical_bytes(corrupt),self.lab.session('LAB-REVIEWER')))
        self.assertEqual(before,self.g.ledger.export())
        self.g.approve('OP-LAB-CHANGE','LAB-CHANGE',reviewed,proof,self.lab.session('LAB-REVIEWER'))
        before=self.g.ledger.export()
        self.denied(lambda:self.g.apply('OP-LAB-CHANGE','R',self.lab.session('other')))
        self.assertEqual(before,self.g.ledger.export())
        self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.assertGreater(len(self.g.ledger.export()['epochs']),len(before['epochs']))

    def test_tampered_external_ledger_is_rejected_before_native_apply(self):
        self.bootstrap();self.approved()
        with self.g.ledger.db() as db:
            db.execute('DROP TRIGGER deny_events_UPDATE')
            db.execute('UPDATE events SET body=? WHERE operation=?',
                       (canonical_bytes({'proofDigest':'sha256:'+'0'*64}),'OP-LAB-CHANGE'))
        with self.assertRaisesRegex(Denied,'invalid initial reservation'):
            self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.assertEqual(0,self.g._repo.head()['sequence'])

    def test_nonce_replay_after_restart_is_rejected_with_authentic_signature(self):
        self.bootstrap();self.approved('FIRST');self.g.apply('OP-FIRST','R',self.lab.session())
        nonce=self.g.ledger.get('OP-FIRST')['proof']['body']['nonce']
        self.g=self.gateway();_,_,r,s,_=self.proposal('REPLAY')
        proof=self.lab.approval(s,nonce=nonce)
        with self.assertRaises(sqlite3.IntegrityError):
            self.g.approve('OP-REPLAY','REPLAY',r,proof,self.lab.session('LAB-REVIEWER'))
        self.assertEqual(1,self.g._repo.head()['sequence'])

    def test_stale_native_backup_cannot_recover_a_known_commit(self):
        self.bootstrap()
        stale=self.root/'stale-native.sqlite'
        with closing(sqlite3.connect(self.g._repo.path)) as source,closing(sqlite3.connect(stale)) as backup:
            source.backup(backup)
        self.approved()
        def fault(stage):
            if stage=='after_journal_committed':raise RuntimeError('test process response loss')
        self.g.failpoint=fault
        with self.assertRaises(RuntimeError):self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        os.replace(stale,self.g._repo.path)
        self.g=self.gateway()
        with self.assertRaisesRegex(Denied,'previously committed effect unavailable'):
            self.g.recover('OP-LAB-CHANGE',self.lab.session())
        self.assertEqual('RECOVERY_REQUIRED',self.g.ledger.get('OP-LAB-CHANGE')['state'])
        self.assertEqual(0,self.g._repo.head()['sequence'])

    def test_duplicate_historical_approval_identity_rejected(self):
        self.bootstrap();self.approved();self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        rows=copy.deepcopy(self.g._repo.export_records()['journal'])
        ops=[copy.deepcopy(self.g.ledger.get('LAB-GENESIS')),copy.deepcopy(self.g.ledger.get('OP-LAB-CHANGE'))]
        body=ops[1]['proof']['body'];body['approvalId']=ops[0]['proof']['body']['approvalId']
        wire=decode(self.lab.sign('approval','acp-route-a-approval/2',body))
        ops[1]['proof']=wire;rows[1][3]['approval']['proof']=wire
        with self.assertRaisesRegex(Denied,'duplicate historical approval identity'):
            HistoricalAuthority(self.lab.host,rows,ops,lambda:self.lab.now)
        self.assertEqual(2,audit(self.g,self.lab.session())['entries'])

    def test_independent_predecessor_digest_rejects_changed_historical_chain(self):
        self.bootstrap();self.approved();self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        rows=copy.deepcopy(self.g._repo.export_records()['journal']);rows[1][3]['previousDigest']='sha256:'+'f'*64
        ops=[self.g.ledger.get('LAB-GENESIS'),self.g.ledger.get('OP-LAB-CHANGE')]
        with self.assertRaisesRegex(Denied,'changed predecessor chain'):
            HistoricalAuthority(self.lab.host,rows,ops,lambda:self.lab.now)
        self.assertEqual(2,audit(self.g,self.lab.session())['entries'])

    def test_authenticated_witness_rollback_after_reader_restart_rejected(self):
        self.bootstrap();old=self.witness.latest()[0]
        self.approved();self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        def old_head(challenge):
            return self.lab.sign('witness','acp-route-a-witness-response/1',{'repositoryId':self.lab.host.config['repositoryId'],
                'applicationId':self.lab.host.config['applicationId'],'challenge':challenge,'observedAt':self.lab.now,'checkpoint':old})
        self.lab.latest=old_head
        restarted=WitnessClient(self.lab.host,self.lab,lambda:self.lab.now,self.root/'reader-checkpoints.sqlite')
        with self.assertRaisesRegex(WitnessConflict,'stale or conflicting'):restarted.latest()

    def test_correctly_signed_stale_witness_and_cross_repository_receipt_rejected(self):
        _,_,receipt=self.bootstrap();operation=self.g.ledger.get('LAB-GENESIS')
        with self.assertRaisesRegex(Denied,'trusted current verification time required'):
            verify_receipt(self.lab.host,receipt,operation['bindings']['commit'],None)
        self.lab.stale=True
        with self.assertRaisesRegex(Denied,'stale or replayed witness'):self.witness.latest()
        self.lab.stale=False
        changed=copy.deepcopy(operation['bindings']['commit']);changed['repositoryId']='OTHER'
        wire=self.lab.service_sign('acp-route-a-service-receipt/1',{'commit':changed,'issuedAt':self.lab.now})
        self.denied(lambda:verify_receipt(self.lab.host,wire,operation['bindings']['commit'],self.lab.now))
        self.assertEqual(hashed(receipt),verify_receipt(self.lab.host,receipt,operation['bindings']['commit'],self.lab.now))

    def test_interrupted_publication_and_lost_recovery_response_do_not_duplicate(self):
        self.bootstrap();_,_,_,s,proof=self.approved()
        def interrupted(stage):
            if stage=='after_witnessed':raise RuntimeError('publication interrupted')
        self.g.failpoint=interrupted
        with self.assertRaises(RuntimeError):self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.g=self.gateway()
        def response_loss(stage):
            if stage=='after_published':raise RuntimeError('recovery response lost')
        self.g.failpoint=response_loss
        with self.assertRaisesRegex(RuntimeError,'response lost'):self.g.recover('OP-LAB-CHANGE',self.lab.session())
        self.g=self.gateway();operation=self.g.ledger.get('OP-LAB-CHANGE')
        self.assertEqual('PUBLISHED',operation['state'])
        self.denied(lambda:self.g.recover('OP-LAB-CHANGE',self.lab.session()))
        raw=self.g.retrieve('OP-LAB-CHANGE',s,proof,operation['bindings']['approvedEvent'],'R',self.lab.session())
        self.assertEqual(operation['bindings']['receipt'],decode(raw))
        self.assertEqual(2,audit(self.g,self.lab.session())['entries'])

    def _unwitnessed_revocation(self,key):
        self.bootstrap();self.approved()
        def fault(stage):
            if stage=='after_receipt_stored':raise RuntimeError('test witness interruption')
        self.g.failpoint=fault
        with self.assertRaises(RuntimeError):self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        operation=self.g.ledger.get('OP-LAB-CHANGE')
        records=self.g._repo.export_records()
        bundle={'row':records['journal'][1],
                'proposals':[r for r in records['proposals'] if r[2] in {'REVIEW_REQUIRED','APPROVED'}],
                'migrationDecision':None}
        self.revoke('revokedKeys','keyId',key)
        # Proof and receipt were genuinely signed and the actual local commit
        # predates revocation. That alone cannot qualify an UNSEEN head.
        self.denied(lambda:self.witness.advance(operation['bindings']['commit'],canonical_bytes(operation['bindings']['receipt']),bundle))
        self.assertEqual(0,self.witness.latest()[0]['head']['sequence'])
        self.assertEqual('RECOVERY_REQUIRED',self.g.ledger.get('OP-LAB-CHANGE')['state'])

    def test_unwitnessed_backdated_commit_cannot_bypass_current_reviewer_revocation(self):
        self._unwitnessed_revocation('LAB-KEY-approval')

    def test_unwitnessed_backdated_commit_cannot_bypass_current_service_key_revocation(self):
        self._unwitnessed_revocation('LAB-KEY-receipt')

    def test_exact_witnessed_retry_after_later_revocation_preserves_historical_acceptance(self):
        self.bootstrap();self.approved();self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        operation=self.g.ledger.get('OP-LAB-CHANGE');records=self.g._repo.export_records()
        bundle={'row':records['journal'][1],
                'proposals':[r for r in records['proposals'] if r[2] in {'REVIEW_REQUIRED','APPROVED'}],
                'migrationDecision':None}
        self.revoke('revokedKeys','keyId','LAB-KEY-receipt')
        checkpoint,_=self.witness.advance(operation['bindings']['commit'],canonical_bytes(operation['bindings']['receipt']),bundle)
        self.assertEqual(operation['bindings']['commit']['newHead'],checkpoint['head'])
        self.assertEqual(2,audit(self.g,self.lab.session())['entries'])

    def _duplicate_witness_identity(self,field):
        self.bootstrap();self.approved('FIRST');self.g.apply('OP-FIRST','R1',self.lab.session())
        old=self.g.ledger.get('OP-FIRST')['proof']['body'][field]
        c,p,r,s,_=self.proposal('SECOND')
        proof=self.lab.approval(s,**{field:old})
        with self.assertRaises(sqlite3.IntegrityError):
            self.g.approve('OP-SECOND','SECOND',r,proof,self.lab.session('LAB-REVIEWER'))
        # Deliberately bypass the gateway in this TEMPORARY artificial repository.
        # Native core has no external approval-ID/nonce ledger. Generate an actual
        # cryptographically verified native test commit, then test independent
        # witness rejection rather than inventing a pretend acceptance receipt.
        auth=self.g._authority(decode(s),self.lab.session('LAB-REVIEWER'),'APPROVE',p['plan'])
        self.g._repo.approve('SECOND',decode(proof),auth,self.lab.now)
        approved_row,_=self.g._event('SECOND','APPROVED')
        auth=self.g._authority(decode(s),self.lab.session(),'APPLY',p['plan'])
        self.g._repo.apply('SECOND','R2',auth,self.lab.now)
        records=self.g._repo.export_records();row=records['journal'][-1]
        commit=commit_evidence(self.lab.host,decode(s),p['plan'],decode(proof),row,event_ref(self.lab.host,approved_row),'R2')
        receipt=self.lab.service_sign('acp-route-a-service-receipt/1',{'commit':commit,'issuedAt':self.lab.now})
        bundle={'row':row,'proposals':[r for r in records['proposals'] if r[1]=='SECOND' and r[2] in {'REVIEW_REQUIRED','APPROVED'}],
                'migrationDecision':None}
        self.denied(lambda:self.witness.advance(commit,receipt,bundle))
        self.assertEqual(1,self.witness.latest()[0]['head']['sequence'])
        self.assertEqual(2,self.g._repo.head()['sequence'])

    def test_independent_witness_rejects_duplicate_approval_id_despite_valid_native_proof(self):
        self._duplicate_witness_identity('approvalId')

    def test_independent_witness_rejects_duplicate_nonce_despite_valid_native_proof(self):
        self._duplicate_witness_identity('nonce')


if __name__=='__main__':unittest.main()
