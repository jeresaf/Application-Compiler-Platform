# Phase 6 realization bindings — proposal, not approved behavior

The approved Canonical snapshots describe use-case input/output types and ordered execution steps. They do not specify which operation receives an input member, which resource field it mutates, or how a use-case output is constructed. Query projections specify query output only. The target must not derive these behaviors from names or silently treat required inputs as unused.

This proposal introduces an independently reviewed realization input without editing historical Canonical snapshots, accepted compiler contracts or Phase 1–5 evidence. It is not implemented, approved or sufficient for capability admission.

A binding document would carry a version, the exact Canonical snapshot digest, exact semantic IDs/revisions, an independently approved document digest and explicit operation bindings. The compiler host would validate approval before lowering. The worker would receive the immutable approved value and have no approval authority. Its digest would contribute to Target IR, generated artifact provenance and admission identity. Changed bindings would require new approval. No target-specific inference would supply absent bindings.

Each operation binding must declare the input members consumed, the execution step receiving them, the resource fields written, and pure typed expressions producing those values. Each output binding must declare a typed expression for every required output member and its evaluation point relative to transaction commit. All writes must respect declared write sets, authorization, tenant scope, aggregate boundaries, invariants and optimistic concurrency. Unsupported or inconsistent bindings must reject compilation.

The immediate decision for both reference domains is whether the task text should update `FLD-TASK-SUMMARY`, which execution step performs that update, and whether `OUTPUT-TASK-TEXT` should return the committed summary or another explicitly specified value. These are business-behavior decisions, not consequences of the identifiers. No assignment is approved by this proposal.

If a separately versioned realization input is not permitted, the missing behavior requires a separately approved semantic-model decision before these use cases can be admitted. In either case, current use-case negotiation remains unsupported. Phase 6 stays IN PROGRESS and Phase 7 stays NOT STARTED.
