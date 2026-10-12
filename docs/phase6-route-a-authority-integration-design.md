# Route A authenticated authority integration design

Reviewed source: `2b8cb7603f82ad696679157937fd3f9d1fbd04e4`.
Route A SELECTED FOR ENGINEERING DESIGN. Design identifier:
`acp-route-a-authority/1` (proposed, not implemented or deployed).
Construction, approvals, genesis, transitions, SQL and deployment NOT AUTHORIZED.
Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.

This external host adapter reuses [HistoryRepository](../tooling/history_repository.py)
and [changes.request](../tooling/changes.py). It changes neither Canonical semantics
nor the sealed 0.5.0 generator. Route B is not selected or implemented. The
[acceptance sequence](phase6-route-a-acceptance-sequence.md),
[threat model](phase6-route-a-security-threat-model.md),
[recovery matrix](phase6-route-a-recovery-matrix.md) and
[implementation plan](phase6-route-a-implementation-plan.md) are part of this design.

## Identities and trusted configuration

Each application has a distinct proposed repository identity, private storage,
approval namespace, export manifest and witness checkpoint. Logical IDs in the review
packages are proposals, not initialized repositories or authenticated host bindings.
No actual issuer, endpoint, principal, key, credential or provider is selected here.

Before construction, project authority must authenticate through a human-selected
provider and approve a registration binding repository ID, application ID, service
identity, host/TLS trust, authority policy and storage/witness ownership. Registration
is distinct from genesis authorization. A configuration document must bind:

| Configuration | Required binding |
| --- | --- |
| Identity | Repository/application IDs; trusted service subject and authenticated host endpoint. |
| Authentication | Approved issuer, audience, verification-key source/trust roots, subject mapping, validity and replay rules. |
| Roles | Real project authority, author, independent reviewer and operator identities; exact role grants and separation policy. |
| Proof policy | Version/encoding, allowed signature algorithms and key IDs, clock tolerance, maximum lifetime, action/scopes and replay namespace. |
| Historical trust | Authenticated configuration versions, key validity, grant history and revocation/compromise chronology. |
| Durability | Per-repository storage, operation ledger, receipt signer, witness trust, backup checkpoints and recovery approvers. |

Its digest uses exact versioned canonical JSON bytes with a distinct engineering
domain prefix. It is not a Canonical IR field. Missing selections mean the
configuration is incomplete and cannot authorize execution. Unauthenticated JSON
principal names, test HMAC keys and fixture approval labels confer no authority.

`authenticate(session)` resolves a genuine authenticated session into a stable
principal through trusted host configuration, checking intended service/audience,
issuer signature, time, authentication freshness and replay controls. Project authority
registers trust and scoped reviewer grants. Authors propose; independent reviewers
confirm exact reviewed bytes through authenticated human interaction. Operators may
manage service processes and recovery requests but cannot grant review authority or
approve their own requests. The service identity signs service receipts, never human
approvals. Administrative storage access is not project approval.

## Repository-bound proof envelope

Proposed wire version `acp-route-a-approval/1` has a closed `proofVersion`, `body`,
`signature` envelope. This document defines fields, not a sample issued proof.
Future signed body fields are:

- `repositoryId`, `applicationId`, `authorityConfigurationDigest`;
- `action`: GENESIS_ACCEPT or SEMANTIC_TRANSITION_ACCEPT;
- `request`: the exact unchanged `changes.request(plan)` object;
- `candidateDigest`, `planDigest`, `requiredScopes` (must equal request values);
- `expectedHead`: EMPTY_UNINITIALIZED for genesis, otherwise exact sequence,
  Canonical digest and journal digest;
- authenticated `authorPrincipal`, independent `reviewerPrincipal`;
- `issuedAt`, `notBefore`, `expiresAt`, integer UTC seconds under approved clock policy;
- `approvalId` and unpredictable, issuer-generated `nonce`, unique within the
  repository/action namespace and bound to one exact operation;
- `keyId`, `verificationPolicyVersion` and authenticated grant/identity-evidence digests;
- `migrationDeclarationDecisionDigest` when MIGRATION is required, otherwise null;
- `permittedUse`: accepted-history action only; explicitly no data-binding, SQL or
  deployment authorization.

Signature input is a version-specific domain prefix followed by the exact canonical
body bytes. The approved configuration must pin signature algorithm and encoding;
unknown versions/algorithms/keys or ambiguous encodings fail closed. No signing
algorithm, issuer key or nonce is provisioned by this task. Duplicate keys, unsafe
numbers and noncanonical transport representations must be rejected at admission.

`request(plan)` does **not** contain repository ID or expected head. The adapter must
not infer these from caller-supplied proof content. The trusted gateway binds an
immutable per-operation context containing configured repository/application, full
reproduced plan, action and its exact base/empty state. `verify(proof, request, now)`:

1. Compares the supplied legacy request to the request independently derived from
   that trusted full plan; validates closed proof shape, signed bytes and policy.
2. Verifies the signed repository, configuration, action, exact request, candidate,
   head and scope fields against trusted context. No cross-repository context reuse.
3. Checks authenticated reviewer grants, author/reviewer separation, proof validity,
   revocation and the operation-ledger reservation. Requires the migration declaration
   decision when the reproduced plan requires MIGRATION.
4. Returns exactly `{principal, proofDigest, request}`, where principal is the
   independently verified reviewer and proofDigest is
   `changes.fingerprint(the complete proof, "proof")`.

No extra verdict fields or changed legacy request schema are necessary. The opaque
proof can carry the additional signed context. `bootstrap` and `apply` retain their
own empty-journal/head/read-set checks inside their SQLite write transaction. Gateway
context is not a substitute for those checks. Raw constructors/methods and unscoped
authority objects must not be exposed as production endpoints.

## Verification is not nonce consumption

The same proof is verified at `approve` and again at `apply`; historical audit also
verifies it later. Consuming a nonce inside `verify` would break this lifecycle.
Verification must be deterministic and free of consumption side effects.

A future host-managed, durable per-repository operation ledger reserves an approval
ID/nonce for one exact action, plan and expected head before acceptance. Reservation
is not approval. Only the same operation may retry a reservation. The host serializes
acceptance and holds other operations during uncertain recovery. After an actual
journal commit, it records the exact committed head and consumes the reservation.
The core journal and external ledger are not one atomic transaction today: this
gap is addressed by fencing and reconciliation, not an invented atomicity claim.

If the process dies after core commit but before ledger consumption, recovery finds
the exact stored proof fingerprint, plan and head, then completes consumption for
that operation. If no commit exists and the old head is unchanged, only that operation
may retry, with current validity rechecked. If state is inconsistent or cannot be
authenticated, stop. Never release a nonce for another action or accept a conflicting
genesis. Independent witnessed checkpoints prevent an old restored empty store from
making a consumed genesis proof appear unused.

## Historical verification

The real adapter must implement `verify_historical(proof, request, committed_at)`;
the minimal Python Protocol does not declare it, but authenticated `audit` calls it.
Return the identical three-field verdict produced at live verification.

The host constructs a per-entry historical context from the complete exported or
retained chain: repository, entry action, plan and exact predecessor head. That index
is not trusted merely because it was read from storage. Cross-check it through native
hash/plan/index audit and authenticated proof verification before admission. Never
accept a proof's self-declared head as the historical context. Genesis requires actual
sequence zero with no preceding journal digest; transitions bind their exact predecessor.

Verify original signature/key identity, exact request and added context, authenticated
proof-time configuration and reviewer grants, validity at issuance and commit time,
and historical revocation policy. Current grant lists alone are insufficient. Proposed
policy: revocation effective at or before commit invalidates that acceptance; ordinary
later revocation does not rewrite earlier events. A later compromise declaration can
quarantine affected history for current use while preserving its original evidence.
Project authority must approve the final effective-time/compromise policy before
construction. Missing key/grant/revocation history fails closed.

Consumed nonces remain valid evidence of their one original accepted operation during
historical audit; they do not become reusable live approvals. Audit checks each approval
ID/nonce against its exact operation and detects duplicate accepted uses. Structural
`audit()` without a real authority is insufficient for production admission.

## Trust, receipts, storage and witnessing

Use human-selected TLS trust and service authentication for write/read/export APIs.
Authenticated reads expose repository identity, exact head, snapshot digest, plan and
receipt chain with freshness evidence. Unknown host bindings or stale observations
block use. No cloud provider or deployment hostname is hard-coded.

The existing SQLite transactions atomically append journal, snapshots, revision indexes,
retry records and proposal events. Preserve compare-and-swap and append-only triggers.
Limit filesystem access to the service writer; readers/exporters cannot edit records.
Triggers do not protect against a privileged host administrator: require an independently
administered witness and immutable backup checkpoints in a separate trust domain.

The core approval verdict is not a signed service receipt. After reading and verifying
an actual commit, the future service signs and durably stores an external receipt bound
to repository/application/configuration, action, plan/proof digests, exact old/new heads,
core commit time and service key. Persist its exact bytes before returning it. Repeated
delivery returns the same receipt. A receipt never grants data or deployment authority.
The independent witness confirms the exact new head and receipt before the history
is exposed as usable accepted-history evidence to consumers. A locally committed,
unwitnessed event is retained but publication/admission remains blocked.

Versioned exports include exact journal/records/proposal events, snapshots, source
receipts, plans/proofs, authority/key/grant history, operation ledger, external receipts
and latest authenticated witness checkpoint, with file hashes and provenance. Exclude
private keys and bearer credentials. Restore only into a quarantined store: verify all
bytes, native continuity/indexes, real historical proofs and latest witness equality
before any promotion. Existing `restore` does not perform authenticated historical
verification; the host must explicitly run that verification before admission.

No retained application PostgreSQL credentials, SQL executor or deployment endpoint
belongs to this history service. All infrastructure, keys and principals remain
unselected; implementation and deployment require separate human authorization.

## Conditional-review hardening

The [gateway and ledger contract](phase6-route-a-gateway-contract.md) specifies the
trusted context lifecycle, closed durable states, retry retrieval authorization,
independent historical context and exact remaining human decisions. It supplements
this reviewed design; implementation and construction remain unauthorized. Earlier
manifest hashes describe document bytes at `c9949c4` and remain historical evidence.

## Stage-specific contract correction

The [corrected gateway contract](phase6-route-a-gateway-contract.md) makes proposal,
proof, reservation and retry fields stage-specific. Its proposed engineering proof
envelope `/2` adds a signed operation ID and actual REVIEW_REQUIRED event binding
(null for genesis), with explicit genesis retry identity. `/1` above remains the
historical unimplemented design at the reviewed checkpoint. No existing approval or
Canonical contract is rewritten. Future implementation requires `/2` review and separate
authorization; no signature, repository or authority is created by this correction.
