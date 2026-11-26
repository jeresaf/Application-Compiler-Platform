# Batch 03R cardinality component checkpoint

Baseline `3073f144eefbc79f7643960bc66da0c153966b22`.

A successor runtime component now acquires tenant coordination on the connection bound to an existing writable READ COMMITTED transaction. The disposable PostgreSQL test verifies transaction and isolation rejection, contention on an independent connection, separate tenant and application keys, and lock release on commit and rollback. Run it using the existing verified offline recovery build classpath and the owned container runner in `verification/cardinality/run.py`.

This is component qualification. The component is outside the active generator bundle and has no production callers. No historical SQL, sealed target, migration, permission contract, or authentication check changed. An advisory key is a coordination mechanism and conveys no authorization.

The unresolved critical path is to enforce participation before existing endpoint locks in generated invocation and lifecycle transactions, including independent writers and lifecycle's separate transaction boundaries. The generated deferred validation and additive migration remain unchanged. The component test does not reproduce the historical deadlock or establish corrected transaction outcomes, retained-data compatibility, or application-scale performance.

Batch 03R remains PARTIALLY_QUALIFIED. SEC-01, SEC-02, and Phase 6 release closure remain BLOCKED. Phase 11 remains IN_PROGRESS. Phase 12 remains NOT_STARTED.
