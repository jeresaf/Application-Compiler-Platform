# R3 synthetic case intake

This increment adds a reusable creation executor and Vue form to the existing
Spring/Vue/PostgreSQL target planner. It is a **synthetic engineering preview**,
not an accepted Case Management semantic transition or deployment authorization.
The sealed 0.5.0 release and historical 0.6.0 candidate remain unchanged.

## Semantic boundary

Canonical 0.3 Command operates on an existing resource. Its validator forbids
assigning immutable identity/tenant fields; the closed task UI requires an existing
selected resource. There is no approved create Command or intake UseCase.

`proposals/phase10-r3-intake/` contains an exact native requirements-only ChangeSet,
its planned candidate, the explicitly synthetic creation contract, and an approval
request. The native plan's BACKWARD/no-migration classification describes adding
requirements only; it does not establish compatibility or approval of creation.
A project-authority decision must authorize a versioned CREATE execution/UI
protocol and exact Command, UseCase, Permission/Policy, identity, input, state,
event/failure and concurrency semantics before accepted adoption. No Canonical
schema is changed, no signature or journal acceptance is issued, and R2's retained
population and authorization package are untouched.

The separately fingerprinted `acp-intake-synthetic-generator/1` composes the existing
0.6.0 pure target, native ArtifactPlan adaptation and CAS. It does not replace the
compiler or register a production target. The closed synthetic contract lowers
String inputs, singleton String value objects, authenticated tenant/self-assignee,
generated identity and the declared initial state into parameterized INSERT SQL.
Missing fields, unsupported types, inconsistent ownership, unknown contracts and
arbitrary operations reject. Optional fields are explicitly absent; no backfill
value becomes a creation default. Input constraints are proposed, not approved.

The generic generated controller reuses ApplicationPolicy.actor/SessionGate,
InvocationCore's durable fencing/replay transaction and ExecutionStore audit and
classification audit. Its separate synthetic role check is not an accepted create
permission. Principal/tenant existence is verified before creation. Unknown request
fields cannot supply tenant, assignee or identity. The endpoint defaults off and
requires both `acp.intake.mode=synthetic-preview` and development runtime mode.
No test credentials are generated into production source.

## Reproduce

Use existing pinned dependencies and an isolated SDK/compiler environment:

```bash
python3.14 -B -m unittest verification.reference_application.test_intake -v
python3.14 -B -m engineering.reference_application.intake_run \
  --workspace /tmp/acp-r3-intake \
  --maven-seed /absolute/retained/m2 --npm-seed /absolute/retained/npm \
  --browser-seed /absolute/retained/browsers --offline
```

The execution directory must not exist. Ports 18081/4174 must be unused. Inputs,
outputs and evidence stay inside the inventoried execution directory and its
private `-inputs` sibling. Dependency provisioning requires operator permission.
Maven artifacts are hash-verified and used offline; npm uses its existing lock;
no system packages are installed. Only a newly allocated PostgreSQL 18.6 container
and localhost services are used, and owned processes/container are cleaned up.
The run produces generated source, consumed build hashes, candidate/TargetIR/
ArtifactPlan, screenshots, browser results, database rows/dump/history and replay
observations. It does not rerun historical physical qualification.

The browser creates a case through the generated form/API, then executes the
existing review → approve → archive flow. Fixtures provision tenants/users only;
the test asserts there is no case before browser creation. It verifies invalid
inputs, unknown fields, unauthorized/wrong-tenant/expired tokens, replay and payload
conflicts, audit, idempotency, a fresh JVM and durable revocation.

Native Phase 7 Java/TypeScript adapters analyze actual candidate sources. Facts
are bound to the candidate digest, generator, ArtifactPlan and exact source hashes.
They are not relabeled an admitted original-reference Source Model. Vue bodies
remain unsupported. Phase 8's existing result format reports preview execution
separately from BLOCKED candidate admission and NOT_RUN accepted transition. The
existing MCP Application rejects this candidate rather than attaching its mappings
to the historical approved identity; that fail-closed boundary has a regression.
No security finding is cleared and no original verification PASS is transferred.

Source ownership/provenance is checked before and after execution. Intake mappings
include the proposed requirement/criterion. Shared unchanged infrastructure keeps
its applicable original origins; every artifact also binds the complete TargetIR.
This avoids falsely attributing all shared code to intake and stays within the
existing 1 MiB compiler fingerprint limit without removing tests or raising limits.

Phase 10 remains IN_PROGRESS; Phases 11–12 are not started. Operational security
is NOT_ESTABLISHED. PHASE6_CLOSURE_BLOCKED; PHASE6_RELEASE_CLOSURE_BLOCKED.
