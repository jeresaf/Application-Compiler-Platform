# Approved execution 0.3 synthetic reference-domain decisions

Status: APPROVED REFERENCE SEMANTICS. The human project authority explicitly supplied `Approve ADR-0015 and the execution-v03 fixture decisions.` on 2026-10-08. AI proposed these semantics; human approval is a separate subsequent act. They are authoritative only for ACP reference applications/corpora validating compiler behavior, not production business requirements. Stable names are not evidence for assignments. Fresh exact-content approval for both Canonical 0.2 snapshots and upgrade plans is recorded in [the reference authority record](../test-corpus/execution-v03/human-approval.json); historical Canonical 0.1 approval is not reused.

| Site | Approved reference fixture decision |
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

The general model is broader than the approved summary-only fixture behavior: tests exercise exact Money assignment, ordered interacting effects, typed query inputs/projections and complete event construction. No implied CRUD, anonymization replacement, closure timestamp or pagination-order behavior is added. See the [inventory](execution-dataflow-inventory.md), [ADR](adr/0015-explicit-operation-effects-and-dataflow.md) and [validation report](execution-v03-completion-report.md).
