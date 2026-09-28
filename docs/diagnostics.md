# Executable Phase 1 diagnostic contract

Phase 2's separate `ACP-IR-*` codes and CLI behavior are documented in the [canonical contract](canonical-ir.md#reproduction-and-diagnostics). The Phase 1 catalogue below is unchanged.

Applies to historical kernel 0.1 and current authoring model 0.2.0. This catalogue contains only emitted codes; future compiler/target diagnostics require their own implementation and fixtures.

## Authoring-model envelope and ordering

[validate.py](../tooling/validate.py) emits `code`, `severity`, `stage`, `subject`, `path`, `message` and `remediation`. Severity is ERROR. Subject is the semantic ID when available, otherwise the empty string. Path is an escaped JSON pointer into the submitted snapshot. Remediation gives a repair direction, not an automatic edit or approval.

ACP-INPUT has stage `input`; ACP-SHAPE has stage `shape`; all other model codes below have stage `semantic`, even when the internal module checks UI, privacy or execution. Preserve these stable codes/stages. Diagnostics sort by `(subject, path, code, message)` using codepoint order, independently of object key order. Node-array reordering may change pointers; semantic comparisons use subject/code. Third-party schema-validator wording is not a stable contract.

Input/shape failures stop dependent passes. Unresolved or wrong-kind references prevent graph-dependent checks; independent semantic errors may accumulate. Shape messages identify schema keywords/locations without echoing input values. Messages and remediation must not embed secret values, credentials or entire input records. Tests exercise non-secret CLI output. Passing draft checks does not permit compilation or release.

| Code | Meaning | Remediation |
| --- | --- | --- |
| ACP-INPUT | Unreadable/invalid/oversized JSON, duplicate keys, nonfinite/floating numbers or excessive nesting | Supply strict UTF-8 JSON within the byte/depth limits |
| ACP-SHAPE | Unsupported version/kind/property, missing field or invalid record shape | Follow the declared authoring-model version; propose unsupported concepts explicitly |
| ACP-ID | Duplicate semantic ID | Give every durable concept a unique ID |
| ACP-REF | Missing or stale exact reference | Include the exact referenced ID and revision |
| ACP-KIND | Wrong referenced kind | Reference the required semantic kind |
| ACP-BASIS | Missing, self-referential or cyclic justification | Supply noncircular Requirement/Decision basis |
| ACP-APPROVAL | Missing current attestation | Supply an exact-revision attestation; authenticity remains a separate authority obligation |
| ACP-LIFECYCLE | Ineligible compile state or invalid supersession | Use explicit lifecycle changes and isolate candidates |
| ACP-ISSUE | Open blocking issue or invalid resolution | Resolve with an approved Decision |
| ACP-OWNER | Field/resource/actor/machine binding mismatch | Align structural owners and expression bindings |
| ACP-TYPE | Invalid literal/declaration/operator/presence handling or predicate type | Use compatible bounded types and explicit presence/null handling |
| ACP-SECRET | Secret classification/type mismatch | Use a symbolic SecretReference with SECRET classification |
| ACP-WORKFLOW | Invalid topology, ambiguous trigger or unreachable state | Correct explicit states, ownership and triggers |
| ACP-ACCEPTANCE | Requirement/criterion links disagree | Make references reciprocal |
| ACP-DOMAIN | Empty or cyclic value-object definition | Provide a nonempty acyclic bounded field definition |
| ACP-CARDINALITY | Inconsistent endpoint bounds or detach behavior | Align min/max and deletion semantics |
| ACP-AGGREGATE | Invalid root/member/invariant ownership or cross-aggregate composition | Keep members and composition inside one declared consistency boundary |
| ACP-OWNERSHIP | Cyclic composition or invalid ownership/deletion declaration | Remove ownership cycles and reference-delete contradictions |
| ACP-SECURITY | Inconsistent authentication, role, permission, policy, session or rate contract | Align actor/resource/action links, complete PolicySets and bounded policies |
| ACP-TENANT | Invalid tenancy declaration or scope | Preserve exact actor/resource tenant fields and shared tenant identity type |
| ACP-PRIVACY | Inconsistent classification/export/lifecycle/anonymization/hold obligations | Satisfy classification and align resource, retention and legal-hold contracts |
| ACP-EXECUTION | Inconsistent service, query, step, command, failure, compensation or transaction contract | Declare compatible operation ownership and execution boundaries |
| ACP-RETRY | Invalid retry failures or retry/idempotency horizon | Retry declared transient failures within all required windows |
| ACP-DELIVERY | Inconsistent event/delivery/deduplication contract | Align reciprocal references, resource scope and retention windows |
| ACP-SCHEDULE | Invalid local schedule, timezone or database version | Use a supported explicit schedule with pinned timezone/DST policy |
| ACP-UI | Invalid task UI ownership/binding/permissions/states | Bind controls to task inputs and views to projections with complete boundaries/states |
| ACP-ACCESSIBILITY | Screen not covered by its selected accessibility requirement | Include the screen in the requirement's subjects |
| ACP-QUALITY | Invalid metric threshold/comparison/version or incomplete evidence subject/method coverage | Align typed obligations, units, versions and verification methods |
| ACP-RECOVERY | Backup interval/retention or recovery RPO/freshness inconsistency | Align backup spacing and restore evidence age with recovery obligations |
| ACP-APPLICABILITY | Applicability is not a closed Boolean expression | Supply a typed Boolean condition with Decision basis |

## Design-binding diagnostics

[validate_bindings](../tooling/design_bindings.py) currently returns a **sorted unique list of code strings**, not the authoring-model envelope. Its logical stage is sidecar validation, but it emits no stage/subject/path/severity fields. The caller retains the submitted sidecar/model context. No source-location adapter or full diagnostic envelope is claimed.

| Code | Executable condition | Remediation |
| --- | --- | --- |
| ACP-DESIGN-SHAPE | Sidecar fails its closed schema | Use the versioned design-binding shape without extra properties |
| ACP-DESIGN-SNAPSHOT | Application or snapshot differs from model | Bind the exact application and snapshot |
| ACP-DESIGN-REF | Missing subject or stale revision | Reference a current semantic revision |
| ACP-DESIGN-KIND | Subject is not a supported bindable UI kind | Bind Screen/Form/control/action/wizard/table/search/filter/view-state intent |
| ACP-DESIGN-DUPLICATE | Subject ID appears in multiple bindings | Keep one binding per subject in a sidecar |

Shape and snapshot failures return immediately. Other design codes accumulate in codepoint order. Codes do not echo catalogue/component values or secret data.

## Evidence diagnostics

[evaluate_evidence](../tooling/evidence_semantics.py) returns `{status, diagnostics}`, where status is PASS/BLOCKED/NOT_APPLICABLE and diagnostics is a **sorted unique list of code strings**. It does not emit stage/subject/path/severity/remediation fields. The caller supplies the obligation ID, model, records, context, evaluation instant and applicability approval input; those are the evaluation's subject/context. Repair guidance below documents this current API without inventing an emitted envelope.

| Code | Executable condition | Remediation |
| --- | --- | --- |
| ACP-EVIDENCE-APPLICABILITY | Invalid closed condition/evaluation instant, or false condition without caller approval | Provide explicit Boolean applicability, UTC evaluation time and reviewed authority input |
| ACP-EVIDENCE-BINDING | Context absent/wrong or observation references/subjects/digests/profile do not match | Bind exact obligation, evidence requirement, subjects and supplied current context |
| ACP-EVIDENCE-SHAPE | Observation fails closed schema | Supply a conforming versioned observation record |
| ACP-EVIDENCE-FRESHNESS | Invalid/non-UTC observation time, future observation or age exceeds maximum | Supply a valid observation within the explicit evaluation window |
| ACP-EVIDENCE-RESULT | Observation result is not PASS | Obtain passing evidence; NOT_RUN and FAIL cannot pass |
| ACP-EVIDENCE-MEASUREMENT | Missing/duplicate/invalid metric or threshold/workload/sample/window failure | Supply finite measurements satisfying the typed obligation |
| ACP-EVIDENCE-METHOD | Not every required method has qualifying evidence | Supply fresh passing evidence for each required method |

Applicability/context failures may return immediately. Invalid records contribute stable codes and cannot qualify a method; missing-method errors can accompany other failures. Input record ordering cannot change the sorted code set. No observation values are included in diagnostics. The applicability approval Boolean and digest strings do not prove authenticated authority.

## Compatibility and limits

There are 30 model codes, five design codes and seven evidence codes. Historical cases compare exact model code/subject multiplicity; current portable negatives require specified code/subject pairs and allow independent extra errors. Focused sidecar tests compare code strings. [Coverage](coverage.md) records representative test limits.

Later adapters may add exact revisions, source URI/spans, related locations and provenance only through a separate tested contract. Capability, lowering, migration, trust and production verification error families are not executable here and are intentionally absent from this catalogue. A raised development-helper exception (for example explicit rounding rejection) is not another ACP diagnostic family.
