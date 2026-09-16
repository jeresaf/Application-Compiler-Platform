# Application Compiler Platform

ACP maintains an authoritative application specification through semantic compilation, verification, and repeated production evolution.

## Current state

Phase 1 contract baseline with an executable **kernel**, not a complete application model or compiler. The [architecture charter](ACP_CODEX_MASTER_HANDOFF.md) is authoritative. No production implementation language, textual frontend, target stack, storage engine, or plugin ABI has been selected.

Start with:

1. [Constitution](docs/constitution.md) and [glossary](docs/glossary.md).
2. [Meta-model](docs/metamodel.md), [IR and compiler contracts](docs/ir-design.md), and [diagnostics](docs/diagnostics.md).
3. [Change model](docs/change-model.md), [threat model](docs/threat-model.md), and [production gates](docs/production-gates.md).
4. [Decisions and proposals](docs/adr/README.md), [coverage](docs/coverage.md), and [roadmap](docs/roadmap.md).

## Repository boundaries

| Path | Responsibility |
| --- | --- |
| `docs/` | Normative contracts, explicit proposals, architectural decisions |
| `contracts/` | Language-independent machine-readable kernel schema |
| `test-corpus/` | Portable semantic examples and expected diagnostics |
| `tooling/` | Replaceable contract validation harness; no production compiler dependency |

Only demonstrated boundaries have directories. Future packages must earn their own boundary through contracts and tests.

## Run contract checks

Python is a test-harness choice only; see [ADR-0003](docs/adr/0003-contract-harness.md). The current harness was verified on CPython 3.14.7; dependencies are pinned for that environment.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r tooling/requirements.txt
.venv/Scripts/python -m unittest discover -s tooling/tests -v
.venv/Scripts/python tooling/validate.py test-corpus/semantic/reference.json
```

On POSIX use `.venv/bin/python`. Validation is offline after dependency installation. Exit codes: `0` kernel-valid, `1` validation errors, `2` unreadable/invalid input. `--mode compile` additionally checks approval closure; it **does not certify approval authenticity or production readiness**. The schema and corpus are portable to the eventual compiler runtime.

See [coverage](docs/coverage.md) for what is executable, contractual, or still proposed. Fixture actors, requirements, and approvals are synthetic test data.
