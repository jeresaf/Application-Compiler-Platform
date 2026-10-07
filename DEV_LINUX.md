# Linux development baseline

Linux is the supported ACP development and CI host platform. Hosted CI uses
Ubuntu 24.04 in `.github/workflows/acp-contracts.yml`. This is an engineering
environment decision only: ACP semantics, Canonical IR, change model, compiler
contracts and generated targets remain target-neutral.

This checkout contains specifications, JSON contracts, a Python validation CLI,
and an independent Node canonical-byte/hash checker. No application server,
Docker stack, external database, environment file, host ports or background
services are required. SQLite is a standard-library reference adapter; tests
create temporary databases.

## Setup

Run from the repository root. CPython 3.14.7 and Node.js 24.21.0 are pinned in CI
as test tooling, not production runtime selections. Use the existing NVM setup
(`nvm use 24.21.0`) for Node. This Ubuntu laptop currently has CPython 3.14.4;
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
Commands terminate when complete; there is no service to start or stop.

## Evidence and phase boundaries

Phase 1, Phase 2, Phase 3 and Phase 4 are CLOSED AND GREEN. Phase 5 is CLOSED AND GREEN at bounded evaluation scope. Worker/source-analysis architectures are ACCEPTED; core runtime/frontend remain DEFERRED; Xtext production use is REJECTED on provenance. [experiment commands](experiments/phase5/COMMANDS.md) and the [evaluation report](docs/phase5-completion-report.md) record the decisions, raw evidence and limitations. Phase 6 is NOT STARTED.
The [Phase 4 report](docs/phase4-completion-report.md) records the current 92-test
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
CI evidence. No container resources or persistent Docker volumes are involved.
