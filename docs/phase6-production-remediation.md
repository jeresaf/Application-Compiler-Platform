# Phase 6 production remediation — first corrective tranche

Status: IN_PROGRESS. Phase 6 remains IN_PROGRESS. Phase 7 is NOT_STARTED.
Reviewed baseline: `7e4e3438179e7a446c5f3737ad1d6d9cb07a96ea`.
Corrective branch: `codex/phase6-production-remediation`.

The first blocked closure audit, its findings and its original machine record
remain historical evidence at `phase6-final-closure-audit.md` and
`targets/spring-vue-postgres/evidence/phase6-final-closure.json`. They are not
rewritten by this tranche. Hosted run
[37910102322](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/37910102322)
performed that audit: contracts, phase5-experiments, phase5c-hard-gates and
phase6-target passed; phase6-closure-audit deliberately exited 2 with
PHASE6_CLOSURE_BLOCKED. The overall hosted run was blocked, not successful and
not an unexplained compiler failure.

## Release and compatibility

Target `acp-spring-vue-postgres/0.5.0` and generator
`acp-spring-vue-generator/0.5.0` are an intentional output-affecting successor.
All prior registry entries are preserved. Target IR stays at 0.2.0: runtime
configuration enforcement and storage correction change generated implementation,
not the meaning or structure of that compiler contract. Admission contract 5.0.0
and approved Canonical/ChangeSet/Authoring bytes are unchanged.

Policy C remains in force. The production target evolution window explicitly
allows 0.2.0, 0.3.0 and 0.4.0 to 0.5.0, subject separately to exact accepted
semantic/migration authority and storage compatibility. Target 0.1 is excluded;
its retained reader adapter is forensic/test-only. This window does not authorize
an arbitrary semantic change or an unapproved data binding.

## Storage and authority

The planner chooses semantic compatibility, scalar storage, relationship forms
and approved backfill encoding separately. Canonical 0.3 String additions use
bytea with exact UTF-8 backfills. Optional Nullable fields retain an independent
presence column; optionality and nullability are not collapsed. Existing String
columns with incompatible PostgreSQL storage cause an explicit migration failure.
No backfill is inferred. The PostgreSQL test suite uses synthetic test authority
and labels that scope explicitly.

The deployed 0.4→0.5 release journey keeps both existing approved snapshots
unchanged, commits old application state, upgrades without cleaning and checks
new behavior and origin retention. It does not manufacture a semantic ChangeSet.
The new String addition/backfill cases lack human business approval and cannot
satisfy the full accepted semantic-evolution closure criterion. Existing approved
reference authority remains bounded to its exact recorded digests.

## Dependency correction

Spring Boot 4.1.1 imports both Jackson BOMs. The successor overrides its
`jackson-2-bom.version` to 2.21.7 and `jackson-bom.version` to 3.1.7 rather than
mixing individual module versions. The direct Jackson 2 databind declaration
inherits that BOM. Patched versions are established by upstream advisories,
including [jackson-core](https://github.com/FasterXML/jackson-core/security/advisories/GHSA-7hhh-6rmp-j9qf)
and [jackson-databind](https://github.com/FasterXML/jackson-databind/security/advisories/GHSA-cxp5-3px4-pw24),
and Boot's [dependency-management contract](https://docs.spring.io/spring-boot/how-to/build.html).
Resolved Maven graph, packaged JAR inventory, SBOM, fresh scans and individual
advisory dispositions must be retained before claiming remediation. Build-plugin
and compiler security coverage and legal review remain separate obligations.

## Production runtime contract

`acp-runtime-configuration/1.0.0` selects a PostgreSQL, HTTPS OIDC,
trusted TLS proxy and single-instance PostgreSQL-claims scheduler profile.
The packaged resource lists required properties. Job credential handles and
principal adapters remain deployment owned. Active delivery requires a transport
adapter at startup. Configuration validation precedes activation and polling;
production cannot disable polling to bypass it. No default credentials are emitted.

Explicit `acp.runtime.mode=development` with polling disabled supports isolated
integration fixtures. It is not production startup evidence. Enabling polling in
development still requires complete valid runtime configuration and transport.
Proxy-network restriction, TLS operation and provider assurance require deployment
verification; declaring properties does not verify external infrastructure.

`fixtures/deployment-oidc/identity.ts` is a HUMAN_OWNED integration example using
issuer discovery, authorization-code PKCE, state and nonce. Its token and identity
hints are disposable in the integration exercise; backend signature, issuer,
audience, expiry, permission and tenant validation remain authoritative. Production
provider acceptance and identity assurance still require review.

## Audit gate

Each criterion declares required evidence, a verifier, pass/block conditions,
exact failure reason, deployment disposition and evaluation provenance. Files
must exist, match hashes, belong to the criterion and bind current approved
inputs, approval record, execution commit and sealed bundle. Evidence expires;
self-reported PASS is ignored. Deployment obligations require an externally
accepted human review digest, never a runner-created approval.

Exit 1 represents an audit execution exception. Exit 2 represents a performed
blocked closure recommendation. Dedicated CI preserves both machine evidence
and artifacts on either outcome and has no continue-on-error waiver. The
successor audit uses a new evidence identity. Results below distinguish observed runtime evidence, later reporting review and hosted execution.

## Corrective tranche results

**PHASE6_CLOSURE_BLOCKED — audit PERFORMED, exit 2, no execution exception.**
Phase 6 remains **IN_PROGRESS**; Phase 7 remains **NOT_STARTED**. This is the
first corrective tranche, not production readiness or a closure request.

Target `acp-spring-vue-postgres/0.5.0` and generator
`acp-spring-vue-generator/0.5.0` are sealed at
`ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb`.
Target IR remains `0.2.0`; its contract and meaning did not change. Admission
contract `5.0.0`, all prior release entries/digests, approved Canonical content,
and the first blocked audit files remain unchanged.

The [successor admission record](../targets/spring-vue-postgres/evidence/phase6-remediation-admission.json)
and [new closure evaluation](../targets/spring-vue-postgres/evidence/phase6-remediation-closure.json)
retain separate identities. Strict full admission executed at `1abbf0d` with the
same immutable bundle; the completed audit coordinator executed at `8510c2c` and
independently revalidated reused admission. Reporting review is separately bound
to `bb4f306`. These are not claims that runtime tests executed at a later evidence
commit. The release-upgrade helper's captured source digest matches `054cf55`,
committed after the running coordinator's HEAD; this qualification is retained
in raw `local-validation.json`. The fresh hosted run below used the committed `f3b74bf` sources.

Local Linux results:

- Complete Python suite: **250 tests, PASS**, one PostgreSQL-only skip; the
  database case separately passed against actual PostgreSQL 18.6.
- Migration and adversarial closure regressions: **15 tests, PASS** (three
  migration cases and twelve evaluator cases), including UTF-8/non-normalized
  Unicode/U+0000, optional/nullable presence, required-field verification,
  transactional rollback, stale/invalid bindings and incompatible storage.
- Both exact approved applications: **zero capability blockers**, strict full
  admission PASS, **149 backend tests**, frontend typechecking/tests/production
  builds, **24 primary Chromium journeys** and **16 supplemental HTTP journeys**.
- Disposable authorization-code PKCE / RS256-JWKS integration: **four Chromium
  executions**, covering identity changes, wrong-tenant queries and expired
  access tokens against the real generated backend.
- Fault/materializer/ownership/history/approval suite: **38 tests, PASS**.
- Real sealed 0.4.0 → 0.5.0 release evolution: old invocation committed,
  every existing domain/runtime row preserved, zero Flyway migrations,
  successor invocation committed, **67 compiler-origin mappings compared per
  application**, and the explicit human identity-extension adoption checked
  separately. This does not approve a new semantic ChangeSet or backfill.
- Independent Node canonical checks: all three profiles PASS, each with nine
  positive vectors, thirteen negative vectors and two snapshot hashes.
- Repository checks, dependency consistency and whitespace checks: PASS.

The initial full Python attempt exposed a stale active-release assertion; the
corrected complete run above passed. Earlier OIDC fixture contamination and a
clean-checkout audit exception are retained under raw `attempts/`, not relabeled
as successful executions. The final audit completed all producers successfully.

## Rebuilt packages and security

Both packages repeated byte-for-byte in the same checkout/cache and passed the
production test-authority exclusion check. Independent clean builds remain a
separate blocker. No browser-test authority, disposable issuer, credential or
integration private key is included in production output.

| Application | Package SHA-256 | Bytes |
| --- | --- | ---: |
| payment | `497cf43fbaf2ad0d7cb49b048238d146c95714271b7073f1f8c6a3d94a933d73` | 33587200 |
| case-management | `e41e3af40cd1532a6d76a192eea0b908a1e38b180f4a036c6457344ff8613670` | 33699840 |

Fresh Maven dependency graphs, packaged JAR inventories and CycloneDX SBOMs
record **188 components per application**. Actual Jackson core/databind are
**2.21.7 and 3.1.7**, coherently selected through Spring Boot BOM properties;
Jackson annotations retain their BOM-selected version 2.21. Fresh OSV runtime
queries report **zero matches** and npm production assessments report **zero
findings** for both packages. All seven prior advisories (five HIGH, two MODERATE)
are retained with `REMEDIATED_IN_PACKAGED_RUNTIME` dispositions in the
[dated security review](../targets/spring-vue-postgres/evidence/phase6-remediation-security.json).
These are runtime-scope observations, not a universal security guarantee.
Compiler/build-plugin vulnerability coverage, complete transitive locking and
license/notices review remain unresolved. No suppression or reachability waiver
was applied.

Raw logs, original reports, exact plans, browser/JUnit evidence and production
tars are retained locally under `.audit-artifacts/phase6-remediation-0.5.0/`,
ignored by Git. The new machine report binds the raw archive SHA-256 and each
entry digest. `/tmp` files are ephemeral; committed summaries and the retained
workspace archive are the durable local evidence. CI uploads its own artifacts.

## Remaining closure requirements

The new evaluator reports **21 blocked criteria**. Each has a declared verifier,
evidence contract, failure reason and input/execution/evaluation binding. Missing
criterion-specific evidence remains blocked even when a broader suite passes.
Runtime security evidence is explicitly partial: criterion 21 rejects it with
`INCOMPLETE_SECURITY_COVERAGE`. Human deployment dispositions are never accepted
through self-reported statuses.

| Criterion | Remaining requirement |
| ---: | --- |
| 5 | **Accepted-history deployed evolution**: A deployed target-release evolution of unchanged approved snapshots is separate from accepted semantic evolution. Synthetic String/backfill witnesses are not new human business approvals; a complete accepted ChangeSet/data-binding deployment chain remains required. |
| 8 | **Integrated ownership**: Actual compiler replacement/human identity preservation/unapproved AI rejection plus retained approved AI/framework/CAS/unknown-file tests. Complete integrated cross-owner transition matrix remains incomplete. |
| 9 | **Provenance completeness**: Exact ArtifactPlans retained separately from conservative sidecar origin sets. Host per-artifact revisions checked; exhaustive target-object bijection/input-digest reconciliation and HUMAN-owned artifact provenance remain incomplete. |
| 10 | **Traceability**: Machine-readable family→basis→ID/revision→host-artifact trace exists; suite-level runtime links do not prove a per-object assertion chain for every representative. |
| 12 | **Manual accessibility**: MANUAL_ACCESSIBILITY_REVIEW=OUTSTANDING; permitted before deployment, not represented as automated evidence. Human acceptance of this disposition is still required. |
| 13 | **Browser support**: SUPPORTED_BROWSER_PROFILE=CHROMIUM only; Firefox/WebKit OUTSTANDING, not supported by this audit. |
| 14 | **Deployable package**: Versioned startup configuration is implemented. Deployment-owned identity/principal/transport wiring, external TLS/proxy operation and production provider acceptance still require complete deployable-profile evidence. |
| 15 | **Container/package profile**: Chosen audit package is a reproducible JAR+static-assets tar, not OCI. Java 21/Node generation environment bound; no image digest or portable architecture/container guarantee claimed. |
| 18 | **Transitive dependency inventory**: Package JAR dependencies, npm lock and Python distributions inventoried. Maven plugin/build graph checksums and full transitive immutable resolution lock not complete; inventory alone is not a lock. |
| 20 | **License review**: License declarations inventoried; unknowns/redistribution notices and compatibility require resolution and human/legal review. No automatic legal approval. |
| 21 | **Current vulnerability assessment**: npm audit and OSV timestamped runtime assessments are independent of deterministic package bytes. Missing/unscored/high/critical findings block closure; exact results in package evidence. Compiler/build-plugin vulnerability coverage is incomplete even if runtime scanners return zero findings. |
| 22 | **Worker confinement**: Retained real sandbox/protocol/resource supervision tests rerun. Exhaustive process/identity/clock syscalls plus memory/CPU exhaustion under the production sandbox are not all exercised by existing tests. |
| 24 | **Deployment migration failure/recovery**: Actual PostgreSQL String/backfill/presence/required/transactional rollback and incompatible-storage regressions supplement existing Flyway upgrade checks; the complete unavailable-DB/partial-upgrade/safe-retry deployment matrix remains required. |
| 25 | **Real application restart matrix**: Lost-process idempotency/outbox/Job/lifecycle runtime tests exist. A complete real process restart with all specified committed state simultaneously is not proven. |
| 26 | **Deployment obligations**: Every generated OUTSTANDING row retained and classified in domain evidence; none waived. Release blockers are separately enumerated. |
| 27 | **Encryption/TLS**: At-rest, backup encryption, TLS termination and key management remain REQUIRED_BEFORE_PRODUCTION_DEPLOYMENT; not runtime guarantees. |
| 28 | **Physical destruction**: ANONYMIZE does not establish physical erasure, WAL/replica/backup destruction; retained deployment obligations. |
| 30 | **Performance baseline**: Build durations/package sizes are measured; bounded Query/Action/startup/browser-load/concurrent-rate performance measurements are not complete. No synthetic SLO promised. |
| 31 | **Resource scaling**: Approved fixtures within limits pass; no larger valid generated UI fixture/node-limit scaling and provenance-growth curve accepted. |
| 32 | **Generation/package determinism**: Independent compiler contexts compare ArtifactPlan digest and repeated package builds compare exact bytes. Package builds share the same checkout/build cache; two independently materialized clean package builds are still required. Runtime random keys excluded. |
| 33 | **Hosted-result binding**: the local evaluation predates the completed hosted run below. Hosted execution is now verified separately; a criterion-specific reevaluation is still outstanding. |

The accepted semantic-evolution boundary is explicit: no human approval for the
new String fields/backfill values exists. PostgreSQL regression fixtures are
synthetic test witnesses. The actual unchanged-semantics target upgrade does not
substitute for an accepted ChangeSet/data-binding deployment chain.

## Successor hosted validation

The historical reviewed run `37910102322` remains distinct: ordinary jobs passed,
closure audit performed and deliberately exited 2. Subsequent corrective run
`37927888281` passed contracts and both Phase 5 jobs, but its ordinary target job
failed a stale 0.4.0 assertion in the sealed 0.3 upgrade harness; its closure job
was skipped. That failure is not an intentionally blocked closure result.
The harness now checks the sealed active successor and supported production
upgrade policy while retaining row/migration/frontend/ownership assertions.
Corrected [Ubuntu run 38024839562](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/38024839562)
executed `f3b74bfeadb2614bf0feeaf320707acede730e95` on 2026-10-10.
`contracts`, `phase5-experiments`, `phase5c-hard-gates` and `phase6-target` all
**passed**. The dedicated closure job recorded **PHASE6_CLOSURE_BLOCKED** at
05:42:54 UTC and **deliberately exited 2**; advisory retrieval and artifact upload
passed. The overall GitHub workflow conclusion is **failure**, correctly
reflecting blocked closure, not an unexplained compiler failure. No waiver or
continue-on-error was introduced.

The corrected sealed 0.3.0 → 0.5.0 upgrade also passed locally for both domains:
all stored rows and V1/V2/V3 bytes remained exact, Flyway applied zero migrations,
frontend typechecks/tests/builds passed and the explicit human identity
customization survived regeneration. This supplements the sealed 0.4.0 → 0.5.0
journey above.

The local evaluation predates the completed hosted observation. Its criterion
33 remains `MISSING_EVIDENCE` for the registered hosted-binding witness; the
subsequent hosted execution is now verified and retained separately. This report
does not silently rewrite the earlier criterion status or imply closure approval.


[Hosted machine evidence](../targets/spring-vue-postgres/evidence/phase6-remediation-hosted.json)
binds the exact GitHub run/source, all job results, performed audit/exit 2,
criterion dispositions, fresh hosted package/SBOM/security observations and
GitHub artifact `11660244558`. The downloaded archive's SHA-256 was independently
verified as `95c35d3d287d85e7e1bd3a651a238017994378a9824b5ee9866e9ad4da009f13`.
The complete hosted archive and workflow logs are retained under the local
ignored evidence directory. Hosted scans at 2026-10-10 05:42 UTC also found zero
OSV runtime matches and zero npm production findings. All seven historical
advisories retain runtime remediation dispositions.

Hosted and local production packages have separately recorded digests. Their
repeated-build checks are within their respective checkout/cache; no cross-host
byte equality or independent-clean reproducibility PASS is inferred. The hosted
closure evaluation also records 21 blocked criteria and no execution exception.
Stop after this corrective tranche for review; no Phase 6 closure is requested.
