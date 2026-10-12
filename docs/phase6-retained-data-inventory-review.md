# Phase 6 retained-data inventory and authentic history discovery

Review checkpoint: `9c29727148dd6f9fd563722bd9c5fbffd9dd5699`, branch
`codex/phase6-production-remediation`. This is a measured engineering review package,
not permission to migrate or deploy. Phase 6 remains IN_PROGRESS; Phase 7 NOT_STARTED.

The separate [PAYMENT binding package](../proposals/phase6-measured-data-binding-review/payment.md)
and [CASE MANAGEMENT binding package](../proposals/phase6-measured-data-binding-review/case-management.md)
contain exact application, semantic decision, candidate, binding, inventory, population
and writer digests. The [review manifest](../proposals/phase6-measured-data-binding-review/manifest.json)
binds both machine packages and their human-readable notes.

## What was actually measured

Two **newly constructed synthetic reference test deployments** use PostgreSQL 18.6,
separate databases and schema `acp_retained_inventory`. Both were generated from the
actual sealed 0.4.0 source commit `7e4e3438179e7a446c5f3737ad1d6d9cb07a96ea`, bundle
`61c4647cfbe38cdbd97d03305685b3903f3ff24cfdb20d7c5b4502b478a0e06a`.
This immediate predecessor is in the supported 0.2/0.3/0.4→0.5 window; target 0.1 is outside it.
No target upgrade or semantic evolution was executed in this task.

The [deployment record](../targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12/deployment.json)
binds container/image identities, generated predecessor archives, seed source, actual
Maven logs and JUnit results. Existing approved fixture provisioning and clone paths seed
three resources per application, across two synthetic tenants. A wrong-tenant invocation
is rejected, and an existing supported task commits domain and runtime state. The identity
helper is the existing reference-only fixture, not evidence of production authentication.
No new password, key, human signature or history receipt was created.

Only sealed predecessor V1–V3 schema bootstrap ran in these initially empty databases.
No EVOLVE-REFERENCE-NOTE column was added. No evolution expand, backfill, verify, switch
or contract SQL ran. Existing unrelated `FLD-NOTE` in CASE MANAGEMENT remains an old field.
The proposed new note bytes were never assigned to any row.

After seed processes completed, both databases were fenced with default read-only
transactions. Capture uses a repeatable-read read-only transaction. A second capture
matches the entire frozen population, including runtime state. The local bootstrap user
can remove this reference fence; a future execution gate must recheck live state and stop
on drift, rather than treating this local fence as production access control.

| Application | Retained owner rows | Tenant-one | Tenant-two | Committed outbox rows |
| --- | --- | --- | --- | --- |
| PAYMENT | 3 | 2 | 1 | 1 |
| CASE MANAGEMENT | 3 | 2 | 1 | 3 |

Resources in each database are `fixture-resource`, `retained-same-tenant` and
`retained-tenant-two`. Both inventories include database and cluster identities,
schema OID/columns/constraints/indexes/sequences, server version, exact row counts,
semantic-field/column mappings, every domain/relationship/runtime table, SQL NULLs,
exact bytea hex, non-bytea database text, timestamps and inventory/population digests:

- [PAYMENT frozen inventory](../targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12/payment.json).
- [CASE MANAGEMENT frozen inventory](../targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12/case-management.json).
- [Validation and measured-population negative checks](../targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12/validation.json).

Inventory digests include capture metadata. Population digests exclude only capture time
and transaction snapshot token; database identity, all old bytes/runtime state, schema,
source/seal and writer inventory remain bound. Digests use SHA-256 of sorted compact JSON
with ASCII escapes, as implemented in `tooling/audit/retained_inventory.py`. They are
engineering evidence hashes, not new Canonical IR semantics or signatures.

## History discovery boundary

[Accepted-history availability](../targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12/history-availability.json):
**AUTHENTIC_HISTORY_UNAVAILABLE for both applications.** No deployed repository identity,
trusted authority configuration, authorized authenticated read endpoint, accepted head,
accepted snapshot or journal receipt was supplied or discovered in the inspected scope.
Journal continuity is unverified. This is a bounded availability finding, not a claim
that no such repository exists anywhere.

Previously approved execution-v03/deterministic-v04 fixture snapshots and plans remain
historical evidence. Their zero-sequence test anchors do not prove a deployed accepted
journal. The newly seeded PostgreSQL outbox/idempotency records are application runtime
state, not Canonical accepted-history receipts. No adapter was initialized to create a
replacement history, and no synthetic anchor was attached to an accepted plan.

## Writer compatibility and proposed binding

The [writer inventory](../targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12/writers.json)
pins all Python/Java/SQL sources in the tooling and target worker/template boundaries,
with line digests for insertion/provisioning sites. Conservative source pinning rejects
added files even if dynamic SQL evades literal matching.

`phase6_reference_tests.seed_sql` creates tenant, actor, owner and relationship rows;
its child-relationship tests provision other resources. `invocation_reference_tests`
clones explicit original Canonical owner columns. The new inventory seed harness calls
those existing paths. Delivery, privacy, HTTP and target-upgrade harnesses reuse these
helpers. Owner seed and clone writers omit EVOLVE-REFERENCE-NOTE and become incompatible
with the final required schema. Inserts of unrelated child/runtime rows do not acquire
that owner field. History SQLite inserts and standalone migration probes are identified
separately; neither is an application resource provisioner.

PAYMENT CMD-RECORD and CASE MANAGEMENT CMD-REVIEW→CMD-APPROVE→CMD-ARCHIVE update existing
resources. Their inputs do not create owner rows or require a new note. Generated runtime
writers create session/rate/idempotency/outbox/audit/job/delivery/lifecycle rows, not owner
resources. No supported domain import endpoint was found. External import/provisioning
writers remain unknown and must be inventoried before any rollout; their absence is not
assumed. The source inventory is not proof of arbitrary tenant infrastructure.

Proposed bytes `65cc8100f09fa68b27` are a nine-byte synthetic Unicode/NUL witness only.
Each independent binding package proposes them for its exact three frozen owner rows.
They are not approved, not a production value, and not a new-record default. Future new
records require an explicit non-null valid String; empty String is distinct and allowed.
Old writers must be adapted or fenced before final required-field enforcement. Historical
backfill must never silently supply missing new-record input.

## Validation and independent reproduction

Both real predecessor Maven seed tests passed with zero failures/errors/skips. Thirteen
inventory regressions pass. On each measured population, missing row, extra row, changed
tenant, modified bytes, unexpected writer, wrong database, wrong schema, stale population
digest and wrong application all reject. Adversarial changed payloads are rehashed where
applicable, so a valid checksum alone cannot hide drift from the frozen baseline.

From repository root, verify the durable captures without any database connection:

```bash
python3.14 -m unittest discover -s tooling/tests -p test_retained_inventory.py -v
python3.14 tooling/audit/retained_inventory.py \
  --writers targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12/writers.json \
  --verify-frozen targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12/payment.json \
  --observed targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12/payment-recapture.json
```

Use the corresponding `case-management` files for the second application. Install
repository requirements only inside `.venv` and run these commands through its interpreter.
The capture CLI can produce a new read-only observation against the retained local
reference databases; it first verifies sealed generated artifacts and the source writer
manifest. Compare the new observation to the frozen capture. A changed source manifest
or changed population requires review and a new decision; never silently reuse a binding.

The sealed predecessor archives retain generated source and ownership metadata. Their
provenance maps bind every artifact to the original approved Canonical snapshot and exact
sealed bundle. The deployment record gives archive hashes. Local `.audit-artifacts`
working copies and `/tmp` logs are convenience evidence; the review package retains
necessary logs, JUnit, inventories, archives and hashes durably in the repository.

## Hosted evidence

[Run 38243318747](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/38243318747)
is bound to the exact reviewed source `9c29727148dd6f9fd563722bd9c5fbffd9dd5699`.
The downloaded target archive matches GitHub's published SHA-256
`67b9258aeec8fb9b01651f6dc7076f4537dbe5e02161bea1b70c90dbd7716410`.
[Verified full-admission evidence](../targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12/full-admission.json)
and the retained underlying report confirm both original Canonical 0.3 applications
remain accepted, with backend, frontend and real-browser checks PASS. This proves neither
admission of the proposed evolution nor an accepted migration plan.

The [final exact-source CI observation](../targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12/ci-final.json)
records these actual final conclusions:

| Job | Final conclusion |
| --- | --- |
| contracts | success |
| phase5-experiments | success |
| phase5c-hard-gates | success |
| phase6-target | success |
| phase6-closure-audit | failure |

The overall run concluded **failure**, not GREEN. The closure audit was PERFORMED with
no execution exception, exited 2, and recommended PHASE6_CLOSURE_BLOCKED with 21 blockers.
Its downloaded archive matches the published SHA-256
`1d95df3d6d2e3f757d6bbe54ab983f08afc70d402ced2763eff6fe423589a1c6`.
Raw run/job/artifact metadata and the new closure report are retained separately from
older evidence. The first blocked closure audit is unchanged.

This hosted run validates the reviewed commit. New uncommitted inventory tooling and
packages have separate local validation and source hashes; no new-source hosted CI is
claimed. Earlier hosted records and the first blocked closure audit remain unchanged.

## Exact remaining decisions

1. Human signing of each preserved semantic-content signing request through a trusted
   authority. Content is APPROVED_CONTENT; authenticated proof is PENDING_HUMAN_SIGNING.
2. Independent PAYMENT decision on its exact proposed scalar, inventory/population,
   tenant/resource set, predecessor identity and writer manifest.
3. Independent CASE MANAGEMENT decision on its own corresponding exact inputs. Identical
   scalar/binding digests do not authorize another application's population.
4. Supply genuine accepted-history repository identities, authority configuration and
   authorized authenticated read mechanisms; verify accepted heads, snapshots, continuity
   and the provenance of each receipt before preparing an accepted migration plan.
5. Review any exact rebased migration plan, deterministic SQL, writer switch/fence,
   recovery/restore and failure obligations only after authentic authority is available.
   Before commit, prove rollback; for staged or ambiguous commits inspect actual state;
   after commit require approved repair/restore and reconciliation of later effects.
6. Give separate explicit migration execution and deployment authorization if desired.
   Neither is granted by this inventory or the semantic content decisions.

Accepted migration plan NOT_APPROVED; SQL execution NOT_AUTHORIZED; deployment
NOT_AUTHORIZED. Stop for architecture and human review. Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.
