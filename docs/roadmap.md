# Roadmap and exit criteria

The charter's phase order remains authoritative. Contract previews of later stages do not mean those stages are implemented. The current delivery is a Phase 1 baseline and executable kernel; Phase 1's broader semantic extensions remain open.

| Phase | Deliverable / exit evidence | Current state |
| --- | --- | --- |
| 0 Constitution | Charter, authority hierarchy, vocabulary, AI boundaries, production definition | Baseline recorded |
| 1 Meta-model | Typed concepts, identity/lifecycle/relationships/invariants/ownership; diagrams; machine-readable model; valid/invalid semantic corpus; explicit unresolved decisions | Kernel implemented; full bounded-domain contracts and P-01–P-05 require further decisions |
| 2 Canonical IR | Approved/typed/normalized framework-neutral snapshots; serialization/version/hash vectors; schema migrations; validation and compatibility suite | Boundary contract only; P-07 open |
| 3 Change/provenance | Atomic changes, semantic diff/impact, proposal branches, approval authority, journal/snapshot/history; race/crash/retry tests | Logical contract only; P-06/P-09 open |
| 4 Compiler core | Independently testable ingest/analyze/normalize/realize/lower/verify stages with ports and diagnostic/source mappings | Stage contracts only; production runtime unselected |
| 5 DSL/frontend evaluation | Representative ANTLR/Langium/Xtext experiments, diagnostics/editor/refactor/performance evidence, accepted technology ADR | ADR-0004 protocol prepared; no grammar or selection |
| 6 First target | One selected production stack; capability negotiation; target IR; deterministic generation; migration and ownership tests | No target chosen |
| 7 Source intelligence | Symbol/reference/type graph, completeness, source ownership, impact, drift regressions | Port/ownership contracts only |
| 8 Verification | Isolated build/test/migration/security/traceability/evidence gates | Baseline contracts only |
| 9 MCP adapter | Mature high-level semantic operations with bounded context, approvals and provenance | Deferred |
| 10 Reference application | Generate and evolve a serious multi-tenant/financial/workflow/document/report/UI/job application | Synthetic semantic slice only; no generated application |
| 11 Hardening | Concurrency, recovery, scale, compatibility, supply chain, isolation and fault-injection evidence | Deferred |
| 12 Production validation | Repeated create/modify/migrate/verify/deploy/explain/maintain/recover releases with all profile gates | Not claimed |

## Immediate next investigations

1. Resolve P-01/P-02: nominal/refined value semantics, relation/aggregate ownership, nullable expressions, policy composition, mandatory tenant/retention enforcement. Add fixtures before promoting semantics to supported.
2. Resolve P-03–P-05: execution failures/transactions/delivery, task UI vs Design IR, quality and operations obligations. Keep all business defaults application-specific.
3. Stabilize Phase 1 contracts against more than one domain; then decide canonical serialization/hash/migration vectors and approval authority contracts.
4. Evaluate production core runtime before writing it; frontend evaluation stays behind semantic stabilization. Technology selection needs measured ADR evidence, even if a familiar language seems convenient.

## Reference evolution corpus

The current synthetic tenant/payment/state-machine fixture exercises semantics; it does not establish complete financial correctness. A serious Reference A must additionally cover multiple organizations/campuses, users/roles/record scope, financial reversals/audit/retention, approval workflows, documents, reports, notifications, APIs, responsive/accessibility UI, background jobs, and runtime controls. SACCO/alumni terms must remain fixture vocabulary.

Planned repeated-release sequence: initial release → stable-ID rename → add optional relationship/field → required-field backfill → tenant policy tightening → financial reversal workflow → API/event version coexistence → UI task redesign → dependency/target upgrade → restore/failure recovery. Every step measures semantic impact, migration safety, provenance, custom-source preservation, stale evidence, drift and reproducibility. No phase accepts one-time generation as sufficient evidence.
