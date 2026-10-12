# Route A gateway and operation-ledger contract

Design hardening of reviewed commit `c9949c429e336270c27b1938960b5cd6c330a4ab`.
Proposed contract version `acp-route-a-gateway/1`. Implementation NOT YET AUTHORIZED;
construction, genesis, SQL and deployment NOT AUTHORIZED. Phase 6 IN_PROGRESS;
Phase 7 NOT_STARTED. This supplements the [authority design](phase6-route-a-authority-integration-design.md).
The [executable contract oracle](../verification/route_a/test_gateway_contract.py)
is test-only: it has no authentication provider, cryptography, I/O, repository or receipts.

## Trusted context construction and lifetime

A future gateway must resolve an authenticated service endpoint through a project-authority
registered configuration registry. Pin the exact immutable configuration bytes and digest,
repository/application ID, host/service binding and policy version. Validate registration,
configuration activation, host authentication and current revocation before constructing
context. A client route ID is a lookup hint only: disagreement with authenticated endpoint
and registry selection is denied. No client header, proof, plan, thread-local variable,
mutable global or default repository can select verification context.

Context is a deeply immutable value, not a dictionary holding mutable plan references.
It contains: contract/configuration versions and digest; repository/application and service;
operation ID and action; caller principal and authentication-evidence reference; proposal
ID and immutable proposal-event digest/version when applicable; exact plan bytes/digest,
legacy request bytes, candidate digest, author and scopes; expected head; proof fingerprint
when one exists; policy and snapshot observation references. Tokens and keys are excluded.
The operation binding excludes transient caller/session fields but includes all immutable
subject fields. Context owns canonical byte copies; callers cannot mutate nested content.

A request-scoped adapter closes over one context and exposes unchanged `authenticate`,
`verify` and `verify_historical` interfaces to the native repository. It must not cache a
current-context singleton, and must not survive the call. Dispose context/session after
return; later calls reconstruct from durable exact subject records, not client copies.
Registry versions are immutable and append-only. Rotation cannot reinterpret old context.
If a configuration is no longer permitted for new writes, require a separately reviewed
replacement operation under the new configuration; never silently update a signed subject.
Historical verification continues under the original approved policy chronology.

| Gateway operation | Construction and checks | Lifetime and durable binding |
| --- | --- | --- |
| bootstrap | Authenticated author; independently observed empty native journal plus external latest witness/ledger; reproduce revision-one genesis from pinned source; action GENESIS_ACCEPT. | One invocation. Before native bootstrap, reserve exact subject/proof; no published or consumed genesis may exist. Empty native storage alone is insufficient. |
| propose | Authenticated author equals ChangeSet author; reproduce full plan from trusted native snapshot and exact ChangeSet; check app/config, actual base, provenance and IDs. | One invocation. Persist immutable subject referencing returned native PROPOSED event and exact plan. Native result must equal independently reproduced bytes. No approval reservation yet. |
| review | Load latest proposal through trusted repository read; authenticate its author and compare exact pinned event/plan. Native review is author submission, NOT independent reviewer approval. | One invocation. Pin REVIEW_REQUIRED event to the same subject; edits create a new version, invalidate old review bindings and require resubmission. |
| approve | Independent authenticated reviewer; load current REVIEW_REQUIRED event and reconstruct subject; validate signed repo/head/plan/config/scopes, author separation and current grants. | Reserve exact nonce/proof/subject before calling native approve. Pin native APPROVED event and proof fingerprint after commit. Approval-event crash is reconciled separately from journal commit. |
| apply | Authenticated author with explicit apply grant; reconstruct from immutable approved event, pinned subject and ledger. Confirm unchanged proof, plan, action, repository/config and expected head; recheck current grants/time/read set. | One invocation with fenced writer lease. Only a RESERVED operation with reconciled native APPROVED event may call native apply. Persist actual journal result through the state machine below. |
| idempotent retry | Authenticate anew and perform separate RECEIPT_READ authorization before consulting cached native result; exact durable operation lookup. | Read/recovery context, never a new acceptance context; rules below. No expiry bypass for an uncommitted operation. |
| historical audit | Authenticated AUDIT_READ caller; registered repository and independently trusted latest checkpoint; rebuild per-entry context from verified chain. | Fixed consistent export/head; distinct context per entry, original policy version and predecessor. Never use last live context. |
| export | Authenticated EXPORT_READ grant; pin one published head and complete historical audit; consistent snapshot and ledger/receipt/witness checkpoints. | Immutable export observation and manifest; unfinished tail is quarantined evidence, not a published snapshot. Concurrent writes cannot change pinned bytes. |
| restore | Authenticated RECOVERY_OPERATOR under explicit recovery grant; registered destination identity and independent latest checkpoint. | Quarantined recovery session with no append/publication permissions; do not initialize or authorize genesis as part of restore. Promotion requires historical verification and exact witness/ledger reconciliation. |

Approval/application binding is durable, not the lifetime of a Python object: native
proposal ID is insufficient because a PROPOSED proposal can be edited. Gateway subject
maps repository + proposal-event version + plan digest + configuration digest to a unique
operation. Approve compares this subject with current native event; apply loads the exact
APPROVED event and compares the full signed subject again. Edits, rebase, different proof,
new configuration or stale head cannot mutate the reservation; they require a new operation
and fresh review. Native transactions retain their own reproduction/head/read-set checks.
The gateway holds a per-repository fencing epoch across lookup/reconciliation/native call;
all native writes must pass through that single authorized gateway. Loss of lease stops
writes. Without OS/process enforcement against a second unfenced writer, this design is
not safe to deploy; integration must demonstrate enforcement before construction admission.
For a single-host SQLite deployment, the proposed enforcement is one dedicated service
writer UID/process and a kernel-held per-repository lock spanning reconciliation and the
entire native call. A lease expiry must never permit a second process while the first
can still write. Before failover, prove the old process has exited and released its lock,
or externally fence its host/storage access. A new fencing epoch alone cannot stop a
zombie process inside native SQLite, which has no epoch argument. Cross-host failover is
unsupported until the selected storage/host fencing mechanism demonstrably excludes the
old writer; an unproven distributed lease is not sufficient. Restore must also acquire
this external writer fence before promoting a quarantined store.

## Closed durable operation state machine

State names describe host evidence, not fabricated accepted journal entries. Native
proposal lifecycle remains PROPOSED → REVIEW_REQUIRED → APPROVED → APPLIED. The host
ledger is separate and records versioned events with CAS, durable timestamps and reason
codes. The first operation row is RESERVED after real proof verification; pre-reservation
rejections belong to a separate security attempt log. No proof is issued in this task.

| State | Required durable evidence and permitted next states |
| --- | --- |
| RESERVED | Unique repo/operation/nonce and immutable subject/proof; native approval may be pending reconciliation. → JOURNAL_COMMITTED, REJECTED, EXPIRED, RECOVERY_REQUIRED, QUARANTINED. |
| JOURNAL_COMMITTED | Read-back authenticated actual native entry, exact plan/proof/head and commit time; nonce consumed. → RECEIPT_STORED, RECOVERY_REQUIRED, QUARANTINED. |
| RECEIPT_STORED | Exact immutable signed service-receipt bytes and digest persisted, matching actual entry. → WITNESSED, RECOVERY_REQUIRED, QUARANTINED. |
| WITNESSED | Independently authenticated monotonic witness acknowledgement of exact receipt/new head. → PUBLISHED, RECOVERY_REQUIRED, QUARANTINED. |
| PUBLISHED | Durable publication record/index for that witnessed head. → QUARANTINED only; exact authorized retrieval is a read, not a state transition. |
| REJECTED | Proven no journal commit; rejected operation/nonce permanently retired. Terminal; fresh reviewed operation needed. |
| EXPIRED | Proven no journal commit and expired/revoked proof; retired reservation retained. Terminal; cannot renew same approval. |
| RECOVERY_REQUIRED | Preserve last stable state and all uncertain effects; fence every new append/publication. → exact last stable state, or QUARANTINED. |
| QUARANTINED | Suspect integrity/trust, inconsistent stores or fork; immutable evidence preserved. No automatic exit. Separate explicitly authorized recovery case and re-audit required; no semantic append used to conceal damage. |

No unknown state, skipped normal state, reverse normal transition or same-state write
is valid. Durable stage replay is a read when exact evidence already exists. In recovery,
return to the last stable state only after independently reconciling *all* possible later
effects; then record each later stage in order with its actual evidence. This includes
RESERVED→JOURNAL_COMMITTED if the native commit occurred before the crash. Never regress
an actual committed event into an expired or rejected operation. If commit existence is
uncertain, use RECOVERY_REQUIRED rather than terminal rejection/expiry. A published event
may be quarantined but cannot be unpublished by deleting its historical publication.

Uniqueness constraints: separate unique keys for (repository ID, operation ID),
(repository ID, approval ID) and (repository ID, nonce); native
proposal version + plan + proof mapping; per-operation receipt bytes; per-repository witness
sequence. Store full immutable subject, canonical bytes, configuration reference, grant
references, native event IDs, old/new heads and proof fingerprint. CAS every ledger event
against row version and writer epoch. Exactly one pending append may hold the repository
fence; unresolved commit/receipt/witness state blocks subsequent appends. Fencing epochs
and nonce state must survive restart and restore, independent of a copied old journal.

## Crash and reconciliation rules

No atomicity is claimed between native SQLite, ledger, receipt store, witness and publisher.
Each store must durably commit its own transaction before success. Before each side effect,
record intent under the fence; afterward read back exact effects and append the next state.

| Crash window | Recovery under repository fence |
| --- | --- |
| Before RESERVED commit | No native write permitted. Reauthenticate/revalidate; old pending request has no right to append. |
| RESERVED commit / native approve | Inspect native proposal events. Exact APPROVED event reconciles; REVIEW_REQUIRED may retry approve while proof valid. Any changed event blocks. No journal commit inferred from APPROVED. |
| RESERVED / native journal transaction | Atomic native rollback leaves no entry; exact current head, valid proof and reconciled APPROVED event allow same operation retry. Partial indexes/corruption quarantine. |
| Native commit / JOURNAL_COMMITTED ledger update | Find exact entry by plan/proof/operation mapping; validate native historical audit, actual head and external checkpoints; consume reserved nonce and record commit. Uncertain absence stays fenced; conflicting entry quarantines. |
| JOURNAL_COMMITTED / receipt persistence | Read receipt store by operation; existing exact bytes reconcile, otherwise generate only from verified actual commit under selected service policy. No replacement for conflicting receipt. |
| RECEIPT_STORED / witness acknowledgement persistence | Query independent witness for exact operation/head/receipt; reconcile stored authenticated acknowledgement or retry the same witness submission. Unavailability fences; conflict quarantines. |
| WITNESSED / publication persistence | Verify acknowledgement then idempotently publish exact head; read back index/outbox. No consumer may bypass WITNESSED or use local commit as publication. |
| Any ambiguous result / RECOVERY_REQUIRED persistence | Persist recovery intent if possible and stop process writes; restart requires reconciliation even if recovery flag write failed. A lease timeout alone cannot clear uncertainty. |
| Terminal/quarantine persistence | Keep original stable evidence and reasons. A failed state write does not authorize further calls; reconcile on restart. |

Expiry after actual commit blocks *new* acceptance but must not erase committed history.
Recovery can finalize receipts/witnessing after historical proof-time verification under
separate recovery authority. It cannot call native apply to append using an expired proof.
Receipt retrieval requires current read grants even if original approval was valid.

## Authorized retry retrieval

Expose a distinct authenticated RECEIPT_READ endpoint. Default policy permits the original
authenticated author with current app/repository RECEIPT_READ grant; a delegated auditor
requires a separate explicit scoped grant, not operator status or the retry key alone.
A request supplies exact operation ID, proposal version, action, plan and retry identifier;
server looks up the immutable subject and compares every field, application, repository,
configuration and original author. Bind caller to that author or explicit delegate grant.
Never invoke native apply as a receipt lookup API.

Require actual committed-entry and stored-receipt verification. Only PUBLISHED state may
return usable accepted-history evidence. Earlier committed states return authenticated
pending/recovery status without an accepted receipt; RESERVED may retry *execution* only
through the full apply path and fresh validity checks. Wrong repository, principal,
operation, plan, action, retry key or proposal version is rejected without receipt bytes.
Revoked/expired caller sessions and absent read grants fail closed. Native cache shortcuts
cannot waive gateway authorization; a returned native result alone is not a service receipt.

## Independently trusted historical context

Registration establishes immutable repository/application identity and genesis policy.
Obtain the latest checkpoint from an independently authenticated witness channel and
monotonic reader state, never exclusively from the archive being checked. Freeze a
consistent chain ending at that checkpoint. Native structural audit first validates entry
hashes, contiguous sequences, snapshots, revision indexes and plans; it does not establish
authenticity. The host then builds an immutable sequence→context index from exact entries.
For sequence zero, expected predecessor is EMPTY_UNINITIALIZED. For sequence n>0 use
entry n−1's independently recomputed journal digest and candidate content digest plus
sequence n−1. Compare with current entry's previousDigest, plan base and signed context.
A proof's self-declared predecessor is only a comparison operand, never the source.

A per-audit adapter is closed over registered identity, independently pinned checkpoint
and immutable verified index. `verify_historical(proof, request, committed_at)` selects
exactly one indexed entry by complete proof fingerprint + exact request + commit time;
ambiguity, missing match or any difference fails. It derives full trusted context from
that entry and predecessor, validates original signed repo/config/action/plan/head/scopes,
and returns the unchanged native verdict. Audit all entries under original authenticated
configuration/key/grant histories, verifying author identity, reviewer separation, original
signature, issuer/audience, key validity, proof time and commit time, and applicable
revocation/compromise chronology. Archived sessions need authenticated identity evidence,
not reusable bearer tokens. A key ID or policy copied from a proof cannot enroll trust.

This index is initially untrusted derived data; admit it only after complete structural
and authenticated historical verification and agreement with independent checkpoint.
Missing original trust history, invalid signatures, truncated suffix, inconsistent
predecessor, duplicate nonce or witness disagreement quarantines admission. Export carries
all verification material but never replaces independent trust roots. Restore always starts
quarantined; promotion needs exact latest checkpoint equality and reconciled nonce/receipt/
publication state. No newly chosen trust root may retrospectively bless old history.

## Migration isolation and remaining decisions

History MIGRATION scope reviews the declaration inside the exact semantic plan. It grants
no data-binding, executable SQL, PostgreSQL access or application deployment permission.
The gateway has no application DB/deployment credentials. Downstream consumers must enforce
separate independently approved bindings, exact executable migration artifacts, live
population checks and scoped execution/deployment grants. Native history lifecycle cannot
provide these gates by itself. Missing evidence blocks the downstream action.

Human architecture decisions still required:

1. Accept or revise this context interface, immutable proposal-version binding and fencing
   policy, including an explicit author apply grant and independent RECEIPT_READ grants.
2. Approve closed ledger transitions, cross-store reconciliation, publication/witness gate,
   quarantine recovery protocol and terminal nonce retention.
3. Select actual trust host/provider/issuer/audiences, principals and role separation;
   exact registration/configuration protocol, signature encodings/algorithms, clock bounds,
   key custody/rotation and historical revocation/compromise policy.
4. Select independent witness, storage/backup custody, fencing enforcement, retention,
   recovery authorities and authenticated checkpoint freshness policy.
5. Separately authorize adapter implementation and integration testing. This design and
   test oracle confer no construction authorization. Subsequently authorize construction,
   each exact genesis and each transition separately after their real inputs exist.
6. Keep independent data bindings, SQL and deployment unapproved until separate exact review.

Prior review manifests bind their documents at commit `c9949c4`, not subsequent edited
working-tree documents. They remain immutable historical records. New hardening evidence
has its own manifest and does not replace earlier genesis review packages or proofs.

## Executable regression contract and future adversarial integration

The maintained contracts CI discovery already includes `verification/route_a`; no gate
is removed. `test_gateway_contract.py` contains 13 executable, side-effect-free contract
oracle tests. Its symbolic HostFacts/HistoricalFacts are supplied test premises, **not**
implementations of authentication or evidence verification. No test value is a deployable
credential, signature, approval or accepted receipt. Its functions are not imported by
production code. The real adapter remains unimplemented and unauthorized.

| Contract regression | Checked now | Required later against real adapter |
| --- | --- | --- |
| Context lifecycle | All nine operation purposes, frozen subjects, nested mutable-input rejection, interleaved isolation and wrong host/config/app/repository denial. | Authenticated registry lookup, deep canonical copying, provider validation, context disposal, concurrent requests with no global leakage. |
| Proposal binding | Changed proposal version, plan, action, proof, operation, head, reviewer and caller action grant rejected; approve/apply compare same subject. | Actual stored-event CAS, exact legacy request/full-plan comparison, tampered approval bytes, edit/rebase race and policy rotation. |
| Closed ledger | Every undefined state pair rejected; required stage evidence; irreversible terminal/quarantine behavior. | Real durable constraints, row-version and fencing-epoch CAS; no direct second writer; tampered ledger bytes fail. |
| Crash recovery | Each pre-publication stable state can resume only after exact reconciliation; uncertain commit cannot become rejected/expired. | Kill before/after each native/ledger/receipt/witness/publication commit; disk/fsync failure; durable observation gaps; stale restore and lease loss. |
| Retry authorization | Wrong principal/repo/app/config/action/operation/proposal/plan/head/proof/retry/scopes, absent read grant, unauthenticated caller, unverified receipt and unpublished states all denied. | Exercise native cached-apply path through gateway and prove it cannot bypass RECEIPT_READ; session expiry/revocation, delegated scope, and zero leaked receipt bytes. |
| Historical context | Forged predecessor rejected against preceding chain entry; invalid index, missing checkpoint/structural audit or each proof-time identity/grant/signature/key/time/revocation/scope/config fact denied. | Genuine signatures and original authenticated grant/key/config history; matching full-proof fingerprint/request/commit-time lookup with duplicate-match rejection; independent witness freshness/fork/truncation tests. |
| Migration isolation | History context refuses data-binding, SQL, PostgreSQL migration and deployment operation purposes. | Credential/network isolation, independently verified downstream grants and live population checks. |

Boolean facts in this oracle define mandatory independent verification obligations;
setting them true in a test is not evidence that cryptography, persistence or authority
integration exists. The prior 11 exact replay regressions remain independent and unchanged.
Future implementation authorization must include a separate real integration harness that
satisfies all columns, including original threat/recovery matrices. Missing evidence is a
failed admission, never a test skip interpreted as approval.

## Hosted observation for this checkpoint

[Run 38279457352](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/38279457352)
completed against `c9949c429e336270c27b1938960b5cd6c330a4ab`.

| Job | Final conclusion |
| --- | --- |
| contracts | success, including maintained pure Route A replay |
| phase5-experiments | success |
| phase5c-hard-gates | success |
| phase6-target | success |
| phase6-closure-audit | failure; audit PERFORMED, no exception, PHASE6_CLOSURE_BLOCKED, exit 2 |

Overall workflow conclusion is **failure**, not GREEN. The 21 exact closure blockers
are preserved separately in the [extracted closure summary](../proposals/phase6-route-a-hardening-review/evidence/closure-summary.json).
They cover accepted-history deployed evolution; integrated ownership/provenance/traceability;
manual accessibility/browser support; deployable packaging and container profile;
dependency, license and vulnerability evidence; worker confinement; migration recovery
and restart matrices; deployment obligations, encryption/TLS and physical destruction;
performance/scaling/determinism; and fresh hosted reproduction. No blocker is waived here.

The [artifact observation](../proposals/phase6-route-a-hardening-review/evidence/closure-artifact-observation.json)
binds the uploaded ZIP and exact original closure-report entry bytes; the summary preserves
each blocker object unchanged. Raw [run](../proposals/phase6-route-a-hardening-review/evidence/ci-run.json),
[jobs](../proposals/phase6-route-a-hardening-review/evidence/ci-jobs.json),
[artifact metadata](../proposals/phase6-route-a-hardening-review/evidence/ci-artifacts.json)
and [job log](../proposals/phase6-route-a-hardening-review/evidence/closure-job.log) are retained.
That run validates the reviewed commit, not this uncommitted hardening or new oracle tests.
New local results and exact file hashes are recorded in the
[hardening review manifest](../proposals/phase6-route-a-hardening-review/manifest.json).

STOP FOR HUMAN ARCHITECTURE REVIEW. No implementation, service construction, repository
initialization, genesis acceptance or downstream execution is authorized by this design.

Local validation: **24 Route A tests PASS** (13 gateway oracle and 11 unchanged exact
replay), **13 retained-inventory tests PASS**, sealed 0.5.0 verification PASS with
unchanged bundle digest. No source in the sealed generator or approved Canonical corpus
was changed. See [local validation](../proposals/phase6-route-a-hardening-review/validation.json)
and [exact-bound remaining decision requests](../proposals/phase6-route-a-hardening-review/human-decisions.json).
The latter are proposed review subjects, not signatures or granted authority.
