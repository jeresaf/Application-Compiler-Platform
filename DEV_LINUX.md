# Ubuntu L490 development

This checkout contains specifications, JSON contracts, a Python validation CLI,
and an independent Node canonical-byte/hash checker. There is no application
server, Docker/Compose stack, external database, environment file, migration or
seed command. No host ports, containers or background services are required.
SQLite is a standard-library reference adapter; tests create temporary databases.
Do not add shared PostgreSQL/MariaDB infrastructure for this harness.

## Setup

Run from the repository root. Use Node 24.21.0 through the existing NVM setup
(`nvm use 24.21.0`), matching CI. Python tooling is CPython 3.14;
CI remains pinned to 3.14.7. This laptop has Ubuntu CPython 3.14.4, which is
validated separately; it does not replace the CI pin or select a production runtime.
All dependency versions in `tooling/requirements.txt` remain unchanged.

Never reuse a Windows virtual environment or bytecode cache. Preserve a copied
`.venv` outside the checkout before creating the Linux environment. Python
regenerates incompatible bytecode automatically; caches are ignored by Git.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r tooling/requirements.txt
.venv/bin/python -m pip check
```

If Ubuntu reports missing `ensurepip`, install `python3.14-venv` with your
administrator account, then repeat setup. Alternatively, bootstrap pip only
inside the isolated environment (the fallback used for this migration):

```bash
python3 -m venv --without-pip .venv
curl -fsS https://bootstrap.pypa.io/get-pip.py -o /tmp/acp-get-pip.py
.venv/bin/python /tmp/acp-get-pip.py
.venv/bin/python -m pip install -r tooling/requirements.txt
```

No activation is required. Do not run global pip installs or change host runtimes.
Dependency installation needs network access; validation is offline afterward.

## Run and test

```bash
.venv/bin/python -m pip check
.venv/bin/python tooling/check_repository.py
.venv/bin/python -m unittest discover -s tooling/tests -v
node tooling/check_canonical_vectors.mjs
.venv/bin/python tooling/validate.py test-corpus/semantic/approved.json --mode compile
.venv/bin/python tooling/canonical_ir.py validate test-corpus/canonical/payment.json
```

The last two commands exercise the real CLIs. Compile eligibility is not
production approval. Commands terminate when complete; there is no service to
start or stop. Rebuild tooling by creating a fresh virtual environment and
installing the same requirements. The suite includes SQLite transactions,
subprocess crash/recovery, concurrency and history persistence tests.

## Migration and rollback

Starting commit: `46e6907c7d2589d1d35bede722c55612cd7cc862`.
Branch: `codex/ubuntu-l490-migration`.
The copied Windows environment referenced `C:\Users\User` and contained
`Scripts/` and `Lib/`; it was preserved at
`/tmp/acp-windows-venv-20261007` (temporary storage, not a durable backup).
The new ignored `.venv` uses Linux binaries. README now includes Linux commands;
`.gitattributes` enforces LF for executable source and shell/CI files.
No semantic contracts, runtime pins, application behavior or stored data changed.

To roll back the tracked migration changes, first preserve any subsequent work,
then switch back to `main` after committing or stashing this branch's edits.
The Linux `.venv` is untracked and independent of branches. Retain it on Ubuntu;
restore the saved Windows environment only on Windows. No Docker volumes or
project data need restoration.

## Laptop verification — 2026-10-07

- Linux x86_64, CPython 3.14.4, Node v24.21.0, SQLite 3.46.1.
- Fresh Linux wheels installed with all six dependency pins unchanged.
- `pip check`, repository checks and `git diff --check`: PASS.
- Full regression: 63 tests passed in 185.821 seconds.
- Independent canonical checker: 9 positive and 13 negative vectors plus
  2 snapshot hashes passed.
- Approved-authoring compile-profile CLI and canonical payment validation: PASS.
  Canonical output correctly reports `authorityVerified: false`.
- Pip reported an unwritable host cache under sandboxing; caching was disabled.
  Installation and dependency consistency succeeded. No host package was installed.
- Docker build/health/volume/resource checks are inapplicable: this project has no
  container services. Container memory/CPU consumption is zero for this workflow;
  native test-process peak memory/CPU was not measured.
- No remaining setup step is required in this checkout. For a fresh setup,
  use the documented isolated pip fallback if the host still lacks `ensurepip`.

Full test log for this run: `/tmp/acp-ubuntu-tests.log` (temporary).
Changes are left uncommitted for review on the migration branch.
