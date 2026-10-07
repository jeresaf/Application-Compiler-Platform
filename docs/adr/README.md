# Architecture decisions

ACCEPTED records an engineering choice within its stated scope. PROPOSED records investigation, not authorization. Supersession preserves history and links the replacement; no unperformed experiment is evidence for technology selection.

| ID | Status | Date | Decision / question |
| --- | --- | --- | --- |
| [0001](0001-semantic-boundaries.md) | ACCEPTED | 2026-09-15 | Typed semantic boundaries and minimal repository |
| [0002](0002-identity-lifecycle.md) | ACCEPTED | 2026-09-15 | Stable identity, exact references, independent lifecycle/evidence |
| [0003](0003-contract-harness.md) | ACCEPTED, tooling only | 2026-09-15 | JSON Schema and replaceable Python contract harness |
| [0004](0004-technology-evaluation.md) | **PROPOSED** | 2026-09-15 | Production language/frontend experiments and selection protocol; no selection |
| [0005](0005-open-architecture.md) | PROPOSED register with bounded resolution notes | 2026-09-15; updated 2026-09-28 | P-01 through P-07 and semantic-history P-09 have scoped successor ADRs; P-08, remaining P-09 and P-10 through P-13 remain open |
| [0006](0006-domain-semantics.md) | ACCEPTED | 2026-09-16 | P-01 bounded domain/type/rule semantics; model 0.2.0 |
| [0007](0007-security-privacy.md) | ACCEPTED | 2026-09-16 | P-02 explicit security/privacy and mandatory tenant obligations |
| [0008](0008-execution-semantics.md) | ACCEPTED | 2026-09-16 | P-03 bounded execution, failures, consistency and delivery |
| [0009](0009-task-interfaces.md) | ACCEPTED | 2026-09-16 | P-04 task interfaces and independent design bindings |
| [0010](0010-quality-operations.md) | ACCEPTED | 2026-09-16 | P-05 measurable quality/operations and evidence contracts |
| [0011](0011-canonical-interchange.md) | ACCEPTED, bounded Phase 2 | 2026-09-28 | P-07 canonical interchange, normalization, digests, compatibility and candidate migration |
| [0012](0012-change-history.md) | ACCEPTED, bounded Phase 3 | 2026-09-28 | P-06 immutable snapshots and atomic semantic journal; semantic-history portion of P-09 |

| [0013](0013-compiler-core.md) | ACCEPTED, bounded Phase 4 | 2026-10-07 | Immutable compiler execution, ports, provenance/obligations, incremental cache and synthetic artifact planning |

## Resolution without rewriting history

ADR-0005's P-01/P-02/P-03/P-04/P-05 rows describe the investigations as recorded. Their accepted replacements are ADR-0006/0007/0008/0009/0010 respectively, including explicit bounded exclusions. They are no longer open foundational Phase 1 questions. The remaining register stays PROPOSED.

The [current meta-model](../metamodel.md) and [coverage](../coverage.md) define executable 0.2 scope; [kernel 0.1](../kernel-0.1.md) preserves the original contract. [Completion report](../phase1-completion-report.md) records closure evidence.

P-07's bounded interchange/normalization questions are resolved by ADR-0011; see the [Phase 2 report](../phase2-completion-report.md). Production authority/signatures, persistence and plugin wire ABI remain later work.

ADR-0012 now implements bounded P-06 and semantic-history P-09. The remainder of P-09 concerns generated-source ownership, maps and regeneration and remains open. Its final acceptance evidence is recorded in the [Phase 3 report](../phase3-completion-report.md).

**No production language, runtime or parser has been selected.** Python, JSON, SQLite, HMAC, the independent Node.js byte checker and CI action runtimes are reference/development choices only. ADR-0004 remains PROPOSED because the executable Phase 5 experiments leave hard-gate evidence unresolved; see the [evaluation report](../phase5-completion-report.md). Phase 4 reference compiler-core work is recorded in ADR-0013. Phase 5 is EXPLICITLY BLOCKED ON EVIDENCE; Phase 6 is NOT STARTED.
