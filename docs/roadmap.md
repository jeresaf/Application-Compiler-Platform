# Roadmap and exit criteria

The charter's phase order remains authoritative. Model 0.2.0 resolves P-01 through P-05 through ADR-0006 through ADR-0010. Phase 1 closure awaits the final repository checks and green Ubuntu/Windows CI evidence recorded in the [completion report](phase1-completion-report.md). Later-stage boundary documents are contracts, not implementations.

| Phase | Deliverable / exit evidence | Current state |
| --- | --- | --- |
| 0 Constitution | Authority hierarchy, vocabulary, AI boundaries, production definition | Baseline recorded |
| 1 Meta-model | Typed identity/lifecycle/basis/ownership, bounded domain semantics, closed schemas, diagnostics, positive/negative corpus, two domains and cross-platform CI | Model 0.2.0 implemented; closure validation pending |
| 2 Canonical IR | Approved/typed/normalized framework-neutral snapshots; serialization/version/hash vectors; migrations and compatibility suite | **Next gated phase; not started.** P-07 requires a decision during that phase |
| 3 Change/provenance | Atomic changes, semantic diff/impact, proposals, authenticated approval, journal/history and crash/race tests | Logical contracts only; P-06/P-09 open |
| 4 Compiler core | Independently testable compiler stages, ports, diagnostics and mappings | Stage contracts only; production runtime unselected |
| 5 DSL/frontend evaluation | Comparative parser/editor/diagnostic/refactor/performance experiments and technology ADR | ADR-0004 protocol only; no experiments, grammar or selection |
| 6 First target | Selected production stack, capability negotiation, Target IR, deterministic generation and migration/ownership tests | No target chosen; P-08 open |
| 7 Source intelligence | Symbol/reference/type graph, completeness, ownership, impact and drift regressions | Port contracts only; P-09/P-10 open |
| 8 Verification | Isolated build/test/migration/security/traceability/evidence gates | Typed obligations and reference evidence checks only; P-11/P-12 open |
| 9 MCP adapter | Mature semantic operations with bounded context, approvals and provenance | Deferred |
| 10 Reference application | Generate and evolve a serious multi-tenant/workflow/document/report/UI/job application | Two synthetic semantic reference domains; no generated application |
| 11 Hardening | Concurrency, recovery, scale, compatibility, supply chain, isolation and fault injection | Deferred |
| 12 Production validation | Repeated create/modify/migrate/verify/deploy/maintain/recover releases passing all profile gates | Not claimed |

## Phase 1 exit gate

Accepted bounded semantics and safe exclusions are in [coverage](coverage.md); executable assets are listed in the [corpus](../test-corpus/README.md). The final exit table and exact local/CI results live in the [completion report](phase1-completion-report.md). No failing required check may be treated as a completed exit criterion.

## Next gated investigations

1. Review and accept the Phase 1 completion evidence before authorizing Phase 2. No Canonical IR implementation is included in this task.
2. In a separately authorized Phase 2, resolve P-07: canonical encoding, versioning, ordering/hashing and migration/reapproval vectors. Authoring JSON does not settle these choices.
3. Preserve P-06 and P-09 for durable changes, concurrency, provenance and regeneration; P-08 for capability/plugin boundaries; P-10 for source intelligence; P-11 for isolation; P-12 for production authority/evidence; P-13 for AI candidate validation.
4. Perform ADR-0004's required evidence-based experiments before selecting any production language/parser. Semantic stabilization does not select a technology automatically.

P-01 through P-05 are resolved at bounded Phase 1 scope; they are not immediate open investigations. Their explicit exclusions remain rejected until separately proposed and approved.

## Reference evolution remains later work

Payment tests monetary types and tenant-scoped command/workflow contracts. Case-management tests organization/users, related owned case records, assigned review, approval/archive workflows and task UI without financial assumptions. Neither is a generated or production-validated application.

The later repeated-release corpus must exercise stable-ID rename, optional relationship addition, required-field backfill, tenant policy tightening, workflow evolution, API/event version coexistence, UI redesign, target upgrade and recovery. Each measures migration safety, provenance, custom-source preservation, stale evidence, drift and reproducibility. One-time generation cannot satisfy production readiness.
