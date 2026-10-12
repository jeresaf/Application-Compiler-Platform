# Route A security threat model

DESIGN ONLY. No service, authority, repository or approval is created.
Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.

## Assets, actors and boundaries

Protect exact approved Canonical bytes; application/repository identities; full plans,
proofs and revision history; project-authority trust configuration; author/reviewer
separation; approval nonces; private service/human signing material; latest witnessed
head; and the distinction between semantic acceptance and application execution.

Untrusted clients may submit fabricated JSON identities, proofs, plans and retry keys.
Authors cannot approve their own proposals. Operators and storage administrators may
restart, restore or tamper with a host but must not acquire project approval authority.
Compromised service credentials can forge service statements unless independent
reviewer-proof and witness verification rejects them. Human-signing trust, service
identity, witness administration and backup custody must be separately registered
under a real, human-approved trust model. No reference HMAC test key is suitable.

The main boundaries are authenticated caller → trusted gateway; gateway → configured
authority adapter; adapter → human identity/grant and historical key policy; gateway →
native HistoryRepository; journal → external operation/receipt ledger; service →
independent witness; and accepted-history reader → separately authorized migration/
deployment consumers. TLS authenticates transport/service, not human approval by itself.
Hashes bind bytes, not authority. Native triggers do not defeat a host administrator.

## Required negative and recovery tests

These are specifications for future authorized integration tests, not claims of tested
real authentication. Each case must deny new acceptance/publication unless the stated
verified recovery succeeds. A safe duplicate receipt retrieval is not a second acceptance.

| Case | Required result and evidence |
| --- | --- |
| Wrong repository | Signed repository differs from configured context: deny before any write; same-app cross-repository proof replay also denied. |
| Wrong application | Proof/request/plan/application mismatch: deny; no scope inheritance from another application. |
| Self-approval | Authenticated author equals reviewer: deny, even if both roles are otherwise granted. |
| Wrong author | Session principal, plan author or signed author differs: deny. |
| Expired proof | Reject before approval/append and recheck at apply; approval while valid does not waive later expiry. |
| Revoked authority | Live revocation denies new acceptance; historical evaluation follows approved effective-time and compromise policy. Missing chronology denies admission. |
| Unknown key | Unknown key ID, algorithm or untrusted configuration version: deny, never auto-enroll from proof JSON. |
| Tampered plan | Recomputed plan/request or digest differs from signed body: deny. |
| Modified Canonical snapshot | Byte/digest mismatch or invalid Canonical admission: deny, even if semantically similar. |
| Replayed genesis proof | Used nonce, wrong repository or nonempty journal: no new genesis. Restore of an old empty store cannot reset external consumption/witness state. |
| Concurrent genesis attempts | Only one exact authorized bootstrap may commit; loser is denied and reconciled against actual head. No duplicate sequence zero. |
| Stale journal head | Native current head differs from signed expected head: reject; fresh plan and independent review required. |
| Changed read set | Changed revisions or absent-ID reservation: reject at native apply; do not reuse old proof after rebase. |
| Interrupted transaction | No partial journal/snapshot/index state may be exposed. Recover exact reservation or quarantine. |
| Lost response after commit | Authenticate and locate exact committed plan/proof/head; return the same verified receipt or remain blocked. Never append a replacement. |
| Duplicate retry | Exact operation may return its stored receipt to an authorized reader; different plan/action/repository under the retry ID is rejected. |
| Corrupted receipt | Reject signature/body/head inconsistency; retain original bytes for investigation and block admission. |
| Truncated history | Latest independent witness/checkpoint or client monotonic head detects missing suffix; quarantine. A valid prefix hash alone is insufficient. |
| Restored stale backup | Remain quarantined until verified missing entries and ledger state reach the independent latest checkpoint. No sequence reuse. |
| Witness disagreement | Block publication, all new acceptance and consumer admission; retain both observations for project-authority recovery review. |

Also test operator attempts to modify reviewer grants, cross-action proofs, replaced
authority configuration, duplicate JSON keys, malformed signatures, future-dated proofs,
forged TLS/service identity, rollback of the nonce ledger, stolen read tokens used for
writes, missing historical keys/grants and a service receipt lacking human approval.
No fail-open offline mode is permitted. Degraded availability is preferable to admitting
unverified history; it is not permission to invent or erase entries.

## Existing guarantees and integration gaps

Native planners already enforce exact candidate/revision/source invariants, and native
storage checks empty genesis, current head, read sets, immutable IDs and atomic writes.
The maintained [pure regressions](../verification/route_a/test_replay.py) exercise
semantic reproduction and negative mutations only. They do not test the real adapter,
identity provider, receipt signing, ledger, witness or restoration service, all of
which remain unimplemented. Existing public-key-labelled test fixtures are historical
test evidence and must never be imported as real approvals or accepted receipts.

`request(plan)` lacks repository context. The proposed
[signed adapter envelope](phase6-route-a-authority-integration-design.md) closes that
gap through independently trusted per-operation context and an additional signed body,
while preserving the native verdict/request shape. A trusted host must prevent direct
unscoped calls to the repository. Core `apply` can return a stored retry result before
live proof verification: the gateway must authenticate and authorize receipt retrieval,
check exact operation ownership/context and return no new acceptance authority.

## Execution isolation and residual risks

Do not provision application database or deployment credentials to the history service.
Separate accepted semantic history, declared migration approval, independently approved
data binding and SQL/deployment grants. Existing migration-planning readers need a real
independent binding authority; a journal read cannot manufacture one. Human-approved
SQL artifacts and live population checks remain necessary at any future execution gate.

Residual risks requiring human decisions include identity-provider assurance, clock
trust/tolerance, signing algorithms/custody, key compromise policy, witness availability
and independence, immutable-backup retention, operator access and recovery authority.
A fully compromised trust root or colluding authority and witness is outside an honest
single-host hash-chain guarantee and must be addressed by the selected governance model.
Do not claim production security until authorized implementation and independent
integration tests demonstrate all applicable controls.
