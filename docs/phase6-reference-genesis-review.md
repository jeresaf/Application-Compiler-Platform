# Phase 6 next checkpoint: separate genesis decisions

Status: STOPPED FOR ARCHITECTURE REVIEW AND EXPLICIT HUMAN AUTHORIZATION.
Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.

The retained-data inventory checkpoint at `cad62a3aa668bfc134d72458f969cc1ac6669bb7`
is approved for merge by the current user instruction. That approval grants no
history genesis, independent data binding, migration or deployment authority.
The completed [post-push hosted observation](phase6-retained-data-inventory-postpush-review.md)
already binds run 38250157253 to that commit: all four required jobs succeeded;
closure was PERFORMED with no exception, PHASE6_CLOSURE_BLOCKED, exit 2, 21 blockers.
The observation, exact compressed closure report and frozen database captures are
preserved without rewriting their bytes or hashes.

## Separate exact-bound human requests

- [PAYMENT review request](../proposals/phase6-reference-genesis-review/payment.md)
  and [machine request](../proposals/phase6-reference-genesis-review/payment.json).
- [CASE MANAGEMENT review request](../proposals/phase6-reference-genesis-review/case-management.md)
  and [machine request](../proposals/phase6-reference-genesis-review/case-management.json).
- [Proposed authority model](../proposals/phase6-reference-genesis-review/authority-model.json)
  and [file manifest](../proposals/phase6-reference-genesis-review/manifest.json).

Each request binds its original approved Canonical 0.3 snapshot, distinct proposed
repository/application identity, exact authority-model bytes, sealed target identities
and source-bound hosted evidence. A proposed logical repository ID names a review
subject; it does not create a repository or establish a trusted host.

These are exact-bound **review requests**, not completed executable genesis grants.
Host, authentication issuer/audience, trusted keys and real authority/author/reviewer/
operator principals are unresolved. No such values were supplied. Their absence must
block acceptance rather than being filled with synthetic credentials. Human review
must select the bootstrap route and explicitly approve the repository identity and
scope. A subsequent request must bind concrete authenticated configuration, reviewed
verifier and plan bytes, validity and replay controls, and independent approval proof.
Any changed binding requires a new request digest and fresh independent review.

The [bootstrap design](phase6-new-reference-authority-bootstrap-design.md) identifies
the unsupported direct adoption of later revisions by the legacy adapter. Fresh
prospectively authorized replay requires a proven exact supported chain; a new
baseline-adoption protocol requires separate architecture and implementation review.
Neither is implemented or authorized here. No preview/test anchor is accepted history.

## Accepted plan and proof admission

Before any append, a future verifier must reproduce the exact plan from its declared
source/baseline or authoritative ChangeSet, verify unchanged Canonical admission,
and compare its digest to the independently authenticated reviewer proof. Proofs must
bind repository, application, action, expected head, snapshot, plan, policy and allowed
scope; unknown, stale, expired, replayed, self-approved or wrong-scope proofs fail closed.
Separate author authentication is required. A genesis-only approval cannot authorize
later changes, data binding, migration plans, SQL or deployment. New genesis begins a
new chain at its real acceptance time and cannot assert acceptance of earlier fixtures.

## Auditable export and restoration design

An export must include exact journal entries and receipts, ordered sequence and
previous-digest links, accepted snapshots, plans and proof bytes, source/ChangeSet
inputs, authority-policy/key history, verifier version, authenticated export time,
repository/application identities and independently witnessed exact head. A manifest
binds every file digest and archive format/version. Exported private keys, session
credentials and bearer tokens are prohibited. Artifact hashes alone confer no trust;
the export needs independently verifiable receipt and checkpoint authentication.

Restoration must occur in a quarantined store with acceptance disabled. Verify every
file, proof, snapshot digest, plan reproduction and journal link, then compare the
restored head with an independently retained latest authenticated witness checkpoint.
Reject missing/extra entries, tamper, wrong identity, conflicting chains or a stale
valid prefix. An unavailable witness blocks promotion. Restore missing committed
entries from verified copies; never renumber, delete accepted entries or create
replacement historical receipts. Promotion to the original repository identity needs
explicit recovery authority; copying an export does not establish a new authority.
Record authenticated before/after head observations and recovery provenance.

Future recovery tests must cover interrupted export, corrupt archives, missing receipts,
expired or revoked trust material under the approved historical-verification policy,
stale backups, witness disagreement, concurrent append during export and crash before/
after atomic commit. A consistent export is taken at one exact head; later entries
must be imported and verified before promotion. Restore exercises and test fixtures
must remain separate from the accepted service and its real receipts.

## Preserved boundaries

Semantic content APPROVED_CONTENT; authenticated content signing PENDING;
independent data bindings NOT APPROVED; migration plans NOT APPROVED;
migration execution NOT AUTHORIZED; deployment NOT AUTHORIZED.
Sealed 0.4.0 and 0.5.0 remain unchanged. Inventory coverage remains three resources
across two synthetic tenants per application, with external writers uninventoried.
Existing authentic deployed history remains unavailable in the inspected scope.
No authority was constructed, repository initialized, approval issued, receipt created
or migration SQL executed. Stop before any genesis acceptance.
