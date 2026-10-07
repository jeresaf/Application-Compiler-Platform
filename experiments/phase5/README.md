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
