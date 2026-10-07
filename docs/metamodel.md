# ACP Phase 1 meta-model 0.2

Status: normative bounded semantic specification. Exact authoring model version: **`0.2.0`**. This document incorporates [ADR-0006](adr/0006-domain-semantics.md) through [ADR-0010](adr/0010-quality-operations.md), with the shared boundaries and identity contracts of ADR-0001 and ADR-0002. The [historical kernel 0.1](kernel-0.1.md) remains the specification of `0.1.0` only.

The [Phase 1 schema](../contracts/phase1.schema.json) defines exact record properties, requiredness, enumerations and bounds. This specification defines their cross-record meaning. The [validator](../tooling/validate.py) and its semantic modules make the bounded checks executable. Both shape and semantic validation are required. [Coverage](coverage.md) separates those checks from runtime obligations. No unspecified property, unknown kind, generic extension bag or implicit conversion is accepted.

This is an **authoring model, not Canonical IR**: it includes candidates, issues and fixture attestations. JSON and Python are replaceable contract tooling under ADR-0003. Phase 2's separate [canonical contract](canonical-ir.md) now defines normalization and serialization over these semantics. Production language, parser, database, target, deployment platform and runtime remain unselected. [IR boundaries](ir-design.md) constrain the future production pipeline.

## 1. Snapshot, identity, lifecycle and basis

The closed snapshot record contains `modelVersion`, `applicationId`, `snapshotId`, `nodes`, `approvals` and `issues`. It describes one application snapshot, not a persistence transaction or canonical byte encoding. `Ref<T>` below means an exact `{id, revision}` reference to a node of kind T in this snapshot. References are never resolved by display name or by fetching an external location.

Every one of the 69 kinds has the same durable envelope:

| Property | Contract |
| --- | --- |
| `id` | Unique within the snapshot; ASCII letter followed by letters, digits or `._:-`, at most 128 characters. Stable semantic identity, independent of name or source position. |
| `revision` | Positive integer, at most 2^53-1. Exact references include this revision. |
| `kind` | Closed discriminator selecting the kind's `data` record. |
| `name` | Nonblank display text; never a lookup key. |
| `lifecycle` | CAPTURED, REFINING, PROPOSED, REVIEW_REQUIRED, APPROVED, REJECTED, DEPRECATED or SUPERSEDED. |
| `steward` | Nonblank responsible principal/team handle; no authority is inferred from the string. |
| `origins` | Nonempty records of `source`, `locator`, `actor`, `actorType` (HUMAN, AI or IMPORT). Locators are evidence handles, never fetched. |
| `basis` | Unique exact Requirement/Decision references. Required nonempty for every non-intent kind; no self-justification or cycles. |
| `supersededBy` | Optional only as allowed by lifecycle: SUPERSEDED requires a different, active, same-kind replacement. |
| `data` | Closed, kind-specific record. Literal ValueObject payloads are the sole field-ID keyed value records; they are checked against declared fields, not treated as metadata/extensions. |

All promoted kinds inherit this identity, lifecycle, stewardship, origin and basis behavior. Structural owners are explicit references, not stewards: Field belongs to Entity/ValueObject; State to StateMachine; ExecutionStep to UseCase; InputControl to Form; WizardStep to Wizard; ViewState and ResponsivePolicy to Screen. Other records link their typed subjects/resources rather than acquiring implicit containment ownership. Aggregate consistency ownership and Service operation ownership have additional constraints below.

Reference arrays are unique. Their meaning is set-like except `UseCase.steps` and `Wizard.steps`, whose order is semantic. Expression operand order and List value order are also semantic. Node, approval and object-property order have no semantic meaning. Set values compare independently of order. None of these rules selects canonical bytes.

The lifecycle transition contract remains CAPTURED -> REFINING -> PROPOSED -> REVIEW_REQUIRED -> APPROVED; review may return to REFINING, proposals/reviews may be REJECTED, approved nodes may become DEPRECATED or SUPERSEDED, and deprecated nodes may become SUPERSEDED. The harness checks snapshot eligibility and attestations, not a transition engine or immutable history. Renaming preserves ID/kind and creates a revision with updated exact references; historical allocation/non-reuse and concurrency enforcement are later change-engine obligations.

APPROVED/DEPRECATED nodes require matching exact-revision attestations. A `compile` validation profile requires all selected nodes to be active and forbids open blocking issues. It does not compile anything or authenticate reviewers. Issue resolution must reference an approved Decision. Real authority verification, revocation and content-digest binding remain later work. IMPLEMENTED, VERIFIED and RELEASED are evidence-derived states, not accepted lifecycle values; evidence never silently approves a node.

## 2. Retained intent, domain and workflow kinds

The seven intent kinds permit empty basis. Each has a nonblank `statement`:

| Kind | Other required data and meaning |
| --- | --- |
| Fact | `evidence`: observed assertion, not an executable constraint. |
| Constraint | Nonempty `subjects`: mandatory restriction, with prose preserved rather than interpreted. |
| Requirement | `priority` MUST/SHOULD/COULD and nonempty `acceptance` references, reciprocal with AcceptanceCriterion. |
| Preference | `rationale`: soft preference. |
| Goal | `measure`: stated optimization objective. |
| Assumption | `reviewTrigger`: explicit uncertainty. |
| Decision | `strength` PREFERRED/REQUIRED/LOCKED, `rationale`, nonempty `alternatives`; chosen direction with provenance. |

The remaining retained kinds have these **current 0.2** contracts. Required fields are listed; `?` denotes optional data properties.

| Kind | Data and cross-record meaning |
| --- | --- |
| Entity | Nonempty `identity` Field refs; `tenancy`; `tenantField?`. Identity fields belong to this entity, are required and use Identifier<this entity>. Tenancy rules are in section 4. |
| Field | `owner` Entity/ValueObject, `type`, `optional`, `classification`, `classificationRef`, `exportPermission?`. One structural owner; optional means absence, not null. Classification behavior is in section 4. |
| Parameter | `type`, `value`: declared type and conforming literal. A changed parameter is a semantic revision. |
| Invariant | `resource` Entity, Boolean `predicate`, nonempty `enforcement` set WRITE/TRANSITION/READ/EXPORT. Declares required checkpoints, not a storage mechanism. |
| Command | `resource`, `invariants`, `emits`, `aggregate`, nonempty `writes`, `failures`, `idempotency`. Resource must be aggregate root; writes remain members. Invariants and emitted events share resource. |
| Event | `resource`, `payload` Field refs, `delivery`. Payload fields belong to resource; delivery linkage is reciprocal. |
| Actor | `subject` Entity, `authentication` AuthenticationModel. Actor/model linkage is reciprocal. |
| Role | `actor`, nonempty `permissions`; permission actors agree. |
| Policy | `actor`, nonempty `roles`, `resource`, `action` Command/Query, `effect` ALLOW/DENY, Boolean `predicate`, `permission`, `scope`. Roles, permission and scope must agree with actor/action/resource. |
| StateMachine | `resource`, `initial` State; owns at least one state through inverse references. |
| State | `machine`, `terminal`; belongs to exactly one machine. |
| Transition | `machine`, `from`, `to`, `command`, `actor`, Boolean `guard`, `effects` Event refs; endpoints belong to machine, command/effects share machine resource. |
| AcceptanceCriterion | `requirement`, `scenario`; reciprocal requirement acceptance link. A scenario is an obligation, not passing evidence. |

Terminal states have no outgoing transitions. Duplicate `(machine, from, command)` triggers are rejected even when guards differ. Every state must be graph-reachable from the initial state, ignoring guards. Guard satisfiability, overlap reasoning and actual state execution are not implemented. Prose contradictions are represented as explicit issues; absence of issues is not a proof of consistency.

## 3. P-01: domain, types and rules

[ADR-0006](adr/0006-domain-semantics.md), [type semantics](../tooling/type_semantics.py), [domain validator](../tooling/phase1_semantics.py).

| Kind | Required data and meaning |
| --- | --- |
| ValueObject | `equality: STRUCTURAL`; owns a nonempty, acyclic field definition through Field.owner. No entity identity; instances compare by typed field values. |
| TypeDefinition | `base`, `semantics` NOMINAL/REFINED, `refinement` NONE/RANGE/LENGTH. Named references retain this definition's exact identity; REFINED cannot use NONE. |
| Relation | `source`, `target` Entity refs; `sourceCardinality`, `targetCardinality`; `ownership` REFERENCE/COMPOSITION; `onDelete` RESTRICT/DETACH/DELETE_OWNED. |
| Aggregate | `root`, nonempty `members`, `invariants`, `consistency: ATOMIC`. Root is a member, invariants target members, an entity cannot belong to two aggregates. |

Cardinalities contain nonnegative `min` and `max` (integer or UNBOUNDED), with min <= finite max. Source cardinality counts source instances per target; target cardinality counts targets per source. Composition requires source cardinality exactly 1..1, an acyclic source-to-target graph and both endpoints in the same aggregate. Reference relations cannot DELETE_OWNED. DETACH requires source minimum zero so a surviving target can lose its source. These are declaration checks; no data instances are counted or deleted. Aggregate membership is not mandatory for every entity, but commands and composition require their declared aggregate boundaries.

### Type algebra

| Type | Accepted meaning and bounds |
| --- | --- |
| Boolean, String | Native Boolean and textual values. No truthy/string coercion. |
| Integer | Integer value encoded as a canonical decimal string, not a JSON floating-point number. |
| Decimal | `precision` 1..38, `scale` 0..18 and <= precision, `rounding` REJECT/HALF_EVEN/HALF_UP/DOWN. Value is a decimal string. |
| Money | Decimal policy plus uppercase three-letter `currency`. Same currency and numeric policy required for compatible operations; registry membership/conversion not inferred. |
| Email | Distinct textual type; bounded lexical check for one @, no whitespace and a dotted domain, not mailbox verification. |
| SecretReference | Symbolic `secret:` handle with the schema/harness's bounded character vocabulary, never an inline credential. |
| Date | Real calendar date YYYY-MM-DD. |
| Instant | Valid UTC timestamp ending Z, at most six fractional second digits. |
| LocalDateTime | Valid local date/time with no offset; no implicit conversion to Instant. |
| Duration | Nonnegative fixed elapsed seconds encoded as an integer string; no calendar months/years. |
| Identifier | `entity: Ref<Entity>`; typed entity identity, not structural equality. |
| Named | `definition: Ref<TypeDefinition>`; definition identity retained, with underlying literal/refinement validation. |
| Value | `definition: Ref<ValueObject>`; record keyed by owned Field IDs, required fields present, unknown fields rejected. |
| Nullable | `item: Type`; explicit null or item value. Nested Nullable is rejected. |
| List, Set | `element: Type`, `minItems`, `maxItems` in 0..10000, min <= max. List is ordered; Set rejects duplicates by typed value equality. |

TypeDefinition bases are restricted to String, Integer, Decimal, Money, Date, Instant or Duration. RANGE uses conforming min/max literals on Integer/Decimal/Money/Duration only. LENGTH uses nonnegative min/max on String only. Recursive Value/Named declarations and unsupported refinements are rejected.

`Field.optional` controls absence. `Nullable` controls explicit null. An absent value is never silently null, zero or false. Decimal/Money stored literals must already fit precision and scale: ingestion never rounds. The tested `quantize` helper applies an explicitly requested rounding policy, rejecting overflow; it is not a generated arithmetic runtime. Addition preserves type/policy and cannot convert currency or erase nominal identity.

Typed value equality compares Decimal/Money numeric values, Value fields structurally, Lists in order and Sets independent of order, while retaining Named identity. Entity identities require `identityEq`; `eq` cannot compare Identifier, SecretReference, optional or nullable values directly. General ordering/quantification/conversion is absent.

### Pure expressions

| Tag | Inputs / typing rule |
| --- | --- |
| literal | `type`, `value`; validate declared type and literal. |
| parameter | Exact Parameter `ref`; result is its type. |
| field | `binding` resource/actor and Field `ref`; field owner must match that context. Optional access retains presence information. |
| present | Same binding/ref as field; explicit Boolean presence test. |
| coalesce | `value`, `fallback`; resolve optional/nullable access with a compatible fallback. |
| size | Collection `value`; Integer result. |
| contains | `collection`, compatible `value`; Boolean result. |
| binary | `op`, `left`, `right`: eq for same comparable value type; identityEq for same Identifier type; gt for compatible numeric/temporal types; add for same numeric type; and for Booleans. |

Predicates and guards must type as Boolean. Expressions cannot invoke services, host code, clocks, random values, network, filesystem or secret resolution. The model validator checks typing; it does not execute general application rules. The evidence evaluator executes only closed applicability expressions supplied with explicit parameter values from the model.

## 4. P-02: security and privacy

[ADR-0007](adr/0007-security-privacy.md), [security validator and bounded decision helpers](../tooling/security_semantics.py).

| Kind | Required data and additional constraints |
| --- | --- |
| AuthenticationModel | `actor`, `assurance` SINGLE_FACTOR/MULTI_FACTOR, distinct `mechanisms` KNOWLEDGE/POSSESSION/EXTERNAL_ASSERTION. MULTI_FACTOR requires at least two mechanisms. |
| Permission | `actor`, `resource`, `action` Command/Query; action resource agrees. |
| Scope | `actor`, `resource`, `mode` GLOBAL/SAME_TENANT; `actorTenant?`, `resourceTenant?` governed by tenancy below. |
| RoleAssignment | `role`, `actor`, `scope`, opaque `principal`; actor agrees with role/scope. This is a modeled grant, not authenticated principal resolution. |
| PolicySet | `resource`, `action`, nonempty `policies`, `combining: DENY_OVERRIDES`, `default: DENY`. Exactly one set per operation, covering all its policies. |
| DataClassification | `level` PUBLIC/INTERNAL/SENSITIVE/SECRET, `audit` NONE/WRITE/READ_WRITE, Boolean `encryptAtRest`/`encryptInTransit`, `export` DENY/PERMISSION_REQUIRED, `redaction` NONE/MASK/OMIT. |
| SessionPolicy | `authentication`, positive `idleSeconds`, `absoluteSeconds`, `reauthSeconds`; idle and reauthentication cannot exceed absolute lifetime. |
| RatePolicy | `permission`, positive `requests`, `windowSeconds`, `burst`, `partition` ACTOR/TENANT; burst <= requests. |
| Retention | `resource`, `trigger` CREATED/CLOSED, nonnegative `minimumSeconds`. |
| DeletionPolicy | `resource`, `trigger` CREATED/CLOSED, `mode` DELETE/ANONYMIZE/PRESERVE, `afterSeconds`, `fields`, `holdBehavior: BLOCK`. |
| LegalHold | `resource`, Boolean `condition`, release `Permission` for that resource. |
| DataLifecycle | `resource`, `retention`, `deletion`, `holds`; linked resources agree, triggers agree, deletion age >= retention minimum. |

Entities declare GLOBAL, TENANT_ROOT or SCOPED. Only SCOPED entities declare `tenantField`, which must be required Identifier<TENANT_ROOT>. A scoped resource's Scope must be SAME_TENANT and identify the resource's and actor subject's declared tenant fields with identical tenant identifier types. GLOBAL scope cannot carry tenant-field references or expose a scoped resource. This boundary cannot be bypassed by an ALLOW predicate.

Policy roles must grant the named permission and match the actor; policy action/resource/permission/scope must agree. The bounded decision helper takes already supplied policy outcomes and authentication/tenant facts: unauthenticated, cross-tenant or missing/unknown context denies; any DENY overrides ALLOW; no ALLOW denies. It does not execute credential verification, role resolution or policy predicates against live records. Runtime enforcement must preserve these obligations on every entry point.

Field classification label must equal its DataClassification level. SECRET and SecretReference must agree. SENSITIVE/SECRET require READ_WRITE audit, encryption at rest and in transit, and non-NONE redaction. SECRET requires OMIT and export DENY. PERMISSION_REQUIRED export requires a permission whose resource is the field owner; since Permission resources are Entities, ValueObject fields cannot satisfy that export mode and must use DENY. An optional exportPermission on DENY-classified data grants no export permission. Sensitive entity data requires a DataLifecycle, and an entity cannot have multiple lifecycle policies. Entity lifecycle rules are not recursively inferred through arbitrary value graphs.

ANONYMIZE requires a nonempty field set from its resource; other deletion modes require an empty set. Identity and tenant fields cannot be anonymized. Legal hold blocks deletion/anonymization until released through the modeled permission; the disposal helper checks explicit ages/hold state, not actual storage or legal compliance. Encryption, audit, redaction, retention, deletion and anonymization are modeled obligations, not executed capabilities or proof of irreversible removal.

## 5. P-03: execution

[ADR-0008](adr/0008-execution-semantics.md), [execution validator and schedule/retry helpers](../tooling/execution_semantics.py).

| Kind | Required data and additional constraints |
| --- | --- |
| Service | Nonempty `operations` Command/Query refs. Every operation has exactly one logical Service owner. |
| Query | `resource`, `scope`, `result`, nonempty `projection`, `paginated`, `maximumResults` 1..10000. Result is a Value type; projection entries bind output `field` to typed `value` expression. |
| UseCase | `service`, ordered nonempty `steps`, input/output ValueObject refs. |
| ExecutionStep | `owner` UseCase, `operation`, `onFailure` STOP/COMPENSATE, `compensation?`, `transaction?`. Reciprocal use-case membership; operation is owned by declared service. |
| Transaction | `aggregate`, nonempty `commands`, `consistency: ATOMIC`, `onFailure: ROLLBACK`; all commands share the aggregate. |
| Failure | `code`, `category` BUSINESS/TRANSIENT/SECURITY, `retryable`; only TRANSIENT may be retryable. |
| RetryPolicy | Nonempty `failures`, `maxAttempts` 1..20, `initialSeconds` 1..86400, `maxDelaySeconds` 1..604800, `multiplier` 1..4. Initial <= maximum delay; failures are retryable TRANSIENT. |
| IdempotencyPolicy | Entity `scope`, `keyType` String/Identifier/Named, positive `windowSeconds`, `replay: RETURN_RESULT`, `conflict: REJECT_DIFFERENT_INPUT`. |
| DeliveryPolicy | `event`, `guarantee` AT_MOST_ONCE/AT_LEAST_ONCE, `ordering` NONE/PER_AGGREGATE, positive `windowSeconds`, `deduplication?`. |
| Schedule | INTERVAL with positive `intervalSeconds`, or LOCAL_DAILY with `localTime`, `timezone`, `tzdbVersion`, `gap` SKIP/REJECT, `overlap` EARLIER/LATER/REJECT. |
| Job | `useCase`, `schedule`, `retry`, `idempotency`, positive `timeoutSeconds`. |

Queries are read-only: there is no write property. Scope agrees with resource. Projection fields belong to the result ValueObject, appear once, cover required output fields and match expression types. Query fields are explicit task projections, not an inferred entity schema.

Commands enter through their aggregate root with member write sets, declared failures and resource-scoped idempotency. Steps reference Command/Query, never recursively invoke arbitrary use cases. COMPENSATE requires a distinct compensating command with the same resource and service; compensation cycles are rejected. A step's transaction must contain its operation. Cross-aggregate transactions are rejected. Ordered steps can express coordination, but no execution engine, parallel DAG or automatic rollback of external effects exists.

AT_LEAST_ONCE delivery requires same-resource deduplication retained at least for the delivery window. Event/delivery references are reciprocal. Exactly-once transport is not accepted. A job's retry failures must be declared by its commands. Its attempts multiplied by timeout plus capped retry delays must fit both job and command idempotency windows. This validates bounded declarations, not concurrent replay safety in a deployed system.

Local schedules require the installed pinned timezone database version and a valid zone from that package; no ambient OS database is used. The local-occurrence helper tests gap and overlap behavior with explicit dates. Timezone pinning and explicit policies define schedule meaning; there is no cron parser, live scheduler, broker, worker or production transaction implementation.

## 6. P-04: task UI and independent design bindings

[ADR-0009](adr/0009-task-interfaces.md), [UI validator](../tooling/ui_semantics.py). Screen is the accepted page concept; `Page` is not another accepted discriminator.

| Kind | Required data and additional constraints |
| --- | --- |
| Screen | `task` UseCase; nonempty `content` Form/Wizard/Table/Search; nonempty `actions`; `states`; `boundary`; `responsive`; `accessibility`. |
| Form | `useCase`, nonempty `controls`, `submit` Action; action invokes the same use case. |
| InputControl | `form`, `field`, `label`, `errorMessage`, `required`, `purpose` TEXT/MULTILINE/DATE/CHOICE. Field belongs to the use-case input ValueObject. |
| Action | `useCase`, nonempty `permissions`, `label`, `confirmation` NONE/REQUIRED; permissions cover all invoked operations. |
| Wizard | `screen`, ordered nonempty `steps`. |
| WizardStep | `wizard`, `form`, `requiresPrevious`; false for first step, true thereafter; reciprocal ownership and matching task. |
| Table | `query`, nonempty `columns`, `emptyMessage`; columns belong to query output ValueObject. |
| Search | `query`, nonempty `filters`, `label`; filters share query. |
| Filter | `query`, `field`, `operator` EQ/CONTAINS/RANGE, `inputType`; field belongs to output projection and input/operator types agree. |
| ViewState | `screen`, `state` EMPTY/LOADING/ERROR/SUCCESS, `message`, `recovery?`; ERROR requires recovery Action. |
| PermissionBoundary | `actor`, nonempty `permissions`, `denied` ERROR ViewState. |
| ResponsivePolicy | `screen`, both COMPACT/EXPANDED `modes`, `preserveActions: true`, `preserveReadingOrder: true`. |

Forms cover required input fields exactly once, with reciprocal control ownership and matching requiredness. Entity-field binding is rejected for controls, columns and filters. Screen actions and owned wizard forms agree with its task; boundary permissions cover action and displayed query permissions with matching actors. Each screen has exactly its four owned view states, with the denied state among them, matching responsive ownership and an accessibility requirement naming the screen. Hiding UI never substitutes for backend authorization.

AccessibilityRequirement is listed with quality kinds below because it shares their evidence contract. Labels, keyboard access, focus and error announcements are required declarations. No browser rendering, responsive layout or assistive-technology behavior is implemented by validation.

The separate [design-binding schema](../contracts/design-bindings.schema.json), version `0.1.0`, associates the exact application/snapshot and semantic subject revisions with a versioned catalogue and component handles. Bindable kinds are Screen, Form, InputControl, Action, Wizard, WizardStep, Table, Search, Filter and ViewState. Duplicate subjects, stale references, wrong snapshots/kinds and unrecognized properties are rejected by [validate_bindings](../tooling/design_bindings.py). Two in-test catalogues bind unchanged semantic UI. This sidecar is not Design IR, a component tree, CSS or framework selection.

## 7. P-05: quality, operations and evidence

[ADR-0010](adr/0010-quality-operations.md), [quality validator](../tooling/quality_semantics.py), [evidence evaluator](../tooling/evidence_semantics.py).

| Kind | Required data and additional constraints |
| --- | --- |
| TestRequirement | `criterion`, nonempty `subjects`, `level` UNIT/INTEGRATION/AUTHORIZATION/E2E/MIGRATION, `evidence`. |
| PerformanceRequirement | `subject` Query/UseCase, `metric`, `comparison`, positive finite `threshold`, `workload`, `evidence`. |
| AccessibilityRequirement | Nonempty UI `subjects`, all LABELS/KEYBOARD/FOCUS/ERROR_ANNOUNCEMENT `checks`, `method: AUTOMATED_AND_MANUAL`, `evidence`. |
| ReliabilityRequirement | `subject` Service/UseCase/Job, `metric` AVAILABILITY_PERCENT/FAILURE_PERCENT, positive finite `threshold` <=100, `windowSeconds` >=60, `evidence`. |
| CompatibilityRequirement | `subject` Command/Query/Event/UseCase, `policy: BACKWARD`, at least two distinct `supportedVersions` including `currentVersion`, positive `windowSeconds`, `evidence`. |
| ObservabilityRequirement | Nonempty `subjects` Command/Query/Service/Job, `signals` LOG/METRIC/TRACE/AUDIT/HEALTH/READINESS, `correlation: REQUIRED`, `redaction: CLASSIFICATION`, `evidence`. |
| Backup | Nonempty Entity `resources`, positive `intervalSeconds`/`retentionSeconds`, `encrypted: true`, `evidence`; retention >= interval. |
| Recovery | `backup`, nonnegative `rpoSeconds`, positive `rtoSeconds`/`restoreTestIntervalSeconds`, `evidence`; RPO >= backup spacing and evidence maximum age <= restore-test interval. |
| Applicability | Closed Boolean `condition`, nonblank `rationale`, exact `decision`; no actor/resource field binding. |
| EvidenceRequirement | Nonempty exact `subjects`, nonempty required `methods`, positive `maxAgeSeconds`, `applicability`. |

Performance metrics are P95_LATENCY_MS and MAX_MEMORY_MB with LTE, or THROUGHPUT_PER_SECOND with GTE. Workload explicitly states positive concurrency/durationSeconds/minimumSamples and nonnegative records. Evidence requirements must cover all obligation subjects and methods; accessibility requires both AUTO_A11Y and MANUAL_A11Y. Backup subjects are its resources; Recovery subjects are its backup's resources. Other method names are closed by the schema, not arbitrary metric labels.

Observations use the separate [evidence schema](../contracts/evidence.schema.json), version `0.1.0`. Records bind exact `requirement`/`obligation`/`subjects` references, snapshot, artifact/configuration/tool SHA-256 handles, profile version, method, observedAt, result and measurements, with workload/window where applicable. These handles are compared, not computed as canonical hashes or authenticated signatures.

Evaluation receives explicit UTC time and artifact/configuration/tool/profile context. Every required method needs fresh PASS evidence with exact references, subjects and context. Missing, NOT_RUN, FAIL, future, stale or mismatched evidence blocks. Measurements must satisfy the obligation's metric, direction, threshold, sample count and workload/window; recovery evidence must satisfy RPO/RTO. Results are PASS, BLOCKED or NOT_APPLICABLE.

False applicability is a reviewed obligation: the harness returns NOT_APPLICABLE only with the explicit caller-supplied `applicability_approved` flag, otherwise BLOCKED. This flag is a test trust input, not authenticated approval. Evidence signatures, authority, actual tests/measurements and production gate orchestration are unimplemented. A modeled Backup/Recovery requirement is not evidence that a backup or restore occurred.

## 8. Validation and boundaries

Strict bounded input -> version/closed shape -> identity -> exact references and reference kinds -> common lifecycle/basis/approval/issues and typed domain/workflow checks -> P-01 through P-05 checks. Invalid structure or references stop dependent checks. Independent semantic errors accumulate under the [stable diagnostic contract](diagnostics.md). Input limit is 1 MiB and 48 nesting levels; duplicate JSON keys, floating-point JSON numbers and nonfinite numbers are rejected. Domain numeric values use strings as defined above.

The executable model has 69 kinds: 7 intent, 8 domain/type/rule, 10 security/access, 5 privacy, 13 execution, 3 workflow, 12 task UI and 11 acceptance/quality/operations/evidence kinds. The [coverage inventory](coverage.md) lists each exactly once. Historical 0.1 regression acceptance does not satisfy current 0.2 requirements, and there is no automatic migration between them.

Safe deferrals are the explicit bounded exclusions in ADR-0006 through ADR-0010: recursive/unbounded types and rules, calendar periods/conversions, richer access/privacy policy languages, distributed atomic transactions/general orchestration, rich visual realization and evidence trust/execution. Unknown concepts remain rejected. P-06, P-08 onward and ADR-0004 retain their later decision gates; bounded P-07 is resolved by ADR-0011. None licenses framework, parser, ORM, database, cloud, MCP or production-language concepts inside canonical semantics.

## Versioned successor: Authoring 0.3.0

The 0.2 contract above remains historical and unchanged. [ADR-0015](adr/0015-explicit-operation-effects-and-dataflow.md) defines the separately versioned [Authoring 0.3 schema](../contracts/authoring-0.3.schema.json), including operation input/output ValueObjects, exact mutable field write sets, ordered assignments, step resource/input bindings, prior-step results, use-case output bindings, query predicates and explicit Filter-to-Query-input bindings, scheduled inputs and event payload constructions. [Inventory](execution-dataflow-inventory.md) records the original ambiguities. New fixture decisions require independent review and exact-content approval. No framework-specific behavior sidecar is authoritative.
