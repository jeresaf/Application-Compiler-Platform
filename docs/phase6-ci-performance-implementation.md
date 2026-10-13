# Authorized CI scheduling implementation

The authorization baseline is `0057b008bd8fa5519b3b625c89fb262f53f6f844`.
The explicit user CI-only implementation request has byte digest
`sha256:1c899b302ce6104bed0c8860605e3595b588d94bec9a3ad124ec0337fa69aaa4`; this documentary binding issues no authority proof.
The original five jobs retain every existing step, command, version and artifact
collection path. `engineering/ci/parity.py` checks complete original job bodies,
allowing only the closure dependency removal, distinct ephemeral PostgreSQL
passwords, and additive CI tests/source bindings. No tests move between jobs.
The Route A preservation test invokes this stricter parity check for the
explicitly authorized workflow exception; all other protected bytes stay checked.

`phase6-target` and `phase6-closure-audit` run concurrently after contracts and
Phase 5C. Inspection of `tooling/audit/phase6.py` shows that the audit invokes its
own full admission under `/tmp/acp-phase6-final-audit/admission`; it never consumes
`/tmp/acp-phase6-target`. Both generate and test both approved applications afresh.
Separate GitHub-hosted runners provide separate workspaces, temporary files,
locks, service containers, PostgreSQL instances/schemas, build directories and
evidence. Distinct ephemeral passwords prevent credential reuse and retain the existing
package scanner’s forbidden test-credential marker. Neither job
uses admission resume, prior verdicts, cached proofs or accepted receipts.
Duplicate full generation remains deliberately preserved; this optimization
removes scheduling serialization, not verification work.

The final job uses `always()` and directly depends on all five required jobs.
It compares `needs` with the authenticated GitHub job API for the exact attempt,
checks each job's checkout/source/run/attempt binding, downloads every original
required artifact, verifies GitHub SHA-256 archive digests and ZIP CRCs, and
checks the performed exact-source closure report. Failed, skipped, cancelled,
missing, malformed, stale or wrong-source evidence fails closed. Exit 2 remains
failure. Engineering validation and release closure are reported separately.
The final job cannot override an upstream failure. Its upload explicitly enables
hidden files for the dedicated `.ci-evidence` directory; only generated CI
observations are written there, and authentication tokens are never persisted. Cancellation of the entire
workflow can stop even `always()` jobs; it never yields release success.
Configure branch protection to require `final-ci-aggregate` as well as existing
required checks; repository protection changes are outside this implementation.

The current 21 blockers are preserved. A06-06, A14-06 and A17-16 remain INCOMPLETE;
A09-08 remains BLOCKED. T09 remains HUMAN_DECISION_RECORDED with
ACCEPT_DELIVERABLES_WITH_RESERVATIONS. Operational security is not established.
Phase 6 is IN_PROGRESS; Phase 7 is NOT_STARTED.

## Developer feedback

Run with the existing isolated Python environments and pinned dependencies:

```sh
python3.14 engineering/ci/focused.py integrity
python3.14 engineering/ci/focused.py route-a
python3.14 engineering/ci/focused.py compiler
python3.14 engineering/ci/focused.py modules tooling.tests.test_closure_evaluator
python3.14 engineering/ci/focused.py full-local
```

All commands print `FOCUSED_CHECKS_ONLY`, including full local verification:
local success does not establish hosted browser/PostgreSQL admission or release
closure. The full push/PR workflow remains mandatory. The contracts suite skips
the opt-in PostgreSQL migration method when its database variable is absent;
the existing closure audit executes it against disposable PostgreSQL. This is
existing regression coverage, not a standalone T08 grant or application migration.

## Measurement and review

Use `python3.14 engineering/ci/measure.py BASELINE_API_DIRECTORY OPTIMIZED_API_DIRECTORY`
with completed `ci-run.json` and `ci-jobs.json` API observations to calculate
wall-time savings, DAG critical-path duration (excluding queue gaps), runner-time
changes and explicitly listed setup overhead.
The final artifact records raw job/step timestamps, exact artifact IDs/digests,
source, run attempt, unittest summaries found in retained logs and closure
blockers. Summaries may overlap across suites; do not sum them as unique tests.
JUnit/browser inventories remain in the original artifacts. Compare the complete
baseline and optimized run timestamps for wall time, sum job durations for runner
minutes, and report setup-step durations separately. Report real hosted results
directly after completion, without another evidence-only commit. A blocked
closure is expected to leave the workflow failed even if engineering passes.
The 50–55 minute target is aspirational until measured; parallelism can increase
runner usage and queueing. No cache or reduced test inventory is introduced.

Independent engineering review is requested for the scheduling independence,
exact command/artifact parity, authorized preservation-test exception, aggregation
failure matrix, source/attempt bindings and completed hosted measurements.
This checkpoint requests no operational authority or closure approval.
