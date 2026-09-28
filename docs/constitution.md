# Constitution

Status: normative Phase 1 elaboration of charter v0.2, sections 1–6, 27, 31, 41–48. If this document conflicts with the charter, fix this document through an ADR.

## Authority

1. The charter governs ACP architecture. Accepted ACP ADRs refine it without silently weakening it.
2. An application's approved specification and accepted decisions govern intended behavior. Constraints are mandatory; goals optimize within them. Preferences require a recorded justification when overridden. Facts and assumptions retain their evidence and uncertainty.
3. Proposals, conversations, imported observations, and AI suggestions are candidates, never implicit approvals.
4. Source/infrastructure observations describe what exists; deployment/runtime observations describe what runs. Neither rewrites intended behavior. Differences produce drift records and proposed change sets.

MUST, MUST NOT, SHOULD, and MAY express contract strength. `Normative` means a requirement for implementation, not a claim that it is already executable. [Coverage](coverage.md) makes that distinction explicit. `PROPOSED` ADRs have no decision authority. Accepted engineering ADRs in this repository record decisions within the user's authorized development phase; they do not approve fixture business rules or grant production privileges.

## Invariants

- Durable concepts have immutable, application-scoped semantic identity. Names and file positions are labels/locators.
- Every transformation preserves semantic provenance and enumerates new enforcement and verification obligations.
- Canonical semantics exclude parser objects, framework annotations, database column types, deployment vendor settings, and target source fragments.
- Deterministic stages use declared versioned inputs. AI outputs are isolated candidates with explicit provenance and review requirements.
- Unresolved conflicts and blocking ambiguities prevent affected production compilation/release. Unknown capabilities or missing evidence never mean success.
- Security, privacy, accessibility, reliability, evolution, and observability are semantic requirements before target generation.
- Human-owned source is protected. Ownership does not grant authority to change approved intent.
- Semantic changes are atomic, revision-checked transactions with impact, compatibility, approval, migration, and evidence requirements.
- Production readiness requires all baseline gates and stronger profile gates for the exact artifact and environment. A successful build alone is insufficient.

## AI operation classes

| Class | Allowed outcome |
| --- | --- |
| DETERMINISTIC | Reproducible artifact under a declared stage contract |
| AI_ASSISTED | Candidate with model/tool/input provenance; validation remains mandatory |
| AI_REQUIRES_APPROVAL | Candidate held outside approved state until authorized review |
| FORBIDDEN_AUTOMATIC | No automatic execution; explicit operator-controlled workflow |

Security reductions, locked decision changes, destructive migrations, and irreversible infrastructure operations require explicit impact and approval handling. No model output may supply its own approval authority. Builds execute under scoped worker permissions, without unrestricted host access or production credentials.
