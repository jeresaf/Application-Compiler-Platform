# Phase 4 synthetic compiler corpus

`vectors.json` pins compiler artifact-plan digests for the complete payment and
case-management semantic fixtures. They use the explicit host test approval
allowlist and neutral architecture/design fixtures; no approval or production
readiness is inferred from a vector. Target: `acp-synthetic-test-target/0.1.0`.
These are test records, not generated applications or Phase 6 output.

The independent Node checker still verifies the **unchanged** Phase 2 canonical
bytes/hashes. Phase 4 object hashes use a separate compiler domain and the same
accepted byte codec. No duplicate semantic/canonical algorithm is added.

[Compiler tests](../../tooling/tests/test_compiler.py) execute both complete domains,
independent stage failures, declared versions/ports/dependencies, cancellation and
resource budgets, immutable inputs, deterministic diagnostics, approval and
blocking issue rejection, provenance/rename continuity, capability mismatch,
obligation preservation, source-map sidecars, unsafe path/ownership/race rejection,
Phase 3 impact/incremental cache reuse and cache poisoning rejection. Small fixtures
live in [compiler_fixtures.py](../../tooling/compiler_fixtures.py); they are not
new authoring kinds. Separate Python processes compare complete small artifact-plan
bytes under C/C.UTF-8 locales, distinct working/temp directories, hash seeds,
irrelevant environment variables and reversed structured discovery order.

Run `.venv/bin/python3.14 -m unittest discover -s tooling/tests -p test_compiler.py -v`.
Regenerate only these new vectors with
`.venv/bin/python3.14 tooling/compiler_fixtures.py`, then review the diff. Never
change canonical snapshots/vectors merely to accommodate compiler output changes.
See the [execution contract](../../docs/compiler-core.md) for exact limits.
