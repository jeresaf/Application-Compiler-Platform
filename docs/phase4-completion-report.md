# Phase 4 — Compiler Core 0.1.0 completion report

Status: **CLOSED AND GREEN — bounded Compiler Core 0.1.0.**
Date: 2026-10-07. Phase 5 is NOT STARTED. Phases 1–3 remain closed and green;
their historical reports and evidence are unchanged.

## Delivered scope

[ADR-0013](adr/0013-compiler-core.md) and the [execution contract](compiler-core.md)
define the bounded phase. There are eight executable independently testable
immutable stage boundaries, exact request/context/version contracts, exclusive
Success/Failure, declared ports, compiler diagnostics, provenance, outstanding
obligations, deterministic identities/audits, conservative impact/cache invalidation
and ownership-safe immutable artifact planning.

| Category | Delivered | Boundary |
| --- | --- | --- |
| Compiler contracts | Frozen request/context/stage/result/projection/realization/target/plan/audit records; exact versions, identities, provenance and obligations | Reference typed API, not a production language or plugin ABI selection |
| Reference implementations | Structured frontend, existing semantic/canonical functions, exact-content fixture authority, in-memory snapshots/cache/store/control, pure projection and neutral realization | Host-injected synthetic approval; no IAM, SQL in passes, production persistence, hard worker isolation or real filesystem writes |
| Synthetic target | Complete payment/case-management records, capability rejection, exact semantic/source mappings, artifact intentions and outstanding obligations | Test data only; no framework, generated application, target runtime or enforcement proof |
| Future production implementations | AI/source/evidence/clock/secret/environment and worker/filesystem boundaries formalized as ports | No Phase 5–9 implementation; no parser/target/source intelligence/MCP selection |

Normalize calls Phase 2's existing `normalize_candidate`/`admit`. Canonical schema,
normalization/serialization implementation and all canonical vectors are unchanged.
Phase 3 graph/impact semantics are reused; SQLite remains a history reference adapter,
not compiler architecture. Fixture AI is unnecessary: no AI provider is configured.

## Acceptance evidence

Implementation commit: `842e66cd7365c4c070bca53abd089924df6d1852`.

| Check | Observed result |
| --- | --- |
| Complete local Linux regression | **PASS: 92 tests in 284.309 seconds**, including 63 Phase 1–3 tests and 29 compiler tests |
| Local tooling | CPython 3.14.4, Linux x86_64, SQLite 3.46.1; Node v24.21.0; all pinned Python dependencies unchanged |
| Dependency/repository/whitespace checks | `pip check`, `check_repository.py`, `git diff --check`: **PASS** |
| Independent Node canonical verification | **PASS: 9 positive, 13 negative, 2 snapshot hashes** |
| Ubuntu 24.04 hosted CI | [**GREEN: run 37611841644**](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/37611841644), [contracts job](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/37611841644/job/112760668862); dependency, repository, complete Python suite and independent Node steps all succeeded |
| Hosted tooling | Workflow pins CPython **3.14.7** and Node **24.21.0**; no CI gate weakened |
| Prior canonical assets and reports | Git diff confirms canonical schema/code/corpus and Phase 1–3 reports unchanged |
| Cross-process determinism | Complete small artifact-plan bytes equal across three Python processes, C/C.UTF-8 locales, cwd/tmp directories, hash seeds and irrelevant environment/discovery order |

Full-domain synthetic plans contain 101 payment and 149 case-management records,
with 40 and 44 outstanding obligations respectively. Their Phase 4 hashes are
pinned in the [compiler corpus](../test-corpus/compiler/vectors.json), independently
of the unchanged Phase 2 canonical vectors.

The earlier development run exposed an incomplete source-map constructor while
files were being edited. It was corrected, the cross-process test rerun, and the
complete final suite passed on the fixed implementation. Failed development runs
are not closure evidence. Pip's sandboxed host cache was unwritable, so pip disabled
caching; dependency consistency still passed. Local `/tmp` logs are ephemeral only;
the hosted run above is the durable acceptance link. No host tools or services were
changed. This report's closure/status edits are documentation of that tested code.
Reproduction commands are in [DEV_LINUX.md](../DEV_LINUX.md) and
[compiler-core.md](compiler-core.md#reproduction).

## Exit coverage and limitations

The suite exercises full pipelines for both domains; independent stages; failure
at each boundary with no output and no downstream execution; exact version/type
rejection; deterministic/redacted diagnostics; immutable source and sidecars;
canonical admission rechecks; missing/invalid decision, dependency, capability
and obligation failures; bounded work/input/output/node/depth and cancellation/
operational timeout; derived identity collisions and rename continuity; unsafe
paths, ownership preservation and atomic reference-store races; changed revision
invalidation, dependency closure, unrelated cache reuse and rehashed cache poison
rejection. Separate processes vary cwd/tmp/locale/hash seed/environment/discovery
order and compare complete artifact-plan bytes. Ordered semantic changes alter
output. Warm/cold cache audit counters are operational metadata, not output identity.

The cache deliberately covers only pure per-concept Project subpasses. Whole-stage
recomputation is conservative. Byte/work/node limits are a memory-budget abstraction,
not an OS RSS cap. Supervisor timeout/cancellation is cooperative at checkpoints;
hard preemption and hostile plugin isolation are future adapters. Source mappings
are sidecars and reference plans, not source intelligence or real filesystem
regeneration. No production enforcement/test execution, migration, deployment or
scale claim is made. All semantic obligations remain OUTSTANDING. Phase closure
certifies these bounded compiler contracts only, never production readiness.


## Required final state

- PHASE 1 = CLOSED AND GREEN
- PHASE 2 = CLOSED AND GREEN
- PHASE 3 = CLOSED AND GREEN
- PHASE 4 = CLOSED AND GREEN
- PHASE 5 = NOT STARTED

No Phase 5 DSL/parser evaluation, Phase 6 production target generation, Phase 7
source intelligence, Phase 8 production verification engine or Phase 9 MCP
implementation was started. Future phase work requires its own continuation.
