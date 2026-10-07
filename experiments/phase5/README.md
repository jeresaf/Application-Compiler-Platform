# Phase 5 technology experiments — not production compiler code

ADR-0004 governs this investigation. `protocol.json` preregisters hard gates,
soft weights, workload seed/run counts and laptop worker budgets before benchmark
results. The existing semantic model, canonical vectors and Phase 4 interfaces
remain authoritative. No PEG candidate is justified yet.

The experiment language is deliberately an inspectable semantic declaration
notation, not the finished ACP language. It exposes stable IDs/revisions, lifecycle,
labels, provenance/basis and schema-backed typed records. It has explicit Money and
exact-reference literals. It must lower to ordinary frontend-independent authoring
records before existing Analyze/Normalize passes. Its verbosity is an experiment
limitation, not a decision that final ACP syntax should mirror JSON.

Heavy dependency builds and benchmark workers run sequentially on the 16 GB laptop.
Dependencies/build caches stay ignored and local to this area. Raw results record
failed/unrun workloads explicitly. Missing evidence blocks selection; it never
creates a performance win. The eventual report distinguishes exercised prototypes
from missing editor/maintenance/scale evidence.


Phase 5 is **EXPLICITLY BLOCKED ON EVIDENCE**, with no production selection.
See [reproduction commands](COMMANDS.md), [machine-readable gates](results/gates.json),
[raw/derived measurements](results/comparison.md), and the
[evaluation report](../../docs/phase5-completion-report.md).

Phase 5B now invokes every actual parser inside Phase 4 Ingest, then Elaborate;
framework objects stop at strict immutable Document boundaries. The common module
and visibility policy is deliberately bounded experiment logic. Shared lexical
label edits preserve stable IDs and update qualified references across files.

See [Phase 5B raw evidence](results/phase5b/), [current gates](results/gates.json)
and [commands](COMMANDS.md). Persistent Python framing workers currently start a
cold native parser per request; do not describe those timings as warm native
workers. Native builder/resource updates are separate from full ACP semantic
validation. Full 10k/100k semantics remain NOT_SUPPORTED under existing limits.

Four production decisions remain independently DEFERRED. The unprovenanced
third-party Tree-sitter wasm is explicitly rejected for production; syntax-only
analysis never counts as resolved semantic evidence. No Phase 6 work is included.
