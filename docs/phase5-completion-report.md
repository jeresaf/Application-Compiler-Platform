# Phase 5 — technology evaluation evidence and explicit deferral

Status: **EXPLICITLY BLOCKED ON EVIDENCE; NOT CLOSED AND GREEN**.
Phases 1–4 remain CLOSED AND GREEN. Phase 6 is NOT STARTED. No production
compiler runtime, textual frontend, integration model or source analyzer is selected.

## Investigation boundary

ADR-0004 governs this work. The [preregistered protocol](../experiments/phase5/protocol.json)
was committed as `af10065` before measurements, against Phase 4 baseline
`cfa9a8b64ab23b6432f5c4593bca93706a98f455`. Hard gates cannot be offset by speed.
Soft weights are editor 25, performance 20, memory 15, integration 20,
ergonomics 10 and operations 10. **No weighted ranking is awarded** while required
evidence is missing. No concrete gap justified a PEG candidate. Python remains
the reference harness, not a preferred production candidate.

All implementation is under [experiments/phase5](../experiments/phase5/README.md).
The existing structured frontend and semantic/compiler contracts remain supported
and unchanged. The textual declaration language is deliberately experimental:
explicit stable identity/revision headers, exact-reference literals, Money literals
and schema-backed record bodies. It is not the final ACP language.

The payment and case-management fixtures cover Entity, Field, ValueObject,
Relation/cardinality, Money, requirements/decisions, actors/roles/permissions/scopes/
policies, commands/queries/use cases, states/transitions, invariants, task UI,
quality/test obligations, lifecycle and provenance. Original semantic origins stay
in the canonical model; physical DSL spans are a separate source-map sidecar.
No development-host concept enters canonical identity or generated-target semantics.

## Reproducible artifacts

- [Commands](../experiments/phase5/COMMANDS.md), deterministic generator and exact
  source fixtures, three grammars, handwritten adapters and typed core slices.
- [Version/license manifest](../experiments/phase5/versions.json), npm/Cargo locks,
  [resolved dependency/digest and LOC inventory](../experiments/phase5/results/inventory.json).
- [Machine metadata](../experiments/phase5/results/machine.json), raw results and
  [descriptive comparison](../experiments/phase5/results/comparison.md).
- [ANTLR](../experiments/phase5/results/antlr.json),
  [Langium](../experiments/phase5/results/langium.json) and
  [Xtext](../experiments/phase5/results/xtext.json) parse/fidelity/recovery/scale evidence.
- Frontend semantic/stage/determinism evidence:
  [ANTLR](../experiments/phase5/results/antlr-behavior.json),
  [Langium](../experiments/phase5/results/langium-behavior.json),
  [Xtext](../experiments/phase5/results/xtext-behavior.json).
- [Core graph probes](../experiments/phase5/results/core-runtime.json),
  [canonical interoperability](../experiments/phase5/results/canonical-interop.json),
  [source analysis](../experiments/phase5/results/source-analysis.json),
  [maintenance probes](../experiments/phase5/results/maintenance.json).

Evaluated candidates: ANTLR 4.13.2, Langium/CLI 4.4.0, Xtext 2.44.0;
Java 21, TypeScript 5.9.3/Node 24.21.0, Rust 1.90.0;
Tree-sitter web binding 0.25.10 with wasm bundle 0.1.13 and the TypeScript 5.9.3
native API. Local CPython is 3.14.4; official Ubuntu 24.04 CI pins 3.14.7.
The exact laptop hardware and runtime output are recorded, not inferred from a
marketing model name. Local generated-output rebuilds and hosted clean-runner
builds are distinct evidence.

## Recorded findings and hard gates

| Gate | Demonstrated evidence | Remaining evidence blocking selection |
| --- | --- | --- |
| Semantic fidelity | All three parse both complete reference domains into exactly equal ordinary JSON records; synthetic fixture approvals applied equally; unchanged Analyze and Normalize pass with physical source maps; canonical semantics equal | Finish production textual Ingest design: Phase 4 Ingest deliberately accepts structured authoring only; current text adaptation precedes that boundary. Broader syntax evolution and number-range coverage needed |
| Stage isolation | No parser objects enter SemanticAST/Canonical IR; structured adapter remains independent; versioned worker guard tests crash, timeout, malformed/version/size/cancellation cases | Guard is experimental Python infrastructure, not a selected plugin ABI; wire each real frontend/core pairing through it and test cancellation during active stages and restart/retry authority state |
| Diagnostic correctness | Malformed/incomplete/missing-close source produces errors and no production model; eight semantic cases preserve deterministic diagnostics, IDs and parsed declaration spans; conflicting identity bodies rejected | Full related-location projection, policy conflict combinations and all required editor recovery scenarios; safe rename and import/module visibility remain incomplete |
| Determinism | Three independent processes per candidate vary declaration/map order, locale, temporary directories, hash seed and irrelevant environment, preserving canonical meaning; unchanged cross-runtime byte vectors pass | Working-directory and actual concurrent frontend/core variation, ordered-meaning perturbations at the textual boundary and broader worker/retry permutations are NOT_RUN |
| Source-intelligence viability | Actual syntax-only, native and combined APIs exercise imports/alias/overload/interface, generated and human-owned code, unresolved calls; KNOWN/UNKNOWN/UNRESOLVED/ABSENT distinguished | One TypeScript corpus establishes feasibility only; source ownership/rename continuity and Java/Rust native source adapters remain untested; wasm grammar provenance needs review |
| Evolution/maintenance viability | Exact candidate versions, npm/Cargo locks, major resolved JVM dependencies, digest-pinned generators; offline cached restoration and fresh generated-output builds; TypeScript 5.9.2 → 5.9.3 native API comparison | Framework/toolchain upgrades for ANTLR/Langium/Xtext/Java/Rust, older-language fixture migration and full transitive licensing/support/deployment review remain incomplete; Maven transitive reproducibility not proven |

The eight semantic probes cover duplicate identities, dangling references, stale
revisions, mixed currencies, wrong Money values, invalid terminal transitions,
ambiguous transitions and blocking conflict. They reproduce existing portable
negative cases; they do not redefine accepted semantics. Draft parser success
on a semantically invalid model never counts as production compilation success.

Actual editor evidence is in [ANTLR's custom adapter](../experiments/phase5/results/antlr-editor.json),
[Langium's native workspace](../experiments/phase5/results/langium-editor.json) and
[Xtext's native API probe](../experiments/phase5/results/xtext-editor.json).
Langium demonstrates native completion, definition, cross-file references, rename
edits and invalidation after deleting a module. Its default declaration rename
changes the stable ID: **FAIL for ACP label-rename safety**, not a reason to reject
the whole framework before an ACP-specific implementation is measured. ANTLR's
custom index provides completion/navigation/reference lookup and label-only rename,
but is not a complete LSP and lacks reference-token spans. Xtext's native results
must be read at their recorded scope; no unexercised LSP feature earns points.
None implements the required import visibility/cyclic-module policy yet.

Scale experiments use deterministic 1k, 10k and 100k declarations, three cold
processes and five warm parses after discarding one initial parse. Raw process
elapsed time, parser time and peak RSS are separate. Nearest-rank p95 with these
small samples is the maximum observation, not a stable latency guarantee.
The 768 MiB managed-heap cap and 90-second timeout are enforced; the 1 GiB total
RSS budget is observed, not an OS-enforced container limit. The machine is an
ordinary laptop, not an isolated performance laboratory. Final serial reruns
replace pilot measurements taken while some dependency builds overlapped.

Large scale fixtures intentionally omit required semantic fields: they measure
parsing only. Full validation, incremental edits and rename/reference updates at
those sizes remain NOT_SUPPORTED or NOT_RUN as recorded. Existing 1 MiB/2000-node
reference bounds were not increased. Both real domains separately measure
semantic validation. Timings cannot be combined into an overall performance rank.

The three typed core slices exercise immutable subject/result/diagnostic contracts,
provenance locators, injected graph ports, bounded graph traversal and cancellation.
Java virtual-thread and Rust thread correctness probes run eight jobs; TypeScript
parallelism is NOT_RUN. The graph benchmark is separate from frontend cold/warm
parsing. Full Phase 4 contract/wire conformance, real worker integration and
serialization-cost comparisons are incomplete. No language is selected from this
small slice. Java and Rust independently pass the authoritative nine positive and
thirteen negative byte vectors plus both snapshot hashes; the existing Node
verifier still passes. No expected byte/hash vector changed.

Source-only Tree-sitter reports both calls UNKNOWN. Native TypeScript resolves the
aliased Payment overload as KNOWN and the missing function as UNRESOLVED. Combined
analysis correlates exact spans. ABSENT refers only to decorator syntax absent from
these complete fixtures, not absence of a runtime behavior. Semantic certainty is
never inferred from matching syntax alone.

## Deferrals and next evidence

ADR-0004 remains PROPOSED. All four technology decisions are **deferred separately**:
production core, textual frontend, integration model and source-analysis approach.
Neither same-process colocation nor a versioned worker is selected by architectural
preference. No candidate is rejected solely on exploratory timings, LOC or existing
reference-language familiarity.

To unblock, implement/test module visibility and cycles, stable-label source rename
and related diagnostic locations across the three candidates; measure incremental
validation/rename at scale; complete core worker/serialization/concurrency and
ordered-meaning/environment checks; exercise controlled framework/toolchain
upgrades and legacy language migration; complete transitive licensing/provenance
and support review. Reapply the preregistered hard gates before assigning scores.
The maintenance strategy is to keep exact pins, verified generator digests,
dependency locks/inventories and corpus equivalence checks, then upgrade one
component at a time on Linux. EPL, BSD, MIT/Apache and JVM deployment obligations
need artifact-level review before production packaging; manifest labels do not
constitute a redistribution clearance.

## Validation record

Local Linux validation: **92 existing regression tests PASS** in 277.696 seconds;
**3 experiment guard tests PASS**; all-candidate smoke gates PASS; Java/Rust/Node
canonical interoperability PASS; repository checks and dependency consistency PASS.
The [validation record](../experiments/phase5/results/validation.json) preserves
local output, CI metadata and source digests. [Ubuntu CI run 37618487121](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/37618487121)
is GREEN for both contract and experiment jobs on source commit `7b4032c`.
The final evidence commit also runs the workflow; its result is checked before
handoff. Official Python/Node pins remain 3.14.7 / 24.21.0; Java setup resolves
Temurin 21.0.0 (21+35). Historical Phase 1–4 reports retain their original evidence.
This report is an explicit evidence-blocked evaluation, not an assertion that all
Phase 5 exit criteria passed.


## Implementation and operational observations

The inventory records handwritten adapter/core lines separately from generated
Java volume; maintenance results record build durations. These quantify effort,
not product quality. Reproduction requires a Java/Maven parser-generator toolchain,
Node/npm for Langium and native TypeScript APIs, and Rust/Cargo for the systems
probe. Same-process deployment and versioned worker serialization cost remain
unmeasured rather than receiving an inferred integration score.

Concrete integration defects found and corrected: Gson's default omitted explicit
null values from the case-management fixture; generated Langium rules required
avoiding reserved JavaScript runtime names; Xtext required its generated grammar
resources, mixed IDE bindings and an injected native completion acceptor. The
initial hosted Java build selector was unsupported and was corrected to its exact
release selector. These are measured implementation experiences, not architectural
arguments for a preferred ecosystem. The narrow Xtext experiment integer datatype
and incomplete module/rename policies remain explicit limitations.
