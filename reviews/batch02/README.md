# Batch 02 integrated qualification

Baseline `792f7f23a44ca6309977c395dc98938645036071` on `codex/phase11-hardening`. Batch 01 V3 passed all eight jobs. H5 45631338799 and H6 45631338940 returned Maven Central HTTP 429. The main workflow's engineering jobs passed while release closure returned BLOCKED. See the [single delivery register](../batch01/delivery-register.json) for current rows and original requirements.

| Workstream | Delivery and integration boundary |
| --- | --- |
| A | Reuse V3's exact Batch 01 GitHub artifact 15031660633 as a transport. Check its archive SHA-256 and the entire current 832-entry lock before either H5 or H6 consumes it. Maven builds retain their offline mode; npm, browser and image provisioning retain their original paths. A missing, expired or changed archive fails acquisition explicitly. |
| B | Run the existing native R8 disposable R6→R7 pipeline on the integrated branch. Its independent verifier checks actual V5 history, prior row and document identity, writer rejection, browser evidence, idempotency, restore and cleanup. The historical R8 artifact passed this verifier, separately from any new run. |
| C | R8 qualifies stopped/fenced transition and restore only. Pool starvation and pending job growth require distinct observations and decisions. REL-01 stays unattributed. Preserve H9's bounded REL-02 mapping. Mixed writers and physical power loss remain unverified. |
| D | Validate transfer inventory, size and every content digest before Maven use. Retain Batch 01 BOM scope and H11 exposure review. Frontend, shaded code, native shared libraries and legal review remain open. SEC-01 stays blocked on D1–D6. |
| E | Propose staging-profile version 1 for one disposable Spring/Vue/PostgreSQL environment. Existing synthetic identity, least-privilege roles, readiness, redacted logs and independent restore provide the test baseline. Operational issuer, service principals, trust roots, TLS endpoints, secret delivery, database grants, telemetry destinations, alert owners, encryption, retention, custody, RPO/RTO and release authority require exact owner selections. PITR is conditional on RPO/RTO. |
| F | Qualify exact-source V3 for both domains, R8 for Case Management evolution, H5/H6 for authenticated and operational behavior, and H7 for backup/restore. Retain each job result and release-gate disposition independently. |

Payment's existing V3 lifecycle covers compiler, publication, build, runtime and recovery. A new Payment schema transition requires authentic accepted history, independently approved data binding and migration authority. R8 reuses existing native Source Intelligence, Phase 8 and read-only MCP operations. Cross-baseline native analysis and broader MCP change previews remain outstanding.

## Integrated test matrix

| Check | Evidence or gate |
| --- | --- |
| Compiler, publication and stale-source rejection | Existing Batch 01 checks for both domains |
| Case Management semantic preview, migration, authenticated runtime, recovery | R8 actual disposable qualification plus independent evidence verifier |
| Payment authenticated runtime, state and recovery | V3 reference demonstration and runtime; schema evolution BLOCKED |
| API, browser, job and migration compatibility | R8 stopped/fenced scope; mixed-version operation NOT_RUN |
| Capacity and bounded failure | V3 performance, H3/H4 and H9; unresolved historical CREATE cause |
| Security and configuration | H5/H6, H10 disabled execution, V3 security readiness |
| Supply chain and evidence | Maven transfer negative tests, V3 determinism and H11.2 scope |
| Operational acceptance | Staging proposal only; provider, key, recovery and deployment decisions BLOCKED |
| Closure | Existing release predicates continue to govern |

Critical path is verified inputs, exact-source builds, disposable R8 and Payment execution, independently verified evidence, then owner decisions for expanded compatibility or production scope. Batch 03 priorities are durable verified-input distribution, Payment evolution authority, reproducible attribution and approved overload/recovery targets.
