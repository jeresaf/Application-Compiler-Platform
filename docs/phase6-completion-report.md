# Phase 6 implementation status — NOT CLOSED

Phase 6 is IN PROGRESS. This file is not an acceptance or completion claim. Phases 1–5 retain their approved historical status. Phase 7 is NOT STARTED. No generated application is claimed production-ready.

The approved incomplete foundation is commit `65d1694a553dc3b08cd33a4c6909fbd86da258f9`. The earlier continuation used `codex/phase6-negotiated-target`; the approved-execution continuation is recorded separately below. The [target contract](phase6-target.md) records exact implementation boundaries and [ADR-0014](adr/0014-first-production-target.md) records the engineering direction.

Local Linux evidence collected on 2026-10-07: Ubuntu 26.04.1 LTS, CPython 3.14.4, Node 24.21.0, Temurin Java 21+35, Maven 3.10.0 and libseccomp 2.6.0-2ubuntu5. Official Ubuntu 24.04 / CPython 3.14.7 CI is still outstanding. The [reproducible template report](../targets/spring-vue-postgres/evidence/template-checks-linux.json) records both domains and their explicit admission failures.

| Check | Result and limits |
| --- | --- |
| Continuation complete regression run | 124 tests PASS, 340.058 seconds; final added/updated boundary cases separately rerun below |
| Canonical byte/hash verification | PASS: 9 positive, 13 negative, 2 snapshot hashes; canonical corpus unchanged |
| Repository/document checks | PASS before final documentation updates |
| Worker/store/provenance foundations | 16 tests PASS, including atomic staging failure, negotiated project-capability enforcement and rejection of unbound use-case behavior |
| Continuation worker fault supervision | 7 tests PASS: streaming limits, malformed output, timeout/crash/signal, sandbox failure, parallel workers and bundle integrity |
| Continuation materializer faults | 6 tests PASS: concurrent stale writers, crash before publication, unknown insertion, root/parent symlink swaps and concurrent human edit |
| Final continuation focused rerun | 33 tests PASS, 23.616 seconds: foundations, worker faults, materializer faults and target migrations |
| Final Compiler Core regression rerun | 29 tests PASS after the project-artifact extension; synthetic vectors unchanged |
| Target upgrade planner | 4 tests PASS, including required backfill, stale/unauthorized history, rename continuity and destructive blocking |
| Payment backend template fixture | Java 21 / Spring Boot 4.1.1 compile and 5 JUnit tests PASS, including real Flyway/PostgreSQL 18.6 |
| Case-management backend template fixture | Independently compiled; same 5 tests PASS against real PostgreSQL 18.6 |
| Payment frontend template fixture | Type checking PASS; 4 component tests PASS; Vite production build PASS |
| Case-management frontend template fixture | Clean npm lockfile install, type checking, 4 component tests and Vite production build PASS |
| Complete production-target compilation | BLOCKED by explicit unsupported capability errors for both domains |
| Six-step accepted-history target evolution | NOT COMPLETE |
| Browser journeys / API integration | NOT RUN |
| Ubuntu Phase 6 CI | NOT RUN; full target job not yet implemented |

The application-template checks bypassed capability admission deliberately to test source templates in isolation. Their `/tmp` files/logs and PostgreSQL container are ephemeral local evidence. They do not show that either complete canonical reference domain has passed the target pipeline.

Continuation identified a semantic blocker: accepted use-case inputs/outputs and ordered operations do not declare input-to-mutation bindings or output construction. For example, `INPUT-TASK-TEXT` has no declared assignment to `FLD-TASK-SUMMARY`; the query projection does not establish a use-case output binding. Inferring these effects from names would violate the continuation requirement to reject insufficient semantics. The later continuation rejects [target realization bindings](phase6-realization-bindings-proposal.md) as an authority for business semantics. [ADR-0015](adr/0015-explicit-operation-effects-and-dataflow.md) and its [dedicated semantic-evolution report](execution-v03-completion-report.md) introduce separately versioned authoritative effects/dataflow. The human project authority explicitly approved ADR-0015 and the execution-v03 fixture decisions on 2026-10-08. The semantic blocker is resolved and target implementation resumes against Canonical 0.2; the remaining target gates below still apply.

Remaining exit gates include complete fail-closed capability enforcement; canonical authentication assurance/session/idempotency/rate semantics; relation/cardinality persistence; jobs/schedules/retry with declared timezone data; privacy lifecycle enforcement; event delivery; approved migration integration and the complete evolution sequence; all generated security/tenant/workflow/API/database tests; selected real browser journeys; full design-role and extension coverage; versioned configuration/observability contracts; deterministic container packaging; complete dependency inventory/license provenance and locking; adversarial worker/materializer supervision; full Ubuntu CI and final regression evidence.

P-08 and generated-source P-09 have prototype contracts and tests, but their required Phase 6 acceptance remains outstanding. ADR-0004's production-core runtime and textual frontend remain independently DEFERRED. No Phase 7, 8, 9 or 10 implementation has begun.

## Approved execution continuation — 2026-10-08

Work on `codex/phase6-approved-execution` consumes the freshly approved exact Canonical 0.2 reference snapshots. The original evidence above remains historical evidence for the earlier foundation. The human approval and the executable public test-key reference representation are distinct from the AI fixture proposal. Authoring 0.3 and Canonical 0.2 are APPROVED AND GREEN; ChangeSet 0.2 is GREEN. Phase 6 remains OPEN and Phase 7 is NOT STARTED.

The target now compiles exact typed Command/Query/UseCase records, ordered staged assignments, prior-step results, explicit output/event payloads and one-root-instance atomic STOP flows. Standalone commands use a transaction boundary. Guards read pre-state; invariants read post-assignment staged state. PostgreSQL tests exercise exact writes, unchanged fields and child tables, rollback of all steps and event intents, authorization/tenant boundaries, strict HTTP codecs, Money precision/currency, refined nominal types, session expiry/revocation and deferred relation constraints. These are component checks, not complete application acceptance.

Canonical 0.2 String/Identifier/Named(String) values use strictly validated UTF-8 bytes in PostgreSQL `bytea`; nested ValueObjects use their typed JSON UTF-8 bytes. This preserves U+0000 and avoids PostgreSQL text/jsonb restrictions. SQL byte substring containment is equivalent to code-point containment for valid UTF-8 values and patterns. Optional nullable entity fields have a separate presence bit. Query input uses a typed JSON POST body, including the exact `QUERY-TEXT` member. This target storage choice changes no neutral semantics or canonical vectors and supplies no encryption guarantee.

`DataClassification`, `RatePolicy`, `IdempotencyPolicy`, `DeliveryPolicy`, `Job`, `Schedule`, `RetryPolicy`, `DataLifecycle`, `Retention`, `DeletionPolicy` and `LegalHold` remain UNSUPPORTED. They are not made supported by template presence. Complete admission also rejects unspecified pagination ordering, CLOSED retention timestamps and anonymization replacements. The [inventory](execution-dataflow-inventory.md) records those semantic gaps; target code does not invent them. Infrastructure failure-category mapping still needs an explicit decision.

The dedicated Ubuntu 24.04 `phase6-target` CI job runs [the strict negotiated gate](../tooling/check_phase6_target.py) with PostgreSQL 18.6, CPython 3.14.7, Node 24.21.0 and Java 21. The gate uses the real compiler/ProductionTarget, fresh reference approval, deterministic plans, CAS materialization, human ownership and provenance checks before generated builds and browser checks. It currently fails at real capability admission for both domains. No `continue-on-error`, skipped admission or component bypass can make it green. Browser journey implementation and full negotiated database evolution remain outstanding; the semantic six-step history test does not establish those target gates. Hosted CI has not been run for this worktree.

To reproduce component diagnostics independently, run `tooling/check_execution_components.py --output /tmp/acp-execution-components --run-builds` with the documented ephemeral test-database environment. To reproduce the strict admission gate, run `tooling/check_phase6_target.py --output /tmp/acp-negotiated-target --run-builds`. Use fresh output directories. `/tmp` artifacts are ephemeral local evidence only.

Current [component evidence](../targets/spring-vue-postgres/evidence/execution-components-linux.json): payment 23 Java tests and case-management 22 Java tests PASS on PostgreSQL 18.6. Both frontends pass lockfile installation, type checking, 4 component tests each and production builds. These runs include NUL-containing strings and strict typed HTTP inputs. Historical and successor independent Node vectors each pass 9 positive, 13 negative and 2 snapshot hashes, unchanged. Fresh approval plus six-step semantic evolution tests pass (4 tests, 393.145 seconds); the complete regression now passes 166 tests in 1,364.475 seconds. Final focused target lowering checks pass 7 tests in 18.872 seconds; historical migration safety checks pass 4 tests in 35.355 seconds.

The [strict negotiated local gate](../targets/spring-vue-postgres/evidence/negotiated-gate-linux.json) reaches NegotiateLower for both approved domains and returns `ACP-COMPILER-CAPABILITY`, with explicit worker capability/semantic-decision diagnostics. Materialization, generated builds and browser checks are not reached by this gate. The separate component successes above do not bypass this result.

Final repository/documentation and dependency consistency checks pass. Generated artifacts for both domains match the exact artifacts used by the passing component builds. Phase 6 remains OPEN; pending capability enforcement, authoritative missing semantics, full negotiated database evolution and browser journeys prevent closure. Phase 7 remains NOT STARTED.

## Reviewed open-phase expectation — 2026-10-08

Checkpoint `101205d576aa690381c34dca480fe8053780367d` is human-approved as an incomplete Phase 6 foundation. The [versioned expected-blocker contract](../targets/spring-vue-postgres/expected-open-blockers.json) binds both exact already-approved Canonical 0.2 digests and every current admission blocker. The real compiler/ProductionTarget reaches NegotiateLower and its complete actual lowering admission error is captured directly, not reconstructed by a second negotiation. [Local evidence](../targets/spring-vue-postgres/evidence/expected-open-state-linux.json) records `EXPECTED_BLOCKED_STATE = PASS`; target admission remains BLOCKED.

The Ubuntu target job now uses `--expect-open-blockers` and depends on all historical contract/experiment gates. Added, disappeared or duplicate blockers, earlier failures, wrong snapshots and missing real admission fail the assertion. No `continue-on-error` or skipped admission is used. Any manifest state other than INCOMPLETE automatically removes the allowance and requires the complete negotiated build gate. Without the flag the command remains strict and returns failure for blocked admission. The earlier intentionally failing gate results remain historical evidence, not the current CI policy. Hosted green status must be verified separately; local expectation success is not hosted evidence. Phase 6 remains IN PROGRESS; Phase 7 remains NOT STARTED.

## Deterministic successor investigation

The approved execution checkpoint remains incomplete. The [successor proposal report](deterministic-v04-proposal-report.md) records the semantic audit, proposed separate contracts, capability-honesty corrections and safe partial runtime mechanisms. ADR-0016 remains PROPOSED / HUMAN REVIEW REQUIRED. Historical approved bytes and reports remain preserved. Phase 6 stays IN PROGRESS; Phase 7 is NOT STARTED.
