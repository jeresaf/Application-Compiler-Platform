# Phase 6 declared Failure target implementation contract

Status: PLAN ONLY / Failure UNSUPPORTED. Accepted [ADR-0008](adr/0008-execution-semantics.md) distinguishes BUSINESS, SECURITY and TRANSIENT; only declared retryable TRANSIENT failures participate in bounded retries. [ADR-0015](adr/0015-explicit-operation-effects-and-dataflow.md) defines execution and rollback barriers. Infrastructure exception mapping is a separate mechanism and does not constitute semantic Failure support.

## New audit finding F-01

Classification: **CANONICAL_SEMANTIC_REQUIRED**. Failure declares `code`, `category` and `retryable`. Commands list exact Failure references. Neither declaration supplies an executable predicate or exact runtime-condition-to-Failure binding. The reference executor raises mechanism-level INVARIANT, DENIED, WORKFLOW, INPUT_OR_OUTPUT_TYPE and QUERY_NO_RESULT signals, but does not bind those signals to a particular declared Failure ID/revision. An invariant violation and a Failure named INVALID_STATE are not evidence that the former produces the latter. If an operation declares two BUSINESS failures, targets could choose different codes for the same state/input while satisfying the current shape.

No target may infer a trigger from a code/name, exception message, declaration order, framework class, invariant proximity or a generic catch. F-01 is newly discovered while preparing this contract; the original five deterministic audit gaps are resolved in the unapproved proposal, but this distinct question remains explicit. Do not implement semantic Failure until a human-reviewed canonical choice binds exact conditions to declarations and defines precedence when multiple triggers apply. This document proposes no trigger syntax, new version or approval. Review whether typed predicate/guard bindings or a closed exact semantic failure-site binding best fits the accepted expression language before amending any still-unapproved successor.

## Implementation boundary once trigger semantics are approved

A lowering contract must bind each supported declared failure to its exact operation and semantic ID/revision, code/category/retryable and approved trigger. Validate trigger inputs/types/scope, category/retry compatibility, exhaustive handling and precedence; reject unsupported declarations at negotiation. Do not turn failure declarations into generic documentation-only obligations while claiming support.

Generated Command/Query execution must deliberately evaluate those bindings at their specified semantic sites. A declared failure aborts the current semantic transaction: tentative domain changes, outputs, event intents and idempotency-success finalization roll back. UseCase STOP/COMPENSATE follows accepted explicit step semantics and preserves already committed earlier boundaries. Do not add distributed rollback. Query absence/authorization/invariant failure maps to a declared Failure only when an approved binding says so.

Transport a typed failure envelope with exact semantic reference and declaration fields. HTTP status/header/wire representation is a versioned target-profile decision with a closed mapping preserving distinctions. Public messages and diagnostics cannot expose resource values or raw exception causes. Retry only exact declared retryable TRANSIENT failures allowed by the bound RetryPolicy, preserving occurrence/idempotency identity and retry horizon; BUSINESS/SECURITY are never automatically retried. A caught infrastructure SQLState may become a declared transient failure only through an approved exact binding; unknown faults stay safe INTERNAL, never fabricated BUSINESS.

## Required evidence and admission

Before support, run generated backend and HTTP tests proving every deliberate BUSINESS/SECURITY/TRANSIENT declaration, undeclared/unknown rejection, trigger overlap precedence, rollback and prior-boundary preservation, no duplicate events, exact retry eligibility, query failure, wrong-tenant denial, redacted diagnostics and unknown-exception INTERNAL behavior. Test real PostgreSQL transaction failures and generated UseCase control flow, not only a mapping helper. Browser error handling must consume the typed contract without inventing a business success.

Keep Failure UNSUPPORTED and the exact current expected blocker until those conditions hold. The existing versioned infrastructure mapper and value-free audit may continue independently; they cannot resolve F-01 or remove Failure's blocker.
