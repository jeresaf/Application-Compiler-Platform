# Route A governance correction and decision sequence

This append-only review package applies to commit
`f5793fbab115ceb3ea814a73c38434dd2335be50`. It changes no implementation,
Canonical, native HistoryRepository contract, ChangeSet semantics, approval/2,
operation ledger, sealed generator or frozen inventory. Phase 6 IN_PROGRESS;
Phase 7 NOT_STARTED. Operational implementation NOT_AUTHORIZED; operational
security NOT_ESTABLISHED. All 21 Phase 6 closure blockers remain.

## A — Correct provenance before interpreting approval

The previous assistant incorrectly labelled an independent assistant technical-review
verdict as an explicit human project-authority disposition. The immutable record at
`proposals/phase6-route-a-implementation-review/security-remediation/independent-disposition/human-review-decision.json`
is preserved byte-for-byte. Read it together with the exact-bound
[provenance clarification](../proposals/phase6-route-a-implementation-review/security-remediation/governance-correction/provenance-clarification.json).

Four different facts must remain separate:

1. The user's earlier explicit implementation-and-isolated-testing-only authorization
   is documented in the original implementation package, bound to request digest
   `sha256:44805966e05af1db2c4faa3b786361737495025b0eb9e30bfbafe35c701c2eab`.
   It is a documentary instruction, not a cryptographic authority proof.
2. The bounded laboratory checkpoint was accepted by an independent assistant
   technical-review verdict. Relaying that verdict in a user message did not independently
   grant formal project-authority acceptance or operational approval. No authenticated
   reviewer identity is inferred.
3. Formal project-authority operational approval has NOT been granted.
4. Genuine cryptographically authenticated Route A project-authority approvals have
   NOT been issued. This correction creates no signature, grant, receipt or journal entry.

The prior README, next-gate document and request also reference the misattributed
acceptance. Their hashes remain unchanged. The clarification enumerates these derivative
references; none may be used to infer a human approval. This is a provenance correction,
not a retroactive replacement, deletion or re-signing of evidence.

## B — Standalone T08 request, not execution

Review [T08's exact-bound request](../proposals/phase6-route-a-implementation-review/security-remediation/governance-correction/t08-request.json)
and [execution scope](../proposals/phase6-route-a-implementation-review/security-remediation/governance-correction/t08-review.md).
The sole proposed test is
`tooling.tests.test_canonical03_migrations.PostgreSQL03MigrationTests.test_real_postgresql_storage_presence_required_and_rollback`
from the reviewed commit. It is currently skipped in the compiler suite and has not been
run in this correction task. A17-16 remains INCOMPLETE.

The request explicitly describes actual fixture SQL and cleanup. Any permission must
name a verified disposable empty PostgreSQL 18.6 environment, bind the exact source/test
hashes and separate isolated test execution from application migration. No endpoint,
credential or permission is invented. Do not execute until a separate explicit grant
resolves the prerequisites and binds the request digest.

## C — T09 is a control-specific human review

Review [T09's request and acceptance criteria](../proposals/phase6-route-a-implementation-review/security-remediation/governance-correction/t09-request.json)
and [evidence dossier](../proposals/phase6-route-a-implementation-review/security-remediation/governance-correction/t09-review.md).
A19-01 remains PENDING_FORMAL_REVIEW_DISPOSITION. Assistant technical acceptance,
ordinary CI success, artifact existence and this request are not formal project-authority
control approval. The request binds the implementation, exact-source CI, authorization,
corrected provenance, deliverable inventory, dependency/license evidence and limitations.
T08's pending/skip status must be disclosed; no T08 result is fabricated.

An independent human must explicitly identify the reviewed scope, exact evidence hashes,
their review capacity and the control-specific decision. Any bounded deliverable
disposition must preserve A06-06, A09-08, A14-06, A17-16 and release blockers. It grants
no operational authority and issues no cryptographic approval proof.

## D — T01–T07 are independent selection decisions

The [dependency map](../proposals/phase6-route-a-implementation-review/security-remediation/governance-correction/t01-t07-dependencies.json)
separates decisions, required inputs, reviewers, dependencies and later execution gates.
No actual issuer, host, provider, custodian, reviewer, key or endpoint is selected.

| Decision | Selection scope | Dependencies before final binding |
|---|---|---|
| T01 | Repository/application ownership and environment boundary | None; actual identities and ownership evidence supplied by humans. |
| T02 | Identity provider, issuer/audience, role and registration policy | T01. |
| T03 | Algorithm policy, custody, rotation and compromise response | T01 and T02; no real key creation. |
| T04 | Version/revocation authority, clock/freshness policy, observer custody | T01, T02 and T03. |
| T05 | Topology, privileged threat boundary and enforced writer/storage isolation | T01; identity/custody integration bound after T02–T04. |
| T06 | Portable authority history, backup custody, retention and recovery objectives | T03, T04 and T05. |
| T07 | Exact infrastructure inventory, accountable operators and rollback plan | T01–T06. |

T02/T03/T04 must be reviewed together for interface compatibility, but each needs its
own explicit decision. T05 and early T06 design can proceed as paper alternatives;
their final configuration bindings wait for dependencies. Dependencies express required
inputs, not inherited grants. A selected technology or approved design never permits
provisioning, registration, real key creation, service startup, restore promotion or
operation. Those require later exact-bound execution requests and independent review.
Changing a threat boundary cannot silently promote a blocked control to PASS.

## Exact-source CI and preservation

[CI reconciliation](../proposals/phase6-route-a-implementation-review/security-remediation/governance-correction/ci-reconciliation.json)
records runs 38349532713 and 38355244432 separately. Four ordinary jobs passed in each;
the performed closure audit returned PHASE6_CLOSURE_BLOCKED, exit 2. Overall workflows
are **failure**, not GREEN. Complete closure-report bytes and blocker summaries are
retained with artifact and entry digests. Implementation run 38344618535 stays immutable.

The [unchanged control register](../proposals/phase6-route-a-implementation-review/security-remediation/governance-correction/outstanding-controls.unchanged.json)
is an exact copy, not a new assessment: A06-06 INCOMPLETE; A09-08 BLOCKED;
A14-06 INCOMPLETE; A17-16 INCOMPLETE; A19-01 PENDING_FORMAL_REVIEW_DISPOSITION.
Preservation proof and evidence hashes are in the new package manifest. Old records,
including the erroneous attribution, remain untouched and must be interpreted with
the clarification rather than treated as grants.

## Stop

No production registration, operational infrastructure, real signing keys, real
project-authority approvals, operational history, PAYMENT/CASE genesis, accepted
semantic transitions, independent binding approvals, migration SQL or application
deployment are authorized by this task or these requests. No T08 test or fixture SQL
has been executed in this task. No broader implementation has started.
STOP FOR EXPLICIT HUMAN REVIEW. Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.
