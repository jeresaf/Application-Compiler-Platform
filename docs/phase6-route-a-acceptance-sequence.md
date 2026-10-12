# Route A prospective acceptance sequence

Design only; no step is authorized to execute. Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.
The [authority adapter](phase6-route-a-authority-integration-design.md) and
[recovery matrix](phase6-route-a-recovery-matrix.md) govern every future operation.

## Exact semantic subjects

| Application | A: revision-one genesis | B: execution-v03 | C: deterministic-v04 |
| --- | --- | --- | --- |
| PAYMENT / APP-FIXTURE | `sha256:eaec1ba1aeb76a96bda57fab383ff6ce87a05f16d1ebea56f5727883255d9f6e` | `sha256:d2cd65d09c4739f53d4c57dddd1d29eb5456bc421c5fac745b336459590d25ac` | `sha256:d0f6e8d96a07e8e8358ad8f1f558f9ec3d69fd8008cceb75e82f4f695e3cf47d` |
| CASE MANAGEMENT / APP-CASE-MANAGEMENT | `sha256:3ee1b350e4222870270c871a379a36c48b8d6fbb684c05ad4ed7438b0b065779` | `sha256:4207852923d9e7e16f7e273d5bedbaa78bc2f10d82efa6f5568f00d23b89055b` | `sha256:5b3a69bb1d6e0e69ed620cd1dd32d10e8a07cec276583055b53ec03bfdcc6b90` |

Historical source and plan identities, complete revision deltas and source file hashes
remain in the [feasibility evidence](../proposals/phase6-history-route-feasibility/reproduction.json).
The [maintained tests](../verification/route_a/test_replay.py) assert these six exact
digests, source-receipt reproduction, immutable revisions and basis resolution, plus
negative mutations. They instantiate neither repositories nor authorities. CI now
runs them as a separate contracts step, without removing any existing gate.

## Three operations per application

The proposed repositories are logically separate:
`urn:acp:reference-history:payment:new-1` and
`urn:acp:reference-history:case-management:new-1`. These strings are review subjects,
not registered trusted identities. Each operation below needs its own real approval.

| Operation | Exact source identity | Expected state | Plan and scopes |
| --- | --- | --- | --- |
| PAYMENT A | Existing reference_models + canonical_fixtures historical recipe; authoring digest `sha256:6177521b3ea4a9e5fd6326010f01755d9ef54300e96c5bdeb0d83a757d0d4bc8` | Authenticated EMPTY_UNINITIALIZED | `genesis(source, real_author)`; SEMANTIC, SECURITY. |
| PAYMENT B | `test-corpus/execution-v03/payment-change.json`, exact historical operations, with newly reviewed live envelope | Actual PAYMENT A head, sequence 0 | `prepare(A, new_change)`; MIGRATION, SECURITY, SEMANTIC. |
| PAYMENT C | `test-corpus/deterministic-v04/payment-change.json`, exact historical operations, with newly reviewed live envelope | Actual PAYMENT B head, sequence 1 | `prepare(B, new_change)`; SECURITY, SEMANTIC. |
| CASE A | Existing historical recipe; authoring digest `sha256:749d1fbdcf7a59cfd4f5c28ec37ed83e7d5913a72a2922521eb5697f90418418` | Authenticated EMPTY_UNINITIALIZED | `genesis(source, real_author)`; SEMANTIC, SECURITY. |
| CASE B | `test-corpus/execution-v03/case-management-change.json`, exact historical operations, with newly reviewed live envelope | Actual CASE A head, sequence 0 | `prepare(A, new_change)`; MIGRATION, SECURITY, SEMANTIC. |
| CASE C | `test-corpus/deterministic-v04/case-management-change.json`, exact historical operations, with newly reviewed live envelope | Actual CASE B head, sequence 1 | `prepare(B, new_change)`; SECURITY, SEMANTIC. |

Initial source bytes can be reconstructed from the retained historical recipe and
checked against the pinned authoring digest. Fixture lifecycle/approval labels are
structural source witnesses only. A deterministic import receipt is not an accepted
journal receipt. Both historical transition files declare `sources: []`; do not claim
they contain imported source receipts. Retain their original authoring/proposal files
as documentary evidence. Any additional declared source attachment changes the plan
and needs exact new review.

For each operation, the future authorized host must:

1. Authenticate its configured repository/service and the real proposal author; observe
   the actual current head or empty state through trusted reads. Never insert a zero
   preview journal digest or invent a predecessor receipt.
2. Reproduce the exact candidate through the existing planner. For B/C, preserve the
   historical semantic operations but create a separate new envelope with actual author,
   actual base and reviewed provenance links. Keep historical files and approvals intact.
3. Compare complete canonical candidate bytes and digest to the exact stage pin. Obtain
   the fresh plan digest. Author and live-head changes make historical plan hashes
   unsuitable as executable subjects; future exact plan hashes are deliberately unknown.
4. Have an independent authorized reviewer approve the exact repository-bound action,
   full plan, head, candidate and scopes. B additionally requires explicit review of its
   declared migration plan. No historical preview proof or old genesis review request
   authorizes this action.
5. Reserve the real approval nonce for that exact operation. For B/C, follow PROPOSED →
   REVIEW_REQUIRED → APPROVED → APPLIED; A uses the separately authorized bootstrap.
   Reverify approval at acceptance, including time, grants and exact live head.
6. Verify the actual append, read the exact stored plan/proof/snapshot and new head,
   reconcile durable nonce consumption, persist the service receipt and obtain independent
   witness confirmation. Run authenticated historical audit, not only structural audit.
7. Publish a fresh authenticated observation binding application/repository, sequence,
   Canonical digest, actual journal digest, plan/proof/receipt/configuration digests and
   witness checkpoint. Proceed to the next stage only after this gate succeeds.

Final accepted sequence would be 2; its Canonical digest is known above, but no journal
digest, timestamp, approval proof or accepted head exists today. Every future acceptance
occurs at its actual new time. This chain cannot manufacture previously deployed history.

## Migration scope is not execution authority

Execution-v03 declares REQUIRED migration and therefore requires MIGRATION scope.
Keep that scope and its exact declaration. The future reviewer must separately approve
the declaration's inclusion in accepted semantic history; it remains NOT APPROVED now.

| Decision | Required subject | What it cannot authorize |
| --- | --- | --- |
| Semantic history acceptance | Exact repository/head, candidate, full plan, author and independent proof | Application SQL, data values or deployment. |
| Declared migration plan acceptance | Exact declaration and plan digest, explicit MIGRATION scope and human decision | Independent retained-row binding or SQL execution. |
| Independent data binding | Exact application, frozen/live measured population, binding bytes, writer findings and recovery obligations | Genesis, semantic plan acceptance or deployment. |
| SQL execution | Separate approved executable migration, SQL/artifact hashes, real target/database/schema, current population, operator and recovery grant | Deploying application artifacts or unrelated SQL. |
| Deployment | Separate approved sealed artifacts, environment, provenance, health checks and operator grant | Unapproved semantic changes or binding values. |

`HistoryRepository.apply` changes its history SQLite store; it does not execute application
migration SQL. Its MIGRATION scope does not by itself express deployment authorization.
Additional host and consumer enforcement is required: history APIs expose no SQL/deploy
operation or application-database credentials. A future SQL executor must independently
verify a narrowly scoped execution grant, approved bindings, migration artifacts, exact
live population and recovery authorization; a deployment executor needs its own grant.
An accepted-history reader must not synthesize data-binding approvals from a journal.
Neither executor is implemented or authorized by this design.

The [new revision-one review packages](../proposals/phase6-route-a-genesis-review/manifest.json)
are separate from the earlier final-0.3 baseline proposals. They are incomplete review
subjects pending human configuration and real verifier/plan bytes, never executable
grants. No repository is initialized. No approval, migration or deployment is authorized.
