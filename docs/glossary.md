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
| Kernel-valid | Passes the historical 0.1.0 contract; does not satisfy current 0.2.0 obligations or production gates |
| Phase 1 model-valid | Passes closed 0.2.0 shape and semantic checks for the selected authoring profile; not Canonical IR or runtime certification |
| ValueObject | Nonempty acyclic owned field definition; instances compare by typed value, not entity identity |
| Relation | Entity endpoints with explicit cardinalities, reference/composition ownership and deletion behavior |
| Aggregate | One root plus member entities with a single atomic consistency owner; commands enter through the root |
| Named type | Exact TypeDefinition reference retaining nominal identity and bounded refinement rules |
| Presence / nullability | Optional permits absence; Nullable permits explicit null; neither coerces implicitly |
| Scope | Explicit actor/resource boundary; SCOPED entities require matching tenant identifier fields |
| PolicySet | Complete policy composition for an operation: default DENY, matching DENY overrides ALLOW |
| DataLifecycle | Resource-specific retention/deletion/hold obligations; not actual disposal execution |
| UseCase / Service | Ordered task steps and their logical operation ownership boundary; no deployment topology implied |
| Idempotency / delivery | Explicit replay/conflicting-input/window obligations and at-most/at-least-once event delivery declarations |
| Screen | Task-oriented page semantics with actions, view states and permission/accessibility boundaries |
| Design binding | Independent versioned catalogue association to exact semantic UI references; not a renderer or Design IR |
| Applicability | Decision-backed closed Boolean condition governing an evidence obligation; false requires review |
| EvidenceRequirement | Exact subjects, required verification methods, applicability and maximum observation age |

The [0.2 meta-model](metamodel.md) defines the accepted vocabulary precisely. Model ownership also includes structural containment and aggregate/Service responsibility; source-region ownership in the table above is a separate later-stage concern. Modeled authentication, encryption, transactions, accessibility and recovery are obligations, not implemented runtime services.
