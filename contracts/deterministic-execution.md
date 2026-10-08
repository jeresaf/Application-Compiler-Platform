# Deterministic execution successor

Status: **ACCEPTED reference semantics**, explicitly approved on 2026-10-08, including the complete fixture decisions and F-01. [ADR-0016](../docs/adr/0016-deterministic-query-lifecycle-and-rate-semantics.md) defines the meaning; the [approval record](../docs/deterministic-v04-approval-record.md) binds exact reviewed content and plans. Schema titles and stored proposal metadata retain historical wording to preserve reviewed bytes. Target implementation remains incomplete. Phase 6 stays IN PROGRESS. Phase 7 is NOT STARTED.

Separate closed schemas are [Authoring 0.4](authoring-0.4.schema.json), [Canonical 0.3](canonical-0.3.schema.json) and [ChangeSet 0.3](change-0.3.schema.json). The required feature is `acp.deterministic-execution.0.4`. The byte profile remains `acp-jcs-safe-v1`. Existing accepted schemas, vectors, approvals and ADR-0015 are unchanged.

Query `orderBy` is ordered, including exact field revisions, direction and distinct null/absence placement. Paginated queries explicitly end in their complete identity; identity membership is a set, while the authored ordering-key sequence determines precedence. No alternative uniqueness proof language is added. Lifecycle anchors name terminal closing states and successful transaction commit. Anonymization effects are an unordered field-keyed set of REMOVE/NULL/REPLACE constants. Rate algorithms and retry timing are explicit closed records. INTERVAL anchors are explicit UTC instants; LOCAL_DAILY is unchanged.

Inspect a migration without inventing meaning:

```bash
.venv/bin/python3.14 tooling/deterministic_canonical.py test-corpus/execution-v03/payment-authoring.json
```

Exit 1 means REVIEW_REQUIRED and returns no guessed candidate; exit 0 returns an unapproved mechanically convertible candidate; exit 2 means invalid input. All outcomes require fresh exact-content approval before admission. The command never issues approval or writes history. `canonical_ir.py validate` structurally checks the separate planned candidates, and the ordinary authoring validator accepts stored PROPOSED drafts only in draft mode.

Reproduce both historical [reference proposals](../test-corpus/deterministic-v04/README.md) with `python3.14 tooling/deterministic_fixtures.py`. Node independently verifies their actual canonical content hashes. Typed constant `Money<UGX> 1.00` has canonical decimal spelling `"1"`; this is the unchanged canonical numeric spelling rule, not a different amount. The fixture proposal, exact field type and positive invariant remain independently reviewable.

The complete successor adds required IdempotencyPolicy windowAnchor/inFlight, DeliveryPolicy windowAnchor/occurrenceOrder, Job missedOccurrences/catchUp, LegalHold releaseMode and DataClassification redactionScope. Command eventBindings becomes ordered only in this successor, with explicit emissionOrder; Command, Query and UseCase require the closed invocationOrder protocol. Job catchUp is null except for CATCH_UP, which requires a bounded maximum and explicit overflow. Migration reports every missing choice without a candidate. Reference transitions in `tooling/deterministic_invocation.py` test supplied commit/ordering/recovery facts; they are not a durable target implementation. All existing target blockers remain.

The final F-01 extension makes Command failureBindings a required ordered array of exact Failure reference, stage and closed typed trigger. It supports exact workflow, pure predicate, applicable invariant and portable infrastructure conditions with canonical precedence, category/context validation and declaration coverage. Query result/absence semantics remain separate. Target exception names/SQLStates never enter these canonical fields. Migration marks missing failureBindings REVIEW_REQUIRED without inferring from code text.
