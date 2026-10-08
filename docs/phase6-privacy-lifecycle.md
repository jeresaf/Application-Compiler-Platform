# Phase 6 privacy and lifecycle checkpoint

Phase 6 remains **IN PROGRESS / NOT CLOSED**. Phase 7 is **NOT STARTED**.
Canonical 0.3, Authoring 0.4, ChangeSet 0.3, ADR-0016 and the exact approved
Payment and Case snapshots retain their authority and bytes. No UI capability
is implemented by this tranche.

## Release and IR compatibility decision

Target `acp-spring-vue-postgres/0.3.0` and generator
`acp-spring-vue-generator/0.3.0` intentionally succeed sealed 0.2.0.
The release registry retains both 0.1.0 and 0.2.0 entries unchanged.
The new exact bundle is recorded in `release-contract.json` and generated provenance.

**Target IR remains 0.2.0 deliberately.** Existing IR nodes already retain the
exact classification tuples, lifecycle anchor, durations, holds and typed
disposal effects. Neither the IR shape nor the meaning of any IR member changes.
The successor implements those existing semantics in new generated runtime,
V3 schema and deployment/provenance artifacts. Runtime/schema versions are not
IR versions. An IR carrying an older profile/generator is rejected by the
existing exact generation boundary; retaining IR 0.2 does not authorize mixing
released generators.

## Exact supported boundary

Canonical 0.3 support is constrained to these forms; Canonical 0.2 compatibility
retains its earlier independent negotiation limits.

| Family | Implemented subset |
| --- | --- |
| DataClassification | PUBLIC/INTERNAL: WRITE, NONE; SENSITIVE: READ_WRITE, MASK; SECRET: READ_WRITE, OMIT. All require export DENY, NON_DOMAIN_OBSERVABILITY and both encryption requirements true. |
| DataLifecycle | CLOSED_COMMIT, COMMITTED_ENTRY, one exact terminal state/machine, scoped single-identity aggregate root; no reopening. |
| Retention | CLOSED, nonnegative signed-32-bit integer seconds from authoritative closure. |
| DeletionPolicy | CLOSED, ANONYMIZE, BLOCK; optional String/Nullable String REMOVE, or exact Money UGX/18/2/REJECT constant canonical `1` REPLACE. No DELETE or arbitrary expression support. |
| LegalHold | Pure literal-true Boolean condition, exact Permission, CURRENT_LIFECYCLE_ACTION and explicit exact Hold ID/revision release. Other conditions/modes reject. |

READ audits follow authentication, tenant/permission checks and actual selected
results. WRITE audits share the semantic transaction and disappear on rollback.
Lifecycle writes audit only affected classified fields. Audit rows contain
references, actor, tenant, resource and mode, never raw classified values.
Export DENY fails closed; there is no export endpoint or newly admitted
PERMISSION_REQUIRED subset.

`PrivacyGuards.observability` and the injected `Observability` contract 1.0.0
cover log, trace, diagnostic, error and audit-value metadata. MASK is the fixed
`[REDACTED]` marker; OMIT removes the member. NONE imposes no classification
redaction and grants no permission to log arbitrary bodies. Generated diagnostics
accept a closed code enum and semantic Field IDs. Framework request/binding/
provider details are suppressed in generated application configuration. Authorized
typed API values, domain state and committed Event payloads remain exact values.
Trusted custom logging/export adapters must use the classified metadata port;
external exporter verification remains outstanding.

## Closure proof, timing and atomic disposal

A terminal Command writes the lifecycle ID/revision, tenant/resource, machine/
state exact revisions, root version and full PostgreSQL transaction identity in
the same transaction as its domain change. Rollback produces no anchor. Only
`pg_xact_commit_timestamp` resolves the actual closing commit instant, after
commit proof; observation/request/migration times are never substituted. The
cached anchor is written once. Missing or aged-out authoritative proof fails
closed. PostgreSQL must run with `track_commit_timestamp=on`.

Payment binds WF-PAYMENT/STATE-POSTED; Case binds WF-CASE/STATE-ARCHIVED.
Retention is 86400 seconds and anonymization delay 172800 seconds. Both constraints
must permit action, using exact integer nanoseconds. Reversed clocks fail safely.
Automatic polling observes eligibility and records literal-true holds as blocked.
It never invents an implicit release principal.

Authenticated disposal takes the same root row lock used by Commands and rechecks
current state, tenant, time and every hold. Permission possession alone is not a
release request. Exact explicit release requires the declared Permission and its
audit shares the action transaction; rollback removes it. No permanent release
state is stored. A later resource action re-evaluates the hold and requires a
fresh request.

Payment stages UGX 1.00 and evaluates complete retained WRITE invariants before
updating; the positive-amount database constraint remains. Case clears FLD-NOTE
and sets its presence bit false: ABSENT remains distinct from explicit NULL.
Other fields, committed outbox payloads and stored idempotency results are not
rewritten. Anonymization manufactures no domain Event.

The durable anchor/action tables distinguish unproven, waiting, held, uncertain
and completed work. Session advisory fencing prevents simultaneous workers;
root locking serializes Commands and disposal. A durable action XID precedes
any effect, and action completion, effects and audits commit atomically.
Recovery consults authoritative PostgreSQL transaction status. An unresolved
attempt remains indeterminate; a proven rollback can retry with fresh hold
checks. Completed work returns its durable result without repeated effects or
audits. Attempt records contain references/status/time/XID only.

## Production management port

`RuntimeBootstrap.management()` exposes `LifecycleRuntime` management contract
1.0.0 inside the generated application. It is a direct trusted-host service port,
not a new Canonical UseCase or business HTTP endpoint. The host passes the normal
verified JWT principal and an explicit set of `Release(hold, revision)` references
to `dispose(lifecycle, resource, principal, releases)`. Normal session, actor,
tenant and exact release Permission checks still run. Never construct principals
from unverified client claims. `observe`/`poll` can report eligibility but cannot
release holds. Polling cadence is an engineering mechanism only.

## Deployment obligations and upgrade honesty

`acp/deployment-requirements.json` records exact originating semantic IDs/revisions.
All entries remain **OUTSTANDING**: TLS, storage encryption, key management,
backup encryption/lifecycle, observability exporters, WAL/replica retention,
privacy destruction and classified historical Event/idempotency storage.
The artifact digest, IR version, V1/V2/V3 digests, profile, generator, exact
bundle and approved snapshot digest are bound into generated provenance.
Application anonymization proves no secure physical erasure or backup/WAL/
replica destruction.

V1 and V2 bytes remain those of released 0.2 applications. New
`V3__privacy_lifecycle.sql` adds lifecycle state. Existing terminal rows without
closure proof become LEGACY_UNPROVEN with no fabricated XID/instant. They require
future evidence-backed remediation, not migration-time anchoring.
`check_privacy_profile_upgrade.py` archives and runs the actual sealed 0.2
application, commits real Job/domain/delivery state, applies only V3 in place,
compares every old column/row and origin mapping, then exercises a new real
lifecycle action. The existing real 0.1 upgrade gate remains enabled.

## Reproduction and open closure gate

Use the isolated `.venv` and PostgreSQL 18.6, with the `ACP_TEST_DATABASE_*`
variables documented in the preceding runtime tranche. Run sequentially because
the component harnesses share an ephemeral integration schema:

```bash
.venv/bin/python3.14 tooling/check_target_release.py
.venv/bin/python3.14 tooling/check_privacy_lifecycle_components.py --output /tmp/acp-privacy-components --run-builds
.venv/bin/python3.14 tooling/check_privacy_profile_upgrade.py --output /tmp/acp-privacy-upgrade --new-projects /tmp/acp-privacy-components
.venv/bin/python3.14 tooling/check_phase6_target.py --output /tmp/acp-privacy-open --expect-open-blockers
```

`/tmp` logs are ephemeral local evidence. Checked-in JSON evidence and separately
uploaded Ubuntu CI artifacts retain the reproducible results. Prior phase reports,
release evidence and blocker contracts are historical records and remain intact.
Blocker contract 4.0.0 is derived from real worker negotiation against both exact
approved snapshots, rather than assumed from the desired capability count.
Contract 4.0.0 is immutable; a changed blocker baseline requires a successor contract.
Expected-open CI passing is not target admission or Phase 6 closure. Strict
closure remains BLOCKED pending task UI and complete browser/evolution evidence.

## Linux evidence

The [component report](../targets/spring-vue-postgres/evidence/privacy-lifecycle-components-linux.json)
records 145 passing PostgreSQL/backend tests (72 Payment, 73 Case), including
32 new lifecycle/HTTP privacy tests, plus frontend install/type/test/build checks
for both applications. All 113 preceding backend tests remain present.
The [final bundle binding](../targets/spring-vue-postgres/evidence/privacy-final-bundle-binding-linux.json)
records byte equality of all 65 generated production artifacts per application
after correcting an upgrade-harness assertion about an empty legacy table.
Only bundle provenance/upgrade metadata changed; Ubuntu CI repeats the complete
suite against the final sealed bundle. The [deployment projections](../targets/spring-vue-postgres/evidence/privacy-deployment-payment.json)
retain every infrastructure verification obligation as OUTSTANDING.

The complete Linux Python regression suite passes: **230 tests**. Repository
contracts, dependency consistency and all three independent Node canonical-byte/
hash corpora pass. Approved semantic schemas, snapshots, approvals and historical
phase reports are unchanged. The successor expected-open gate reports exactly
the eleven task UI families in each approved application; strict closure remains
BLOCKED.

The [actual 0.2-to-0.3 upgrade report](../targets/spring-vue-postgres/evidence/privacy-target-upgrade-linux.json)
passes for both domains, including exact old-state/origin preservation,
LEGACY_UNPROVEN closure and a real new lifecycle action. The
[preserved 0.1-to-0.3 upgrade gate](../targets/spring-vue-postgres/evidence/privacy-legacy-target-upgrade-linux.json)
also passes for both domains. Historical release evidence remains unchanged.

The [preserved Canonical 0.2 components](../targets/spring-vue-postgres/evidence/privacy-legacy-components-linux.json)
pass PostgreSQL/backend and frontend checks for both domains, without widening
legacy target admission. The [Linux validation summary](../targets/spring-vue-postgres/evidence/privacy-validation-linux.json)
binds the final bundle, checks and exact remaining blocker sets.
