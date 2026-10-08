# Roadmap and exit criteria

The charter's phase order remains authoritative. Model 0.2.0 resolves P-01 through P-05 through ADR-0006 through ADR-0010. **Phase 1 exit criteria are satisfied:** repository checks and all 23 tests passed locally and on both Ubuntu and Windows in [CI run 35513441694](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/35513441694). The [completion report](phase1-completion-report.md) records the evidence and limitations. Later-stage boundary documents are contracts, not implementations.

| Phase | Deliverable / exit evidence | Current state |
| --- | --- | --- |
| 0 Constitution | Authority hierarchy, vocabulary, AI boundaries, production definition | Baseline recorded |
| 1 Meta-model | Typed identity/lifecycle/basis/ownership, bounded domain semantics, closed schemas, diagnostics, positive/negative corpus, two domains and cross-platform CI | **COMPLETE: bounded model 0.2.0 closed and green** |
| 2 Canonical IR | Approved/typed/normalized framework-neutral snapshots; serialization/version/hash vectors; migrations and compatibility suite | **COMPLETE: bounded Canonical Application 0.1.0, closed and green.** ADR-0011 resolves bounded P-07; [report](phase2-completion-report.md) |
| 3 Change/provenance | Atomic changes, semantic diff/impact, proposals, authenticated approval, journal/history and crash/race tests | **COMPLETE: bounded Change and Provenance 0.1.0, closed and green.** Bounded P-06 and semantic-history P-09 resolved in [ADR-0012](adr/0012-change-history.md); [report](phase3-completion-report.md) |
| 4 Compiler core | Independently testable compiler stages, ports, diagnostics and mappings | **COMPLETE: bounded Compiler Core 0.1.0, closed and green**; 92 regression tests and Ubuntu CI; eight-stage reference compiler; [report](phase4-completion-report.md); production runtime unselected |
| 5 DSL/frontend evaluation | Comparative parser/editor/diagnostic/refactor/performance experiments and technology ADR | **CLOSED AND GREEN (bounded evaluation)**; Phase 5C accepts native worker and source-analysis architectures; core runtime/textual frontend independently DEFERRED; Xtext production REJECTED on provenance; [report](phase5-completion-report.md); [ADR-0004](adr/0004-technology-evaluation.md) |
| 6 First target | Selected production stack, capability negotiation, Target IR, deterministic generation and migration/ownership tests | **IN PROGRESS, NOT CLOSED**; Java 21 / Spring Boot / Vue / PostgreSQL target prototype; [status](phase6-completion-report.md); P-08 acceptance outstanding |
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
work. The separately authorized Phase 5 experiments are recorded in their [report](phase5-completion-report.md). Integration and source-analysis architectures are accepted; production core/frontend remain deferred. Phase 6 is IN PROGRESS and NOT CLOSED; Phase 7 is NOT STARTED.

## Phase 6 semantic blocker resolution

ADR-0016 is ACCEPTED by the user's subsequent explicit approval on 2026-10-08. Authoring 0.4 is APPROVED REFERENCE SEMANTICS; Canonical 0.3 is APPROVED REFERENCE SNAPSHOTS; ChangeSet 0.3 is GREEN for bounded reference evolution. The exact [approval record](deterministic-v04-approval-record.md) covers both complete fixture decisions, including F-01. Required reference-app canonical gaps are zero. Proposal-time reports preserve their historical status.

The current approved [privacy/lifecycle checkpoint](phase6-privacy-lifecycle.md) uses sealed target `acp-spring-vue-postgres/0.3.0`, generator `acp-spring-vue-generator/0.3.0` and unchanged Target IR `0.2.0`. Actual negotiation against both approved Canonical 0.3 applications leaves exactly eleven task-interface capability blockers per domain: Action, Filter, Form, InputControl, PermissionBoundary, Screen, Search, Table, ViewState, Wizard and WizardStep (interface version `0.2.0`), bound by immutable [contract 4.0.0](../targets/spring-vue-postgres/expected-open-blockers-v4.json). Privacy/lifecycle support is constrained to the documented subset; infrastructure verification remains OUTSTANDING. [Hosted Ubuntu CI 37809799618](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/37809799618) passed for implementation commit `01fe1e905ed97e482a004761a553e2d8b7a1a749`. Strict Phase 6 closure remains BLOCKED; Phase 6 is IN PROGRESS / NOT CLOSED and Phase 7 is NOT STARTED.

Historical delivery/Jobs checkpoint: The [delivery and Jobs tranche](phase6-delivery-jobs.md) uses target profile and generator 0.2.0 and explicitly versioned Target IR 0.2.0. Actual worker negotiation against both unchanged approved Canonical 0.3 snapshots reports 16 blockers per application, bound by [contract 3.0.0](../targets/spring-vue-postgres/expected-open-blockers-v3.json): five privacy/lifecycle families and eleven UI families. DeliveryPolicy, Schedule and Job support is constrained to the exact documented subset. Historical blocker contracts 1.1.0 and 2.0.0 remain unchanged. Strict Phase 6 closure remains BLOCKED; Phase 6 is IN PROGRESS and Phase 7 is NOT STARTED.

Historical target capability work began against the accepted [explicit execution/dataflow successor](adr/0015-explicit-operation-effects-and-dataflow.md) and its [dedicated report](execution-v03-completion-report.md). Authoring 0.2 / Canonical 0.1 and historical Phase 1–5 closure remain preserved. Authoring 0.3.0 and Canonical 0.2.0 are APPROVED AND GREEN; ChangeSet 0.2 is GREEN; ADR-0015 is ACCEPTED; execution-v03 fixture decisions are APPROVED REFERENCE SEMANTICS (explicit human approval, 2026-10-08). Phase 6 remains IN PROGRESS; Phase 7 remains NOT STARTED. Phase 6 closure still requires negotiated generated enforcement and complete target gates.
