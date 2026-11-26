# Batch 03R writer participation and recovery

Baseline `16e6eb6ba6761615c0abe8a151a8925423cb5ac5`. V11 adds migration-owned participation records. Existing V1–V3 and V10 SQL are retained. An eligible writer must enter the supported transaction protocol before endpoint locks. Holding an advisory lock alone does not satisfy the writer check. The participation routine rejects a second tenant in the same transaction. Generated 0.3 runtime operations use the existing tenant authorization independently of coordination.

The disposable writer regression verifies denied writes to the participation record, a successful coordinated write followed by rollback, and rejection of an already-connected retired role after revocation. This is a controlled role-handoff qualification, with no operational principals or grants enrolled. Deployment still requires non-owner runtime and migration principals, reviewed exact grants and a stopped-writer cutover. Arbitrary explicit SQL pre-locking and privileged changes are outside the qualified writer contract.

Both generated applications passed bounded contention and application smoke checks. Both V10 transactions were interrupted after executing the migration but before commit. Their changes rolled back, and exact V10 could then be installed. Payment additionally rejected invalid retained relationship data without applying V10. Both applications started with their expected Flyway migration sequence.

The cardinality candidate delegates authenticated history and binding checks to the existing semantic upgrade planner. It supports otherwise valid Canonical 0.3 additive field plans that do not need a bulk backfill on guarded tables. Guarded backfills require a separately coordinated write plan. The local planning tests use synthetic history and confer no approval.

The existing recovery runner now takes an explicit cardinality option. Historical default selection and assertion thresholds remain in force. H3, H6, the complete performance profile, and R8 have not qualified the corrected candidate. Scope remains QUALIFICATION_ONLY and Batch 03R remains PARTIALLY_QUALIFIED.
