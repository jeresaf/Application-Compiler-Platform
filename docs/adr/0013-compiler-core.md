# ADR-0013: Immutable compiler execution and reference orchestration

Status: ACCEPTED for bounded Phase 4 contracts/reference harness. Date: 2026-10-07.
Basis: charter §§3, 8, 20, 30, 36–39; ADR-0001 through ADR-0012.
No production language, parser, plugin ABI, storage service or framework selected.

## Decision

Use versioned immutable execution/stage records around the accepted semantic,
canonical and change contracts. Implement independently executable Ingest,
Elaborate, Analyze, Normalize, Project, Realize, Negotiate/Lower and Generate
boundaries with exclusive Success/Failure results, declared context/ports,
deterministic identities, provenance, obligations, resource/cancellation contracts
and an audit manifest. Reuse Phase 1 validation, Phase 2 normalization/admission/
byte encoding and Phase 3 reference/dependency impact. No failed representation
can feed a downstream stage. [Execution contract](../compiler-core.md) defines
exact behavior and limits.

Extend the replaceable Python test harness under ADR-0003. The structured frontend,
exact-content test allowlist, in-memory snapshot/cache/artifact stores, neutral
realization and clearly named synthetic target prove stage composition. Generation
produces immutable plans only; no application files are written. Source maps stay
sidecars. All runtime enforcement/verification obligations stay outstanding.
Pure Project subpasses have conservative exact-dependency cache keys and verified
entries. Other stages re-run; authorization is never trusted from cache.

## Alternatives and consequences

| Alternative | Assessment |
| --- | --- |
| Monolithic validator/generator | Hides failure, authority and target boundaries; independently replaceable passes are required |
| Select production runtime/parser/framework now | Would bypass ADR-0004 and later phase gates; rejected |
| New canonical representation/normalizer | Would compete with accepted Canonical Application meaning and vectors; rejected |
| Full production plugin, worker and filesystem implementation | Exceeds Phase 4; use typed ports and bounded reference adapters instead |
| Cache every stage or infer minimal invalidation immediately | Risks stale authorization/security results; start with independently verified pure projection entries and conservative stage recomputation |

Immutable byte-backed documents give deep immutability without exposing parser or
storage objects. This costs copies/validation and is not a scale benchmark. Compiler
object hashes are separately domain-separated using the accepted codec. No canonical
schema or vector changes are needed. Derived identities exclude names/revisions;
provenance and cache content bind exact revisions and declared inputs.

Dependency-manifest cycles fail; legal semantic cycles terminate with visited sets.
Required capability mismatches and dropped obligations fail explicitly. Ownership
plans protect HUMAN_OWNED content and detect races/collisions before the reference
store's atomic application. Ports invert dependencies; they are not a sandbox for
hostile adapters. Cooperative budgets and declared supervisor control are executable;
worker isolation, hard preemption, production RSS enforcement and symlink-safe real
filesystem stores remain future P-08/P-09/P-11 work.

## Evidence and phase limits

[Compiler tests](../../tooling/tests/test_compiler.py) cover independent stages,
failures/no downstream execution, versions, immutable inputs, authority rechecks,
provenance/rename/collision behavior, obligation propagation, caches/impact,
ownership and resources, repeated execution and separate-process environmental
variation. [Synthetic vectors](../../test-corpus/compiler/vectors.json) cover both
full domains. [Completion report](../phase4-completion-report.md) records actual
local and Ubuntu CI acceptance, not unperformed production experiments.

This resolves only bounded orchestration/capability/plan aspects of P-08 and
compiler-object/artifact-plan provenance aspects of P-09. Production plugin ABI,
source maps after manual edits, regeneration and source intelligence remain open.
AIProvider is a candidate-only contract; successful reference compilation has no AI
provider. Clock/secret/environment/source/evidence ports remain unimplemented
production boundaries. ADR-0004 remains PROPOSED. Phase 5 is NOT STARTED.
