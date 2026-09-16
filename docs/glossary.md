# Glossary

| Term | Meaning |
| --- | --- |
| Meta-model | Types, relations, constraints, identity, and lifecycle rules used to describe applications |
| Specification | Versioned desired intent, including candidate and approved revisions kept distinct |
| Semantic AST | Frontend-independent unresolved representation with source locations and references |
| Canonical IR | Resolved, typed, normalized, framework-neutral approved semantic snapshot |
| Product / Domain / Application IR | Bounded projections of canonical intent, business semantics, and behavior; not competing authorities |
| Architecture IR | Selected technical realization, capabilities, enforcement plan, and decision provenance |
| Design IR | Design tokens, visual components, and interaction realization separated from UI intent |
| Target IR | Framework/runtime-specific lowered representation |
| Semantic ID | Immutable identity within one application; never derived from current name or source offset |
| Revision | Immutable version of a concept; positive integer in the kernel |
| Snapshot | Immutable closed set of exact concept revisions plus model version |
| Reference | Semantic ID and exact revision resolved within a snapshot |
| Basis | Requirement/decision references justifying a semantic concept |
| Origin | Who supplied a statement and where; distinct from justification and approval |
| Approval | Authority-backed attestation to an exact revision/change digest |
| Evidence | Observation supporting an obligation for specific versioned inputs; can become stale |
| Obligation | Required enforcement or verification derived from semantics |
| Lifecycle | Authoring/approval/retirement state, independent of implementation and evidence |
| Change set | Intent plus revision-checked semantic operations and required impact/approval evidence |
| Semantic diff | Meaningful change by stable ID, independent of textual formatting |
| Ownership | Authority to modify a source artifact/region under an explicit extension contract |
| Drift | Difference between desired, observed source/infrastructure, or runtime state |
| Capability | Versioned semantic behavior a target can implement with stated constraints |
| Diagnostic | Stable code, affected semantic references, location, explanation, and repair guidance |
| Production profile | Baseline gates plus application/target/environment-specific requirements |
| Kernel-valid | Passes the implemented Phase 1 subset; says nothing about unimplemented production gates |
