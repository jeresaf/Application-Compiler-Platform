# Phase 1 executable coverage

Current authoring model: **0.2.0, 69 kinds**. P-01 through P-05 have accepted bounded semantics in ADR-0006 through ADR-0010. The 20-kind 0.1 kernel is historical regression coverage, not the current model. The [meta-model](metamodel.md) is normative; the [completion report](phase1-completion-report.md) records test and CI evidence.

## Supported kind inventory

Every kind has the common identity/revision/lifecycle/steward/origin/basis/exact-reference envelope and a closed data schema.

| Domain | Supported kinds |
| --- | --- |
| Intent (7) | Fact, Constraint, Requirement, Preference, Goal, Assumption, Decision |
| Domain/types/rules (8) | Entity, Field, Parameter, Invariant, ValueObject, Relation, Aggregate, TypeDefinition |
| Security/access (10) | Actor, Role, Policy, AuthenticationModel, Permission, Scope, RoleAssignment, PolicySet, SessionPolicy, RatePolicy |
| Privacy (5) | DataClassification, Retention, DeletionPolicy, LegalHold, DataLifecycle |
| Execution (13) | Command, Event, Service, Query, UseCase, ExecutionStep, Transaction, Failure, RetryPolicy, IdempotencyPolicy, DeliveryPolicy, Schedule, Job |
| Workflow (3) | StateMachine, State, Transition |
| Task UI (12) | Screen, Form, InputControl, Action, Wizard, WizardStep, Table, Search, Filter, ViewState, PermissionBoundary, ResponsivePolicy |
| Acceptance/quality/operations/evidence (11) | AcceptanceCriterion, TestRequirement, PerformanceRequirement, AccessibilityRequirement, ReliabilityRequirement, CompatibilityRequirement, ObservabilityRequirement, Backup, Recovery, Applicability, EvidenceRequirement |

## Accepted and executable now

“Executable” means shape/semantic validation and the named bounded reference helpers. It does not mean an application runtime implements the declared capability.

| Area / decision | Executable checks and evidence | Implementation limit |
| --- | --- | --- |
| Shared kernel, ADR-0001/0002 | Closed shapes, exact IDs/revisions/kinds, ownership, basis cycles, lifecycle/attestations, blocking issues, workflow topology, criterion reciprocity, strict input and stable diagnostics | No authenticated approvals, transition engine, durable history or general prose/guard satisfiability proof |
| P-01, ADR-0006 | ValueObject and nominal/refined types; cardinality and acyclic composition; aggregate/root/write boundaries; null vs absence; bounded List/Set; typed value/identity equality; precision/rounding and date/time validation | Declaration validation plus rounding/equality helpers; no storage constraints, general rule execution or live consistency enforcement |
| P-02, ADR-0007 | Authentication/role/permission/scope links; complete deny-overrides PolicySets; mandatory tenant-field typing; classification/audit/encryption/export/redaction declarations; session/rate bounds; retention/delete/anonymization/hold consistency; decision/disposal helper tests | No credential verifier, real grant resolution, enforcement service, encryption, anonymization or jurisdiction compliance proof |
| P-03, ADR-0008 | Logical Service ownership; typed read projections; ordered steps; aggregate transactions; failures/compensation; retry/idempotency horizons; delivery/deduplication declarations; pinned timezone and gap/overlap helper tests | No worker, transport, scheduler, distributed transaction, concurrent replay implementation or generated execution |
| P-04, ADR-0009 | Task input/projection binding; entity-field UI rejection; form/wizard ownership; action/boundary permissions; four view states; responsive/accessibility declarations; two design catalogues and negative sidecar checks | No Design IR, layout/rendering, actual keyboard/focus behavior or frontend generation |
| P-05, ADR-0010 | Typed quality/observability/backup/recovery obligations; subject/method coverage; closed applicability; evidence context, freshness, result, metric, workload/sample/window checks | No test executor, signed evidence, authority verification, backup/restore service or production gate orchestration |

## Positive and negative assets

- Historical 0.1: 28-node draft and approved fixtures; 54 named portable cases (8 positive, 46 negative), plus focused regression tests.
- Current payment: 101 nodes, 68 kinds. Money policies, tenant scope, workflow, execution, task UI and quality declarations.
- Current case-management: 149 nodes, 63 kinds. Organization/user/case/document/assignment/review/approval/comment semantics, cardinalities, assigned-review authorization and archival workflow. Together the reference domains cover all 69 kinds.
- Current portable cases: 100 total; two positive domains and 98 negatives, covering shape rejection and a semantic/reference/bounds failure for each of the 49 promoted kinds.
- The current corpus asserts required code/subject pairs; additional independent diagnostics are allowed. The historical corpus asserts exact code/subject multiplicity. These are distinct assertion contracts.
- Focused tests cover current approved-snapshot closure and a Scope lifecycle/basis failure, literal records that resemble semantic metadata, precision/presence/temporal/tenant/privacy/execution/UI/quality cases.
- In-test design fixtures cover two independent catalogues, wrong semantic kind and unknown CSS property. The validator additionally implements snapshot/revision/duplicate checks; exhaustive branch coverage is not claimed.
- In-test evidence fixtures cover passing performance evidence, stale/future dates, artifact mismatch, NOT_RUN, wrong method, failing threshold, missing evidence and false applicability with/without caller approval. Other supported measurements and binding checks are implemented but do not all have dedicated observation vectors.
- All four schemas are checked; current generated schema/corpus assets are compared with builders. Unknown/framework fields fail closed, including per-promoted-kind leakage cases. This proves rejection of undeclared fields, not detection of technology words in prose.
- Full suite: 23 unittest methods including many cases/subtests. Methods, corpus cases and deployed application tests are different counts.

## Safe bounded deferrals

| Accepted boundary | Deferred/rejected semantics | Why safe for subsequent IR design |
| --- | --- | --- |
| ADR-0006 | Recursive value types, arbitrary refinements/quantification, calendar periods, currency conversion, multi-aggregate atomic writes, wider specialized type registry | Accepted types and operations are closed; omitted constructs cannot enter accepted model 0.2 |
| ADR-0007 | Richer attribute/relationship policy languages, federation protocols, jurisdiction/consent rules, cascading privacy, irreversible anonymization proofs and cross-tenant administration | Explicit actor/resource/tenant scope and typed obligations have defined meaning without these extensions |
| ADR-0008 | General orchestration DAGs, recursive invocation, distributed atomic transactions, arbitrary calendar schedules, exactly-once transport | Ordered steps, bounded failures/retries, single-aggregate transactions and explicit delivery guarantees are representable |
| ADR-0009 | Additional rich UI/API/report/notification concepts, layout/tokens/components, media/charts/gestures and renderers | Task intent and separate catalogue bindings already have a closed boundary; unknown UI kinds remain rejected |
| ADR-0010 | Broader metrics, evidence signatures/executors and production profile orchestration | Typed obligations and observations can be represented without claiming trust or actual verification |

These are accepted scope limits, not unresolved foundational P-01 through P-05 decisions. Business values (currency, thresholds, retention ages, timezone, tenant hierarchy) remain application-specific.

## Later-phase obligations and known limits

P-06 through P-13 remain proposals: persistence/concurrency, canonical encoding/migration, plugin capabilities, provenance/source intelligence, build isolation, production evidence authority and AI candidate validation. ADR-0004's production language/parser experiments have not run. Python/JSON tooling does not decide them.

Validation is bounded to 1 MiB/48 levels. Model validity does not prove guard satisfiability, dynamic cardinality, live tenant enforcement, execution safety, accessibility or measured quality. Synthetic approvals and applicability-authority inputs are not trusted credentials. No generated application, migration, deployment, production benchmark or cross-runtime canonical hash has been produced. Coverage is representative, not exhaustive branch or model checking.

Phase 1 closes the bounded meta-model contract only. [Roadmap](roadmap.md) keeps Phase 2 behind an explicit review gate.

## Regression policy

Material semantic changes require updated contracts, a design decision when appropriate, positive and negative fixtures, stable diagnostics and coverage updates. Reproducing cases accompany semantic validator fixes. A schema addition alone is not implemented semantic support.
