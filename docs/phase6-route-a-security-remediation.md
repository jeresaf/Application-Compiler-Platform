# Route A independent security remediation

Authorization remains implementation and isolated testing only, bound to request
`sha256:44805966e05af1db2c4faa3b786361737495025b0eb9e30bfbafe35c701c2eab`.
The reviewed implementation is `a02986bc2cebf3ab0ee5d12c5d11fff2f86a4025`;
the remediation baseline is `27cbccb34a9ae771c27c7720a967984d0c2d8fdc`.
The original instruction, request, decisions, frozen inventories, completion reports,
Canonical snapshots and sealed releases are preserved. No native compiler file or
workflow gate needs modification for these tests.

## Source and executable evidence

The new `engineering/route_a_gateway/freshness.py` implements a configurable provider
interface and a separate durable authority observer. `verification/route_a/lab_provider.py`
provides a disposable signed provider; `/authority-status` is an ephemeral loopback test
route, not a production endpoint. A dedicated `authority-status` key and purpose are
authenticated by the existing immutable registered host configuration. No response can
select its own root, key, repository, application, issuer, audience or verification policy.

Every provider request uses a random challenge. A response must be canonical, genuinely
Ed25519 signed, repository/application bound, current within the registered host's
freshness bound (`witnessMaxAge`, 30 seconds in the fixtures), and reference the exact
registered configuration and policy. The shared challenge-age setting is explicit;
authority configuration expiry is a separate signed value. Time comes from the host's
injected trusted clock. Neither clients nor proof envelopes supply verification time.

The response includes a monotonic authority revision, configuration expiry, available
historical configuration/key/grant identities, and effective revocation/compromise
chronology for principals, keys and grants. This is a bounded single-configuration
protocol: it cannot register new keys or silently replace a pinned configuration.
Unknown/missing evidence fails closed. Configuration/provider selection and observer
location are host-owned; approval/application contexts retain immutable observation
bytes and each authentication/verification independently rechecks current status.

The observer retains signed responses and policy cores in separate SQLite storage with
FULL synchronization and append-only triggers. Revisions cannot move backward; equal
revisions must have the same policy core. A signed fork durably quarantines the observer,
including after restart, with no automatic release. Revocation history cannot disappear
or become weaker, although a later authenticated compromise declaration can move the
invalidation boundary earlier. Authenticated expired/conflicting configuration evidence
advances the observed revision floor before admission is denied. An older status cannot
restore admission. Challenge and observation time are transport freshness, not policy
version changes. Provider outage never authorizes from this retained cache.

`Host.authenticate`, `Authority.verify`, historical verification, witness reads, receipt
verification, publication, export/restore verification and recovery require fresh authority
evidence. Receipt verification requires an explicit trusted current integer time; `None`
cannot disable freshness. Historical verification obtains the provider at current host
time and then checks the immutable proof at its independently verified commit time.
It never queries the provider using an approval's claimed historical time as "now".

Ordinary later revocation can preserve an earlier valid commit. A signed compromise
declaration whose `invalidFrom` covers that commit rejects the historical proof. Missing
historical key or grant versions rejects authenticated admission even if native structural
audit succeeds. This relies on truthful authenticated provider chronology; synthetic
tests do not establish operational provider governance or detect unreported compromise.

`archive.HistoricalAuthority` now rejects duplicate historical approval identities/nonces
and uses the actual current host clock. Native rows still independently establish each
predecessor; the proof cannot invent its own head. Service receipts and retained witness
signatures also consult current historical-key evidence. The native verdict shape and
`acp-route-a-approval/2` are unchanged.

Gateway construction, apply and recovery validate durable ledger chronology and its
independently retained prefix before native effects. Fence acquisition closes its file
descriptor if ownership checks fail. New tests use independent spawned approval/apply
callers, SIGTERM while holding the lock, a replaced inode, stale writer epochs, tampered
external ledger, nonce replay after restart and a genuinely stale native backup during
recovery. A commit known to exist cannot be recreated from an older backup.
Authentication and proof checks precede operation-epoch allocation/reservation;
rejected callers or invalid proofs cannot append operation-ledger housekeeping rows.
Authenticated authority-status observations are retained separately as verification
evidence, including negative status evidence.

Additional real integration tests cover signed witness rollback after reader restart,
fork/stale responses, a correctly signed receipt for another repository, interrupted
publication and a lost recovery response. Receipt retrieval remains separately authorized;
the original author without RECEIPT_READ is denied. No test creates operational history.

First-time witness acceptance additionally checks the proof and service key at the
current trusted time. Historical commit-time verification alone cannot let a compromised
service backdate an unseen head to bypass live revocation or expiry. Already witnessed
exact retries are resolved from the witness's own durable state and retain historical
verification. The witness independently rejects duplicate approval IDs and nonces,
including when a test adversary bypasses the gateway ledger with an otherwise genuinely
verified native commit. Those deliberate bypasses use only temporary artificial histories.
An unwitnessed commit whose proof has since expired or whose reviewer/service authority
has been revoked remains blocked; no replacement approval or receipt is manufactured.

## Reproduction and coverage matrix

```sh
engineering/route_a_gateway/.venv/bin/python3.14 -m unittest discover -s verification/route_a -v
.venv/bin/python3.14 -m unittest discover -s tooling/tests -v
node tooling/check_canonical_vectors.mjs
node tooling/check_canonical_vectors.mjs test-corpus/execution-v03
node tooling/check_canonical_vectors.mjs test-corpus/deterministic-v04
.venv/bin/python3.14 tooling/check_target_release.py
python3.14 tooling/check_repository.py
```

Tests need loopback sockets and disposable subprocesses. The opt-in compiler PostgreSQL
test is reported explicitly if not configured; it is never counted as a passed test.
There are no new dependencies. The maintained cryptography pins and license evidence in
the original implementation package remain unchanged.

`verification/route_a/security_coverage.py` compares controls across all twenty sections
of the implementation authorization. Each row identifies source, concrete integration
tests, measured positive/negative log entries, exact-source hosted evidence, limitations,
and PASS/BLOCKED/INCOMPLETE disposition. It verifies test definitions and complete
successful logs. Hosted PASS requires all four ordinary engineering jobs and compares
current source bytes to the precise hosted Git commit. Documents/test names alone cannot
produce PASS. A local-only matrix remains INCOMPLETE until exact-source hosted evidence
is reconciled. Negative evidence is not applicable to read-only integrity measurements;
those rows identify that limit explicitly.

The security review package is under
`proposals/phase6-route-a-implementation-review/security-remediation/`.
It retains distinct observations for the original implementation run, the cancelled
attempt, exact-HEAD rerun, and remediation-source run. Source and evidence manifests bind
exact hashes. Later evidence commits do not retroactively become the tested source.

## Hosted source reconciliation

Run `38318733625` validates `a02986b`, not the later evidence commit. Its four ordinary
jobs passed; the performed closure audit returned PHASE6_CLOSURE_BLOCKED, exit 2, with
21 outstanding blockers. Earlier evidence is immutable.

Run `38325045550`, attempt 1, was cancelled against exact HEAD `27cbccb`. The contracts
check annotation states: "The run was canceled by @jeresaf." The jobs were cancelled,
not passed; the metadata does not state the user's reason. The workflow has no concurrency
cancellation rule and had not reached a job timeout. Attempt 2 was requested using the
authenticated GitHub rerun interface. Final conclusions are retained separately after
completion; neither a pending nor a cancelled run counts as PASS.

## Outstanding operational blockers and stop

- No genuine identity/authority provider, trust root, reviewer identity, operational
  signing custody, authority registration or witness enrollment is provisioned.
- Tests establish cryptographic identity and policy separation with disposable keys.
  Shared fixture processes are not evidence of independent operational governance.
- Participating single-host writers are fenced. A same-UID/root adversary can replace
  a lock inode or directly edit stores. Detection at checked boundaries does not provide
  atomic confinement against that adversary. Cross-host fencing is unsupported.
- Independent authority/witness observers require durable, separately governed custody.
  Privileged deletion or simultaneous rollback of those stores is not prevented by
  this laboratory implementation.
- Only Ed25519 and one pinned registered configuration are supported. Online multi-version
  policy/key rotation, production provider selection, delegated receipt reads and large
  streaming exports remain unsupported. Archives retain the pinned configuration; fresh
  dynamic revocation evidence must come from the external provider, never an archive.
- Process-crash tests do not establish physical power-loss durability or production
  availability. Local monotonic observation is not a globally distributed fork detector.

Full operational security is NOT ESTABLISHED. Full implementation gate is REVIEW_REQUIRED;
the matrix records incomplete controls rather than claiming a partial implementation PASS.
Stop for independent security review of the exact source and evidence. This request does
not seek genesis or operational construction authorization. PAYMENT/CASE genesis,
accepted transitions, independent data bindings, application migration SQL and deployment
remain unauthorized. Sealed generator 0.5.0 remains unchanged. Phase 6 IN_PROGRESS;
Phase 7 NOT_STARTED.
