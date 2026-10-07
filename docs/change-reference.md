# Executable Phase 3 reference protocol

Version 0.1.0. This is the bounded implementation of the [change model](change-model.md), with [schema](../contracts/change.schema.json), [planner and ports](../tooling/changes.py), [repository](../tooling/history_repository.py) and [reference authority](../tooling/reference_authority.py). Canonical Application 0.1.0 and `acp-jcs-safe-v1` are unchanged.

## Operations and lifecycle

A ChangeSet contains ID, authenticated author, intent, branch label, exact base `{sequence,digest,journalDigest}`, operations, declared reads, migration plan, retained source/receipt pairs, parent proposal/journal digests and optional rollback target. One repository contains one application's history. Branches isolate candidates; they do not alter the accepted head.

| Operation | Rules |
| --- | --- |
| ADD | Never previously accepted ID, revision 1, APPROVED candidate lifecycle; authenticated approval is still required before acceptance. |
| REVISE | Exact expected prior revision, same ID/kind/lifecycle, revision +1. Rename preserves ID. Revision-only no-ops fail. |
| DEPRECATE | APPROVED to DEPRECATED at revision +1; retained in canonical content. |
| SUPERSEDE | Different active same-kind replacement at exact revision; no cycles or simultaneously retired replacement. Keep a SUPERSEDED tombstone outside canonical content and reserve the retired ID forever. |

One explicit operation per ID is permitted. Full canonical validation follows planning. Exact-reference inbound dependents advance once per transaction and references are rewritten, including transitive cycles. This can revise many nodes for a rename; approval covers the complete diff. Literal records are not semantic references. Issue references also advance. No Canonical IR lifecycle extension is needed for tombstones.

Proposal events follow `PROPOSED -> REVIEW_REQUIRED -> APPROVED -> APPLIED`. Nonterminal edits append a new PROPOSED plan and invalidate approval. REJECTED/APPLIED are terminal. Authenticated authors propose, edit, review, reject and rebase; independent authorized reviewers approve. Unsafe rebase appends MERGE_REQUIRED with conflicts and parent digests. Resolution requires a new current-base ChangeSet, full validation and fresh approval.

## Dependencies and analysis

The planner computes full before/after diff, changed fields, write IDs, transitive reverse-reference impact and dependency-closed reads. Reads include revisions and node digests; new IDs have absent-ID reservations. Extra declared reads are validated. The repository verifies the historical base's sequence, content digest and journal digest.

Apply rederives the plan, checks reads and requires the current head to equal the base. Stale reads or head fail without accepted-state writes. Independent rebase creates a new proposal. New incoming dependencies cause conflicts even when prior reads survive. Concurrent security changes and concurrent workflow changes use conservative category-wide fences. Disjoint files do not imply semantic independence.

Impact is complete only for the bounded exact-reference graph. `external: NOT_ANALYZED` excludes source, targets, tests, deployment and runtime. Risk is LOW/REVIEW/HIGH/CRITICAL; compatibility is BACKWARD/REVIEW_REQUIRED/BREAKING. These route review and do not prove prose/guard satisfiability or external compatibility.

Direct structural data changes and required-field additions require a migration plan: compatibility, irreversible declaration, steps, preconditions, verification, recovery and observation digests. UNKNOWN compatibility and missing required obligations block planning. `dataEffect` distinguishes DECLARED_IRREVERSIBLE, REQUIRES_DATA_REVIEW and NO_DATA_CHANGE_INFERRED. Data is not scanned and migration descriptions are not executed. Reviewers must establish actual backfill, compatibility and recovery. Irreversible work requires IRREVERSIBLE scope and CRITICAL risk.

## Authority

Approval requests bind application, authenticated author, Phase 2 content digest, required scopes and `planDigest`. The latter covers the entire candidate, ChangeSet, diff, impact, reads/writes, migrations, provenance and classifications. Material edits invalidate approval. Plan/journal/node/proof/record hashes use `ACP\0change-history-v1\0<domain>\0` prefixes over unchanged canonical bytes; these do not replace Canonical IR hashes.

`ApprovalAuthority.authenticate(session)` resolves a host-authenticated principal. `verify(proof, request, now)` fails closed or returns exactly `{principal,proofDigest,request}`. The repository independently checks receipt shape, binding and author/reviewer separation. The host supplies trusted time, session resolution and the authority adapter. JSON names are not authentication. Verification runs at approval and again inside apply; an unavailable authority prevents a new commit. Only then is Phase 2 admission invoked.

The HMAC reference adapter requires an injected key of at least 32 bytes, session mappings and application-scoped grants. It checks signature, exact request, issue/expiry times, current grants and revocation. Scopes: SEMANTIC, SECURITY, LOCKED_DECISION, MIGRATION, IRREVERSIBLE. Revocation is in memory. Production IAM, durable revocation, clocks, key rotation and distributed trust are deferred. Tests use synthetic credentials. Optional `verify_historical` checks signature and acceptance time without deleting accepted history after later revocation. A committed retry returns its old receipt even after expiry; it authorizes no new mutation.

## Persistence, recovery and portability

Complete immutable snapshots, exact revisions, identity/retirement reservations, proposal events and linked journal are stored separately from canonical semantics. UPDATE/DELETE denial triggers prevent ordinary mutation, not privileged database tampering.

One `BEGIN IMMEDIATE` transaction appends snapshot, indexes, tombstones, approval/provenance-bearing journal, retry receipt and APPLIED event. Rollback journaling and FULL synchronization rely on SQLite filesystem assumptions. Process failure before commit leaves the old head; failure after commit returns the same receipt on retry. Retry keys bind one immutable plan/change. Competing writers cannot both commit against the same base. Storage failures roll back.

No build, test, release or remote authority transport is implemented. Authority adapters must be suitable for the short critical section. Accepted semantic state is separate from release success; failed observations never mutate it.

`audit()` recomputes the journal chain, plans and accepted indexes, checks proposal lifecycle/outcomes and evidence hashes, and optionally verifies historical authority. External `{sequence,journalDigest}` anchors detect coherent rewriting/truncation affecting the anchored prefix. Unanchored hashes cannot establish authenticity against privileged rewrites. Callers retain anchors independently; no remote anchoring service is supplied.

`export_records()` returns `acp-history-export-1` JSON records without SQLite pages. `restore(export, anchor)` requires an empty destination and validates inside the import transaction. Invalid imports roll back. Individual values retain the 1 MiB/depth-48 bound. Whole-history export is materialized in memory; streaming, pagination, scale and production disaster recovery are deferred.

## Rollback, evidence and provenance

Rollback is a new current-base ChangeSet restoring supported prior content at fresh revisions. The helper cannot resurrect retired IDs, reverse deprecation or restore different membership; these require explicit forward repair. Crossing declared irreversible work requires an irreversible repair plan and approval. Semantic rollback does not undo deployed data changes.

Append-only observations bind exact snapshot digest, subject revisions, artifact digest and PASS/FAIL/BLOCKED/NOT_RUN. Any snapshot change conservatively makes them STALE. They are untrusted observations, not production verification credentials; they do not replace Phase 1's full evidence context.

Lookup supports snapshot sequence/content digest, semantic ID/revision, journal history, source digest and transitive basis provenance. Requirement -> decision -> concept lineage retains exact historical revisions, origins, changes and snapshot digests. Full authoring inputs and Phase 2 migration receipts are retained and deterministically revalidated. Unknown provenance parents and inconsistent receipts fail.

Generated-source ownership/maps, source intelligence, production migrations, production authority/storage, distributed repositories and signing infrastructure remain later work. Phase 4 is not started.

## Explicit execution-version compatibility

The [ChangeSet 0.2 schema](../contracts/change-0.2.schema.json) explicitly binds `canonicalVersion: 0.2.0`. It can upgrade a historical 0.1 snapshot only through explicit authored revisions/additions and a newly approved plan. Dependent exact references advance through the existing closure rule. History keeps old snapshots/journal entries intact and exact lookups can retrieve both versions. ChangeSet 0.1 cannot revise a Canonical 0.2 snapshot. Existing storage, CAS, stale-base and digest-bound authority protocols remain mandatory. [Successor tests](../tooling/tests/test_execution_v03.py) exercise both reference domains and rejection of inherited approval.
