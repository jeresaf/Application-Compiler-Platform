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

The audit-only delivery fixture uses a separate scheduler observation clock immediately after the original occurrence while keeping the invocation clock aligned with real PostgreSQL commit timestamps. Exact occurrence identity and the count of non-skipped occurrences are still asserted. Production scheduler semantics and bundled historical test source are unchanged.

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

**PHASE6_CLOSURE_BLOCKED — audit performed.** No human closure approval is implied. Phase 6 remains IN_PROGRESS; Phase 7 remains NOT_STARTED. No push was performed.

The final runtime audit executed from `2184cb334889fa04ad281838768d8080c813a0f6`. Reporting-policy review is separately bound to `bc665e35218e6125c7b1c53cb1eec27951338fd5`; it tightens criterion 32 without changing observed runtime evidence. The later evidence commit records results and is not represented as the browser source commit. The audit exited **2 intentionally**, with no execution error.

Both unchanged approved applications negotiated with **zero capability blockers** and passed full admission. Fresh local results: **145 backend tests, 24 main browser journeys, 16 supplemental HTTP/browser journeys and 38 worker/materializer/ownership/history/approval tests passed**. Automated axe evidence remains distinct from outstanding manual review.

Each application package reproduced byte-for-byte in two builds and passed the test-code exclusion gate. These builds shared a checkout/cache; independent clean package reproduction remains **BLOCKED**, not inferred from these results. The distribution contains a configuration inventory, not a complete enforced production configuration schema.

| Application | Package SHA-256 | Bytes | SBOM |
| --- | --- | ---: | --- |
| payment | `f9ffc1a2c04d51e2ba8eb44650194d86771464b93d780177b84e5364bd823bbb` | 33566720 | [CycloneDX](../targets/spring-vue-postgres/evidence/phase6-final-payment-sbom.cdx.json) |
| case-management | `0eed486f966012782eb52f156cdf3a04bc17977580eaf3422bd3590ca97f1efc` | 33679360 | [CycloneDX](../targets/spring-vue-postgres/evidence/phase6-final-case-management-sbom.cdx.json) |

Package files and the raw evidence archive are retained locally under `.audit-artifacts/phase6-final-closure/` and ignored by Git. Their digests and archive-entry hashes are bound in the [machine report](../targets/spring-vue-postgres/evidence/phase6-final-closure.json). `/tmp` logs remain ephemeral. The dedicated CI job will retain packages and raw evidence when explicitly pushed and run; no fresh hosted audit is claimed.

### Security and license disposition

Production npm audit returned zero findings. OSV returned **14 package/advisory matches per application**, representing **7 distinct advisories: 5 HIGH and 2 MODERATE** across Jackson 2.21.5/3.1.5 core/databind. The versioned PURL query follows the [OSV batch API](https://google.github.io/osv.dev/post-v1-querybatch/). [Core HIGH advisory](https://osv.dev/vulnerability/GHSA-7hhh-6rmp-j9qf) and [databind HIGH advisory](https://osv.dev/vulnerability/GHSA-cxp5-3px4-pw24) affect the packaged versions. Dated advisory records, affected ranges, severities and CVSS data are in the [security evidence](../targets/spring-vue-postgres/evidence/phase6-final-security.json). No reachability waiver or dependency upgrade was applied.

Each application inventory contains 188 backend/frontend components, including development tooling distinguished from runtime dependencies; 54 components lack a captured license declaration. Unknown declarations do not prove incompatibility, but complete notices/redistribution review is unresolved. Maven build-plugin/transitive locking and generation-tool vulnerability coverage are incomplete. No legal approval or universal security guarantee is claimed.

### Required corrective tranche

1. Create a deliberate successor for actual production defects: Canonical 0.3 migration/backfill storage, affected Jackson dependencies, and startup configuration/transport admission. Do not mutate sealed 0.4.0 or change approved business semantics.
2. Prove the complete applicable accepted-history deployment chain, including explicit authorization/backfills, migrations, post-transition backend/frontend behavior, ownership and provenance; independent legacy upgrade tests are insufficient.
3. Complete the non-test OIDC integration fixture, exact provenance/runtime trace reconciliation, ownership-transition matrix, migration failure and real-process restart matrices, remaining sandbox exhaustion/syscall probes, independent clean packaging, dependency/license/security review, bounded scaling/performance measurements and fresh pinned Ubuntu closure-audit execution.

### All requested dispositions

| Requirement | Area | Disposition | Evidence or exact gap |
| ---: | --- | --- | --- |
| 1 | Immutable baseline | PASS | Exact merged baseline and execution commit; clean checkout, protected history and sealed bundle checked. |
| 2 | Release immutability | PASS | No bundled file changes; 0.4.0 retained. Production defects identified here require a deliberate successor. |
| 3 | Full actual admission | PASS | Original strict CLI with --full-admission --run-builds; no expected-blocker allowance. |
| 4 | Integrated final entrypoint | PASS | Audit orchestrates full strict admission, supplemental browser, fault/materializer/history, provenance and package checks; exits 2 for unmet closure criteria. |
| 5 | Accepted-history deployed evolution | BLOCKED | Semantic six-step witnesses and independent upgrades do not prove every accepted deployed transition. Canonical 0.3 backfill storage currently falls through to text instead of bytea; no deployed 0.2→0.3 chain or sequential 0.1→0.2→0.3→0.4 proof. |
| 6 | Historical provenance | PASS | Policy C: target 0.1 excluded from supported production upgrade window. Historical test adapter is forensic evidence only; 0.2/0.3 ordinary reader remains production policy. |
| 7 | Scheduler observation | PASS | Exact occurrence-scoped recovery assertions retain non-skipped count. Separate deterministic scheduler observation is fixed immediately after the original occurrence; invocation clock alone observes actual PostgreSQL commit time. |
| 8 | Integrated ownership | BLOCKED | Actual compiler replacement/human identity preservation/unapproved AI rejection plus retained approved AI/framework/CAS/unknown-file tests. Complete integrated cross-owner transition matrix remains incomplete. |
| 9 | Provenance completeness | BLOCKED | Exact ArtifactPlans retained separately from conservative sidecar origin sets. Host per-artifact revisions checked; exhaustive target-object bijection/input-digest reconciliation and HUMAN-owned artifact provenance remain incomplete. |
| 10 | Traceability | BLOCKED | Machine-readable family→basis→ID/revision→host-artifact trace exists; suite-level runtime links do not prove a per-object assertion chain for every representative. |
| 11 | Production browser review | PASS | 24 production-browser journeys plus 16 exact HTTP outcomes against real Spring/PostgreSQL; report preserves database facts and axe incomplete results. |
| 12 | Manual accessibility | DEPLOYMENT_OBLIGATION | MANUAL_ACCESSIBILITY_REVIEW=OUTSTANDING; permitted before deployment, not represented as automated evidence. Human acceptance of this disposition is still required. |
| 13 | Browser support | DEPLOYMENT_OBLIGATION | SUPPORTED_BROWSER_PROFILE=CHROMIUM only; Firefox/WebKit OUTSTANDING, not supported by this audit. |
| 14 | Deployable package | BLOCKED | Deterministic tar audit binds jar/assets/migrations/profile/provenance/deployment requirements/configuration inventory. An enforced exact startup configuration schema and deployable non-test identity/principal/transport integrations are still missing. |
| 15 | Container/package profile | DEPLOYMENT_OBLIGATION | Chosen audit package is a reproducible JAR+static-assets tar, not OCI. Java 21/Node generation environment bound; no image digest or portable architecture/container guarantee claimed. |
| 16 | Startup configuration | BLOCKED | Database/OIDC placeholders and Job principal/handle guards exist. Missing delivery transport is deferred to poll-time; explicit scheduler/TLS/proxy validation and configuration schema enforcement are incomplete. Do not modify sealed 0.4. |
| 17 | Test-only exclusion | PASS | Packages rebuilt using restored production identity; inspect archive entries and decompressed JS/class content for BrowserServer, decoder, tokens, test endpoints and credentials. |
| 18 | Transitive dependency inventory | BLOCKED | Package JAR dependencies, npm lock and Python distributions inventoried. Maven plugin/build graph checksums and full transitive immutable resolution lock not complete; inventory alone is not a lock. |
| 19 | SBOM | PASS | CycloneDX 1.6 JSON from actual packaged backend JARs and frontend lock; generation/build-only tools distinguished in evidence. |
| 20 | License review | BLOCKED | License declarations inventoried; unknowns/redistribution notices and compatibility require resolution and human/legal review. No automatic legal approval. |
| 21 | Current vulnerability assessment | BLOCKED | npm audit and OSV timestamped runtime assessments are independent of deterministic package bytes. Missing/unscored/high/critical findings block closure; exact results in package evidence. Compiler/build-plugin vulnerability coverage is incomplete even if runtime scanners return zero findings. |
| 22 | Worker confinement | BLOCKED | Retained real sandbox/protocol/resource supervision tests rerun. Exhaustive process/identity/clock syscalls plus memory/CPU exhaustion under the production sandbox are not all exercised by existing tests. |
| 23 | Materializer | PASS | Retained traversal/symlink/stale-CAS/concurrent-writer/crash/manual/human/AI/framework fault suites rerun. Power-loss durability and hostile same-user mutation remain Phase 11 concerns. |
| 24 | Deployment migration failure/recovery | BLOCKED | Existing migration planner, Flyway repeat/legacy upgrade tests do not cover complete unavailable-DB/validation/partial-upgrade/incompatible-schema/safe-retry deployment matrix. Destructive rollback NOT CLAIMED. |
| 25 | Real application restart matrix | BLOCKED | Lost-process idempotency/outbox/Job/lifecycle runtime tests exist. A complete real process restart with all specified committed state simultaneously is not proven. |
| 26 | Deployment obligations | DEPLOYMENT_OBLIGATION | Every generated OUTSTANDING row retained and classified in domain evidence; none waived. Release blockers are separately enumerated. |
| 27 | Encryption/TLS | DEPLOYMENT_OBLIGATION | At-rest, backup encryption, TLS termination and key management remain REQUIRED_BEFORE_PRODUCTION_DEPLOYMENT; not runtime guarantees. |
| 28 | Physical destruction | DEPLOYMENT_OBLIGATION | ANONYMIZE does not establish physical erasure, WAL/replica/backup destruction; retained deployment obligations. |
| 29 | Production OIDC integration | BLOCKED | Required identity()/onIdentityChange()/accessToken()/permissions() contract documented. No accepted non-test provider adapter fixture proving token acquisition/change notification/configuration end-to-end. |
| 30 | Performance baseline | BLOCKED | Build durations/package sizes are measured; bounded Query/Action/startup/browser-load/concurrent-rate performance measurements are not complete. No synthetic SLO promised. |
| 31 | Resource scaling | BLOCKED | Approved fixtures within limits pass; no larger valid generated UI fixture/node-limit scaling and provenance-growth curve accepted. |
| 32 | Generation/package determinism | BLOCKED | Independent compiler contexts compare ArtifactPlan digest and repeated package builds compare exact bytes. Package builds share the same checkout/build cache; two independently materialized clean package builds are still required. Runtime random keys excluded. |
| 33 | Fresh hosted reproduction | BLOCKED | Dedicated closure CI job added with pinned Ubuntu/Python/Node and Java. Not run while the user instruction forbids pushing. Existing baseline CI success is historical, not current audit evidence. |
| 34 | Historical contracts | PASS | Protected contract/corpus/release/ADR bytes compared against immutable merged baseline. |
| 35 | Human closure authority | PASS | Audit recommendation does not mark Phase 6 COMPLETE; stop for explicit human review. |
| 36 | Recommendation | PASS | Only PHASE6_CLOSURE_BLOCKED or PHASE6_CLOSURE_RECOMMENDED; blocked report lists remediation criteria. |
| 37 | Bound machine-readable report | PASS | Baseline, exact execution commit, Canonical/bundle/IR/UI/migration/package/SBOM/security/browser/fault/history/obligation evidence bound with digests. |
| 38 | Dedicated closure CI | PASS | Separate dependent job; no continue-on-error. BLOCKED audit exits nonzero rather than faking green. |
| 39 | Phase disposition | PASS | Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED; closure cannot be accepted automatically. |

The machine report binds the immutable baseline, exact Canonical/release/bundle/UI/migration/package/SBOM digests, dated security evidence, browser observations, fault/history results and every generated outstanding deployment requirement. Family-level [traceability](../targets/spring-vue-postgres/evidence/phase6-final-traceability.json) is retained without pretending suite-level links are per-object runtime proof. Stop here for human review of this blocked audit and authorization of the corrective tranche.
