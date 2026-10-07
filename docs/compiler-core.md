# Compiler core 0.1.0 reference contract

Status: Phase 4 executable reference architecture; no production language, parser,
framework, persistence service or target selected. [ADR-0013](adr/0013-compiler-core.md)
records the decision. Canonical Application 0.1.0 and Change/Provenance 0.1.0 are
unchanged. Linux is the engineering host, not a semantic or generated-target property.

## Execution boundary

[Contracts](../tooling/compiler_contracts.py), [ports](../tooling/compiler_ports.py),
[kernel](../tooling/compiler_core.py) and [test adapters](../tooling/compiler_reference.py)
are replaceable Python harness components under ADR-0003. Frozen typed records with
immutable `Document` bytes form the stage API. `Document.read()` returns a detached
strict JSON value. The byte codec is the existing Phase 2 `canonical_json` profile;
compiler object hashes have a separate `ACP\0compiler-core-0.1\0<domain>\0` prefix.
No canonical normalization, semantic validator or history algorithm is duplicated.
This in-process typed API is not a production plugin/wire ABI.

`CompilationRequest` version 0.1.0 declares application identity, exact canonical
snapshot and structured-source digests, compiler/pipeline/frontend/authority/target/
generator versions, start/end stage, feature/capability/configuration manifests,
resource/cancellation policy, exact dependency snapshots and their dependency edges,
architecture/design decision digests, approval evidence, accepted AI candidate
digests, optional change-plan digest and outstanding change obligations, repository
root and allowed ports. Set/keyed manifests normalize their ordering; semantic
ordered collections remain governed exclusively by Phase 2 rules. Unknown versions
or required features fail closed. The logical repository root is `.`; absolute host
paths do not participate in compiler identity.

`CompilationContext` is a frozen binding of the request, exact snapshot reader,
frontend, authority, target, cache, supervisor control and immutable ownership
inventory. Only those named ports can be used by the orchestrator. Clock, secrets,
environment, AI, source analysis and evidence execution are separate protocols,
not bound into deterministic reference compilation. Pure transforms do not read
SQL, network, clock, locale, filesystem listings, process environment, usernames,
random state or the working directory. The CLI alone loads the explicitly named
fixture before execution. Port adapters are trusted host code, not imported JSON.

The successful result is `Success(output, output_digest, provenance, obligations,
diagnostics, metrics)`. `Failure(diagnostics, provenance, metrics)` has no output
or output digest. A pipeline returns immediately on Failure and produces no
successful audit manifest. There is no recovery/editor AST in this version.
Unresolved invariants cannot become warnings or feed a later pass.

## Independent stage contracts

`execute(stage, input, context)` checks the exact input/output record type and
version and can run each pass independently. `compile_pipeline` selects the
requested contiguous range; its input must be the first stage's proper record.
A partial success is marked RANGE_COMPLETE, never complete compilation.

| Stage | Immutable input → output | Executable reference behavior |
| --- | --- | --- |
| Ingest | Source → Ingested | Exact source digest, negotiated frontend version, byte/node/depth bounds and relative source map; structured input stays supported, textual adapters parse inside the frontend port |
| Elaborate | Ingested → SemanticAST | Exact negotiated dialect; frontend elaboration returns an immutable SemanticAST with validated model version and source map; no parser class escapes |
| Analyze | SemanticAST → ResolvedModel | Validate exact dependency snapshots and acyclic dependency manifest; reuse full Phase 1 compile checks for exact references, types, blocking issues, security/workflow and conflicts; extract obligations |
| Normalize | ResolvedModel → CanonicalModel | Reuse `normalize_candidate` and `admit`; require exact requested digest and trusted current exact-content approval; no second canonicalizer |
| Project | CanonicalModel → Projections | Recheck admission; partition every canonical node exactly once into typed Product/Domain/Application views, preserving complete semantic records and ID/revision mappings |
| Realize | Projections → Realization | Validate projection coverage and meaning; independently approved, digest-bound architecture and design decisions with exact canonical origins; neutral reference realization objects |
| NegotiateLower | Realization → TargetIR | Recheck origins/choices; require every requested capability; synthetic target port must retain semantics, provenance and all outstanding obligations |
| Generate | TargetIR → ArtifactPlan | Exact target/snapshot, integrity/coverage and obligation checks; synthetic record plans; safe paths, content hashes, ownership and compare-and-swap intentions; no filesystem writes |

The authoring 0.2 contract currently permits exact local semantic references only.
Dependency snapshots are separately validated approved inputs; this phase does not
invent cross-application reference syntax. Cyclic dependency manifests fail.
Legal cyclic local semantic references use a bounded visited-set closure, while
forbidden basis/value/workflow cycles remain the existing semantic validator's job.

Source maps stay in immutable sidecars through normalization, projection, lowering
and artifact planning. They do not alter the canonical envelope or acquire authority.
Diagnostics retain safe supplied relative locations when available. Every stage
result binds canonical subject IDs/revisions, producer and input identities.

## Derived identity, provenance and obligations

Derived identity hashes the sorted stable `(applicationId, semanticId)` origin set
plus role/discriminator. Revisions change content, provenance and cache identity,
not durable derived identity. Display names and file locations never identify a
concept. Derived objects retain exact revision origins, producing stage, compiler/
pipeline versions and input digests. Canonical basis/origin records remain intact;
requirement/decision lineage is traversable through those exact semantic records.
Realization also binds approved decision digests; target and artifact provenance
bind target/capability and generator manifests respectively. Colliding derived IDs,
missing/changed origins, altered semantics and incomplete artifact mappings fail.

Analyze extracts authorization, audit, privacy, accessibility, test, reliability,
observability, compatibility, performance and constraint obligations from the
accepted typed kinds. Explicit change-plan obligations, including migration, are
bound to a declared plan digest and current subjects. That digest is a dependency,
not new approval: the host remains responsible for Phase 3's authenticated plan
approval before submitting it. All obligations remain OUTSTANDING. Every later
stage must retain the exact set; the synthetic target proves transport, not actual
runtime enforcement, generated tests or measured quality. Artifact verification
lists link relevant obligations and always require record-integrity verification.
No omitted obligation is considered satisfied.

## Determinism and incremental invalidation

Whole-stage identities bind stage name, all request declarations, exact typed input
and (for Generate) ownership inventory. Identity excludes runtime elapsed time and
cache counters. Output digests bind complete immutable outputs. `repeat=True`
executes a pass twice and fails on disagreement; this is a useful reference check,
not proof that arbitrary third-party code is deterministic.

The implemented cache is deliberately narrow: the pure per-concept Project subpass.
Its key includes role, application/semantic ID, the full exact semantic dependency
closure, compiler/pipeline versions, feature/configuration manifest and dependency
snapshot bindings. Architecture choices, AI providers and resource counters do
not affect that subpass's meaning; all stage entry validation, authority and
current execution limits still run. Entries verify key, output digest and expected
immutable value, including provenance. Even a rehashed incorrect entry fails;
this prioritizes correctness over optimization. There is no persistent cache or
cache of authorization decisions. Failed stage envelopes cannot become cached
successful compiler outputs.

`incremental_impact` reuses Phase 3's exact-reference graph and reverse dependency
rules. It compares old/new immutable records, unions old/new edges, computes a
visited-set reverse closure and conservatively unions supplied Phase 3 impact.
It identifies changed subjects, affected projection groups and affected passes.
Top-level stages conservatively re-run on any changed snapshot; eligible unchanged
Project subpasses reuse their verified entries. A changed root Decision invalidates
its dependents. Independent changed subjects preserve eligible unrelated entries.
No invalidation relies solely on a caller-provided impact list. This is a
correctness baseline, not a performance or minimal-recompilation claim.

The audit manifest (0.1.0) records input canonical digest, compiler/pipeline,
stage identities and input/output/provenance digests, exact dependencies, declared
configuration, outstanding obligations, artifact-plan/provenance digests, completion
status and per-stage cache hit/miss/work metrics. Warm/cold audits may differ in
operational cache metrics while artifact bytes stay identical. Timestamps and
external signatures are excluded; later attestations can bind the manifest.

## Resource policy and cancellation

Defaults are 1 MiB input/output per stage, 2,000 semantic nodes, depth 48,
200,000 cooperative work units, at most 32 diagnostic subjects and 60,000 ms
supervisor elapsed time. A stage emits one ordered diagnostic envelope on failure,
so the positive diagnostic limit is respected. Bounds must be positive and cannot
exceed the accepted codec's byte/depth limits. Traversal and reference closure are
iterative and charged to the work budget. Byte/node/work limits are also the
reference memory-budget abstraction; no operating-system RSS cap is claimed.

The immutable cancellation input supports immediate cancellation or a declared
work boundary. The explicit Control port can report cancellation and elapsed time.
The reference control supplies declared test values, never ambient time. Limits
are checked before work, during traversals and after external operations; an
exhausted budget returns Failure with no downstream output. Trusted in-process
adapters must be bounded/cooperative. Hard preemption of a stuck or hostile plugin,
OS memory containment and isolated worker timeouts belong to later P-08/P-11
production adapters; this phase does not claim that a Python protocol sandboxes code.

## Artifact and effect boundary

`acp-synthetic-test-target/0.1.0` supports only `reference.records/1` and
`reference.obligations/1`. It exercises both full domains, including Entity,
ValueObject, Command, Query, Permission/Policy, UseCase, Workflow, task UI and
quality/test obligations. Its JSON records are compiler test data, not application
source, a selected framework or the Phase 6 production target.

Each artifact binds a normalized relative path, role, immutable content/digest,
one of the four ownership classes, provenance, exact semantic/source mappings,
CREATE/UPDATE/NO_OP intention, expected prior digest, COMPARE_AND_SWAP policy and
verification obligations. Absolute paths, drive syntax, backslashes, traversal,
empty components, duplicate paths and file/directory prefix collisions fail.
Existing ownership must match. HUMAN_OWNED can only remain unchanged as NO_OP;
no automatic creation/adoption/update is permitted. The kernel never writes files.
The in-memory ArtifactStore revalidates inventory and the full plan atomically
before applying anything, including expected-digest race checks. No real filesystem
adapter, symlink traversal protection, region patching or regeneration service is
claimed; those remain P-09/future target obligations.

## Reproduction

```bash
.venv/bin/python3.14 -m unittest discover -s tooling/tests -p test_compiler.py -v
.venv/bin/python3.14 tooling/compiler_reference.py test-corpus/phase1/payment.json
.venv/bin/python3.14 tooling/compiler_reference.py test-corpus/phase1/case-management.json
node tooling/check_canonical_vectors.mjs
```

The reference CLI explicitly manufactures synthetic fixture approvals through the
host test allowlist. It is not an approval service and must not be used to admit
real specifications. It prints plan identity and outstanding obligation counts;
it writes no generated files. Phase 4 vector regeneration is separate:
`.venv/bin/python3.14 tooling/compiler_fixtures.py`. Review changed expected hashes;
never regenerate Phase 2 vectors to accommodate a compiler change.

Phase 5B adds an optional elaboration operation to the reference frontend port so
real textual adapters enter Ingest before producing semantic records. Existing
structured adapters retain the copy fallback. This is a target-neutral adapter
extension; Canonical Application 0.1.0, authority contracts and resource limits do
not change. Experimental frontend identities are exact manifest versions, not a
production plugin registration or selected DSL ABI.

## Frontend diagnostic metadata (Phase 5C)

The reference frontend port can reject input with immutable `SourceDiagnostic`
metadata. The compiler transports it through `Failure`, with no output: stable
code, semantic subject/related IDs, relative primary/related locations and explicit
location confidence (`TOKEN`, `END_OF_INPUT`, `DECLARATION`, `UNRECOVERABLE`).
Adapter exception wording and source text never become diagnostic explanations;
the host supplies fixed safe remediation. Unsupported codes, unsafe paths or IDs,
inconsistent confidence and oversized metadata fail closed.

`Ingested` and `SemanticAST` may carry an immutable source-detail sidecar for
JSON-pointer-to-token locations and exact-reference source positions. It is source
metadata only; Canonical Application content, canonical hashes, semantic identity,
change contracts and target-neutral stages are unchanged. The structured frontend
uses the empty default sidecar and retains its existing diagnostic behavior.
These reference extensions are not a production plugin ABI. Native worker
protocols and Linux process controls belong to the engineering experiment, not
Canonical IR or generated-target semantics.

## Explicit Authoring 0.3 / Canonical 0.2 support

The structured reference frontend `acp-structured-reference/0.2.0` accepts Authoring 0.3 with exact feature `acp.execution.0.3`. The historical frontend and feature remain exact and preserve their vectors. New requests also require `semantic.execution-dataflow/0.3`; an old target cannot silently accept and ignore the successor effects. All eight neutral stages retain explicit effects/dataflow and exact new approval; resumed canonical stages also check feature identity. The synthetic target emits semantic records, not executable target support. Old snapshots cannot acquire effects from target inference. Spring capability work remains paused pending review of [ADR-0015](adr/0015-explicit-operation-effects-and-dataflow.md).
