# ADR-0006: Bounded domain, type and rule semantics (P-01)

Status: ACCEPTED under the Phase 1 completion instruction. Date: 2026-09-16.

## Decision

Promote ValueObject, Relation, Aggregate and TypeDefinition into the shared semantic-node contract. Every new kind inherits stable ID, revision, lifecycle, steward, origins, basis and exact local references. Value objects own fields and compare by typed value; entities compare by typed identity. Aggregate members have one consistency owner and one root; writes enter through root commands. Composition is acyclic and belongs within one aggregate. Relations state both cardinalities and deletion behavior explicitly.

TypeDefinition provides nominal/refined scalar types with a bounded range/length refinement algebra. No arbitrary executable predicates or host-language regexes are accepted as refinements. Add bounded List/Set, Nullable, value-object and named types. Field absence (`optional`) is distinct from explicit null (`Nullable`). Presence and coalescing are explicit; absent/null values never coerce to Boolean or numeric values.

Decimal and Money declare precision, scale and rounding (REJECT, HALF_EVEN, HALF_UP, DOWN). Stored literals must already fit; rounding is an explicit operation, never ingestion repair. Arithmetic cannot implicitly convert currency or nominal type. Date is a calendar date, Instant is UTC, LocalDateTime has no offset, and Duration is fixed nonnegative seconds. Local schedules separately declare timezone, DST-gap and overlap behavior. General calendar-period arithmetic is deferred and rejected.

## Alternatives and consequences

Primitive erasure loses currency/identity constraints; a universal expression evaluator creates an unbounded language before semantic stabilization. The bounded algebra gives precise tests and portability, at the cost of rejecting richer expressions until explicitly versioned. No storage layout, ORM association, parser runtime or target language is selected.

Introduce authoring model `0.2.0`; retain the original `0.1.0` contract and corpus unchanged as historical regression tests. Historical validation is not permission to bypass current semantics. No automatic migration or Canonical IR format is introduced. Tests must cover two domains, cyclic ownership, cardinality, null/presence, nominal equality, collections, precision, rounding and temporal literals.

## Safe deferrals

Recursive value types, arbitrary refinements/quantification, calendar periods, currency conversion and multi-aggregate atomic writes are rejected. They do not prevent an IR from representing the accepted bounded algebra. Runtime enforcement and generated constraints remain later-stage obligations, not Phase 1 implementations.
