# Stage 2B-1 laboratory contracts, challenges and reservations

Accepted baseline: `1db415af4486bb03392978d07091afd609fe9f02`.

This increment validates execution contracts, authenticates synthetic laboratory
challenges and persists their issuance/reservation. It launches no candidate or
verifier workload, collects no execution evidence, signs no attestation and
produces no successful execution/admission/release result. Existing Stage 1/2A
modules, twelve record schemas, workflow, generator and Canonical bytes remain
unchanged. Stage 2B is IN_PROGRESS; this is not Stage 2B-2 authorization.

## Exact authorized inventory

New modules:

- `engineering/evidence_admission/execution_context.py`
- `engineering/evidence_admission/challenge.py`
- `engineering/evidence_admission/execution_ledger.py`

New tests (explicit discovery, no package initializer):

- `verification/evidence_admission/stage2b/lab_fixtures.py`
- `verification/evidence_admission/stage2b/test_challenge.py`
- `verification/evidence_admission/stage2b/test_execution_ledger.py`

New documentation: this file.

Only existing-file change:
`verification/evidence_admission/test_preservation.py`. It recognizes the exact
seven additions and compares accepted methods by AST, permitting only the exact
inventory predicates. It additionally compares all other accepted-baseline
checkout files, retaining only the previously pinned local checkout forms.
No broad directory exclusion or workflow exception is introduced.

## Closed execution contract

Schema identity: `acp-phase6-lab-execution-contract/1`.

Exact digest:

```
SHA256("ACP-PHASE6-LAB-EXECUTION-CONTRACT\0" || existing JCS bytes)
```

Reuse `parse_canonical`, `canonicalize`, common Stage 1 definitions and format
checks. The contract is a companion document, not a new authenticated Stage 1
record. Digest equality establishes content identity, not authority.

Every object is closed except the explicitly defined environment name/value map.
Unknown fields, unsupported versions, noncanonical serialization and unsupported
numeric values fail. Exact top-level fields:

| Field | Meaning |
|---|---|
| schema | Exact version above |
| repository | Existing ACP repository identity |
| auditSessionId | Existing session identity format |
| registrationDigest | Exact authenticated verifier registration payload |
| policyDigest | Independently pinned trusted policy |
| binding | Existing execution/evaluation commits, source tree, bundle, approval and both Canonical digests |
| subjects | Exact application, snapshot and known package digests |
| criteria | Sorted unique criterion identities |
| cases | Sorted unique application/witness/case identities, each with its criterion |
| commands | Ordered command objects; no shell command string |
| artifacts | Sorted unique expected relative paths and exact roles/media types |
| limits | Count/byte/memory/process/CPU/time bounds |
| isolationProfileDigest | Required independently selected laboratory isolation profile |

Each command binds `commandId`, ordered `argv`, `executablePath`,
`executableDigest`, `dependencyDigest`, `workingDirectory`,
`workingDirectoryDigest` and the complete allowed `environment` map. Repeated
argv values are allowed; duplicate command identities are not. NUL values,
known shell/dispatcher entrypoints and ambiguous paths fail. This is a data
contract, not an enforcement engine: a renamed executable's behavior is not
established by its filename. Executable identities require independent review.

Each artifact binds `path`, `role`, `mediaType`, `expectedDigest`, `maxBytes`.
Unknown-at-issuance generated artifact digests may be null; PACKAGE digests may
not. Every challenged package must appear as a known PACKAGE artifact. No actual
artifact bytes are collected or verified in this increment.

`limits` binds `maxArtifacts` (1..4096), `maxTotalBytes` (1..256 MiB),
`memoryBytes`, `processes`, `cpuSeconds`, `executionTimeoutSeconds`. Individual
artifact bounds are at most 64 MiB. Positive execution limits are serialized and
pinned, not applied here. The execution timeout is independent of nonce expiry.

Case criteria must cover the declared criteria. Application cases must cover
exactly the declared applications; SHARED_HOST cases may supplement them.
Witness identities must match the applicable authenticated registration scope.
Case lists are independently pinned; registration does not independently
establish their completeness without that trust input.

## Independently injected context

`LabExecutionContext` is frozen and contains only immutable bytes/identities and
the existing immutable `LabTrustContext`. It binds contract bytes/digest,
externally selected issuer, signed registration/policy and verifier-source root.
The contract must match the external pin and trusted repository/policy. Candidate
authors cannot be selected as issuer. Source inspection and registration
verification reuse `authenticate_lab_registration`; no source validator is copied.
Application source/package identities are pinned comparisons in this increment;
no application checkout or execution is measured yet.

A hostile caller controlling the harness can construct a different context.
Python immutability does not establish external authority or process isolation.
There is no candidate-driven trust discovery, production enrollment or real
identity provider. The trusted harness must independently select pins and own
ledger storage. Synthetic keys and review inputs convey no operational authority.

## Challenge construction and authentication

`construct_challenge_payload` returns an unsigned proposed payload, using the
existing `execution-challenge/1` fields without extension. Record identity uses
the existing 32-hex format. Nonces are 32 bytes from `secrets.token_bytes`, encoded
as canonical unpadded base64url. Construction alone cannot issue or reserve.
There is no signing/private-key API in the new engineering modules; synthetic
signing occurs only in fixtures reused from Stage 2A.

`validate_challenge` authenticates content against the independent context:

1. Existing structural/schema/canonical validation.
2. Existing Stage 2A registration, source, policy and revocation authentication.
3. Exact contract policy, session, repository and registration references.
4. Exact source/bundle/approval/Canonical binding, subjects/packages and criteria.
5. Current validity, maximum reservation window and policy-supported schema.
6. Existing signature primitive with CHALLENGE_ISSUER role, key/principal
   revocation and key validity. Exactly the externally selected issuer must sign.

A correct signature under candidate or wrong-role keys is insufficient.

The result is proposed issuance metadata, not permission to run. Only the trusted
ledger's `issue` operation persists an issuance. It binds the exact challenge
payload digest, record ID, nonce, repository/session, contract digest,
registration/policy digests, validity and SHA-256 of the entire signed record.
The signed schema has no contract-digest field; the independently controlled,
immutable-by-API issuance record is the explicit external association. Possessing
only a challenge signature without that matching issuance cannot authenticate.

`authenticate_challenge` additionally requires exact matching issuance and
ISSUED state. It is logically read-only and idempotent while unused. It returns
only a digest. Reserved, failed, expired or quarantined challenges fail.
Re-authentication is not a second issuance or reservation.

## Timing and expiry

- Issuance: injected trusted UTC time, whole seconds, distinct from candidate time.
- Reservation deadline: exclusive challenge `expiresAt`, at most 900 seconds
  after issuance, also bounded by policy challenge-age, policy/registration expiry
  and the issuance revocation checkpoint expiry.
- Execution duration: separately pinned `executionTimeoutSeconds`; the fixture
  uses 3600 seconds deliberately to show it is not the reservation window.
- Attestation signing: not implemented or authorized here.
- Final execution verification: not implemented or authorized here.

No validity extension follows reservation. Authentication at or after expiry
fails. Reservation after expiry durably marks EXPIRED and then raises; repeating
with an older clock cannot restore permission. Existing reservations cannot be
reused. This increment defines no exception allowing post-expiry signing or
final execution verification. A later exception requires an independently
reviewed protocol and authorization, not an inferred reservation exemption.
No production timing policy is established.

## SQLite ledger and transaction semantics

`ExecutionLedger` is a laboratory host component, not HistoryRepository.
Initialization is explicit (`create=True`) and rejects an existing file. Reopen
requires a `LedgerCheckpoint`; missing expected storage is never recreated.

Storage prerequisites: absolute nonsymlink path, private owned parent directory,
owned regular single-link 0600 database file. Current device/inode is checked
before and after each transaction. Candidate access is not experimentally denied
by this increment because no candidate workload runs. Ownership/mode checks are
prerequisites, not proof of confinement against same-UID/root attackers.

Settings: DELETE rollback journal, synchronous FULL, foreign_keys ON,
busy_timeout 10000 ms, trusted_schema OFF. Mutations use BEGIN IMMEDIATE,
transactional compare-and-set and rollback on failure. Directory metadata is
synchronized on initial construction. SQLite manages journal/commit durability;
filesystem and storage hardware remain assumptions.

Tables:

- `metadata`: version 1 and randomly generated laboratory database identity.
- `operations`: unique challenge digest, nonce, record identity and execution
  identity; exact issuance bytes, state and result digest.
- `events`: sequential append-by-API event log with predecessor and
  domain-separated hash, including database identity and exact event body.

`result_digest` is always NULL in this increment. No public setter or verified
result path exists. Tampered non-null results fail materialization verification.

Each read/write checks SQLite integrity, metadata, contiguous event chain,
allowed lifecycle and exact agreement between replayed events and materialized
operations. Checkpoints bind database identity, sequence, head, state digest,
device and inode. A reopened database must match the externally supplied exact
checkpoint, not merely a compatible predecessor. Concurrent already-open trusted
handles can observe subsequent valid transactions. The host must retain a fresh
checkpoint for later reopen; it must not derive trust by accepting an unknown
replacement's own advertised head.

Issuance and reservation each commit their event and operation update in one
SQLite transaction. Duplicate constraints roll back the whole transaction.
No cross-store atomicity is claimed.

## Lifecycle and recovery

The complete names are defined: ISSUED, RESERVED, RUNNING, COLLECTING, SEALED,
VERIFIED, EXPIRED, FAILED, QUARANTINED, RECOVERY_REQUIRED.

Reachable transitions in Stage 2B-1 only:

```
ISSUED -> RESERVED                    authenticated atomic reservation only
ISSUED -> EXPIRED                     expired reservation attempt only
ISSUED -> FAILED / QUARANTINED / RECOVERY_REQUIRED
RESERVED -> FAILED / QUARANTINED / RECOVERY_REQUIRED
RECOVERY_REQUIRED -> FAILED / QUARANTINED
```

All other transitions fail, including RUNNING and VERIFIED. Terminal states
cannot return to ISSUED. Generic transition calls cannot reserve. An execution
identity is retained after failure and cannot be reused for another challenge.

`recover()` explicitly changes unresolved RESERVED operations to
RECOVERY_REQUIRED. Reopen alone does not resume them. Operators may then mark
FAILED or QUARANTINED; they cannot release the nonce for another attempt.

Tests terminate one real process with an uncommitted transaction: reopen at the
previous checkpoint observes SQLite rollback. Another process exits after a
committed reservation: reopen using its exact externally delivered checkpoint
retains RESERVED, recovery marks RECOVERY_REQUIRED, and replay fails.

Truncation, conflicting operations, altered/missing events, wrong checkpoints,
missing databases and inode-changing replacements fail closed. Corrupt evidence
is not rewritten as a clean ledger. Quarantine transitions apply only when the
ledger is valid enough to mutate safely; rejected corrupt files require external
host quarantine and investigation.

This is not authenticated remote witnessing or privileged anti-rollback.
A same-UID/root adversary can replace storage or forge an unkeyed chain and
compromise the checkpoint channel. Byte-identical copies cannot provide portable
restoration authorization; inode checks intentionally reject replacement.
Backup/restore, cross-host coordination and externally anchored rollback
resistance remain later independently authorized work.

## Tests and execution

Use accepted CPython 3.14.7 and the unchanged Stage 2A lock:
cryptography 50.0.2, cffi 2.1.1, pycparser 3.11, attrs 26.1.0,
jsonschema 4.26.0, jsonschema-specifications 2025.9.1, referencing 0.37.0,
rpds-py 2026.6.3, tzdata 2026.4. No new dependency or source-build fallback.
SQLite comes from the accepted Python distribution, not a separately installed
package. Actual SQLite version is reported with local validation.

```
env LD_LIBRARY_PATH=/tmp/acp-stage1-python3147/lib /tmp/acp-stage1-3147-venv/bin/python3.14 -m unittest discover -s verification/evidence_admission -v
env LD_LIBRARY_PATH=/tmp/acp-stage1-python3147/lib /tmp/acp-stage2a-3147-venv/bin/python3.14 -m unittest discover -s verification/evidence_admission/stage2a -v
env LD_LIBRARY_PATH=/tmp/acp-stage1-python3147/lib /tmp/acp-stage2a-3147-venv/bin/python3.14 -m unittest discover -s verification/evidence_admission/stage2b -v
env LD_LIBRARY_PATH=/tmp/acp-stage1-python3147/lib /tmp/acp-stage2a-3147-venv/bin/python3.14 -m unittest discover -s verification/ci -v
git diff --check
```

Stage 2B tests explicitly cover all 30 requested scenarios, including unknown
issuer, invalid/unsigned signatures, altered contract/commands/cases, wrong
registration/source/package/application/Canonical/bundle, duplicate digest/nonce/
execution, expiry/revocation/missing checkpoint/policy substitution, competing
process reservations, repeated reservation, real process interruption, reopen,
corrupt/conflicting state, forbidden transitions, failed replay, missing external
checkpoint/storage, replacement and idempotent read-only verification.
Additional tests cover closed schemas, shells/paths/environment ambiguity,
record identity uniqueness, event hashes and checkpoint state/head mismatches.
No candidate workload is executed. Existing Stage 2A fixture Git setup/inspection
is reused; test process crashes exercise only synthetic SQLite transactions.

## Local checkpoint results

CPython 3.14.7; SQLite 3.46.1; bundled OpenSSL 4.0.3 29 Sep 2026.
Unchanged dependency inventory above; `pip check` passes.

| Suite | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Stage 1 and preservation | 44 | 0 | 0 |
| Existing Stage 2A | 52 | 0 | 0 |
| Stage 2B-1 | 43 | 0 | 0 |
| Existing CI parity/aggregation | 26 | 0 | 0 |
| Total | 165 | 0 | 0 |

The Stage 1 result includes exact generator/Canonical snapshot checks and all
39 criterion/historical blocker preservation assertions. Existing 43 Stage 1
checks remain, plus the accepted-baseline Stage 2B inventory/AST/byte check.
The two competing processes produce exactly one reservation and one rejection.
Crash/reopen, invalid replacement and replay tests pass; no warnings or skips
appear in the final Stage 2B run. Logs are ephemeral local files under
`/tmp/acp-stage2b-final-*.log`, not hosted acceptance evidence.
Git whitespace checks pass. No full compiler/target/closure run was newly
performed for this local increment. No hosted validation of these uncommitted
changes is claimed. Existing workflow remains unchanged and therefore does not
yet discover Stage 2B tests.

## Recommendations for separately authorized Stage 2B-2

1. Isolation: evaluate dedicated nonprivileged user namespaces with immutable
   source mounts, no network, no host control sockets, PID/process limits,
   seccomp and independently tested key/collector denial. Pin backend/runtime
   and environment identities. Do not claim these controls are implemented here.
   Hosted runner capabilities and required provisioning need separate review.
2. Dual-role attestations: require distinct authorized EXECUTOR and COLLECTOR
   principals over identical existing signature_input bytes; verify every
   signature and reject role confusion, surplus invalid signatures and aliases.
3. Collection: supervisor-confirmed writer shutdown, directory-relative no-follow
   reads, regular single-link files, byte/size/inventory checks, collector-owned
   staging, fsync and same-filesystem rename. No candidate output execution.
4. Observations: registered runner case events over supervisor-owned channels;
   exact argv/executable/source/environment, start/end/exit/signal observations.
   JUnit remains corroborating data, never sufficient evidence alone.
5. CI: preserve Stage 1/2A commands and all gates; propose explicit Stage 2B
   discovery and fault propagation only after separate CI authorization. No
   current workflow step runs these new tests. Do not silently skip required
   confinement tests when the future backend is unavailable.

Later supervision, collection, attestations, post-expiry verification exceptions,
operational keys/providers, registration activation, independent data bindings,
accepted-history genesis, migration SQL and deployment remain excluded.
No new human approval or authenticated receipt is issued. T09 reservations,
all 39 criteria and 21 closure blockers remain unchanged.

Expected sealed generator:
`sha256:ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb`.

Stage 1 = ENGINEERING ACCEPTED

Stage 2A = ENGINEERING ACCEPTED

Stage 2B = IN_PROGRESS

Phase 6 = IN_PROGRESS

Phase 7 = NOT_STARTED

Operational security = NOT ESTABLISHED

Release closure = BLOCKED
