# Roadmap and exit criteria

The charter's phase order remains authoritative. Model 0.2.0 resolves P-01 through P-05 through ADR-0006 through ADR-0010. **Phase 1 exit criteria are satisfied:** repository checks and all 23 tests passed locally and on both Ubuntu and Windows in [CI run 35513441694](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/35513441694). The [completion report](phase1-completion-report.md) records the evidence and limitations. Later-stage boundary documents are contracts, not implementations.

| Phase | Deliverable / exit evidence | Current state |
| --- | --- | --- |
| 0 Constitution | Authority hierarchy, vocabulary, AI boundaries, production definition | Baseline recorded |
| 1 Meta-model | Typed identity/lifecycle/basis/ownership, bounded domain semantics, closed schemas, diagnostics, positive/negative corpus, two domains and cross-platform CI | **COMPLETE: bounded model 0.2.0 closed and green** |
| 2 Canonical IR | Approved/typed/normalized framework-neutral snapshots; serialization/version/hash vectors; migrations and compatibility suite | **COMPLETE: bounded Canonical Application 0.1.0, closed and green.** ADR-0011 resolves bounded P-07; [report](phase2-completion-report.md) |
| 3 Change/provenance | Atomic changes, semantic diff/impact, proposals, authenticated approval, journal/history and crash/race tests | **COMPLETE: bounded Change and Provenance 0.1.0, closed and green.** Bounded P-06 and semantic-history P-09 resolved in [ADR-0012](adr/0012-change-history.md); [report](phase3-completion-report.md) |
| 4 Compiler core | Independently testable compiler stages, ports, diagnostics and mappings | **COMPLETE: bounded Compiler Core 0.1.0, closed and green**; 92 regression tests and Ubuntu CI; eight-stage reference compiler; [report](phase4-completion-report.md); production runtime unselected |
| 5 DSL/frontend evaluation | Comparative parser/editor/diagnostic/refactor/performance experiments and technology ADR | **NOT STARTED**; ADR-0004 protocol only; no experiments, grammar or selection |
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

1. Phase 2 local and Ubuntu/Windows validation is complete, including independent canonical-byte checks. The user's continuation after Phase 1 closure began this phase on 2026-09-28; its [report](phase2-completion-report.md) records exact evidence and limitations.
2. Phase 3 is closed with all 63 tests and canonical checks passing locally and on Ubuntu/Windows CI. Atomic history, dependency-aware conflicts, provenance and authenticated approval use replaceable reference adapters. Phase 4 now implements bounded reference orchestration on those accepted contracts; its separate report records acceptance.
3. Preserve the remaining P-09 generated-source ownership/regeneration work; P-08 capability/plugin boundaries; P-10 source intelligence; P-11 isolation; P-12 production authority/evidence; P-13 AI candidate validation. Production persistence and identity remain unselected despite executable reference adapters.
4. Perform ADR-0004's required evidence-based experiments before selecting any production language/parser. Semantic stabilization does not select a technology automatically.

P-01 through P-05 are resolved at bounded Phase 1 scope; they are not immediate open investigations. Their explicit exclusions remain rejected until separately proposed and approved.

## Reference evolution and later releases

Payment tests monetary types and tenant-scoped command/workflow contracts. Case-management tests organization/users, related owned case records, assigned review, approval/archive workflows and task UI without financial assumptions. Neither is a generated or production-validated application.

Phase 3 executes initial state, stable-ID rename, optional relationship, required field with migration obligations, security tightening and workflow change in both domains. These are semantic history sequences, not deployed releases. Later work must execute actual backfills, API/event coexistence, UI redesign, target upgrades and recovery, measuring migration safety, custom-source preservation, stale evidence and drift. One-time generation cannot satisfy production readiness.

Phase 4 uses typed contracts, a structured reference frontend and a synthetic test
target. Its P-08/P-09 scope is compiler orchestration/capability/plan provenance only;
production plugin ABI, real source regeneration and worker isolation remain later
work. Phase 5 requires a separate continuation; it is not part of this task.
