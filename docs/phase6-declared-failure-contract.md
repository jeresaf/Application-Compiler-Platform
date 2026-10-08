# Phase 6 declared Failure implementation contract

Status: PLAN ONLY / Failure UNSUPPORTED. F-01 was discovered in the earlier audit because Failure codes/categories and Command references did not bind runtime conditions. The complete still-PROPOSED [ADR-0016](adr/0016-deterministic-query-lifecycle-and-rate-semantics.md) now supplies exact ordered FailureBinding semantics in Authoring 0.4 / Canonical 0.3 / ChangeSet 0.3. No trigger is inferred from a name, code, exception, nearby invariant or framework default.

## Canonical lowering boundary

Lower exact Command failureBindings only after human acceptance and fresh Canonical 0.3 approval. Bind exact Failure/operation revisions, trigger, evaluation stage and authored precedence. Supported triggers are WORKFLOW_NO_APPLICABLE_TRANSITION (exact applicable machine), PREDICATE (pure Boolean in PRE_STATE or POST_ASSIGNMENT), INVARIANT_FAILURE (exact applicable WRITE invariant), and INFRASTRUCTURE_CLASS (closed portable class). Validate declaration coverage, context, category, exact references and nonambiguous ordering before generation. Reject unsupported declarations rather than retain them as documentation while claiming support.

Generate pre-state workflow applicability and ordered PRE_STATE checks; staged assignments; POST_ASSIGNMENT predicates; bound and remaining invariants; the selected state transition; typed output/event construction; atomic successful commit. Do not reevaluate workflow guards against post-state. Shared Command/Transition event constructions retain accepted ADR-0015 identity/dedup meaning. A failure rolls back the current boundary's tentative state/output/events/idempotency success; STOP prevents subsequent steps. Earlier committed boundaries and explicit compensation retain accepted rules. Do not add distributed rollback.

## Provider classification remains separate

Target mapping 1.1.0 classifies only exact listed runtime classes/SQLStates into portable DEPENDENCY_UNAVAILABLE, SERIALIZATION_CONFLICT or TIMEOUT. It never selects a final semantic Failure. Exact known ordinary wrappers may expose a recognized cause; arbitrary subclasses/wrappers and message text cannot broaden classification. Unknown faults remain INTERNAL. One concrete fault selects at most one portable class.

Canonical bindings alone decide whether that class produces a declared TRANSIENT Failure for this operation. The fixtures bind dependency unavailability, not serialization conflict or timeout. Retry requires a trusted occurrence from an exact approved binding, exact RetryPolicy membership, TRANSIENT and retryable true; a transport envelope is not authority. Preserve operation, scheduled occurrence, typed input and idempotency identity. Prove rollback/no effect before releasing a claim or retrying; an indeterminate commit retains IN_PROGRESS until recovery proves commit or rollback.

## Typed transport requirements

The generated semantic Failure envelope carries exact Failure ID/revision, code, category, retryable, exact operation ID/revision and a generated opaque correlation identifier. No raw sensitive values, exception messages/causes, SQL diagnostics or traces. A closed target transport contract chooses HTTP status/body/header representation while preserving semantic identity across transports. Authentication/session/authorization denial remains platform security protocol behavior unless an explicit semantic binding applies; it never picks an arbitrary SECURITY declaration. Reference provenance/binding indexes are private test evidence and not a public approval mechanism.

Queries in these fixtures have no semantic Failure declarations and are not ExecutionSteps. Preserve their independent result/absence behavior; do not add symmetry-only failure bindings or infer a no-result code. A future declared Query Failure subset requires explicit canonical design.

## Required evidence before support

After approval, run generated backend and HTTP tests for every deliberately bound BUSINESS/SECURITY/TRANSIENT Failure, exact precedence, stale/undeclared/unknown rejection, current-boundary rollback, prior-boundary preservation, no duplicate events, retry eligibility and identity preservation, wrong-tenant denial and redacted diagnostics. Test real PostgreSQL provider classification and generated UseCase control flow, not only mapping helpers. Browser error handling consumes the typed envelope without fabricated success.

Pure reference tests and portable classifier tests are engineering evidence only. Keep Failure UNSUPPORTED until approval, fresh snapshots, actual generated execution, backend/PostgreSQL and HTTP tests, and honest constrained negotiation all exist. The exact current expected-open blockers remain unchanged.
