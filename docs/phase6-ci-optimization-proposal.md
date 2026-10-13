# Phase 6 CI optimization proposal

Status: **PROPOSAL ONLY — NO WORKFLOW CHANGE AUTHORIZED OR IMPLEMENTED**.
T09 grants no CI, sealed-contract or operational change. Full hosted release verification
remains mandatory. Batch this decision with the next authorized substantive checkpoint;
do not create evidence-only push chains.

## Critical path and proposed parallel execution

The reported 77-minute path is consistent with retained run 38365033881:
74m36s elapsed, including contracts 17m30s and Phase 5 experiments 14m05s in parallel,
Phase 5C hard-gates 19s, target 33m40s, then closure audit 22m56s. These are one run's
measurements, not a performance guarantee. Source evidence:
`proposals/phase6-route-a-implementation-review/security-remediation/governance-finalization/hosted/38365033881/ci-run.json`
and `ci-jobs.json` at `6bca893f9207a68173c64e969104d93173eb5fb5`.

| Proposed change, requiring separate authorization | Safety conditions and expected effect |
|---|---|
| Run unchanged target and unchanged full closure-audit producers concurrently after the engineering prerequisites; add a final required collector. | Separate runners, PostgreSQL services, ports, directories and credentials. Confirm neither producer consumes the other's mutable outputs. Collector waits for every required engineering result and the audit, verifies exact source/artifact bindings, and fails closed. This removes their serial dependency without removing work. On this sample, roughly 51–52 minutes is an illustrative lower-overhead path instead of 75–77; measure contention/cost before promising savings. |
| Split Python regressions, Route A tests and independent Node vectors/repository checks into parallel jobs, preserving an aggregate required contracts check. | Every current test and vector stays assigned and required. Preserve source/history checkout depth and pinned environments. Do not change optional-test authorization or infer PASS from a skip. Measure setup overhead and exact test inventory parity. |
| Review Phase 5C's dependency on contracts. | Its current command consumes Phase 5C artifacts. If dependency analysis confirms contracts is only an ordering barrier, allow earlier artifact verification while keeping contracts required at final aggregation. No job may be bypassed because another finished first. |

Compare old/new schedules on equivalent inputs: test inventories, reports, hashes,
artifact identities and failure propagation. Never parallelize mutating scripts against
the same database or generated project.

## Duplicate generation and test work

The target job generates/builds full admission, while the closure audit calls
`tooling/audit/admission.py` again and repeats supplemental browser work. Compiler
discovery also overlaps explicitly selected target/audit regression modules.

- Cache verified dependency downloads by lockfiles, toolchain, OS and architecture.
  Never cache an old PASS, approval, witness, advisory date or closure result as fresh evidence.
- Inventory repetitions by command, inputs, environment and purpose. Identical names
  can exercise different failure states; retain those independent executions.
- Share fresh immutable builds only where unchanged admission/evaluator contracts permit.
  Bind source, Canonical/ChangeSet/approval inputs, bundle, toolchain, producer, logs and
  artifact hashes. Preserve clean-build, regeneration, determinism and upgrade tests.
- Audit `--resume` is constrained reuse, not a general cross-job cache. Do not inject
  arbitrary target output or relabel old execution. If safe reuse is unsupported, retain
  fresh generation and use parallelism. No sealed 0.5.0 producer or contract is altered.

## Existing T08 execution discrepancy

The contracts job skipped the opt-in PostgreSQL method, but the closure audit invokes
`tooling.tests.test_canonical03_migrations` with a PostgreSQL environment. Its retained
`remediation-regressions.log` in run 38365033881 reports
`test_real_postgresql_storage_presence_required_and_rollback ... ok`; the command exited 0.
Log SHA-256:
`b4cc82bcc0ba23e9ded5d2c72100018cabaef0299ad4310406d4a8796b120523`, bound by the committed
complete closure report. Archive SHA-256:
`ab3b94bfbe1794a65c84e237a81ea57855b2301352c941db535f1524317ead27`.
Both hashes were verified locally against the retained report and archive bytes.

Prior global NOT_EXECUTED statements were incorrect. This task runs no test; T09 grants
no T08 execution or retroactive authorization. A17-16 remains INCOMPLETE. Separately
reconcile execution provenance and authorization before any status/schedule change.

## Focused feedback and release gates

Offer additive local or separately authorized fast checks: repository integrity, canonical
vectors, pure contracts and affected modules. Label them FOCUSED_CHECKS_ONLY, never release
admission. Keep current full hosted triggers unchanged until separately authorized.

The final required gate must retain Ubuntu 24.04, CPython 3.14.7, Node.js 24.21.0,
dependency consistency, repository checks, complete existing regression coverage,
independent canonical bytes/hashes, both original applications' full admission,
history/security/upgrade checks and the performed closure audit. Missing, skipped where
execution is required, stale, wrong-source or failed evidence fails closed. Do not use
continue-on-error or success-only aggregation to hide exit 2: PHASE6_CLOSURE_BLOCKED
remains a failing release gate with all 21 blockers. T09 is not an operational PASS.

Require separate CI-only authorization and independent review of parity, freshness,
isolation and failure paths before implementation. Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.
