# Phase 6 final closure audit

Phase 6 remains **IN_PROGRESS**. Phase 7 remains **NOT_STARTED**. This audit cannot close Phase 6 automatically. The merged task-interface baseline is `db5d03dcc0763a62b3150d9b485581b163e89435`; main has not been pushed.

The sealed target and generator remain 0.4.0, Target IR 0.2.0 and admission contract 5.0.0. Bundle `61c4647cfbe38cdbd97d03305685b3903f3ff24cfdb20d7c5b4502b478a0e06a` and all approved Canonical/ADR/contracts/migration bytes must remain unchanged. Audit-only code lives in `tooling/audit/`, outside the bundle's top-level `tooling/*.py` glob.

## Reproduction and strict-gate relationship

From a clean audit checkout with the Linux prerequisites and a disposable PostgreSQL 18.6 database with commit timestamps enabled:

```bash
ACP_TEST_DATABASE_URL=jdbc:postgresql://127.0.0.1:54339/acp_test \
ACP_TEST_DATABASE_USER=acp_test ACP_TEST_DATABASE_PASSWORD=ephemeral-test-only \
.venv/bin/python3.14 tooling/audit/phase6.py --output /tmp/acp-phase6-final-audit
```

Use a fresh output directory. These are disposable test credentials, never generated production configuration. The entrypoint invokes the existing strict target CLI with `--full-admission --run-builds`, including all compiler phases, real materialization, backend/frontend builds, PostgreSQL and production-build browser journeys. It then runs the supplemental exact-HTTP browser suite, retained worker/materializer/ownership/history tests, host-plan traceability, historical negotiation probes, deterministic packaging and supply-chain assessment. There is no expected-blocker allowance. Earlier ordinary strict behavior remains historical; the final closure entrypoint composes full admission with the additional closure criteria, without changing bundled gates.

Exit **2** means `PHASE6_CLOSURE_BLOCKED`, not a successful target release. The dedicated `phase6-closure-audit` Ubuntu job depends on the retained contracts, Phase 5 hard gates and Phase 6 target job. It uploads evidence even when closure is blocked and uses no `continue-on-error`. Its hosted execution remains outstanding while the instruction not to push applies.

## Explicit compatibility and deployment policies

Historical provenance policy **C** is chosen: target 0.1 and sidecar 0.1 are outside the supported production upgrade window. The historical 0.1 adapter is retained only for forensic regression evidence; it is not a production migration tool. The ordinary reader supports sidecars 0.2/0.3. This narrows the production claim; it does not rewrite or invalidate historical tests. A future decision to support 0.1 directly requires a deliberate successor if bundled production tooling changes.

`SUPPORTED_BROWSER_PROFILE = CHROMIUM`. Firefox and WebKit remain outstanding. `MANUAL_ACCESSIBILITY_REVIEW = OUTSTANDING`; the audit proposes treating it as required before production deployment, subject to human acceptance of that disposition. Axe cannot satisfy manual review.

The audit distribution contract is a reproducible JAR plus frontend static-assets tar, not an OCI image. Two clean compiler plans and two package builds are compared. Packages bind migrations, target profile, provenance, deployment requirements and an explicit configuration inventory. That inventory is **not** a complete enforced startup schema. Java runtime provisioning, static hosting, TLS/proxy/CSP and non-test identity/principal/transport integrations remain deployment responsibilities. No deployable reference package is represented as production-ready.

The production frontend identity contract requires `identity()`, `onIdentityChange(listener)`, `accessToken()` and `permissions()`. Token acquisition must use a trusted deployment provider; notification must occur on login/logout, subject, tenant, actor and session changes and return an unsubscribe function. Permission hints affect presentation only. The backend validates issuer/audience/session/tenant and remains authoritative. The generated default intentionally fails closed. A non-test provider fixture is still a closure requirement.

Every generated outstanding requirement is retained and classified. Encryption at rest, TLS termination, key management, backup encryption, classified exporter behavior, backup/WAL/replica lifecycle and physical destruction are not target runtime guarantees. Application anonymization does not prove physical erasure. Manual/license review remains explicit. Power-loss durability and hostile same-user mutation remain Phase 11 concerns.

## Findings requiring a corrective tranche

The audit's synthetic Canonical 0.3 required-field planning probe produces a `text` column, while current generated String storage is `bytea`. `target_migrations.plan_upgrade()` selects execution storage only for Canonical 0.2. This is an actual production migration-planning defect. **Stop at the audit finding:** do not mutate sealed 0.4.0. A deliberate successor is required before implementing a correction.

The largest unmet criterion is deployed accepted-history evolution: authorization, exact old/new snapshots, backfills, applied migration/preconditions, regenerated frontend, behavior, ownership and provenance must be proved across every applicable transition. Semantic six-step history and independent target upgrades do not satisfy this chain. Other release gaps include startup configuration/transport validation, a non-test identity integration fixture, full provenance/runtime trace reconciliation, complete deployment failure/restart matrices, transitive resolution/license/security review, scaling/performance evidence and fresh hosted audit execution.

The machine-readable report will enumerate all 39 requested dispositions and bind the execution commit, actual evidence and precise remediation. Its execution commit identifies the code/browser run; any later evidence-only commit records the report rather than claiming it was the run's source commit.

## Audit execution result

Execution pending. No closure recommendation is accepted, and no Phase 6 completion status has changed.
