# PAYMENT — independent retained-data binding review

**REVIEW_REQUIRED. No data-binding approval is recorded.**

Application: `APP-FIXTURE`. Owner: `ENT-PAYMENT`. Field: `EVOLVE-REFERENCE-NOTE`.

Semantic content decision: `sha256:e16442cb591899fcb392682770793a5984c9e8a6b7fa7577dd813ba5d664083f`. This does not approve this data value.

Proposed value (escaped JSON): `"e\u0301\u0000\ud83e\udd8b'"`; UTF-8 hex `65cc8100f09fa68b27`, 9 bytes.

Binding digest: `sha256:2a584b4d5ca471d1f1686db24e3b094e1a91f7e69e4d9f4775fcad1607c49481`.

## Population and tenant boundary

Every retained row of owner ENT-PAYMENT in this application reference database, only for tenants and resource IDs explicitly enumerated in the independently reviewed frozen inventory. No production rows.

Database/schema identity, exact tenant and row IDs/counts and inventory digest are PENDING. No population approval can be inferred from fixture names. Every selected retained row would receive the same synthetic scalar; no unselected row may change.

Only exact synthetic tenants enumerated in the future inventory; names such as tenant-one/tenant-two are test examples, not authorization or a production allowlist

Synthetic Unicode/NUL byte-preservation witness only, not a business note or production tenant default

## Unicode, presence and future writes

Store exact UTF-8 bytes in bytea; never normalize composed/decomposed accents, strip NUL, trim text or reinterpret as SQL text

Old schema absence, transitional SQL NULL, final required non-null String and explicit empty String are distinct states. Empty String remains valid; this proposed value is nonempty. Raw bytea NOT NULL alone cannot enforce valid String/UTF-8; provisioning/application validation needs its own evidence.

This mapping is only a one-time retained-row transformation on the reviewed frozen population. No DEFAULT clause, create input, UI value or future tenant policy is authorized. New writers supply explicit independently chosen values.

## Detecting erroneous backfill

- Compare pre/post row identities, exact tenant counts and unchanged old column/runtime bytes
- Compare encode(new_column, hex) for every selected row to 65cc8100f09fa68b27
- Verify no selected row remains null, no unselected row changed and no new/removed row was hidden
- Verify empty/null/absent negative cases and decomposed-accent/NUL preservation through typed application reads
- Capture exact SQL hash, transaction outcome, row inventory digest and per-object runtime evidence

## Recovery

- Before COMMIT, transactional PostgreSQL DDL/backfill/verification can roll back as a unit if actually executed in one transaction; prove original schema and rows survive fault injection
- Separately committed expand/backfill stages are not undone by rollback of a later transaction. Keep exact stage receipts and fence affected writers
- Inspect actual schema, row inventories and transaction/version receipts before retry; no blind replay
- Reviewed forward repair or verified backup/restore with reconciliation of later committed domain/idempotency/outbox/job effects. No automatic production rollback
- Do not deploy required-model readers over transitional nulls; switch/fence incompatible insert writers before final NOT NULL

## Independent decisions required

- Independent human decision for this application, exact binding digest and exact frozen population
- Bind the decision to the real rebased plan digest and approved Canonical candidate; identical binding digest cannot authorize another application or plan
- Exact SQL/recovery/lock policy and execution/deployment approvals remain separate
- Missing population inputs block execution even if the proposed scalar value is later approved

[Exact machine package](payment.json). No SQL, journal receipt, migration execution or deployment approval is created.
