# Route A implementation and isolated reference plan

Status: SELECTED FOR ENGINEERING DESIGN; implementation/construction NOT AUTHORIZED.
Reviewed commit `2b8cb7603f82ad696679157937fd3f9d1fbd04e4`.
Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED. Route B is not implemented.

## Work completed in this design tranche

The [authority design](phase6-route-a-authority-integration-design.md),
[six-operation acceptance sequence](phase6-route-a-acceptance-sequence.md),
[threat model](phase6-route-a-security-threat-model.md) and
[recovery matrix](phase6-route-a-recovery-matrix.md) specify future behavior only.
Separate [revision-one genesis review packages](../proposals/phase6-route-a-genesis-review/manifest.json)
bind the exact original 0.1 starting snapshots and approved 0.3 endpoints without
replacing earlier final-baseline proposals or approving a future operation.

[Maintained pure regressions](../verification/route_a/test_replay.py) are the only
new executable implementation in this tranche. They verify all six pinned snapshots,
historical plans/scopes/source receipts, immutable revision/basis continuity, and
negative base/version/revision/source/migration/content mutations. No repository,
authority, session, signature or receipt is created. Tests live outside `tooling` and
the target worker/template roots to preserve the exact frozen writer inventory;
the contracts workflow explicitly discovers them. This is not a new writer boundary
or evidence that external application writers have been inventoried.

## Proposed provider-neutral reference infrastructure

| Component | Proposed isolation and responsibility | Human selections required |
| --- | --- | --- |
| Repository host | Separate PAYMENT/CASE identities, directories/stores, operation ledgers, receipt streams and API authorization contexts | Real host/service identities, trusted endpoints, filesystem owners and resource limits. |
| Authentication provider | Real authenticated project authority, authors and independent reviewers; operator roles separate | Provider/issuer/audience, trust roots, principal mappings, assurance and session policies. |
| Signing custody | Human-approval signing separated from service-receipt signing | Algorithms, key custody, approved key enrollment/rotation and historical verification. |
| Durable storage | Single authorized writer per repository; atomic native commits; fenced external reconciliation | Disk durability, filesystem/process controls, availability and retention obligations. |
| Independent witness | Different administrative trust domain; monotonic registered repository heads and receipt digests | Witness identity, verification keys, freshness/fork policy and administrators. |
| Backup/export | Immutable, independently retained checkpoints and complete auditable exports | Backup custodian, retention, verification schedule, recovery approvers and restore location. |
| Observability | Authenticated head/audit/ledger status, rejection metrics and redacted immutable incident evidence | Access policy, alert owners, log retention and escalation contacts. |
| Application isolation | No retained application PostgreSQL or deployment credentials/network privileges in history service | Explicit network/storage boundaries and any later independently approved executors. |

Use configurable endpoint/provider/storage inputs. No cloud, DNS name, account, issuer,
actual key or credential is assumed. No services, databases, directories for accepted
history or infrastructure resources are provisioned by this plan. Existing measured
PostgreSQL deployments remain read-only reference evidence, three resources across two
synthetic tenants per application. External writers remain uninventoried.

## Future milestones and admission gates

1. **Architecture review now:** choose the final adapter/proof protocol, real trust model,
   nonce reservation/reconciliation, historical revocation policy, witness and recovery
   model. Approve or reject the revised genesis subjects separately per application.
2. **Separate implementation authorization:** implement an external real authority adapter,
   authenticated gateway, operation ledger, receipt and witness/export integration.
   Do not expose raw repository constructors or use reference-authority test credentials.
   Maintain the native verdict shape and canonical/semantic contracts.
3. **Authorized integration testing:** demonstrate every threat/recovery case with isolated
   real identities and storage under explicit testing authorization. Pure tests today
   do not establish those guarantees. No human approval is simulated as a production grant.
4. **Separate construction authorization:** register exact host/repository/configuration
   identities, provision selected infrastructure and enroll real principals/keys through
   actual authority procedures. Record authenticated trust bindings and storage/witness
   ownership. Construction still grants no genesis or semantic acceptance.
5. **Exact genesis review and authorization:** freeze actual source, real author, plan,
   repository/configuration, proof policy and expected empty state. Human reviewer signs
   the final exact operation only after genuine independent review. Existing review-only
   packages, historical fixture proofs and broad role grants cannot replace this action.
6. **Separate prospective transitions:** after each verified/witnessed head, prepare and
   review execution-v03 then deterministic-v04. Keep execution MIGRATION scope and
   separately approved declaration. No automatic acceptance of the next stage.
7. **Independent downstream gates:** retained-data binding, executable migration and
   deployment each need their own approved evidence and narrow grants. This plan authorizes
   none of them. Never infer these permissions from a successful history append.

Any future implementation touching a file in the sealed generator bundle requires an
intentional successor release. Keep sealed 0.4.0/0.5.0 bytes and approved Canonical
snapshots unchanged. External adapter placement is not permission to weaken admission.
Keep historical approvals and all prior review packages immutable.

## Hosted evidence and local verification

Requested run [38270051115](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/38270051115)
completed against exact source `2b8cb7603f82ad696679157937fd3f9d1fbd04e4`.
All four ordinary engineering jobs succeeded. Overall conclusion: **failure**, because
the separately reported closure gate returned `PHASE6_CLOSURE_BLOCKED`, exit 2.
No overall workflow pass or Phase 6 closure is claimed.

| Job | Observed conclusion |
| --- | --- |
| contracts | success |
| phase5-experiments | success |
| phase5c-hard-gates | success |
| phase6-target | success |
| phase6-closure-audit | failure; audit PERFORMED, PHASE6_CLOSURE_BLOCKED, exit 2 |

Exact [run](../proposals/phase6-route-a-integration-review/evidence/ci-run.json),
[job conclusions](../proposals/phase6-route-a-integration-review/evidence/ci-jobs.json),
[uploaded artifact metadata](../proposals/phase6-route-a-integration-review/evidence/ci-artifacts.json)
and [closure log excerpt](../proposals/phase6-route-a-integration-review/evidence/closure-exit.txt)
are retained separately from all earlier observations. The closure log reports no
`AUDIT_EXECUTION_EXCEPTION`; exit 2 denotes completed evaluation with blockers under
the unchanged evaluator. Earlier blocker records remain immutable.

That run concerns committed `2b8cb76`, not the new local tests, CI step or design documents.

Local verification: 11 pure replay tests PASS; 13 retained-inventory regressions PASS;
repository checks PASS; sealed release check PASS with unchanged 0.5.0 bundle digest
`ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb`.
The [review manifest](../proposals/phase6-route-a-integration-review/manifest.json)
binds the new deliverables and validation evidence.

## Required end state

Route A SELECTED FOR ENGINEERING DESIGN; semantic replay EXACTLY REPRODUCIBLE;
real authority adapter DESIGNED, NOT DEPLOYED; reference history NOT INITIALIZED;
genesis and transitions NOT AUTHORIZED; authenticated content proofs PENDING;
independent data bindings NOT APPROVED; executable migration and deployment NOT
AUTHORIZED. Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED. STOP FOR HUMAN ARCHITECTURE REVIEW.

## Conditional-review hardening

The [gateway and ledger contract](phase6-route-a-gateway-contract.md) specifies the
trusted context lifecycle, closed durable states, retry retrieval authorization,
independent historical context and exact remaining human decisions. It supplements
this reviewed design; implementation and construction remain unauthorized. Earlier
manifest hashes describe document bytes at `c9949c4` and remain historical evidence.
