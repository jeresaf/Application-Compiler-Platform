"""Authenticated laboratory authority status; no trust enrollment or cached admission.

Provider and observer locations are supplied by the host, never an approval/client.
Only keys authenticated by the immutable registered Host can sign status responses.
"""
from dataclasses import dataclass
from contextlib import closing
import secrets
import sqlite3
from canonical_json import canonical_bytes
from .security import require, closed, decode, hashed, Denied, LABEL

STATUS = 'acp-route-a-authority-status/1'


@dataclass(frozen=True)
class Observation:
    raw: bytes

    @property
    def body(self):
        return decode(self.raw)['body']

    def principal(self, principal, at):
        require(not any(r['principal'] == principal and at >= r['invalidFrom']
                        for r in self.body['revokedPrincipals']), 'provider revoked principal')

    def key(self, key_id, at):
        require(key_id in self.body['historicalKeys'], 'historical signing key version unavailable')
        require(not any(r['keyId'] == key_id and at >= r['invalidFrom']
                        for r in self.body['revokedKeys']), 'provider revoked signing key')

    def grants(self, host, principal, action, scopes, at):
        revoked = {r['grantId'] for r in self.body['revokedGrants'] if at >= r['invalidFrom']}
        matches = [g for g in host.config['grants'] if g['principal'] == principal
                   and action in g['actions'] and set(scopes) <= set(g['scopes'])
                   and g['validFrom'] <= at < g['validUntil']
                   and (g['revokedAt'] is None or at < g['revokedAt'])]
        # Never silently change the exact grant-evidence set bound in approval/2.
        require(bool(matches) and all(g['id'] not in revoked for g in matches),
                'provider revoked grant evidence')
        require(all(g['id'] in self.body['historicalGrants'] for g in matches),
                'historical reviewer grant version unavailable')

    def historical(self, host, at):
        require(type(at) is int and host.digest in self.body['historicalConfigurations'],
                'historical configuration version unavailable')


@dataclass(frozen=True)
class FreshnessClient:
    provider: object
    observer_path: str

    def check(self, host, now):
        require(type(now) is int, 'trusted integer clock required')
        challenge = secrets.token_hex(32)
        try:
            raw = self.provider.status(challenge)
        except Exception as error:
            raise Denied('current authority provider unavailable; cached admission forbidden') from error
        b, signer = host.signed(raw, STATUS, 'authority-status', now)
        closed(b, 'classification algorithm issuer audience keyId repositoryId applicationId '
                  'configurationDigest policyVersion authorityRevision challenge observedAt '
                  'configurationExpiresAt historicalConfigurations historicalKeys historicalGrants '
                  'revokedPrincipals revokedKeys revokedGrants')
        host.identity(b)
        require(b['classification'] == LABEL and bool(signer) and b['challenge'] == challenge,
                'unauthenticated or replayed authority status')
        require(type(b['observedAt']) is int and 0 <= now-b['observedAt'] <= host.config['witnessMaxAge'],
                'stale signed authority observation')
        require(type(b['configurationExpiresAt']) is int, 'invalid configuration expiry')
        require(type(b['authorityRevision']) is int and b['authorityRevision'] >= 1,
                'invalid authority revision')
        require(type(b['historicalConfigurations']) is list
                and len(set(b['historicalConfigurations'])) == len(b['historicalConfigurations'])
                and all(type(x) is str for x in b['historicalConfigurations']), 'invalid historical version inventory')
        known = {'revokedPrincipals': ('principal', {g['principal'] for g in host.config['grants']}),
                 'revokedKeys': ('keyId', {k['id'] for k in host.config['keys']}),
                 'revokedGrants': ('grantId', {g['id'] for g in host.config['grants']})}
        for name, permitted in [('historicalKeys',known['revokedKeys'][1]),
                                ('historicalGrants',known['revokedGrants'][1])]:
            require(type(b[name]) is list and all(type(x) is str for x in b[name])
                    and len(set(b[name]))==len(b[name]) and set(b[name])<=permitted,
                    'unknown/duplicate historical authority version')
        for name, (identity, permitted) in known.items():
            require(type(b[name]) is list, 'invalid revocation chronology')
            seen = set()
            for r in b[name]:
                closed(r, identity+' effectiveAt invalidFrom')
                require(r[identity] in permitted and r[identity] not in seen, 'unknown/duplicate revocation identity')
                require(type(r['effectiveAt']) is int and type(r['invalidFrom']) is int
                        and 0 <= r['invalidFrom'] <= r['effectiveAt'] <= now,
                        'invalid effective/compromise chronology')
                seen.add(r[identity])
        observation = Observation(raw)
        # Challenge/time are transport freshness, not a new policy version.
        core = {k:v for k,v in b.items() if k not in {'challenge','observedAt','keyId'}}
        self._remember(host, core, raw)
        require(b['configurationDigest'] == host.digest and b['policyVersion'] == host.config['policyVersion'],
                'conflicting authority configuration')
        # Authenticated negative evidence advances the floor too. A later replay
        # of an older, longer-lived configuration must not undo observed expiry.
        require(now < b['configurationExpiresAt'], 'authority configuration expired')
        observation.key(b['keyId'], now)
        return observation

    def _remember(self, host, core, response):
        raw = canonical_bytes(core)
        with closing(sqlite3.connect(self.observer_path, timeout=5)) as db, db:
            db.execute('PRAGMA synchronous=FULL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS trust (digest TEXT PRIMARY KEY);
                CREATE TABLE IF NOT EXISTS observations (revision INTEGER PRIMARY KEY, body BLOB NOT NULL, digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS responses (digest TEXT PRIMARY KEY, raw BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS conflicts (digest TEXT PRIMARY KEY, raw BLOB NOT NULL);
                CREATE TRIGGER IF NOT EXISTS immutable_trust_update BEFORE UPDATE ON trust BEGIN SELECT RAISE(ABORT,'immutable trust'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_trust_delete BEFORE DELETE ON trust BEGIN SELECT RAISE(ABORT,'immutable trust'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_observation_update BEFORE UPDATE ON observations BEGIN SELECT RAISE(ABORT,'append-only authority'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_observation_delete BEFORE DELETE ON observations BEGIN SELECT RAISE(ABORT,'append-only authority'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_response_update BEFORE UPDATE ON responses BEGIN SELECT RAISE(ABORT,'append-only authority evidence'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_response_delete BEFORE DELETE ON responses BEGIN SELECT RAISE(ABORT,'append-only authority evidence'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_conflict_update BEFORE UPDATE ON conflicts BEGIN SELECT RAISE(ABORT,'quarantined authority'); END;
                CREATE TRIGGER IF NOT EXISTS immutable_conflict_delete BEFORE DELETE ON conflicts BEGIN SELECT RAISE(ABORT,'quarantined authority'); END;
            ''')
            db.execute('BEGIN IMMEDIATE')
            trust = db.execute('SELECT digest FROM trust').fetchall()
            require(not trust or trust == [(host.digest,)], 'authority observer belongs to another repository')
            if not trust: db.execute('INSERT INTO trust VALUES (?)', (host.digest,))
            require(not db.execute('SELECT 1 FROM conflicts LIMIT 1').fetchone(),
                    'conflicting signed authority version: observer quarantined')
            db.execute('INSERT OR IGNORE INTO responses VALUES (?,?)',(hashed(response),response))
            old = db.execute('SELECT revision,body,digest FROM observations ORDER BY revision DESC LIMIT 1').fetchone()
            if old is not None:
                require(hashed(old[1]) == old[2], 'authority observer corrupt')
                require(core['authorityRevision'] >= old[0], 'authority version rollback')
                if core['authorityRevision'] == old[0]:
                    if raw != old[1]:
                        db.execute('INSERT INTO conflicts VALUES (?,?)',(hashed(response),response))
                        db.commit()
                        raise Denied('conflicting signed authority version: observer quarantined')
                    return
                prior = decode(old[1])
                for name,identity in [('revokedPrincipals','principal'),('revokedKeys','keyId'),('revokedGrants','grantId')]:
                    new={r[identity]:r for r in core[name]}
                    require(all(r[identity] in new and new[r[identity]]['invalidFrom']<=r['invalidFrom']
                                and new[r[identity]]['effectiveAt']>=r['effectiveAt'] for r in prior[name]),
                            'revocation history erased or weakened')
            db.execute('INSERT INTO observations VALUES (?,?,?)',
                       (core['authorityRevision'], raw, hashed(raw)))
