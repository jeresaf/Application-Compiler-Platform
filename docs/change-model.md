# Semantic change and provenance contract

Status: normative logical contract; persistence, merge algorithm and execution implementation remain P-06/P-09. Phase 2's [canonical contract](canonical-ir.md) resolves bounded P-07 content encoding/import, not this change engine. Basis: charter §§3.7, 3.11, 17–22, 26.

## Records

| Record | Required information |
| --- | --- |
| ChangeSet | ID, intent, author/origins, base snapshot, branch/proposal, semantic operations, dependency read set, impact closure, risk, compatibility, migrations, required approvals/evidence, status |
| Operation | ADD/REVISE/DEPRECATE/SUPERSEDE; semantic ID, expected prior revision (except ADD), proposed revision; rename is REVISE |
| SemanticDiff | Added/changed/retired concepts, old/new typed values, changed policy/behavior/quality obligations, ID continuity |
| Impact | Direct and transitive dependencies across semantics, realization, source, tests, migration, deployment/runtime; confidence and unresolved analysis |
| MigrationPlan | Data impact, observations/digests, preconditions, phases, compatibility window, verification, recovery strategy, irreversible steps |
| Approval | Authorized principal, exact change/input/impact digest, scope, decision, timestamp, authority proof, revocation/expiry policy |
| JournalEntry | Previous journal identity/digest, change and snapshot references, actor, approval evidence, outcome; append-only logical history |
| Evidence | Obligation refs and revisions, input/artifact/config/tool/profile digests, method, executor, observed result, time, environment, log/report digests |

Unknown risk/compatibility is blocking, not LOW/BACKWARD_COMPATIBLE by default. Compatibility dimensions include stored data, API, events, source extension contracts, active clients, operations, and security. Narrowing types, permission changes, removed audit/retention requirements, and incompatible event/API schemas require explicit analysis even if source builds pass.

## Transaction protocol

1. PLAN creates an isolated candidate against an exact base; no approved-state mutation.
2. VALIDATE and IMPACT analyze the candidate and its dependency closure. Incomplete source/data observations are retained as unknown.
3. APPROVE binds the final candidate, impact, migration, and input versions. A new edit invalidates prior approval.
4. APPLY uses compare-and-append against the base and read-set revisions. Snapshot, journal, and provenance commit atomically or not at all. Idempotency keys prevent duplicate application on retry.
5. COMPILE/BUILD/TEST/VERIFY produce artifacts and evidence outside the spec transaction. Failure leaves the approved snapshot intact and records failure; it never falsely marks implementation current.
6. PACKAGE/RELEASE evaluates exact-artifact gates and separate environment authorization. Runtime observations record what actually deployed.

This avoids holding a storage transaction across a build or deployment. A crash after spec commit is recoverable from an idempotent work record; a crash during release requires observed-state reconciliation.

## Concurrency and history

Edits on disjoint files are not necessarily semantically independent. Compare declared read/write sets and dependency closure. Simultaneous change of an ID/revision, conflicting policy, changed locked decision, or incompatible requirement produces a merge proposal, never last-write-wins. Disjoint semantic changes may be rebased only with fresh validation, impact, and approvals. Exact merge algorithm and storage engine are proposed in ADR-0005.

Rollback of a specification creates a new history entry; it cannot undo deployed data destruction. Production rollback may require restore or forward repair. Retired IDs remain reserved. Historical evidence remains inspectable but becomes stale when any relevant revision, artifact, environment, tool, or profile changes.

## Migration obligations

Plan expand → optional dual read/write → backfill → verify → switch → contract when compatibility requires it. Each phase has retry/idempotency behavior, ownership, data preconditions, active client constraints, and recovery evidence. Contracting schema before old clients retire blocks release. Financial/audit deletion and secret/security changes require dedicated approval scope. A backup claim is insufficient without restore verification.

Acceptance scenarios for Phase 3: rename preserves ID; stale base fails without writes; retry does not duplicate journal entries; concurrent security edits conflict; a locked decision cannot be casually revised; narrowing detects incompatible observed data; a crash resumes safely; stale evidence cannot satisfy a new revision. These are contracts, not tests claimed to run in Phase 1.
