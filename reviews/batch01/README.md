# ACP current state and Batch 01 delivery

Stocktake dated 25 November 2026, Africa/Kampala. Engineering baseline `bf34ca5d7eda7a483c0e77585663f73698c53dca` on `codex/phase11-hardening`. The charter, constitution and accepted ADRs continue to govern ACP. The [delivery register](delivery-register.json) carries the 17 H8 findings, 39 Phase 6 criteria, 23 production gates, six security-owner decisions, 38 advisory finding rows and active lifecycle/CI dependencies. Historical predicates and observations remain available at their original sources.

| Phase | Accepted or demonstrated | Current engineering obligation |
| --- | --- | --- |
| 0 | Constitution and architecture baseline adopted. | Apply authority, provenance and semantic boundaries to integrated delivery. |
| 1 | Bounded Model 0.2.0 closed. | Existing schema and domain limits define supported input. |
| 2 | Bounded Canonical 0.1.0 closed; later reference snapshots explicitly approved through 0.3. | Preserve exact semantics, digests and admission history. |
| 3 | Bounded change/provenance contract closed. | Operational authority and authenticated accepted-history deployment remain separate decisions. |
| 4 | Bounded compiler core closed. | Build through its existing target, provenance and publication ports. |
| 5 | Bounded frontend evaluation closed. | Preserve experimental and hard-gate results. Production adoption remains scoped by recorded decisions. |
| 6 | Payment and Case Management generation, candidate runtime, ownership, migration and recovery work. Sealed 0.5.0 remains distinct from 0.6.0 and later candidates. | Exact qualifying release evidence for 21 blocked predicates. Historical audit is 18 PASS and 21 BLOCKED. |
| 7 | Bounded native Java and TypeScript Source Intelligence with ownership, drift and impact evidence. | Vue/SFC and dynamic runtime completeness remain limited. Keep explicit uncertainty in the integrated pipeline. |
| 8 | Exact-artifact and Source Model verification, with bounded execution-evidence ingestion. | Produce complete, assertion-bound evidence for both domains and retain BLOCKED/NOT_RUN states. |
| 9 | Read-only stdio MCP with bounded context and versioned interfaces. | Any change operation starts with pure preview and closed validation under existing authority. Authenticated mutation and approval require separate decisions. |
| 10 | Case Management R0/R1 lifecycle, synthetic R2–R8 evolution, documents, jobs and stopped/fenced R6→R7 migration recovery. Payment provides another exercised reference domain. | Combine existing lanes into a two-domain lifecycle with explicit accepted-history, migration and mixed-version boundaries. |
| 11 | H1–H9 bounded hardening, H10 disabled plugin data foundation, H11–H11.2 package/software supply-chain evidence. | SEC-01 and SEC-02 remain blocked. Resolve open reliability causes, operating bounds, supply-chain attribution and owner decisions. |
| 12 | NOT_STARTED. | Repeated production lifecycle only after profile, authority and applicable gates are approved. |

The original roadmap still shows Phase 11 as “Deferred,” contains a historical “Phase 7 NOT STARTED,” and ends one checkpoint with Phases 9–12 “NOT_STARTED.” These describe different checkpoints. This dated table gives the current engineering view, with phase acceptance verified against historical decisions. The original roadmap and audit remain immutable.

## Workstreams, integration order and file ownership

| Track | Scope and exclusive source ownership | Dependencies and merge criteria |
| --- | --- | --- |
| WS-A | Existing workflows, qualification runners and CI parity/preservation guards. | Pinned interpreters and hash-checked transfers. Record exact-source job conclusions and acquisition blockers separately. |
| WS-B | Compiler lifecycle composition and tests outside sealed generators. Read-only MCP/Source Intelligence/Phase 8 entry points reused as consumers. | WS-A inputs and approved semantics. Demonstrate both domains across generation, ownership and verification. Accepted semantic application or SQL requires separate authority. |
| WS-C | Reliability and compatibility tests; only separately fingerprinted successor logic for material fixes. | WS-B generation path. Preserve historical CREATE finding, tenant controls and CAS. Reproduce before changing behavior. |
| WS-D | Existing supply-chain evidence and security contract tests. | WS-A build receipts and WS-B package identities. Widen verified coverage; approved lock changes and hostile execution are separate. |
| WS-E | Coherent production-profile inputs, recovery/custody and monitoring design. | Approved trust/service identities, operational requirements and exact lab authorization. Stop before production provisioning. |
| WS-F | This register, integrated acceptance matrix and exact-source evidence index. | WS-A through E supply discrete evidence. Report candidate qualification, formal production gates and sealed closure separately. |

Engineering critical path: pinned CI → immutable input build → both reference lanes → generation/ownership/source verification → approved evolution and recovery → exact evidence assembly. Reliability work can independently exercise bounded workload and error models from the same lanes. Package SBOM/license/triage work can independently consume same-source evidence. Production critical path: authority/profile decisions → admitted semantic, infrastructure and service inputs → authorized release lifecycle → applicable G-01–G-23 verification, with sealed Phase 6 closure evaluated independently. SEC-01 remains blocked pending D1–D6 and actual OS enforcement. SEC-02 remains blocked pending scope/identity, exposure, license and review evidence.

## Integrated qualification matrix

| When | Evidence to run or retain | Failing or unsupported state |
| --- | --- | --- |
| Focused development | Interpreter assertion, dependency/hash/transfer negatives, source and ownership contracts, canonical vectors, advisory/SBOM and manifest rejection. | Reject source or artifact substitution before use. |
| Affected integration | Both approved snapshots, target/generator identity, clean generated build, Source Model/ArtifactPlan comparison and Phase 8 obligation checks. | Explicit unresolved source relation or unmet obligation. |
| Application qualification | Authenticated Payment and Case Management operation, browser/API boundary and business effect, ownership-safe regeneration. | Runtime results remain candidate-only and source-bound. |
| Recovery and compatibility | Authorized disposable migration, transaction and restart cases; verify old/new writer fencing, database retention, semantic/audit continuity and restore cleanup. | Existing stopped transition provides no live mixed-version guarantee. |
| Performance and security | Bounded workloads, observed pool and queue state, dependency identity/attribution and security negatives. | Preserve empirical limits and rejected/unknown paths. Hostile-plugin OS cases stay NOT_RUN until approved. |
| Final source | Required main and affected workflow jobs, exact SHA, artifacts and hashes. | Acquisition failures and intentional closure exit 2 remain discrete. |
| Production and release | Independent exact execution and approval admission for applicable predicates. | Missing operational approval, stale evidence, or incomplete dependencies remain BLOCKED. |

REL-01, REL-03 and REL-04 share workload and resource observability needs. The historical CREATE error remains unattributed. The reduced pool produces a bounded analogous failure only. REL-02 has a distinct HTTP classification cause and a qualified H9-only correction. Pending job growth requires an approved behavioral bound; it cannot be inferred from pool size. ENG-01 concerns consumer/producer compatibility and writer overlap. ENG-02 concerns publisher, storage and host privilege. The durability claim requires process-crash versus power-loss distinctions independent of API compatibility.

No Phase 12 start or production acceptance is recorded. SEC-01, SEC-02 and Phase 6 release closure remain BLOCKED.
