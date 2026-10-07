# Proposed execution 0.3 reference decisions for human review

These decisions are explicit proposed test semantics, recorded with AI proposal provenance. They are not human-authored or approved business behavior until reviewed. Stable names are not evidence for any assignment. Exact new approval must bind the complete Canonical 0.2 snapshot, not this prose alone.

| Site | Proposed fixture decision |
| --- | --- |
| Both use cases | Require task text plus an exact root-resource Identifier. The resource must already exist and remain authorized in the actor's tenant. |
| Payment `CMD-RECORD` | Consume operation text; assign only `FLD-TASK-SUMMARY`; preserve amount, identity, tenant and unrelated fields. Return the resulting summary. Existing positive-amount guard and invariant still apply. |
| Case `CMD-REVIEW` | Consume use-case text through an explicit operation input; assign only the root summary. Return the resulting summary. Do not create or update review/assignment child records from the command's name. |
| Case `CMD-APPROVE` | Consume the prior review step's exact result member; assign only root summary; return that summary. Do not invent approval records. |
| Case `CMD-ARCHIVE` | Consume the prior approval step's exact result member; assign only root summary; return that summary. Existing workflow transitions still determine state. |
| Both use-case outputs | Return the last step's exact result text only after successful transaction completion. |
| Payment event | Populate amount from checked post-command state, with the exact Money type. Shared command/transition declarations produce one occurrence. |
| Case events | Populate the nested case-title ValueObject from checked post-command state for each command occurrence. Shared command/transition declarations produce one occurrence per command. |
| Both task queries | Bind the String Filter value to Query input `QUERY-TEXT`; apply case-sensitive code-point substring containment against resource summary; retain the existing per-row summary projection and tenant scope. |
| Both scheduled tasks | Explicitly bind literal text `Explicit scheduled fixture text` and resource identity `fixture-resource`. These are reproducible test invocation values, not production scheduling defaults. |

The general model is broader than the proposed summary-only fixture behavior: tests exercise exact Money assignment, ordered interacting effects, typed query inputs/projections and complete event construction. No implied CRUD, anonymization replacement, closure timestamp or pagination-order behavior is added. See the [inventory](execution-dataflow-inventory.md), [ADR](adr/0015-explicit-operation-effects-and-dataflow.md) and [validation report](execution-v03-completion-report.md).
