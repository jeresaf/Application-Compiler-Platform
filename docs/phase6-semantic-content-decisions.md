# Phase 6 semantic-content decisions and remaining authorization

Reviewed source: `f0c2e37640d8b87f7cf9ebc6fe73f236f298a583`, branch
`codex/phase6-production-remediation`. Date: 2026-10-12.

The explicit user-provided project-authority decision approves PAYMENT and CASE MANAGEMENT
independently, for exact synthetic reference semantic content only. No reviewer identity,
signature, key, session or accepted journal receipt is invented.

| State | PAYMENT | CASE MANAGEMENT |
| --- | --- | --- |
| Semantic decision recorded | APPROVED_CONTENT | APPROVED_CONTENT |
| Authenticated approval proof | PENDING_HUMAN_SIGNING | PENDING_HUMAN_SIGNING |
| Independent retained-data binding | REVIEW_REQUIRED | REVIEW_REQUIRED |
| Real journal rebase | PENDING_AUTHENTIC_HISTORY | PENDING_AUTHENTIC_HISTORY |
| Accepted executable plan | NOT_APPROVED | NOT_APPROVED |
| Migration / deployment | NOT_AUTHORIZED | NOT_AUTHORIZED |

Phase 6 remains IN_PROGRESS; Phase 7 remains NOT_STARTED.

## Immutable documentary records

[PAYMENT decision](../targets/spring-vue-postgres/evidence/semantic-content-decisions/2026-10-12/payment.json)
and [CASE MANAGEMENT decision](../targets/spring-vue-postgres/evidence/semantic-content-decisions/2026-10-12/case-management.json)
record the human statement, date, reviewed source, distinct application identity, approved
candidate and ChangeSet file digests, predecessor snapshot, new Requirement and four
AcceptanceCriteria, scope/exclusions and unchanged AI proposal provenance.
The [record manifest](../targets/spring-vue-postgres/evidence/semantic-content-decisions/2026-10-12/manifest.json)
contains exact SHA-256 file digests. The recorder creates files exclusively and refuses to
replace existing differing bytes. Corrections/revocations must be separate superseding
records, not edits to these records. Git review and digest pins provide documentary integrity,
not cryptographic human authentication.

The approved content includes required String semantics, preservation of existing updates,
explicit new-record values, BREAKING final-schema compatibility and REVIEW_REQUIRED staged
rollout intent. It does **not** approve retained-data values, production tenants, real rebase,
preview plan, migration/security execution, SQL, schema deployment or closure.

The preview plans require SEMANTIC, SECURITY and MIGRATION scopes. A content decision is
not a full-plan proof. Existing `ReferenceAuthority` verifies whole requests, not this
restricted content-decision type. Its historical reference key must not be used to invent
new authority, sessions or signatures. No proof is issued and no Canonical admission port
or migration authority is changed by this recording.

Exact unsigned signing requests are provided separately for
[PAYMENT](../targets/spring-vue-postgres/evidence/semantic-content-decisions/2026-10-12/payment-signing-request.json)
and [CASE MANAGEMENT](../targets/spring-vue-postgres/evidence/semantic-content-decisions/2026-10-12/case-management-signing-request.json).
Each includes domain-separated exact message hex, SHA-256 and a payload binding the record,
application, source, candidate, ChangeSet and exclusions. Human signing identity, trusted
key/verification channel and signature remain pending. Such a future attestation would
still attest content only; integrating an authenticated content-decision adapter requires
separate review and cannot silently grant full-plan execution scopes.

The original review packages, their empty full-plan approval arrays and historical
unapproved planning labels remain as reviewed evidence. The new decision records supply
current semantic-content status without rewriting those historical package bytes.
Original approved Canonical 0.3 snapshots and all historical approvals remain unchanged.

## Independent binding review

The [PAYMENT package](../proposals/phase6-independent-data-binding-review/payment.md)
and [CASE MANAGEMENT package](../proposals/phase6-independent-data-binding-review/case-management.md)
remain REVIEW_REQUIRED. Their common proposed scalar has exact UTF-8 hex
`65cc8100f09fa68b27` and binding digest
`sha256:2a584b4d5ca471d1f1686db24e3b094e1a91f7e69e4d9f4775fcad1607c49481`.
Equal binding digests do not authorize another application, plan or retained population.
Each decision must bind its application, real rebased plan, exact frozen row/tenant inventory,
database/schema identity, value and bytes. Missing inventories block execution; no row counts,
production applicability or database identity is invented here.

The packages distinguish absent/SQL-null/empty/nonempty values, decomposed Unicode and NUL,
all-selected-rows same-value intent, byte/error checks, writer fencing, transactional rollback,
ambiguous commits, separately committed stages and backup/restore or forward repair.
The sentinel is a reference-only retained-row transformation, never a new-record default.

## Information required for genuine accepted history

Obtain independently for APP-FIXTURE and APP-CASE-MANAGEMENT:

1. The authoritative repository/deployment identity and trusted read-only access or a
   provenance-authenticated export. A local temporary SQLite fixture is not deployment
   history. Do not initialize a new repository and label its genesis an existing head.
2. Exact head `{sequence, digest, journalDigest}`, head observation time and fencing/version
   token; exact accepted Canonical snapshot bytes and application/schema identity.
3. Complete append-only journal chain from a trusted anchor, predecessor digests, accepted
   plans, original approval requests/proofs/verdicts, committed times, source receipts and
   accepted-state indexes needed for a reproducible audit. Verify the chain and historical
   proofs through trusted authority; imported JSON claims alone are insufficient.
4. Trusted human/host authority configuration and scope/revocation policy for new requests.
   Supply authenticated author/reviewer channels separately; no names, keys or sessions are
   assumed by this plan. Also provide current proposal/lifecycle state if repository rebase
   is requested, exact old/current node revisions and tombstones.
5. Actual deployed old target seal, generation/artifact manifests, database/schema identity,
   exact retained-data inventory, tenant population and runtime/ownership/provenance evidence.
   These bind migration feasibility; journal acceptance alone does not prove deployment.
6. Independent data-binding decision for the real application/plan/population, then exact
   SQL and deployment/recovery approvals. None are supplied by these semantic records.

## Rebase procedure once real history is supplied

The currently stored base sequence 0 and zero journal digest are synthetic preview anchors;
they remain unaccepted. For each domain, authenticate the supplied journal provenance,
verify the real chain and head snapshot, and compare to the exact predecessor approved here.
Detect stale reads, revision conflicts, occupied IDs or an already-applied field before
changing anything. A real history at another semantic checkpoint requires an explicit
reviewed path; do not invent a predecessor or silently replay a different transition.

Preserve the approved ChangeSet file and its digest as immutable content evidence. Create
a **new proposed ChangeSet** with a fresh ID, actual base head and parent linkage to the
preview plan; retain the exact approved operation semantics and AI origins. Recompute
revision closure, candidate, read/write sets, required scopes and plan digest using the
existing planner against the real head snapshot. Audit any differences explicitly.
The existing `HistoryRepository.rebase` detects conflicts and creates an isolated proposal
through authenticated author ports; it does not apply that proposal. It must not be invoked
against a fabricated repository to manufacture a receipt.

A changed source/ChangeSet/candidate identity cannot inherit this exact documentary binding.
Keep this decision as historical content approval and obtain fresh review of the exact
rebased artifacts. In particular, **every changed rebase plan digest requires independent
human review**, including SECURITY/MIGRATION scopes and separately approved bindings.
Recheck head and fencing before any future acceptance. No automatic accepted journal append,
SQL generation approval or execution follows from a successful re-prepare.

## Verification and hosted evidence

`tooling/audit/semantic_content_decisions.py` verifies documentary records against the
explicit decision pins and source, and is not an injected compiler authority. Regression
coverage rejects cross-application use, candidate/requiredness/classification/operation
edits, changed ChangeSet/compatibility/anchor/source and record replacement. Documentary
records fail the existing full-plan proof verifier. Denial ports reject independent
bindings and keep preview migration lowering blocked with UNACCEPTED_HISTORY.

Keep operation-order regression, historical execution-v03/deterministic-v04 tests,
Canonical byte/hash checks, release immutability and both approved applications' full
admission distinct from the new recorded semantic content. Hosted CI observation is bound
to the reviewed source; local recording changes require their own future source-bound run
if committed. No new recording commit is made in this preparation task.

The [current CI observation](../targets/spring-vue-postgres/evidence/phase6-semantic-recording-ci-f0c2e37.json)
binds run `38240131941` to reviewed `f0c2e37`. At the recorded observation, contracts,
phase5-experiments and phase5c-hard-gates passed; phase6-target was still running and
closure had not been observed. Overall status is IN_PROGRESS, NOT FINAL, not GREEN.
Available artifact metadata is preserved without claiming downloads. The observation
also binds the retained earlier hosted full admission of both original Canonical 0.3
applications, explicitly separate from pending current-source admission and unexecuted
new semantic candidates.

The [local validation record](../targets/spring-vue-postgres/evidence/phase6-semantic-recording-validation.json)
binds the exact decision/review files, tests and release seal. Seventeen historical
reference approval/evolution tests and seven new integrity/order regressions passed.
The historical synthetic evolution tests use test-only authority and do not supply a
real deployment journal, production data decision or new execution proof. Canonical
0.2/0.3 byte/hash vectors and repository checks also passed. Prior tracked files,
including proposals, historical approvals and the first blocked audit, are unchanged.

Sealed target/generator 0.5.0 remains exactly
`ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb`.
No implementation, SQL, migration, deployment, Phase 6 closure or Phase 7 work is authorized.
