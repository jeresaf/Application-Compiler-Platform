# Route A failure and recovery matrix

DESIGN ONLY; no failure was induced in an accepted repository and no recovery executed.
Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED. The
[security matrix](phase6-route-a-security-threat-model.md) defines adversarial cases.

## State and publication rules

A future operation moves through: reviewed request → valid independent proof → durable
reservation → native journal commit → durable consumption/receipt → independent witness
confirmation → usable published head. No state before actual commit is an accepted
journal head. A committed but unwitnessed event remains immutable and publication is
blocked; do not undo it to make the ledger appear clean.

The operation ledger and core journal are separate durability domains in this design.
Recovery must fence all new appends until it reconciles them. `verify` itself never
consumes a nonce. A retry is bound to one repository, action, plan, proof and expected
head; it cannot switch to different bytes or acquire SQL/deployment scope.

| Failure point | Native/host state | Authorized future recovery | Fail-closed condition |
| --- | --- | --- | --- |
| Before registration/genesis approval | No trusted repository or grant | Remain uninitialized; obtain exact human decisions | Missing trust or grant. |
| Before durable reservation | No write initiated | Retry authenticated request only while its proof is valid | Unknown operation, invalid proof or changed head. |
| Reservation persisted, before native transaction | Reserved nonce, no committed journal entry | Match exact operation; verify old head and retry the same action | Ledger/head cannot be authenticated. |
| Crash during native transaction | SQLite transaction must roll back atomically | Verify no partial entry/index state; retry same reservation if valid | Partial/corrupt state or unexpected head. |
| Native commit, before response or ledger consumption | Exact entry exists; reservation still pending | Read plan/proof fingerprint and actual head; reconcile consumption for this operation | Different entry, head, proof or missing authority verification. |
| Ledger consumed, receipt not stored | Entry and consumption recorded | Reproduce receipt body from actual commit, sign under authorized service policy, persist before publication | Unknown signing key/policy or ledger mismatch. |
| Receipt persisted, response lost | Same immutable receipt exists | Authenticated exact-operation retrieval returns those same bytes | Unauthorized caller or conflicting retry ID. |
| Witness unavailable | Local commit/receipt retained, not usable as accepted-history input | Retry witnessing exact head; keep later appends and consumer admission fenced | No required witness confirmation. |
| Witness rejects or conflicts | Possible fork/tamper | Quarantine; preserve every chain/observation; explicit recovery authority investigates | Never choose a branch silently. |
| Expiry or revocation before uncommitted retry | Reserved but not committed | Reject old proof; prepare separately reviewed replacement request; retain prior reservation history | Do not extend lifetime or auto-approve. |
| Stale head or concurrent competing operation | Native CAS/lifecycle rejection | Observe actual head; regenerate plan and obtain fresh approval | Reusing stale plan/proof. |
| Duplicate bootstrap after successful commit | Journal nonempty | Host authenticates exact prior operation and returns stored receipt; no second bootstrap | A different proof/action or missing reconciliation. |
| Duplicate transition retry | Native exact retry result may exist | Gateway authorizes read/recovery; verify original commit and receipt | A different plan under the same key. |
| Journal/snapshot/index corruption | Native audit fails | Stop acceptance and publication; retain forensic copies; restore verified evidence under review | Rebuilding history with invented entries. |
| Truncated journal or rolled-back ledger | Prefix may remain internally valid | Compare independent latest checkpoint and monotonic client state; restore exact missing records | Inability to prove latest state. |
| Stale backup restoration | Quarantined store | Verify archive, full chain/proofs/ledger/receipts, reach latest witness checkpoint before promotion | A valid older prefix is insufficient. |
| Lost authority/key history | Historical verification unavailable | Obtain authentic retained configuration/key/grant evidence or remain blocked | Replacing it with a new test authority. |
| Service/human key compromise | New trust uncertainty | Suspend writes/admission, apply approved compromise and rotation policy, retain old evidence | No retrospective rewriting or automatic trust in replacement keys. |

## Export and restoration procedure specification

Export at one exact observed head. Include native journal, records and proposal events,
snapshots, import receipts, plans/proofs, trusted authority/key/grant chronology,
operation/nonce ledger, signed service receipts and independently authenticated witness
checkpoints. Bind every file to an export manifest and archive digest. Record source
repository/application, exact head, exporter identity, time and policy version. Private
keys, passwords and session tokens must not enter the archive.

Restore into an isolated quarantined store with no acceptance or consumer publication.
Verify manifest/archive bytes, repository/application identity, native continuity and
indexes, every real historical proof and consumed nonce's exact operation. Native
`restore` alone invokes structural audit; explicitly invoke authenticated audit afterward.
Compare against the latest independently retained witness, not a checkpoint copied only
from the same archive. Import any authentic missing suffix and ledger/receipt evidence
before promotion. An unavailable or conflicting witness blocks promotion.

Promotion requires an explicitly authorized recovery operator and project policy,
with authenticated before/after head observations. A new repository identity needs its
own registration; copying files does not create authority. Never delete an accepted
entry, reuse its sequence or fabricate a receipt to fill a gap. Semantic rollback is
an independently reviewed forward repair; application-data rollback is a separate
operation with independent binding, SQL and deployment authorization.

## Operator runbooks and observability

Future runbooks must cover ordinary startup validation, registration/configuration
changes, proof rejection, stuck reservations, lost-response reconciliation, witness
outage, backup verification, quarantined restore, key rotation/revocation and incident
escalation. Each runbook begins by checking configured identity, actual head, historical
audit and witness freshness; none may include an approval bypass or test credential.

Record operation IDs, principal references, configuration/plan/proof/receipt digests,
exact observed heads, state transitions, rejection codes and witness acknowledgments.
Exclude raw credentials and private signing material. Alert on stale witnesses,
unreconciled commits, duplicate nonce attempts, audit failure and configuration drift.
Keep immutable security observations separate from the accepted semantic journal;
failed attempts are not new accepted semantic entries.
