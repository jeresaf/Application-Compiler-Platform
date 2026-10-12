"""Real cryptography/storage/native history tests; NON_AUTHORITATIVE_TEST_ONLY."""
import copy
import multiprocessing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tooling'))
sys.path.insert(0,str(ROOT))
from canonical_json import canonical_bytes,loads
from canonical_fixtures import synthetic_approved
from changes import genesis,prepare,request,ChangeError
from change_fixtures import change,revise,migration
from engineering.route_a_gateway.security import Host,Denied,decode,hashed,Context,Authority
from engineering.route_a_gateway.storage import Fence,Ledger,NORMAL,STATES
from engineering.route_a_gateway.gateway import Gateway,event_ref
from engineering.route_a_gateway.evidence import WitnessClient,verify_receipt
from engineering.route_a_gateway.archive import audit,export,restore
from lab_provider import Lab,RemoteWitness
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import base64


def crash_worker(directory,host_raw,registration,registration_root,port,key_raw,now,operation,retry,session,point,bootstrap=None):
    host=Host(host_raw,registration,registration_root)
    key=Ed25519PrivateKey.from_private_bytes(key_raw)
    def signer(version,body):
        body={'classification':'NON_AUTHORITATIVE_TEST_ONLY','algorithm':'Ed25519',
            'issuer':host.config['issuer'],'audience':host.config['audience'],'keyId':'LAB-KEY-receipt',**body}
        signature=key.sign(version.encode()+b'\0'+canonical_bytes(body))
        return canonical_bytes({'proofVersion':version,'body':body,'signature':base64.b64encode(signature).decode()})
    def fault(stage):
        if stage==point:os._exit(73)
    witness=WitnessClient(host,RemoteWitness(port),lambda:now,Path(directory).parent/'reader-checkpoints.sqlite')
    g=Gateway(directory,host,witness,signer,lambda:now,fault)
    if bootstrap is None:g.apply(operation,retry,session)
    else:g.bootstrap(bootstrap['source'],'author',operation,retry,bootstrap['proof'],session)


def competing_worker(path,parent_pid,queue):
    try:
        with Fence(path):queue.put('ACQUIRED')
    except Denied:queue.put('DENIED')
    inherited=Fence(path);inherited.fd=-1;inherited.pid=parent_pid
    try:inherited.assert_owned();queue.put('OWNED')
    except Denied:queue.put('LOST')


def laboratory_source():
    nodes=[{'id':id,'revision':1,'kind':'Fact','name':id,'lifecycle':'APPROVED','steward':'LAB',
        'origins':[{'source':'NON_AUTHORITATIVE_TEST_ONLY','locator':id,'actor':'LAB','actorType':'HUMAN'}],
        'basis':[],'data':{'statement':'LAB '+id,'evidence':'NON_AUTHORITATIVE_TEST_ONLY'}} for id in ('FACT-A','FACT-B')]
    return synthetic_approved({'modelVersion':'0.2.0','applicationId':'APP-ROUTE-A-LAB','snapshotId':'LAB-SOURCE',
        'nodes':nodes,'approvals':[],'issues':[]})


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.lab=Lab(self.root);self.addCleanup(self.lab.close)
        self.witness=WitnessClient(self.lab.host,self.lab,lambda:self.lab.now,self.root/'reader-checkpoints.sqlite')
        self.g=self.gateway()
        self.source=laboratory_source()

    def gateway(self,failpoint=None):
        return Gateway(self.root/'repository',self.lab.host,self.witness,self.lab.service_sign,lambda:self.lab.now,failpoint)

    def bootstrap(self):
        plan,s=self.g.genesis_subject(self.source,'author','LAB-GENESIS','LAB-GENESIS-RETRY',self.lab.session())
        proof=self.lab.approval(s)
        receipt=self.g.bootstrap(self.source,'author','LAB-GENESIS','LAB-GENESIS-RETRY',proof,self.lab.session())
        return s,proof,receipt

    def proposal(self,id='LAB-CHANGE',target='FACT-A'):
        c=change(id,self.g._repo.head(),[revise(self.g._repo.snapshot(),target,name='LAB-RENAMED-'+id)])
        p=self.g.propose(c,self.lab.session())
        reviewed=self.g.review(id,p['event'],self.lab.session())
        s=self.g.approval_subject('OP-'+id,id,reviewed,self.lab.session())
        return c,p,reviewed,s,self.lab.approval(s)

    def approved(self,id='LAB-CHANGE'):
        c,p,r,s,proof=self.proposal(id)
        self.g.approve('OP-'+id,id,r,proof,self.lab.session('LAB-REVIEWER'))
        return c,p,r,s,proof

    def denied(self,call):
        with self.assertRaises((Denied,ValueError,KeyError,ChangeError,sqlite3.Error)):
            call()

    def attest_archive(self,archive):
        # An adversarial service can re-sign a manifest but cannot forge reviewer
        # proofs, external latest witness or independently retained nonce state.
        archive['serviceAttestation']=decode(self.lab.service_sign('acp-route-a-export-attestation/1',{'manifest':archive['manifest']}))
        return canonical_bytes(archive)

    def test_native_genesis_transition_signed_receipt_audit_retry_export_restore(self):
        self.bootstrap();c,p,r,s,proof=self.approved()
        receipt=self.g.apply('OP-LAB-CHANGE','LAB-RETRY',self.lab.session())
        op=self.g.ledger.get('OP-LAB-CHANGE')
        self.assertEqual('PUBLISHED',op['state'])
        self.assertEqual(1,self.g._repo.head()['sequence'])
        self.assertEqual(receipt,self.g.retrieve('OP-LAB-CHANGE',s,proof,op['bindings']['approvedEvent'],'LAB-RETRY',self.lab.session()))
        self.assertEqual(2,audit(self.g,self.lab.session())['entries'])
        raw=export(self.g,self.lab.session())
        result=restore(raw,self.root/'restored',self.lab.host,self.witness,lambda:self.lab.now,self.lab.session())
        self.assertEqual('VERIFIED_IN_QUARANTINE',result['status'])
        self.denied(lambda:Gateway(self.root/'restored',self.lab.host,self.witness,self.lab.service_sign,lambda:self.lab.now))

    def test_propose_and_review_have_no_proof_or_approval_reservation(self):
        self.bootstrap();before=self.g.ledger.export()['operations']
        self.proposal()
        self.assertEqual(before,self.g.ledger.export()['operations'])

    def test_original_application_and_nonlaboratory_configuration_rejected(self):
        for field,value in [('applicationId','APP-FIXTURE'),('applicationId','APP-CASE-MANAGEMENT'),('classification','PRODUCTION'),('algorithm','none')]:
            c=self.lab.host.config;c[field]=value
            self.denied(lambda:Host(canonical_bytes(c)))

    def test_immutable_host_and_context_copies(self):
        plan,s=self.g.genesis_subject(self.source,'author','G','R',self.lab.session())
        ctx=self.g._context(decode(s),self.lab.session(),'BOOTSTRAP')
        mutable=self.lab.host.config;mutable['repositoryId']='OTHER'
        self.assertEqual('LAB-REPOSITORY',ctx.host.config['repositoryId'])
        self.denied(lambda:Context(self.lab.host,bytearray(s),'author','x','BOOTSTRAP'))
        with self.assertRaises(AttributeError):ctx.action='SQL'

    def test_genesis_has_no_proposal_binding_and_rejects_fabricated_version(self):
        plan,s=self.g.genesis_subject(self.source,'author','G','R',self.lab.session())
        self.assertIsNone(decode(s)['proposalBinding'])
        bad=self.lab.approval(s,proposalBinding={'changeId':'fake','reviewRequiredEvent':{'serial':1,'digest':'x'}})
        self.denied(lambda:self.g.bootstrap(self.source,'author','G','R',bad,self.lab.session()))
        self.assertEqual([],self.g._repo.export_records()['journal'])

    def test_signature_and_closed_envelope_security_matrix(self):
        plan,s=self.g.genesis_subject(self.source,'author','G','R',self.lab.session())
        good=self.lab.approval(s)
        auth=self.g._authority(decode(s),self.lab.session(),'BOOTSTRAP')
        mutations={'repositoryId':'OTHER','applicationId':'OTHER','authorPrincipal':'other',
            'reviewerPrincipal':'author','candidateDigest':'sha256:'+'0'*64,'planDigest':'sha256:'+'0'*64,
            'requiredScopes':['SEMANTIC'],'expectedHead':{},'operationId':'OTHER','authorityConfigurationDigest':'OTHER',
            'issuedAt':1001,'notBefore':1001,'expiresAt':999,'keyId':'UNKNOWN','algorithm':'none',
            'verificationPolicyVersion':'UNKNOWN','identityEvidenceDigest':'x','grantEvidenceDigest':'x',
            'permittedUse':'SQL','genesisRetryIdentity':'OTHER'}
        for field,value in mutations.items():
            with self.subTest(field=field):
                bad=self.lab.approval(s,**{field:value})
                self.denied(lambda:auth.verify(decode(bad),request(plan),self.lab.now))
        e=decode(good);e['body']['planDigest']='TAMPERED'
        self.denied(lambda:auth.verify(e,request(plan),self.lab.now))
        for mutation in ('bad-signature','unknown-field','old-version'):
            e=decode(good)
            if mutation=='bad-signature':e['signature']='AAAA'
            elif mutation=='unknown-field':e['body']['extra']=True
            else:e['proofVersion']='acp-route-a-approval/1'
            self.denied(lambda:auth.verify(e,request(plan),self.lab.now))
        self.denied(lambda:decode(b'{"x":1,"x":2}'))
        self.denied(lambda:decode(b'{ "x":1}'))

    def test_authentication_and_independent_reviewer_grants(self):
        self.bootstrap();c,p,r,s,proof=self.proposal()
        for caller in ('author','other','limited'):
            with self.subTest(caller=caller):
                self.denied(lambda:self.g.approve('OP-LAB-CHANGE','LAB-CHANGE',r,proof,self.lab.session(caller)))
        for overrides in ({'principal':'other'},{'repositoryId':'OTHER'},{'serviceId':'OTHER'},{'expiresAt':999},{'notBefore':1001}):
            with self.subTest(overrides=overrides):
                self.denied(lambda:self.g.approval_subject('OP-LAB-CHANGE','LAB-CHANGE',r,self.lab.session(**overrides)))

    def test_revoked_grants_and_keys_at_original_proof_time(self):
        plan,s=self.g.genesis_subject(self.source,'author','G','R',self.lab.session())
        proof=decode(self.lab.approval(s))
        for area in ('keys','grants'):
            config=self.lab.host.config
            item=next(k for k in config[area] if k.get('purpose')=='approval' or k.get('principal')=='LAB-REVIEWER')
            item['revokedAt']=999
            host=self.lab.authenticated_host(config)
            changed=decode(s);changed['authorityConfigurationDigest']=host.digest
            ctx=Context(host,canonical_bytes(changed),'author','LAB','AUDIT_READ')
            key=next(k for k in host.config['keys'] if k['purpose']=='approval')
            body={**proof['body'],**changed,'identityEvidenceDigest':hashed(canonical_bytes(key))}
            # Genuine test signature and matching registered subject; rejection
            # must reach the independently varied key/grant revocation control.
            wire=self.lab.sign('approval','acp-route-a-approval/2',body)
            self.denied(lambda:Authority(ctx,lambda:1000).verify_historical(decode(wire),request(plan),1000))

    def test_duplicate_genesis_and_cross_repository_replay(self):
        s,proof,_=self.bootstrap()
        self.denied(lambda:self.g.bootstrap(self.source,'author','LAB-GENESIS','LAB-GENESIS-RETRY',proof,self.lab.session()))
        config=self.lab.host.config;config['repositoryId']='LAB-OTHER-REPOSITORY'
        host=self.lab.authenticated_host(config);changed=decode(s)
        changed.update(repositoryId=config['repositoryId'],authorityConfigurationDigest=host.digest)
        self.denied(lambda:Authority(Context(host,canonical_bytes(changed),'author','LAB','BOOTSTRAP'),lambda:1000).verify(decode(proof),decode(s)['request'],1000))

    def test_changed_review_event_new_proposal_cannot_inherit_approval(self):
        self.bootstrap();c,p,r,s,proof=self.proposal()
        changed=copy.deepcopy(c);changed['operations'][0]['node']['name']='SECOND-VERSION'
        new=self.g.propose(changed,self.lab.session())
        r2=self.g.review(c['id'],new['event'],self.lab.session())
        self.assertNotEqual(r,r2)
        self.denied(lambda:self.g.approve('OP-LAB-CHANGE',c['id'],r,proof,self.lab.session('LAB-REVIEWER')))
        self.denied(lambda:self.g.approve('OP-LAB-CHANGE',c['id'],r2,proof,self.lab.session('LAB-REVIEWER')))

    def test_changed_approved_event_and_proof_rejected(self):
        self.bootstrap();c,p,r,s,proof=self.approved()
        # Native edit is a test adversary bypassing the gateway; real filesystem isolation
        # must exclude this path. The gateway observes and rejects its changed event.
        from tooling.reference_authority import ReferenceAuthority
        auth=ReferenceAuthority(b'LAB-ONLY'*8,{'s':'author'},{})
        self.g._repo.propose(c,auth,'s')
        self.denied(lambda:self.g.apply('OP-LAB-CHANGE','R',self.lab.session()))

    def test_expiry_between_approve_and_apply(self):
        self.bootstrap();self.approved();self.lab.now=1300
        self.denied(lambda:self.g.apply('OP-LAB-CHANGE','R',self.lab.session()))
        self.assertEqual(0,self.g._repo.head()['sequence'])

    def test_retry_read_rejects_all_binding_changes_and_no_native_apply_shortcut(self):
        self.bootstrap();_,_,_,s,proof=self.approved();self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        op=self.g.ledger.get('OP-LAB-CHANGE');ref=op['bindings']['approvedEvent']
        args=['OP-LAB-CHANGE',s,proof,ref,'R',self.lab.session()]
        for index,value in [(0,'UNKNOWN'),(1,canonical_bytes({**decode(s),'planDigest':'OTHER'})),
                            (2,self.lab.approval(s,nonce='OTHER')),(3,{'serial':999,'digest':'OTHER'}),
                            (4,'OTHER'),(5,self.lab.session('other')),(5,self.lab.session(expiresAt=999))]:
            bad=args.copy();bad[index]=value
            with self.subTest(index=index):self.denied(lambda:self.g.retrieve(*bad))
        self.denied(lambda:self.g.apply('OP-LAB-CHANGE','R',self.lab.session('other')))

    def test_unpublished_receipt_never_retrieved(self):
        self.bootstrap();_,_,_,s,proof=self.approved()
        def outage_after_commit(stage):
            if stage=='after_commit':self.lab.outage=True
        self.g.failpoint=outage_after_commit
        with self.assertRaises(Exception):self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        op=self.g.ledger.get('OP-LAB-CHANGE')
        self.denied(lambda:self.g.retrieve('OP-LAB-CHANGE',s,proof,op['bindings']['approvedEvent'],'R',self.lab.session()))
        self.lab.outage=False
        self.g.failpoint=lambda _:None
        self.g.recover('OP-LAB-CHANGE',self.lab.session())
        self.assertEqual('PUBLISHED',self.g.ledger.get('OP-LAB-CHANGE')['state'])

    def test_receipt_corruption_and_witness_fork_stale_outage(self):
        _,_,raw=self.bootstrap();op=self.g.ledger.get('LAB-GENESIS')
        bad=decode(raw);bad['body']['commit']['planDigest']='OTHER'
        self.denied(lambda:verify_receipt(self.lab.host,canonical_bytes(bad),op['bindings']['commit']))
        for flag in ('fork','stale'):
            setattr(self.lab,flag,True)
            with self.subTest(flag=flag):self.denied(lambda:audit(self.g,self.lab.session()))
            setattr(self.lab,flag,False)
        self.lab.outage=True
        with self.assertRaises(Exception):audit(self.g,self.lab.session())

    def test_competing_process_writer_and_lost_ownership(self):
        ctx=multiprocessing.get_context('spawn')
        with Fence(self.g.lock_path) as fence:
            q=ctx.Queue()
            p=ctx.Process(target=competing_worker,args=(self.g.lock_path,os.getpid(),q));p.start();p.join(10)
            self.assertEqual(0,p.exitcode);self.assertEqual('DENIED',q.get(timeout=1));self.assertEqual('LOST',q.get(timeout=1))
            q.close();q.join_thread()
            fence.assert_owned()
        with Fence(self.g.lock_path) as fence:fence.assert_owned()

    def test_durable_ledger_cas_nonce_and_illegal_transitions(self):
        self.bootstrap();_,_,_,s,proof=self.approved()
        with Fence(self.g.lock_path) as fence:
            epoch=self.g.ledger.epoch(fence);op=self.g.ledger.get('OP-LAB-CHANGE')
            self.denied(lambda:self.g.ledger.transition('OP-LAB-CHANGE','PUBLISHED',op['version'],epoch,{'publication':'fake'},fence))
            self.denied(lambda:self.g.ledger.transition('OP-LAB-CHANGE','RECOVERY_REQUIRED',999,epoch,{'reason':'LAB'},fence))
            self.denied(lambda:self.g.ledger.transition('OP-LAB-CHANGE','RECOVERY_REQUIRED',op['version'],epoch-1,{'reason':'LAB'},fence))
            self.denied(lambda:self.g.ledger.reserve(s,op['plan'],decode(proof),fence,epoch))
            self.g.ledger.transition('OP-LAB-CHANGE','QUARANTINED',op['version'],epoch,{'reason':'LAB'},fence)
        self.denied(lambda:self.g.recover('OP-LAB-CHANGE',self.lab.session()))

    def test_crash_at_every_native_and_external_boundary_then_reconcile(self):
        self.bootstrap()
        points=['after_snapshot','before_commit','after_commit','after_journal_committed',
                'after_receipt_persistence','after_receipt_stored','after_witnessed','after_published']
        ctx=multiprocessing.get_context('spawn')
        for n,point in enumerate(points):
            with self.subTest(point=point):
                id='CRASH-'+str(n);self.approved(id)
                process=ctx.Process(target=crash_worker,args=(self.root/'repository',self.lab.host.raw,self.lab.host.registration,self.lab.host.registration_root,
                    self.lab.server.server_port,self.lab.keys['receipt'].private_bytes_raw(),self.lab.now,
                    'OP-'+id,'R-'+id,self.lab.session(),point))
                process.start();process.join(60)
                if process.is_alive():process.kill();process.join();self.fail('laboratory crash worker timed out')
                self.assertEqual(73,process.exitcode)
                self.g=self.gateway()
                op=self.g.ledger.get('OP-'+id)
                if op['state']!='PUBLISHED':self.g.recover('OP-'+id,self.lab.session())
                self.assertEqual('PUBLISHED',self.g.ledger.get('OP-'+id)['state'])
                self.assertEqual(n+1,self.g._repo.head()['sequence'])
                self.assertEqual(n+2,audit(self.g,self.lab.session())['entries'])

    def test_approval_crash_before_and_after_native_approval(self):
        self.bootstrap()
        _,_,reviewed,s,proof=self.proposal()
        def fault(stage):
            if stage=='after_native_approval':raise RuntimeError('LAB interruption')
        self.g.failpoint=fault
        with self.assertRaises(RuntimeError):self.g.approve('OP-LAB-CHANGE','LAB-CHANGE',reviewed,proof,self.lab.session('LAB-REVIEWER'))
        self.g=self.gateway()
        self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.assertEqual('PUBLISHED',self.g.ledger.get('OP-LAB-CHANGE')['state'])

    def test_restore_corruption_wrong_identity_missing_authority_receipts_truncation(self):
        self.bootstrap();raw=export(self.g,self.lab.session())
        for case in ('hash','repository','missing-receipt','missing-trust','truncated'):
            a=decode(raw)
            if case=='hash':a['manifest']['files']['native.json']='OTHER'
            elif case=='repository':a['manifest']['repositoryId']='OTHER'
            elif case=='missing-trust':del a['files']['authority-history.json']
            elif case=='missing-receipt':
                a['files']['ledger.json']['bindings']=[r for r in a['files']['ledger.json']['bindings'] if r[1]!='receipt']
                a['manifest']['files']['ledger.json']=hashed(canonical_bytes(a['files']['ledger.json']))
            else:
                a['files']['native.json']['journal']=[]
                a['manifest']['files']['native.json']=hashed(canonical_bytes(a['files']['native.json']))
            with self.subTest(case=case):self.denied(lambda:restore(self.attest_archive(a),self.root/('restore-'+case),self.lab.host,self.witness,lambda:self.lab.now,self.lab.session()))

    def test_stale_backup_after_real_second_commit_is_rejected(self):
        self.bootstrap();raw=export(self.g,self.lab.session());self.approved();self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.denied(lambda:restore(raw,self.root/'stale',self.lab.host,self.witness,lambda:self.lab.now,self.lab.session()))

    def test_history_scopes_never_authorize_sql_or_deployment(self):
        self.bootstrap()
        for action in ('SQL','DEPLOYMENT','DATA_BINDING','POSTGRESQL_MIGRATION'):
            self.denied(lambda:self.g.downstream(action,self.lab.session()))

    def test_independent_authenticated_migration_declaration_is_required(self):
        self.bootstrap()
        c=change('LAB-MIGRATION',self.g._repo.head(),[revise(self.g._repo.snapshot(),'FACT-A',name='MIGRATION-TEST')],migration_plan=migration())
        p=self.g.propose(c,self.lab.session());r=self.g.review(c['id'],p['event'],self.lab.session())
        s=self.g.approval_subject('OP-MIGRATION',c['id'],r,self.lab.session())
        self.assertIn('MIGRATION',p['plan']['requiredScopes'])
        d=self.lab.sign('approval','acp-route-a-migration-declaration/1',{
            'repositoryId':self.lab.host.config['repositoryId'],'applicationId':self.lab.host.config['applicationId'],
            'authorityConfigurationDigest':self.lab.host.digest,'planDigest':p['plan']['planDigest'],
            'migrationDeclarationDigest':hashed(canonical_bytes(c['migration'])),'reviewerPrincipal':'LAB-REVIEWER',
            'issuedAt':1000,'notBefore':1000,'expiresAt':1200,'permittedUse':'DECLARATION_IN_HISTORY_ONLY','decision':'APPROVED'})
        proof=self.lab.approval(s,migrationDeclarationDecisionDigest=hashed(d))
        self.denied(lambda:self.g.approve('OP-MIGRATION',c['id'],r,proof,self.lab.session('LAB-REVIEWER')))
        self.g.approve('OP-MIGRATION',c['id'],r,proof,self.lab.session('LAB-REVIEWER'),d)
        self.g.apply('OP-MIGRATION','R',self.lab.session())
        self.assertEqual(2,audit(self.g,self.lab.session())['entries'])
        self.denied(lambda:self.g.downstream('SQL'))

    def test_replayed_nonce_and_approval_id_rejected_after_publication(self):
        self.bootstrap();self.approved('FIRST');self.g.apply('OP-FIRST','FIRST-R',self.lab.session())
        for key in ('nonce','approvalId'):
            _,_,r,s,_=self.proposal('SECOND-'+key)
            old=self.g.ledger.get('OP-FIRST')['proof']['body'][key]
            proof=self.lab.approval(s,**{key:old})
            self.denied(lambda:self.g.approve('OP-SECOND-'+key,'SECOND-'+key,r,proof,self.lab.session('LAB-REVIEWER')))
        self.assertEqual(1,self.g._repo.head()['sequence'])

    def test_stale_head_and_changed_read_set_fail_before_new_append(self):
        self.bootstrap();first=self.proposal('FIRST');c,p,r,s,proof=self.proposal('STALE')
        self.g.approve('OP-FIRST','FIRST',first[2],first[4],self.lab.session('LAB-REVIEWER'))
        # A second approval cannot reserve while FIRST remains unresolved.
        self.denied(lambda:self.g.approve('OP-STALE','STALE',r,proof,self.lab.session('LAB-REVIEWER')))
        self.g.apply('OP-FIRST','FIRST-R',self.lab.session())
        self.denied(lambda:self.g.approve('OP-STALE','STALE',r,proof,self.lab.session('LAB-REVIEWER')))
        from changes import stale_reads
        self.assertTrue(stale_reads(p['plan'],self.g._repo.snapshot()))
        self.assertEqual(1,self.g._repo.head()['sequence'])

    def test_live_revocation_and_historical_proof_time_verification_are_distinct(self):
        config=self.lab.host.config
        key=next(k for k in config['keys'] if k['purpose']=='approval');key['revokedAt']=1100
        grant=next(g for g in config['grants'] if g['principal']=='LAB-REVIEWER');grant['revokedAt']=1100
        self.lab.host=self.lab.authenticated_host(config)
        self.witness=WitnessClient(self.lab.host,self.lab,lambda:self.lab.now,self.root/'revocation-reader.sqlite')
        g=Gateway(self.root/'revocation',self.lab.host,self.witness,self.lab.service_sign,lambda:self.lab.now)
        plan,s=g.genesis_subject(self.source,'author','G','R',self.lab.session())
        proof=decode(self.lab.approval(s))
        auth=g._authority(decode(s),self.lab.session(),'BOOTSTRAP')
        self.assertEqual('LAB-REVIEWER',auth.verify_historical(proof,request(plan),1000)['principal'])
        self.denied(lambda:auth.verify(proof,request(plan),1150))
        # Missing historical key evidence cannot fall back to structural audit.
        config=self.lab.host.config;config['keys']=[k for k in config['keys'] if k['purpose']!='approval']
        host=Host(canonical_bytes(config));new=decode(s);new['authorityConfigurationDigest']=host.digest
        self.denied(lambda:Authority(Context(host,canonical_bytes(new),'author','LAB','AUDIT_READ'),lambda:1000).verify_historical(proof,request(plan),1000))

    def test_reservation_crash_reconciles_exact_native_review_without_new_proof(self):
        self.bootstrap();_,_,r,s,proof=self.proposal()
        def fault(stage):
            if stage=='after_reservation':raise RuntimeError('LAB crash')
        self.g.failpoint=fault
        with self.assertRaises(RuntimeError):self.g.approve('OP-LAB-CHANGE','LAB-CHANGE',r,proof,self.lab.session('LAB-REVIEWER'))
        self.g=self.gateway();status=self.g.recover('OP-LAB-CHANGE',self.lab.session())
        self.assertEqual('APPROVED_RESERVED',status['status'])
        self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.assertEqual('PUBLISHED',self.g.ledger.get('OP-LAB-CHANGE')['state'])

    def test_missing_native_commit_after_stable_commit_remains_recovery_required(self):
        self.bootstrap();self.approved()
        def fault(stage):
            if stage=='after_journal_committed':raise RuntimeError('LAB crash')
        self.g.failpoint=fault
        with self.assertRaises(RuntimeError):self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.assertEqual('RECOVERY_REQUIRED',self.g.ledger.get('OP-LAB-CHANGE')['state'])
        # Remove the file as an adversarial missing store. Do not manufacture a replacement.
        os.rename(self.g._repo.path,str(self.g._repo.path)+'.lost')
        with self.assertRaises(Exception):self.g.recover('OP-LAB-CHANGE',self.lab.session())
        self.assertEqual('RECOVERY_REQUIRED',self.g.ledger.get('OP-LAB-CHANGE')['state'])

    def test_authenticated_witness_conflict_quarantines_unpublished_commit(self):
        self.bootstrap();self.approved()
        def fault(stage):
            if stage=='after_commit':self.lab.fork=True
        self.g.failpoint=fault
        self.denied(lambda:self.g.apply('OP-LAB-CHANGE','R',self.lab.session()))
        self.assertEqual('QUARANTINED',self.g.ledger.get('OP-LAB-CHANGE')['state'])
        self.lab.fork=False
        self.denied(lambda:self.g.recover('OP-LAB-CHANGE',self.lab.session()))

    def test_self_approval_even_with_both_grants_and_valid_signature_is_rejected(self):
        config=self.lab.host.config
        next(k for k in config['keys'] if k['purpose']=='approval')['principal']='author'
        author=next(g for g in config['grants'] if g['principal']=='author')
        author['actions'].append('APPROVE');author['scopes']=['SEMANTIC','SECURITY']
        self.lab.host=self.lab.authenticated_host(config)
        witness=WitnessClient(self.lab.host,self.lab,lambda:self.lab.now,self.root/'self-approval-reader.sqlite')
        g=Gateway(self.root/'self-approval',self.lab.host,witness,self.lab.service_sign,lambda:self.lab.now)
        plan,s=g.genesis_subject(self.source,'author','G','R',self.lab.session())
        proof=self.lab.approval(s,reviewerPrincipal='author',grantEvidenceDigest=self.lab.host.grant('author','APPROVE',plan['requiredScopes'],1000))
        self.denied(lambda:g.bootstrap(self.source,'author','G','R',proof,self.lab.session()))
        self.assertEqual([],g._repo.export_records()['journal'])

    def test_retired_nonce_is_retained_and_expiry_cannot_hide_commit(self):
        self.bootstrap();self.approved('EXPIRES');self.lab.now=1250
        self.g.retire_uncommitted('OP-EXPIRES','EXPIRED',self.lab.session())
        self.denied(lambda:self.g.recover('OP-EXPIRES',self.lab.session()))
        self.approved('NEXT');self.g.apply('OP-NEXT','R',self.lab.session())
        self.denied(lambda:self.g.retire_uncommitted('OP-NEXT','REJECTED',self.lab.session()))
        self.assertEqual(2,audit(self.g,self.lab.session())['entries'])
        result=restore(export(self.g,self.lab.session()),self.root/'with-retirement',self.lab.host,self.witness,lambda:self.lab.now,self.lab.session())
        self.assertEqual('VERIFIED_IN_QUARANTINE',result['status'])

    def test_signed_service_claim_without_authentic_human_approval_is_rejected_by_witness(self):
        self.bootstrap();self.approved()
        def fault(stage):
            if stage=='after_receipt_stored':raise RuntimeError('LAB pause')
        self.g.failpoint=fault
        with self.assertRaises(RuntimeError):self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        op=self.g.ledger.get('OP-LAB-CHANGE');exported=self.g._repo.export_records()
        row=next(r for r in exported['journal'] if r[0]==1)
        proposals=[r for r in exported['proposals'] if r[2] in {'REVIEW_REQUIRED','APPROVED'}]
        bundle={'row':copy.deepcopy(row),'proposals':proposals,'migrationDecision':None}
        bundle['row'][3]['approval']['proof']['signature']='AAAA'
        from engineering.route_a_gateway.evidence import verify_witness_submission
        checkpoint,_=self.witness.latest()
        previous=exported['journal'][0][3]
        self.denied(lambda:verify_witness_submission(self.lab.host,op['bindings']['commit'],canonical_bytes(op['bindings']['receipt']),bundle,checkpoint,previous))
        self.assertEqual(0,self.witness.latest()[0]['head']['sequence'])

    def _genesis_crash(self,point):
        plan,s=self.g.genesis_subject(self.source,'author','LAB-GENESIS','R',self.lab.session())
        proof=self.lab.approval(s)
        process=multiprocessing.get_context('spawn').Process(target=crash_worker,args=(self.root/'repository',
            self.lab.host.raw,self.lab.host.registration,self.lab.host.registration_root,self.lab.server.server_port,self.lab.keys['receipt'].private_bytes_raw(),
            self.lab.now,'LAB-GENESIS','R',self.lab.session(),point,{'source':self.source,'proof':proof}))
        process.start();process.join(30)
        if process.is_alive():process.kill();process.join();self.fail('genesis crash worker timed out')
        self.assertEqual(73,process.exitcode)
        self.g=self.gateway();self.g.recover('LAB-GENESIS',self.lab.session())
        self.assertEqual(1,audit(self.g,self.lab.session())['entries'])

    def test_genesis_process_crash_during_snapshot_rolls_back(self):self._genesis_crash('after_snapshot')
    def test_genesis_process_crash_before_commit_rolls_back(self):self._genesis_crash('before_commit')
    def test_genesis_process_crash_after_commit_reconciles(self):self._genesis_crash('after_commit')

    def test_freshly_signed_stale_witness_head_cannot_rollback_reader(self):
        self.bootstrap();old=self.witness.latest()[0]
        self.approved();self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        original=self.lab.latest
        def stale(challenge):
            return self.lab.sign('witness','acp-route-a-witness-response/1',{'repositoryId':self.lab.host.config['repositoryId'],
                'applicationId':self.lab.host.config['applicationId'],'challenge':challenge,'observedAt':self.lab.now,'checkpoint':old})
        self.lab.latest=stale
        self.denied(lambda:self.witness.latest())
        self.lab.latest=original
        self.assertEqual(1,self.witness.latest()[0]['head']['sequence'])

    def test_corrupted_durable_event_cannot_be_hidden_by_rehashing_export_manifest(self):
        self.bootstrap();a=decode(export(self.g,self.lab.session()))
        e=next(e for e in a['files']['ledger.json']['events'] if e[3]=='RECEIPT_STORED')
        e[5]['receipt']='sha256:'+'0'*64
        a['manifest']['files']['ledger.json']=hashed(canonical_bytes(a['files']['ledger.json']))
        self.denied(lambda:restore(self.attest_archive(a),self.root/'tampered-ledger',self.lab.host,self.witness,lambda:self.lab.now,self.lab.session()))

    def test_authenticated_host_configuration_rejects_client_substitution(self):
        host=self.lab.host
        raw=host.raw
        wrong_root=Ed25519PrivateKey.generate().public_key().public_bytes_raw()
        self.denied(lambda:Host(raw,host.registration,wrong_root))
        altered=host.config;altered['repositoryId']='CLIENT-SELECTED'
        self.denied(lambda:Host(canonical_bytes(altered),host.registration,host.registration_root))
        e=decode(host.registration);e['body']['serviceId']='CLIENT-ENDPOINT'
        self.denied(lambda:Host(raw,canonical_bytes(e),host.registration_root))
        self.denied(lambda:Gateway(self.root/'unregistered',Host(raw),self.witness,self.lab.service_sign,lambda:self.lab.now))
        self.denied(lambda:host.check_registration(100001))

    def test_recovery_grant_cannot_bypass_independent_receipt_read(self):
        config=self.lab.host.config
        next(g for g in config['grants'] if g['principal']=='other')['actions'].append('RECOVER')
        self.lab.host=self.lab.authenticated_host(config)
        self.witness=WitnessClient(self.lab.host,self.lab,lambda:self.lab.now,self.root/'recovery-reader.sqlite')
        self.g=Gateway(self.root/'recovery-only',self.lab.host,self.witness,self.lab.service_sign,lambda:self.lab.now)
        self.bootstrap();_,_,_,s,proof=self.approved()
        def fault(stage):
            if stage=='after_receipt_stored':raise RuntimeError('LAB interruption')
        self.g.failpoint=fault
        with self.assertRaises(RuntimeError):self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.g.failpoint=lambda _:None
        result=self.g.recover('OP-LAB-CHANGE',self.lab.session('other'))
        self.assertEqual('PUBLISHED',result['status']);self.assertNotIn('receipt',result)
        op=self.g.ledger.get('OP-LAB-CHANGE')
        self.denied(lambda:self.g.retrieve('OP-LAB-CHANGE',s,proof,op['bindings']['approvedEvent'],'R',self.lab.session('other')))

    def test_witness_conflict_during_recovery_also_quarantines(self):
        self.bootstrap();self.approved()
        def outage_after_commit(stage):
            if stage=='after_commit':self.lab.outage=True
        self.g.failpoint=outage_after_commit
        with self.assertRaises(Exception):self.g.apply('OP-LAB-CHANGE','R',self.lab.session())
        self.lab.outage=False;self.lab.fork=True;self.g.failpoint=lambda _:None
        self.denied(lambda:self.g.recover('OP-LAB-CHANGE',self.lab.session()))
        self.assertEqual('QUARANTINED',self.g.ledger.get('OP-LAB-CHANGE')['state'])

    def test_restore_cannot_erase_retired_nonce_at_unchanged_journal_head(self):
        self.bootstrap();self.approved('RETIRED')
        self.g.retire_uncommitted('OP-RETIRED','REJECTED',self.lab.session())
        original=decode(export(self.g,self.lab.session()))
        forged=copy.deepcopy(original)
        data=forged['files']['ledger.json']
        for table in ('operations','events','bindings'):
            data[table]=[r for r in data[table] if r[0]!='OP-RETIRED']
        forged['manifest']['files']['ledger.json']=hashed(canonical_bytes(data))
        forged['manifest']['ledgerObserverDigest']=hashed(canonical_bytes(data))
        # Native head, journal, receipts and all recomputed archive hashes still match.
        self.assertEqual(original['manifest']['head'],forged['manifest']['head'])
        self.denied(lambda:restore(self.attest_archive(forged),self.root/'lost-retirement',self.lab.host,self.witness,lambda:self.lab.now,self.lab.session()))

    def test_export_service_attestation_protects_metadata_and_exporter_identity(self):
        self.bootstrap();original=decode(export(self.g,self.lab.session()))
        for field,value in [('exporter','other'),('capturedAt',999),('authorityConfigurationDigest','OTHER')]:
            bad=copy.deepcopy(original);bad['manifest'][field]=value
            with self.subTest(field=field):
                self.denied(lambda:restore(canonical_bytes(bad),self.root/('metadata-'+field),self.lab.host,self.witness,lambda:self.lab.now,self.lab.session()))
        bad=copy.deepcopy(original);bad['manifest']['exporter']='other'
        self.denied(lambda:restore(self.attest_archive(bad),self.root/'wrong-export-grant',self.lab.host,self.witness,lambda:self.lab.now,self.lab.session()))


if __name__=='__main__':unittest.main()
