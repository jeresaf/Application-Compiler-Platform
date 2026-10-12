# Proposed new reference history authority

Status: DESIGN ONLY — NOT AUTHORIZED FOR CONSTRUCTION OR GENESIS ACCEPTANCE.
Reviewed inventory source: `cad62a3aa668bfc134d72458f969cc1ac6669bb7`.
Phase 6 remains IN_PROGRESS; Phase 7 NOT_STARTED.

This proposal concerns a **new** accepted-history reference service for PAYMENT and
CASE MANAGEMENT. Existing deployed authentic history remains
AUTHENTIC_HISTORY_UNAVAILABLE in the inspected scope. No repository, authority,
credential, signature, receipt or accepted head is created by this document.
The synthetic preview anchors, fixture approvals and PostgreSQL runtime records
cannot be imported as previously accepted journal entries.

## Baseline and adapter gap

The proposed initial baselines are the original approved Canonical 0.3 snapshots,
not the EVOLVE-REFERENCE-NOTE candidates:

| Application | Canonical snapshot digest |
| --- | --- |
| PAYMENT / APP-FIXTURE | `sha256:d0f6e8d96a07e8e8358ad8f1f558f9ec3d69fd8008cceb75e82f4f695e3cf47d` |
| CASE MANAGEMENT / APP-CASE-MANAGEMENT | `sha256:5b3a69bb1d6e0e69ed620cd1dd32d10e8a07cec276583055b53ec03bfdcc6b90` |

Authoritative files are `test-corpus/deterministic-v04/payment-canonical-candidate.json`
and `case-management-canonical-candidate.json`. Their current revisions, identities,
bases and approved semantic bytes must survive unchanged. Historical source and
approval artifacts remain documentary provenance; they do not become authenticated
accepted prehistory by being copied into a new service.

The existing `tooling/history_repository.py` adapter cannot directly do this.
`bootstrap` requires a reproducible `changes.genesis` INITIALIZE plan from authored
source; `_append` requires each previously unseen identity to start at revision one.
These approved snapshots contain later revisions. Its `audit` also reconstructs the
first entry through the existing genesis procedure. Renumbering nodes, inventing
missing predecessor acceptances or attaching a preview anchor would misrepresent
the baseline and is prohibited.

Proposed resolution, requiring separate architecture approval: define a versioned
**baseline-adoption protocol outside Canonical IR and compiler contracts**, with
independent verification of the exact approved snapshot and an explicit declaration
that earlier accepted journal history is unavailable. A newly authorized sequence
zero would have no preceding journal digest and would describe acceptance into this
new repository at the actual acceptance time. It would make no statement about
earlier deployment or acceptance times. Its verifier must check existing Canonical
validity and distinguish documentary basis references from verified journal ancestry.
If required basis validation cannot be satisfied honestly, adoption must stop.
The legacy adapter is not represented as supporting this protocol today.

Until that protocol and its verifier are reviewed, implemented and tested under
separate authorization, genesis is blocked. An alternative is to supply genuine
authenticated existing history; reconstructing fictional receipts is never an
alternative. Sealed 0.4.0/0.5.0 generators need no mutation for this design.

A fresh, prospectively authorized replay from a supported revision-one genesis is
another option. It must first demonstrate an exact reproducible source/ChangeSet
chain to these approved snapshots and compatibility with the existing verifier.
This review has not established that complete chain or authorized new acceptances.
Any resulting receipts would record new acceptance times, never historical ones.
Human review should compare this option before authorizing a new adoption protocol.

## Trust and separation of duties

PAYMENT and CASE MANAGEMENT require separate repository identities, application
scopes and chains, even if a future approved service hosts both. Repository IDs,
host URI, TLS trust binding, authority identity, issuer/audience, reviewer identities,
key IDs, storage location and policy digest are **PENDING HUMAN SELECTION**. No
placeholder is a trusted value and no local hostname establishes authority.

Before construction, the project authority must pin the service URI, trusted TLS
identity or trust anchor, host instance, service account and storage ownership in
a reviewed configuration. An independent channel must authenticate that binding.
The service must validate real authenticated sessions against approved issuer,
audience, signature keys, validity times and replay controls. Author, independent
reviewer and deployment operator are distinct roles; an author cannot approve their
own request. Service administrators cannot grant themselves project approval.
Test issuers, local reference HMAC fixtures and unsigned signing requests are not
real authority credentials.

Explicit genesis authorization must bind application and repository identities,
trusted host configuration digest, policy/version, exact baseline file and Canonical
digests, verifier version, author, independent approver, allowed action and validity
window. Each application's authorization is separate. Existing semantic-content
approval does not authorize repository construction, genesis, data binding, migration
or deployment. Approval authentication must be independently verifiable before an
acceptance attempt; missing, expired, mismatched or self-approved grants fail closed.

## Proposed journal and receipts

The service must atomically persist the entry, exact accepted snapshot and receipt
with a compare-and-swap against the expected head. Only the service writer may append;
readers cannot write. Entries are immutable; corrections, revocations and recovery
observations append new events. SQLite reference triggers alone do not protect
against a privileged storage administrator. A separately administered witness and
immutable backups must retain published head checkpoints to detect truncation,
forking or restoration of an older valid prefix.

The proposed receipt envelope must bind, with an approved exact-byte encoding and
domain separation: protocol version, repository/application/authority identities,
trusted host and approval-policy digests, sequence, previous journal digest,
baseline or ChangeSet request digest, accepted Canonical digest, source/provenance
digests, authenticated author and independent approval proof, granted scopes,
commit time and signing key identity. Algorithm choice, key custody, rotation,
revocation and historical verification policy need human approval before key
creation. No new cryptographic contract is asserted to exist here.

Receipts must be verifiable independently using pinned public trust material, or
an explicitly approved durable authenticated verification mechanism. A TLS download
alone does not prove an arbitrary saved receipt's authenticity. Verification must
check both receipt authenticity and chain/head continuity. Signatures alone cannot
detect rollback to an earlier correctly signed prefix without an independent latest
head observation. The service may expose a locally committed entry as pending
publication, but it must not expose it as execution-eligible accepted history until
the required independent witness confirms the exact head.

## Reproduction and authenticated observations

The baseline verifier must reproduce the approved Canonical digest from the exact
snapshot bytes, verify graph/reference validity and preserve every identity and
revision. Later evolution requires authoritative ChangeSets, independently checked
plans and real scoped approvals against the exact authenticated prior head. Candidate
content approval alone is insufficient. Unknown protocol versions fail closed.

Authenticated read endpoints must return the repository and application identities,
current sequence, Canonical digest, journal digest, complete receipt chain, snapshot,
policy/key history and witness checkpoint. Each observation records capture time,
authenticated host identity, freshness challenge, exact response bytes/digests and
verifier result. Clients compare their retained latest checkpoint and the independent
witness. Wrong application, missing entries, changed bytes, stale head, unavailable
authentication or inconsistent witnesses block admission. Private credentials never
belong in evidence exports.

## Failure and recovery obligations

These are future acceptance tests and operational requirements, not executed tests.

| Failure | Required outcome and recovery |
| --- | --- |
| Missing trust configuration or genesis grant | Remain uninitialized; obtain exact independent authorization. |
| Invalid, expired, replayed or self-approved identity/grant | Reject without an append; record a separate security observation. |
| Duplicate genesis request | Return the same verified receipt only for identical authorized bytes; reject a conflicting baseline. |
| Crash before atomic commit | No accepted entry; retry the exact request against the observed empty head. |
| Lost response after commit | Read and authenticate the head/receipt; retry idempotently, never create a second genesis. |
| Concurrent append or changed head | Reject stale compare-and-swap; prepare a new request and obtain fresh scoped approval. |
| Witness unavailable after local commit | Hold publication and execution admission; retry witnessing the same entry, without deleting it. |
| Signature, snapshot or journal corruption | Stop reads used for admission and all appends; preserve bytes for investigation. |
| Backup restore behind witnessed head | Fail closed; restore verified missing entries and recheck full continuity. Never reuse sequences. |
| Witness disagreement or fork | Quarantine service; reconcile under explicit project-authority review, retaining both branches as evidence. |
| Lost/compromised key or revoked authority | Suspend acceptance; apply separately approved rotation/revocation policy with historical verification retained. |
| Baseline cannot reproduce approved digest or validate references | Reject adoption; resolve provenance under review without altering approved semantic bytes. |
| Later application deployment fails | Keep journal intact; deployment recovery requires its own approved plan and retained-data evidence. |

Before construction is accepted, test these cases with actual authenticated principals,
process crashes and durable storage, including wrong repository/application replay,
issuer/audience mismatch, unknown keys, modified receipt/snapshot, journal gaps,
truncation, old-prefix restore, two concurrent genesis attempts and authorization
scope escalation. No test credential or synthetic receipt may enter the real chain.
An accepted journal cannot be rolled back by deleting entries; application rollback
and forward repair remain separate, explicitly authorized operations.

## Human decisions before any next action

1. Approve or reject the proposed baseline-adoption protocol and its separate
   implementation/verifier work, considering fresh authorized replay first;
   approve the exact original baseline per application.
2. Select and authenticate the real host, repository identities, trust roots and
   service ownership; approve construction scope separately from genesis.
3. Select real author/reviewer/operator principals and independent approval policy,
   authentication, receipt verification, key custody and witness/backup operators.
4. Approve exact genesis requests only after the above configuration and verifier
   bytes are available for review. No executable genesis request exists in this package.

Independent retained-row bindings remain REVIEW_REQUIRED. Measured coverage is
**three resources across two synthetic tenants per application**, with bounded
repository writer coverage and external writers unknown. Authentic deployed history
remains UNAVAILABLE. Neither this design nor hosted CI grants binding approval,
authenticated semantic proof, migration SQL permission or deployment authority.
Stop for human review before constructing any authority or accepting genesis.
