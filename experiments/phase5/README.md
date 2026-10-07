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

Heavy builds run sequentially on the 16 GB laptop. Phase 5C explicitly authorizes at most two independent native workers for final concurrency evidence.
Dependencies/build caches stay ignored and local to this area. Raw results record
failed/unrun workloads explicitly. Missing evidence blocks selection; it never
creates a performance win. The eventual report distinguishes exercised prototypes
from missing editor/maintenance/scale evidence.


Phase 5 is **CLOSED AND GREEN at bounded evaluation scope**. Worker integration and source-analysis architectures are ACCEPTED; core runtime/frontend remain DEFERRED. Xtext production use is REJECTED on exact patched-generator provenance.
See [reproduction commands](COMMANDS.md), [machine-readable gates](results/gates.json),
[raw/derived measurements](results/comparison.md), and the
[evaluation report](../../docs/phase5-completion-report.md).

Historical Phase 5B invokes every actual parser inside Phase 4 Ingest, then Elaborate;
framework objects stop at strict immutable Document boundaries. The common module
and visibility policy is deliberately bounded experiment logic. Shared lexical
label edits preserve stable IDs and update qualified references across files.

See [Phase 5B raw evidence](results/phase5b/), [current gates](results/gates.json)
and [commands](COMMANDS.md). Historical Phase 5B Python framing workers start a cold native parser per request; those timings are not warm native workers. Phase 5C implements true persistent native parsers in `native/NativeWorker.java` and `langium/native-worker.mjs`, connected through `native_frontend.py`. Native builder/resource updates are separate from full ACP semantic
validation. Full 10k/100k semantics remain NOT_SUPPORTED under existing limits.

Four production decisions remain independently DEFERRED. The unprovenanced
third-party Tree-sitter wasm is explicitly rejected for production; syntax-only
analysis never counts as resolved semantic evidence. No Phase 6 work is included.

Phase 5C raw evidence is in [results/phase5c](results/phase5c/). `run5c.py` checks native failures/concurrency and real compiler diagnostics; `fault5c.py` checks Java/TS/Rust failure parity; `measure5c.py` records persistent/direct/split calls; `maintenance5c.py` checks upgrades and provenance disposition; `check5c.py` verifies evidence without promoting missing data to PASS. Phase 6 is NOT STARTED.
