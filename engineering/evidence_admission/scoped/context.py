"""Explicit immutable laboratory inputs; never an operational trust provider."""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from engineering.evidence_admission.encoding import parse_canonical
from engineering.evidence_admission.signatures import LabKey, validate_keys
from .manifest import require, time, sha


@dataclass(frozen=True)
class LabContext:
    now: datetime
    release: bytes
    application_source: bytes
    evaluator: bytes
    subjects: bytes
    policy_ref: bytes
    checkpoint: bytes
    scope: bytes
    registration_ref: bytes
    source_inventory: bytes
    observations: tuple[bytes, ...]
    keys: tuple[LabKey, ...]
    review_grants: tuple[bytes, ...] = ()
    revoked_keys: frozenset[str] = frozenset()
    revoked_principals: frozenset[str] = frozenset()
    author_ids: frozenset[str] = frozenset()
    expected_checkpoint: bytes = b''
    checkpoint_observed_at: str = ''
    checkpoint_expires_at: str = ''
    provider_available: bool = True
    recovery_verified: bool = True
    read_authorized: bool = True
    purpose: str = 'QUALIFICATION_ONLY'
    laboratory: bool = True

    def __post_init__(self):
        require(self.laboratory is True and self.purpose == 'QUALIFICATION_ONLY', 'LABORATORY_ONLY')
        require(type(self.now) is datetime and self.now.tzinfo == timezone.utc, 'TRUSTED_UTC_REQUIRED')
        for name in ('release','application_source','evaluator','subjects','policy_ref','checkpoint','scope','registration_ref','source_inventory','expected_checkpoint'):
            raw = getattr(self, name)
            require(type(raw) is bytes, 'IMMUTABLE_CONTEXT_REQUIRED')
            parse_canonical(raw)
        for name in ('observations', 'review_grants'):
            rows = getattr(self, name)
            require(type(rows) is tuple and all(type(r) is bytes for r in rows), 'IMMUTABLE_CONTEXT_REQUIRED')
            for row in rows:
                parse_canonical(row)
        for name in ('revoked_keys', 'revoked_principals', 'author_ids'):
            require(type(getattr(self, name)) is frozenset, 'IMMUTABLE_CONTEXT_REQUIRED')
        validate_keys(self.keys)
        require(self.value('policy_ref')['schema']=='acp-laboratory-policy/1' and self.value('registration_ref')['schema']=='acp-laboratory-registration/1', 'UNSUPPORTED_TRUST_OR_REGISTRATION_PROFILE')
        release=self.value('release')
        seal='sha256:ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb'
        if release.get('kind')=='UNSEALED_CANDIDATE':
            require(release.get('profile')=='acp-spring-vue-postgres/0.6.0' and release.get('generator')=='acp-spring-vue-generator/0.6.0' and release.get('parentProfile')=='acp-spring-vue-postgres/0.5.0' and release.get('parentBundleSeal')==seal, 'UNSUPPORTED_RELEASE_CONTEXT')
        else:
            require(release.get('kind')=='SEALED_RELEASE' and release.get('profile')=='acp-spring-vue-postgres/0.5.0' and release.get('generator')=='acp-spring-vue-generator/0.5.0' and release.get('bundleSeal')==seal and release.get('releaseContractDigest')=='sha256:2f2a10ea29c4f6083352c8b49e5d2d715b0797bdd36b6cad3db762a03d7e4605', 'UNSUPPORTED_RELEASE_CONTEXT')
        self.check_current()

    def check_current(self):
        require(self.provider_available is True and self.recovery_verified is True, 'TRUST_STATE_UNAVAILABLE')
        require(self.read_authorized is True, 'READ_NOT_AUTHORIZED')
        require(self.checkpoint == self.expected_checkpoint, 'CHECKPOINT_FORK_OR_ROLLBACK')
        require(time(self.checkpoint_observed_at) <= self.now < time(self.checkpoint_expires_at), 'STALE_CHECKPOINT')
        require(self.now - time(self.checkpoint_observed_at) <= timedelta(hours=24), 'STALE_CHECKPOINT')

    def freshness(self, issued, expires):
        self.check_current()
        start, end = time(issued), time(expires)
        require(start < end and self.now < end, 'EXPIRED_EVIDENCE')
        require(start <= self.now + timedelta(minutes=5) and self.now-start <= timedelta(hours=24), 'STALE_EVIDENCE')

    def value(self, name):
        return parse_canonical(getattr(self, name))  # new copy; no mutable context aliases
