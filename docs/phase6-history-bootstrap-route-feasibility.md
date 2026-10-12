# Phase 6 history-bootstrap route feasibility

Reviewed source: `dac1334ce9b8f4227eb0da5af074bb775ee28791`.
Status: technical feasibility review only. Construction and genesis NOT AUTHORIZED.
Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.

**PAYMENT and CASE MANAGEMENT both have an exact reproducible semantic chain**:
revision-one Canonical 0.1 genesis → execution-v03 Canonical 0.2 → deterministic-v04
Canonical 0.3. Pure `genesis`/`prepare` evaluation reproduces every stored plan and
the entire canonical encoding of every stored snapshot. This is stronger than
semantic similarity. During this local analysis, no HistoryRepository or authority
instance was constructed,
and no bootstrap, propose, approve, apply, audit or restore operation was executed.

Recommend **fresh prospective replay using the existing semantic/storage mechanism**,
subject to real authority integration and separate authorization of every acceptance.
Exact semantic feasibility is proved here; authenticated accepted replay is not.
The historical ChangeSets cannot be applied byte-for-byte to a real new journal:
their preview heads must be replaced with actual authenticated heads, producing
new plans and requiring new exact approvals. No baseline-adoption contract change
is needed to reproduce these two final snapshots through the demonstrated chain.

Canonical 0.1 here names an initial semantic snapshot, not a deployment of target
release 0.1. No target 0.1 deployment or expansion of its production support window
is proposed. The retained 0.4.0 deployments and their frozen populations are untouched.

## Reproducible evidence and scope

[Reproduction evidence](../proposals/phase6-history-route-feasibility/reproduction.json)
lists the complete per-object revision deltas, source receipts, ChangeSet file hashes,
historical preview heads, scopes and plan/candidate digests for each application.
The [read-only reproduction script](../proposals/phase6-history-route-feasibility/reproduce.txt)
can be run from the repository root with:

```sh
.venv/bin/python3.14 proposals/phase6-history-route-feasibility/reproduce.txt
```

It writes a comparison result to `/tmp/acp-route-feasibility.json`; that temporary
file is ephemeral. The committed review evidence is the JSON linked above. The script
uses only pure planners and the already retained historical fixture-generation recipe.
`canonical_fixtures.synthetic_approved` reconstructs the old structural fixture bytes,
including their pre-existing `fixture:reviewer` / `fixture:not-real-approval` labels.
Those labels are not authenticated reviewers or new approval grants. No authority
helper, key, session, signing operation or repository constructor is invoked.

The initial source is reconstructed from retained `reference_models.models` and
`canonical_fixtures.synthetic_approved`, rather than claimed to be a separately
retained signed source artifact. Its authoring digest matches the historical Canonical
manifest exactly. The genesis author string `author` and later `assistant:proposal-author`
are existing fixture labels used to reproduce historical plan hashes, not selected
real principals. Real authenticated author identities will change the plan digests.

## Existing contract constraints

The relevant implementations are [changes.py](../tooling/changes.py),
[canonical_ir.py](../tooling/canonical_ir.py),
[history_repository.py](../tooling/history_repository.py) and
[reference_authority.py](../tooling/reference_authority.py).

- `changes.genesis` imports authored source through `migrate_authoring`, retaining its
  deterministic receipt and requiring SEMANTIC and SECURITY scopes. The receipt says
  `requiresApproval: true`; it is an import reproduction, not an accepted journal receipt.
- `bootstrap` requires an empty journal, an authenticated author matching the plan,
  byte-equivalent deterministic genesis reconstruction, independent exact approval,
  Canonical admission and an atomic append. A snapshot file alone is not a genesis plan.
- `_append` requires every previously unseen semantic identity to begin at revision one.
  An existing ID/revision can never acquire different node bytes. The final approved
  snapshots have 91 later-revision nodes in PAYMENT and 137 in CASE MANAGEMENT, so
  direct initial insertion fails this invariant. Renumbering would change approved bytes.
- `prepare` checks the closed ChangeSet shape, exact base content digest, reproducible
  declared source receipts and adjacent Canonical versions. ADD requires a fresh ID at
  revision one; REVISE preserves ID/kind/lifecycle and advances exactly one. Exact-reference
  dependency closure advances affected dependents and rewrites their references.
- `propose` also checks authenticated authorship, retained base/head, reserved identities
  and any declared parent digests. Both historical transition files have empty parents.
  `review` is an author submission to REVIEW_REQUIRED; it is not reviewer approval.
- `apply` requires APPROVED lifecycle, complete plan reproduction, current read-set and
  reservations, exact current head and fresh proof verification before Canonical admission
  and atomic journal append. A historical preview base cannot satisfy a live head check.
- `_authorize` requires the injected authority to return an independent principal,
  exact request and exact proof fingerprint. `ReferenceAuthority` is explicitly a public
  test HMAC mechanism, not real project IAM. Its fixture records cannot authorize this run.
- `audit` reproduces genesis and every later plan, sequence/previous-digest continuity,
  snapshots, immutable revision indexes, retry records and proposal lifecycle. Supplying
  a trusted authority enables historical proof verification; omitting it only checks
  structural bindings. A supplied anchor checks a retained prefix, so freshness also
  requires comparison to an independently observed latest head.

Direct import from later authored versions is not a workaround: import support does
not remove `_append`'s revision-one requirement or `audit`'s genesis reproduction rule.

## PAYMENT: exact chain

Application `APP-FIXTURE`.

| Stage | Exact Canonical digest |
| --- | --- |
| Revision-one genesis | `sha256:eaec1ba1aeb76a96bda57fab383ff6ce87a05f16d1ebea56f5727883255d9f6e` |
| execution-v03 | `sha256:d2cd65d09c4739f53d4c57dddd1d29eb5456bc421c5fac745b336459590d25ac` |
| Approved deterministic-v04 endpoint | `sha256:d0f6e8d96a07e8e8358ad8f1f558f9ec3d69fd8008cceb75e82f4f695e3cf47d` |

Genesis source digest:
`sha256:6177521b3ea4a9e5fd6326010f01755d9ef54300e96c5bdeb0d83a757d0d4bc8`.
Receipt: `authoring-0.2-to-canonical-0.1-v1`, target equal to the genesis digest above.
All 101 initial nodes are revision one. Historical-label genesis plan:
`sha256:4503786c4b317ea48b8eadf1a6795e9f190507ae31d4784c435414e20b09c0a3`.
Required scopes: SEMANTIC, SECURITY.

1. [execution ChangeSet](../test-corpus/execution-v03/payment-change.json):
   CHANGE-EXECUTION-V03, ChangeSet 0.2.0; 9 additions at revision one and 48 revisions.
   Exact expected [Canonical 0.2 snapshot](../test-corpus/execution-v03/payment-canonical.json)
   and [historical plan](../test-corpus/execution-v03/payment-plan.json) reproduce.
   Plan digest `sha256:9f32a52a87ef1faa12daf0a24dbbbb6687d2c59e10cb07ea9f1b6035e5f448a0`.
   Required scopes: MIGRATION, SECURITY, SEMANTIC.
2. [deterministic ChangeSet](../test-corpus/deterministic-v04/payment-change.json):
   CHANGE-DETERMINISTIC-V04, ChangeSet 0.3.0; 1 addition at revision one and 91 revisions.
   Exact [approved endpoint](../test-corpus/deterministic-v04/payment-canonical-candidate.json)
   and [historical plan](../test-corpus/deterministic-v04/payment-plan.json) reproduce.
   Plan digest `sha256:882781981441c2ab50d71617a15edfca88c6b9ebaa25c130cf40f56ea8ce356e`.
   Required scopes: SECURITY, SEMANTIC.

Result: **EXACT PURE REPLAY FEASIBLE**. Across the chain, all 250 unique retained
ID/revision records have consistent bytes; every basis reference resolves in the
accumulated snapshots. No missing semantic transition was identified.

## CASE MANAGEMENT: exact chain

Application `APP-CASE-MANAGEMENT`.

| Stage | Exact Canonical digest |
| --- | --- |
| Revision-one genesis | `sha256:3ee1b350e4222870270c871a379a36c48b8d6fbb684c05ad4ed7438b0b065779` |
| execution-v03 | `sha256:4207852923d9e7e16f7e273d5bedbaa78bc2f10d82efa6f5568f00d23b89055b` |
| Approved deterministic-v04 endpoint | `sha256:5b3a69bb1d6e0e69ed620cd1dd32d10e8a07cec276583055b53ec03bfdcc6b90` |

Genesis source digest:
`sha256:749d1fbdcf7a59cfd4f5c28ec37ed83e7d5913a72a2922521eb5697f90418418`.
Receipt: `authoring-0.2-to-canonical-0.1-v1`, target equal to the genesis digest above.
All 149 initial nodes are revision one. Historical-label genesis plan:
`sha256:2af4caca19a0efb57966fa578d3ab9937d0b8a8c7ab9230d76fcf8d1e5356e2b`.
Required scopes: SEMANTIC, SECURITY.

1. [execution ChangeSet](../test-corpus/execution-v03/case-management-change.json):
   CHANGE-EXECUTION-V03, ChangeSet 0.2.0; 9 additions at revision one and 61 revisions.
   Exact expected [Canonical 0.2 snapshot](../test-corpus/execution-v03/case-management-canonical.json)
   and [historical plan](../test-corpus/execution-v03/case-management-plan.json) reproduce.
   Plan digest `sha256:9d79387aa309a5e6b3d979edb2a796c93da2461f6d5d8efd42effca017eefb10`.
   Required scopes: MIGRATION, SECURITY, SEMANTIC.
2. [deterministic ChangeSet](../test-corpus/deterministic-v04/case-management-change.json):
   CHANGE-DETERMINISTIC-V04, ChangeSet 0.3.0; 1 addition at revision one and 137 revisions.
   Exact [approved endpoint](../test-corpus/deterministic-v04/case-management-canonical-candidate.json)
   and [historical plan](../test-corpus/deterministic-v04/case-management-plan.json) reproduce.
   Plan digest `sha256:d904bc51285d778ba66784fbd08842bd151980e8a22f7662c6330e0f3fd51131`.
   Required scopes: SECURITY, SEMANTIC.

Result: **EXACT PURE REPLAY FEASIBLE**. Across the chain, all 357 unique retained
ID/revision records have consistent bytes; every basis reference resolves in the
accumulated snapshots. No missing semantic transition was identified.

## What remains missing or unapproved

There is no missing semantic ChangeSet between the demonstrated three snapshots.
There is also no authenticated deployed journal, accepted head or new real authority
proof. The distinction matters:

- Both transition files declare `sources: []`; neither declares a transition source
  receipt. That is valid under the current planner and is not a hidden missing input
  to `prepare`. Existing execution authoring and deterministic proposal-authoring files
  remain documentary sources; the journal's `source()` lookup will not magically retain
  them as imported receipts. Additional source attachments, if required by authority
  policy, require separately reviewed plan bytes rather than rewriting historical files.
- Both historical transition bases use sequence zero and a zero journal digest. For
  prospective replay, execution must bind the actual genesis head at sequence zero;
  deterministic must bind the actual execution head at sequence one. Real journal
  digests depend on actual proofs and commit times and cannot be specified here.
- Therefore the exact **future** ChangeSet and plan digests remain pending. Changing
  authenticated author, base or other envelope fields changes the plan digest even
  when candidate Canonical bytes remain equal. Historical immutable approvals and
  plan hashes remain valid only for their original review subjects.
- The execution transitions declare REQUIRED migration, including expand/backfill/
  verify/contract obligations, and `prepare` requires MIGRATION approval scope. These
  migration plans remain NOT APPROVED for a new accepted journal. Do not strip the
  declaration or omit the scope to make replay appear authorized. History append is
  not execution of migration SQL; neither action is authorized by this feasibility review.
- Real trusted host, repository identity binding, author/reviewer principals,
  authentication, keys, scoped approval policy, witness and recovery configuration
  remain unselected. No public reference HMAC proof may substitute for them.

The prior [review-only genesis requests](../proposals/phase6-reference-genesis-review/manifest.json)
bind the **final 0.3 snapshots** as their initial baselines. Route A instead needs
separately reviewed revision-one **0.1 genesis** requests, followed by two new exact
acceptance requests per application. Preserve those earlier packages as review
history; do not execute them or silently reinterpret their approved subject/scope.

`prepare` derives candidate content from the supplied base content, operation nodes,
version upgrade and dependency closure. The authenticated author and base sequence/
journal digest live in the plan/ChangeSet envelope; they do not alter candidate nodes.
This code inspection explains why substituting a genuine current head and author can
preserve exact candidate bytes while requiring a different plan proof. No invented
journal digest was used to demonstrate this. Expected new chain positions are genesis
at sequence 0 (Canonical 0.1), execution at 1 (Canonical 0.2) and deterministic at 2
(Canonical 0.3). Their future journal digests remain unknown until genuine acceptance.

## Route comparison

| Concern | A — fresh prospective replay | B — explicit baseline adoption |
| --- | --- | --- |
| Phase 3 consistency | Uses revision-one initialization and ordinary adjacent-version ChangeSets. | Requires a separately specified initial later-revision checkpoint. |
| Contract changes | No Canonical/ChangeSet/storage semantic change needed for this chain; real authority integration still required. | New repository format/protocol, bootstrap verifier and audit semantics; legacy adapter cannot accept it today. |
| Immutable approvals | Historical records unchanged; new head-bound plans need new proofs. | Historical records unchanged; adoption needs a new exact checkpoint grant. |
| Provenance | Retains intermediate accepted snapshots and every demonstrated revision prospectively. | Must distinguish imported historical revision evidence from new accepted ancestry; no fabricated earlier acceptances. |
| Journal authenticity | New genuine genesis and two genuine appends, at their real future acceptance times. | New genuine adoption event only; earlier accepted history remains unavailable. |
| Revision correctness | Every ID starts at one; existing transitions advance exact dependent revisions. | Needs explicit rules for later-revision first observation, basis resolution and reserved identities. |
| Security | Existing scoped approval hooks; repository-specific real authority context must be implemented and reviewed. | Same real authority needs, plus a new privileged adoption path and its attack surface. |
| Replay protection | Exact live heads/read sets/idempotency protect appends; genesis needs repository-specific proof/host policy. | Must design new adoption replay and one-time acceptance rules as well. |
| Operations | Three acceptance events per application; real heads must be observed before subsequent approval. | Fewer initial events, but custom checkpoint production, verification and long-term support. |
| Implementation effort | Lower semantic/storage effort; authority and deployment operations remain substantial and unimplemented. | Higher protocol/verifier/index/export compatibility effort, without demonstrated need for these snapshots. |
| Auditability | Existing genesis/prepare reconstruction and optional authenticated historical verification. | New trusted checkpoint audit and honest limits on unverified prehistory. |
| Testing/recovery | Real-authority negative tests, crash/idempotency/CAS, authenticated audit and export/restore promotion. | All A operational tests plus checkpoint corruption, missing ancestral revisions and format upgrade/downgrade cases. |

`changes.request` currently binds application, author, plan/content digests and scopes;
it does not natively include repository ID or a genesis nonce. A valid reference proof
could be replayed into another empty same-application repository under the same test
authority during its validity window. Host policy and a repository-bound real proof
adapter must close that gap. The replaceable authority receives an opaque proof and
can verify signed repository/action context before returning the existing verdict
shape, without changing Canonical semantics. This integration is a design obligation,
not a tested or supplied implementation. Never claim the test HMAC mechanism meets it.
The real adapter must also implement `verify_historical`, which `audit` calls even
though the minimal `ApprovalAuthority` Protocol declares only `authenticate` and
`verify`. Its historical policy must preserve proof-time trust and scope evidence.

Existing `restore` performs structural `audit` without an authority parameter. Any
future real restoration must remain quarantined until an explicit authenticated
historical audit and latest-witness-head comparison succeed. The existing mechanisms
support core reproduction; they are not a complete production authority service.

Before any authorized replay is accepted as operationally verified, future tests
must demonstrate exact final bytes for both applications with real scoped proofs;
wrong repository/application/author rejection; self-review, expired, revoked and
replayed genesis-proof rejection; stale head/read-set and duplicate-request handling;
crashes before and after atomic commit; modified revision/receipt/index detection;
and authenticated export/restore with stale-backup and witness-mismatch rejection.
All remain future gates. Existing synthetic tests are documentary mechanism evidence,
not authenticated journal receipts for these new reference repositories.

Any later implementation that touches files included in the sealed generator bundle
requires a new intentional release identity; it must not mutate 0.5.0. A real authority
adapter hosted outside that bundle can reuse the existing authority hooks, subject to
separate review. A baseline-adoption adapter outside the bundle would still require
its own versioned protocol, verifier and audit rules; external placement alone does
not make that new mechanism part of the supported HistoryRepository contract.

## Recommendation and remaining human decisions

Select **Route A for further design**, because both exact semantic chains exist and
it avoids changing the accepted Phase 3 revision/genesis rules. Do not authorize
construction or acceptance on the strength of pure planner equality alone.

Human review must decide whether to authorize the separate real-authority integration
and its tests; accept proposed repository/host/trust and independent principals;
review revised 0.1 genesis subjects and scopes per application; and later approve
each live-head-bound transition plan, including the execution migration-plan scope.
Actual data bindings, migration SQL and deployment need independent authorization.
If those scopes or operational inputs cannot be supplied, replay remains blocked;
baseline adoption is not a way to bypass them. Reserve Route B for a demonstrated
need that cannot be satisfied by the existing exact chain, under separate architecture
review of the new protocol and ancestry rules.

No synthetic reference-note candidate was used in this analysis. Approved Canonical
semantics, historical approvals, frozen inventories and sealed 0.4.0/0.5.0 bytes remain
unchanged. No authenticated approval, reviewer identity, key, session, trusted host
or journal receipt was created. STOP FOR HUMAN REVIEW.

Semantic content remains APPROVED_CONTENT; authenticated content signing PENDING.
Independent data bindings and migration plans remain NOT APPROVED; migration SQL
and deployment remain NOT AUTHORIZED.

## Hosted validation

Run [38258433466](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/38258433466)
completed against reviewed source `dac1334ce9b8f4227eb0da5af074bb775ee28791`.

| Job | Job ID | Final conclusion |
| --- | --- | --- |
| contracts | 114842439960 | success |
| phase5-experiments | 114842440173 | success |
| phase5c-hard-gates | 114848569470 | success |
| phase6-target | 114848702061 | success |
| phase6-closure-audit | 114858071920 | failure — intentional PHASE6_CLOSURE_BLOCKED, exit 2 |

Overall run conclusion: **failure**, with the closure evaluation step as the only
failed step. All four compiler/regression jobs succeeded. The
[exact observed closure exit lines](../proposals/phase6-history-route-feasibility/closure-exit.json)
record PHASE6_CLOSURE_BLOCKED and exit 2, rather than an audit execution exception.
[Raw final run metadata](../proposals/phase6-history-route-feasibility/ci-run.json),
[job metadata](../proposals/phase6-history-route-feasibility/ci-jobs.json) and
[artifact metadata](../proposals/phase6-history-route-feasibility/ci-artifacts.json)
retain the exact source and hosted conclusions. Existing frozen captures and earlier
closure blocker evidence are unchanged. This run validates committed `dac1334`;
the new local feasibility report and reproduction evidence were not part of that run.
Phase 6 remains IN_PROGRESS; Phase 7 NOT_STARTED.
