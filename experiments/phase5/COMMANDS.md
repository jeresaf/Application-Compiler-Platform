# Reproduce the Phase 5 experiments on Linux

These commands run from the repository root. Use the existing isolated `.venv`
with `tooling/requirements.txt`, Node 24.21.0, Java 21 and Maven. Hosted CI pins
Python 3.14.7; the laptop's measured reference harness uses 3.14.4. Production
semantics and generated targets remain host-neutral. Do not install Python
dependencies into the system interpreter.

## Resolve and build

```sh
npm --prefix experiments/phase5/langium ci --ignore-scripts --no-audit --no-fund
mvn -B -ntp -f experiments/phase5/xtext/pom.xml \
  -Dmaven.repo.local="$PWD/experiments/phase5/.cache/m2" \
  dependency:build-classpath -Dmdep.outputFile=target/classpath.txt
.venv/bin/python3.14 experiments/phase5/setup.py
.venv/bin/python3.14 experiments/phase5/generate.py
.venv/bin/python3.14 experiments/phase5/build.py antlr
.venv/bin/python3.14 experiments/phase5/build.py xtext
npm --prefix experiments/phase5/langium run generate
npm --prefix experiments/phase5/langium run build
mkdir -p experiments/phase5/core-runtime/out
```

The two generator downloads are digest-pinned in `versions.json`; generated code,
tools and dependency caches are ignored. Maven's resolved artifact/digest inventory
is in `results/inventory.json`; unresolved inherited licenses remain explicit.
The complete npm and Cargo dependency locks are checked in. Maven is not claimed
to provide equivalent transitive locking or an air-gapped supply-chain proof.

## Correctness before timings

```sh
.venv/bin/python3.14 -m unittest discover -s experiments/phase5 -p 'test_*.py' -v
.venv/bin/python3.14 experiments/phase5/smoke.py
.venv/bin/python3.14 -m unittest discover -s tooling/tests -v
.venv/bin/python3.14 tooling/check_repository.py
node tooling/check_canonical_vectors.mjs
```

`smoke.py` rebuilds Java core probes and exercises all three real parsers,
plain-record boundaries, semantic diagnostics, stable-ID override rejection,
independent-process determinism and unchanged Analyze/Normalize contracts.
It does not turn missing editor/maintenance evidence into a passed hard gate.

## Rust probes

Use Rust 1.90.0, installed with rustup into a local ignored cache if it is absent.
Do not change the host's default toolchain. With that toolchain on the command path:

```sh
cargo +1.90.0 run --locked --release \
  --manifest-path experiments/phase5/core-runtime/Cargo.toml -- test-corpus/canonical
rustc +1.90.0 --edition=2024 -O experiments/phase5/core-runtime/core.rs \
  -o experiments/phase5/core-runtime/out/core
experiments/phase5/core-runtime/out/core 1000
```

The laptop uses explicit `RUSTUP_HOME` and `CARGO_HOME` inside
`experiments/phase5/.cache`, recorded in `maintenance.py`. CI uses its isolated
runner toolchain. No generated application or production target is built.

## Measurements (run serially)

```sh
.venv/bin/python3.14 experiments/phase5/run.py metadata
.venv/bin/python3.14 experiments/phase5/run.py antlr
.venv/bin/python3.14 experiments/phase5/run.py langium
.venv/bin/python3.14 experiments/phase5/run.py xtext
.venv/bin/python3.14 experiments/phase5/run.py core
.venv/bin/python3.14 experiments/phase5/editor.py
.venv/bin/python3.14 experiments/phase5/native.py
node experiments/phase5/langium/editor-probe.mjs
node experiments/phase5/langium/source-probe.mjs
.venv/bin/python3.14 experiments/phase5/inventory.py
.venv/bin/python3.14 experiments/phase5/summarize.py
```

`run.py` records raw outputs, elapsed process time and `/usr/bin/time` peak RSS.
Frontend scale uses three independent cold processes and five warm parses after
discarding the first parse. Heap limits are 768 MiB; the 1 GiB total-RSS budget
is an observed acceptance bound, **not an OS-enforced process/container limit**.
Each invocation has a 90-second timeout. A failed workload remains in the report;
further repetitions may be explicitly NOT_RUN after a resource failure.

Core graph timing uses eight iterations in one process; it is **not** the frontend
cold/warm workload. Java/Rust's eight concurrent correctness checks are outside the
timed graph iterations. TypeScript parallel execution is NOT_RUN.

The 1k/10k/100k corpus is parse-only, with intentionally incomplete Entity records.
It cannot establish semantic throughput at those sizes. Full semantic validation
retains the Phase 4 node/byte limits; no bounds are raised for a candidate.

## Maintenance probe

For the controlled TypeScript patch comparison, first install 5.9.2 under the
ignored `.cache/typescript-previous` directory with `npm install --save-exact`.
For offline npm restoration, copy the Langium package manifest and lock into
`.cache/langium-clean` and populate `/tmp/acp-phase5-npm-cache` with the initial
install. Then run `maintenance.py` with the local Rust cache available. It records
offline restoration, clean generated Java rebuilds, Rust offline rebuilding and
native API equivalence across TypeScript 5.9.2 → 5.9.3. It preserves previous
generated Java output under the ignored cache. `/tmp` caches/logs are ephemeral;
the durable evidence is the checked-in `results/` content.

## Phase 5B evidence closure

Use the same clean Linux prerequisites, exact current pins and locked restores
above. The workflow runs these commands on a fresh Ubuntu 24.04 hosted runner.
Local Python dependencies remain isolated in `.venv`; replace `python3.14` below
with `.venv/bin/python3.14` when the environment is not activated.

```sh
python3.14 -m unittest discover -s experiments/phase5 -p 'test_*.py' -v
python3.14 experiments/phase5/smoke.py
python3.14 experiments/phase5/wire.py
python3.14 experiments/phase5/source5b.py
python3.14 experiments/phase5/evidence5b.py
python3.14 experiments/phase5/scale5b.py
python3.14 experiments/phase5/inventory5b.py
python3.14 experiments/phase5/evolution.py prepare
npm --prefix experiments/phase5/.cache/evolution/langium ci --ignore-scripts --no-audit --no-fund
mvn -B -ntp -f experiments/phase5/.cache/evolution/xtext/pom.xml -Dmaven.repo.local="$PWD/experiments/phase5/.cache/m2" dependency:build-classpath -Dmdep.outputFile=target/classpath.txt
python3.14 experiments/phase5/evolution.py
```

`evolution-locks/` pins isolated previous ANTLR 4.13.1, Langium/CLI 4.3.0 and Xtext
2.43.0. Current pins are untouched. Preparation downloads the previous ANTLR jar
only if absent and verifies its recorded SHA-256. Previous Langium's packaged
configuration schema needs a recorded `$id` metadata repair; the comparison
applies that one edit before regeneration. The unmodified first-attempt failure
is preserved in `results/phase5b/evolution-first-attempt.json`. Generated-code
hashes/diffs, corpus results, compatibility effects and rollback are recorded.
Rollback uses unchanged current pins/locks and fresh generated outputs; ignored
previous-version directories can be discarded after review.

The expanded Rust wire binary uses the existing exact Cargo lock. On this laptop
`wire.py` detects the ignored local Rust toolchain; clean CI uses `cargo +1.90.0`.
The Python reference, Java, TS and Rust handlers exercise one shared message set.
They are not complete production compiler/plugin wire contracts.

Clean restoration requires the pinned CPython/Node/JDK/Rust toolchains, PyPI
packages in `tooling/requirements.txt`, npm registry artifacts from both lockfiles,
Cargo registry artifacts from `Cargo.lock`, Maven Central artifacts listed with
exact URLs/digests in `results/phase5b/inventory.json`, the ANTLR download site and
the digest-pinned patched generator URL in `versions.json`. Offline cached
restoration is demonstrated separately in the first-pass maintenance evidence;
independent clean-cache offline Maven restoration and patched-generator source
provenance remain UNKNOWN. The inventory is not legal redistribution clearance.

Phase 5B outputs go to `results/phase5b/`; first-pass measurements remain historical.
Hosted outputs are uploaded as `phase5b-ubuntu-evidence`, separately from laptop
measurements. Process/heap/time measurements are descriptive observations on a
shared laptop, not normalized competitive scores. The supervisor persists, but
its native parser children currently start cold on each request. Native editor
builder/resource updates and source-edit adapter timings are labeled separately.
Full 10k/100k ACP semantic validation remains NOT_SUPPORTED under unchanged bounds.
All `/tmp` logs are ephemeral. No Phase 6 work is included.
