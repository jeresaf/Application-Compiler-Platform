# Phase 6 accepted-history deployed evolution: review plan

Status: PREPARED, NOT EXECUTED. Phase 6 IN PROGRESS; Phase 7 NOT STARTED.
Reviewed checkpoint: `80e19a6282c481c616f370e2876d3099eead0a2e`.
Target/generator 0.5.0 is an accepted incomplete engineering checkpoint, not closure.
Canonical 0.3 semantics and the sealed release remain unchanged.

## Exact hosted observation

The new [machine observation](../targets/spring-vue-postgres/evidence/phase6-checkpoint-hosted-38093244628.json)
binds [run 38093244628](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/38093244628)
to the reviewed commit, all five jobs and steps, uploaded artifact identities and digests,
closure criteria and blockers, full admission, and retained-data upgrade reports.
All four ordinary jobs succeeded. The closure audit was PERFORMED, exited 2,
and returned PHASE6_CLOSURE_BLOCKED with 21 blockers. This run is not green overall.
Both approved Canonical 0.3 applications retain full admission.

The closure archive SHA-256 is
`afcddb6b5930ab5efe2b89e6ad980c298680df93d8adfb68cff2ecab4f666c61`;
the target archive SHA-256 is
`b37039a70f423f310b21a5048e66e92d0bb6954976dd091316a11d33180bf78f`.
Both downloaded archives match hosted metadata. Phase 5 artifacts are metadata-observed,
not independently downloaded in this review. Raw archives/logs are retained locally under
`.audit-artifacts/phase6-evolution-review-38093244628/`; `/tmp` copies are ephemeral.
Hosted expiration is recorded in the observation. Preserve durable copies before expiration.
Earlier hosted observations and the first blocked closure report are immutable historical evidence.

The exact sealed 0.5.0 generator bundle is
`ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb`.
Do not add capabilities by editing this release. Any unsupported compiler behavior requires
an explicitly reviewed successor release and its own seal.

## Authority inventory and separate evidence lanes

1. Execution-v03 contains already approved Canonical 0.2 reference snapshots,
   ChangeSets and plans, verified by `tooling/execution_approval.py` against its exact pins.
   The human instruction approved ADR-0015/reference execution semantics.
2. Deterministic-v04 contains already approved Canonical 0.3 reference snapshots,
   ChangeSets and plans, verified by `tooling/deterministic_approval.py` against its exact pins.
   ADR-0016 and complete fixture decisions, including F-01, are explicitly approved.
3. `test-corpus/change/evolution.json` and generic evolution helpers are synthetic witnesses.
   They do not carry approval for new application semantics or production data decisions.
4. New proposals in [the review manifest](../proposals/phase6-evolution-review/manifest.json)
   are unapproved. No authority record, accepted journal entry, admission proof or migration
   execution is created by preparing them. Their candidate node lifecycle APPROVED is a
   structural active-candidate encoding required by the planner, not a human decision.

The [historical authority inventory](../proposals/phase6-evolution-review/historical-authority-inventory.json)
binds their old/new snapshot digests, plan digests, anchors and exact file hashes.
Historical exact old/new snapshots and authoritative ChangeSets remain in
`test-corpus/execution-v03/` and `test-corpus/deterministic-v04/` for both domains.
Use their stored files and approval-module pins, never reconstructed lookalikes.
A reference approval does not authorize a deployment, data conversion, or unknown SQL.
The stored zero-head fixture anchors are not a deployed accepted-history journal.
No deployed journal receipt or independent deployment data-binding approval is supplied here.

## Supported release upgrades: observed proof and limits

The supported production window is target 0.2, 0.3 and 0.4 to 0.5. Target 0.1 remains
outside it even where forensic upgrade tests pass.

| Path | Retained-data evidence | Interpretation |
| --- | --- | --- |
| 0.2→0.5 | Hosted privacy upgrade report and old runtime seed JUnit; old sealed generator, committed delivery/job rows, preserved runtime tables and origins, new invocation | Target release compatibility, not new semantic approval |
| 0.3→0.5 | Hosted UI upgrade report; actual sealed old generation, row-for-row database preservation, zero migrations, human identity customization, backend/frontend checks | Unchanged-specification release upgrade |
| 0.4→0.5 | Exact-source release helper exit 0 and both RemediationUpgradeTest JUnit reports in closure archive | Retained-data target upgrade; not semantic evolution |

Raw historical mode labels in the first two reports lag actual version fields. The new
observation preserves raw reports and explicitly identifies actual paths to 0.5.
The latest closure upload omits the full `release-upgrade/release-upgrade.json` receipt
and old seed JUnit for 0.4. Source-bound command success and successor JUnit are retained,
but do not replace those missing detailed receipts. A future complete deployment gate must
archive old/new projects, seed receipts, row comparisons, provenance maps and exact seals.
Do not claim an unchanged-specification 0.4→0.5 upgrade proves semantic evolution.

## Accepted-history deployed evolution procedure

Each step below is a future gate, not a completed result.

1. Select each approved old/new Canonical snapshot and exact historical ChangeSet. Verify
   signatures/reference scope, snapshot content hashes and revisions. Audit the actual
   deployed append-only journal, accepted predecessor, sequence and journal digest.
   Re-prepare against its real head. Require an exact new plan approval if its digest differs;
   never synthesize an accepted anchor or recycle a fixture proof for another request.
2. Check deployed target support before admission. Canonical 0.2→0.3 historical authority
   exists, but it does not prove all old-target execution/admission capabilities. Explicitly
   record unsupported baseline objects or storage conversion and stop. Legacy text-to-byte
   conversion must not be inferred. Canonical 0.3 relationship additions are not supported by
   the sealed planner. New structural/removal/irreversible changes also stop for review.
3. Obtain independent approval of exact data bindings, scoped to application, real plan,
   field IDs, tenant population and values. Bind bytes with the migration-bindings digest.
   Semantic MIGRATION scope alone is insufficient. No implicit business default is allowed.
4. Read accepted plan and separately approved bindings through genuine read-only authority
   ports. Missing, revoked, stale or mismatched receipts fail closed. Generate deterministic
   SQL twice from identical sealed inputs and compare bytes/digests. Review exact SQL,
   preconditions, lock policy, backup/restore point, affected row counts and recovery plan.
   Obtain an exact migration execution approval before applying SQL.
5. Generate and deploy the old application from its actual sealed artifact. Commit realistic
   multi-tenant domain/runtime data through real operations, including delivery, job,
   idempotency and lifecycle state. Capture immutable row/byte inventories and ownership.
   Backup and verify restore in an isolated PostgreSQL environment; record server/version.
6. Quiesce writers under the approved compatibility policy. Apply deterministic migration
   through real PostgreSQL with checked preconditions, transactional phases, row counts and
   exact byte assertions. Retain database identity, transaction outcome, SQL hash and logs.
   Never recreate/clean the database between old seed and successor verification.
7. Regenerate backend and frontend from the accepted new snapshot and sealed supported
   successor. Check artifact plans and materialization compare-and-swap, preserve human
   files, build both applications, and migrate/start against the same retained database.
   Archive both generations and deployment manifests with content hashes.
8. Verify changed semantics through actual application behavior and browser/API evidence,
   plus negative authorization/tenant checks. Verify unchanged approved behavior, full
   admission for both Canonical 0.3 references, exact bytes, journal continuity, provenance,
   ownership, recovery and retained operational state. Do not substitute unit tests for
   deployment evidence. Only then evaluate closure criteria; this plan grants no closure.

## Revised synthetic review packages (correction of e15bd10)

The planning approach is an accepted engineering checkpoint only. New semantic candidates,
independent bindings, migration plans and deployment actions remain NOT APPROVED.
The separate [PAYMENT package](../proposals/phase6-evolution-review/payment-human-review.md)
and [CASE MANAGEMENT package](../proposals/phase6-evolution-review/case-management-human-review.md)
provide exact candidate/ChangeSet digests, old/proposed meaning, commands and inputs,
UseCase/UI impact, required-field/new-write rules, risks and rollout decisions.
Their machine companions and [manifest](../proposals/phase6-evolution-review/manifest.json)
bind all review bytes. These revised digests supersede the e15bd10 draft digests.

Each new field now derives from the explicitly proposed AI-origin requirement
`REQ-EVOLVE-REFERENCE-NOTE` and its four synthetic acceptance criteria, rather than
REQ-PAYMENT or REQ-CASE. Existing approved business meanings do not authorize this addition.
Structural lifecycle APPROVED in candidates is not a human approval; packages and manifest
remain REVIEW_REQUIRED with empty approvals.

Static inspection of approved Commands and the sealed generator finds **no supported
payment/case resource-create operation**. Commands lock tenant-scoped existing resources,
reject missing rows and UPDATE; runtime bookkeeping INSERTs are distinct. UseCase inputs
remain resource identity and task text, and UI remains the existing-record task interface.
Direct reference setup and clone INSERT writers omit the new field and become incompatible
with its final required schema. The complete external writer inventory is unknown.

New records provisioned out of band must explicitly provide the new non-null String and
all existing mandatory fields/FK/invariant inputs. Empty String is permitted; absence,
null and non-String are rejected. No normalization, default, new create API, UI or implicit
assignment is introduced. The retained reference backfill remains exact UTF-8 hex
`65cc8100f09fa68b27`, never a production tenant or future-write default.

Compatibility is REVIEW_REQUIRED; the ChangeSet now conservatively declares BREAKING,
not BACKWARD. Old-writer/new-schema runtime compatibility is not claimed. UNKNOWN is a
closed-schema value but the existing planner correctly refuses to prepare it; no evaluator
or planner has been weakened. The proposed safe rollout is expand nullable without a
default, backfill approved retained rows, verify, switch/fence every insert writer and
re-scan under fencing, then contract NOT NULL. Do not run new required-model readers over
nullable rows. The sealed target does not orchestrate this staged deployment; exact SQL,
writer-switch/recovery evidence and any successor-target support need separate review.

For each domain, decisions remain separate: semantic requirement/candidate/ChangeSet;
independent reference-only binding; new-record writer and compatibility policy; real
accepted-history rebase/plan; exact SQL and deployment/recovery approval. A future resource
create Command/dataflow/UI requires an additional exact proposal, not a fabricated current
operation. Preview anchors are synthetic and not accepted history. No unknown future plan
or SQL is authorized. Historical execution-v03 and deterministic-v04 authority is audited
independently, never replaced by these unapproved proposals.

## Complete deployment failure/recovery matrix

Every row requires failure injection for each applicable domain and its actual sealed
old/new pair. All rows are PLANNED, not PASS. Evidence must include exact inputs, stage,
DB/transaction state, artifacts, journal/authority receipts and recovery result.

| Failure point / injection | Required state and recovery |
| --- | --- |
| Missing/revoked approval, binding or accepted journal; stale head | No SQL/materialization; reject, obtain genuine authority and re-prepare exact plan |
| Wrong seal, snapshot, SQL hash or unsupported lowering | No deployment; reject; separately approve supported successor if needed |
| Preflight schema drift, wrong tenant population, unexpected bytes | No writes; inventory drift, repair through reviewed plan and reapprove |
| Backup absent or restore rehearsal fails | No migration; establish verified restore point first |
| Writer not quiesced, lock timeout, concurrent journal/materialization writer | Abort before unsafe change; retain fencing/CAS evidence; retry only after resolving ownership and head |
| Connection/process loss before BEGIN or before first statement | Prove no effects; retry exact approved request with same idempotency identity |
| Expand failure inside transaction | Roll back; verify schema/data match before; repair precondition then bounded retry |
| Partial backfill, NUL/Unicode error, constraint or row-count failure | Roll back transactional unit; compare exact retained bytes; never silently coerce/default |
| Verify failure before COMMIT | Roll back; retain failing rows/query evidence; revise bindings/SQL with fresh approval if changed |
| Connection/process death at COMMIT, ambiguous outcome | Reconcile actual schema/version/row receipts first; never blind replay or duplicate side effects |
| Crash after committed migration before regeneration | Keep committed DB receipt; resume approved forward deployment from checkpoint; no invented rollback |
| Backend/frontend generation failure, disk full, CAS mismatch or symlink | Preserve last valid generation and ownership; reconcile partial outputs atomically, then resume exact plan |
| Human file conflict, unknown ownership, lost origin mapping | Stop activation; retain bytes and previous provenance; explicit adoption/repair review |
| Backend startup or schema compatibility failure | Fence traffic; approved compatible previous backend only if schema permits, otherwise reviewed forward repair |
| Frontend build/deploy failure or mixed client versions | Keep compatible asset generation; enforce retirement policy; verify cached clients before contract phase |
| Post-upgrade semantic, tenant, authorization or byte assertion failure | Fence affected traffic, retain forensic state; reviewed forward repair or verified restore with business reconciliation |
| Duplicate invocation/job/delivery on recovery | Preserve idempotency and committed outbox/job state; prove exactly intended effects before resuming |
| Provenance/evidence upload missing or digest mismatch | Runtime success does not pass gate; retain local signed/bound artifacts and re-upload exact bytes |
| Restore required, restore fails, or forward repair fails | Stay fenced; escalate exact recovery decision; rehearse restore and reconcile post-backup committed effects; no automatic destructive rollback |

No blind Flyway repair, checksum rewrite, partial cleanup, destructive rollback or claim of
production rollback support. Contract/removal and irreversible migrations are outside this
proposal and require separate semantics, compatibility and recovery approval.

## Object-level provenance and ownership assertions

For every applicable changed object and every dependent revision in the plan write set,
produce a row keyed by application/semantic ID/old-new revision. Bind old/new snapshot,
ChangeSet, accepted plan/journal, independent binding, exact SQL and generator seal. Record
basis and source origins, ArtifactPlan host/target object IDs, generated file paths and
SHA-256, table/column ownership, and exact runtime test/assertion/log digests. Unmapped
changed objects or runtime assertions are blockers. Conservative full-model origin sets
alone do not prove object-specific runtime behavior. Paths must be taken from actual
artifact plans after approved lowering; none are fabricated in this planning checkpoint.

For each proposed field, assert every retained row's exact new UTF-8 bytes and unchanged
old columns across tenants, required-field rejection, explicit new-write value behavior,
typed backend reads, unchanged approved UI/query behavior and permission/tenant isolation.
Bind these observations to the actual generated persistence artifacts. If new UI behavior
is desired, first obtain its separate exact semantic specification and approval.

| Owner | Mandatory assertion |
| --- | --- |
| COMPILER | Exact old hash/CAS before replacement; new artifact hash and origin-to-object mapping |
| HUMAN | Byte-for-byte survival or explicit adoption receipt; retain old compiler origin separately |
| AI | Exact bounded approval for proposed artifacts/semantics; origin never relabeled HUMAN |
| FRAMEWORK | Protected artifact policy and exact framework version retained |
| UNKNOWN | Reject materialization until ownership is explicitly resolved |

## Correction validation and latest branch CI observation

The [local verification record](../targets/spring-vue-postgres/evidence/phase6-evolution-corrections-validation.json)
separates historical execution-v03/deterministic-v04 authority from unapproved synthetic
proposals. Sixteen historical authority/semantic regression tests passed, and independent
Canonical 0.2/0.3 byte/hash vectors passed. Revised package hashes, candidate/plan bindings,
AI-only proposal origins, independent requirement basis and preservation of existing
Command/UseCase/UI meanings were checked. Attempting to lower either preview without
accepted history fails UNACCEPTED_HISTORY. No migration was executed.

The [latest branch CI observation](../targets/spring-vue-postgres/evidence/phase6-evolution-corrections-ci-e15bd10.json)
binds push run `38237101639` to reviewed commit
`e15bd1058f69194c87f71599250cf4474b93514c`, with exact observation time, job IDs/steps,
run status and available uploaded artifact metadata. At that observation, contracts,
phase5-experiments and phase5c-hard-gates succeeded; phase6-target was still in progress
and no closure result was available. Overall CI remains **IN_PROGRESS, NOT FINAL**,
not GREEN. Pending stages are not successes. Artifact downloads are not claimed.
This hosted run validates the earlier checkpoint, not these uncommitted revised packages.
A final hosted result and CI bound to revised source remain future evidence.

## Evidence-driven stop condition

The existing closure evaluator remains unchanged and fail-closed. Planning documents and
unapproved preview candidates are not admissible substitutes for accepted-history deployed
semantic evolution evidence. Missing real head, approval, independent bindings, SQL receipt,
per-object traces or recovery proof remains blocked. Preserve all existing gates and full
admission. Stop here for human review: no unsupported semantic implementation, no mutation
of sealed 0.5.0, no Phase 6 closure and no Phase 7 work.
