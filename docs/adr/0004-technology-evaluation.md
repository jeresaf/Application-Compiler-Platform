# ADR-0004: Independent technology and architecture decisions

Status: **ACCEPTED for integration and source-analysis architecture; production core runtime and textual frontend DEFERRED**. Updated 2026-10-07 after Phase 5C. Phase 6 is NOT STARTED.

## Final independent decisions

| Decision | Disposition | Choice and evidence |
| --- | --- | --- |
| Production compiler-core runtime | **DEFERRED** | Java Temurin 21+35, TypeScript 5.9.3 on Node 24.21.0, and Rust 1.90.0 remain viable. Identical immutable representative graph/provenance/obligation slices and expanded native fault fixtures pass. No failed result contains output or partial traversal. These are not complete candidate ports of the eight-stage compiler; speed does not settle implementation/maintenance tradeoffs. |
| Textual DSL/frontend | **DEFERRED** | ANTLR 4.13.2 and Langium/CLI 4.4.0 pass the bounded experiment hard gates. Xtext 2.44.0 is **REJECTED for production** because the exact patched ANTLR3 generator lacks verified source revision/patch/build provenance. Editor and team ergonomics data are not comparable enough for a weighted winner. Structured input remains supported. |
| Frontend/core integration | **ACCEPTED** | Default to disposable, long-lived native workers behind exact-version messages and an immutable host adapter. The demonstrated envelope is `acp-frontend-wire/1`, source `acp-text/1`, accepted byte profile `acp-jcs-safe-v1`, exact frontend identities ANTLR 4.13.2 / Langium 4.4.0, semantic model 0.2.0. Authority/approval and scheduling remain in the host; cancel/crash invalidates the whole in-flight result. Core runtime remains independent. |
| Source-analysis architecture | **ACCEPTED** | Syntax adapter + target-native semantic analyzer + explicit completeness/confidence (`KNOWN`, `UNKNOWN`, `UNRESOLVED`, `ABSENT`). Approved evidence uses TypeScript compiler API 5.9.3 and javac Temurin 21+35. Specific production language adapters remain **Phase 7 work**. Syntax alone never establishes semantic certainty. The previously unprovenanced wasm grammar stays rejected. |

## Why accept these architectures

Native ANTLR/Langium workers preserve parser/runtime state across repeated requests while semantic documents remain independent. The host preserves approval authority and exact request identity across crash/restart and queued retry. Native parser outputs become immutable plain records and bounded source sidecars; generated framework objects never enter Canonical IR. Actual compiler Failures now carry recoverable primary/related token locations and semantic IDs with deterministic, safe diagnostics. Tests include concurrent full pipelines, real active cancellation, malformed/oversized native response transport, stale IDs, duplicate requests and retry. Independent Java/TypeScript/Rust fault probes preserve the same Failure invariant. See [native tests](../../experiments/phase5/results/phase5c/native-tests.json), [diagnostics](../../experiments/phase5/results/phase5c/diagnostics.json), [fault fixtures](../../experiments/phase5/results/phase5c/core-faults.json) and [raw integration measurements](../../experiments/phase5/results/phase5c/integration.json).

The worker architecture wins on required fault containment and separation of authority, without forcing a frontend to dictate the core language. Same-process JVM/Node parser calls are also measured using actual native functions; they remain possible future optimizations when a complete host/core pairing can preserve the same boundaries. No artificial Python embedding is claimed. Split-runtime measurements feed actual frontend output through existing normalization and then into candidate graph-stage cores; these are representative integration proofs, not complete compiler ports.

Source-analysis architecture acceptance relies on the already-approved [Phase 5B native bindings and ownership evidence](../../experiments/phase5/results/phase5b/source.json), which is not rerun for this decision. It demonstrates imports, aliases, overloads, inheritance/interfaces, generated/human ownership, rename continuity and unresolved calls. A native-only syntax adapter is acceptable; no universal parser is required. Future adapters must preserve provenance, identity and confidence, and cannot convert syntax matches into known semantic facts.

## Versions, deployment, limitations and maintenance

Workers use Linux development/CI hosts, currently Ubuntu 24.04, CPython 3.14.7 in CI and Node 24.21.0. This engineering baseline introduces no Linux-specific semantic, IR, compiler-contract or generated-target requirement. Local Python 3.14.4 remains recorded separately. JVM probes use Java 21; Rust probes pin 1.90.0, serde_json 1.0.145 and sha2 0.10.9. These probe pins do not select a production core runtime.

The demonstrated worker model uses FIFO requests per worker and at most two independent native workers, 1 MiB framing, a 90-second probe timeout, observed 1 GiB worker RSS budget and 768 MiB managed heaps. The host owns process lifetime, correlation/version checks, bounded framing and cancellation; workers carry no approval capability. Exact protocol and frontend versions evolve independently with explicit rejection, corpus comparison and rollback. A crash or malformed response discards the result and requires fresh worker retry; source digests and authority are rechecked. Source facts fall back to explicit `UNKNOWN`/`UNRESOLVED`, never guessed certainty. Structured input remains the frontend fallback.

[Maintenance evidence](../../experiments/phase5/results/phase5c/maintenance.json) records Java 21→25, Node 22.20.0→24.21.0 and Rust 1.89.0→1.90.0 comparisons on identical fault/canonical corpora, isolated outputs and rollback. The local Java comparison also changes vendor to JetBrains Runtime; its timing cannot isolate version effects. Hosted comparison uses Temurin. Approved frontend upgrades are retained rather than repeated. npm/Cargo locks, artifact digests and notices remain required. All previously missing Rust crate license metadata is restored. AOP Alliance's upstream Public Domain declaration and the exact ANTLR runtime 3.2 source artifact's BSD notice resolve those metadata gaps; applicable notices/disclaimers must accompany redistribution. This is supply-chain evidence, not blanket legal clearance.

Xtext's patched generator SHA256 `35853e64321ed8aded0bf89b791db4af0a18b362c7c084fb8a46c78dca21f74e` still cannot be matched to verified patch/build sources. Xtext is excluded from production eligibility, despite passing bounded persistence/diagnostic/concurrency probes. The observed ANTLR3 classpath conflict is another operational cost: Xtext needs its Maven ANTLR3 runtime before ANTLR4's bundled classes. The ANTLR worker uses a minimal ANTLR4/Gson classpath and does not inherit Xtext's unresolved generator dependency. Existing clean Ubuntu network restoration is credible for surviving locked models; an empty-cache offline build is not claimed without an artifact bundle.

## Scoring and closure

Weights remain editor 25, performance 20, memory 15, integration 20, ergonomics 10, operations 10. Xtext earns no score after failing provenance. Surviving candidates pass the six gates at the stated experimental scope. Raw startup, warm latency, heap/RSS, byte sizes and direct/split calls are retained. Comparable editor/team ergonomics data remain incomplete, so an aggregate normalized score is **NOT COMPUTABLE**, not zero. No weighted runtime/frontend winner is published; both choices are deliberately deferred. Architecture acceptance is independent of that absent ranking.

**Phase 5 is CLOSED AND GREEN as an evidence evaluation with two justified ACCEPTED architecture decisions and two explicit DEFERRED implementation choices.** This does not authorize production implementation or Phase 6. Any later runtime/frontend commitment must retain these gates and complete the missing comparative decision evidence; it cannot rely on benchmark speed alone. [Gate register](../../experiments/phase5/results/gates.json) and [completion report](../phase5-completion-report.md) are authoritative for the bounded results.

## Historical investigation and approved evidence passes

The following records retain the earlier proposed/deferred findings. Their missing-work statements describe those passes; the independent decisions above supersede them.

### Initial production technology evaluation gate

Historical initial status: PROPOSED; **no parser or production implementation language selected**. Date: 2026-09-15; investigation carried forward 2026-09-16. Basis: charter §§23–25, 39–43 and the user's explicit evidence-before-selection instruction.

## Question and recommendation

Which production core runtime, language frontend, and source-analysis integration best preserve ACP semantics across independent compiler stages and years of evolution? Recommend delaying selection until the semantic corpus and stage contracts can drive the same representative experiments in each candidate. Core runtime and language tooling may differ; compare in-process and versioned process-boundary integration before deciding.

## Evidence available now

Primary documentation reviewed 2026-09-15; these are documented capabilities, **not ACP benchmark results**:

| Candidate | Documented capability | ACP inference / unresolved cost |
| --- | --- | --- |
| [ANTLR](https://www.antlr.org/) | Generates parsers and walkable parse trees from grammars | Suitable for syntax ingestion; ACP must still own semantic model, scope/validation, diagnostic integration, and editor behavior |
| [Langium workflow](https://langium.org/docs/learn/workflow/) | Grammar-derived AST, cross-reference resolution, validation workflow | Relevant semantic/editor integration candidate; measure adapter isolation so generated AST never becomes ACP Canonical IR |
| [Xtext language implementation](https://eclipse.dev/Xtext/documentation/303_runtime_concepts.html) | Provides language implementation services including linking/scoping, validation and generation integration | Relevant language-workbench candidate; measure runtime/model integration, deployment footprint and maintenance burden |
| [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) | Incremental syntax parsing for source tooling | Source syntax adapter candidate; syntax alone does not establish resolved calls/types or runtime enforcement |

At the original investigation baseline, the repository had no language/build precedent beyond reference tooling (ADR-0003), and no comparative parser/native-source experiments had run. That historical starting point did not establish production suitability. The Phase 5 evidence update below supersedes the absence-of-experiments statement; no candidate has earned a production selection score.

## Alternatives to investigate

- Frontends: ANTLR, Langium, Xtext; add a PEG-family option only with a specific corpus/tooling gap it could address. Structured input remains a supported adapter regardless of DSL choice.
- Core: evaluate a typed JVM option, TypeScript, and a systems-oriented option such as Rust against the same contracts. Python remains a possible candidate if evidence justifies it; the test harness confers no preference.
- Integration: same-process language services vs isolated frontend/analyzer workers with versioned messages. Do not require a frontend runtime to dictate the core runtime.
- Source intelligence: syntax adapter plus target-native semantic APIs, compared against native-only analysis where practical. Neither a single universal parser nor name matching is assumed sufficient.

These are investigation options, not technology recommendations or claims about current versions/performance.

## Required experiments before acceptance

For each candidate pin versions, license/dependency inventory, host/OS/toolchain, experiment source, corpus commit/digest, commands, cold/warm run counts, raw outputs, and failure cases. Use identical semantic inputs and verify equivalence before comparing speed.

| Criterion | Experiment and acceptance evidence |
| --- | --- |
| Meta-model fidelity (hard gate) | Encode typed money, exact IDs/refs, lifecycle, tenant scope, workflow, uncertainty, and provenance. Produce identical semantic results; no parser/framework type leakage |
| Independent compiler stages (hard gate) | Replace frontend and run kernel/core tests without it. Cancel/retry stages without shared mutable semantic state |
| Diagnostics/recovery (hard gate) | Broken syntax, incomplete editor input, dangling refs, mixed currencies, conflicting policies. Preserve semantic IDs and source spans; malformed input cannot enter production lowering |
| Deterministic generation (hard gate) | Repeated separate-process runs with varied input map/set order, locale, machine path and concurrency yield identical normalized IR/artifact manifests; all nondeterministic inputs explicit |
| Source intelligence (hard gate) | Analyze overloads, imports, aliases, inheritance, generated code, and human-owned extensions; demonstrate resolved-symbol capability or explicit unknown; retain provenance across rename |
| Editor/LSP usability | Cross-file references, rename continuity, completion and error recovery on representative 1k/10k/100k-node models; record edit latency and correctness |
| Performance/resource bounds | Repeated cold/warm full and incremental validation; latency distribution, peak memory, malformed input limits; define budgets from product needs before scoring |
| Evolution/maintenance (hard gate) | Upgrade one tool version, migrate old model fixtures, recreate build offline, isolate plugin crash, assess supported platforms/licensing/dependency maintenance and team skills |
| Integration cost | Measure adapter code, serialization overhead, test complexity, worker startup and debugging; compare same-runtime and split-runtime paths |

All hard gates must pass; performance cannot compensate for incorrect semantics or incomplete diagnostics. Record missing evidence as NOT_RUN. Decide tie-breaking weights and workload budgets before performance runs; review tradeoffs explicitly rather than retrofitting weights to a preferred tool.

## Consequences and blocked work

Production core language, DSL/editor framework, source analyzer stack, runtime colocation, and plugin ABI remain blocked on evidence. Contract/schema/corpus work is independent and continues. Accepting this ADR later requires raw experiment results, known limitations, maintenance plan, chosen versions, and a reasoned comparison across all seven concerns requested by the user. A documentation-only comparison cannot select a winner.

## Phase 5 evidence update — 2026-10-07

Status remains **PROPOSED; selection explicitly deferred on evidence**. The
[evaluation report](../phase5-completion-report.md), [reproduction commands](../../experiments/phase5/COMMANDS.md),
[gate register](../../experiments/phase5/results/gates.json) and
[descriptive measurements](../../experiments/phase5/results/comparison.md) record
the completed bounded experiment pass and the remaining unrun requirements.
Phases 1–4 remain CLOSED AND GREEN; Phase 5 is EXPLICITLY BLOCKED ON EVIDENCE;
Phase 6 is NOT STARTED. The structured frontend remains supported.

| Independent decision | Disposition | Evidence and reason |
| --- | --- | --- |
| Production compiler-core runtime | **DEFERRED**: Java 21, TypeScript 5.9.3/Node 24.21.0 and Rust 1.90.0 remain candidates | Typed graph/result/diagnostic/provenance/port/cancellation/budget slices execute; Java and Rust independently verify authoritative canonical vectors alongside the existing Node verifier. Full Phase 4 wire/worker conformance, serialization cost and TypeScript parallelism remain missing |
| Textual frontend framework | **DEFERRED**: ANTLR 4.13.2, Langium/CLI 4.4.0 and Xtext 2.44.0 remain candidates | All three generated ACP grammars lower both domains exactly, preserve semantic diagnostics and run unchanged Analyze/Normalize stages. Production textual Ingest, module visibility/cycles, related locations, safe label refactoring and incremental scale evidence remain incomplete |
| Frontend/core integration model | **DEFERRED**: same-process and versioned process boundaries remain open | Actual parsers export ordinary records; worker fault guard is tested. Candidate-native end-to-end versioned integration, authority state on retry/restart and comparable serialization/isolation measurements are not complete. No runtime dictates core colocation |
| Source-analysis approach | **DEFERRED**: syntax, native and combined adapters remain open | Tree-sitter web 0.25.10/wasm bundle 0.1.13 and TypeScript 5.9.3 native APIs demonstrate uncertainty-aware feasibility on the same source fixture. Ownership/rename continuity, additional native adapters and exact wasm grammar provenance remain missing |

No alternative is rejected on familiarity, popularity, LOC or exploratory speed.
The Langium default declaration-name rename **fails ACP stable-ID label-rename
safety**; this rejects that default behavior, not the framework before a custom
policy can be tested. ANTLR's adapter is not a complete LSP; Xtext's native API
coverage does not establish a production module or rename implementation. No PEG
candidate was added because no demonstrated requirement gap justified one.

Weights were committed before measurements: editor 25, performance 20, memory 15,
integration 20, ergonomics 10, operations 10. Required hard-gate evidence is still
UNKNOWN/NOT_RUN, so no weighted score or winner is published. Parse-only 100k-node
success does not establish semantic validation at that size. Reference limits and
canonical expected bytes/hashes are unchanged.

Exact runtime/package pins, generator digests, npm/Cargo locks and resolved JVM
dependencies/licenses are recorded in [versions](../../experiments/phase5/versions.json)
and [inventory](../../experiments/phase5/results/inventory.json). Offline cached
restoration and clean generated-output rebuilding passed; native source results
are identical across the controlled TypeScript 5.9.2 → 5.9.3 patch comparison.
Framework/toolchain upgrades, legacy textual migration, full transitive license
inheritance, release/support review and Maven transitive reproducibility remain
unresolved. The prototype Xtext numeric datatype is narrower than the accepted
safe-integer canonical profile; representative fixtures pass, but wider authoring
numeric coverage must be demonstrated before selection.

Maintain pins and corpus equivalence checks; upgrade one component at a time on
Linux with rollback evidence. ANTLR's BSD, Langium/Tree-sitter's MIT, Xtext's EPL,
TypeScript's Apache and Rust/dependency MIT/Apache terms, plus JVM distribution
obligations, require artifact-level deployment/redistribution review. Inherited
licenses and patched/prebuilt artifact provenance are explicitly unresolved;
top-level license names are not production clearance. No Linux host preference
changes ACP semantic or generated-target neutrality.

## Phase 5B independent dispositions — 2026-10-07

This update supersedes the first-pass missing-evidence inventory above. Status
remains **PROPOSED**. Consult the [current gate register](../../experiments/phase5/results/gates.json)
and [Phase 5B report](../phase5-completion-report.md). Required gates are evaluated
as PASS/FAIL/UNKNOWN/NOT_RUN; only PASS permits scoring. Weights remain exactly
25/20/15/20/10/10. No weighted ranking is computed.

| Independent production decision | Disposition | Current evidence / exact remaining reason |
| --- | --- | --- |
| Compiler-core runtime | **DEFERRED** | Java 21, TS 5.9.3/Node 24.21.0 and Rust 1.90.0 execute identical expanded representative wire fixtures with hashes, provenance, obligations, ports, budgets/cancellation and concurrent work. Full core-wire malformed/oversize failure transport and broader Phase 4 conformance are missing. |
| Textual DSL/frontend | **DEFERRED** | ANTLR 4.13.2, Langium 4.4.0 and Xtext 2.44.0 enter real Ingest→Elaborate, execute both domains, enforce common bounded modules and preserve IDs under custom label edits. Exact recovery/reference-token diagnostics, module diagnostic transport and comparable editor/maintenance closure remain incomplete. |
| Frontend/core integration | **DEFERRED** | Real frontends use one bounded exact-version protocol, with restart/retry and external authority. Persistent framing still invokes cold native parsers. No measured equivalent persistent-native versus same-process embedding comparison justifies colocation. |
| Source-analysis approach | **DEFERRED** | Native TS and javac semantic bindings demonstrate ownership/rename, aliases/imports/overloads/inheritance and unresolved calls in two ecosystems. Feasibility passes; production adapter coverage and maintenance/redistribution review remain open. The third-party prebuilt wasm grammar is **REJECTED FOR PRODUCTION** as a component, not selected through syntax-only evidence. |

No production choice is ACCEPTED, so there is no selected version or rejected
competing framework disguised as a recommendation. The Langium default ID-changing
rename remains a recorded failure; the ACP top-level label/ref-token adapter passes
without changing its generated AST architecture. All three controlled frontend
upgrades and legacy rejection are executable; previous Langium schema metadata
repair and rollback are recorded. Java/Node/Rust toolchain upgrades are NOT_RUN.

The transitive inventory records unresolved aopalliance 1.0 and antlr-runtime 3.2
POM license metadata and the patched Xtext generator's missing exact source/build
provenance. Cached offline Maven success does not prove independent clean-cache
restoration. These gaps prevent production maintenance clearance. Fallback is the
supported structured frontend and existing reference compiler; preserve pins,
upgrade one component at a time, require corpus/byte/failure gates and roll back
via the unchanged production experiment locks. No Phase 6 work is authorized.
