# Batch 03R engineering review

Reviewed source `76dfd874b1a1e5f110b7b86eda2dbefa605323a1`. Original artifact identities and independently computed archive digests are in [original-artifacts.json](original-artifacts.json). An absent downloaded hash indicates that acquisition was incomplete at capture. Repository ID 1371285836 and the exact producing source commit were verified for all five artifact metadata records. Original archives are retained locally under `.audit-artifacts/batch03r/`.

## Failure dispositions

| Job | Classification | Evidence and disposition |
| --- | --- | --- |
| Performance 139675201372 | Dependency acquisition | Payment's retained `rate-regressions/payment/maven.log` contains repeated HTTP 429 for Maven Central metadata and Spring Boot 4.1.1 parent POM. Maven failed during POM model construction before the InvocationCoreTest or RateClockTest assertions. |
| Recovery 139675201454 | Dependency acquisition | Payment's retained `payment-logs/compile.log` contains HTTP 429 for the same parent POM during `test-compile dependency:build-classpath`, before the fresh-JVM recovery scenario. |
| H6 139675200098 | Generated database concurrency | The redacted failure packet records PostgreSQL `40P01`. The shared SQL generator queues deferred relation constraint triggers on both endpoint tables and the edge table. Each trigger attempts ordered `FOR UPDATE` across both endpoint tables after writes and FK checks can already hold conflicting locks. Sorting those scans does not impose a transaction-wide acquisition order. |
| Closure audit and aggregate | Release gate | The retained aggregate separates engineering validation from release acceptance. The audit ran and retained `PHASE6_CLOSURE_BLOCKED`. |

## Implemented remediation

Performance and recovery each depend on the existing same-run dependency determinism producer. Each consumer verifies the complete 832-entry Maven repository before introducing it into execution and selects it in Maven offline mode with the existing settings. Test commands, workload definitions and acceptance thresholds retain their existing behavior. Missing, substituted or incomplete inputs fail before application qualification. Maven Central remains the upstream availability dependency of the producer.

Same-run verified transfer is preferred for ordinary qualification because it removes historical Actions artifact expiry and preserves producer scope without a new service. A content-addressed immutable store would improve upstream outage resilience. Provisioning requires an authorized location, write custodian, read-only runner principal, retention period, restore tests and cost acceptance. Use the existing lock and producer receipt in either case.

## Local validation

With the exact retained Maven inputs reverified and a fresh disposable PostgreSQL environment, Payment passed 18 and Case Management passed 19 InvocationCore/RateClock tests, with zero skips or failures and owned database cleanup. The focused Python performance and recovery suites passed 14 and 12 tests respectively. All 39 preservation tests passed. Workflow parsing and a normalized comparison confirmed that the new dependency and preflight steps leave the existing qualification commands intact.

## Concurrency decision

Target SQL originates in `targets/spring-vue-postgres/worker/relations.py:36–49`. Removing locking without a substitute risks snapshot races. Broad transaction serialization reduces unrelated tenant concurrency. Per-parent or relationship coordination can preserve unrelated work if all writers participate and acquire the complete affected key set before conflicting writes. It must cover old and new endpoints, multi-relationship order, FK interactions and supported isolation levels. A retry may be safe after a confirmed rollback only after its idempotency and external effect boundaries are proven. An unknown commit outcome requires reconciliation.

H6 remains open. No generated SQL correction or before-and-after concurrency qualification is recorded here. Changing installed trigger definitions requires a separately tracked successor migration that preserves historical files and checksums. Qualification requires separate database sessions, multiple application instances, rollback and replay, invariant checks and independent-tenant concurrency across the existing profiles.

## Closure reconciliation

The full closure report contains 39 criteria and 21 blockers. Every outstanding row in the retained closure summary reports `MISSING_EVIDENCE`. Candidate engineering work can support #8, #9, #10, #14, #15, #18, #24, #25, #30, #31 and #32. Independent execution or specialist evidence is still required for #12, #13, #20, #21, #22, #27, #28 and #33. #5 requires accepted semantic history, independently approved data bindings and deployed evolution evidence. #26 requires deployment authority and obligation evidence. Applicable sealed-release witnesses require exact release binding and authorized admission. No criterion changed.

SEC-01 and SEC-02 remain BLOCKED. Phase 6 release closure remains BLOCKED. Phase 11 remains IN_PROGRESS. Phase 12 remains NOT_STARTED.
