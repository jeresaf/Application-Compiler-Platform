# Route A implementation-only authorization request

Status: **PROPOSED — NOT GRANTED**. Reviewed source:
`34e7cc0d890fc876efa7dabd8d40ba1202971e82`.
The human reviewer accepted the stage-specific gateway contract. This accepts design;
it does not authorize implementation, construction, genesis or operational execution.
Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.

The exact machine-readable [authorization request](../proposals/phase6-route-a-implementation-authorization/request.json)
and [review manifest](../proposals/phase6-route-a-implementation-authorization/manifest.json)
bind this scope, the accepted engineering contract and preserved artifacts. No proof,
signature, reviewer grant or authority registration is issued by preparing this request.

## Implementation scope proposed for later explicit authorization

Implement an external engineering adapter that uses the existing HistoryRepository
boundary and unchanged `changes.request(plan)`. The accepted
[gateway contract](phase6-route-a-gateway-contract.md) and
[authority design](phase6-route-a-authority-integration-design.md) remain binding.
In particular, preserve proposed `acp-route-a-approval/2`, signed operation identity and
exact REVIEW_REQUIRED event reference, null ordinary proposal bindings for genesis,
proof-free propose/author review, and proof-required approve/apply/durable reads.

| Work item | Proposed implementation and test scope |
| --- | --- |
| External authenticated gateway adapter | Library/adapter code and isolated test harness only; preserve native authenticate/verify/verify_historical interfaces and verdict shape. No operational service launch or provisioned endpoint. |
| Repository-specific verification context | Deep immutable per-call context from trusted configuration interfaces; exact event resolution through native exports under a writer fence; no client-selected or mutable global trust. |
| Durable operation ledger | External versioned storage schema, uniqueness/CAS and fencing/reconciliation logic, exercised only in temporary test stores. Preserve RESERVED → JOURNAL_COMMITTED → RECEIPT_STORED → WITNESSED → PUBLISHED and terminal/recovery rules. |
| Authenticated proof validation | Closed approval/2 parsing, exact signed subject/version checks, signature/key/policy verification, time/revocation/nonce rules and historical verification interfaces. Test-only vectors do not enroll a real key or grant project authority. |
| Independent reviewer enforcement | Author/reviewer separation, distinct role/action grants, current apply authorization and independent RECEIPT_READ authorization. Operators cannot grant themselves approval privileges. |
| Service receipt verification | Verification code for exact receipt bytes, signer policy, journal/plan/proof and event/head binding; reject changed, missing or unauthenticated receipt data. Any signing helper is fixture-only, never an operational receipt issuer. |
| Head witnessing | Witness protocol/client and test double, independent checkpoint verification, monotonicity/fork/staleness rejection and publication gate. No real witness identity registration or accepted-head publication. |
| Crash/reconciliation integration tests | Isolated test-provider/temporary-store harness with deterministic failpoints and restart/fencing/CAS tests across every store boundary; no claim of cross-store atomicity. |
| Export and quarantined restore tests | Complete verification-material export, manifest checks, original trust chronology, quarantine, independent latest checkpoint, nonce/receipt reconciliation and rejection of stale/tampered archives in disposable fixtures. No operational restore or promotion. |

Proposed source placement: `engineering/route_a_gateway/` for external code, isolated
pinned dependency metadata and test-provider helpers; `verification/route_a/` for tests;
Route A documentation and implementation-review evidence under the paths in request.json.
CI edits may add isolated test execution while preserving Ubuntu 24.04, CPython 3.14.7,
Node.js 24.21.0 and every existing ordinary/semantic/canonical/history/closure gate.
No root dependency or native/generator changes are included in this authorization scope.
If compatibility requires changing any sealed native/tooling/target file, stop and request
separate intentional successor-release authorization. Do not modify the 0.5.0 bundle.

## Test-only boundary

A later implementation-only grant would allow code and automated tests within a local/CI
sandbox, using clearly labelled synthetic test identities, test-only crypto material,
loopback test-provider doubles and temporary files/processes. Those values cannot be
trusted by a real host. Positive native integration fixtures, if required by the harness,
use separate artificial application/repository IDs and disposable non-authoritative test
journals. They must not initialize PAYMENT or CASE MANAGEMENT accepted-history repositories,
accept either approved application genesis/transition, or publish any test artifact as a
human-authorized receipt. They are laboratory fixtures, never new authentic history.

No production/staging/reference authority service may be provisioned or made operational
under this grant. No production credentials or real project-authority sessions are used.
Do not register actual host, issuer, principal, key, witness or trust configuration. Any
fixture signatures and test journal rows must be explicitly NON_AUTHORITATIVE_TEST_ONLY;
never recycle preview approvals or synthetic anchors as genuine accepted history.
This task itself authorizes none of those future tests: it changes only existing symbolic
regressions and prepares the request. No real keys, credentials, signatures or journals
have been created.

## Explicit exclusions

The requested grant must exclude all of the following:

- Production authority registration and operational reference authority construction.
- Real project-authority proof issuance, human signing, reviewer grants or trust enrollment.
- Accepted-history genesis for either reference application or any real authority repository.
- Accepted semantic transitions or acceptance of a migration plan into operational history.
- Independent data-binding approvals or modification of the frozen retained population.
- Migration SQL, PostgreSQL migration and application database access.
- Application deployment, operational publication, restoration or promotion of accepted history.

History MIGRATION scope remains distinct from independent bindings, executable SQL and
deployment grants. External gateway/test code must have no application PostgreSQL or
deployment credentials. Preserve the two original approved Canonical 0.3 snapshots,
historical decisions/unsigned signing requests, frozen captures and sealed 0.4.0/0.5.0.
No test success or engineering approval can waive Phase 6 closure evidence.

## Admission checks for a later implementation checkpoint

Demonstrate all existing threat/recovery cases and the corrected stage requirements with
real cryptographic verification of explicitly test-only vectors, rather than treating the
symbolic oracle's Boolean facts as integration evidence. Include wrong repository/app/
author/reviewer/key/time/scopes/head/event/proof, duplicate nonce and changed proposal;
independent retry retrieval; process/store crashes; interrupted native/ledger commits;
missing/conflicting receipts; witness fork/outage; stale backup; incomplete trust history;
quarantined restore; and attempts to acquire SQL/deployment rights from history scope.

Preserve the native event/plan/head checks and exactly bound approval subject. Reconcile
uncertain writes under an enforceable writer fence before any new append. A lease expiry
alone cannot fence a zombie native SQLite writer. No consumer may use an unwitnessed head.
Full original application admission and ordinary engineering regressions must continue
passing. Missing or unimplemented integration evidence fails closed, not skipped as PASS.

Stop after an implementation checkpoint for another human review. Even an approved
implementation-only request must not initialize an operational authority repository,
accept genesis/transitions, sign real project proofs, approve bindings or execute/deploy.

## Test separation in this finalization

`test_preapproval_ledger_construction_is_rejected` directly calls Ledger with proof-free
propose/review subjects. `test_preapproval_transition_is_rejected_independently_of_construction`
passes a malformed recovered-row SimpleNamespace to `advance` and checks rejection with
no state change. It deliberately does not call Ledger, so it reaches the reducer independently.
Positive propose/review tests remain separate. This is a symbolic test correction, not
adapter implementation, storage construction or issuance of authority.

## Hosted and local evidence

[Hosted run 38297229714](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/38297229714)
completed against exact source `34e7cc0d890fc876efa7dabd8d40ba1202971e82`.

| Job | Final conclusion |
| --- | --- |
| contracts | PASS |
| phase5-experiments | PASS |
| phase5c-hard-gates | PASS |
| phase6-target | PASS |
| phase6-closure-audit | PERFORMED; PHASE6_CLOSURE_BLOCKED; exit 2 |

The overall hosted run concludes failure because its release closure gate is intentionally
blocked. The audit reports 21 outstanding blockers; none is waived. Its
[exact blocker objects](../proposals/phase6-route-a-implementation-authorization/evidence/closure-summary.json),
[source/job observation](../proposals/phase6-route-a-implementation-authorization/evidence/hosted-observation.json),
raw hosted metadata, full closure job log and artifact/archive/report hashes are retained
in the new review package. Earlier hosted evidence and frozen captures remain unchanged.
This run validates reviewed `34e7cc0`, not these later local test/request changes.

Local `.venv/bin/python3.14 -m unittest discover -s verification/route_a -v`:
36 tests PASS (25 gateway, 11 unchanged replay), 29.562 seconds.
Retained-inventory regressions: 13 tests PASS, 0.260 seconds. Release verification confirms
unchanged sealed 0.5.0 bundle
`sha256:ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb`.
Accepted contract bytes, approved snapshots, historical decisions and frozen captures
are preserved. See the package validation record and retained local test log.

## Remaining human decisions

1. Explicitly authorize or decline the exact digest-bound implementation-only request.
   Until then implementation remains NOT AUTHORIZED.
2. Select actual provider/host, principals and grant separation, signature/key/clock/
   revocation policy, witness, storage/fencing/backup/recovery governance in a separate
   future trust decision. Implementation interfaces/test doubles may be configurable;
   no real identity or trust choice is silently selected by this request.
3. Review the resulting implementation and integration evidence before considering any
   separate construction/registration request. Genesis and each transition still need
   their own exact prospective authorization afterward.
4. Keep independent bindings, operational migration and deployment subject to separate
   exact approvals; these decisions are outside this implementation request.

No human decision is recorded as granted here. STOP FOR EXPLICIT HUMAN IMPLEMENTATION
AUTHORIZATION. Construction NOT_AUTHORIZED; genesis NOT_AUTHORIZED; data bindings
NOT_APPROVED; migration/deployment NOT_AUTHORIZED. Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.
