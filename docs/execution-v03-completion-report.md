# Explicit execution/dataflow semantic evolution — APPROVED AND GREEN semantic baseline

Historical Phase 1–5 remain CLOSED AND GREEN for their accepted bounded versions. This successor task does not reopen those technology/semantic decisions. Authoring 0.2.0, Canonical 0.1.0, historical schemas/vectors/reports and journals are preserved. Phase 6 remains IN PROGRESS. Phase 7 is NOT STARTED.

[ADR-0015](adr/0015-explicit-operation-effects-and-dataflow.md) is ACCEPTED by explicit human project-authority approval on 2026-10-08. The [inventory](execution-dataflow-inventory.md) precedes the successor model and covers all historical commands, use cases, queries, events, workflow effects, scheduled inputs and compensation bindings. The former target-sidecar proposal is rejected and historical only.

New Authoring 0.3 and Canonical 0.2 schemas, pure validation/reference execution, explicit revised domain fixtures, ChangeSet 0.2 upgrade and neutral compiler support were merged in the semantic baseline; the explicit human approval is recorded separately in this continuation. The [reference fixture business decisions](execution-v03-fixture-decisions.md) have AI proposal provenance. AI proposal origins remain unchanged. The human explicitly approved this proposal for ACP synthetic reference applications/corpora only, not production business requirements. [Fresh exact-content reference proofs](../test-corpus/execution-v03/human-approval.json) bind both new snapshot and ChangeSet plan digests; historical approval is not reused. Phase 6 target implementation is authorized to resume. The inventory also identifies bounded non-operation details (creation, pagination ordering, anonymization values, closure timestamps and infrastructure failure mappings) which this task does not infer or claim to execute. Full target admission remains a separate gate.

Local Linux evidence on 2026-10-08 uses CPython 3.14.4 and Node.js 24.21.0. The [machine-readable record](../test-corpus/execution-v03/validation-linux.json) records the exact results; local `/tmp` logs are ephemeral only.

| Gate | Result |
| --- | --- |
| Historical Authoring 0.2 / Canonical 0.1 | PRESERVED; 25 historical assets match checkpoint `fab36ed` |
| Authoring 0.3.0 validation | APPROVED AND GREEN: closed shapes, exact references, typed inputs/effects/results, required consumption and security boundaries |
| Canonical 0.2.0 validation | APPROVED AND GREEN: deterministic ordered effects/unordered mappings and separate vectors |
| ChangeSet 0.2 / history compatibility | GREEN: both domain upgrades, old/new lookup, revision continuity, semantic diff, new approval, rename and stale-base rejection |
| Neutral compiler compatibility | GREEN: both complete revised domains compile to synthetic records with explicit execution capability; historical vectors unchanged |
| Pre-approval baseline regression | PASS: 154 tests, 570.884 seconds |
| Approved continuation complete Python regression | PASS: 166 tests, 1,364.475 seconds; final focused lowering checks: 7 PASS, 18.872 seconds |
| Final reference-executor safeguards | PASS: 4 focused tests, 14.822 seconds, after the full run; detached snapshots, one aggregate-root instance per atomic transaction, typed tenants and both valid domain flows |
| Independent Node verification | PASS separately for historical and successor directories: each 9 positive, 13 negative and 2 snapshot hashes |
| New schema meta-validation | PASS for all three successor schemas |
| Stored source/change/plan/canonical reproduction | PASS independently for both revised domains |
| Dependency consistency / repository checks | PASS |
| ADR-0015 / reference fixture decisions | ACCEPTED / APPROVED REFERENCE SEMANTICS; explicit human approval, 2026-10-08 |
| Ubuntu CI | NOT RUN for this branch; workflow preserves Ubuntu 24.04, CPython 3.14.7 and Node 24.21.0 and adds independent successor-vector verification |

The table above preserves the semantic baseline validation evidence. This continuation adds executable fresh human-reference approval and accepted-history upgrade checks, plus Canonical 0.2 evolution and target tests. Updated results are recorded separately below; semantic approval does not establish target acceptance.

The reference execution algebra implements the single atomic STOP flows used by these fixtures. It rejects multi-commit and compensation execution before effects while retaining those explicit ADR-0008 contracts in the semantic model. It does not implement production authentication, persistence, privacy lifecycle, external delivery or a generated target. Assignment effects in this bounded version update existing root fields; child CRUD and relation mutation are not inferred.

Reproduce all current tests with `.venv/bin/python3.14 -m unittest discover -s tooling/tests -v`; verify both Node vector directories as shown in the README. The accepted [ADR-0015](adr/0015-explicit-operation-effects-and-dataflow.md) and [approved reference fixture decisions](execution-v03-fixture-decisions.md) authorize Phase 6 target work to resume. Their exact source, canonical and upgrade-plan digests are in the [manifest](../test-corpus/execution-v03/manifest.json). Human approval is supplied separately from test evidence. It does not close Phase 6, start Phase 7 or establish production readiness.

The complete continuation regression includes fresh exact-content human-reference approval through accepted history and the six-step Canonical 0.2 evolution sequence. Both independent Node vector directories passed unchanged again. The [Phase 6 continuation report](phase6-completion-report.md) records typed generated component tests and the separately BLOCKED complete negotiated target gate. The dedicated `phase6-target` CI job is configured to fail closed at that gate until the outstanding capabilities and semantic decisions are resolved; hosted CI has not been run for this worktree.
