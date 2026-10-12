"""Authenticated historical audit and bounded, permanently quarantined laboratory restore."""
from pathlib import Path
import sqlite3
from canonical_json import canonical_bytes, loads
from changes import request, fingerprint
from history_repository import HistoryRepository
from .security import require, decode, hashed, Context, Authority, LABEL,closed
from .storage import Fence, Ledger, NORMAL, STATES
from .evidence import verify_receipt, CHECKPOINT


class HistoricalAuthority:
    def __init__(self,host,entries,operations):
        self.host=host
        self.index=[]
        previous='EMPTY_UNINITIALIZED'
        for row in entries:
            seq,cid,jd,entry=row
            require(seq==len(self.index),'noncontiguous journal')
            matches=[o for o in operations if o['plan']==entry['plan'] and o['proof']==entry['approval']['proof']]
            require(len(matches)==1,'missing or ambiguous durable authority subject')
            op=matches[0]
            require(op['subject']['expectedHead']==previous,'proof self-declared predecessor rejected')
            require(entry['previousDigest']==(None if seq==0 else previous['journalDigest']),'changed predecessor chain')
            decision=op['bindings'].get('migrationDecision')
            context=Context(host,canonical_bytes(op['subject']),'HISTORICAL_VERIFIER',hashed(canonical_bytes(row)),'AUDIT_READ',
                            canonical_bytes(op['plan']),canonical_bytes(decision) if decision else None)
            self.index.append((fingerprint(entry['approval']['proof'],'proof'),request(entry['plan']),entry['committedAt'],context))
            previous={'sequence':seq,'digest':entry['plan']['candidate']['contentDigest'],'journalDigest':jd}

    def verify_historical(self,proof,expected,committed_at):
        matches=[c for p,r,t,c in self.index if p==fingerprint(proof,'proof') and r==expected and t==committed_at]
        require(len(matches)==1,'missing or ambiguous historical proof context')
        return Authority(matches[0],lambda:committed_at).verify_historical(proof,expected,committed_at)


def audit_locked(gateway,fence):
    gateway.ledger.validate()
    gateway.witness.verify_ledger(gateway.ledger.export(),require_checkpoint=True)
    gateway._repo.audit()
    exported=gateway._repo.export_records()
    rows=exported['journal']
    require(bool(rows),'empty repository cannot qualify as authenticated history')
    operations=[gateway.ledger.get(r[0]) for r in gateway.ledger.export()['operations']]
    require(all(o['state'] in {'PUBLISHED','REJECTED','EXPIRED'} for o in operations),'unfinished ledger operations')
    accepted=[o for o in operations if o['state']=='PUBLISHED']
    require(len(accepted)==len(rows),'missing committed operations')
    auth=HistoricalAuthority(gateway.host,rows,accepted)
    result=gateway._repo.audit(authority=auth)
    seen=set()
    for op in operations:
        proof=op['proof']['body']
        for label in ('approvalId','nonce'):
            key=(label,proof[label]);require(key not in seen,'replayed approval identity');seen.add(key)
        if op['state']!='PUBLISHED':
            require(not any(r[3]['plan']==op['plan'] or r[3]['approval']['proof']==op['proof'] for r in rows),
                    'retired operation actually committed')
            continue
        commit=gateway._commit(op,fence)
        require(op['bindings'].get('commit')==commit,'changed durable commit evidence')
        raw=canonical_bytes(op['bindings']['receipt'])
        rd=verify_receipt(gateway.host,raw,commit)
        checkpoint_raw=canonical_bytes(op['bindings']['checkpoint'])
        observed=op['bindings']['checkpoint']['body']['observedAt']
        body,_=gateway.host.signed(checkpoint_raw,CHECKPOINT,'witness',observed)
        gateway.host.identity(body)
        require(body['checkpoint']=={'head':commit['newHead'],'receiptDigest':rd},'invalid retained witness checkpoint')
        verify_receipt(gateway.host,raw,commit,observed)
    latest,_=gateway.witness.latest()
    require(latest is not None and latest['head']==gateway._head(),'truncated or stale witnessed history')
    final=next(o for o in accepted if o['bindings']['commit']['newHead']==latest['head'])
    require(latest['receiptDigest']==hashed(canonical_bytes(final['bindings']['receipt'])),'latest receipt disagreement')
    return {**result,'classification':LABEL,'authenticated':True,'head':gateway._head(),
            'configurationDigest':gateway.host.digest,'operations':len(operations)}


def audit(gateway,session):
    gateway._caller(session,'AUDIT_READ')
    with Fence(gateway.lock_path) as fence:
        return audit_locked(gateway,fence)


def export(gateway,session):
    caller,_=gateway._caller(session,'EXPORT_READ')
    with Fence(gateway.lock_path) as fence:
        verified=audit_locked(gateway,fence)
        files={'native.json':gateway._repo.export_records(),'ledger.json':gateway.ledger.export(),
               'authority-history.json':{'configuration':gateway.host.config,'registration':decode(gateway.host.registration),
                                         'registrationRoot':gateway.host.registration_root.hex()}}
        observer_digest=gateway.witness.remember_ledger(files['ledger.json'])
        manifest={'version':'acp-route-a-export/1','classification':LABEL,
            'repositoryId':gateway.host.config['repositoryId'],'applicationId':gateway.host.config['applicationId'],
            'authorityConfigurationDigest':gateway.host.digest,'head':verified['head'],
            'ledgerObserverDigest':observer_digest,
            'exporter':caller,'capturedAt':gateway.clock(),
            'files':{n:hashed(canonical_bytes(v)) for n,v in files.items()}}
        # No sessions, credentials or private signing keys are stored in these inputs.
        attestation=gateway.signer('acp-route-a-export-attestation/1',{'manifest':manifest})
        verify_export_attestation(gateway.host,attestation,manifest,gateway.clock())
        return canonical_bytes({'manifest':manifest,'files':files,'serviceAttestation':decode(attestation)})


def verify_export_attestation(host,raw,manifest,at):
    captured=manifest['capturedAt']
    require(type(captured) is int and captured<=at,'invalid export capture time')
    host.check_registration(captured)
    body,signer=host.signed(raw,'acp-route-a-export-attestation/1','receipt',captured)
    closed(body,'classification algorithm issuer audience keyId manifest')
    require(signer==host.config['serviceId'] and body['manifest']==manifest,'export service attestation changed')
    host.grant(manifest['exporter'],'EXPORT_READ',(),captured)


def restore(raw,directory,host,witness,clock,session):
    host.authenticate(session,clock(),'RECOVERY_OPERATOR')
    archive=decode(raw);require(set(archive)=={'manifest','files','serviceAttestation'},'unknown archive fields')
    m,files=archive['manifest'],archive['files']
    require(set(m)==set('version classification repositoryId applicationId authorityConfigurationDigest head ledgerObserverDigest exporter capturedAt files'.split()),'unknown manifest fields')
    require(m['version']=='acp-route-a-export/1' and m['classification']==LABEL,'wrong export format')
    host.identity(m)
    verify_export_attestation(host,canonical_bytes(archive['serviceAttestation']),m,clock())
    require(m['authorityConfigurationDigest']==host.digest,'untrusted archived configuration')
    require(set(files)=={'native.json','ledger.json','authority-history.json'} and set(m['files'])==set(files),'incomplete archive')
    require(all(hashed(canonical_bytes(v))==m['files'][n] for n,v in files.items()),'corrupted archive bytes')
    expected_trust={'configuration':host.config,'registration':decode(host.registration),'registrationRoot':host.registration_root.hex()}
    require(files['authority-history.json']==expected_trust,'missing authenticated historical trust')
    host.check_registration(clock())
    latest,_=witness.latest()
    require(latest is not None and latest['head']==m['head'],'stale backup or witness conflict')
    require(m['ledgerObserverDigest']==hashed(canonical_bytes(files['ledger.json'])),'wrong ledger observation binding')
    witness.verify_ledger(files['ledger.json'],exact=True)
    directory=Path(directory)
    directory.mkdir(mode=0o700,parents=False,exist_ok=False)
    # Marker is never removed, even after successful laboratory verification.
    (directory/'QUARANTINED_RESTORE').write_text(LABEL+'\n')
    with Fence(directory/'writer.lock') as fence:
        native=HistoryRepository(directory/'native.sqlite')
        native.restore(files['native.json'],m['head'])
        ledger=Ledger(directory/'ledger.sqlite',host)
        payload=files['ledger.json']
        require(set(payload)=={'format','operations','events','bindings','epochs'} and payload['format']=='acp-route-a-ledger/1','incomplete ledger archive')
        # Rebuild only exact archived records; no reservation, receipt or journal is issued.
        with ledger.db() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                for n in payload['epochs']:db.execute('INSERT INTO epochs VALUES (?)',(n,))
                for i,a,n,s,p,f in payload['operations']:
                    require(i==s['operationId'] and a==f['body']['approvalId'] and n==f['body']['nonce'],'archive operation identity mismatch')
                    db.execute('INSERT INTO operations VALUES (?,?,?,?,?,?)',(i,a,n,canonical_bytes(s),canonical_bytes(p),canonical_bytes(f)))
                states={}
                for o,v,e,s,t,b in payload['events']:
                    old=states.get(o)
                    require(e in payload['epochs'] and s in STATES,'unknown ledger epoch/state')
                    if old is None:require(v==0 and s=='RESERVED' and t is None,'missing reservation')
                    else:
                        ov,os,ot=old
                        require(v==ov+1,'truncated ledger events')
                        allowed=(NORMAL.get(os)==s or (os in NORMAL and s=='RECOVERY_REQUIRED' and t==os)
                                 or (os=='RECOVERY_REQUIRED' and s==ot and t is None and 'reconciliation' in b)
                                 or (os=='RESERVED' and s in {'REJECTED','EXPIRED'} and b.get('nativeAbsentDigest')))
                        require(allowed,'invalid restored state transition')
                    require(type(b) is dict and bool(b),'missing transition evidence')
                    db.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',(o,v,e,s,t,canonical_bytes(b)))
                    states[o]=(v,s,t)
                for o,k,b in payload['bindings']:db.execute('INSERT INTO bindings VALUES (?,?,?)',(o,k,canonical_bytes(b)))
                db.commit()
            except BaseException:
                db.rollback();raise
        # Keep this object private: the regular constructor rejects its quarantine marker.
        from .gateway import Gateway
        g=object.__new__(Gateway)
        g.directory,g.host,g._repo,g.ledger,g.witness,g.clock=directory,host,native,ledger,witness,clock
        result=audit_locked(g,fence)
        require(result['head']==m['head'],'restored head mismatch')
        (directory/'VERIFIED_LABORATORY_ONLY.json').write_bytes(canonical_bytes(result))
        return {'status':'VERIFIED_IN_QUARANTINE','archiveDigest':hashed(raw),'audit':result}
