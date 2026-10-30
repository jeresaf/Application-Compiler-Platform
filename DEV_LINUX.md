# Linux development baseline

Linux is the supported ACP development and CI host platform. Hosted CI uses
Ubuntu 24.04 in `.github/workflows/acp-contracts.yml`. This is an engineering
environment decision only: ACP semantics, Canonical IR, change model, compiler
contracts and generated targets remain target-neutral.

The repository includes the compiler, the sealed 0.5.0 target, and an unsealed
0.6.0 successor. The internal demonstration below compiles the two exact approved
reference snapshots through all eight compiler stages, materializes their artifact
plans, builds the generated applications and uses disposable PostgreSQL/browser
infrastructure. It is candidate qualification, not production deployment.

## Setup

Run from the repository root. CPython 3.14.7 and Node.js 24.21.0 are pinned in CI
as test tooling, not production runtime selections. Use the existing NVM setup
(`nvm use 24.21.0`) for Node. This Ubuntu 26.04.1 laptop currently has CPython 3.14.4;
local results record that patch version separately from the unchanged CI pin.
Dependency versions remain pinned in `tooling/requirements.txt`.

If virtual environment creation reports missing `ensurepip`, install the matching
Ubuntu package using your administrator account, then repeat setup:

```bash
sudo apt-get install python3.14-venv
```

Keep all Python dependency installation isolated inside the ignored `.venv`:

```bash
python3.14 -m venv .venv
.venv/bin/python3.14 -m pip install -r tooling/requirements.txt
.venv/bin/python3.14 -m pip check
```

No activation or global pip installation is required. Do not reuse virtual
environments copied from another OS. To rebuild tooling, preserve any existing
local environment you need, create a fresh `.venv`, and install the same pinned
requirements. Dependency installation needs network access; validation is offline
afterward. Python bytecode caches are ignored by Git.

## Run and test

```bash
.venv/bin/python3.14 -m pip check
.venv/bin/python3.14 tooling/check_repository.py
.venv/bin/python3.14 -m unittest discover -s tooling/tests -v
node tooling/check_canonical_vectors.mjs
.venv/bin/python3.14 tooling/validate.py test-corpus/semantic/approved.json --mode compile
.venv/bin/python3.14 tooling/canonical_ir.py validate test-corpus/canonical/payment.json
```

The first four commands are also required CI gates. The full suite includes all
Phase 1–3 contracts, SQLite transactions, subprocess crash/recovery, concurrency,
approval, provenance and two-domain evolution tests. The last two commands
exercise the real CLIs; compile eligibility is not production approval.
These validation commands terminate when complete. The optional demonstration below starts controlled disposable services.

## Evidence and phase boundaries

Phase 1, Phase 2, Phase 3 and Phase 4 are CLOSED AND GREEN. Phase 5 is CLOSED AND GREEN at bounded evaluation scope. Worker/source-analysis architectures are ACCEPTED; core runtime/frontend remain DEFERRED; Xtext production use is REJECTED on provenance. [experiment commands](experiments/phase5/COMMANDS.md) and the [evaluation report](docs/phase5-completion-report.md) record the decisions, raw evidence and limitations. Phase 6 is IN_PROGRESS with formal release closure BLOCKED; Phase 7 is IN_PROGRESS under the separately authorized Source Intelligence increment.
The [Phase 4 report](docs/phase4-completion-report.md) records the historical 92-test
local Linux regression and green Ubuntu 24.04 CI evidence.
Their completion reports are historical records, including Windows results that
actually occurred; this environment cleanup does not rewrite them. Future phase
reports use Linux evidence unless another environment is deliberately added.
Canonical byte/hash vectors and semantic/compiler contracts are unchanged.

The earlier Ubuntu migration run on 2026-10-07 passed 63 tests in 185.821 seconds
with CPython 3.14.4, Node v24.21.0 and SQLite 3.46.1. Independent canonical checks
passed 9 positive vectors, 13 negative vectors and 2 snapshot hashes. That run also
passed dependency, repository and validation CLI checks.

Any logs under `/tmp`, including `/tmp/acp-ubuntu-tests.log`, are ephemeral local
evidence, not durable or hosted CI records. Use GitHub Actions run links for hosted
CI evidence. The demonstration creates owned disposable containers without persistent Docker volumes.

## Generated reference applications

Use this existing checkout, Java 21, Maven 3.10.0, Node 24.21.0 and Docker.
Do not create another permanent ACP clone or reuse an existing database.
The runner acquires exact content-locked Maven dependencies and the generated
frontend's locked npm dependencies and Chromium into its private input directory.
It does not install host packages. Obtain the exact database image once:

```bash
docker pull postgres@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336
```

Choose a fresh ignored execution directory for each invocation. From the repository
root, the automated two-domain demonstration is:

```bash
.venv/bin/python3.14 -B engineering/demo/reference.py qualify --workspace "$PWD/.audit-artifacts/reference-demo"
```

The runner records compiler-stage audits, actual production package inventories,
backend/frontend build logs, browser results, screenshots, committed database rows,
fresh JVM identities, restart/replay checks and cleanup evidence. It retains the
explicit HUMAN-owned test identity extension across regeneration. Separate OIDC
browser tests validate signed disposable identity; trusted-JWT component fixtures
do not establish production cryptographic identity or deployment acceptance.

For an interactive session, use a different fresh directory and either domain:

```bash
.venv/bin/python3.14 -B engineering/demo/reference.py serve --domain payment --workspace "$PWD/.audit-artifacts/payment-demo"
.venv/bin/python3.14 -B engineering/demo/reference.py serve --domain case-management --workspace "$PWD/.audit-artifacts/case-demo"
```

Payment uses frontend `http://127.0.0.1:4173` and backend
`http://127.0.0.1:18080`; Case Management uses ports 4174 and 18081.
The runner prints its exact newly owned container and schema. The generated UI
lists the fixture resource; select it, edit the summary, and confirm the workflow.
Enter `r` in the runner terminal to restart the backend against the same disposable
database. Enter `q` to stop. The runner reaps its processes and removes its database.
Logs and generated files remain in the chosen workspace. Inspect database state
only in the exact container printed by that invocation, for example:

```bash
docker exec CONTAINER_PRINTED_BY_RUNNER psql -U acp_runtime -d acp_runtime -c 'SELECT * FROM acp_browser_payment.acp_audit;'
```

Replace the schema with `acp_browser_case_management` for Case Management.
These are synthetic test identities and tenant rows, not deployment credentials.
Do not expose the loopback services. Preserve required results in ACP-Evidence-Vault
under its custody procedure before removing execution directories or private input
caches; do not delete historical evidence or resources belonging to other runs.

The candidate uses Tomcat 11.0.26 with exact Maven input lock SHA-256
`6afefcd376cf8229962d63305d6ff9b9530dd7c32013e1d4f1d14ddd34c0db9e`.
The sealed 0.5.0 release, historical qualifications and 39 closure predicates remain
unchanged. In-process hostile-code confinement, clock secrecy, operational OIDC,
TLS, transport, key custody and formal acceptance remain separate obligations.
Phase 6 release closure remains BLOCKED.

Security assessment checked 2026-10-30: the authorized 11.0.26 patch is not a
claim of a vulnerability-free runtime. Apache lists additional 11.0.26 findings
fixed in 11.0.27, including CVE-2026-103119 (AJP), CVE-2026-101356 (HTTP/2 async)
and CVE-2026-101296 (JNDIRealm). See
[Apache's current advisories](https://tomcat.apache.org/security-11.html).
No unrelated upgrade or risk acceptance is implied. Previously unresolved build-tool
findings remain unresolved; this demonstration does not replace authenticated
release-scoped vulnerability assessment or operational acceptance.

## Source Intelligence

The first Phase 7 increment analyzes both generated references through native javac
and TypeScript semantics. See the [verified CLI and focused qualification commands](docs/phase7-source-intelligence.md).
It preserves human-owned extensions and reports partial completeness, exact source
identity, impact and drift. It does not change Canonical semantics or release authority.
Phase 8 is separately authorized and IN_PROGRESS; Phases 9–12 remain NOT_STARTED.
Operational security is NOT_ESTABLISHED.

## Verification integration

The [Phase 8 runbook](docs/phase8-verification.md) documents the exact accepted
Phase 7 archive input, reproducible qualification and existing-root CLI.
It executes existing offline artifact/provenance checks and leaves missing behavior
results NOT_RUN and operational requirements BLOCKED. It does not grant release approval.
