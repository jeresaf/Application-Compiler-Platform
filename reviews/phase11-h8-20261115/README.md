# H8 independent hardening gap review

Reviewed application source: `73d48b1e82d4898fe1abb46c25b115185ce6723a`, branch `codex/phase11-hardening`.
Review date: 2026-11-15 (Africa/Kampala). This is an assistant engineering assessment, not an authenticated independent human approval, phase closure, risk acceptance or deployment authorization.

## Conclusions

| Question | Engineering disposition | Reason |
| --- | --- | --- |
| A. H1–H7 bounded engineering qualification | PASS | All seven dedicated workflows passed against the reviewed source. Their actual retained records, source/artifact bindings and observations are reconciled in the evidence matrix. PASS covers the declared laboratory assertions only. |
| B. Original Phase 11 hardening scope | PARTIALLY_VERIFIED | Concurrency, recovery, bounded scale, provenance and supply-chain corrections have substantial evidence. Hostile successor isolation, materializer hostile-host/power-loss behavior, complete compatibility, broad current security acceptance and unresolved HTTP reliability remain gaps. Formal engineering exit is not recommended yet. |
| C. Production deployment obligations | BLOCKED | No accepted production profile, operational identities, custody, transport, recovery objectives or complete G-01–G-23 acceptance. H6 intentionally supports development/loopback only. |
| D. Phase 6 release closure | BLOCKED | Exact-source closure audit performed and exited 2. All 39 individual dispositions are retained; useful candidate evidence does not satisfy sealed-release registration/authority requirements. |
| E. Begin Phase 12 | BLOCKED | H8 does not authorize Phase 12. Resolve material engineering findings, select the production profile and obtain the required explicit approvals first. |

H8 is an audit deliverable, not a new implementation phase. The machine files are observations and recommendations; none is an evidence-admission receipt or authority grant.

## Reading the evidence

- [Evidence matrix](evidence-matrix.json): requirement, implementing/execution commits, generator, Canonical candidate, artifact/member hashes, exact workflow, actual observation, scope, limits and approval needs. Focused tests and real application qualification are separate fields.
- [All production gates](production-gates.json): exact G-01–G-23 identifiers and requirements, target profiles, support, missing evidence, remediation, decision owner and present satisfaction status.
- [All 39 closure criteria](phase6-closure.json): verbatim current audit criteria and predicate requirements, unchanged results, remaining evidence and authorization dependencies, with H1–H7 support mapped individually.
- [Prioritized register](remediation-register.json): separate reliability/security/operational findings, P0/P1/P2, evidence, correction, required tests, dependencies, owner and objective exit conditions.
- [Source and evidence index](source-index.json): authenticated GitHub metadata, archive and selected member digests, implementing source inventories, document/source hashes, preservation checks and review limitations.
- [Proposed status update](roadmap-proposal.md): a proposal only. Historical reports and roadmap are unchanged.
- `SHA256SUMS` binds these seven review files. The preservation guard adds only these exact review paths/hashes; it does not relax any prior pin or release predicate.

## What H1–H7 proves

**H1:** explicit Commons IO 2.22.0 dependencies in actual Maven plugin realms, exact JAR bytes, live HTTPS OSV old/new comparison, native application/browser/regeneration execution. The selected-component PASS does not mean the entire supply chain is clean. Old vulnerable cached components and unrelated findings remain recorded.

**H2:** real overlapping CREATE/upload operations in fresh PostgreSQL, four distinct durable sessions, independently observed database contention, two independent worker JVMs, stale-fence rejection, lease/death recovery, rollback and committed-state replay. It also executes R8 stop–fence–migrate–restart with unchanged V1–V4 and new V5. Trusted-JWT component authentication is explicit; it is not H5 cryptographic evidence. Test-only absolute occurrence selection prevents hour-rollover fixture collisions without changing native scheduling. At-least-once attempts are not exactly-once processing.

**H3:** actual closed-loop 4/8/16-client workloads, independent resource sampling and PostgreSQL correctness; 48 explicitly provisioned worker occurrences, 20 eligible documents/tenant boundary, timeout/crash/shutdown and lease recovery. The 34-connection setting is a bounded test profile, not arbitrary-load admission. Empirical p95/p99 are population-limited, not production SLOs. `ActiveProcessorCount` is not an OS CPU quota. Pending occurrences have no approved finite capacity bound.

**H4:** the external exception observer retains exception classes/SQLSTATE without altering native handlers. Two held connections reproduce a pool-exhaustion 500; four permit real overlap. Explicit replay and independent rows/audits prove recovery without duplicate effects. This does not establish that pool exhaustion caused the historical normal CREATE 500.

**H5:** real RS256 verification using pinned public keys, issuer/audience/time/type checks, key substitution and invalid-token rejection, independently bound principals/tenants, session enforcement, role-claim nonauthority and real supported journeys. Rotation is overlap plus repinning/restart, not automatic remote revocation. Ephemeral issuer TLS validates the fixture issuer; it does not qualify application ingress TLS or a real provider. Integrity workers use host-declared service context; they do not receive fabricated interactive credentials.

**H6:** actual generated H5 successor with closed development operational configuration, health/readiness distinction, database/key/worker failure and recovery, bounded/redacted semantic events, fixed-cardinality metrics protected by JWT, native authorization, loopback and host capability. Real 34-connection overlap remains required. Cold acquisition and hour-boundary fixture failures were corrected externally. Unknown resource paths still return inherited 500. Production networked configuration, alert routing and provider operations remain unqualified.

**H7:** actual PostgreSQL 18.6 custom-format logical snapshot capture while two authenticated writes commit after the boundary; full captured application table population and Flyway history restored into a different cluster. Fresh issuer/session authentication, exact documents/tenants/workflow/audits, four idempotency replays without duplicate effects, still-valid and expired lease behavior, one terminal worker result/audit, independent repeated restore and cleanup are verified. Corruption, missing/substituted components, wrong/nonempty targets, interrupted transactional restore, incomplete state, wrong schema and bad credentials reject. First-response timing and a split-read worker observation race were corrected in the external H7 harness. A single PostgreSQL observation statement now supplies queue/result/audit MVCC consistency; HTTP authentication remains exercised.

These are H1/H5/H6 source-fingerprinted successors, not one identical generator magically tested by every increment. H2–H4 use H1; H5 uses its identity successor; H6/H7 use the operational successor. H1–H7's serious runtime domain is synthetic Case Management R7 (and R6→R7 preview where stated), not fresh Payment end-to-end coverage for every hardening scenario. Original approved Payment/Case snapshots remain preserved and ordinary target CI remains separately green. Do not extrapolate R7 hardening to arbitrary tenants, application graphs, browsers or production traffic.

## Reliability findings and unsafe-assumption review

1. **Historical normal CREATE HTTP 500 — UNRESOLVED.** Original H3 local raw failure and later diagnostic specimens are retained. Ten instrumented specimens and later green full runs did not demonstrate its cause. H4 pool exhaustion is a separate controlled reproduction. Preserve the original status; collect correlated exception/SQLSTATE, pool, session/idempotency and transaction outcomes on the next bounded diagnostic execution. No blind retry or new error semantics is authorized by H8.
2. **Unmatched resource HTTP 500 — demonstrated inherited mapping limitation.** The generic sealed `Errors`/`FailureMapping` path handles MVC resource misses as unexpected errors. H6 records that behavior. Fix only in a source-fingerprinted successor after target HTTP compatibility review; test arbitrary unknown paths, redaction and unchanged business/security envelopes. Do not edit sealed templates.
3. **Resource exhaustion — PARTIALLY_VERIFIED, unsafe unrestricted-load assumption rejected.** Real pool starvation and recovery are observed; an unrestricted request profile can exhaust nested transactions. Generic 500 is not a reviewed backpressure contract. Pool sizing alone is not admission control. Pending-job bounds, resource response and statement deadlines are an existing unapproved proposal, not implemented semantics.
4. **Worker authentication — bounded service scope implemented; production enrollment BLOCKED.** Host-configured identity/tenant subset and fencing exist. The preview rejects nondevelopment mode. A service string is not a cryptographic production service credential, revocation system or custody proof. Do not replace it with an invented interactive session.
5. **Failed/recovered connections — VERIFIED within experiments.** H2 terminates a backend connection and processes around commit; H6 pauses/resumes PostgreSQL and recovers readiness/pool behavior. H7 rejects wrong credentials before a successful fresh startup. No arbitrary partition, corrupted cluster or multi-region recovery claim.
6. **Migration/restart — VERIFIED within stop–fence preview and disposable state.** Failed/interrupted transactional DDL, checksum/history preservation, old-writer fencing and committed-state replay exist. No accepted-history deployment or zero-downtime distributed upgrade is proved.
7. **Failure detection — bounded VERIFIED.** H6 probes, telemetry, cardinality and redaction are real. Alert delivery, on-call response, monitoring service integrity, production tracing and policy thresholds need their selected profile and operational evidence.
8. **Backup/restore — bounded VERIFIED; production protection BLOCKED.** Exact logical recovery and adversarial checks are real. See the limitation table below.

Fixture gates are external, bounded synchronization controls; they are not production transaction timing or throughput evidence. Trusted-JWT H1–H4 tests remain distinct from H5–H7 signature validation. Test-only queue leasing faults and auxiliary restore schema are explicitly synthetic. Same-host hash records do not authenticate an adversarial host. No supported capacity or semantic policy may be inferred from test tuning.

## Backup and disaster-recovery limitations

| Obligation | Established / missing | Responsible decision |
| --- | --- | --- |
| Logical consistency | Same exported read-only snapshot; exact all-table/history comparison in independent cluster; supported synthetic population only | Engineering evidence established; production DB owner chooses scope/profile |
| Boundary writes | Two acknowledged later CREATE commits intentionally absent after restore; no zero-loss claim | Application/data owner approves allowable loss and reconciliation |
| Physical backup / WAL / PITR | NOT_RUN; no physical image, continuous WAL, timeline or point-selection proof | Data/recovery owner decides whether required to meet approved RPO/RTO; then separately authorize tests |
| Backup encryption | NOT_ENCRYPTED; dump stayed private with synthetic data | Security/data owner selects encrypted format, custody and rotation before production |
| Key custody | No independent production keys, grants, separation or recovery exercise | Security authority and named custodians |
| Retention | No production retention/immutability, geographic or offsite-loss test | Data/privacy/legal owner and operator |
| Restore authorization | Only ephemeral in-process owned-cluster capability, never arbitrary DB URL | Operator/security owner approves auditable production restore permissions and separation |
| Across environments | Independent clusters on one pinned image, same lab execution host; no cross-version/architecture/storage proof | Deployment owner selects support matrix |
| Destruction | Raw temporary files logically removed; no secure erase, WAL/replica/backup destruction guarantee | Storage/privacy owner supplies retention/destruction policy and independent evidence |
| RPO | Snapshot boundary and two excluded writes measured; no approved loss objective | Business/data owner |
| RTO | Backup, restore, readiness and first authenticated response measured; primary interval includes negative-credential startup; total interval includes fault experiments | Business/operations owner approves objective and repeats realistic complete exercises |

PITR is necessary only if the selected profile's approved loss/recovery objectives require capabilities the logical profile cannot supply. H8 neither mandates its implementation automatically nor accepts an insufficient profile. Production G-19 remains BLOCKED.

## Supply chain, security and operational review

H1's retained live OSV query proves one selected replacement at its scan time. It is not a blanket assessment of packaged backend, production npm, compiler, plugins/transitives, embedded identities, license obligations or every predecessor. The exact sealed closure run completed runtime OSV queries with zero returned advisories for each domain and production npm audit exit 0; those bounded runtime results still omit complete compiler/build-policy acceptance and do not satisfy criterion 21. Older whole-inventory assessments cannot serve as fresh current security PASS. Require exact-package current coverage, resolved unknown/unscored findings and explicit policy before G-14/G-15 or criterion 21 acceptance. No dependency or lock changes are authorized by this audit.

Source scanning and successful public secret scans cover their declared bytes and actual fixture credentials. They do not establish that arbitrary failed logs, third-party telemetry or all production configuration is secret-free. H6/H7 fail-closed exports are evidence; production log retention, access, incident response and redaction policy remain decisions. Metrics need a host-held capability in addition to native authentication; choosing its custodian/monitoring principal is not automatic.

Identity/provider ownership, tenant lifecycle, service grants, overlapping-key custody/retirement/revocation, TLS termination, deployment secrets, database privileges, delivery transport, monitoring/alerts, release signatures and operational ownership all require responsible authorities. No production provider, key manager or monitoring service is selected here.

The sealed worker has bounded syscall/resource probes in historical security tooling; the trusted in-process `SuccessorCandidate` API is not sandboxed hostile execution. Seccomp direct-clock denial does not deny vDSO clocks. Namespaces/credential isolation/exhaustive OS controls, materializer power-loss and hostile same-UID/root mutation remain unqualified. H1–H7's JVM/resource hints cannot fill that gap. Restrict the present claim to trusted generator code until a security-owner-approved process boundary is implemented and independently tested.

T09 remains `HUMAN_DECISION_RECORDED / ACCEPT_DELIVERABLES_WITH_RESERVATIONS`, laboratory-only and not independently authenticated. A06-06 INCOMPLETE, A09-08 BLOCKED, A14-06 INCOMPLETE and A17-16 INCOMPLETE remain. A19-01 is not an unqualified operational PASS. Earlier pending records remain historical, not silently overwritten.

## Accepted-history and deployed evolution

R8/H2 prove native semantic diff/impact, exact candidate/ArtifactPlan and SQL preflight, source ownership/CAS, a stopped and fenced old writer, transactional V5 migration, actual post-upgrade functionality and restore in new disposable clusters. They are synthetic previews. `changes.prepare` does not admit Canonical 0.6/0.7 through the native accepted-history path. Neither preview records, target-upgrade JSON, fixture signatures nor a successful Flyway run are authenticated accepted ChangeSets or journal receipts.

A production chain still needs exact approved old/new snapshots and requirements; trusted repository/authority enrollment and genesis; authenticated independent approvals and journal continuity; separately approved measured-population bindings; exact migration plan/execution scope; deployed target identities; post-upgrade behavior, ownership, provenance and recovery. Target 0.1 remains outside the production upgrade window. Do not silently promote H1/H5/H6 or historical 0.6 into sealed 0.5 history. Evolve through an explicitly versioned successor and authorized contracts, not a weakened closure predicate.

## Priority and next bounded work

The register keeps material release/security prerequisites P0, actual reliability fixes P1 and optional broader-profile work P2. P0 is a blocker classification, not a claim of demonstrated exploitation. Follow dependency order: preserve authority boundaries → choose supported trust/deployment/resource profile → approve incompatible response/capacity changes → fix and test successor-only concrete defects → independently qualify selected security/compatibility/recovery scope → seek formal engineering exit and production acceptance. Current coding cannot substitute for external legal or authority decisions.

**Recommended next bounded engineering increment:** successor-only HTTP error classification and CREATE reliability attribution. Reproduce an unmatched path and correct its native successor mapping under reviewed target compatibility; preserve all semantic/authentication envelopes. Reuse H4 closed diagnostics for a bounded normal CREATE run with independent PostgreSQL outcome correlation. A nonreproduction must remain UNRESOLVED, not FIXED. Implement neither change during H8. Safe overload responses or job bounds require the existing explicit contract/semantic decisions first; do not hide them in that fix.

## Objective engineering exit criteria

1. All declared bounded H1–H7 scenarios remain source-bound and reproducible, with no skips, hidden retries or leaked resources; this baseline satisfies that condition.
2. Original hardening dimensions each have an explicit supported profile, actual evidence and exclusions reviewed by the responsible engineering/security owner. Hostile plugin execution cannot be called supported until isolated and tested.
3. The unmatched-route defect has a compatible successor fix. The historical CREATE finding has either independently proven cause/fix or an explicitly reviewed unresolved disposition appropriate to the intended engineering scope, never invented acceptance.
4. Resource bounds/admission, queue growth and overload behavior have explicit approved contracts and tests for the selected scope. Arbitrary-load support is not required, but a safe declared bound is.
5. Supply-chain assessment has complete declared coverage, immutable inputs and current independently reviewed findings; no global security PASS from the Commons IO comparison.
6. Compatibility/materializer gaps are tested under the selected support/threat model or remain formally excluded with authority. Qualification-only status does not waive production requirements.
7. Formal human Phase 11 engineering exit decision is recorded separately. G-01–G-23 and Phase 6 closure stay independently BLOCKED until their own evidence/authority exists.

## Preservation, custody and verification

No full build, PostgreSQL test, scanner query, dependency installation or live infrastructure experiment is repeated by H8. Existing exact-source evidence is reused. Archives are checked against authenticated GitHub SHA-256 metadata, CRC and member path safety; selected records, producer source inventories and bound members are independently reconciled. Current 0.5.0 seal, historical 0.6.0, H1/H5/H6 generator identities, approved Canonical bytes, protected contracts and all predicate bytes are compared. Focused review-integrity and preservation checks are recorded in the source index: 73 preservation tests passed (zero failures/skips), nine review consistency checks passed (including four adversarial mutations), and repository contract checks passed. H1 realm logs were independently reparsed; H4 actual response arrays and H6/H7 exact scenario sets were checked.

Existing H1–H7 vault entries are read-only inputs. H7 exact-source custody remains in the approved `phase11-h7-recovery-20261113/verified-73d48b1e82d4898fe1abb46c25b115185ce6723a` directory. New downloaded archive copies stay in `.audit-artifacts/phase11-h8-20261115/`; they are execution inputs, not a claim of newly approved durable vault custody. No new vault destination was selected or written. Do not delete that staging until custody and active-use rules are satisfied. Git contains redacted review records/hashes, not raw databases, credentials, private keys or full runtime archives. GitHub artifacts have finite retention; their expiry is recorded.

This review identifies evidence and source consistency, not omniscient proof of every runtime assertion or an independently authenticated human security review. No release profile is activated. No blockers are waived. No historical acceptance boundary changes. Phase 11 remains IN_PROGRESS; Phase 12 NOT_STARTED; operational security NOT_ESTABLISHED; `PHASE6_CLOSURE_BLOCKED`; `PHASE6_RELEASE_CLOSURE_BLOCKED`.
