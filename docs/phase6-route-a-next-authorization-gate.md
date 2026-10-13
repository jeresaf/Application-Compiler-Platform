# Route A next authorization gate

Status: **PROPOSED, NOT GRANTED**. This is a review request and work breakdown,
not permission to construct infrastructure or operational trust. The human accepted
the bounded laboratory checkpoint at implementation `8d34eff20ee51c2117fb8b9f29d93d39ae109a70`
and evidence `0d0aae6e9d0dda530f3a123238318cf39d901605`. The original implementation-and-isolated-testing
authorization has not expanded. Full operational implementation remains REVIEW_REQUIRED;
operational security is NOT_ESTABLISHED. Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.

The separate [documentary decision](../proposals/phase6-route-a-implementation-review/security-remediation/independent-disposition/human-review-decision.json)
and [outstanding-control register](../proposals/phase6-route-a-implementation-review/security-remediation/independent-disposition/outstanding-controls.json)
preserve earlier decisions, manifests and test results. They do not issue signatures,
grants, operational receipts or journal entries. A19-01 remains PENDING_FORMAL_REVIEW_DISPOSITION.

## Required human choices

No reviewer, trusted host, credential, production endpoint or infrastructure identity
is inferred. Each choice needs an explicitly designated accountable human and an
independent reviewer. An operator/author cannot approve their own trust enrollment.

| ID | Required decision | Independent review required |
|---|---|---|
| T01 | Select host/repository ownership, application/repository identifiers, provider endpoints and permitted environment; distinguish service operation from project authority. | Architecture and infrastructure owners, separate from implementer/operator. |
| T02 | Select issuer/audience, identity federation, author/reviewer/read roles, reviewer separation and explicit registration policy. Specify who may authorize registration and revoke it. | Project-authority representative and independent identity/security reviewer. |
| T03 | Select operational signature algorithm policy, key custody/HSM or equivalent, rotation, compromise response and recovery custodians. Laboratory Ed25519 keys confer no operational trust. | Cryptography/custody reviewer and separate governance approver. |
| T04 | Select configuration version authority, revocation source, chronology retention, freshness SLA, clock assumptions, outage behavior and anti-rollback witness custody. | Identity/security reviewer and independent audit reviewer. |
| T05 | Choose single-host or cross-host topology and privileged threat boundary. Specify OS isolation, service users, storage access policy and fencing enforcement; decide which root/host compromise threats remain unsupported. | Infrastructure security and distributed-storage reviewer independent of operator. |
| T06 | Choose backup retention, archive size limits, RPO/RTO, encryption/custody, authority-version retention, independent checkpoint storage and quarantine release policy. | Backup/recovery and independent security/audit reviewers. |
| T07 | Name actual environment inventory, infrastructure owner and operators; approve a rollback/decommission plan and exact configuration digest before any provisioning. | Separate infrastructure change approver and security reviewer. |
| T08 | Decide whether to authorize the exact skipped disposable PostgreSQL regression, with an isolated empty test database and fixture-only SQL. Application migration, retained population changes and production credentials remain excluded. | Architecture/testing authority; no implied data-binding or migration approval. |
| T09 | Give explicit control-specific formal disposition for A19-01 against the complete deliverables and exact manifests. | Human independent reviewer; bounded checkpoint acceptance alone is insufficient. |

## Proposed source and external contract changes

The table is a precise proposed change boundary, not an implemented patch. Human choices
must be resolved into a new exact-bound work order and reviewed contract bytes before
execution. Unknown environment values and policy decisions are missing inputs; they
must not be filled with invented authority. Each row requires separate explicit scope
approval. Choosing a design does not authorize its registration or provisioning.

| Work package | Proposed source boundary and exact contract delta | Threats and tests |
|---|---|---|
| P1: external provider/configuration integration | New `engineering/route_a_gateway/operational/provider.py` and `configuration.py`, plus `verification/route_a/operational/test_provider.py`. Propose `acp-route-a-operational-host/1` with repository/application identity, issuer/audience, algorithm allowlist, key-version references, independently approved role-policy digest, provider/witness identity, independent authority-age limit, clock policy and configuration validity. Propose `acp-route-a-authority-status/2` with exact version chain and signed revocation chronology. Preserve approval/2 and exact native event/head bindings. Preserve laboratory Host classification and rejection of original application IDs; do not simply remove those guards. | Wrong issuer/repository, forged enrollment, role escalation, stale/outage/conflicting provider, compromise chronology, version rollback and key rollover. Test only disposable providers until a separate operational grant exists. |
| P2: registration/custody protocol | New `engineering/route_a_gateway/operational/registration.py`, `custody.py` and matching isolated tests. Propose `acp-route-a-registration-request/1` binding selected environment/repository, immutable configuration digest, operator/author identity, independent approver, scopes, validity, nonce and custody attestation references. Registration and approval-proof issuance are different actions; neither request creation nor service startup grants project authority. | Self-enrollment, confused deputy, cross-repository registration, replay, unapproved config/key substitution, rotation/compromise and emergency revocation. Dry-run proofs use disposable keys only. No real enrollment or real signing in this work package. |
| P3: enforced storage/fencing | New `engineering/route_a_gateway/operational/fencing.py` and `storage_policy.py`, plus multi-process/isolation tests. Define an external writer-capability contract binding repository, monotonically retained epoch, owner, store identity and lease/expiry policy. Require protected journal/ledger access; a cross-host design must prove stale-writer rejection at the effect boundary. Native HistoryRepository and sealed 0.5.0 remain unchanged. If enforcement requires native contract changes, stop for separate successor-release design authorization. | Replaced lock, direct writer bypass, stale lease/epoch, partition, independent process/node crashes, stale journal/ledger and simultaneous rollback. Deployment-specific enforcement evidence is mandatory before operational claims. |
| P4: portable authority history/backup | New `engineering/route_a_gateway/operational/archive_v2.py` and `verification/route_a/operational/test_archive_v2.py`. Propose a separately versioned external archive/2 binding accepted snapshot/head, ordered configuration/key/grant/revocation versions, receipts, witnesses, observer floors, source identity and all entry digests. Read archive/1 unchanged; never silently reinterpret old bytes. Fresh independently trusted revocation/head evidence remains required on restore. | Missing versions, changed predecessor, stale valid signatures, omitted/replayed receipts, forked witnesses, streaming truncation, large histories, partial restore and checkpoint rollback. Restore remains quarantined; promotion needs its own approval. |
| P5: infrastructure evidence plan | New review-only inventory, deployment configuration template and failure/recovery runbook under a separately approved `proposals/phase6-route-a-operational-infrastructure/` scope. No provisioning command executes from a template. Bind actual OS/service accounts, endpoint identity, storage ACLs, independent custodians, configuration hashes and reviewer decisions before requesting execution. | Custody separation, unauthorized access, service outage, backup loss, compromise, power loss, restore/decommission. Independent infrastructure tests are required; laboratory crash tests are insufficient. |

These external schema names/versions are proposals requiring architecture approval.
Operational algorithms, field-level schema bytes, role policy, endpoint and topology
values remain unresolved until T01–T07. No implementation may treat this table as
an accepted contract. Existing native compiler contracts, Canonical semantics, changes.request,
approval/2 event binding, sealed artifacts and historical approvals are outside the change scope.

## Authorization sequence and security implications

1. Resolve T01–T09 as applicable and review the proposed external schemas, threat model,
   interface compatibility and failure/recovery matrix. Record exact documents/configuration
   hashes and the designated independent reviewers. Do not generate human signatures.
2. Request a separate exact-bound engineering integration grant for selected P1–P4,
   with disposable identities, synthetic stores and the proposed tests. Neither this
   request nor current bounded acceptance grants that work. Preserve old tests and gates.
3. Review implementation evidence independently. Provider correctness, custody,
   enforcement, multi-version recovery and deployed infrastructure need separate
   evidence; no laboratory PASS automatically resolves operational controls.
4. If later requested, prepare a separate environment-specific infrastructure/provisioning
   and trust-registration work order under P5. It must bind resolved configuration,
   identities, custodians, endpoints, source digest, rollback steps and permitted actions.
   Infrastructure creation, trust enrollment, key creation and service activation require
   explicit new authorization. Registration itself never authorizes genesis or application work.

An operational provider can expand who is trusted; configuration rotation can alter
historical verification; custody failure can enable forged authority; weak fencing can
permit split-brain commits; incomplete archives can erase compromise evidence. Therefore
no fallback to cached authority, silent version migration, self-registration, automatic
quarantine release or unverified restore promotion is proposed. Independent review must
assess these risks against the chosen deployment's actual enforcement and governance.
Choosing a narrower topology or threat boundary does not convert A09-08 or any other
existing control to PASS. Any proposed change to a control's acceptance criterion
requires an explicit later human architecture/security disposition; unsupported
same-UID/root or cross-host threats remain visible in the register.

## Exclusions and stop

No work under this present task may create real project-authority keys, issue real
approvals or grants, register operational authority, initialize operational history,
accept PAYMENT or CASE MANAGEMENT genesis/semantic transitions, approve data bindings,
execute application migration SQL or deploy applications. Infrastructure selection is
not a deployment authorization. The proposed next work packages also exclude accepted
history and application actions; those need independent later exact-bound decisions.

Every existing Phase 6 closure blocker remains. Resolving provider or infrastructure
controls does not prove accepted-history deployed semantic evolution or close Phase 6.
Approved Canonical snapshots, sealed generator 0.5.0 and immutable evidence stay unchanged.
STOP FOR HUMAN REVIEW. No broader work has started.
