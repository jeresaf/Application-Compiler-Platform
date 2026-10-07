# Phase 6 target contract — implementation in progress

The [profile](../targets/spring-vue-postgres/profile.json) and [ADR](adr/0014-first-production-target.md) describe the first target direction. The worker currently advertises `releaseStatus: INCOMPLETE`. Both complete reference domains fail negotiation on outstanding capabilities. A successful template build is not successful production-target compilation.

## Worker protocol

`acp-target-worker/0.1.0` uses one JSON request and one response per disposable process. Requests have exactly `protocol`, `operation` and `payload`. Responses contain either `ok: true, result` or `ok: false, error`. Duplicate JSON keys, nonfinite numbers, unknown protocol versions, unexpected payload fields and unsupported required capabilities fail closed.

| Operation | Payload |
| --- | --- |
| handshake | `{}` |
| manifest | `{}` |
| negotiate | `nodes`, `required`, `decisions` |
| lower | `nodes`, `required`, `decisions` |
| plan | `model`, `inventory` |
| validate-plan | `artifacts` |

The manifest contains profile, protocol, generator, stack versions, per-family versioned capabilities/constraints, required architecture/design decisions, four ownership classes, migration strategies, evidence labels and resource bounds. Input is limited to 4 MB, output to 16 MB, semantic nodes to 4,000, worker CPU to 20 seconds, host timeout to 30 seconds and address space to 512 MB. Stronger adversarial output supervision remains outstanding.

The host retains snapshot/decision approval and history authority. The worker receives immutable data, not repository credentials or write ports. It starts with a fixed environment; trusted code/profile/templates load before Linux seccomp denies filesystem opens, network creation, process creation, kernel clock/random/identity syscalls and other effects. Pure planning does not read clocks or random values. This prototype is not a completed hostile-plugin security certification; vDSO clock access and startup trust still require explicit hardening assessment.

## Target IR and source layout

Target IR 0.1.0 contains profile/generator/stack, semantic-origin objects, persistence tables/columns, API operations, task screens, design identity and unchanged semantic nodes. Columns record SQL type, semantic type, nullability, optional-update distinction and classification. API operations carry stable paths, method, semantic origin, permission references, structured errors, pagination bounds and optimistic version rules. OpenAPI, backend model and frontend model derive from this IR.

The neutral compiler's optional `target_model` derivative is negotiated through `target.project-artifacts/1`. Its absence preserves Phase 4 serialized identities and synthetic vectors. Multi-artifact plans require complete semantic-origin coverage and exact per-artifact input bindings to contributing semantic objects, target model and generator. Existing synthetic-target one-to-one checks remain active.

Generated roots contain `backend/`, `frontend/`, `database/`, `contracts/` and `acp/`. Deployment packaging is still outstanding. Semantic IDs, rather than display names, drive hashed SQL/API identifiers. Source uses deterministic UTF-8/LF. No generated artifact includes build timestamps. Generator bundle digests bind implementation files in the reference host adapter.

## Capability matrix

The executable manifest is authoritative for current negotiation; retrieve it with `TargetWorker().call("manifest", {})` from [the host adapter](../tooling/target_worker.py). Recognized support is bounded and the release is incomplete.

| Family | Current implementation / limitation |
| --- | --- |
| primitives, Money, entities | SQL lowering and exact-decimal value boundary; broader refined/nested validation remains incomplete |
| relations/cardinality | UNSUPPORTED in negotiation; no silent omission permitted |
| invariants, commands, queries, use cases, workflow | Source templates exist; complete executable conformance and idempotency/rate behavior remain outstanding |
| permissions, policies, tenant scope | Server policy and tenant predicates with unit tests; full authorization and isolation integration suite outstanding |
| authentication/session | UNSUPPORTED canonical assurance/session negotiation until MFA and session semantics are implemented |
| audit/events | Audit/outbox source sites exist; delivery semantics remain UNSUPPORTED |
| task UI | Task/screen forms, selection, errors, permission visibility and accessible hooks; design-role coverage and cross-stack journeys incomplete |
| quality obligations | Metadata retained; trusted production evidence and discharge are not claimed |
| jobs/schedules/retry | UNSUPPORTED |
| files/blob/distributed transactions | UNSUPPORTED |
| privacy/data lifecycle | UNSUPPORTED |

Unsupported families produce deterministic capability errors. The two complete domains cannot be declared supported while these errors remain.

## Ownership and materialization

[FilesystemArtifactStore](../tooling/filesystem_artifacts.py) rejects absolute, traversal, malformed, duplicate and file/directory-colliding paths; symlink roots/ancestors/tree entries; unknown files; missing artifacts; manual edits to managed files; and stale expected digests. It validates the complete plan, stages the complete tree, rechecks originals and publishes by atomic directory exchange on Linux. Failures before publication leave the old tree intact.

| Owner | Regeneration policy |
| --- | --- |
| COMPILER_OWNED | Exact prior-digest CAS; manually edited managed source blocks |
| FRAMEWORK_OWNED | Bootstrap permitted; updates additionally require explicit path-scoped upgrade policy |
| AI_MANAGED | Bound provider/model/input/output provenance and explicit host approval policy/evidence required |
| HUMAN_OWNED | Never overwritten; worker excludes these paths from new plans |

An explicit `adopt_human` handoff is limited to backend/frontend extension paths. Frontend identity and registry files provide extension seams. Backend extension interfaces and broader extension coverage remain outstanding. Generated-source round-trip editing is not promised.

Host-declared ephemeral build scopes may include only `backend/target`, `frontend/node_modules` and `frontend/dist`. They are excluded from source inventory and discarded at regeneration without following contained links. Default policy declares none; unknown paths otherwise block. Concurrent noncooperating filesystem writers and crash/durability cases need further adversarial testing before acceptance.

## Provenance

`acp/provenance.json` binds actual UTF-8 artifact bytes to generator, role, ownership, target-object IDs and exact semantic IDs/revisions. Current maps deliberately claim `ARTIFACT_ONLY`, with no invented symbol or line positions. [Mapping inspection](../tooling/target_provenance.py) returns stale status and no locations after byte/revision changes. General parsing, symbol reconciliation and reanalysis remain Phase 7.

## Migrations

Fresh schemas use Flyway 12.4.0. [The bounded upgrade planner](../tooling/target_migrations.py) checks exact Phase 3 plan digest, previous/current snapshots, accepted-history lookup and independently approved backfill bindings. Stable-ID display renames emit no DDL. Optional fields expand safely; required supported fields expand, apply explicit backfill, verify preconditions and switch to NOT NULL. It never invents a required-field value. Destructive changes and unsupported structural transformations block, including otherwise accepted semantic changes. No production rollback is claimed.

This planner is not yet connected to the complete six-step target pipeline. Relationship upgrades, new-table upgrades, constraint/security evolution, accepted-history production adapter and reviewed destructive contract artifacts remain outstanding.

## Reproduction and evidence

Run `.venv/bin/python3.14 -m unittest discover -s tooling/tests -p test_phase6_foundations.py -v` and the equivalent `test_target_migrations.py` suite. Existing validation remains `python3.14 -m unittest discover -s tooling/tests -v`, repository checks and independent Node vectors.

Generated frontend inputs include an npm lockfile with exact release/integrity values. Maven uses exact direct dependencies, plugins and Boot BOM; a complete transitively verified dependency inventory/lock and license provenance remains outstanding. Template Maven tests require an explicit ephemeral PostgreSQL 18.6 connection using `ACP_TEST_DATABASE_URL`, `ACP_TEST_DATABASE_USER` and `ACP_TEST_DATABASE_PASSWORD`. They fail rather than skip when the database is absent. Production configuration uses separate opaque `ACP_DATABASE_*` and `ACP_OIDC_*` handles, with no generated secret defaults.

Local `/tmp/acp-phase6-build` fixtures were produced directly from pure lowering to test templates while negotiation still rejects complete domains. They are ephemeral, unnegotiated test fixtures and cannot be promoted to Phase 6 completion evidence. See the [status report](phase6-completion-report.md).

The unnegotiated template checks are reproducible with `python3.14 targets/spring-vue-postgres/check_templates.py --output /tmp/acp-phase6-templates-new --acknowledge-unnegotiated-templates --run-builds`, after supplying the three test-database environment handles. The output directory must not exist. The report always records `phase6: NOT_CLOSED` and the complete-domain admission errors, even if template builds pass.
