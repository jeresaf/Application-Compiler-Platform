# ADR-0008: Explicit bounded execution contracts (P-03)

Status: ACCEPTED. Date: 2026-09-16. Supersedes P-03 in ADR-0005.

## Decision

Promote Service, Query, UseCase, ExecutionStep, Transaction, Failure, RetryPolicy, IdempotencyPolicy, DeliveryPolicy, Schedule and Job. Each inherits shared semantic identity, lifecycle, stewardship, origins, basis and exact references. Services are logical ownership boundaries. Queries are read-only typed projections. UseCase steps are explicitly ordered durable nodes; steps cannot belong to two use cases. Cross-service orchestration requires explicit steps; recursive use-case invocation is rejected.

Commands name one aggregate, its root and an explicit write set. Transactions contain commands from one aggregate and require rollback on failure. Cross-aggregate coordination uses ordered steps and explicit compensating commands, never an implicit distributed transaction. Compensation is a business operation, not time reversal. Compensation commands must share resource and declared service ownership; cycles are rejected.

Failures distinguish BUSINESS, TRANSIENT and SECURITY. Only declared retryable TRANSIENT failures may enter bounded retry policies. Idempotency specifies key type/scope, replay behavior, conflicting-input rejection and retention window. Retry horizons must fit that window. Events declare AT_MOST_ONCE or AT_LEAST_ONCE delivery; the latter requires deduplication retained for the delivery window. Exactly-once transport claims are rejected.

Schedules support fixed elapsed intervals or daily local times. Local schedules pin an IANA timezone database version and declare gap SKIP/REJECT and overlap EARLIER/LATER/REJECT. This is schedule meaning, not a cron/library format. The harness uses pinned tzdata with Python's [zoneinfo](https://docs.python.org/3/library/zoneinfo.html); no ambient OS timezone database is used. [tzdata](https://pypi.org/project/tzdata/) is development reference data only, under ADR-0003's replaceable harness boundary.

## Alternatives and consequences

Implicit service calls and generic scripts conceal side effects, failure and consistency boundaries. The explicit bounded model is more verbose but can be validated without selecting an execution framework. General orchestration DAGs, distributed atomic transactions, arbitrary calendar schedules, live worker execution and delivery implementation are deferred. These do not block representing the accepted ordered/failure/consistency semantics in a future IR.
