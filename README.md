# Application Compiler Platform

ACP maintains an authoritative application specification through semantic compilation, verification and repeated production evolution. The [architecture charter](ACP_CODEX_MASTER_HANDOFF.md) is authoritative.

## Current state

**Phase 1 is closed and green: authoring model 0.2.0.** It contains 69 closed semantic kinds with executable shape and semantic validation. ADR-0006 through ADR-0010 resolve the bounded P-01 through P-05 contracts. Payment and case-management reference domains exercise the same model. See the [completion report](docs/phase1-completion-report.md) for local and Ubuntu/Windows CI evidence and the review gate.

**Phase 2 Canonical Application IR 0.1.0 is implemented; closure validation is in progress.** The [canonical contract](docs/canonical-ir.md), [ADR-0011](docs/adr/0011-canonical-interchange.md) and [Phase 2 report](docs/phase2-completion-report.md) define typed content, canonical bytes/hashes, compatibility and migration/reapproval. This remains reference contract tooling, not a production compiler. No production runtime/language, parser, target stack, storage engine or plugin ABI has been selected; [ADR-0004](docs/adr/0004-technology-evaluation.md) remains PROPOSED. Phase 3 has not begun.

Authoring and canonical versions have separate roles:

| Contract | Role |
| --- | --- |
| [Canonical Application 0.1](docs/canonical-ir.md) / [schema](contracts/canonical.schema.json) | Normalized typed content over authoring semantics 0.2.0, domain-separated digest and exact-version reader. Content validity does not establish approval. |
| [Phase 1 model 0.2](docs/metamodel.md) / [schema](contracts/phase1.schema.json) | Current bounded authoring semantics, including domain, security/privacy, execution, task UI and quality/evidence obligations. |
| [Historical kernel 0.1](docs/kernel-0.1.md) / [schema](contracts/kernel.schema.json) | Original 20-kind regression contract. Passing it does not satisfy current 0.2 requirements. No automatic migration is implemented. |

Start with the [constitution](docs/constitution.md), [glossary](docs/glossary.md), [meta-model](docs/metamodel.md), [ADRs](docs/adr/README.md), [coverage](docs/coverage.md) and [roadmap](docs/roadmap.md). Later-stage boundary contracts remain in [IR design](docs/ir-design.md), [change model](docs/change-model.md), [threat model](docs/threat-model.md), [production gates](docs/production-gates.md) and [diagnostics](docs/diagnostics.md).

## Repository boundaries

| Path | Responsibility |
| --- | --- |
| `docs/` | Semantic specifications, architecture decisions, safe deferrals and phase gates |
| `contracts/` | Closed authoring/canonical schemas and independent design/evidence sidecars |
| `test-corpus/` | Portable semantic/canonical cases and two synthetic reference domains |
| `tooling/` | Replaceable validation harness and reference decision helpers; no production compiler dependency |
| `.github/workflows/` | Semantic/canonical checks on Ubuntu and Windows for every push and PR |

## Run all contract checks

CPython 3.14.7 and the pinned dependencies are test tooling only under [ADR-0003](docs/adr/0003-contract-harness.md).

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r tooling/requirements.txt
.venv/Scripts/python -m pip check
.venv/Scripts/python tooling/check_repository.py
.venv/Scripts/python -m unittest discover -s tooling/tests -v
node tooling/check_canonical_vectors.mjs
```

On POSIX use `.venv/bin/python`. Node.js 24.21.0 independently checks canonical bytes/hashes as test tooling only. The full Python suite includes historical/current authoring, design/evidence and Phase 2 normalization, compatibility, migration and approval-boundary checks. [Corpus documentation](test-corpus/README.md) identifies the file-based and in-test fixtures.

Optional individual model checks:

```powershell
.venv/Scripts/python tooling/validate.py test-corpus/semantic/reference.json
.venv/Scripts/python tooling/validate.py test-corpus/semantic/approved.json --mode compile
.venv/Scripts/python tooling/validate.py test-corpus/phase1/payment.json
.venv/Scripts/python tooling/validate.py test-corpus/phase1/case-management.json
```

Validation is offline after dependency installation. CLI exits: 0 valid for the selected authoring profile, 1 validation errors, 2 invalid/unreadable input. The legacy CLI envelope label `scope: kernel` is retained for both versions; `modelVersion` selects the contract. The `compile` profile checks necessary approval closure only: it does not normalize IR, authenticate approval or certify production readiness. Fixtures and attestations are synthetic.

Validate a canonical candidate with `.venv/Scripts/python tooling/canonical_ir.py validate test-corpus/canonical/payment.json`. Separate `normalize` and `migrate` operations require compile-eligible authoring 0.2.0 input and produce candidates only; see the [canonical commands](docs/canonical-ir.md#reproduction-and-diagnostics).
