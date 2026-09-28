# Application Compiler Platform

ACP maintains an authoritative application specification through semantic compilation, verification and repeated production evolution. The [architecture charter](ACP_CODEX_MASTER_HANDOFF.md) is authoritative.

## Current state

**Phase 1 is closed and green: authoring model 0.2.0.** It contains 69 closed semantic kinds with executable shape and semantic validation. ADR-0006 through ADR-0010 resolve the bounded P-01 through P-05 contracts. Payment and case-management reference domains exercise the same model. See the [completion report](docs/phase1-completion-report.md) for local and Ubuntu/Windows CI evidence and the review gate.

This is **not Canonical IR or a production compiler**. No production runtime/language, parser, target stack, storage engine or plugin ABI has been selected. [ADR-0004](docs/adr/0004-technology-evaluation.md) remains PROPOSED. Phase 2 is the next gated phase and has not begun.

Two versions are deliberately retained:

| Contract | Role |
| --- | --- |
| [Phase 1 model 0.2](docs/metamodel.md) / [schema](contracts/phase1.schema.json) | Current bounded authoring semantics, including domain, security/privacy, execution, task UI and quality/evidence obligations. |
| [Historical kernel 0.1](docs/kernel-0.1.md) / [schema](contracts/kernel.schema.json) | Original 20-kind regression contract. Passing it does not satisfy current 0.2 requirements. No automatic migration is implemented. |

Start with the [constitution](docs/constitution.md), [glossary](docs/glossary.md), [meta-model](docs/metamodel.md), [ADRs](docs/adr/README.md), [coverage](docs/coverage.md) and [roadmap](docs/roadmap.md). Later-stage boundary contracts remain in [IR design](docs/ir-design.md), [change model](docs/change-model.md), [threat model](docs/threat-model.md), [production gates](docs/production-gates.md) and [diagnostics](docs/diagnostics.md).

## Repository boundaries

| Path | Responsibility |
| --- | --- |
| `docs/` | Semantic specifications, architecture decisions, safe deferrals and phase gates |
| `contracts/` | Closed historical/current authoring schemas and independent design/evidence sidecars |
| `test-corpus/` | Portable positive/negative cases and two synthetic reference domains |
| `tooling/` | Replaceable validation harness and reference decision helpers; no production compiler dependency |
| `.github/workflows/` | Phase 1 checks on Ubuntu and Windows for every push and PR |

## Run all contract checks

CPython 3.14.7 and the pinned dependencies are test tooling only under [ADR-0003](docs/adr/0003-contract-harness.md).

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r tooling/requirements.txt
.venv/Scripts/python -m pip check
.venv/Scripts/python tooling/check_repository.py
.venv/Scripts/python -m unittest discover -s tooling/tests -v
```

On POSIX use `.venv/bin/python`. The full suite includes historical 0.1 regression tests; current 0.2 schema, payment and case-management tests; all portable negative semantic cases; design-binding tests; evidence applicability, binding, freshness and measurement tests. [Corpus documentation](test-corpus/README.md) identifies the file-based and in-test fixtures.

Optional individual model checks:

```powershell
.venv/Scripts/python tooling/validate.py test-corpus/semantic/reference.json
.venv/Scripts/python tooling/validate.py test-corpus/semantic/approved.json --mode compile
.venv/Scripts/python tooling/validate.py test-corpus/phase1/payment.json
.venv/Scripts/python tooling/validate.py test-corpus/phase1/case-management.json
```

Validation is offline after dependency installation. CLI exits: 0 valid for the selected authoring profile, 1 validation errors, 2 invalid/unreadable input. The legacy CLI envelope label `scope: kernel` is retained for both versions; `modelVersion` selects the contract. The `compile` profile checks necessary approval closure only: it does not normalize IR, authenticate approval or certify production readiness. Fixtures and attestations are synthetic.
