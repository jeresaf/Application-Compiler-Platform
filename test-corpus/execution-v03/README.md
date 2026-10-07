# Authoring 0.3 / Canonical 0.2 reference fixtures

These are explicitly proposed test decisions with AI proposal provenance, requiring human review. Structural APPROVED markers and synthetic allowlists are never real business approval. Historical fixtures and reports remain unchanged.

Each domain has separate authoring, canonical, ChangeSet 0.2 and plan files. The explicit change revises command/use-case/step/query/transition/job meanings and introduces typed operation input/result members, a resource-identity input and its UI/a11y obligations. Dependency revision closure preserves exact references. No migration inference supplies any assignment.

See the [proposed fixture decisions](../../docs/execution-v03-fixture-decisions.md), [ADR-0015](../../docs/adr/0015-explicit-operation-effects-and-dataflow.md), the [inventory](../../docs/execution-dataflow-inventory.md) and [report](../../docs/execution-v03-completion-report.md). Regenerate only this new directory with `python3.14 tooling/execution_fixtures.py` after reviewing fixture-source changes. Verify independent bytes with `node tooling/check_canonical_vectors.mjs test-corpus/execution-v03`; historical Node checks run separately.
