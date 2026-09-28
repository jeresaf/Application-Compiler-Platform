# Architecture decisions

ACCEPTED records an engineering choice within its stated scope. PROPOSED records investigation, not authorization. Supersession preserves history and links the replacement; no unperformed experiment is evidence for technology selection.

| ID | Status | Date | Decision / question |
| --- | --- | --- | --- |
| [0001](0001-semantic-boundaries.md) | ACCEPTED | 2026-09-15 | Typed semantic boundaries and minimal repository |
| [0002](0002-identity-lifecycle.md) | ACCEPTED | 2026-09-15 | Stable identity, exact references, independent lifecycle/evidence |
| [0003](0003-contract-harness.md) | ACCEPTED, tooling only | 2026-09-15 | JSON Schema and replaceable Python contract harness |
| [0004](0004-technology-evaluation.md) | **PROPOSED** | 2026-09-15 | Production language/frontend experiments and selection protocol; no selection |
| [0005](0005-open-architecture.md) | PROPOSED register; P-01 through P-05 and bounded P-07 superseded | 2026-09-15; resolution notes updated 2026-09-28 | P-06 and P-08 through P-13 remain unresolved |
| [0006](0006-domain-semantics.md) | ACCEPTED | 2026-09-16 | P-01 bounded domain/type/rule semantics; model 0.2.0 |
| [0007](0007-security-privacy.md) | ACCEPTED | 2026-09-16 | P-02 explicit security/privacy and mandatory tenant obligations |
| [0008](0008-execution-semantics.md) | ACCEPTED | 2026-09-16 | P-03 bounded execution, failures, consistency and delivery |
| [0009](0009-task-interfaces.md) | ACCEPTED | 2026-09-16 | P-04 task interfaces and independent design bindings |
| [0010](0010-quality-operations.md) | ACCEPTED | 2026-09-16 | P-05 measurable quality/operations and evidence contracts |
| [0011](0011-canonical-interchange.md) | ACCEPTED, bounded Phase 2 | 2026-09-28 | P-07 canonical interchange, normalization, digests, compatibility and candidate migration |

## Resolution without rewriting history

ADR-0005's P-01/P-02/P-03/P-04/P-05 rows describe the investigations as recorded. Their accepted replacements are ADR-0006/0007/0008/0009/0010 respectively, including explicit bounded exclusions. They are no longer open foundational Phase 1 questions. The remaining register stays PROPOSED.

The [current meta-model](../metamodel.md) and [coverage](../coverage.md) define executable 0.2 scope; [kernel 0.1](../kernel-0.1.md) preserves the original contract. [Completion report](../phase1-completion-report.md) records closure evidence.

P-07's bounded interchange/normalization questions are resolved by ADR-0011; see the [Phase 2 report](../phase2-completion-report.md). Production authority/signatures, persistence and plugin wire ABI remain later work.

**No production language, runtime or parser has been selected.** Python, JSON, the independent Node.js byte checker and CI action runtimes are development choices only. ADR-0004 remains PROPOSED because its required comparative experiments have not been performed. Phase 3 has not started.
