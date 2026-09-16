# Diagnostic contract

Status: executable kernel codes below; full compiler envelope is normative for future adapters.

Every diagnostic has a stable `code`, `severity`, `stage`, `subject` semantic ID when available, `path` JSON pointer (kernel), `message`, and `remediation`. The full compiler adds exact subject revisions, primary source URI/span or structured locator, related locations/references, and provenance trail. User-facing explanations state what conflicts and what change could resolve it; compiler jargon is optional detail. Messages never embed secret values or entire input objects.

Kernel diagnostics sort by `(subject, path, code, message)` using codepoint order, independent of input object key order. Node-array reordering changes JSON pointers; semantic meaning of diagnostics remains keyed by subject/code. Tests compare codes/subjects/paths, not third-party validator wording. Severity ERROR blocks the attempted validation profile. Draft success does not permit compilation or release.

| Code | Meaning | Repair direction |
| --- | --- | --- |
| ACP-INPUT | Invalid/unreadable/oversized JSON, duplicate keys, nonfinite numbers, excessive nesting | Supply bounded strict UTF-8 JSON |
| ACP-SHAPE | Unsupported version/kind/property, missing field, invalid shape | Use the declared kernel schema; propose extensions explicitly |
| ACP-ID | Duplicate semantic ID | Preserve unique immutable identity |
| ACP-REF | Missing or stale reference | Include the exact referenced revision |
| ACP-KIND | Reference points to wrong semantic kind | Reference the required kind |
| ACP-BASIS | Missing or cyclic justification | Link to a requirement or decision without circular support |
| ACP-APPROVAL | Missing current approval attestation | Provide authority-backed evidence for exact revision |
| ACP-LIFECYCLE | Ineligible compile state or invalid supersession | Keep candidates isolated; use explicit lifecycle workflow |
| ACP-ISSUE | Open blocking issue or invalid resolution | Resolve through an approved Decision |
| ACP-OWNER | Field/resource/actor/machine ownership mismatch | Align bindings and semantic owners |
| ACP-TYPE | Invalid literal, operator, optional read, or predicate type | Use compatible semantic types and explicit presence rules |
| ACP-SECRET | Secret classification/type misuse | Model symbolic secret references and classification |
| ACP-WORKFLOW | Illegal/ambiguous transition or unreachable state | Correct topology/trigger without inventing business behavior |
| ACP-ACCEPTANCE | Requirement/criterion linkage mismatch | Make acceptance references reciprocal |

Input and shape failures stop dependent passes. Reference failures stop graph-dependent passes to avoid cascading type errors. Workflow errors may accumulate with independent approval/type errors. Generic shape messages identify the location and violated schema keyword without echoing values. Suggestions are proposed edits, not automatic changes. Later capability, migration, ownership, trust, and verification diagnostics need their own code families and fixtures before their stages execute.
