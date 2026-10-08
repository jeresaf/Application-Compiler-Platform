# Phase 6 delivery and scheduling tranche

Phase 6 remains IN PROGRESS. Phase 7 is NOT STARTED. This tranche follows the approved invocation checkpoint `bba16c9e64bd0a16e60343d4aaf11060f209e931`; it does not close Phase 6. Canonical 0.3, ADR-0016, approval proofs and both exact approved snapshot digests are unchanged. Privacy/lifecycle and all eleven task UI families remain blocked.

## Version and provenance decision

The active target profile is `acp-spring-vue-postgres/0.2.0`; generator is `acp-spring-vue-generator/0.2.0`. Target IR is explicitly 0.2.0: the Canonical 0.3 invocation and new durable runtime structures materially extend its meaning. A supplied 0.1.0 IR is rejected rather than reinterpreted. Canonical 0.2 remains an explicitly negotiated legacy semantic subset under the new profile. Historical 0.1.0 profile, V1 migration baselines, blocker contracts and evidence retain their original identities.

The historical local 0.1 bundle was `a718c37c159e9073ea61d3b307599f86ec2e9b9e2376efcccccf1e22ff36f91d`; the same Git checkpoint reconstructed with stored LF schema bytes is `20ab8a9e2554bed8c17a163eb69ab8a37099a014a5cc4c4803c49afd3e2fd6dd`. Three old schema files retained local CRLF. Both hashes are preserved and reproduced; the old profile did not have a sealed portable release contract. JSON checkout endings are now explicitly LF, and local schema bytes match their unchanged Git blobs.

The release contract binds one exact source/template/tooling/schema bundle to each released target/generator identity. The worker and host adapter reject a changed bundle under the same sealed identity. CI also preserves prior release registry entries. Output-affecting changes require an intentional successor generator version and new immutable release entry. Generated `acp/provenance.json` carries target/generator, exact bundle digest, protocol, Canonical/model versions, snapshot digest, features, compiler and pipeline. Artifact mappings retain exact semantic origins and generated content digests. `acp/profile.json` carries the actual successor profile. `acp/target-upgrade.json` records the old-to-new identity transition and exact migration hashes.

## Delivery profile

Delivery supports only AT_LEAST_ONCE / PER_AGGREGATE / EVENT_COMMIT / COMMIT_STEP_EMISSION_SEQUENCE, a 3600-second window and an explicitly referenced idempotency policy covering at least that window. Other guarantees, ordering or anchor forms reject negotiation.

New event identities hash an unambiguous structured tuple containing tenant, aggregate ID/revision, exact resource identity, commit sequence, operation ID/revision, event ID/revision, step ordinal and emission ordinal. Payload, identity, PostgreSQL full transaction ID and pending state are inserted in the domain transaction with state changes, results and idempotency results. Rollback exposes no occurrence.

For the one-root atomic subset, every mutating Command locks the root and increments its checked `acp_version`. The lock lasts through commit/rollback. The first event-producing root version in that transaction is its commit sequence; every event in that transaction shares that sequence. A subsequent transaction cannot acquire the root until the earlier transaction completes, and its first emitted version is greater. Rolled-back versions are not visible. This supplies strict committed serialization order without timestamp or transaction-ID ordering assumptions. Within a commit, explicit UseCase step and declared emission ordinals determine order. Direct Commands use step zero.

Delivery obtains the actual PostgreSQL commit timestamp from the stored full transaction identity, guarding against transaction-ID wrap/reuse. It caches only a proven commit fact. Unavailable proof never acquires a guessed anchor or expiry. `track_commit_timestamp=on` is required.

PostgreSQL session advisory locks fence each tenant/aggregate/resource delivery group across durable claim transactions and transport calls. Workers select only the earliest pending/claimed position. Transport waits are bounded to the lesser of one second or the remaining window; unknown/late adapter completion never acquires an invented acknowledgement. Each attempt has a separate durable row with start/completion instants, result and acknowledgement. Acknowledgement before the half-open deadline releases the barrier. At the exact deadline, an unsatisfied occurrence becomes UNSATISFIED; late acknowledgement remains an unsatisfied obligation. Different groups can progress independently. A lost process after send can redeliver the same exact occurrence after its database session lock releases. This is at least once, not exactly once; consumer deduplication is separate. Occurrence identity and attempts are retained beyond the complete window.

`DeliveryRuntime.Transport` is the replaceable transport port. Tests use deterministic acknowledgement/failure/crash adapters. No broker is required. Without an external adapter, the generated bootstrap uses an explicitly unavailable transport: attempts fail and obligations eventually expire; it never manufactures acknowledgements. External transport availability remains a deployment obligation.

## Pinned scheduling profile

The admitted Schedule subset is LOCAL_DAILY, 09:00:00, Africa/Nairobi, tzdb 2026d, gap SKIP and overlap EARLIER. INTERVAL and other canonical schedule forms remain rejected. The generated evaluator packages exact 2026d offset-transition data and evaluates UTC candidates directly, without JVM/OS ZoneId rules. Its explicit rule horizon is 1900–2100; observations or dates outside packaged coverage reject safely. The pinned artifact also contains America/New_York and Europe/Berlin for target-only transition tests, including EARLIER/LATER and REJECT behavior; these variants do not alter approved fixtures or expand negotiation claims.

The artifact is derived reproducibly from the pinned Python tzdata package, explicit TZif transitions and its POSIX continuation rules. `tooling/package_target_tzdb.py --check` verifies every packaged byte. Generated provenance records its version and SHA-256 digest. Source identity is [IANA release 2026d](https://www.iana.org/time-zones/releases/2026d).

## Durable Job profile

Job occurrence identity includes exact Job and Schedule IDs/revisions, canonical scheduled UTC nanoseconds and tenant. The generated database/schema is application-scoped. Polling time observes when an occurrence is due; it never supplies its identity. Explicit approved literal bindings construct the typed input and exact synthetic fixture resource; no current record is substituted.

`JobRuntime.PrincipalPort` resolves a configured opaque credential handle keyed by Job ID/revision. The configuration property is `acp.jobs.<JobID>.revision-<revision>.credential-handle`. Startup fails if the adapter or a required handle is absent. No credentials are generated. The resulting principal traverses the same session, authorization and tenant checks as HTTP operations. ACTOR rate partition uses its authenticated subject. Durable per-occurrence rate admission records preserve a previously charged logical invocation across retries/recovery; they are written atomically with token admission, after normal authorization. New occurrences receive new rate admissions.

The generated Job selects its exact canonical RetryPolicy. Bound TRANSIENT/retryable Failures retain the same scheduled occurrence, operation inputs and idempotency key across attempts. Each semantic invocation attempt records its start/completion, outcome and exact bound Failure reference durably. An occurrence remains STARTED while its invocation/retries run, then becomes COMPLETED, FAILED with a known failure, or INDETERMINATE when outcome is uncertain. Recovery uses durable idempotency proof and never converts an already-started occurrence to missed work.

The boundary enforces the declared 30-second timeout through a bounded task wait and JDBC transaction timeout. Cancellation does not prove rollback. Uncertainty remains durable until the database/idempotency mechanism establishes a result or no-effect rollback. A process/session fence and exact idempotency identity prevent racing workers from creating independent logical occurrences.

SKIP is implemented with durable half-open activation/recovery skip ranges and explicit skipped records for enumerated not-started occurrences. The range represents the complete unstarted historical prefix without attempting infinite backfill. An occurrence exactly at activation is normally scheduled. Started/indeterminate occurrences are excluded from missed-work skipping and recover under their original identity. Scheduler cursors and observation times are durable; clock reversal fails closed. RUN_LATEST and CATCH_UP reject negotiation.

Job success refers to the semantic invocation, independently of delivery acknowledgement. No domain transaction waits for external delivery.

## Database transition and validation

V1 is byte-identical to the invocation profile's approved generated baseline. V2 adds delivery metadata, attempts, scheduler, Job occurrence and invocation-attempt state. Fresh databases apply V1 then V2. Upgrade tests first apply the historical V1 bytes, seed domain/idempotency/rate/audit/outbox state, then apply the successor migrations and verify preservation. Historical outbox rows have no recoverable original transaction identity; they remain LEGACY_UNPROVEN, retain original payload/identity, and block that resource's delivery until explicit evidence-backed remediation. No upgrade invents commit anchors or silently sends old events.

Actual complete compiler/worker negotiation is recorded in [expected-open evidence](../targets/spring-vue-postgres/evidence/delivery-job-open-linux.json) and [strict evidence](../targets/spring-vue-postgres/evidence/delivery-job-strict-linux.json). Expected-open mode passes contract 3.0.0; strict closure remains BLOCKED. Component builds do not admit either complete application.

Both applications report exactly these sixteen remaining families:

- Privacy/lifecycle: DataClassification, DataLifecycle, Retention, DeletionPolicy, LegalHold.
- UI: Action, Filter, Form, InputControl, PermissionBoundary, Screen, Search, Table, ViewState, Wizard, WizardStep.

The [immutable blocker contract 3.0.0](../targets/spring-vue-postgres/expected-open-blockers-v3.json) binds both exact approved Canonical digests and the successor profile. Historical contract 2.0.0 retains its original nineteen blockers. Phase 6 remains IN PROGRESS; Phase 7 is NOT STARTED.

## Final Linux validation

The sealed successor bundle is `sha256:d66fc31b74ac3c6ee5d391027b66726bbd8c93b2d624329a0cf3c327b9a9f70b`. [Machine-readable generated runtime evidence](../targets/spring-vue-postgres/evidence/delivery-job-components-linux.json) records Payment's 56 and Case Management's 57 passing backend tests with no failures/errors/skips, plus frontend lock installation, type checks, tests and production builds. Each domain includes 24 delivery/schedule/Job tests alongside the existing invocation and infrastructure regressions.

The tests exercise actual commit anchors, occurrence identities and ordering, durable attempts, exact deadlines/late acknowledgement, duplicate workers, send-before-crash redelivery, independent aggregates, rollback, canonical timezone reference vectors, exact Job bindings/principal enforcement, concurrency, SKIP/recovery, retry failure bindings, durable rate admission and lost-result idempotency recovery. The actual PostgreSQL timeout test deliberately observes that cancellation can leave a transaction in progress: recovery stays indeterminate until explicit database abort proof, then commits once under the same occurrence identity. An unbound internal provider fault is terminal and receives no automatic Job retry.

The [actual application upgrade evidence](../targets/spring-vue-postgres/evidence/delivery-job-profile-upgrade-linux.json) records accepted-checkpoint generation, real old-runtime commits and an in-place V2 upgrade for both domains. Domain, idempotency, rate, audit, classification audit, outbox and session rows retain every old column value; all historical artifact origin mappings are preserved. A successor invocation then commits new delivery state. No database clean occurs between the old invocation and upgrade.

The [legacy Canonical 0.2 component evidence](../targets/spring-vue-postgres/evidence/delivery-job-legacy-linux.json) records passing backend PostgreSQL and frontend checks for both domains. A dedicated regression verifies that legacy planning retains V1 only and the correct semantic/provenance version.

Independent Node verification passes all three byte/hash corpora unchanged. Dependency consistency, repository checks, exact sealed release verification and packaged tzdb byte reproduction pass. External transport deployment and production principal credentials are not claimed.

## Reproduction

Use the isolated `.venv` and an explicit ephemeral PostgreSQL 18.6 database with `track_commit_timestamp=on`; supply `ACP_TEST_DATABASE_URL`, `ACP_TEST_DATABASE_USER` and `ACP_TEST_DATABASE_PASSWORD`. These harnesses clean their test schemas, so run them sequentially against a disposable database.

```sh
.venv/bin/python3.14 tooling/check_target_release.py
.venv/bin/python3.14 tooling/package_target_tzdb.py --check
.venv/bin/python3.14 tooling/check_delivery_job_components.py --output /tmp/acp-delivery-recheck --run-builds
.venv/bin/python3.14 tooling/check_target_profile_upgrade.py --output /tmp/acp-upgrade-recheck --new-projects /tmp/acp-delivery-recheck
.venv/bin/python3.14 tooling/check_execution_components.py --output /tmp/acp-legacy-recheck --run-builds
.venv/bin/python3.14 tooling/check_phase6_target.py --output /tmp/acp-open-recheck --expect-open-blockers
.venv/bin/python3.14 -m unittest discover -s tooling/tests -v
```

Use fresh output directories. `/tmp` logs are ephemeral local evidence; the checked-in JSON reports preserve the bounded results. Omitting `--expect-open-blockers` must return failure until complete target admission is implemented.
