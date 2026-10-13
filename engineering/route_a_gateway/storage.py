"""Separate SQLite ledger, append-only observations and kernel-held single-host fence."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import sqlite3
from canonical_json import canonical_bytes, loads
from .security import Denied, require, hashed

NORMAL = {'RESERVED':'JOURNAL_COMMITTED','JOURNAL_COMMITTED':'RECEIPT_STORED',
          'RECEIPT_STORED':'WITNESSED','WITNESSED':'PUBLISHED'}
STATES = set(NORMAL) | {'PUBLISHED','REJECTED','EXPIRED','RECOVERY_REQUIRED','QUARANTINED'}


class Fence:
    """All participating writers must hold this lock for the entire native call.

    This does not exclude a hostile UID with direct database access. Operational
    filesystem/UID enforcement and cross-host fencing are deliberately unsupported.
    """
    def __init__(self, path):
        self.path = Path(path)
        self.fd = None
        self.pid = None

    def __enter__(self):
        require(self.fd is None, 'reentrant fence forbidden')
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise Denied('competing writer') from None
        self.fd, self.pid = fd, os.getpid()
        try:
            self.assert_owned()
        except BaseException:
            os.close(fd)
            self.fd = None
            raise
        return self

    def assert_owned(self):
        require(self.fd is not None and self.pid == os.getpid(), 'lost process ownership')
        try:
            a,b = os.fstat(self.fd), os.stat(self.path, follow_symlinks=False)
            require((a.st_dev,a.st_ino) == (b.st_dev,b.st_ino), 'replaced fence inode')
        except OSError as exc:
            raise Denied('lost fence') from exc

    def __exit__(self, *args):
        if self.fd is not None:
            # Closing a forked descriptor must not unlock the parent's ownership.
            if self.pid == os.getpid():
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


class Ledger:
    def __init__(self, path, host):
        self.path, self.host = str(path),host
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS host (id INTEGER PRIMARY KEY CHECK(id=1), raw BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS epochs (n INTEGER PRIMARY KEY AUTOINCREMENT);
                CREATE TABLE IF NOT EXISTS operations (
                  id TEXT PRIMARY KEY, approval TEXT UNIQUE NOT NULL, nonce TEXT UNIQUE NOT NULL,
                  subject BLOB NOT NULL, plan BLOB NOT NULL, proof BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS events (
                  operation TEXT NOT NULL REFERENCES operations(id), version INTEGER NOT NULL,
                  epoch INTEGER NOT NULL, state TEXT NOT NULL, stable TEXT, body BLOB NOT NULL,
                  PRIMARY KEY(operation,version));
                CREATE TABLE IF NOT EXISTS bindings (
                  operation TEXT NOT NULL REFERENCES operations(id), kind TEXT NOT NULL, body BLOB NOT NULL,
                  PRIMARY KEY(operation,kind));
            ''')
            for table in ('host','epochs','operations','events','bindings'):
                for action in ('UPDATE','DELETE'):
                    db.execute(f"CREATE TRIGGER IF NOT EXISTS deny_{table}_{action} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT,'append-only ledger'); END")
            row=db.execute('SELECT raw FROM host WHERE id=1').fetchone()
            if row is None:
                db.execute('INSERT INTO host VALUES (1,?)',(host.raw,))
            else:
                require(row[0] == host.raw,'ledger configuration changed')
            version=db.execute('PRAGMA user_version').fetchone()[0]
            require(version in (0,1),'unsupported ledger schema version')
            if version==0:db.execute('PRAGMA user_version=1')

    @contextmanager
    def db(self):
        db=sqlite3.connect(self.path,timeout=0,isolation_level=None)
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA synchronous=FULL')
        try:
            yield db
        finally:
            db.close()

    def epoch(self, fence):
        fence.assert_owned()
        with self.db() as db:
            return db.execute('INSERT INTO epochs DEFAULT VALUES').lastrowid

    def reserve(self, subject, plan, proof, fence, epoch):
        fence.assert_owned()
        s,p=loads(subject),proof['body']
        require(s['action'] in {'GENESIS_ACCEPT','SEMANTIC_TRANSITION_ACCEPT'},'preapproval cannot reserve')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                require(epoch==db.execute('SELECT MAX(n) FROM epochs').fetchone()[0],'stale reservation epoch')
                pending=db.execute("SELECT o.id FROM operations o JOIN events e ON o.id=e.operation WHERE e.version=(SELECT MAX(version) FROM events WHERE operation=o.id) AND e.state NOT IN ('PUBLISHED','REJECTED','EXPIRED')").fetchall()
                require(not pending,'unresolved operation fences new acceptance')
                db.execute('INSERT INTO operations VALUES (?,?,?,?,?,?)',
                    (s['operationId'],p['approvalId'],p['nonce'],subject,canonical_bytes(plan),canonical_bytes(proof)))
                db.execute('INSERT INTO events VALUES (?,0,?,?,NULL,?)',
                    (s['operationId'],epoch,'RESERVED',canonical_bytes({'proofDigest':hashed(canonical_bytes(proof))})))
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def get(self, operation):
        with self.db() as db:
            op=db.execute('SELECT subject,plan,proof FROM operations WHERE id=?',(operation,)).fetchone()
            require(op is not None,'unknown operation')
            event=db.execute('SELECT version,epoch,state,stable,body FROM events WHERE operation=? ORDER BY version DESC LIMIT 1',(operation,)).fetchone()
            require(event is not None and event[2] in STATES,'invalid ledger state')
            bindings={k:loads(b) for k,b in db.execute('SELECT kind,body FROM bindings WHERE operation=?',(operation,))}
        return {'subject':loads(op[0]),'plan':loads(op[1]),'proof':loads(op[2]),'version':event[0],
                'epoch':event[1],'state':event[2],'stable':event[3],'evidence':loads(event[4]),'bindings':bindings}

    def bind(self, operation, kind, body, fence):
        fence.assert_owned()
        raw=canonical_bytes(body)
        with self.db() as db:
            old=db.execute('SELECT body FROM bindings WHERE operation=? AND kind=?',(operation,kind)).fetchone()
            if old:
                require(old[0] == raw,'immutable binding changed')
            else:
                db.execute('INSERT INTO bindings VALUES (?,?,?)',(operation,kind,raw))

    def transition(self, operation, target, expected_version, epoch, evidence, fence):
        fence.assert_owned()
        require(type(evidence) is dict and bool(evidence),'durable evidence required')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                row=db.execute('SELECT version,state,stable FROM events WHERE operation=? ORDER BY version DESC LIMIT 1',(operation,)).fetchone()
                require(row is not None and row[0] == expected_version,'ledger CAS conflict')
                require(epoch == db.execute('SELECT MAX(n) FROM epochs').fetchone()[0],'stale writer epoch')
                version,state,stable=row
                require(state not in {'REJECTED','EXPIRED','QUARANTINED'},'terminal state')
                if target == 'RECOVERY_REQUIRED':
                    require(state in NORMAL,'illegal recovery transition')
                    stable=state
                elif state == 'RECOVERY_REQUIRED':
                    require(target == 'QUARANTINED' or (target == stable and 'reconciliation' in evidence),'unreconciled recovery')
                    if target == stable:stable=None
                elif target == 'QUARANTINED':
                    pass
                elif target in {'REJECTED','EXPIRED'}:
                    require(state == 'RESERVED' and evidence.get('nativeAbsentDigest'),'unproven terminal rejection')
                else:
                    require(NORMAL.get(state) == target,'illegal or skipped transition')
                    required={'JOURNAL_COMMITTED':'commit','RECEIPT_STORED':'receipt','WITNESSED':'checkpoint','PUBLISHED':'publication'}[target]
                    require(required in evidence,'missing stage evidence')
                db.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',
                    (operation,version+1,epoch,target,stable,canonical_bytes(evidence)))
                db.commit()
            except BaseException:
                db.rollback();raise

    def export(self):
        with self.db() as db:
            db.execute('BEGIN')
            return {'format':'acp-route-a-ledger/1','operations':[[i,a,n,loads(s),loads(p),loads(f)] for i,a,n,s,p,f in db.execute('SELECT * FROM operations ORDER BY id')],
                    'events':[[o,v,e,s,t,loads(b)] for o,v,e,s,t,b in db.execute('SELECT * FROM events ORDER BY operation,version')],
                    'bindings':[[o,k,loads(b)] for o,k,b in db.execute('SELECT * FROM bindings ORDER BY operation,kind')],
                    'epochs':[r[0] for r in db.execute('SELECT n FROM epochs ORDER BY n')]}

    def validate(self):
        """Recheck complete durable state/evidence, not merely the latest row."""
        data=self.export();epochs=data['epochs']
        require(epochs==list(range(1,len(epochs)+1)),'truncated epoch chronology')
        for oid,approval,nonce,s,plan,proof in data['operations']:
            require(oid==s['operationId'] and approval==proof['body']['approvalId'] and nonce==proof['body']['nonce'],
                    'operation identity disagreement')
            require(s['authorityConfigurationDigest']==self.host.digest and s['planDigest']==plan['planDigest'],
                    'operation configuration/plan disagreement')
            self.host.identity(s)
            require(all(proof['body'].get(k)==v for k,v in s.items()),'durable proof subject disagreement')
            bindings={k:b for o,k,b in data['bindings'] if o==oid}
            require(set(bindings)<=set('approvedEvent retry commit receipt checkpoint migrationDecision'.split()),'unknown ledger binding')
            events=[r for r in data['events'] if r[0]==oid]
            require(bool(events),'missing reservation')
            prior=None
            for o,v,e,state,stable,body in events:
                require(e in epochs and state in STATES and type(body) is dict and bool(body),'invalid durable event')
                if prior is None:
                    require(v==0 and state=='RESERVED' and stable is None
                            and body=={'proofDigest':hashed(canonical_bytes(proof))},'invalid initial reservation')
                else:
                    pv,pe,ps,pt=prior
                    require(v==pv+1 and e>=pe,'version or epoch regression')
                    allowed=(NORMAL.get(ps)==state and stable is None
                        or ps in NORMAL and state=='RECOVERY_REQUIRED' and stable==ps
                        or ps=='RECOVERY_REQUIRED' and state==pt and stable is None and 'reconciliation' in body
                        or ps=='RESERVED' and state in {'REJECTED','EXPIRED'} and stable is None and body.get('nativeAbsentDigest')
                        or ps not in {'REJECTED','EXPIRED','QUARANTINED'} and state=='QUARANTINED')
                    require(allowed,'invalid durable transition')
                    if NORMAL.get(ps)==state:
                        key={'JOURNAL_COMMITTED':'commit','RECEIPT_STORED':'receipt','WITNESSED':'checkpoint','PUBLISHED':'publication'}[state]
                        require(key in body,'missing durable stage evidence')
                        if state=='PUBLISHED':expected=bindings['commit']['newHead']
                        else:expected=hashed(canonical_bytes(bindings[key]))
                        require(body[key]==expected,'stage evidence digest disagreement')
                prior=(v,e,state,stable)
        return {'format':data['format'],'operations':len(data['operations']),'events':len(data['events'])}
