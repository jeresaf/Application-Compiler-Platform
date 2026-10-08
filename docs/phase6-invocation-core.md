# Phase 6 invocation-core tranche

Phase 6 is IN PROGRESS. Phase 7 is NOT STARTED. This tranche does not close Phase 6 or establish complete target acceptance.

## Approval and exact input

ADR-0016 is ACCEPTED, Authoring 0.4 reference semantics and Canonical 0.3 reference snapshots are APPROVED, and ChangeSet 0.3 is GREEN for bounded reference evolution. The [dated human approval](deterministic-v04-approval-record.md) is subsequent to the historical proposal evidence. Its reviewed bytes, plans, AI provenance, schemas and approval record remain unchanged.

| Domain | Exact Canonical 0.3 digest |
| --- | --- |
| Payment | `sha256:d0f6e8d96a07e8e8358ad8f1f558f9ec3d69fd8008cceb75e82f4f695e3cf47d` |
| Case management | `sha256:5b3a69bb1d6e0e69ed620cd1dd32d10e8a07cec276583055b53ec03bfdcc6b90` |

`deterministic_approval.approved_snapshot` checks the exact proof, source, plan, content and asset bindings before the compiler receives authority. Internal structural authoring witnesses never create new human attestations. Semantic changes require fresh approval; target implementation never regenerates different fixture meaning.

## Version compatibility

The worker explicitly accepts Canonical 0.3 / semantic model 0.4 / `acp.deterministic-execution.0.4`. The compiler has a distinct structured frontend identity for that semantic version. Canonical 0.2 / semantic model 0.3 / `acp.execution.0.3` retains its legacy constraints and exact blocker behavior. Neither path reinterprets the other version's nodes.

Node capability suffix `/0.2.0` identifies the existing node-kind interface; it is not a Canonical schema version. The manifest separately declares exact Canonical/model/feature compatibility and version-specific constraints. Legacy capability negotiation retains its own declarations.

## Implemented profile

Query compiles authored key precedence, direction, null placement, absence placement and explicit identity suffix. String/Identifier order uses PostgreSQL UTF-8 `bytea` lexicographic comparison, which follows Unicode scalar order including supplementary scalars and U+0000, independent of text collation. Other ordered types, including nominal wrappers, reject negotiation in this initial subset. Pagination is offset-based under per-request READ COMMITTED; inserts can shift later offsets, and no snapshot isolation across pages is claimed.

Command Failure execution uses exact binding identity and authored stage order. Workflow applicability comes from actual pre-state and guards. PRE_STATE and POST_ASSIGNMENT predicates compile supported typed expressions; post predicates see staged values. Bound WRITE invariants produce their exact Failure; unbound invariants retain their existing outcome. Assignments, transition, output, event staging and successful idempotency results roll back together. STOP prevents later steps. The target accepts one aggregate instance and one atomic boundary; multi-commit and distributed coordination reject negotiation.

Provider classification remains separate from canonical binding. Exact reviewed SQL classes/states are classified through the existing mapper; only exact JDBC adapter wrapper classes `UncategorizedSQLException`, `CannotGetJdbcConnectionException` and `DataAccessResourceFailureException` expose their provider cause to that classifier. Arbitrary wrappers, subclasses and unknown faults remain INTERNAL. This tranche supports declared DEPENDENCY_UNAVAILABLE bindings only; other declared infrastructure-class subsets reject negotiation. Unbound SERIALIZATION_CONFLICT and TIMEOUT cannot become the fixtures' FAIL-TRANSIENT. Message text never selects a class or Failure.

Failure HTTP profile **1.0.0** returns exactly failureId, failureRevision, code, category, retryable, operationId, operationRevision and opaque correlationId, with header `ACP-Failure-Profile: 1.0.0`. BUSINESS maps to 422, SECURITY to 403, TRANSIENT to 503. No raw input/resource values, SQL messages, secrets or traces enter the envelope. Platform invocation outcomes have no manufactured Failure identity: RATE_DENIED is 429, IN_PROGRESS is 202, IDEMPOTENCY_CONFLICT is 409, and IDEMPOTENCY_KEY_REQUIRED is 400. Invalid/missing typed JSON members fail codec validation with 422. Unknown platform faults remain 500.

RatePolicy implements TOKEN_BUCKET / CONTINUOUS_RATIONAL / FULL / AUTHORIZED_INVOCATION / CHARGE / NONDECREASING using integer token units with denominator `windowSeconds × 1,000,000,000`. PostgreSQL numeric state and row locks serialize admissions. ACTOR partitions include policy ID/revision, tenant and actor; TENANT partitions omit the actor. One policy per operation and positive signed-32-bit policy bounds are supported. Unauthorized calls create no rate state. Denials consume no token. Later semantic failure, conflicts and successful replay remain charged; retries retain one logical invocation. Later STOP steps are neither executed nor charged.

Idempotency uses durable policy ID/revision, tenant, resource identity, operation ID/revision and typed String key, plus exact normalized typed input digest with ACP canonical domain separation. Required String/Identifier input fields are supported first; other forms reject negotiation. Keys travel as JSON `idempotencyKey`, preserving semantic Strings including U+0000. Property source order never changes input identity. The generated atomic STOP UseCase subset has unique Command occurrences and precomputable input-only result dataflow; unsupported coordination/dataflow rejects negotiation.

Reservations commit separately as IN_FLIGHT; owner fences protect semantic execution. The domain transaction commits effects, transition, typed per-Command results and staged event occurrences with COMMITTED_RESULT records and the original PostgreSQL transaction identity. Rate and idempotency admission use one supplied instant per logical operation. Replay uses PostgreSQL's authoritative commit timestamp, never arrival or worker completion. Its window is half-open and expires at the exact deadline. Actual commit facts can be cached durably after proof; wrapped/aged transaction IDs without proof cannot supply a guessed timestamp. `track_commit_timestamp=on` is required and checked. Proven database rollback permits clearing a claim; committed results survive restart; unknown/missing facts remain IN_PROGRESS without a lease expiry. Availability is sacrificed when proof is unavailable.

RetryPolicy uses INCLUDING_INITIAL, AFTER_FAILURE_COMPLETION and NONE jitter. Only an exact trusted bound TRANSIENT/retryable occurrence referenced by the selected policy qualifies. Delays are capped integer multiplication after rollback/failure completion, with an injected clock/sleeper in tests. Operation, resource, input, key and reservation identity persist across attempts. A trusted operation caller explicitly selects a policy; the canonical fixtures attach RETRY-TASK to the still-unsupported Job, so HTTP operations do not silently inherit that association. Job occurrence handling remains outside this tranche.

## Evidence and remaining blockers

The generated PostgreSQL and real Spring HTTP harness covers Unicode/case/supplementary ordering, equal leading keys, null/absence placement, repeated pages and intervening inserts; exact workflow identities and staged/bound invariant failure; real server-raised dependency faults, rollback and retry; concurrent rate capacity/refill; in-flight same/different input, durable replay, half-open expiry, connection termination and proof-based recovery. Test-only semantic variants exercise lowering; they never acquire fixture authority.

The [successor blocker contract](../targets/spring-vue-postgres/expected-open-blockers-v2.json) was derived from actual full compiler/worker negotiation, then checked by the expected-open gate. Strict mode fails while any blockers remain. The old contract and reports are preserved historically. Current actual remaining blockers per application:

- Action
- DataClassification
- DataLifecycle
- DeletionPolicy
- DeliveryPolicy
- Filter
- Form
- InputControl
- Job
- LegalHold
- PermissionBoundary
- Retention
- Schedule
- Screen
- Search
- Table
- ViewState
- Wizard
- WizardStep

All eleven UI families stay blocked. Transactional event staging is not transport delivery. Scheduling, lifecycle/disposal, production IdP/TLS, encryption and transport availability remain later gates. Local `/tmp` logs are ephemeral; checked-in machine-readable summaries and hosted artifacts carry durable evidence.

Local invocation validation passed on Linux with CPython 3.14.4, Node 24.21.0, Java 21 and PostgreSQL 18.6: Payment 32 generated Java tests and Case management 33, with zero failures, errors or skips. Both generated frontends passed lock installation, type checks, four tests and production builds. The [machine-readable component report](../targets/spring-vue-postgres/evidence/invocation-components-linux.json) records individual test cases and actual environment versions.

The focused target/compatibility regression rerun passed all 29 tests. Independent Node checks passed all three canonical corpora (each nine positive vectors, thirteen negative vectors and two snapshot hashes), with unchanged approved bytes/hashes. Dependency consistency and repository checks passed. The complete Python suite is also a required hosted workflow gate; the [invocation branch workflow](https://github.com/jeresaf/Application-Compiler-Platform/actions/workflows/acp-contracts.yml?query=branch%3Acodex%2Fphase6-invocation-core) preserves its logs and generated PostgreSQL/HTTP evidence. Hosted CI must be green before this tranche is merged; component success does not waive strict admission.
