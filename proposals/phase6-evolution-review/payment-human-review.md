# PAYMENT — separate human review package

Status: REVIEW_REQUIRED, UNAPPROVED. Engineering planning approach accepted only.
Phase 6 IN PROGRESS; Phase 7 NOT STARTED.

## Old and proposed meaning

Synthetic scenario: authorized users record positive payments within their tenant.

PROPOSED, UNAPPROVED, SYNTHETIC REFERENCE ONLY: ENT-PAYMENT records retain a required exact String reference note. New records must explicitly supply it; retained-row backfill requires independent approval and is never a future-write default. No create operation or UI is added. Existing approved update behavior preserves it. Rollout remains REVIEW_REQUIRED.

New requirement: `REQ-EVOLVE-REFERENCE-NOTE` revision 1. New field: `EVOLVE-REFERENCE-NOTE` revision 1 on `ENT-PAYMENT`.
The field basis is the new synthetic requirement alone. Existing business requirements do not authorize it.
All added origins are AI proposals. Active-candidate lifecycle markers do not represent human approval.

## Exact review bindings

Old snapshot: `sha256:d0f6e8d96a07e8e8358ad8f1f558f9ec3d69fd8008cceb75e82f4f695e3cf47d`

Proposed candidate: `sha256:5c54e0692524ec907b5c5373b8b5536e4f053122ce033dda70957320a53281cf`

ChangeSet file SHA-256: `sha256:3fffe5ef53a9446b4c827a8ab220b8fa5d7e02760f941b7f8d7b227dc3facefa`

Preview plan: `sha256:9b2c7f905976302f3341beccf1a2820563ca3ac957129c9aa8a5c138e3402d15` (synthetic anchor; not executable authority).

Independent backfill binding: `sha256:2a584b4d5ca471d1f1686db24e3b094e1a91f7e69e4d9f4775fcad1607c49481`; UTF-8 hex `65cc8100f09fa68b27`.
Reference retained rows only; no production tenant or future-write default.

## Proposed acceptance criteria

- `AC-EVOLVE-RETAINED`: PROPOSED synthetic reference-only: retained rows receive only the independently approved exact backfill bytes; never use this binding as a production tenant or future-write default.
- `AC-EVOLVE-NEW-WRITE`: PROPOSED: each new reference record must explicitly supply EVOLVE-REFERENCE-NOTE as a non-null String. Absent, null or non-String values are rejected; empty String is permitted. Preserve exact Unicode scalar sequence as UTF-8, without normalization or an inferred default. Target 0.5.0 exposes no resource-create Command or UseCase; direct fixture provisioning must supply this field explicitly.
- `AC-EVOLVE-UPDATE`: PROPOSED: existing task Commands continue to update existing records using their exact approved inputs and preserve EVOLVE-REFERENCE-NOTE. Missing resource identity remains RESOURCE_NOT_FOUND; no upsert or create is introduced.
- `AC-EVOLVE-ROLLOUT`: PROPOSED: old insert writers that omit the field are incompatible with final NOT NULL/no-default schema. Expand nullable, backfill retained rows, verify, switch or fence all insert writers, then contract. Keep REVIEW_REQUIRED until actual old-writer/new-schema and recovery evidence exists.

## Commands, UseCases and UI

Supported resource-create operations: **none**. Existing Commands lock existing records and UPDATE them.
Missing records fail RESOURCE_NOT_FOUND. Runtime outbox/job/audit inserts are not resource creators.

- `CMD-RECORD`: `OPERATION-INPUT` requires `OPERATION-TEXT`; resource identity, expected version, authentication/authorization and existing invocation/idempotency rules still apply. Writes `FLD-TASK-SUMMARY`, not the proposed field.

`UC-TASK` requires `INPUT-TASK-RESOURCE` and `INPUT-TASK-TEXT`; the exact command sequence is CMD-RECORD.
`FORM-TASK`/`CONTROL-TASK-RESOURCE`/`CONTROL-TEXT`/`ACTION-TASK` remain existing-record task controls. No create form or note input is proposed. Dependency revision closure is not a new business effect.

## New records and required constraints

Out-of-band reference provisioning must explicitly supply all existing required fields and the new String, satisfying existing identities, tenant/FK/invariant constraints. It is not a supported create API.

Required provisioning fields: `FLD-AMOUNT`, `FLD-PAYMENT-ID`, `FLD-PAYMENT-TENANT`, `FLD-TASK-SUMMARY`, `EVOLVE-REFERENCE-NOTE`.

The note is required, non-null, non-Nullable String; absent/null/non-String rejected. Empty String permitted; no length/nonblank constraint is invented. Preserve exact UTF-8 scalar bytes, without normalization or any default. New writes must not copy the retained-row backfill implicitly.

PostgreSQL bytea NOT NULL enforces non-null presence, not String or valid UTF-8. Explicit provisioning must validate those proposed rules; no such writer implementation is approved.

Existing update Commands preserve stored notes. Their inputs/assignments do not create a new note or resource. Known seed and clone INSERT writers omit this column and become incompatible after NOT NULL enforcement. All external import/provisioning writers remain to be inventoried.

## Compatibility and rollout

**REVIEW_REQUIRED.** The ChangeSet conservatively declares BREAKING, replacing BACKWARD: old inserts omitting the final NOT NULL/no-default column fail. No runtime compatibility proof is claimed. UNKNOWN cannot produce a prepared plan in the existing fail-closed planner; it has not been bypassed or changed.

1. Expand nullable with no default while compatible old readers/writers run.
2. Backfill only independently approved retained rows; capture byte/tenant inventories.
3. Verify exact bytes and inventory every new-record writer and recovery boundary.
4. Switch reference provisioning to explicit values, fence old insert writers, re-scan rows under writer fencing. Do not activate required-model readers while any nulls remain.
5. Contract NOT NULL only after approved writer/reader compatibility, counts and recovery proof. Resume existing updates and full-admission checks on retained data.

The sealed migration planner emits one migration, not staged traffic orchestration. This rollout needs separately approved exact SQL/deployment support; no implementation or application is performed.

## Risks and decisions

- Final required schema breaks old inserts; nullable expansion alone does not enforce final semantics
- Do not deploy required-model readers against a nullable expanded schema containing nulls
- Public classification is a synthetic proposal; do not store production personal data on that assumption
- A future create Command/input/UI or staged migration support needs separate exact semantic/target approval
- No application resource-create operation is exposed by these approved fixtures
- Staged expand/switch/contract deployment orchestration is not implemented by the sealed single migration planner
- Actual old-writer/new-schema runtime compatibility and revised full admission are unproved
- No approved new-record provisioning validator exists; bytea alone cannot enforce String/UTF-8 validity
- Existing hard-coded seed and clone writers omit the required field
- No real accepted journal anchor, approved binding, exact SQL or deployment receipt is supplied

Review the exact semantic requirement/candidate/ChangeSet, independently review backfill bindings, and decide the writer/compatibility policy separately for this application. Real accepted-history rebasing and exact SQL/deployment decisions remain pending their actual inputs. No approvals are issued by this package.

[Complete machine package](payment-human-review.json) includes source-file hashes, exact operation bindings and acceptance criteria.
