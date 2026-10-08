# Final F-01 extension of the deterministic-v04 proposal

Status: **PROPOSED / HUMAN REVIEW REQUIRED**. Engineering extension of `b85be70a00c8edd0bef78179ece594775a92fd62`; repository publication of that earlier batch approved no new application meaning. ADR-0015 / Authoring 0.3 / Canonical 0.2 remain accepted/approved and unchanged. ADR-0016 / Authoring 0.4 / Canonical 0.3 / ChangeSet 0.3 remain proposals. Phase 6 IN PROGRESS; Phase 7 NOT STARTED.

## Complete proposed behavior

F-01 is resolved by an embedded, closed, semantically ordered Command `failureBindings` construction: exact declared Failure reference, explicit stage and exact workflow, pure typed predicate, applicable WRITE invariant or portable infrastructure trigger. The [complete ADR-0016](adr/0016-deterministic-query-lifecycle-and-rate-semantics.md) defines category/context restrictions, stage precedence, reached-condition semantics, rollback, retry identity and the typed semantic envelope. No target exception name or SQLState enters Canonical IR.

Payment CMD-RECORD explicitly binds FAIL-BUSINESS to workflow non-applicability on WF-PAYMENT. Case CMD-REVIEW / CMD-APPROVE / CMD-ARCHIVE bind it on WF-CASE. Each explicitly binds FAIL-TRANSIENT to portable DEPENDENCY_UNAVAILABLE. Codes do not choose triggers. Potential operational conditions are permitted declarations without manufactured runtime failures. All fixture choices are HUMAN REVIEW REQUIRED; only proposed schemas, plans and hashes were regenerated, with no fresh approval proof or applied journal.

[Repeated audit](phase6-f01-semantic-reaudit.md): **KNOWN_CANONICAL_GAPS_FOR_PHASE6_REFERENCE_DOMAINS = 0 at the proposal level**. It rechecks all required areas and interactions against both exact reference apps, accepted contracts and the complete successor. Remaining work is target implementation or deployment evidence; human authority is still outstanding. Queries in these fixtures are projections, not ExecutionSteps, so no symmetry-only Failure declaration is added. Shared Command/Transition event constructions retain the accepted one-occurrence rule.

## Separate target mechanism

The versioned target classifier is now 1.1.0. Exact SQL serialization/deadlock conditions map to SERIALIZATION_CONFLICT, not dependency unavailable. Exact listed connection-failure conditions map to DEPENDENCY_UNAVAILABLE; exact timeout recognition supplies a TIMEOUT classification. Unknown states/classes, unlisted subclasses and arbitrary wrappers cannot broaden the mapping, and message text cannot change it. One recognized concrete condition produces at most one portable class.

This helper never selects an application Failure or grants retry. A future binding executor must verify the fault's reached execution site, declared deadline context for timeout, and commit/rollback fact before treating recognition as an applicable semantic occurrence. Current generic diagnostic responses remain platform transport outcomes. No generated semantic Failure runtime or capability promotion is introduced. Failure stays UNSUPPORTED; the target stays INCOMPLETE and all 27 expected blockers stay unchanged.

## Validation

Complete local regression: **213 tests PASS in 1274.781 seconds**. The final focused module additionally covers the direct per-command case-state test added after full-suite discovery; together the runs validate the complete current test set. The final focused F-01 suite passes 14 tests in 86.192 seconds with multiple negative/positive variants covering exact membership/revisions/kinds, stage order, duplicate ambiguity, categories, Boolean/context typing, exact machine/invariant scope, portable faults, valid payment/case execution, rollback, STOP, predicate overlap, SECURITY separation and retry identity preservation.

Independent Node verification passes all three corpora (Canonical 0.1, approved 0.2, proposed 0.3): each has 9 positive byte vectors, 13 negative vectors and 2 actual snapshot hashes. The canonical byte profile and historical hashes are unchanged. Dependency consistency and repository checks pass. Local Linux uses CPython 3.14.4 / Node.js 24.21.0; official Ubuntu 24.04 CI retains CPython 3.14.7 / Node.js 24.21.0.

[Generated component evidence](../targets/spring-vue-postgres/evidence/f01-components-linux.json): payment 29 and case 28 PostgreSQL Java tests, zero failures/errors/skips, plus passing Vue tests/type checks/builds. Portable classifier tests exercise unknown SQL/runtime exceptions, misleading message text, unlisted subclasses/wrappers and nested faults with a single classification. These component checks do not admit either complete application.

[Expected-open gate](../targets/spring-vue-postgres/evidence/f01-expected-open-linux.json) remains BLOCKED at real negotiation with exactly 27 blockers per approved Canonical 0.2 application; expected-open mode exits successfully. The [actual strict gate](../targets/spring-vue-postgres/evidence/f01-strict-linux.json) exits 1 with BLOCKED negotiation, preserving closure red. Proposed Canonical 0.3 is independently tested and never substituted into the production gate. The [actual migration CLI results](../targets/spring-vue-postgres/evidence/f01-migration-linux.json) return REVIEW_REQUIRED with no candidate, including missing failureBindings.

[Published main CI](../targets/spring-vue-postgres/evidence/f01-main-checkpoint-ci.json) is GREEN at `b85be70a00c8edd0bef78179ece594775a92fd62`: [Ubuntu run 37737968707](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/37737968707). All contract, Phase 5 and Phase 6 expected-open/component jobs succeeded. This is existing-main evidence, not hosted CI for this uncommitted F-01 extension. The existing workflow automatically includes the new successor tests and all preservation/vector gates.

Local `/tmp/acp-f01-*` logs and generated directories are ephemeral local evidence only. Checked-in reports retain results without relying on temporary paths. Earlier phase/proposal reports and approved artifact bytes are preserved.

## Human review boundary

Technical validation is green. Request one final explicit human approval of the complete ADR-0016 and all deterministic-v04 synthetic fixture decisions together. Do not record approval, issue fresh Canonical 0.3 authority, resume dependent implementation, promote Failure, close Phase 6 or start Phase 7. Changes were prepared on `codex/phase6-explicit-failure-bindings`. The user authorized committing, merging and pushing this engineering proposal; publication does not constitute semantic acceptance of ADR-0016.
