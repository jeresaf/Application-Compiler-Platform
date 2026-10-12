"""Immutable host policy and signature verification; no signing or trust enrollment."""
from dataclasses import dataclass
import base64
import hashlib
import re
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from canonical_json import canonical_bytes, loads
from changes import request, fingerprint

LABEL = 'NON_AUTHORITATIVE_TEST_ONLY'


class Denied(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Denied(reason)


def hashed(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def closed(value, keys):
    require(type(value) is dict and set(value) == set(keys.split()), 'closed object required')


def decode(raw):
    require(type(raw) is bytes, 'immutable wire bytes required')
    value = loads(raw)
    require(canonical_bytes(value) == raw, 'noncanonical transport')
    return value


@dataclass(frozen=True)
class Host:
    """Construct only from independently authenticated host configuration, never proof JSON.

    This checkpoint deliberately enables only isolated laboratory configurations.
    Immutable pinned bytes include complete key/grant/revocation chronology.
    """
    raw: bytes
    registration: bytes | None = None
    registration_root: bytes | None = None

    def __post_init__(self):
        c = decode(self.raw)
        closed(c, 'version classification repositoryId applicationId serviceId issuer audience algorithm policyVersion keys grants maxSessionAge maxProofLifetime witnessMaxAge')
        require(c['version'] == 'acp-route-a-host/1' and c['classification'] == LABEL,
                'only authorized laboratory configuration is enabled')
        require(c['applicationId'] not in {'APP-FIXTURE', 'APP-CASE-MANAGEMENT'}, 'original reference histories excluded')
        require(c['algorithm'] == 'Ed25519', 'unsupported configured algorithm')
        for k in ('repositoryId', 'applicationId', 'serviceId', 'issuer', 'audience', 'policyVersion'):
            require(type(c[k]) is str and bool(c[k].strip()), 'missing host identity')
        for key in c['keys']:
            closed(key, 'id principal purpose publicKey validFrom validUntil revokedAt')
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(key['publicKey']))
        require(len({k['id'] for k in c['keys']}) == len(c['keys']), 'duplicate key')
        for g in c['grants']:
            closed(g, 'id principal actions scopes validFrom validUntil revokedAt')
        if self.registration is not None:
            require(type(self.registration_root) is bytes and len(self.registration_root)==32,'independent registration root required')
            self.check_registration(decode(self.registration)['body']['issuedAt'])

    def check_registration(self,at):
        require(self.registration is not None and self.registration_root is not None,'authenticated host registration evidence missing')
        e=decode(self.registration)
        closed(e,'proofVersion body signature')
        require(e['proofVersion']=='acp-route-a-host-registration/1','unknown host registration')
        b=e['body']
        closed(b,'classification repositoryId applicationId serviceId configurationDigest issuedAt notBefore expiresAt')
        require(b['classification']==LABEL and b['configurationDigest']==self.digest
                and b['serviceId']==self.config['serviceId'],'wrong authenticated configuration or service endpoint')
        self.identity(b);times(b,at)
        try:
            signature=base64.b64decode(e['signature'],validate=True)
            require(base64.b64encode(signature).decode()==e['signature'],'registration signature encoding')
            Ed25519PublicKey.from_public_bytes(self.registration_root).verify(signature,
                b'acp-route-a-host-registration/1\0'+canonical_bytes(b))
        except Exception as exc:
            raise Denied('host registration authentication failed') from exc
        return hashed(self.registration)

    @property
    def config(self):
        return decode(self.raw)

    @property
    def digest(self):
        return hashed(self.raw)

    def grant(self, principal, action, scopes, at):
        require(type(at) is int, 'integer trusted clock required')
        matches = [g for g in self.config['grants'] if g['principal'] == principal
                   and action in g['actions'] and set(scopes) <= set(g['scopes'])
                   and g['validFrom'] <= at < g['validUntil']
                   and (g['revokedAt'] is None or at < g['revokedAt'])]
        require(bool(matches), 'missing or revoked exact action grant')
        return hashed(canonical_bytes(matches))

    def signed(self, raw, version, purpose, at):
        e = decode(raw)
        closed(e, 'proofVersion body signature')
        require(e['proofVersion'] == version, 'unknown envelope version')
        b = e['body']
        c = self.config
        require(b['classification'] == LABEL and b['algorithm'] == c['algorithm']
                and b['issuer'] == c['issuer'] and b['audience'] == c['audience'], 'issuer/audience/algorithm mismatch')
        keys = [k for k in c['keys'] if k['id'] == b['keyId'] and k['purpose'] == purpose]
        require(len(keys) == 1, 'unknown signing key or purpose')
        k = keys[0]
        require(type(at) is int and k['validFrom'] <= at < k['validUntil']
                and (k['revokedAt'] is None or at < k['revokedAt']), 'key validity/revocation')
        sig = base64.b64decode(e['signature'], validate=True)
        require(base64.b64encode(sig).decode() == e['signature'], 'noncanonical signature')
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(k['publicKey'])).verify(
                sig, version.encode() + b'\0' + canonical_bytes(b))
        except Exception as exc:
            raise Denied('invalid cryptographic signature') from exc
        return b, k['principal']

    def authenticate(self, session, at, action, scopes=()):
        self.check_registration(at)
        b, signer = self.signed(session, 'acp-route-a-session/1', 'authentication', at)
        closed(b, 'classification algorithm issuer audience keyId repositoryId applicationId serviceId principal issuedAt notBefore expiresAt sessionId')
        self.identity(b)
        require(b['serviceId'] == self.config['serviceId'], 'wrong authenticated service')
        times(b, at)
        require(at - b['issuedAt'] <= self.config['maxSessionAge'], 'stale authentication')
        require(bool(signer) and bool(b['sessionId']), 'missing authenticated identity')
        self.grant(b['principal'], action, scopes, at)
        return b['principal'], hashed(session)

    def identity(self, body):
        c = self.config
        require(body['repositoryId'] == c['repositoryId'] and body['applicationId'] == c['applicationId'],
                'repository/application mismatch')


def times(b, at):
    require(all(type(b[k]) is int for k in ('issuedAt', 'notBefore', 'expiresAt')), 'invalid proof times')
    require(b['issuedAt'] <= b['notBefore'] <= at < b['expiresAt'], 'proof expired or future dated')


@dataclass(frozen=True)
class Context:
    """No mutable nested objects or bearer credentials; owned canonical copies."""
    host: Host
    subject: bytes
    caller: str
    authentication_digest: str
    action: str
    plan_bytes: bytes | None = None
    migration_decision: bytes | None = None

    def __post_init__(self):
        s = decode(self.subject)
        self.host.identity(s)
        require(s['authorityConfigurationDigest'] == self.host.digest, 'configuration mismatch')
        if self.plan_bytes is not None:
            p=decode(self.plan_bytes)
            require(p['planDigest']==s['planDigest'],'context plan changed')
        if self.migration_decision is not None:decode(self.migration_decision)


SUBJECT_KEYS = ('repositoryId applicationId authorityConfigurationDigest operationId action request '
                'candidateDigest planDigest requiredScopes expectedHead authorPrincipal proposalBinding genesisRetryIdentity')
APPROVAL_KEYS = SUBJECT_KEYS + (' classification algorithm issuer audience keyId verificationPolicyVersion '
                               'reviewerPrincipal issuedAt notBefore expiresAt approvalId nonce '
                               'identityEvidenceDigest grantEvidenceDigest migrationDeclarationDecisionDigest permittedUse')


def subject(host, plan, operation, head, binding=None, genesis_retry=None):
    require(type(operation) is str and 0 < len(operation) <= 128, 'invalid operation identity')
    require(plan['candidate']['content']['applicationId'] == host.config['applicationId'], 'wrong candidate application')
    is_genesis = plan['change'] is None
    require((binding is None and type(genesis_retry) is str and bool(genesis_retry)) if is_genesis
            else (genesis_retry is None and type(binding) is dict), 'stage-specific subject')
    if not is_genesis:
        closed(binding, 'changeId reviewRequiredEvent')
        closed(binding['reviewRequiredEvent'], 'serial digest')
        require(binding['changeId'] == plan['change']['id'] and type(binding['reviewRequiredEvent']['serial']) is int
                and binding['reviewRequiredEvent']['serial'] > 0, 'invalid reviewed event')
    require(head == 'EMPTY_UNINITIALIZED' if is_genesis else head == plan['change']['base'], 'wrong trusted predecessor')
    return canonical_bytes(dict(zip(SUBJECT_KEYS.split(), [host.config['repositoryId'],host.config['applicationId'],
        host.digest,operation,'GENESIS_ACCEPT' if is_genesis else 'SEMANTIC_TRANSITION_ACCEPT',request(plan),
        plan['candidate']['contentDigest'],plan['planDigest'],plan['requiredScopes'],head,plan['author'],binding,genesis_retry])))


class Authority:
    """One invocation only; verification is pure and does not consume nonces."""
    def __init__(self, context, clock):
        self.context, self.clock = context, clock

    def authenticate(self, session):
        c = self.context
        principal, evidence = c.host.authenticate(session, self.clock(), c.action)
        require(principal == c.caller and evidence == c.authentication_digest, 'changed invocation authentication')
        return principal

    def verify(self, proof, expected, now):
        c = self.context
        c.host.check_registration(now)
        b, signer = c.host.signed(canonical_bytes(proof), 'acp-route-a-approval/2', 'approval', now)
        closed(b, APPROVAL_KEYS)
        s = decode(c.subject)
        require({k:b[k] for k in s} == s and expected == s['request'], 'changed exact approval subject')
        require(b['verificationPolicyVersion'] == c.host.config['policyVersion'], 'unknown historical policy')
        require(b['reviewerPrincipal'] == signer and signer != s['authorPrincipal'], 'independent reviewer required')
        times(b, now)
        require(b['expiresAt']-b['issuedAt'] <= c.host.config['maxProofLifetime'],'approval lifetime exceeds trusted policy')
        # Key and grant validity must hold both at signing and at use. Historical
        # audit supplies commit time, never current policy substituted retroactively.
        c.host.signed(canonical_bytes(proof),'acp-route-a-approval/2','approval',b['issuedAt'])
        identity = next(k for k in c.host.config['keys'] if k['id']==b['keyId'])
        require(b['identityEvidenceDigest']==hashed(canonical_bytes(identity)), 'untrusted proof-time identity binding')
        c.host.grant(signer,'APPROVE',s['requiredScopes'],b['issuedAt'])
        require(b['permittedUse'] == 'ACCEPTED_HISTORY_ONLY', 'downstream scope forbidden')
        for k in ('approvalId','nonce','identityEvidenceDigest'):
            require(type(b[k]) is str and bool(b[k].strip()), 'missing approval evidence')
        require(re.fullmatch('[0-9a-f]{64}',b['nonce']) is not None,'approval nonce requires 256-bit canonical encoding')
        require(b['grantEvidenceDigest'] == c.host.grant(signer, 'APPROVE', s['requiredScopes'], now), 'grant evidence mismatch')
        c.host.grant(s['authorPrincipal'], 'AUTHOR', (), now)
        if 'MIGRATION' in s['requiredScopes']:
            require(c.plan_bytes is not None and c.migration_decision is not None,'authenticated migration declaration evidence missing')
            require(b['migrationDeclarationDecisionDigest']==hashed(c.migration_decision),'changed declaration decision')
            decision,reviewer=c.host.signed(c.migration_decision,'acp-route-a-migration-declaration/1','approval',now)
            closed(decision,'classification algorithm issuer audience keyId repositoryId applicationId authorityConfigurationDigest planDigest migrationDeclarationDigest reviewerPrincipal issuedAt notBefore expiresAt permittedUse decision')
            c.host.identity(decision);times(decision,now)
            c.host.signed(c.migration_decision,'acp-route-a-migration-declaration/1','approval',decision['issuedAt'])
            c.host.grant(reviewer,'APPROVE',['MIGRATION'],decision['issuedAt'])
            require(decision['authorityConfigurationDigest']==c.host.digest and decision['planDigest']==s['planDigest']
                    and decision['migrationDeclarationDigest']==hashed(canonical_bytes(decode(c.plan_bytes)['change']['migration']))
                    and reviewer==signer and decision['reviewerPrincipal']==signer
                    and decision['permittedUse']=='DECLARATION_IN_HISTORY_ONLY' and decision['decision']=='APPROVED',
                    'invalid migration declaration decision')
        else:
            require(b['migrationDeclarationDecisionDigest'] is None and c.migration_decision is None,'unexpected migration authority')
        return {'principal':signer,'proofDigest':fingerprint(proof,'proof'),'request':expected}

    def verify_historical(self, proof, expected, committed_at):
        # The historical adapter is separately constructed from verified native rows.
        return self.verify(proof, expected, committed_at)
