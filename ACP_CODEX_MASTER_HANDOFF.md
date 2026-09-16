# ACP — Application Compiler Platform
## Codex Master Handoff and Development Charter
### Status: Architecture Baseline v0.2
### Purpose: Final design and production development handoff

---

## 1. Executive Intent

Build a production-grade, specification-driven application compiler platform that can take refined human requirements and turn them into complete, testable, traceable, deployable application systems.

The platform is not primarily an "AI code generator" and not merely an MCP server.

Its central idea is:

> Human intent is progressively formalized into an authoritative application specification, compiled through semantic intermediate representations, lowered into target-specific representations, and then deterministically generated and verified wherever possible. AI is used only where reasoning is genuinely useful.

The original motivation includes reducing LLM token usage, but token efficiency is a consequence of the architecture rather than the primary design objective.

The long-term objective is to make software development:
- more deterministic;
- more traceable;
- safer to evolve;
- less repetitive;
- easier for AI systems to reason about;
- less dependent on repeatedly loading large codebases into model context;
- capable of producing and maintaining production systems, not merely scaffolding them.

Working project name: **ACP — Application Compiler Platform**.

The name may change later. Do not let naming affect architecture.

---

# 2. Critical Architectural Position

The most important decision is:

> **The Canonical Application Model / IR is the core of ACP.**

Not MCP.
Not ANTLR.
Not Tree-sitter.
Not an LLM.
Not source code.
Not templates.

These are adapters, frontends, analyzers, targets, or execution components around the canonical semantic model.

The expected conceptual flow is:

```text
Human Intent
    ↓
Conversation / Refinement
    ↓
Requirements + Decisions + Constraints
    ↓
Formal Specification
    ↓
Parsing / Structured Input
    ↓
Semantic Analysis
    ↓
Canonical IR
    ↓
Architecture Lowering
    ↓
Target IR
    ↓
Code / Infrastructure Generation
    ↓
Source Analysis
    ↓
Build + Tests + Security + Verification
    ↓
Deployable Artifact
    ↓
Runtime Evidence
    ↓
Drift / Feedback
```

MCP is an efficient AI-facing interface to these capabilities.

---

# 3. Non-Negotiable Constitutional Principles

## 3.1 Specification is authoritative

Conversation is not the source of truth.

Generated source code is not the source of truth for intended behavior.

Approved specification is the authoritative representation of intended application behavior.

However ACP must separately understand:
- what **should** exist — specification;
- what **does** exist — source and infrastructure;
- what **is running** — runtime/deployment state.

This allows drift detection instead of assuming implementation correctness.

---

## 3.2 Meaning must survive compilation

A requirement must remain traceable through all applicable stages:

```text
Requirement
  → Semantic Rule
  → Domain/Application Model
  → Architecture Decision
  → Target Representation
  → Source Implementation
  → Database/API/UI
  → Tests
  → Deployment
  → Runtime Controls
```

Important information must not disappear between stages.

---

## 3.3 Stable semantic identity

All durable concepts receive immutable semantic IDs independent of display names.

Examples:

```text
REQ-000091
DEC-000042
ENT-000031
FLD-000211
INV-000018
CMD-000014
EVT-000033
POL-000018
WF-000014
SCR-000038
API-000027
TEST-000087
```

Renaming `Alumni` to `OldStudent` must not imply deletion and recreation if the semantic concept remains the same.

---

## 3.4 AI is bounded

AI may:
- propose;
- analyze;
- explain;
- design;
- synthesize non-deterministic implementation;
- diagnose failures;
- recommend architecture;
- produce candidate changes.

AI must not silently:
- alter approved requirements;
- weaken security;
- override locked decisions;
- execute destructive operations;
- reinterpret unresolved ambiguity as fact.

---

## 3.5 Determinism is preferred

Given equivalent:
- canonical specification;
- compiler version;
- target profiles;
- target plugin versions;
- locked dependencies;
- configuration inputs;

deterministic compiler stages should produce equivalent output.

AI-generated output must be isolated to stages where deterministic compilation is insufficient.

---

## 3.6 Uncertainty is first-class

ACP must preserve distinctions such as:

```text
CAPTURED
REFINING
PROPOSED
REVIEW_REQUIRED
APPROVED
IMPLEMENTED
VERIFIED
RELEASED
BLOCKED
SUPERSEDED
DEPRECATED
REJECTED
```

A suggestion must never become an approved production rule merely because an LLM wrote it.

---

## 3.7 Destructive changes require explicit handling

Potentially destructive operations include:
- data loss;
- narrowing data types;
- dropping columns/tables;
- incompatible API changes;
- removing permissions or audit requirements;
- security reductions;
- irreversible infrastructure changes.

These require impact analysis and appropriate approval gates.

---

## 3.8 Security is semantic

Security is modeled before code generation.

ACP must be able to represent:
- actors;
- authentication;
- roles;
- permissions;
- resource policies;
- tenant boundaries;
- record-level scope;
- sensitive data classification;
- encryption requirements;
- audit requirements;
- secrets;
- session policy;
- rate limits;
- retention;
- export restrictions.

Security cannot be treated as a post-generation patch.

---

## 3.9 Tests are compiled evidence

A build is not correct merely because it compiles.

Requirements should generate or map to verifiable evidence:
- unit tests;
- integration tests;
- API tests;
- state transition tests;
- authorization tests;
- data integrity tests;
- UI/E2E tests;
- migration tests;
- security checks;
- performance tests when required.

---

## 3.10 Code ownership is explicit

At minimum support:

```text
COMPILER_OWNED
FRAMEWORK_OWNED
AI_MANAGED
HUMAN_OWNED
```

Regeneration must not unexpectedly overwrite human-owned logic.

---

## 3.11 Changes are semantic transactions

ACP changes the system via semantic change sets rather than indiscriminate file rewriting.

Each change should support:
- intent;
- impacted semantic concepts;
- semantic diff;
- risk;
- compatibility classification;
- migration needs;
- verification requirements;
- approval requirements;
- provenance.

---

## 3.12 Everything important is explainable

ACP should eventually answer:

> Why does this field, endpoint, permission, screen, database constraint, generated function, test, deployment setting, or runtime control exist?

The explanation must trace back to requirements and decisions.

---

# 4. Model Intent Correctly

ACP must distinguish at least:

```text
FACT
CONSTRAINT
REQUIREMENT
PREFERENCE
GOAL
ASSUMPTION
DECISION
```

These must not be treated as equivalent.

Example:

```text
FACT
Currency is UGX.

CONSTRAINT
Financial transactions must be auditable.

REQUIREMENT
Members must pay the registration fee before contributing.

PREFERENCE
Prefer PostgreSQL where target requirements allow it.

GOAL
Registration should require as few user actions as practical.

ASSUMPTION
The first deployment will run in one region.

DECISION
Use PostgreSQL for Reference Application A.
```

Constraints cannot simply be violated to optimize goals.

Preferences may be overridden with justification.

Assumptions must remain visible and revisitable.

Decisions require provenance.

---

# 5. Requirements and Traceability

A requirement is a first-class versioned semantic object.

Example:

```yaml
id: REQ-SACCO-001
title: Membership registration payment
statement: >
  A member must complete the required registration payment
  before making ordinary SACCO contributions.
status: APPROVED
priority: MUST
acceptance:
  - unpaid member cannot contribute
  - paid member can contribute
  - duplicate registration payment is rejected
derived:
  - RULE-SACCO-004
  - POL-SACCO-002
  - TEST-SACCO-011
  - TEST-SACCO-012
```

Values likely to change should be represented separately where appropriate:

```yaml
id: PARAM-SACCO-MEMBERSHIP-FEE
type: Money<UGX>
value: 50000
```

The requirement references the parameter instead of hard-coding the value throughout implementation.

ACP should detect:
- approved requirements without implementation;
- implementation without requirement/decision provenance;
- approved requirements without verification evidence;
- stale tests;
- contradictory requirements.

---

# 6. Decision System

Architecture and important product decisions are first-class.

Use ADR-like records:

```yaml
id: ADR-0042
status: ACCEPTED
decision: Use PostgreSQL for this target profile.
reason:
  - transactional integrity
  - relational constraints
  - reporting requirements
alternatives:
  - MongoDB
  - SQLite
```

Support decision strengths:

```text
PREFERRED
REQUIRED
LOCKED
```

A locked decision cannot be altered through routine generation or AI reasoning.

Changing it requires an explicit decision/change-set workflow.

---

# 7. Canonical Semantic Model

The first major engineering task is to define the meta-model.

Do not begin by writing an ANTLR grammar.

Candidate top-level domains:

```text
Application
│
├── Metadata
├── Context
├── Facts
├── Constraints
├── Goals
├── Preferences
├── Assumptions
├── Requirements
├── Decisions
│
├── Domain
│   ├── Entity
│   ├── ValueObject
│   ├── Field
│   ├── Relation
│   ├── Aggregate
│   ├── Parameter
│   ├── Invariant
│   ├── Command
│   └── Event
│
├── Security
│   ├── Actor
│   ├── AuthenticationModel
│   ├── Role
│   ├── Permission
│   ├── Policy
│   ├── Scope
│   └── DataClassification
│
├── Workflow
│   ├── StateMachine
│   ├── State
│   ├── Transition
│   ├── Guard
│   └── Effect
│
├── ApplicationLayer
│   ├── UseCase
│   ├── Service
│   ├── Query
│   ├── Transaction
│   └── Job
│
├── Interface
│   ├── API
│   ├── Screen
│   ├── Form
│   ├── Table
│   ├── Search
│   ├── Report
│   ├── Dashboard
│   └── Notification
│
├── Integration
│   ├── ExternalSystem
│   ├── Webhook
│   ├── Queue
│   ├── ScheduledJob
│   └── FileExchange
│
├── Quality
│   ├── AcceptanceCriterion
│   ├── TestRequirement
│   ├── PerformanceRequirement
│   ├── AccessibilityRequirement
│   ├── ReliabilityRequirement
│   └── CompatibilityRequirement
│
└── Operations
    ├── Environment
    ├── DeploymentProfile
    ├── Observability
    ├── Backup
    ├── Recovery
    ├── Retention
    └── Scaling
```

This list is a starting point, not a frozen design.

---

# 8. Intermediate Representation Strategy

Do not use a parser-specific parse tree as the application model.

Recommended stages:

```text
Source / Structured Input
        ↓
Parser Output
        ↓
Semantic AST
        ↓
Canonical IR
        ↓
Domain/Application IR
        ↓
Architecture IR
        ↓
Target IR
        ↓
Generated Artifacts
```

A useful conceptual decomposition:

## Product IR
Human/product concerns:
- users;
- business capabilities;
- workflows;
- rules;
- reports;
- permissions.

## Domain IR
Formal business semantics:
- entities;
- value objects;
- aggregates;
- invariants;
- commands;
- events.

## Application IR
Application behavior:
- use cases;
- queries;
- services;
- transactions;
- policies.

## Architecture IR
Technical realization:
- APIs;
- persistence;
- services;
- queues;
- cache;
- frontend boundaries;
- deployment topology.

## Target IR
Framework-specific representation:
- Spring controller;
- NestJS service;
- Prisma model;
- JPA entity;
- PostgreSQL migration;
- Vue component;
- React component;
- Playwright test;
- Kubernetes resource.

Do not force all layers into one giant mutable object if separate typed IRs improve clarity and invariants.

---

# 9. Semantic Types

Avoid reducing domain concepts to primitive strings and integers.

Candidate semantic types include:

```text
Email
PhoneNumber
URL
Money<Currency>
Percentage
Date
DateTime
Duration
Timezone
CountryCode
CurrencyCode
File
Image
GeoPoint
Identifier
NationalIdentifier
SecretReference
Version
```

Example:

```text
Money<UGX>
```

must make invalid currency arithmetic difficult or impossible.

Target compilers decide representation in database/runtime/UI.

---

# 10. Rules and Invariants

Rules and invariants should be first-class semantic constructs.

Example:

```text
invariant SACCO_001 {
    Contribution.amount > 0
}

invariant SACCO_002 {
    Contribution.member.status == ACTIVE
}
```

A semantic invariant may drive:
- runtime validation;
- database constraints;
- application guards;
- generated tests;
- audit checks;
- migration verification.

Do not assume every invariant can or should be implemented at every layer.

The compiler must know enforcement locations.

---

# 11. Commands, Events and Side Effects

Model behavioral intent explicitly.

Example:

```text
command RecordContribution
event ContributionRecorded
event ContributionReversed
```

Avoid forcing tightly coupled implementations such as:

```text
PaymentService → EmailService → AuditService → ReportService
```

when the semantics are better expressed as events.

The architecture lowering phase chooses:
- direct invocation;
- domain event;
- transaction outbox;
- message broker;
- asynchronous worker;

based on target profile and system requirements.

---

# 12. Workflow and State Machines

Business workflows should support explicit state machines.

Example:

```text
Loan:
DRAFT
  → SUBMITTED
  → UNDER_REVIEW
  → APPROVED
  → DISBURSED
  → REPAID
```

Alternative states may include:

```text
REJECTED
CANCELLED
DEFAULTED
```

The model must represent:
- legal transitions;
- transition actors;
- guards;
- effects;
- required data;
- emitted events.

From this, ACP may derive:
- backend transition guards;
- authorization;
- UI action availability;
- audit entries;
- tests.

Invalid transitions must be detectable before runtime when possible.

---

# 13. Security Model

Security is part of the meta-model.

Example:

```text
role CampusAdmin {
    read Alumni
        where Alumni.campus == actor.campus

    update Alumni
        where Alumni.campus == actor.campus
}
```

A single policy may affect:
- API authorization;
- database query scope;
- UI visibility;
- exports;
- tests;
- audit rules.

Sensitive data example:

```text
field NationalID {
    classification SENSITIVE
    expose ADMIN_ONLY
    audit READ
    encrypt AT_REST
}
```

Target generation may translate this into:
- serializer restrictions;
- logging redaction;
- encryption integration;
- audit hooks;
- privileged UI controls;
- security tests.

---

# 14. Privacy and Data Lifecycle

Represent:
- retention periods;
- anonymization;
- deletion rules;
- legal hold;
- immutable financial/audit records;
- export;
- archival.

Example:

```text
on AccountDeletion:
    anonymize Profile
    preserve FinancialLedger
    preserve AuditReference
```

These semantics must be independent of a particular target framework.

---

# 15. UI and UX Semantic Model

Do not generate UI directly from database schemas.

Model UI intent.

Candidate UI semantics:

```text
ApplicationShell
Navigation
Page
Layout
Section
Wizard
Form
Field
Action
Table
Filter
Search
Modal
Dashboard
Metric
Chart
EmptyState
LoadingState
ErrorState
PermissionBoundary
ResponsiveRule
AccessibilityRequirement
```

Example:

```text
screen AlumniRegistration {
    layout Wizard
    step PersonalDetails
    step Education
    step Contact
    step Confirmation
}
```

The Design System should be separately modeled:

```text
Design IR
├── Tokens
├── Typography
├── Spacing
├── Components
├── Interaction
├── Responsive Rules
└── Accessibility Rules
```

The same application semantics should be capable of targeting different visual systems.

---

# 16. Accessibility

Accessibility is a build concern, not an optional polish step.

ACP should support requirements for:
- labels;
- keyboard navigation;
- focus management;
- semantic controls;
- error messaging;
- accessible dynamic content;
- responsive behavior;
- design token constraints;
- automated accessibility verification where possible.

---

# 17. Database and Migration Safety

Creating a new schema is easier than evolving a production database.

ACP must include a migration planner.

Conceptual flow:

```text
Semantic Schema Change
    ↓
Data Impact Analysis
    ↓
Compatibility Analysis
    ↓
Migration Plan
    ↓
Preconditions
    ↓
Migration
    ↓
Verification
    ↓
Cleanup / Finalization
```

Example:

```text
DANGEROUS CHANGE

payments.reference
VARCHAR(100) → VARCHAR(20)

Observed maximum existing length: 67

Potential data loss: YES

Deployment blocked pending explicit strategy.
```

Support phased migrations where required:
1. expand;
2. dual-read/write if necessary;
3. backfill;
4. switch;
5. contract.

---

# 18. Backward Compatibility

ACP must eventually model:
- API versions;
- deprecated fields;
- compatibility windows;
- mobile/client minimum versions;
- migration deadlines;
- event schema compatibility.

A deployment may have multiple clients active simultaneously.

Do not assume atomic replacement of the entire distributed system.

---

# 19. Change Sets and Semantic Diffs

A change set is a first-class object.

Example:

```yaml
id: CHANGE-000142
intent: Allow SACCO Treasurer to reverse an erroneous contribution.
risk: HIGH
changes:
  - add CMD-SACCO-REVERSE-CONTRIBUTION
  - add PERM-SACCO-REVERSE
  - add EVT-CONTRIBUTION-REVERSED
affected:
  - Payment
  - Ledger
  - Audit
  - MemberBalance
  - TreasurerUI
compatibility: BACKWARD_COMPATIBLE
migration: NONE
approval: REQUIRED
```

Execution model:

```text
PLAN
→ VALIDATE
→ IMPACT ANALYZE
→ APPROVE when necessary
→ APPLY TO SPEC
→ COMPILE
→ BUILD
→ TEST
→ VERIFY
→ PACKAGE
→ COMMIT/RELEASE
```

Semantic diff must be separate from textual source diff.

Example:

```text
Added:
  Loan.guarantors

Changed:
  Loan.maxAmount
  UGX 5,000,000 → UGX 10,000,000

Permission removed:
  Treasurer → Loan.approve

Impact:
  2 APIs
  3 screens
  1 migration
  11 tests
```

---

# 20. Versioning and Provenance

Every meaningful build should be reproducible from versioned inputs.

Track:
- specification version;
- compiler version;
- target plugins;
- generator versions;
- dependency lockfiles;
- configuration schema version;
- artifacts;
- tests;
- approvals;
- provenance.

A generated symbol should eventually be explainable:

```text
requireMembershipFee()

Generated by:
ACP Compiler 2.7.1

From:
RULE-SACCO-001

Requirement:
REQ-SACCO-003

Introduced:
SPEC v31

Modified:
SPEC v74

Generator:
target-nestjs-policy 4.2

Verified by:
TEST-SACCO-011
TEST-SACCO-012
```

---

# 21. State Storage Strategy

Do not make ad-hoc YAML files the only durable state model.

Evaluate a design with:
- immutable/versioned canonical snapshots;
- append-only change journal;
- semantic IDs;
- content hashes;
- durable provenance;
- Git-exportable human-readable representations.

The canonical persistence implementation should be replaceable behind repository interfaces.

Possible early storage may be simple, but the logical model must support:
- atomic change sets;
- version history;
- semantic diff;
- rollback;
- audit;
- branching or isolated proposal states.

Do not confuse storage format with canonical semantics.

---

# 22. Conflict Detection

The semantic layer must detect conflicts.

Example:

```text
REQ-014:
Users may delete their financial history.

CONSTRAINT-002:
Financial records must be retained for seven years.
```

Expected:

```text
SEMANTIC CONFLICT

REQ-014 conflicts with CONSTRAINT-002.

Affected:
Ledger
Payment
AuditRecord

Compilation blocked until resolved.
```

Conflict resolution must be explicit and recorded.

---

# 23. Parser / DSL Position

Do not commit prematurely to ANTLR.

The language frontend is replaceable.

Evaluate at least:
- ANTLR;
- Langium;
- Xtext;
- PEG-family tooling when justified.

Evaluation criteria:
- grammar scalability;
- semantic model integration;
- diagnostics;
- error recovery;
- IDE/LSP support;
- refactoring;
- references/scoping;
- ecosystem;
- performance;
- TypeScript/JVM/runtime integration;
- versioning;
- testability;
- maintenance burden.

ANTLR is a strong candidate for grammar parsing.

Langium is a strong candidate if TypeScript-native language tooling and LSP integration are strategically valuable.

Xtext deserves consideration if the DSL becomes a major language-engineering product.

The parser must produce a parse representation that is transformed into ACP's semantic AST/IR.

The parser's AST must never become the canonical application model.

---

# 24. Tree-sitter Position

Tree-sitter solves a different problem.

Use it primarily for understanding existing/generated source code:
- symbols;
- definitions;
- references;
- syntax structure;
- incremental parsing;
- source impact analysis.

Conceptually:

```text
Desired System
    ↓
Canonical / Target IR
    ↓
semantic comparison
    ↑
Source Model
    ↑
Tree-sitter / language analyzers
    ↑
Existing Source
```

Tree-sitter may be supplemented by native compiler/LSP semantic APIs when deeper type information is needed.

Do not assume syntax trees alone provide complete semantic understanding.

---

# 25. Source Intelligence

ACP should build a semantic source index.

Desired capabilities:

```text
get_symbol(...)
find_references(...)
find_implementations(...)
dependency_graph(...)
affected_tests(...)
impact_analysis(...)
source_ownership(...)
drift(...)
```

The source model should minimize the need to send entire repositories into an LLM context.

---

# 26. Generated vs Custom Code

Avoid naive full-file regeneration.

Support:
- generated regions only where safe;
- extension points;
- partial classes/modules where target language allows;
- adapters;
- plugin hooks;
- AST-aware edits;
- generated base classes plus custom subclasses where appropriate.

Code ownership must be machine-readable.

Protected/human-owned code must not be overwritten automatically.

---

# 27. Deterministic Generation vs AI

Classify compiler operations:

```text
DETERMINISTIC
AI_ASSISTED
AI_REQUIRES_APPROVAL
FORBIDDEN_AUTOMATIC
```

Examples:

```text
Generate basic DTO        → DETERMINISTIC
Generate CRUD route       → DETERMINISTIC
Propose index             → AI_ASSISTED or optimizer-assisted
Write novel algorithm     → AI_ASSISTED
Change auth architecture  → AI_REQUIRES_APPROVAL
Drop production database  → FORBIDDEN_AUTOMATIC
```

Use AI where reasoning is valuable, not where templates/compilers are sufficient.

---

# 28. MCP Role

MCP is an interface layer over ACP.

It should expose high-level semantic operations rather than raw file editing as the primary workflow.

Candidate MCP surface:

```text
project.summary
project.context
project.status
project.drift

spec.query
spec.validate
spec.diff
spec.propose_change
spec.apply_change

architecture.explain
architecture.impact

compiler.plan
compiler.build
compiler.verify

source.symbol
source.references
source.impact
source.patch

tests.affected
tests.run
tests.failures

release.plan
release.verify
```

Avoid hundreds of tiny MCP tools unless evidence shows they are needed.

The model should operate on stable semantic references and task-specific context bundles.

---

# 29. Token-Efficiency Architecture

Token reduction should emerge from:
- stable semantic IDs;
- context queries;
- compact module summaries;
- semantic diffs;
- source symbol retrieval;
- dependency graphs;
- impact analysis;
- project state summaries;
- requirement/decision references;
- target-aware context bundles.

Example:

```text
project.context(
  project="ReferenceApp",
  task="add loan guarantors"
)
```

could return only:

```text
Relevant domain:
Loan
Member
Guarantor

Requirements:
REQ-LOAN-003
REQ-LOAN-008

Policies:
POL-LOAN-002

Workflow:
WF-LOAN-001

Decision:
ADR-014

Spec:
v281

Likely impact:
3 domain concepts
2 APIs
2 screens
6 tests
```

The AI then requests deeper information only as needed.

---

# 30. Build and Execution Isolation

Generated software and build steps may contain defects or unsafe behavior.

ACP must eventually execute builds/tests/migrations in controlled environments.

Plan for:
- sandboxed build workers;
- filesystem boundaries;
- resource limits;
- network policy;
- secret isolation;
- ephemeral environments;
- reproducible containers/toolchains;
- explicit production credentials separation.

Never run arbitrary generated code with unrestricted host access.

---

# 31. Production Quality Gates

ACP may only declare a target production-ready when the configured production profile passes required gates.

Baseline gates should include:

```text
Specification valid
No unresolved blocking ambiguity
No unresolved semantic conflicts
Required decisions accepted
Required traceability satisfied
Architecture valid
Security policies compiled
Authorization tests pass
Migration plan validated
Build succeeds
Required unit tests pass
Required integration tests pass
Required E2E tests pass
Acceptance criteria pass
Dependency policy passes
Security scanning passes
Secrets scanning passes
Configuration validates
Health checks exist
Observability requirements exist
Backup/recovery requirements satisfied
Deployment package reproducible
Critical requirement evidence complete
```

Profiles may strengthen these gates.

They must not silently weaken the global baseline.

---

# 32. Software Supply Chain

Production readiness should include:
- dependency lockfiles;
- dependency vulnerability policy;
- SBOM generation;
- artifact hashing;
- generator/compiler provenance;
- secret scanning;
- static analysis where supported;
- license policy when required;
- signed/reproducible artifacts where target environments justify it.

Design this as part of release verification, not as an afterthought.

---

# 33. Observability

Generated applications should support semantic observability requirements.

Model:
- structured logs;
- correlation IDs;
- traces;
- metrics;
- audit events;
- health/readiness checks;
- alert conditions;
- business metrics where specified.

Sensitive data must not leak into logs.

---

# 34. Performance and Scale

Performance requirements belong in the spec.

Example:

```text
query AlumniSearch {
    expectedRecords 5_000_000
    targetP95 500ms
    paginated true
}
```

This can influence:
- indexes;
- query architecture;
- cache;
- pagination;
- asynchronous processing;
- tests.

Do not claim performance guarantees without measurable verification.

---

# 35. Reliability and Recovery

Represent and verify when applicable:
- retry semantics;
- idempotency;
- timeout policy;
- transaction boundaries;
- outbox/inbox patterns;
- disaster recovery;
- backup;
- restore verification;
- RPO;
- RTO;
- graceful degradation.

These should be architecture semantics, not arbitrary target code.

---

# 36. Target Plugin Architecture

Target frameworks must be plugins/adapters around stable compiler contracts.

Candidate future targets may include:

Backend:
- Spring Boot;
- NestJS/Node;
- .NET;
- Laravel.

Frontend:
- Vue;
- React;
- mobile targets later.

Persistence:
- PostgreSQL;
- other databases only through capability profiles.

Infrastructure:
- Docker;
- selected cloud/container targets.

A target plugin declares capabilities.

If a requested semantic capability cannot be implemented safely by the selected target, compilation should produce a target capability error rather than silently approximating behavior.

---

# 37. Capability Profiles

Example:

```yaml
target:
  backend: spring-boot
  frontend: vue
  database: postgresql
```

The compiler loads a capability model.

Example failure:

```text
TARGET CAPABILITY ERROR

Requested:
Feature X

Selected target:
Target Y

Safe implementation:
Unavailable

Required action:
change target, add plugin, or revise requirement.
```

---

# 38. Reference Application Strategy

Do not validate ACP using trivial TODO/CRUD applications.

Use at least one complex reference system containing:
- users;
- organizations/campuses/tenants;
- record-level permissions;
- financial operations;
- workflows;
- approvals;
- documents;
- reports;
- notifications;
- audit;
- migration evolution;
- API;
- responsive UI;
- background jobs;
- version changes.

A multi-campus alumni + SACCO platform is a strong candidate for **Reference Application A**, but no SACCO-specific assumptions may leak into ACP core abstractions.

Reference applications are compiler test suites, not architecture templates.

---

# 39. Testing ACP Itself

ACP needs multiple test layers:

## Compiler tests
- parser tests;
- semantic validation tests;
- invalid-spec tests;
- conflict tests;
- lowering tests;
- target IR tests.

## Golden tests
Known specification → expected stable generated output.

Use carefully so legitimate formatting changes do not make tests useless.

## Property tests
Validate invariants over large generated input ranges.

## Migration tests
Verify safe schema evolution and unsafe-operation detection.

## Target integration tests
Generated target apps must compile and run.

## Security tests
Ensure policies are enforced across generated layers.

## Drift tests
Deliberately modify generated/source artifacts and confirm drift detection.

## Regression corpus
Every significant ACP bug should produce a permanent regression case.

---

# 40. Development Roadmap

Do not skip foundational phases.

## Phase 0 — Constitution
Deliver:
- architecture principles;
- vocabulary;
- authority hierarchy;
- AI boundaries;
- production definition.

This document is the current starting baseline.

## Phase 1 — Meta-Model
Precisely define:
- each semantic concept;
- IDs;
- lifecycle;
- relationships;
- invariants;
- validation;
- ownership.

Deliver:
- `docs/metamodel.md`
- diagrams
- machine-readable type model/prototype

## Phase 2 — Canonical IR
Design framework-neutral typed IR.

Deliver:
- schema/types;
- serialization contract;
- compatibility/versioning rules;
- examples;
- validation suite.

## Phase 3 — Change and Provenance Model
Deliver:
- change-set model;
- semantic diff;
- impact graph;
- approvals;
- change journal;
- snapshot/version model.

## Phase 4 — Compiler Core
Deliver stages:
- ingest;
- semantic analysis;
- normalize;
- lower;
- target compile;
- verify.

No full DSL is required yet. Structured fixtures may feed the IR.

## Phase 5 — DSL / Language Frontend Evaluation
Prototype representative grammar and tooling in top candidates.

Write an ADR comparing:
- ANTLR;
- Langium;
- Xtext;
- another option only if justified.

Select using measured criteria.

## Phase 6 — First Target Plugin
Choose one production-quality stack.

Do not implement multiple stacks until the plugin boundary is proven.

## Phase 7 — Source Intelligence
Add:
- Tree-sitter/native semantic analyzers;
- symbol graph;
- references;
- source ownership;
- drift.

## Phase 8 — Verification Engine
Integrate:
- builds;
- tests;
- migrations;
- security;
- traceability;
- quality gates.

## Phase 9 — MCP Adapter
Expose mature semantic/compiler capabilities to AI tools.

MCP should not dictate compiler internals.

## Phase 10 — Reference Application
Generate and evolve a serious application through ACP.

Do not merely generate once. Perform multiple schema, policy, workflow, UI, and compatibility changes.

## Phase 11 — Hardening
Focus on:
- concurrency;
- migration rollback/recovery;
- supply chain;
- sandboxing;
- scale;
- performance;
- compatibility;
- provenance;
- failure recovery.

## Phase 12 — Production Validation
Prove ACP can:
- create;
- modify;
- migrate;
- verify;
- deploy;
- explain;
- maintain;
- recover;

a non-trivial application across repeated releases.

---

# 41. Codex Development Instructions

Codex should treat this document as the architecture charter.

## First task

Do **not** begin by implementing ANTLR grammar or application generators.

Start by producing:

```text
docs/
  constitution.md
  glossary.md
  metamodel.md
  ir-design.md
  change-model.md
  threat-model.md
  production-gates.md
  roadmap.md
  adr/
```

Create a minimal repository skeleton that supports the architecture without locking implementation language prematurely.

Then define the Phase 1 meta-model rigorously.

## Engineering behavior

Codex should:
- record important architectural decisions as ADRs;
- keep approved decisions separate from proposed decisions;
- avoid guessing business semantics;
- identify unresolved assumptions explicitly;
- prefer stable interfaces;
- use dependency inversion around storage, parser, target, AI, and source analyzers;
- make compiler stages independently testable;
- add regression tests with every meaningful bug fix;
- preserve provenance;
- avoid framework leakage into canonical semantics;
- avoid premature optimization;
- avoid premature multi-target support;
- avoid implementing a textual DSL before the semantic model is stable.

## When blocked

Do not hide uncertainty.

Create a design issue or proposed ADR with:
- question;
- options;
- recommendation;
- consequences;
- what is blocked.

Continue non-destructive independent work where possible.

---

# 42. Initial Repository Shape — Proposal, Not Yet Locked

Codex should review this before adopting it:

```text
acp/
├── docs/
│   ├── constitution.md
│   ├── glossary.md
│   ├── metamodel.md
│   ├── ir-design.md
│   ├── change-model.md
│   ├── threat-model.md
│   ├── production-gates.md
│   ├── roadmap.md
│   └── adr/
│
├── packages/
│   ├── model/
│   ├── ir/
│   ├── compiler-core/
│   ├── change-engine/
│   ├── provenance/
│   ├── diagnostics/
│   ├── source-model/
│   ├── verifier/
│   ├── target-sdk/
│   └── mcp-adapter/
│
├── frontends/
│   └── structured/
│
├── targets/
│   └── reference-target/
│
├── reference-apps/
│   └── reference-a/
│
├── test-corpus/
│
└── tooling/
```

Do not create packages merely because they appear in this proposal.

Prove module boundaries first.

---

# 43. Questions Codex Must Resolve Through ADRs

These are not user questions to ask immediately. They are engineering investigations.

1. What exact canonical meta-model best separates requirements, semantics, architecture, and target concerns?
2. Should canonical state use immutable event/change journaling plus snapshots?
3. What serialization format should define IR interchange?
4. How will schema/IR version migration work?
5. Which implementation language best serves compiler core requirements?
6. Should language tooling live in the same runtime as compiler core?
7. What plugin ABI/API should target compilers implement?
8. What guarantees are required for deterministic generation?
9. How should human-owned source and generated source interoperate by target?
10. How should deep source semantics be obtained beyond Tree-sitter syntax?
11. Which build sandbox model is appropriate?
12. What is the minimum viable production profile?
13. How should secrets and environment-specific configuration be modeled?
14. How should provenance be embedded/mapped without polluting source?
15. Which semantic constraints can compile to database enforcement vs application enforcement?
16. How should target capability negotiation work?
17. How should branch/proposal states and concurrent spec edits merge?
18. How should compiler errors remain understandable to non-compiler experts?
19. How should AI-assisted outputs be validated and cached?
20. How should context bundles be constructed to minimize LLM tokens without withholding necessary semantics?

---

# 44. Architecture Risks to Actively Guard Against

## Risk: Building a glorified scaffolder
Mitigation:
Focus on evolution, migration, verification, provenance, drift, and semantic changes.

## Risk: Parser-first design
Mitigation:
Meta-model and IR first.

## Risk: MCP-first design
Mitigation:
Compiler platform first; MCP adapter later.

## Risk: LLM owns too much
Mitigation:
Prefer deterministic compiler stages and validation.

## Risk: Framework leakage
Mitigation:
Keep canonical semantics target-neutral.

## Risk: Round-trip editing becomes impossible
Mitigation:
Source ownership + extension architecture + semantic source model.

## Risk: Unsafe migrations
Mitigation:
Explicit migration planner and production data checks.

## Risk: Generated UI is CRUD quality only
Mitigation:
Create dedicated UX/UI semantics and Design IR.

## Risk: Security inconsistency
Mitigation:
Compile policy across backend, query, UI, exports, and tests.

## Risk: Spec becomes unreadable
Mitigation:
Keep canonical model machine-strong while providing human-focused views and DSL/editor tooling.

## Risk: Canonical model becomes a universal-object monster
Mitigation:
Use typed bounded IR layers and clear compiler passes.

## Risk: Too many targets too early
Mitigation:
One rigorous reference target first.

## Risk: Token savings degrade correctness
Mitigation:
Context minimization must be dependency-aware; correctness outranks token minimization.

---

# 45. Explicit Non-Goals for Early Development

Do not initially attempt:
- every programming language;
- every database;
- every frontend framework;
- fully autonomous production deployment;
- arbitrary round-trip regeneration of any legacy application;
- natural-language-only specifications;
- perfect automatic architecture selection;
- unrestricted AI-written migrations;
- automatic destructive production operations.

These may become future capabilities, but they should not distort the compiler foundation.

---

# 46. Success Criteria

ACP is successful when it can take an approved specification for a non-trivial system and repeatedly:

1. validate its semantics;
2. identify conflicts;
3. lower it into a chosen architecture;
4. generate a production-quality target implementation;
5. generate or map verification evidence;
6. build and test the application;
7. safely evolve the specification;
8. calculate semantic impact;
9. generate safe migrations;
10. preserve human-owned extensions;
11. detect source/spec/deployment drift;
12. explain implementation provenance;
13. expose only relevant semantic context to an AI;
14. reproduce equivalent builds from equivalent inputs;
15. enforce production quality gates.

A one-time successful generated application is not sufficient evidence.

The same application must survive multiple realistic releases.

---

# 47. Final Architectural Directive

Do not build:

> "An MCP that asks AI to write entire applications."

Build:

> **A compiler platform that maintains an executable, versioned, traceable specification of an application, uses deterministic compilation wherever possible, uses AI only for bounded reasoning tasks, understands both desired and existing systems, verifies production behavior, and exposes high-level semantic operations through MCP.**

The canonical semantic model is the core.

Everything else is replaceable around it.

---

# 48. Codex Starting Prompt

Use the following as the initial instruction after placing this document in the repository:

> Read `ACP_CODEX_MASTER_HANDOFF.md` completely and treat it as the current architecture charter. Do not start with ANTLR, MCP tools, or application code generation. Begin with Phase 1: formalize the ACP meta-model and architecture contracts. Create the documentation and minimal repository structure required to make those contracts precise. Record material design choices as ADRs, preserve unresolved items as explicit proposals, and build tests/fixtures for semantic validation as soon as the model becomes executable. Keep the Canonical IR framework-neutral. Before selecting parser or implementation technologies, produce an evidence-based ADR showing how the choice supports the meta-model, compiler stages, diagnostics, deterministic generation, source intelligence, and long-term maintenance. The objective is a production application compiler platform, not a prototype scaffolder.

---

End of Architecture Baseline v0.2.
