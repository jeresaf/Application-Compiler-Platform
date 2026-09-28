# ADR-0005: Open architecture proposals

Status: PROPOSED investigation register; no option below is approved by implication. Date: 2026-09-15; updated 2026-09-16. Each proposal must become its own accepted/superseded ADR before dependent production implementation. Recommendations guide experiments only.

## Meta-model extensions

Resolution note, 2026-09-20: the P-01 through P-05 investigation rows below are preserved as history. Their bounded semantic questions are superseded by accepted [ADR-0006](0006-domain-semantics.md), [ADR-0007](0007-security-privacy.md), [ADR-0008](0008-execution-semantics.md), [ADR-0009](0009-task-interfaces.md) and [ADR-0010](0010-quality-operations.md), respectively (all dated 2026-09-16). Their explicit exclusions are safe deferrals, not unresolved foundational Phase 1 semantics. P-06 through P-13 remain PROPOSED. This note does not accept any production technology or rewrite the original investigations.

| ID / question | Options and recommendation | Consequences / evidence / blocked work |
| --- | --- | --- |
| P-01 How complete is the domain/type/rule algebra? | Flat records vs explicit value objects/relations/aggregates/refinements. Recommend typed bounded records and pure expressions; explicitly define nullable, collection, numeric, temporal and identity behavior | Needs money rounding, cascade, cyclic containment, aggregate consistency, relation/cardinality, precision and type-registry vectors. Blocks full domain IR and database lowering |
| P-02 How compose security and privacy? | Role-only rules vs resource/actor/tenant predicates plus classification/lifecycle rules. Recommend explicit scoped predicates with deny precedence and mandatory tenant boundaries; design authentication/session/permission/retention/hold separately | Needs formal policy composition, incomplete-context denial, role assignment, conflict detection, audit/encryption/export and delete/retain cases. Blocks security-capable target generation; kernel typing is insufficient |
| P-03 How model execution and delivery? | Implicit services vs explicit commands/queries/events/transactions/jobs and effects. Recommend explicit failure, idempotency, consistency and delivery semantics; architecture chooses direct/outbox/broker | Needs concurrent commands, failure/compensation, retry/deduplication, schedule/timezone and event evolution fixtures. Blocks behavioral orchestration and integration lowering |
| P-04 How separate task UI from design? | Schema-derived UI vs task/interaction semantics plus independent Design IR. Recommend typed task views with accessibility and policy obligations, then design bindings | Needs wizard/error/focus/responsive cases and two design bindings with unchanged behavior. Blocks UI/API realization and Design IR schema |
| P-05 How represent measurable quality/operations? | Text requirements only vs typed subject/method/threshold/environment obligations. Recommend explicit performance/accessibility/reliability/compatibility/observability/recovery records and trusted evidence | Needs exact evidence inputs, applicability, freshness, health/redaction/restore and workload examples. Blocks complete verification/operations schemas |

## Infrastructure and evolution decisions

Phase 3 resolution note, 2026-09-28: [ADR-0012](0012-change-history.md) implements bounded P-06 and the requirement/decision/concept/change/snapshot history portion of P-09. Final executable acceptance is recorded in its report. Production storage/identity and generated-source ownership/regeneration remain unselected. Older status notes below describe their original phases and do not reopen already resolved bounded questions.

Resolution note, 2026-09-28: [ADR-0011](0011-canonical-interchange.md) resolves P-07 for bounded Canonical Application 0.1.0 interchange, normalization, bytes/digests and authoring 0.2.0 candidate import. The historical row below remains the original investigation. Production authority/signatures, persistence, future-version transformations and plugin wire ABI are not implemented by this resolution. P-06 and P-08 through P-13 remain open.

| ID / question | Options and recommendation | Consequences / evidence / blocked work |
| --- | --- | --- |
| P-06 Durable state and concurrent proposals | Mutable document store, full event sourcing, or immutable snapshots with semantic journal. Recommend evaluate snapshots plus atomic append-only change journal behind a repository port; not a commitment to event sourcing | Crash/retry/branch/read-set conflict experiments; compare storage cost and operational recovery. Blocks storage engine, merge algorithm, trusted atomic apply |
| P-07 Interchange, canonical bytes and migration | JSON, schema-driven binary encoding, or typed native-only serialization. Recommend evaluate versioned JSON interchange plus separate canonical hash profile; fixtures do not settle it | Unicode, number, set/order, round-trip, unknown-field and cross-runtime hash vectors; immutable schema migration/reapproval tests. Blocks persistent digests/signatures, stable interchange and wire ABI |
| P-08 Plugin API/ABI and capability negotiation | In-process library ABI vs versioned worker protocol. Recommend pure lowering/planning contracts and versioned capability manifests; evaluate worker isolation | Define capability versions, constraints, enforcement/evidence outputs, cancellation and resource budgets; reject partial capability. Blocks target SDK/runtime protocol and first target |
| P-09 Ownership and provenance mapping | Embedded source markers, sidecars, AST-aware regions, target extension interfaces. Recommend digest-bound sidecars plus target-native extension seams; avoid arbitrary round-trip promises | Rename/reformat/manual drift cases, stale-map rejection, nonoverlap/path/symlink tests. Blocks regeneration and source patching; origin locations alone are insufficient |
| P-10 Source semantics and context bundles | Syntax-only extraction vs native semantic analyzers plus syntax fallback. Recommend explicit analyzer capabilities/completeness with dependency-closed context queries | Compare cross-file overload/inheritance/refactor cases; ensure budgeted contexts retain security/locked decisions and label omissions. Blocks trustworthy source impact/drift and AI context completeness |
| P-11 Build sandbox, secrets and environment binding | Host process, container worker, VM/microVM worker. Recommend isolated ephemeral workers selected by threat model; never unrestricted generated-code execution | Escape/network/resource/secret-boundary tests across supported OSs; separate production credentials; model environment schema and opaque handles. Blocks execution worker/deployment adapter |
| P-12 Minimum production profile and evidence authority | Ad hoc target checks vs global baseline plus additive profiles. Recommend instantiate every baseline gate for one serious target with applicability proofs and authenticated evidence | Define trust/freshness, manual evidence, criticality, restore/security/performance budgets; repeated-release reference exercise. Blocks production-ready claim and target selection acceptance |
| P-13 AI output validation and cache | Freeform generation vs bounded candidate artifacts. Recommend input/policy/model provenance, deterministic validation, review, and digest-bound reuse | Changed-input/policy/model/stale approval/cache poisoning tests; sampling never claims determinism. Blocks AI implementation adapter and candidate acceptance service |

## Charter §43 question index

| Charter questions | Decision / investigation |
| --- | --- |
| 1 canonical boundaries | ADR-0001, meta-model, P-01–P-05 |
| 2 journal/snapshots; 17 concurrent edits | P-06 and change-model contract |
| 3 serialization; 4 version migration | ADR-0003 (fixtures only), P-07 |
| 5 implementation language; 6 language tooling runtime | ADR-0004 |
| 7 plugin ABI; 16 capabilities | P-08 and IR contracts |
| 8 deterministic guarantees | IR determinism contract, P-07, ADR-0004 experiments |
| 9 source ownership; 14 provenance embedding | P-09 |
| 10 deep source semantics; 20 context bundles | P-10 and ADR-0004 |
| 11 sandbox; 13 secrets/environment | P-11, threat model, P-02 |
| 12 minimum production profile | P-12 and production gates |
| 15 database vs application enforcement | P-01/P-02/P-08; negotiate enforcement per invariant; unsupported enforcement fails |
| 18 understandable errors | Diagnostic contract and portable negative corpus; frontend source spans pending |
| 19 AI validation/cache | P-13 |

No unresolved proposal is permission for a target to approximate missing semantics. The explicit capability error path is part of the accepted boundary contract.
