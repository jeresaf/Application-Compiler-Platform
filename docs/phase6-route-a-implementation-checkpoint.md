# Route A authenticated history implementation checkpoint

Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED. Implementation and isolated testing are
authorized by the separately recorded [documentary human decision](../proposals/phase6-route-a-implementation-review/human-decision.json)
against source `a0e95496e9217fcb24a5da1f444484dccbb64ac5` and request-body digest
`sha256:44805966e05af1db2c4faa3b786361737495025b0eb9e30bfbafe35c701c2eab`.
The original request, accepted design documents and their historical hashes are unchanged.
The instruction is not a cryptographic authority proof, signature, credential or receipt.

This checkpoint adds working external code and laboratory integration tests. It does not
construct an operational service, register trust or initialize either original reference
application's accepted history. All fixture journals, keys, proofs, sessions and witness
records are NON_AUTHORITATIVE_TEST_ONLY, use APP-ROUTE-A-LAB and temporary stores, and are
discarded after tests. No application database is opened and no migration SQL is executed.
Independent architecture/security review is required before accepting this checkpoint.

## Source and interfaces

| Module | Responsibility |
| --- | --- |
| `engineering/route_a_gateway/security.py` | Immutable host/configuration and invocation contexts; canonical closed-envelope ingestion; Ed25519 verification; authenticated sessions; scoped/revocation-time grants; approval/2 exact subject and native verdict adapter. |
| `engineering/route_a_gateway/storage.py` | Append-only SQLite operation/nonce/approval ledger, schema version 1, CAS events, durable epochs, complete evidence validation and kernel-held process fence. |
| `engineering/route_a_gateway/gateway.py` | Proof-free propose/review; exact event references; independent approval; fenced native bootstrap/apply; recovery; authorized receipt retrieval; explicit downstream denial. |
| `engineering/route_a_gateway/evidence.py` | Versioned signed service receipt verification, witness submission verification, challenge-bound witness client and separately retained durable monotonic reader checkpoints. |
| `engineering/route_a_gateway/archive.py` | Independently derived historical authority contexts, full authenticated native audit, export manifest and permanently quarantined laboratory restoration. |
| `verification/route_a/lab_provider.py` | Disposable synthetic authentication/approval/service/witness keys and loopback HTTP witness with its own SQLite checkpoint/journal storage. Test-only signing lives here, outside gateway source. |
| `verification/route_a/test_gateway_integration.py` | Real native history, cryptographic, process-crash, durable storage, authorization, witness and recovery tests. Existing symbolic/replay regressions remain independent. |

The library uses the existing native modules through `PYTHONPATH=tooling:.`; it modifies
no native interface or published Canonical model. It has no operational CLI or endpoint.
Gateway constructors receive trusted host dependencies from the embedding host, never
client proof/route parameters. Host configuration must have an authentic registration
attestation verified against an independently injected root before Gateway can open its
stores. The only such attestations issued here are labelled disposable laboratory fixtures.
Wrong root/configuration/service identity and missing/expired attestations fail closed.
`Host` owns canonical immutable bytes; `Context` owns
canonical subject/plan/decision copies and authentication digests, excluding bearer tokens
and private keys. Mutable dictionaries returned by accessors are copies. Per-invocation
Authority objects expose unchanged authenticate/verify/verify_historical verdict shapes.

Current trust injection is intentionally laboratory-only. A configured algorithm is
required, and the implemented supported suite is Ed25519 via PyCA cryptography. Other
algorithms fail closed. Issuer, audience, principal/key bindings, proof/session lifetime,
effective-time revocation, service identity, witness key and host policy are explicit
configuration values. No default production issuer/root/custodian is selected. A future
operational host must independently select and authenticate its registered endpoint and
registration root before injection. No registration or enrollment service is implemented
or authorized here; the adapter implements verification, not authority issuance.
Configuration versions cannot silently replace ledger policy. Online rotation across
multiple host configurations is outside this checkpoint and fails closed.

## Approval and native event binding

The envelope remains `acp-route-a-approval/2`, with closed proofVersion/body/signature
objects. Signatures cover `version UTF-8 + NUL + exact canonical body bytes`. Transport
must already be canonical; duplicate keys, unsafe/noninteger numbers and unknown fields
are rejected. The algorithm, issuer, audience, key role and principal mapping come from
the immutable host, not a key embedded in the proof. Approval nonces use canonical
256-bit hex encoding; test issuers generate them with the standard secrets module.

Native `export_records()` rows are read under the same kernel lock as the native write.
Engineering references use the accepted `acp-route-a-proposal-event/1` domain prefix,
registered repository/application, exact row and positive serial. PROPOSE/REVIEW require
no independent approval or nonce reservation. APPROVE loads the current REVIEW_REQUIRED
row and reserves its exact signed subject before native approve. APPLY independently
checks the actual APPROVED row, its immediately preceding reviewed event and unchanged
proof. An edit or rebase cannot inherit an old approval. No future event is invented.
Genesis retains null ordinary proposal binding and its explicit operation/retry identity.

MIGRATION-scoped plans additionally require an independently signed, exact-plan declaration
decision (`acp-route-a-migration-declaration/1`) retained separately in the ledger. Its
digest must equal the approval envelope's declaration decision digest. The signed decision
binds the exact migration declaration bytes and says DECLARATION_IN_HISTORY_ONLY. The
fixture decision is synthetic, never a real project approval or SQL/data-binding grant.

## Durability, witnessing and recovery

The native journal and external ledger are separate transaction domains. SQLite FULL
synchronous mode and append-only triggers protect participating writes. The closed normal
sequence is RESERVED → JOURNAL_COMMITTED → RECEIPT_STORED → WITNESSED → PUBLISHED.
Durable event versions and writer epochs enforce CAS; exact subject/proof/binding records
cannot be replaced. Operation IDs, approval IDs and nonces remain uniquely reserved after
expiry/rejection. Full-ledger validation checks transition chronology and evidence hashes.
The separately retained reader store also checkpoints complete ledger observations before
native acceptance and at durable stage boundaries. Restart requires actual ledger state
to extend every independently retained operation/event/binding/epoch; restore requires an
exact latest ledger observation. This detects loss of a retired nonce even when journal
head and recomputed archive hashes are unchanged. Missing checkpoints fail closed. The
reader store is outside the export and must have independently governed custody; none
of these separate stores is claimed to commit atomically with another.

Process locking uses nonblocking kernel flock, retained throughout reconciliation and
native calls. Ownership checks reject changed PID, closed descriptor or replaced lock
inode. Spawned competitors cannot acquire the repository lock; process death releases it.
No expiring-lease or cross-store atomicity claim is made. Direct hostile access by the
same UID/root to SQLite files is outside the tested gateway writer boundary. Operational
construction still needs a dedicated writer UID, filesystem/process confinement and
independent enforcement; cross-host fencing/failover is unsupported.

Recovery first audits actual durable native state and matches exact plan/proof/retry.
An uncertain or missing previously committed effect remains RECOVERY_REQUIRED. A proof
is never renewed automatically. Reserved approval crashes can finish the same native
approval; if apply retry is not yet bound, recovery returns APPROVED_RESERVED and requires
explicit authenticated apply. Actual uncommitted execution retries recheck author and
current authority. Already committed entries use proof-time historical verification.
Authenticated witness conflicts quarantine the operation; no automatic quarantine exit
or semantic repair is available. Proven uncommitted reservations can be explicitly retired
by their authenticated author; their nonces are never freed.

Receipts bind repository/application/configuration, operation/action, actual journal row
digest, previous/new head, candidate/plan/proof, native approved event and retry. They have
signed issuance time and a separately configured service signing identity. The adapter
only accepts a signer injected by its host; the only signer supplied in this checkpoint
is the disposable test provider. No operational receipt issuer is provisioned.

The independent loopback witness reproduces plans, validates native event/proof linkage
and genuine reviewer signatures, verifies service receipts and enforces contiguous heads
in its own SQLite store. A service signature alone cannot authorize semantic acceptance.
Challenge-bound signed responses prevent replay; freshness checks and an external durable
reader checkpoint reject even freshly signed stale/forked head observations. A committed
but unwitnessed entry cannot become PUBLISHED or permit another native write. Outage
recovery preserves the original receipt and journal; it never appends a replacement.

## Historical audit and quarantined restoration

Native structural audit runs first. A distinct historical adapter indexes exact original
proof fingerprint/request/commit-time matches and derives each predecessor from the prior
verified native entry, never the proof's own claim. Original host/key/principal/grant
chronology and signature validity are checked at proof and commit time. Service receipts,
approved-event linkage, nonce ownership and retained witness signatures are also checked.
Current receipt reads separately authenticate a fresh session and RECEIPT_READ grant,
compare every original subject/proof/approved-event/retry field and require PUBLISHED.
They never invoke native cached apply for lookup. Delegated receipt readers are not
implemented; the default original-author-only policy fails closed for all other callers.
Recovery returns status/digest only and cannot bypass receipt-read authorization.

Export contains portable native rows/snapshots/plans/proofs, public authority policy,
operation ledger, receipts and witness responses with complete file hashes and exact
source identities/head. A signed service attestation binds the full export manifest,
exporter identity and capture time; the original exporter's grant is checked independently.
It is a service assertion, not a human approval. No sessions or private keys are exported. Restore compares hashes
and externally injected original trust, then compares an independently obtained latest
witness and durable reader checkpoint. It restores only into a newly created temporary
directory marked QUARANTINED_RESTORE, runs structural plus authenticated audit and records
VERIFIED_IN_QUARANTINE. The marker is never removed; Gateway rejects that directory.
There is no operational promotion or automatic missing-suffix fabrication.

The current archive uses the native bounded canonical JSON encoder; it is not a streaming
production backup implementation and rejects oversized archives. Tests use two synthetic
Facts and bounded histories, not arbitrary production-scale repositories. Original retained
application populations remain three resources across two synthetic tenants; no expanded
population or external application-writer coverage is claimed.

## Threat coverage and required controls

Test names below refer to `IntegrationTests` in the integration module. Parameterized
cases use actual signatures, SQLite state or process termination; no symbolic Boolean
premises substitute for these observations.

| Threat/control | Executable integration evidence |
| --- | --- |
| Full native bootstrap/change/audit/retry/export/restore | `test_native_genesis_transition_signed_receipt_audit_retry_export_restore` |
| Wrong repo/app/config/action/plan/candidate/scopes/operation/algorithm/key/policy; malformed signature; expired/future proof; duplicate/noncanonical JSON | `test_signature_and_closed_envelope_security_matrix` |
| Wrong author/reviewer, missing reviewer grant, changed endpoint/session identity | `test_authentication_and_independent_reviewer_grants` |
| Validly signed self-approval with both roles | `test_self_approval_even_with_both_grants_and_valid_signature_is_rejected` |
| Original app/production configuration refused | `test_original_application_and_nonlaboratory_configuration_rejected` |
| Authenticated immutable host configuration; no client-selected root/endpoint | `test_authenticated_host_configuration_rejects_client_substitution` |
| Immutable per-call configuration/subject | `test_immutable_host_and_context_copies` |
| Proof-free propose/review do not reserve approval | `test_propose_and_review_have_no_proof_or_approval_reservation` |
| Genesis has no fabricated proposal event | `test_genesis_has_no_proposal_binding_and_rejects_fabricated_version` |
| Duplicate genesis and same-app cross-repository replay | `test_duplicate_genesis_and_cross_repository_replay` |
| Changed review/proposal event or old approval inheritance | `test_changed_review_event_new_proposal_cannot_inherit_approval` |
| Changed actual approved event/proof | `test_changed_approved_event_and_proof_rejected` |
| Apply expiry and proof-time/live revocation | `test_expiry_between_approve_and_apply`, `test_live_revocation_and_historical_proof_time_verification_are_distinct`, `test_revoked_grants_and_keys_at_original_proof_time` |
| Exact independent migration declaration; no SQL authority | `test_independent_authenticated_migration_declaration_is_required` |
| Durable CAS/epoch/closed transitions/quarantine | `test_durable_ledger_cas_nonce_and_illegal_transitions` |
| Nonce/approval-ID replay and terminal retention | `test_replayed_nonce_and_approval_id_rejected_after_publication`, `test_retired_nonce_is_retained_and_expiry_cannot_hide_commit` |
| Stale head/read set | `test_stale_head_and_changed_read_set_fail_before_new_append` |
| Competing process and lost owner | `test_competing_process_writer_and_lost_ownership` |
| Native rollback and actual post-commit recovery | `test_crash_at_every_native_and_external_boundary_then_reconcile` (eight spawned process-death boundaries) |
| Genesis crash during snapshot/before commit/after commit | Three `test_genesis_process_crash_*` tests |
| Approval commit/reservation response loss | `test_approval_crash_before_and_after_native_approval`, `test_reservation_crash_reconciles_exact_native_review_without_new_proof` |
| Missing actual committed store | `test_missing_native_commit_after_stable_commit_remains_recovery_required` |
| Unauthorized/changed retry lookup | `test_retry_read_rejects_all_binding_changes_and_no_native_apply_shortcut` |
| Recovery grants cannot return receipt bytes | `test_recovery_grant_cannot_bypass_independent_receipt_read` |
| Witness outage/unpublished receipt; exact later recovery | `test_unpublished_receipt_never_retrieved` |
| Receipt integrity; witness fork/staleness/outage | `test_receipt_corruption_and_witness_fork_stale_outage` |
| Conflicting witness cannot be auto-recovered | `test_authenticated_witness_conflict_quarantines_unpublished_commit` |
| Conflicts arising during reconciliation also quarantine | `test_witness_conflict_during_recovery_also_quarantines` |
| Service claim without valid human proof | `test_signed_service_claim_without_authentic_human_approval_is_rejected_by_witness` |
| Durable reader rollback protection | `test_freshly_signed_stale_witness_head_cannot_rollback_reader` |
| Corrupt/truncated archive, missing trust/receipts, wrong repo | `test_restore_corruption_wrong_identity_missing_authority_receipts_truncation` |
| Stale but previously valid backup | `test_stale_backup_after_real_second_commit_is_rejected` |
| Rehashed export cannot hide wrong durable event evidence | `test_corrupted_durable_event_cannot_be_hidden_by_rehashing_export_manifest` |
| Same-head archive cannot erase retired nonce state | `test_restore_cannot_erase_retired_nonce_at_unchanged_journal_head` |
| Export metadata, exporter identity and source hashes are authenticated | `test_export_service_attestation_protects_metadata_and_exporter_identity` |
| Quarantine bypass | Full restore test asserts Gateway rejects the restored directory |
| SQL/data-binding/deployment isolation | `test_history_scopes_never_authorize_sql_or_deployment` |

## Reproduction and dependency review

On Ubuntu with `python3.14-venv` installed through the package manager:

```sh
python3.14 -m venv engineering/route_a_gateway/.venv
engineering/route_a_gateway/.venv/bin/python3.14 -m pip install -r tooling/requirements.txt
engineering/route_a_gateway/.venv/bin/python3.14 -m pip install --require-hashes -r engineering/route_a_gateway/requirements.txt
engineering/route_a_gateway/.venv/bin/python3.14 -m pip check
engineering/route_a_gateway/.venv/bin/python3.14 -m unittest discover -s verification/route_a -v
.venv/bin/python3.14 -m unittest discover -s tooling/tests -v
.venv/bin/python3.14 tooling/check_target_release.py
node tooling/check_canonical_vectors.mjs
node tooling/check_canonical_vectors.mjs test-corpus/execution-v03
node tooling/check_canonical_vectors.mjs test-corpus/deterministic-v04
```

Loopback HTTP and spawned processes must be enabled for integration tests. The compiler's
requirements and root environment are unchanged. The workflow retains Ubuntu 24.04,
CPython 3.14.7, Node.js 24.21.0 and every existing gate, and adds isolated adapter dependencies
plus a Route A test-log artifact. Exit status remains enforced through bash pipefail.

Pinned external dependencies are cryptography 50.0.2, cffi 2.1.1 and pycparser 3.11,
installed with required hashes of the exact published artifacts.
The [dependency evidence](../proposals/phase6-route-a-implementation-review/evidence/dependencies.json)
records installed/published versions, metadata hashes, artifact hashes and license expressions;
license texts are retained beside it. PyCA documents the maintained verification primitive
in its [Ed25519 documentation](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).
PyPI exact-release metadata reported no vulnerabilities for these versions at capture time.
This lookup is not a comprehensive vulnerability/supply-chain audit or operational approval.

## Validation and remaining admission boundaries

Local validation: 78 Route A tests passed in 269.373 seconds; 270 compiler tests
completed in 1195.954 seconds with one existing opt-in disposable-PostgreSQL test skipped.
Repository checks, sealed-release verification and all three independent Node vector
corpora passed. Exact logs and hashes are in the implementation review package.
Hosted results will be recorded separately against the exact pushed source commit. An earlier source run cannot validate
this implementation. A blocked closure audit remains separately reported and never makes
the overall workflow PASS. No Phase 6 closure recommendation is overridden.

Independent review must evaluate the code, exact source hashes, negative/crash evidence and
remaining limitations. This checkpoint does not claim production readiness. Missing integration
evidence must be reported as incomplete, never substituted with a symbolic oracle PASS.
Operational provider registration and selection of genuine registration roots, real signing custody,
multi-version online rotation, delegated receipt access, cross-host fencing and streaming
large-history export remain unsupported. These limitations are fail-closed boundaries,
not permission to weaken the accepted gateway contract or use test keys in a real host.
Physical power-loss/filesystem durability, hostile same-UID/root confinement and production
availability are not established by disposable process-crash tests.
The tested authority source is an authenticated immutable configuration with effective-time
key/grant chronology. A live external registry/revocation-provider integration is not yet
implemented; real provider freshness, compromise updates and administrative custody need
separate engineering integration and review. Do not interpret laboratory results as proof
of those missing operational controls or as a complete production admission PASS.

Real authority registration/construction, operational history initialization, PAYMENT/CASE
genesis, accepted semantic transitions, independent data-binding approvals, migration SQL
and deployment remain NOT AUTHORIZED. Sealed 0.4.0/0.5.0 and approved Canonical snapshots
remain unchanged. Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED. STOP FOR INDEPENDENT REVIEW.
