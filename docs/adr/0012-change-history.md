# ADR-0012: Bounded semantic changes and durable history

Status: ACCEPTED, bounded Phase 3 reference contract; transactional invariants pass local executable tests. Date: 2026-09-28. Scope: P-06 and the semantic-history portion of P-09. Phase closure still requires hosted Ubuntu/Windows checks in the completion report.

## Decision and alternatives

Use immutable complete Canonical Application snapshots with an atomic append-only semantic journal behind a repository port. Store proposals separately from accepted state. A change commits only against its exact predecessor after deterministic planning, dependency checks and authenticated approval. The [change contract](../change-model.md) defines operations and authority boundaries; the [completion report](../phase3-completion-report.md) records evidence.

| Option | Assessment |
| --- | --- |
| Mutable current document plus ad hoc audit log | Lower initial storage cost, but separate writes can lose atomicity and do not guarantee immutable historical revision meaning. Rejected as the authoritative model. |
| Full event sourcing | Requires event-version evolution and replay semantics beyond this phase. No demonstrated need justifies adopting it. |
| Immutable snapshots plus semantic journal | Direct historical reads and independently validated snapshots; atomic consistency and explicit provenance. Selected despite deliberate duplication and full-snapshot cost. The journal explains accepted transitions; it is not the sole state representation. |

SQLite is a replaceable local reference adapter, not a production storage selection. Explicit `BEGIN IMMEDIATE`, rollback journaling and `synchronous=FULL` serialize the short compare-and-append section. SQLite permits one writer at a time. [SQLite transaction documentation](https://www.sqlite.org/lang_transaction.html).

Atomicity assumes working filesystem locking and durable flush behavior. Process-exit tests exercise recovery; they do not simulate hardware power loss or certify network filesystems. [SQLite atomic commit documentation](https://www.sqlite.org/atomiccommit.html).

## Consequences and evidence

Exact-reference dependents advance deterministically, including cycles, without changing the Phase 2 schema or hash profile. Snapshot, revision/identity indexes, tombstones, journal, retry receipt and applied proposal event commit together. Builds and releases are outside this transaction. Stale bases cannot apply; explicit independent rebase requires new approval. Dependency conflicts and conservative security/workflow fences require merge review.

Approval binds the canonical content digest and a separate digest of the whole plan, including impact and migration obligations. The HMAC reference authority uses injected sessions, application scopes, expiry, current grants, revocation and author/reviewer separation. It is not production identity, key custody or durable revocation infrastructure.

Portable exports contain versioned JSON records, not SQLite pages. Empty-store restore verifies history against an external anchor before commit. This demonstrates replaceable representation, not a second production adapter. Hash chains detect partial alteration; an independently retained anchor is needed for coherent privileged rewriting or truncation. Historical authority verification is separate from current revocation.

Tests cover actual competing connections, subprocess exits before/after commit, idempotent recovery, approval invalidation, supersession, forward rollback, provenance, tampering and restore. Both reference domains undergo six accepted snapshots. [Storage observations](../../test-corpus/change/storage-observations.json) record measured payload/database sizes and reopened anchored audits. These are synthetic size observations, not throughput benchmarks.

Plans are duplicated in proposal history and the journal to favor inspection. Production requires retention, indexing, capacity, backup/restore, key management and workload evaluation. P-06 is resolved only for this bounded contract. P-09 is resolved for requirement/decision/concept/change/snapshot lineage and import receipts. Generated-source ownership, maps, regeneration and drift remain open. ADR-0004 remains PROPOSED. Phase 4 is not started.
