# Batch 03R disposable writer cutover

Baseline `c9a2c42df04648b6fbefb107e06fad50c955fe28`.

The integrated verifier compiles the old and corrected application for each domain. It migrates with a separate schema owner and runs the JVMs with distinct non-owner identities. The old JVM's effective runtime grants are inherited from a laboratory group. The cutover disables new old-role logins, revokes group membership and checks effective write privileges. It then tests rejection through the still-running old JVM, stops it, verifies that its sessions are gone, applies the successor migrations as the migration owner and starts the corrected JVM. Flyway checksums and committed state are compared before and after cutover. Runtime schema validation uses read-only Flyway access.

The PostgreSQL comparison now interrupts both V10 and V11 before commit and verifies a clean rerun. It also exercises repeated participation and independent tenant progress during contention, and checks the retained coordination row count after rollback and commit.

The accepted-history migration planner supports a guarded backfill when the approved bindings identify a single exact tenant. The SQL requires a stopped writer window through immediate exclusive lock acquisition and verifies the affected table population before entry and backfill. Remaining paths that require multi-tenant transaction support or relationship structure changes fail closed. Synthetic approval ports used by the tests confer no authority.

The cutover runner saves single-sample query and action timings for smoke-test context. Observed baseline→corrected query/action samples were 257→231 ms and 124→171 ms for Payment, and 277→314 ms and 220→332 ms for Case Management. They do not measure serialization overhead against the existing service profiles. H3, H6, full performance, R8 and engineering successor promotion remain open. Batch 03R is PARTIALLY_QUALIFIED.
