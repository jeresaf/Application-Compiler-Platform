# Explicit execution/dataflow semantic evolution — local validation GREEN, review pending

Historical Phase 1–5 remain CLOSED AND GREEN for their accepted bounded versions. This successor task does not reopen those technology/semantic decisions. Authoring 0.2.0, Canonical 0.1.0, historical schemas/vectors/reports and journals are preserved. Phase 6 remains IN PROGRESS. Phase 7 is NOT STARTED.

[ADR-0015](adr/0015-explicit-operation-effects-and-dataflow.md) is proposed for human review. The [inventory](execution-dataflow-inventory.md) precedes the successor model and covers all historical commands, use cases, queries, events, workflow effects, scheduled inputs and compensation bindings. The former target-sidecar proposal is rejected and historical only.

New Authoring 0.3 and Canonical 0.2 schemas, pure validation/reference execution, explicit revised domain fixtures, ChangeSet 0.2 upgrade and neutral compiler support are implemented on `codex/semantic-execution-v03`. The [reference fixture business decisions](execution-v03-fixture-decisions.md) have AI proposal provenance. Synthetic exact-content authority tests cannot substitute for the user's review or real human-authored application approval. No target capability implementation was resumed. The inventory also identifies bounded non-operation details (creation, pagination ordering, anonymization values, closure timestamps and infrastructure failure mappings) which this task does not infer or claim to execute. Full target admission remains a separate gate.

Local Linux evidence on 2026-10-08 uses CPython 3.14.4 and Node.js 24.21.0. The [machine-readable record](../test-corpus/execution-v03/validation-linux.json) records the exact results; local `/tmp` logs are ephemeral only.

| Gate | Result |
| --- | --- |
| Historical Authoring 0.2 / Canonical 0.1 | PRESERVED; 25 historical assets match checkpoint `fab36ed` |
| Authoring 0.3 validation | GREEN: closed shapes, exact references, typed inputs/effects/results, required consumption and security boundaries |
| Canonical 0.2 validation | GREEN: deterministic ordered effects/unordered mappings and separate vectors |
| Change/history compatibility | GREEN: both domain upgrades, old/new lookup, revision continuity, semantic diff, new approval, rename and stale-base rejection |
| Neutral compiler compatibility | GREEN: both complete revised domains compile to synthetic records with explicit execution capability; historical vectors unchanged |
| Complete Python regression run | PASS: 154 tests, 570.884 seconds |
| Final reference-executor safeguards | PASS: 4 focused tests, 14.822 seconds, after the full run; detached snapshots, one aggregate-root instance per atomic transaction, typed tenants and both valid domain flows |
| Independent Node verification | PASS separately for historical and successor directories: each 9 positive, 13 negative and 2 snapshot hashes |
| New schema meta-validation | PASS for all three successor schemas |
| Stored source/change/plan/canonical reproduction | PASS independently for both revised domains |
| Dependency consistency / repository checks | PASS |
| New business-meaning approval | REQUIRES HUMAN REVIEW; no inherited or real approval is claimed |
| Ubuntu CI | NOT RUN for this branch; workflow preserves Ubuntu 24.04, CPython 3.14.7 and Node 24.21.0 and adds independent successor-vector verification |

The current successor module contains 29 contract/reference tests. The full run included 27; the final focused run adds coverage for the two final defensive boundaries and rechecks valid flows and invalid tenant values. This is composed local evidence, not a claim that a hosted job or generated application ran.

The reference execution algebra implements the single atomic STOP flows used by these fixtures. It rejects multi-commit and compensation execution before effects while retaining those explicit ADR-0008 contracts in the semantic model. It does not implement production authentication, persistence, privacy lifecycle, external delivery or a generated target. Assignment effects in this bounded version update existing root fields; child CRUD and relation mutation are not inferred.

Reproduce all current tests with `.venv/bin/python3.14 -m unittest discover -s tooling/tests -v`; verify both Node vector directories as shown in the README. Review [ADR-0015](adr/0015-explicit-operation-effects-and-dataflow.md) and the [explicit fixture decisions](execution-v03-fixture-decisions.md) before target work resumes. Their exact source, canonical and upgrade-plan digests are in the [manifest](../test-corpus/execution-v03/manifest.json). No semantic approval, Phase 6 closure, Phase 7 start or production-readiness claim follows from these tests.
