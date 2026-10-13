"""Fenced external orchestration over unchanged native history interfaces.

    Engineering laboratory only. No network endpoint, enrollment, SQL or deployment API.
"""
from pathlib import Path
import os
from canonical_json import canonical_bytes, loads
from changes import genesis, prepare, request, fingerprint, ChangeError
from history_repository import HistoryRepository
from .security import Host, Context, Authority, require, hashed, decode, Denied, subject
from .storage import Fence, Ledger, NORMAL
from .evidence import commit_evidence, verify_receipt, RECEIPT, WitnessConflict


def event_ref(host,row):
    return {'serial':row[0],'digest':hashed(b'acp-route-a-proposal-event/1\0'+canonical_bytes({
        'repositoryId':host.config['repositoryId'],'applicationId':host.config['applicationId'],'row':row}))}


class Gateway:
    def __init__(self,directory,host,witness,receipt_signer,clock,failpoint=None):
        require(type(host) is Host,'trusted immutable host required')
        host.current_authority(clock())
        self.directory=Path(directory)
        self.directory.mkdir(mode=0o700,parents=True,exist_ok=True)
        require(not self.directory.is_symlink(),'symlink repository forbidden')
        stat=self.directory.stat()
        require(stat.st_uid == os.getuid() and stat.st_mode & 0o077 == 0,'private single-host directory required')
        require(not (self.directory/'QUARANTINED_RESTORE').exists(),'restore cannot acquire write gateway')
        self.host,self.witness,self.signer,self.clock=host,witness,receipt_signer,clock
        self.failpoint=failpoint or (lambda _:None)
        self.lock_path=self.directory/'writer.lock'
        with Fence(self.lock_path) as fence:
            self._repo=HistoryRepository(self.directory/'native.sqlite')
            self.ledger=Ledger(self.directory/'ledger.sqlite',host)
            self.ledger.validate()
            existing=self.ledger.export()
            self.witness.verify_ledger(existing,require_checkpoint=bool(existing['operations']))

    def _caller(self,session,action,scopes=()):
        self.host.check_registration(self.clock())
        return self.host.authenticate(session,self.clock(),action,scopes)

    def _context(self,s,session,action,plan=None,migration_decision=None):
        caller,evidence=self._caller(session,action)
        return Context(self.host,canonical_bytes(s),caller,evidence,action,
                       canonical_bytes(plan) if plan is not None else None,migration_decision,
                       self.host.current_authority(self.clock()).raw)

    def _authority(self,s,session,action,plan=None,migration_decision=None):
        return Authority(self._context(s,session,action,plan,migration_decision),self.clock)

    def _head(self):
        rows=self._repo.export_records()['journal']
        if not rows:return 'EMPTY_UNINITIALIZED'
        row=rows[-1]
        return {'sequence':row[0],'digest':row[3]['plan']['candidate']['contentDigest'],'journalDigest':row[2]}

    def _published_head(self,fence):
        self.ledger.validate()
        existing=self.ledger.export()
        self.witness.verify_ledger(existing,require_checkpoint=bool(existing['operations']))
        for row in self.ledger.export()['operations']:
            require(self.ledger.get(row[0])['state'] in {'PUBLISHED','REJECTED','EXPIRED'},'unresolved operation blocks native writes')
        self._repo.audit()
        head=self._head()
        checkpoint,_=self.witness.latest()
        require((checkpoint is None and head=='EMPTY_UNINITIALIZED') or
                (checkpoint is not None and checkpoint['head']==head),'native head disagrees with independent latest witness')
        if checkpoint is not None:
            from .archive import audit_locked
            audit_locked(self,fence)
            rows=self.ledger.export()['operations']
            matches=[self.ledger.get(r[0]) for r in rows if self.ledger.get(r[0])['bindings'].get('commit',{}).get('newHead')==head]
            require(len(matches)==1 and matches[0]['state']=='PUBLISHED','head not durably published')
            receipt=canonical_bytes(matches[0]['bindings']['receipt'])
            require(verify_receipt(self.host,receipt,matches[0]['bindings']['commit'],self.clock()) == checkpoint['receiptDigest'],'witness receipt mismatch')
        return head

    def _event(self,change_id,state):
        rows=[r for r in self._repo.export_records()['proposals'] if r[1]==change_id]
        require(bool(rows) and rows[-1][2]==state,'wrong current proposal lifecycle')
        row=rows[-1]
        p=self._repo.proposal(change_id)
        require(p=={'state':row[2],'planDigest':row[3],**row[4]},'native event read mismatch')
        return row,rows

    def propose(self,change,session):
        # Never reserve an approval/nonce for a proof-free submission.
        caller,evidence=self._caller(session,'PROPOSE')
        change=decode(canonical_bytes(change))
        require(caller==change['author'],'wrong authenticated author')
        with Fence(self.lock_path) as fence:
            require(self._published_head(fence)==change['base'],'stale current base')
            plan=prepare(self._repo.snapshot(),change)
            require(plan['candidate']['content']['applicationId']==self.host.config['applicationId'],'wrong application')
            # Native propose uses only authenticate; context still pins exact plan/head.
            pre={'repositoryId':self.host.config['repositoryId'],'applicationId':self.host.config['applicationId'],
                 'authorityConfigurationDigest':self.host.digest,'plan':plan,'base':change['base']}
            authority=Authority(Context(self.host,canonical_bytes(pre),caller,evidence,'PROPOSE'),self.clock)
            fence.assert_owned()
            result=self._repo.propose(change,authority,session)
            require(result==plan,'native plan differs from reproduction')
            row,_=self._event(change['id'],'PROPOSED')
            return {'plan':plan,'event':event_ref(self.host,row)}

    def review(self,change_id,expected_event,session):
        caller,evidence=self._caller(session,'REVIEW')
        with Fence(self.lock_path) as fence:
            self._published_head(fence)
            row,_=self._event(change_id,'PROPOSED')
            require(event_ref(self.host,row)==expected_event and caller==row[4]['plan']['author'],'changed event or wrong author')
            pre={'repositoryId':self.host.config['repositoryId'],'applicationId':self.host.config['applicationId'],
                 'authorityConfigurationDigest':self.host.digest,'event':expected_event,'plan':row[4]['plan']}
            auth=Authority(Context(self.host,canonical_bytes(pre),caller,evidence,'REVIEW'),self.clock)
            fence.assert_owned();self._repo.review(change_id,auth,session)
            reviewed,_=self._event(change_id,'REVIEW_REQUIRED')
            return event_ref(self.host,reviewed)

    def approval_subject(self,operation,change_id,expected_event,session):
        self._caller(session,'REVIEW')
        with Fence(self.lock_path) as fence:
            head=self._published_head(fence)
            row,_=self._event(change_id,'REVIEW_REQUIRED')
            require(event_ref(self.host,row)==expected_event,'changed reviewed version')
            caller,_=self._caller(session,'REVIEW')
            require(caller==row[4]['plan']['author'],'wrong subject author')
            return subject(self.host,row[4]['plan'],operation,head,{'changeId':change_id,'reviewRequiredEvent':expected_event})

    def genesis_subject(self,source,author,operation,retry,session):
        caller,_=self._caller(session,'BOOTSTRAP')
        require(caller==author,'wrong genesis author')
        with Fence(self.lock_path) as fence:
            require(self._published_head(fence)=='EMPTY_UNINITIALIZED','duplicate genesis')
            plan=genesis(source,author)
            return plan,subject(self.host,plan,operation,'EMPTY_UNINITIALIZED',genesis_retry=retry)

    def approve(self,operation,change_id,expected_event,proof_raw,session,migration_decision=None):
        self._caller(session,'APPROVE')
        with Fence(self.lock_path) as fence:
            head=self._published_head(fence)
            row,_=self._event(change_id,'REVIEW_REQUIRED')
            require(event_ref(self.host,row)==expected_event,'changed reviewed version')
            plan=row[4]['plan']
            s=subject(self.host,plan,operation,head,{'changeId':change_id,'reviewRequiredEvent':expected_event})
            auth=self._authority(decode(s),session,'APPROVE',plan,migration_decision)
            proof=decode(proof_raw)
            verdict=auth.verify(proof,request(plan),self.clock())
            require(auth.context.caller==verdict['principal'],'wrong authenticated reviewer')
            epoch=self.ledger.epoch(fence)
            self.ledger.reserve(s,plan,proof,fence,epoch)
            if migration_decision is not None:
                self.ledger.bind(operation,'migrationDecision',decode(migration_decision),fence)
            self.witness.remember_ledger(self.ledger.export())
            self.failpoint('after_reservation')
            auth.authenticate(session)
            fence.assert_owned();self._repo.approve(change_id,proof,auth,self.clock())
            self.failpoint('after_native_approval')
            self._bind_approval(operation,fence)
            self.witness.remember_ledger(self.ledger.export())

    def _bind_approval(self,operation,fence):
        op=self.ledger.get(operation);s=op['subject']
        binding=s['proposalBinding']
        if binding is None:return None
        rows=[r for r in self._repo.export_records()['proposals'] if r[1]==binding['changeId']]
        # May be followed by APPLIED after a crash; approval itself remains exact.
        matches=[i for i,r in enumerate(rows) if r[2]=='APPROVED' and r[4].get('proof')==op['proof']]
        require(len(matches)==1,'missing or ambiguous approved event')
        i=matches[0];row=rows[i]
        require(i>0 and rows[i-1][2]=='REVIEW_REQUIRED' and event_ref(self.host,rows[i-1])==binding['reviewRequiredEvent']
                and row[4]['plan']==op['plan'],'approval predecessor/proof changed')
        ref=event_ref(self.host,row)
        self.ledger.bind(operation,'approvedEvent',ref,fence)
        return ref

    def bootstrap(self,source,author,operation,retry,proof_raw,session):
        self._caller(session,'BOOTSTRAP')
        with Fence(self.lock_path) as fence:
            require(self._published_head(fence)=='EMPTY_UNINITIALIZED','duplicate genesis')
            plan=genesis(source,author)
            s=subject(self.host,plan,operation,'EMPTY_UNINITIALIZED',genesis_retry=retry)
            auth=self._authority(decode(s),session,'BOOTSTRAP')
            require(auth.context.caller==author,'wrong genesis author')
            proof=decode(proof_raw);auth.verify(proof,request(plan),self.clock())
            epoch=self.ledger.epoch(fence)
            self.ledger.reserve(s,plan,proof,fence,epoch)
            self.ledger.bind(operation,'retry',retry,fence)
            self.witness.remember_ledger(self.ledger.export())
            try:
                self.failpoint('after_reservation')
                fence.assert_owned()
                self._repo.bootstrap(plan,proof,auth,self.clock(),session,self.failpoint)
                return self._finish(operation,fence,epoch)
            except Exception as error:
                self._recovery(operation,fence,epoch,error);raise

    def apply(self,operation,retry,session):
        self._caller(session,'APPLY')
        with Fence(self.lock_path) as fence:
            self.ledger.validate()
            self.witness.verify_ledger(self.ledger.export(),require_checkpoint=True)
            op=self.ledger.get(operation);s=op['subject']
            decision=op['bindings'].get('migrationDecision')
            auth=self._authority(s,session,'APPLY',op['plan'],canonical_bytes(decision) if decision else None)
            require(auth.context.caller==s['authorPrincipal'] and op['state']=='RESERVED','wrong author or unready operation')
            require(s['proposalBinding'] is not None,'genesis is not apply')
            auth.verify(op['proof'],request(op['plan']),self.clock())
            require(self._head()==s['expectedHead'],'stale journal head')
            checkpoint,_=self.witness.latest()
            require(checkpoint is not None and checkpoint['head']==self._head(),'unwitnessed predecessor')
            ref=self._bind_approval(operation,fence)
            row,_=self._event(s['proposalBinding']['changeId'],'APPROVED')
            require(event_ref(self.host,row)==ref,'changed approved event')
            require(type(retry) is str and 0<len(retry)<=128,'invalid retry identity')
            epoch=self.ledger.epoch(fence)
            self.ledger.bind(operation,'retry',retry,fence)
            self.witness.remember_ledger(self.ledger.export())
            try:
                fence.assert_owned()
                auth.authenticate(session)
                self._repo.apply(s['proposalBinding']['changeId'],retry,auth,self.clock(),self.failpoint)
                return self._finish(operation,fence,epoch)
            except Exception as error:
                self._recovery(operation,fence,epoch,error);raise

    def _recovery(self,operation,fence,epoch,error=None):
        op=self.ledger.get(operation)
        if isinstance(error,WitnessConflict) and op['state'] not in {'REJECTED','EXPIRED','QUARANTINED'}:
            self.ledger.transition(operation,'QUARANTINED',op['version'],epoch,{'reason':'authenticated witness conflict'},fence)
            self.witness.remember_ledger(self.ledger.export())
            return
        if op['state'] in NORMAL:
            self.ledger.transition(operation,'RECOVERY_REQUIRED',op['version'],epoch,{'reason':'interrupted external operation'},fence)
            self.witness.remember_ledger(self.ledger.export())

    def _commit(self,op,fence):
        self._repo.audit()
        rows=self._repo.export_records()['journal']
        matches=[r for r in rows if r[3]['plan']==op['plan'] and r[3]['approval']['proof']==op['proof']]
        require(len(matches)==1,'actual commit unavailable or ambiguous')
        row=matches[0]
        sequence=row[0]
        predecessor='EMPTY_UNINITIALIZED' if sequence==0 else {
            'sequence':sequence-1,'digest':rows[sequence-1][3]['plan']['candidate']['contentDigest'],
            'journalDigest':rows[sequence-1][2]}
        require(op['subject']['expectedHead']==predecessor,'independent predecessor mismatch')
        decision=op['bindings'].get('migrationDecision')
        context=Context(self.host,canonical_bytes(op['subject']),'HISTORICAL_VERIFIER',hashed(canonical_bytes(row)),'AUDIT_READ',
                        canonical_bytes(op['plan']),canonical_bytes(decision) if decision else None)
        require(Authority(context,self.clock).verify_historical(op['proof'],request(op['plan']),row[3]['committedAt'])
                ==row[3]['approval']['verdict'],'unauthenticated historical commit')
        approved=self._bind_approval(op['subject']['operationId'],fence)
        return commit_evidence(self.host,op['subject'],op['plan'],op['proof'],matches[0],approved,op['bindings']['retry'])

    def _move(self,operation,target,epoch,evidence,fence):
        op=self.ledger.get(operation)
        self.ledger.transition(operation,target,op['version'],epoch,evidence,fence)
        self.witness.remember_ledger(self.ledger.export())
        self.failpoint('after_'+target.lower())

    def _finish(self,operation,fence,epoch):
        self.host.current_authority(self.clock())
        op=self.ledger.get(operation)
        commit=self._commit(op,fence)
        self.ledger.bind(operation,'commit',commit,fence)
        if op['state']=='RESERVED':self._move(operation,'JOURNAL_COMMITTED',epoch,{'commit':hashed(canonical_bytes(commit))},fence)
        op=self.ledger.get(operation)
        if op['state']=='JOURNAL_COMMITTED':
            receipt=op['bindings'].get('receipt')
            raw=canonical_bytes(receipt) if receipt else self.signer(RECEIPT,{'commit':commit,'issuedAt':self.clock()})
            rd=verify_receipt(self.host,raw,commit,self.clock())
            self.ledger.bind(operation,'receipt',decode(raw),fence)
            self.witness.remember_ledger(self.ledger.export())
            self.failpoint('after_receipt_persistence')
            self._move(operation,'RECEIPT_STORED',epoch,{'receipt':rd},fence)
        op=self.ledger.get(operation)
        if op['state']=='RECEIPT_STORED':
            rd=verify_receipt(self.host,canonical_bytes(op['bindings']['receipt']),commit,self.clock())
            exported=self._repo.export_records()
            row=next(r for r in exported['journal'] if r[2]==commit['newHead']['journalDigest'])
            proposals=[]
            if op['subject']['proposalBinding'] is not None:
                events=[r for r in exported['proposals'] if r[1]==op['plan']['change']['id']]
                i=next(i for i,r in enumerate(events) if event_ref(self.host,r)==op['bindings']['approvedEvent'])
                proposals=events[i-1:i+1]
            bundle={'row':row,'proposals':proposals,'migrationDecision':op['bindings'].get('migrationDecision')}
            checkpoint,raw=self.witness.advance(commit,canonical_bytes(op['bindings']['receipt']),bundle)
            self.ledger.bind(operation,'checkpoint',decode(raw),fence)
            self._move(operation,'WITNESSED',epoch,{'checkpoint':hashed(raw)},fence)
        op=self.ledger.get(operation)
        if op['state']=='WITNESSED':
            self.host.current_authority(self.clock())
            checkpoint,_=self.witness.latest()
            if checkpoint!={'head':commit['newHead'],'receiptDigest':hashed(canonical_bytes(op['bindings']['receipt']))}:
                raise WitnessConflict('witness fork before publication')
            self._move(operation,'PUBLISHED',epoch,{'publication':commit['newHead']},fence)
        require(self.ledger.get(operation)['state']=='PUBLISHED','operation not publishable')
        return canonical_bytes(self.ledger.get(operation)['bindings']['receipt'])

    def recover(self,operation,session):
        self._caller(session,'RECOVER')
        with Fence(self.lock_path) as fence:
            self.ledger.validate()
            self.witness.verify_ledger(self.ledger.export(),require_checkpoint=True)
            epoch=self.ledger.epoch(fence);op=self.ledger.get(operation)
            require(op['state'] not in {'QUARANTINED','REJECTED','EXPIRED','PUBLISHED'},'no automatic terminal recovery')
            try:
                self._repo.audit()
            except Exception:
                self._recovery(operation,fence,epoch)
                raise
            rows=self._repo.export_records()['journal']
            matches=[r for r in rows if r[3]['plan']==op['plan'] and r[3]['approval']['proof']==op['proof']]
            if op['state']=='RECOVERY_REQUIRED':
                # Actual absent or exact commit proven by structural export, not a flag.
                require(len(matches)<=1,'ambiguous commit')
                require(op['stable']=='RESERVED' or len(matches)==1,'previously committed effect unavailable; remain in recovery')
                self._move(operation,op['stable'],epoch,{'reconciliation':hashed(canonical_bytes(rows))},fence)
                op=self.ledger.get(operation)
            if not matches:
                # Resume only the same still-valid approval; no replacement acceptance.
                decision=op['bindings'].get('migrationDecision')
                auth=self._authority(op['subject'],session,'RECOVER',op['plan'],canonical_bytes(decision) if decision else None)
                require(auth.context.caller==op['subject']['authorPrincipal'],'uncommitted execution recovery requires author')
                auth.verify(op['proof'],request(op['plan']),self.clock())
                require(self._head()==op['subject']['expectedHead'],'uncertain or changed predecessor')
                require(op['state']=='RESERVED','missing later commit')
                if op['plan']['change'] is None:
                    require(auth.context.caller==op['plan']['author'],'genesis recovery author required')
                    self._repo.bootstrap(op['plan'],op['proof'],auth,self.clock(),session,self.failpoint)
                else:
                    cid=op['plan']['change']['id']
                    p=self._repo.proposal(cid)
                    if p['state']=='REVIEW_REQUIRED':
                        row,_=self._event(cid,'REVIEW_REQUIRED')
                        require(event_ref(self.host,row)==op['subject']['proposalBinding']['reviewRequiredEvent'],'changed recovery event')
                        self._repo.approve(cid,op['proof'],auth,self.clock())
                    self._bind_approval(operation,fence)
                    if 'retry' not in op['bindings']:
                        self.witness.remember_ledger(self.ledger.export())
                        return {'status':'APPROVED_RESERVED','operationId':operation,'nextAction':'EXPLICIT_AUTHENTICATED_APPLY'}
                    self._repo.apply(cid,op['bindings']['retry'],auth,self.clock(),self.failpoint)
            try:
                receipt=self._finish(operation,fence,epoch)
            except Exception as error:
                self._recovery(operation,fence,epoch,error)
                raise
            # Recovery authority is not receipt-read authority. A caller must use
            # retrieve() with independent current grants to obtain usable bytes.
            return {'status':'PUBLISHED','operationId':operation,'receiptDigest':hashed(receipt)}

    def retrieve(self,operation,expected_subject,expected_proof,approved_event,retry,session):
        caller,_=self._caller(session,'RECEIPT_READ')
        with Fence(self.lock_path) as fence:
            op=self.ledger.get(operation)
            require(caller==op['subject']['authorPrincipal'],'receipt belongs to another author')
            require(op['state']=='PUBLISHED' and op['subject']==decode(expected_subject)
                    and op['proof']==decode(expected_proof) and op['bindings'].get('approvedEvent')==approved_event
                    and op['bindings'].get('retry')==retry,'changed retrieval binding or unpublished operation')
            from .archive import audit_locked
            audit_locked(self,fence)
            commit=self._commit(op,fence)
            raw=canonical_bytes(op['bindings']['receipt']);rd=verify_receipt(self.host,raw,commit,self.clock())
            latest,_=self.witness.latest()
            # Authenticated full audit verifies retained per-operation checkpoint below.
            require(latest is not None and latest['head']==self._head(),'stale latest checkpoint')
            require(op['bindings']['checkpoint']['body']['checkpoint']=={'head':commit['newHead'],'receiptDigest':rd},'wrong stored checkpoint')
            return raw

    def downstream(self,*args,**kwargs):
        raise Denied('data binding, migration SQL and deployment are outside history authority')

    def retire_uncommitted(self,operation,target,session):
        caller,_=self._caller(session,'RECOVER')
        require(target in {'REJECTED','EXPIRED'},'unknown retirement state')
        with Fence(self.lock_path) as fence:
            epoch=self.ledger.epoch(fence);op=self.ledger.get(operation)
            require(op['state']=='RESERVED' and caller==op['subject']['authorPrincipal'],'only author may retire an uncommitted reservation')
            self._repo.audit()
            exported=self._repo.export_records()
            require(not any(r[3]['plan']==op['plan'] or r[3]['approval']['proof']==op['proof'] for r in exported['journal']),
                    'cannot reject an actual or uncertain commit')
            require(self._head()==op['subject']['expectedHead'],'unknown native predecessor')
            if target=='EXPIRED':
                require(self.clock()>=op['proof']['body']['expiresAt'],'proof has not expired')
            self.ledger.transition(operation,target,op['version'],epoch,
                {'nativeAbsentDigest':hashed(canonical_bytes(exported))},fence)
            self.witness.remember_ledger(self.ledger.export())
