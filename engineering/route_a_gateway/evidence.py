"""Signed service receipts and independently authenticated witness responses."""
import secrets
import sqlite3
from contextlib import closing
from canonical_json import canonical_bytes
from changes import fingerprint,genesis,prepare,request
from .security import closed, require, hashed, LABEL,subject,Context,Authority,decode


class WitnessConflict(ValueError):
    pass

RECEIPT = 'acp-route-a-service-receipt/1'
CHECKPOINT = 'acp-route-a-witness-response/1'


def commit_evidence(host, subject, plan, proof, row, approved_event, retry):
    seq,change_id,journal_digest,entry=row
    require(entry['plan'] == plan and entry['approval']['proof'] == proof,'commit subject mismatch')
    require(journal_digest == fingerprint(entry,'journal') and seq == entry['sequence'],'invalid actual journal evidence')
    require(entry['retryKey'] == ('GENESIS' if plan['change'] is None else retry),'wrong committed retry')
    require(change_id == ('GENESIS' if plan['change'] is None else plan['change']['id']),'wrong committed change')
    expected=subject['expectedHead']
    require(seq == (0 if expected == 'EMPTY_UNINITIALIZED' else expected['sequence']+1)
            and entry['previousDigest'] == (None if expected == 'EMPTY_UNINITIALIZED' else expected['journalDigest']), 'commit predecessor mismatch')
    return {'repositoryId':host.config['repositoryId'],'applicationId':host.config['applicationId'],
        'authorityConfigurationDigest':host.digest,'operationId':subject['operationId'],
        'action':subject['action'],'sequence':seq,'previousHead':expected,
        'newHead':{'sequence':seq,'digest':plan['candidate']['contentDigest'],'journalDigest':journal_digest},
        'planDigest':plan['planDigest'],'candidateDigest':plan['candidate']['contentDigest'],
        'proofDigest':fingerprint(proof,'proof'),'commitEvidenceDigest':hashed(canonical_bytes(row)),
        'proposalBinding':subject['proposalBinding'],'approvedEvent':approved_event,'retryIdentity':retry,
        'committedAt':entry['committedAt'],'serviceId':host.config['serviceId']}


def verify_receipt(host, raw, expected, at=None):
    preliminary=decode(raw)['body']
    issued=preliminary['issuedAt']
    require(type(issued) is int and issued>=expected['committedAt'] and (at is None or issued<=at),'invalid receipt signing time')
    host.check_registration(issued)
    b,signer=host.signed(raw,RECEIPT,'receipt',issued)
    closed(b,'classification algorithm issuer audience keyId commit issuedAt')
    host.identity(b['commit'])
    require(b['commit'] == expected and signer == host.config['serviceId'],'receipt binding mismatch')
    return hashed(raw)


class WitnessClient:
    """Provider must run under a separate trust/storage domain in deployment.

    No actual provider registration or operational endpoint is implemented here.
    Signed nonce challenges prevent cached latest-head responses qualifying as fresh.
    """
    def __init__(self, host, provider, clock, monotonic_path):
        self.host,self.provider,self.clock=host,provider,clock
        self.monotonic_path=str(monotonic_path)
        with closing(sqlite3.connect(self.monotonic_path)) as db,db:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE IF NOT EXISTS configuration (digest TEXT PRIMARY KEY)')
            rows=db.execute('SELECT digest FROM configuration').fetchall()
            require(not rows or rows==[(host.digest,)],'reader configuration changed')
            if not rows:db.execute('INSERT INTO configuration VALUES (?)',(host.digest,))
            db.execute('CREATE TABLE IF NOT EXISTS checkpoints (sequence INTEGER PRIMARY KEY, body BLOB NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS ledger_checkpoints (serial INTEGER PRIMARY KEY AUTOINCREMENT, body BLOB NOT NULL, digest TEXT NOT NULL)')
            for table in ('configuration','checkpoints','ledger_checkpoints'):
                for action in ('UPDATE','DELETE'):
                    db.execute(f"CREATE TRIGGER IF NOT EXISTS deny_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append-only reader checkpoint'); END")

    @staticmethod
    def _ledger_extends(current,previous):
        require(current['format']==previous['format']=='acp-route-a-ledger/1','wrong observed ledger version')
        require(current['epochs'][:len(previous['epochs'])]==previous['epochs'],'ledger epoch rollback')
        for table,keysize in [('operations',1),('events',2),('bindings',2)]:
            newer={tuple(row[:keysize]):canonical_bytes(row) for row in current[table]}
            require(len(newer)==len(current[table]),'duplicate observed ledger identity')
            require(all(newer.get(tuple(row[:keysize]))==canonical_bytes(row) for row in previous[table]),
                    'lost or modified independently retained ledger evidence')

    def verify_ledger(self,current,exact=False,require_checkpoint=False):
        """This trusted reader store is retained outside exported native/ledger stores.

        It must have a separately governed durable location in an operational host.
        Archive bytes cannot select or replace it. Tests use a third temporary store.
        """
        with closing(sqlite3.connect(self.monotonic_path)) as db:
            old=db.execute('SELECT body,digest FROM ledger_checkpoints ORDER BY serial DESC LIMIT 1').fetchone()
        if old is None:
            require(not (exact or require_checkpoint),'independent ledger checkpoint missing')
            return
        require(hashed(old[0])==old[1],'independent reader ledger checkpoint corrupt')
        previous=decode(old[0])
        self._ledger_extends(current,previous)
        if exact:require(canonical_bytes(current)==old[0],'stale or incomplete ledger backup')

    def remember_ledger(self,current):
        raw=canonical_bytes(current)
        with closing(sqlite3.connect(self.monotonic_path)) as db,db:
            db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT body,digest FROM ledger_checkpoints ORDER BY serial DESC LIMIT 1').fetchone()
            if old is not None:
                require(hashed(old[0])==old[1],'corrupt independent ledger checkpoint')
                self._ledger_extends(current,decode(old[0]))
                if old[0]==raw:return hashed(raw)
            db.execute('INSERT INTO ledger_checkpoints(body,digest) VALUES (?,?)',(raw,hashed(raw)))
        return hashed(raw)

    def _remember(self,checkpoint):
        with closing(sqlite3.connect(self.monotonic_path)) as db,db:
            db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT sequence,body FROM checkpoints ORDER BY sequence DESC LIMIT 1').fetchone()
            if checkpoint is None:
                if old is not None:raise WitnessConflict('latest witness rolled back to empty')
                return
            sequence=checkpoint['head']['sequence'];raw=canonical_bytes(checkpoint)
            if old is not None:
                if sequence<old[0] or sequence==old[0] and raw!=old[1]:
                    raise WitnessConflict('stale or conflicting independently retained checkpoint')
                if sequence==old[0]:return
            db.execute('INSERT INTO checkpoints VALUES (?,?)',(sequence,raw))

    def response(self, method, *args):
        self.host.check_registration(self.clock())
        challenge=secrets.token_hex(32)
        raw=getattr(self.provider,method)(challenge,*args)
        now=self.clock()
        b,signer=self.host.signed(raw,CHECKPOINT,'witness',now)
        closed(b,'classification algorithm issuer audience keyId repositoryId applicationId challenge observedAt checkpoint')
        self.host.identity(b)
        require(b['challenge']==challenge and type(b['observedAt']) is int
                and 0 <= now-b['observedAt'] <= self.host.config['witnessMaxAge'],'stale or replayed witness response')
        require(bool(signer),'unauthenticated witness')
        checkpoint=b['checkpoint']
        if checkpoint is not None:
            closed(checkpoint,'head receiptDigest')
            closed(checkpoint['head'],'sequence digest journalDigest')
            require(type(checkpoint['head']['sequence']) is int and checkpoint['head']['sequence'] >= 0,'invalid checkpoint sequence')
        self._remember(checkpoint)
        return checkpoint,raw

    def latest(self):
        return self.response('latest')

    def advance(self, commit, receipt_raw, native_bundle):
        receipt_digest=verify_receipt(self.host,receipt_raw,commit,self.clock())
        checkpoint,raw=self.response('advance',commit,receipt_raw,native_bundle)
        if checkpoint != {'head':commit['newHead'],'receiptDigest':receipt_digest}:
            raise WitnessConflict('conflicting witness checkpoint')
        return checkpoint,raw


def verify_witness_submission(host,commit,receipt_raw,bundle,previous_checkpoint,previous_entry):
    """Witness-side validation: a service signature alone cannot approve semantics."""
    closed(bundle,'row proposals migrationDecision')
    row=bundle['row'];entry=row[3];plan=entry['plan'];proof=entry['approval']['proof']
    expected='EMPTY_UNINITIALIZED' if previous_checkpoint is None else previous_checkpoint['head']
    require(commit['previousHead']==expected,'witness predecessor differs')
    if previous_entry is None:
        require(plan['change'] is None and expected=='EMPTY_UNINITIALIZED','not a valid genesis')
        regenerated=genesis(plan['sources'][0]['source'],plan['author'])
        binding=None
    else:
        require(plan['change'] is not None and plan['change']['base']==expected,'witness stale plan')
        regenerated=prepare(previous_entry['plan']['candidate'],plan['change'])
        from .gateway import event_ref
        rows=bundle['proposals']
        require(len(rows)==2 and rows[0][2]=='REVIEW_REQUIRED' and rows[1][2]=='APPROVED'
                and rows[0][1]==plan['change']['id']==rows[1][1]
                and rows[0][4]['plan']==plan==rows[1][4]['plan'] and rows[1][4]['proof']==proof,
                'witness approval event linkage missing')
        binding={'changeId':plan['change']['id'],'reviewRequiredEvent':event_ref(host,rows[0])}
        require(event_ref(host,rows[1])==commit['approvedEvent'],'witness approved event changed')
    require(regenerated==plan,'witness plan reproduction failed')
    s=subject(host,plan,commit['operationId'],expected,binding,
              commit['retryIdentity'] if plan['change'] is None else None)
    decision=bundle['migrationDecision']
    ctx=Context(host,s,'WITNESS_VERIFIER',hashed(canonical_bytes(row)),'AUDIT_READ',
                canonical_bytes(plan),canonical_bytes(decision) if decision is not None else None)
    require(Authority(ctx,lambda:entry['committedAt']).verify_historical(proof,request(plan),entry['committedAt'])
            ==entry['approval']['verdict'],'witness approval authenticity failed')
    reconstructed=commit_evidence(host,decode(s),plan,proof,row,commit['approvedEvent'],commit['retryIdentity'])
    require(reconstructed==commit,'witness actual commit evidence changed')
    return verify_receipt(host,receipt_raw,commit)
