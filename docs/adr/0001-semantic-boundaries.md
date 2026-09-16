# ADR-0001: Typed semantic boundaries

Status: ACCEPTED. Date: 2026-09-15. Basis: charter §§2, 7–8, 15, 36, 41–44.

## Decision

Keep authoring state, semantic AST, Canonical IR, architecture/design realization, Target IR, source observations, and runtime evidence distinct. A canonical snapshot contains typed records and resolved references. Product, domain, and application projections share canonical identity; they do not mutate each other or maintain competing business rules. Lowered nodes retain many-to-many origin links and obligation mappings.

Create `docs`, `contracts`, `test-corpus`, and `tooling` now. Document future ports before creating production packages. A structured contract fixture is sufficient to exercise the semantic kernel.

## Alternatives and evidence

- Parser AST as core: cannot satisfy replaceable frontend or framework-neutral meaning (charter §§8, 23).
- One mutable universal object: mixes authority, analysis, realization, and observations; makes stage preconditions difficult to enforce (§44).
- Full proposed package tree now: boundaries are not yet demonstrated (§42).
- Typed immutable records and explicit transforms: directly supports stage-local validation, semantic diffs, ownership, and traceability.

## Consequences and validation

Cross-stage mappings become required data, with real storage/validation costs. Some logical records may share one runtime later, but adapters may not leak into the kernel. Unknown semantic kinds must be rejected rather than stored in an unchecked extensions bag. Kernel fixtures verify closed shapes, references, typed expressions, and proposal isolation; architecture and target conformance remain later work.
