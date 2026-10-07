# Phase 4 — Compiler Core 0.1.0 completion report

Status: implementation complete; final local and Ubuntu CI acceptance pending.
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

Final complete local regression and exact Ubuntu CI run will be recorded here
before closure. Development failures are not counted as green acceptance.
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
