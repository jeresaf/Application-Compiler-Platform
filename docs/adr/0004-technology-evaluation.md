# ADR-0004: Production technology evaluation gate

Status: PROPOSED; **no parser or production implementation language selected**. Date: 2026-09-15; investigation carried forward 2026-09-16. Basis: charter §§23–25, 39–43 and the user's explicit evidence-before-selection instruction.

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

The repository initially had no language/build precedent. CPython 3.14.7 and pinned JSON Schema tooling now run the Phase 1 corpus only (ADR-0003). That evidence does not establish production suitability. No parser benchmark, native-source experiment, or long-term dependency study has run. None of these candidates has earned a selection score.

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
