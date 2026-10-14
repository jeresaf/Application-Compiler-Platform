"""Single-host laboratory SQLite ledger; reservation only, never workload launch.

Custody is a host prerequisite, not something SQLite or Python objects establish.
Hash chains detect corruption; they do not defeat a privileged database rewrite.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import secrets
import re
import sqlite3
import stat

from .encoding import canonicalize, parse_canonical, payload_digest
from .execution_context import LabExecutionContext
from .registration import sha
from .signatures import LabVerificationError, require, utc

STATES = frozenset(('ISSUED', 'RESERVED', 'RUNNING', 'COLLECTING', 'SEALED', 'VERIFIED',
                    'EXPIRED', 'FAILED', 'QUARANTINED', 'RECOVERY_REQUIRED'))
# Later stages are deliberately unreachable in this increment.
TRANSITIONS = {'ISSUED': frozenset(('RESERVED', 'EXPIRED', 'FAILED', 'QUARANTINED', 'RECOVERY_REQUIRED')),
               'RESERVED': frozenset(('FAILED', 'QUARANTINED', 'RECOVERY_REQUIRED')),
               'RECOVERY_REQUIRED': frozenset(('FAILED', 'QUARANTINED'))}
ZERO = 'sha256:' + '0' * 64


@dataclass(frozen=True)
class LedgerCheckpoint:
    database_id: str
    sequence: int
    head: str
    state_digest: str
    device: int
    inode: int


class ExecutionLedger:
    def __init__(self, path, *, create=False, expected_checkpoint=None):
        require(type(create) is bool, 'EXPLICIT_CREATE_FLAG_REQUIRED')
        self.path = Path(path)
        self._db = None
        require(self.path.is_absolute() and '..' not in self.path.parts, 'ABSOLUTE_LEDGER_PATH_REQUIRED')
        require(not any(p.is_symlink() for p in (self.path, *self.path.parents)), 'SYMLINK_LEDGER_PATH')
        parent = self.path.parent.stat()
        require(parent.st_uid == os.getuid() and stat.S_IMODE(parent.st_mode) & 0o077 == 0, 'PRIVATE_LEDGER_DIRECTORY_REQUIRED')
        if create:
            require(expected_checkpoint is None, 'CANNOT_RECREATE_EXPECTED_HISTORY')
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                os.close(fd)
            except OSError as error:
                raise LabVerificationError('LEDGER_ALREADY_EXISTS_OR_UNAVAILABLE') from error
        else:
            require(type(expected_checkpoint) is LedgerCheckpoint, 'EXTERNAL_CHECKPOINT_REQUIRED')
            require(self.path.is_file(), 'EXPECTED_LEDGER_MISSING')
        info = self.path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o600, 'INVALID_LEDGER_CUSTODY')
        self._identity = (info.st_dev, info.st_ino)
        try:
            self._db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=10, isolation_level=None)
            self._db.execute('PRAGMA journal_mode=DELETE')
            self._db.execute('PRAGMA synchronous=FULL')
            self._db.execute('PRAGMA foreign_keys=ON')
            self._db.execute('PRAGMA busy_timeout=10000')
            self._db.execute('PRAGMA trusted_schema=OFF')
            if create:
                self._db.executescript('''BEGIN IMMEDIATE;
                    CREATE TABLE metadata(id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL CHECK(version=1), database_id TEXT NOT NULL);
                    CREATE TABLE operations(challenge TEXT PRIMARY KEY, nonce TEXT UNIQUE NOT NULL,
                        record_id TEXT UNIQUE NOT NULL, issuance BLOB NOT NULL, state TEXT NOT NULL,
                        execution TEXT UNIQUE, result_digest TEXT);
                    CREATE TABLE events(sequence INTEGER PRIMARY KEY, previous TEXT NOT NULL,
                        digest TEXT UNIQUE NOT NULL, body BLOB NOT NULL);
                    COMMIT;''')
                self._db.execute('INSERT INTO metadata VALUES(1,1,?)', (secrets.token_hex(32),))
                directory_fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            with self._transaction():
                self._inspect()
                if not create:
                    require(self._checkpoint() == expected_checkpoint, 'LEDGER_CHECKPOINT_MISMATCH')
        except (sqlite3.Error, OSError, ValueError, KeyError, TypeError) as error:
            self.close()
            raise LabVerificationError('LEDGER_OPEN_REJECTED:' + str(error)) from error

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    def _file_identity(self):
        require(self._db is not None, 'LEDGER_CLOSED')
        info = self.path.lstat()
        require(not self.path.is_symlink() and stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                (info.st_dev, info.st_ino) == self._identity and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o600, 'LEDGER_REPLACED_OR_EXPOSED')

    @contextmanager
    def _transaction(self):
        try:
            self._file_identity()
            self._db.execute('BEGIN IMMEDIATE')
            yield
            self._file_identity()
            self._db.execute('COMMIT')
        except (sqlite3.Error, OSError, ValueError, KeyError, TypeError) as error:
            if self._db is not None and self._db.in_transaction:
                self._db.execute('ROLLBACK')
            if isinstance(error, LabVerificationError):
                raise
            raise LabVerificationError('LEDGER_STORAGE_FAILURE') from error
        except BaseException:
            if self._db is not None and self._db.in_transaction:
                self._db.execute('ROLLBACK')
            raise

    def _inspect(self):
        require(self._db.execute('PRAGMA integrity_check').fetchall() == [('ok',)], 'CORRUPT_LEDGER')
        require(self._db.execute('SELECT id,version FROM metadata').fetchall() == [(1, 1)], 'INVALID_LEDGER_METADATA')
        database_id = self._db.execute('SELECT database_id FROM metadata').fetchone()[0]
        require(type(database_id) is str and len(database_id) == 64 and all(c in '0123456789abcdef' for c in database_id), 'INVALID_DATABASE_ID')
        rows = {}; previous = ZERO; count = 0
        for sequence, predecessor, digest, raw in self._db.execute('SELECT sequence,previous,digest,body FROM events ORDER BY sequence'):
            count += 1
            require(sequence == count and predecessor == previous, 'BROKEN_LEDGER_CONTINUITY')
            require(digest == sha(b'ACP-PHASE6-LAB-LEDGER-EVENT\0' + canonicalize(
                {'databaseId': database_id, 'sequence': sequence, 'previous': predecessor, 'body': parse_canonical(raw)})), 'CHANGED_LEDGER_EVENT')
            event = parse_canonical(raw)
            require(set(event) == {'challenge', 'from', 'to', 'execution', 'issuance'}, 'INVALID_LEDGER_EVENT')
            challenge = event['challenge']; old = rows.get(challenge)
            require(event['to'] in STATES and event['to'] not in ('RUNNING', 'COLLECTING', 'SEALED', 'VERIFIED'), 'UNSUPPORTED_LEDGER_STATE')
            if old is None:
                require(event['from'] is None and event['to'] == 'ISSUED' and event['execution'] is None,
                        'INVALID_ISSUANCE_EVENT')
                issuance = event['issuance']
                require(type(issuance) is dict and issuance['challengeDigest'] == challenge, 'INVALID_ISSUANCE_BINDING')
            else:
                require(event['issuance'] is None and event['from'] == old['state'] and
                        event['to'] in TRANSITIONS.get(old['state'], ()), 'INVALID_LEDGER_TRANSITION')
                issuance = old['issuance']
                if event['to'] == 'RESERVED':
                    require(type(event['execution']) is str and old['execution'] is None, 'INVALID_RESERVATION')
                else:
                    require(event['execution'] == old['execution'], 'CHANGED_EXECUTION_IDENTITY')
            rows[challenge] = {'issuance': issuance, 'state': event['to'], 'execution': event['execution'], 'resultDigest': None}
            previous = digest
        actual = {}
        for challenge, nonce, record_id, raw, state, execution, result in self._db.execute('SELECT * FROM operations'):
            issuance = parse_canonical(raw)
            require(nonce == issuance['nonce'] and record_id == issuance['recordId'], 'ALTERED_ISSUANCE_IDENTITY')
            actual[challenge] = {'issuance': issuance, 'state': state, 'execution': execution, 'resultDigest': result}
        require(actual == rows, 'LEDGER_MATERIALIZATION_CONFLICT')
        return database_id, count, previous, rows

    def _checkpoint(self):
        database_id, sequence, head, rows = self._inspect()
        return LedgerCheckpoint(database_id, sequence, head, sha(canonicalize(rows)), *self._identity)

    def checkpoint(self):
        with self._transaction():
            return self._checkpoint()

    def observe(self, challenge):
        with self._transaction():
            rows = self._inspect()[3]
            require(challenge in rows, 'UNKNOWN_CHALLENGE')
            return rows[challenge]

    def _append(self, event):
        database_id, sequence, previous, _ = self._inspect()
        sequence += 1
        digest = sha(b'ACP-PHASE6-LAB-LEDGER-EVENT\0' + canonicalize(
            {'databaseId': database_id, 'sequence': sequence, 'previous': previous, 'body': event}))
        self._db.execute('INSERT INTO events VALUES(?,?,?,?)', (sequence, previous, digest, canonicalize(event)))

    def issue(self, raw, context):
        from .challenge import validate_challenge
        issuance = validate_challenge(raw, context)
        digest = issuance['challengeDigest']
        with self._transaction():
            self._append({'challenge': digest, 'from': None, 'to': 'ISSUED', 'execution': None, 'issuance': issuance})
            self._db.execute('INSERT INTO operations VALUES(?,?,?,?,?,NULL,NULL)',
                             (digest, issuance['nonce'], issuance['recordId'], canonicalize(issuance), 'ISSUED'))
            self._inspect()
        return digest

    def _transition(self, challenge, expected, target, execution=None):
        require(target in TRANSITIONS.get(expected, ()), 'UNAUTHORIZED_STATE_TRANSITION')
        self._append({'challenge': challenge, 'from': expected, 'to': target, 'execution': execution, 'issuance': None})
        cursor = self._db.execute('UPDATE operations SET state=?,execution=? WHERE challenge=? AND state=?',
                                  (target, execution, challenge, expected))
        require(cursor.rowcount == 1, 'STATE_COMPARE_AND_SET_FAILED')
        self._inspect()

    def reserve(self, raw, context, execution_id):
        from .challenge import validate_challenge
        require(type(context) is LabExecutionContext, 'EXTERNAL_EXECUTION_CONTEXT_REQUIRED')
        # Authentication precedes mutation. Expired valid issuance is separately burned below.
        require(type(execution_id) is str and re.fullmatch(r'[0-9a-f]{32}', execution_id), 'INVALID_EXECUTION_ID')
        payload = parse_canonical(raw)['payload']
        digest = payload_digest(payload)
        with self._transaction():
            rows = self._inspect()[3]
            require(digest in rows and rows[digest]['state'] == 'ISSUED', 'CHALLENGE_ALREADY_CONSUMED_OR_UNKNOWN')
            row = rows[digest]
            require(row['issuance']['signedRecordDigest'] == sha(raw) and
                    row['issuance']['contractDigest'] == context.expected_contract_digest, 'CHANGED_RESERVATION_SUBJECT')
            expired = context.trust.now >= utc(row['issuance']['expiresAt'])
            if expired:
                self._transition(digest, 'ISSUED', 'EXPIRED')
            else:
                issuance = validate_challenge(raw, context)
                require(issuance == row['issuance'], 'CHANGED_ISSUANCE')
                self._transition(digest, 'ISSUED', 'RESERVED', execution_id)
        require(not expired, 'EXPIRED_CHALLENGE')
        return digest  # reservation identity only; no running capability

    def transition(self, challenge, expected, target):
        # Generic caller cannot reserve or advance into execution/result states.
        require(target in ('FAILED', 'QUARANTINED', 'RECOVERY_REQUIRED'), 'UNAUTHORIZED_STATE_TRANSITION')
        with self._transaction():
            rows = self._inspect()[3]
            require(challenge in rows and rows[challenge]['state'] == expected, 'STATE_COMPARE_AND_SET_FAILED')
            self._transition(challenge, expected, target, rows[challenge]['execution'])

    def recover(self):
        """Explicit restart reconciliation: unresolved reservations are never resumed."""
        with self._transaction():
            rows = self._inspect()[3]
            for digest, row in rows.items():
                if row['state'] == 'RESERVED':
                    self._transition(digest, 'RESERVED', 'RECOVERY_REQUIRED', row['execution'])
        return self.checkpoint()
