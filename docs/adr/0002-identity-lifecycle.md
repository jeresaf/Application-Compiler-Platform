# ADR-0002: Identity, revision, and lifecycle

Status: ACCEPTED. Date: 2026-09-15. Basis: charter §§3.3, 3.6, 5–6, 19–22.

## Decision

Use `(applicationId, id)` as semantic identity and `(applicationId, id, revision)` for immutable revision identity. ID allocation is external to normalization; IDs are opaque ASCII tokens, never recomputed from names. A snapshot has exactly one revision of each included ID. References pin revisions; historical/cross-application edges use explicit external artifacts in a future contract.

Separate authoring/approval lifecycle from implementation, verification, release, and blocking observations. An approved requirement remains approved when a test fails. `IMPLEMENTED`, `VERIFIED`, and `RELEASED` are evidence-derived views; `BLOCKED` is a computed work/gate condition. They are not writable synonyms for approval. ADR `ACCEPTED` corresponds to approval of a Decision revision, not automatic acceptance of its dependencies.

Every durable semantic concept has a responsible steward, origin records, and justification where derived. Stewardship is distinct from generated-source ownership.

## Alternatives and evidence

- Name IDs violate rename continuity (§3.3).
- One status enum cannot describe an approved rule whose old implementation is released while its new revision is unverified (§§3.6, 18, 20).
- Floating references hide dependency changes and stale evidence (§§20–21).
- Exact references and independent evidence satisfy these cases at the cost of explicit reference updates in change sets.

## Consequences and validation

Concurrent edits require revision checks and revalidation. Retired concepts retain identity; IDs are not recycled. Approval verification needs a trusted authority adapter; fixture attestations only check shape and subject binding. The kernel tests duplicate IDs, stale/wrong-kind references, approval closure, and rename continuity. Persistent history, signature verification, and lifecycle transition execution are Phase 3 obligations.
