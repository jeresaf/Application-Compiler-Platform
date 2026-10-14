"""Injected immutable laboratory context, never loaded from candidate configuration.

Constructors do not authenticate the harness. The caller must supply this context
across an independent boundary; no operational root or persistence exists here.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import re

from .encoding import canonicalize, parse_canonical, payload_digest
from .validation import validate_structure
from .signatures import LabKey, require, utc, validate_keys, verify_record_signatures

REPOSITORY = 'jeresaf/Application-Compiler-Platform'
POLICY_SCHEMA = 'acp-phase6-evidence/trust-policy/1'


@dataclass(frozen=True)
class ReviewerGrant:
    principal_id: str
    purposes: frozenset[str]
    criteria: frozenset[int]
    applications: frozenset[str]
    valid_from: datetime
    valid_until: datetime

    def __post_init__(self):
        for name in ('purposes', 'criteria', 'applications'):
            object.__setattr__(self, name, frozenset(getattr(self, name)))
        require(self.valid_from.tzinfo == timezone.utc and self.valid_until.tzinfo == timezone.utc and
                self.valid_from < self.valid_until, 'INVALID_REVIEWER_GRANT_VALIDITY')
        require(self.purposes <= {'TECHNICAL', 'SECURITY'} and self.purposes, 'INVALID_REVIEWER_PURPOSE')
        require(type(self.principal_id) is str and all(type(c) is int and 1 <= c <= 39 for c in self.criteria)
                and self.applications <= {'PAYMENT', 'CASE_MANAGEMENT'}, 'INVALID_REVIEWER_SCOPE')


@dataclass(frozen=True)
class RevocationView:
    sequence: int
    observed_at: datetime
    expires_at: datetime
    revoked_keys: frozenset[str]
    revoked_principals: frozenset[str]
    revoked_records: frozenset[str]
    complete: bool

    def __post_init__(self):
        for name in ('revoked_keys', 'revoked_principals', 'revoked_records'):
            object.__setattr__(self, name, frozenset(getattr(self, name)))
            require(all(type(v) is str for v in getattr(self, name)), 'IMMUTABLE_REVOCATION_IDENTITIES_REQUIRED')
        require(type(self.sequence) is int and self.sequence >= 0 and type(self.complete) is bool, 'INVALID_REVOCATION_VIEW')
        require(type(self.observed_at) is datetime and type(self.expires_at) is datetime, 'IMMUTABLE_REVOCATION_TIME_REQUIRED')

    @property
    def digest(self):
        return payload_digest({'schema': 'acp-phase6-lab-revocation/1', 'sequence': self.sequence,
            'observedAt': self.observed_at.isoformat(), 'expiresAt': self.expires_at.isoformat(),
            'revokedKeys': sorted(self.revoked_keys), 'revokedPrincipals': sorted(self.revoked_principals),
            'revokedRecords': sorted(self.revoked_records), 'complete': self.complete})


@dataclass(frozen=True)
class WitnessContract:
    criterion: int
    witness_id: str
    path: str
    digest: str

    def __post_init__(self):
        require(type(self.criterion) is int and 1 <= self.criterion <= 39, 'INVALID_WITNESS_CRITERION')
        require(all(type(v) is str for v in (self.witness_id, self.path, self.digest)), 'IMMUTABLE_WITNESS_REQUIRED')
        require(re.fullmatch(r'sha256:[0-9a-f]{64}', self.digest) is not None, 'INVALID_WITNESS_DIGEST')


@dataclass(frozen=True)
class LabTrustContext:
    repository: str
    policy_digest: str
    policy_sequence: int
    policy_floor: int
    previous_policy_digest: str | None
    previous_policy_raw: bytes | None
    anchor_keys: tuple[LabKey, ...]
    keys: tuple[LabKey, ...]
    policy_threshold: int
    registration_threshold: int
    reviewer_grants: tuple[ReviewerGrant, ...]
    reviews: tuple[bytes, ...]
    candidate_authors: frozenset[str]
    allow_reviewer_custodian_combination: bool
    now: datetime
    revocation: RevocationView | None
    expected_revocation_digest: str
    expected_revocation_sequence: int
    registration_heads: tuple[tuple[str, str, str | None], ...]
    criteria: frozenset[int]
    applications: frozenset[str]
    executor_ids: frozenset[str]
    witness_contracts: tuple[WitnessContract, ...]
    environment_contract_digest: str
    independence_contract_digest: str
    independence_contract: bytes
    criterion_contracts: tuple[tuple[int, str], ...]
    source_commit: str
    source_inventory: bytes
    entrypoint: str
    dependency_path: str
    dependency_digest: str
    laboratory: bool = True

    def __post_init__(self):
        require(self.laboratory is True, 'LABORATORY_SCOPE_REQUIRED')
        require(self.repository == REPOSITORY, 'WRONG_REPOSITORY')
        require(type(self.now) is datetime and self.now.tzinfo == timezone.utc, 'TRUSTED_UTC_REQUIRED')
        for name in ('repository', 'policy_digest', 'expected_revocation_digest', 'environment_contract_digest',
                     'independence_contract_digest', 'source_commit', 'entrypoint', 'dependency_path', 'dependency_digest'):
            require(type(getattr(self, name)) is str, 'IMMUTABLE_CONTEXT_IDENTITY_REQUIRED')
        for name in ('anchor_keys', 'keys', 'reviewer_grants', 'reviews', 'registration_heads', 'witness_contracts', 'criterion_contracts'):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        for name in ('candidate_authors', 'criteria', 'applications', 'executor_ids'):
            object.__setattr__(self, name, frozenset(getattr(self, name)))
        require(type(self.source_inventory) is bytes, 'IMMUTABLE_SOURCE_INVENTORY_REQUIRED')
        require(type(self.independence_contract) is bytes, 'IMMUTABLE_INDEPENDENCE_CONTRACT_REQUIRED')
        require(type(self.allow_reviewer_custodian_combination) is bool, 'INVALID_ROLE_COMBINATION_POLICY')
        for number in (self.policy_sequence, self.policy_floor, self.expected_revocation_sequence):
            require(type(number) is int and number >= 0, 'INVALID_CHECKPOINT_SEQUENCE')
        require(self.previous_policy_raw is None or type(self.previous_policy_raw) is bytes, 'IMMUTABLE_POLICY_REQUIRED')
        require(all(type(r) is bytes for r in self.reviews), 'IMMUTABLE_REVIEWS_REQUIRED')
        require(all(type(r) is ReviewerGrant for r in self.reviewer_grants), 'INVALID_REVIEWER_GRANTS')
        require(all(type(w) is WitnessContract for w in self.witness_contracts), 'INVALID_WITNESS_CONTRACTS')
        require(all(type(h) is tuple and len(h) == 3 for h in self.registration_heads), 'IMMUTABLE_HEADS_REQUIRED')
        require(all(type(h[0]) is str and type(h[1]) is str and (h[2] is None or type(h[2]) is str)
                    for h in self.registration_heads), 'IMMUTABLE_HEAD_IDENTITIES_REQUIRED')
        require(all(type(c) is tuple and len(c) == 2 and type(c[0]) is int and type(c[1]) is str
                    for c in self.criterion_contracts), 'IMMUTABLE_CRITERION_CONTRACTS_REQUIRED')
        require(len({h[0] for h in self.registration_heads}) == len(self.registration_heads), 'CONFLICTING_REGISTRATION_HEADS')
        require(len({r.principal_id for r in self.reviewer_grants}) == len(self.reviewer_grants), 'DUPLICATE_REVIEWER_GRANT')
        require(all(type(p) is str for p in self.candidate_authors | self.applications | self.executor_ids), 'IMMUTABLE_SCOPE_REQUIRED')
        require(all(type(c) is int and 1 <= c <= 39 for c in self.criteria), 'INVALID_CRITERION_SCOPE')
        require(self.previous_policy_digest is None or type(self.previous_policy_digest) is str, 'IMMUTABLE_POLICY_IDENTITY_REQUIRED')
        require(len({(w.criterion, w.witness_id) for w in self.witness_contracts}) == len(self.witness_contracts), 'DUPLICATE_WITNESS_CONTRACT')
        validate_keys(self.anchor_keys)
        validate_keys(self.keys)
        require(self.anchor_keys and self.keys, 'EXTERNAL_ANCHOR_REQUIRED')
        require(type(self.policy_threshold) is int and self.policy_threshold > 0, 'INVALID_POLICY_THRESHOLD')
        require(type(self.registration_threshold) is int and self.registration_threshold > 0, 'INVALID_REGISTRATION_THRESHOLD')


def check_revocation(context):
    require(type(context) is LabTrustContext and context.laboratory is True, 'EXTERNAL_LAB_CONTEXT_REQUIRED')
    view = context.revocation
    require(type(view) is RevocationView and view.complete is True, 'MISSING_REVOCATION_CHECKPOINT')
    require(view.observed_at.tzinfo == timezone.utc and view.expires_at.tzinfo == timezone.utc, 'UTC_REVOCATION_REQUIRED')
    require(view.observed_at <= context.now < view.expires_at, 'STALE_REVOCATION_CHECKPOINT')
    require(view.sequence >= context.expected_revocation_sequence, 'REVOCATION_ROLLBACK')
    require(view.sequence == context.expected_revocation_sequence and view.digest == context.expected_revocation_digest,
            'CONFLICTING_REVOCATION_CHECKPOINT')
    return view


def verify_lab_policy(raw, context):
    """Authenticate a pinned laboratory policy, including its external predecessor."""
    view = check_revocation(context)
    require(type(raw) is bytes and validate_structure(raw).status == 'STRUCTURE_VALID_UNTRUSTED', 'INVALID_POLICY_STRUCTURE')
    record = parse_canonical(raw)
    payload = record['payload']
    require(payload['schema'] == POLICY_SCHEMA, 'UNSUPPORTED_POLICY_VERSION')
    require(record['payloadDigest'] == context.policy_digest, 'UNPINNED_POLICY')
    require(payload['repository'] == context.repository, 'WRONG_REPOSITORY')
    require(payload['sequence'] >= context.policy_floor, 'POLICY_ROLLBACK')
    require(payload['sequence'] == context.policy_sequence, 'CONFLICTING_POLICY_SEQUENCE')
    require(record['payloadDigest'] not in view.revoked_records, 'REVOKED_POLICY')
    require(utc(payload['issuedAt']) <= context.now < utc(payload['expiresAt']), 'EXPIRED_POLICY')
    require((context.now - view.observed_at).total_seconds() <= payload['freshness']['maxSnapshotAgeSeconds'],
            'STALE_REVOCATION_CHECKPOINT')
    require(payload['thresholds']['policy'] == context.policy_threshold and
            payload['thresholds']['registration'] == context.registration_threshold, 'POLICY_THRESHOLD_MISMATCH')
    require(payload['independenceContractDigest'] == context.independence_contract_digest, 'WRONG_INDEPENDENCE_POLICY')
    require(payload_digest(parse_canonical(context.independence_contract)) == context.independence_contract_digest,
            'INDEPENDENCE_CONTRACT_DIGEST_MISMATCH')
    independence = parse_canonical(context.independence_contract)
    require(type(independence) is dict and set(independence) == {'schema', 'allowReviewerCustodianCombination',
            'distinctTechnicalSecurityReviewers', 'candidateCannotReview'}, 'INVALID_INDEPENDENCE_CONTRACT')
    require(independence == {'schema': 'acp-phase6-lab-independence/1',
            'allowReviewerCustodianCombination': context.allow_reviewer_custodian_combination,
            'distinctTechnicalSecurityReviewers': True, 'candidateCannotReview': True}, 'WRONG_INDEPENDENCE_POLICY')
    require(payload['criterionContracts'] == [{'criterion': n, 'contractDigest': d} for n, d in context.criterion_contracts],
            'POLICY_CRITERION_CONTRACT_MISMATCH')
    expected = {}
    for key in context.keys:
        for role in key.roles:
            expected.setdefault((key.principal_id, role), []).append(key.key_id)
    expected_roles = [{'signerId': p, 'role': r, 'keyIds': sorted(ids)} for (p, r), ids in sorted(expected.items())]
    require(payload['signerRoles'] == expected_roles, 'POLICY_ROLE_MISMATCH')
    if context.previous_policy_digest is None:
        require(payload['sequence'] == 0 and payload['predecessorPolicyRef'] is None and
                context.previous_policy_raw is None, 'UNAUTHORIZED_POLICY_GENESIS')
    else:
        require(type(context.previous_policy_raw) is bytes and
                validate_structure(context.previous_policy_raw).status == 'STRUCTURE_VALID_UNTRUSTED', 'MISSING_POLICY_PREDECESSOR')
        previous = parse_canonical(context.previous_policy_raw)
        require(previous['payload']['schema'] == POLICY_SCHEMA and previous['payloadDigest'] == context.previous_policy_digest,
                'WRONG_POLICY_PREDECESSOR')
        require(payload['predecessorPolicyRef'] == {'schema': POLICY_SCHEMA, 'payloadDigest': context.previous_policy_digest},
                'UNAUTHORIZED_POLICY_REPLACEMENT')
        require(previous['payload']['sequence'] + 1 == payload['sequence'], 'POLICY_CONTINUITY_FAILURE')
        require(previous['payloadDigest'] not in view.revoked_records, 'REVOKED_POLICY_PREDECESSOR')
        require(previous['payload']['thresholds']['policy'] == context.policy_threshold, 'PREDECESSOR_THRESHOLD_MISMATCH')
        previous_roles = previous['payload']['signerRoles']
        for key in context.anchor_keys:
            require(any(r['signerId'] == key.principal_id and r['role'] == 'POLICY_CUSTODIAN' and
                        key.key_id in r['keyIds'] for r in previous_roles), 'UNAUTHORIZED_POLICY_REPLACEMENT')
    verify_record_signatures(raw, context.anchor_keys, 'POLICY_CUSTODIAN', context.policy_threshold,
                             context.now, view.revoked_keys, view.revoked_principals)
    return record['payloadDigest']  # authenticated only within supplied laboratory context
