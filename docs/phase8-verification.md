# Phase 8 — bounded verification integration

## Phase 7 acceptance recommendation

The charter's Phase 7 exit list requires native analyzers, a symbol graph,
references, ownership and drift. The first increment demonstrates these against
both generated references, with native overload/alias resolution, exact provenance,
human extensions, impact and deterministic drift checks. All 26 tests passed in
[run 41081168320](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/41081168320)
for `8b351ce75ca44da2bf7516414ff4e94c645563f9`.

Recommend **bounded engineering acceptance**. Formal phase closure still needs the
required approval; this recommendation is not that approval. Vue SFC/CSS semantics,
dynamic dispatch/reflection, full ecosystem coverage and comprehensive affected-test
selection remain unsupported. These do not prevent the original bounded source
index gate from being met. Source Models retain UNKNOWN completeness; semantic-ID
carriers do not prove business implementation or runtime coverage. The original
Phase 7 report and accepted evidence remain unchanged.

## Working integration

The original eight-stage compiler reproduces the approved Canonical snapshot,
Target IR, ArtifactPlan and unchanged generated artifacts. The existing Phase 7
native Source Model is ingested with exact file/baseline hashes. The integration
executes `SuccessorCandidate.verify_materialized`, the same offline provenance and
ownership predicate used by Phase 6 qualification, for the generator-declared
`target-source-integrity` obligations. It also reuses Source Intelligence's current
source/configuration/ownership checks. No second compiler, generator or audit
registry is introduced.

`acp-verification-result/1` binds Canonical, compiler, pipeline, unsealed generator,
Target IR, ArtifactPlan, Source Model and verifier code digests. Each declared
artifact check and every original compiler semantic obligation is retained with
exact semantic ID/revision and artifact relationships. Known native symbol carriers
are linked without upgrading historical ARTIFACT_ONLY confidence.

- PASS: an applicable existing offline predicate actually succeeded on current inputs.
- FAIL: the invoked existing integrity predicate failed.
- BLOCKED: stale/mismatched inputs, incomplete source coverage or missing operational evidence.
- NOT_RUN: the executor was not run, or no behavioral result is bound to a semantic obligation.

Summary counts describe verification rows, not the 39 Phase 6 release criteria.
Artifact PASS never discharges a behavioral obligation. All original compiler
obligations remain OUTSTANDING in their original plans. Runtime authorization,
builds, migrations, E2E, security, performance and manual/operational acceptance are
not inferred from source integrity. Existing deployment requirements remain BLOCKED.
Full source traceability is BLOCKED while the Source Model is partial.

The `EvidenceExecutor` logical port returns a compact hash-bound descriptor to the
full result file, preserving its existing Document byte limit. Its operation is
closed; clients cannot supply commands. This increment runs trusted read-only host
checks, not untrusted application workloads. It establishes no sandbox, execution
authentication, release admission or production authority.

Retained local results are verified by checking their complete identities and
independently rerunning the existing predicates. Deleting results or manufacturing
PASS labels fails comparison. A checksum alone is not authenticated execution.
Results are deterministic for the same inputs and verifier code; run source commit
and archive identity are recorded separately in execution-owner.json.

## Reproduce

Activate the existing Python 3.14 environment. No host dependency installation,
databases, application builds or repeated Phase 7 suites are required.

```bash
python3.14 engineering/verification/qualification.py \
  --workspace /tmp/acp-phase8-verification \
  --phase7-archive /path/to/phase7-source-intelligence.zip \
  --execution-evidence /path/to/hosted-execution-archives \
  --evaluated-at "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

The qualification now includes 30 tests; an authenticated `gh` session with
repository Actions-read access is required for live execution provenance.
The original accepted archive is artifact `12988799586` from run `41081168320`,
SHA-256 `55ae6a899cd429628563fe3c65e035038c4f9d32d595305f16253f93325e07fe`.
It supplies the actual native models and original bindings; its source commit,
test counts, member inventory and hashes are checked. The CLI creates fresh owned
reference applications. For faster local checks, `--reuse-applications <prepared
Phase7 workspace>` copies only generated applications into disposable test storage;
the original evidence and applications are not mutated. No Git clone is created.
GitHub provisions only the existing pinned Python harness and retrieves the same
archive, then generates both applications afresh. It never reruns the Phase 7 suite.
The archived input must remain available: GitHub retention expires 2027-01-28;
a preserved byte-identical local copy continues to work. Missing/substituted inputs
fail closed, with no reconstructed replacement.

For an existing generated root, use `engineering/verification/cli.py run` with
`--root`, `--baseline`, `--baseline-sha256`, `--source-model`,
`--source-model-sha256` and `--output`. `verify-retained` additionally takes
`--retained` and `--retained-sha256` and independently rechecks its observations.
Outputs must be outside application source and cannot overwrite existing files.
Keep execution evidence before removing disposable workspaces.

Phase 8 is IN_PROGRESS. The next original roadmap deliverable remains the rest of
Phase 8: integrate independently bound build/runtime/migration/security results
through existing executors before exposing mature operations in Phase 9 MCP.
Phases 9–12 are NOT_STARTED. Phase 6 retains all 21 release blockers and its 39
unchanged predicates. Sealed 0.5.0 and unsealed 0.6.0 identities are unchanged.
Operational security is NOT_ESTABLISHED; production release is NOT_AUTHORIZED.

## Execution-evidence extension

The existing integration consumes the actual demonstration, recovery and security
artifacts from [qualified baseline run 41098093388](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/41098093388)
at `9fd0fe07249fc1b23e9850175c478d303e1e06c8`. It does not rebuild applications or
start PostgreSQL merely to ingest these results. GitHub's authenticated API must
independently confirm repository, source commit, completed run/job/step and exact
artifact digest. A local checksum or a JSON field claiming authenticated authority
cannot replace those checks. API unavailability blocks reuse rather than upgrading
local observations to authenticated hosted evidence.

The exact producing executor and dependency-lock closure is compared with the
pinned source commit. The demonstration also binds the original compiler audits,
ArtifactPlan and every generated file to the current Source Model. Recovery's
existing test compiler has different provenance labels; its own Target IR and
ArtifactPlan are reconstructed with that existing compiler. Admission is scoped
to exact equality of the executable target model and all backend, migration and
UI-model bytes. The producer identities remain distinct from the consumer's
identities; semantic similarity is insufficient. Package-readiness JUnit and
scanner evidence retain their own producing context and immutable packaged
library inventory.

Real results cover backend build/readiness tests, frontend type checking/tests/
build, API startup, disposable issuer/JWKS/PKCE authentication, browser journeys,
PostgreSQL migration history, committed-state restart, idempotency/audit, the
existing 15-case migration/crash recovery matrix and bounded dependency scanning.
Reported vulnerabilities, unknown identities and incomplete coverage remain FAIL
or BLOCKED; a successful scanner job does not mean a clean assessment. Existing
recovery and replay-state assertion evaluators are reused. Missing family results,
retries, skips, conflicting reports and substituted inputs fail closed.

Only the existing Phase 6 assertion-to-object mapping for `BOUNDARY-TASK` can
promote its exact semantic obligation, with the actual two browser permission/
forged-call/tenant scenarios and unchanged assertion source. Builds and runtime
health do not discharge business acceptance, policy, backup, accessibility or
production requirements. Partial Vue/CSS analysis does not block independently
verified backend/recovery execution; full source traceability remains BLOCKED.
Historical Phase 6 engineering qualifications are not revoked by NOT_RUN here:
that status means no complete result is bound by this invocation.

Freshness uses the applicable reference specification's existing EvidenceRequirement
maximum age and an explicit UTC evaluation instant, both retained in the report.
Identical inputs, authority observations and evaluation instant produce identical
results. A historical evaluation is not a claim of present freshness. Expired
results require fresh execution evidence, not a relaxed threshold.

For existing-root CLI calls, add `--execution-evidence` and `--evaluated-at` to
`run` or `verify-retained`. Archive filenames are `demonstration.zip`, `recovery.zip`
and `security.zip`; exact service artifact IDs/digests are pinned by the adapter.
No second runner, witness registry, signing authority or release profile is created.
The user-approved append-only custody destination is
`/home/aiko-jerry/ACP-Evidence-Vault/phase8-execution-evidence-20261030/`.
Preserved observations document custody, not human signatures or operational trust.
