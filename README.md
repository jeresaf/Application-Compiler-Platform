# Application Compiler Platform

ACP maintains an authoritative application specification through semantic compilation, verification and repeated production evolution. The [architecture charter](ACP_CODEX_MASTER_HANDOFF.md) is authoritative.

## Current state

**Phase 1 is closed and green: authoring model 0.2.0.** It contains 69 closed semantic kinds with executable shape and semantic validation. ADR-0006 through ADR-0010 resolve the bounded P-01 through P-05 contracts. Payment and case-management reference domains exercise the same model. See the [completion report](docs/phase1-completion-report.md) for historical local and Ubuntu/Windows CI evidence and the review gate.

**Phase 2 is closed and green: Canonical Application IR 0.1.0.** The [canonical contract](docs/canonical-ir.md), [ADR-0011](docs/adr/0011-canonical-interchange.md) and [Phase 2 report](docs/phase2-completion-report.md) define typed content, canonical bytes/hashes, compatibility and migration/reapproval. Its schemas and byte/hash vectors are unchanged by Phase 3.

**Phase 3 is closed and green: bounded Change and Provenance 0.1.0.** Immutable snapshots, atomic journal, proposals, dependency conflicts, authenticated approval, provenance and recovery are executable reference contracts. All 63 tests and independent canonical checks pass on Linux; the completion report preserves earlier Ubuntu and Windows validation evidence. See [ADR-0012](docs/adr/0012-change-history.md), the [reference protocol](docs/change-reference.md) and [completion report](docs/phase3-completion-report.md). SQLite and HMAC are replaceable reference adapters. No production language/runtime, parser, storage engine, authority, target or plugin ABI is selected; [ADR-0004](docs/adr/0004-technology-evaluation.md) accepts integration/source-analysis architecture and defers core/frontend implementation choices.

**Phase 4 is CLOSED AND GREEN: bounded Compiler Core 0.1.0.** Eight immutable executable stage contracts, declared ports, deterministic identities, provenance/obligations, conservative incremental cache invalidation and ownership-safe artifact plans are covered by 92 passing regression tests and Ubuntu CI. See the [execution contract](docs/compiler-core.md), [ADR-0013](docs/adr/0013-compiler-core.md) and [completion report](docs/phase4-completion-report.md). **Phase 5 is CLOSED AND GREEN at the bounded evaluation scope:** native worker integration and target-native source-analysis architectures are ACCEPTED; production core runtime and textual frontend remain independently DEFERRED. Xtext is rejected for production on patched-generator provenance. Raw measurements and missing soft comparisons are explicit; no runtime/frontend winner is inferred from speed. See the [evaluation report](docs/phase5-completion-report.md), [ADR-0004](docs/adr/0004-technology-evaluation.md) and [reproduction commands](experiments/phase5/COMMANDS.md). **Phase 6 is IN PROGRESS and NOT CLOSED.** The first target prototype uses Java 21 / Spring Boot, Vue and PostgreSQL; full-domain capability admission and acceptance gates remain incomplete. See the [target contract](docs/phase6-target.md) and [status report](docs/phase6-completion-report.md). Phase 7 is NOT STARTED.

Authoring and canonical versions have separate roles:

The [explicit execution/dataflow successor](docs/adr/0015-explicit-operation-effects-and-dataflow.md) introduces separately versioned Authoring 0.3.0, Canonical 0.2.0 and ChangeSet 0.2.0. Historical contracts remain preserved. Proposed reference behavior requires human review before Phase 6 target work resumes; see the [dedicated report](docs/execution-v03-completion-report.md).

| Contract | Role |
| --- | --- |
| [ChangeSet 0.1](docs/change-reference.md) / [schema](contracts/change.schema.json) | Exact-base semantic operations, migration and provenance inputs; independent of canonical content. |
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
| `.github/workflows/` | Full semantic, canonical and change-history checks on Ubuntu 24.04 for every push and PR |

## Run all contract checks

CPython 3.14.7 and the pinned dependencies are test tooling only under [ADR-0003](docs/adr/0003-contract-harness.md).

Linux is the supported ACP development and CI host platform. Ubuntu 24.04 is the official hosted CI environment. This engineering-environment decision does not make the Canonical IR, semantic model, change model, compiler contracts or generated targets Linux-specific; ACP architecture remains target-neutral.

Phase 1–3 completion reports retain their historical validation evidence. Future phase reports use Linux evidence unless another environment is deliberately added.

For Linux setup and local validation, see [DEV_LINUX.md](DEV_LINUX.md).

```bash
python3.14 -m venv .venv
.venv/bin/python3.14 -m pip install -r tooling/requirements.txt
.venv/bin/python3.14 -m pip check
.venv/bin/python3.14 tooling/check_repository.py
.venv/bin/python3.14 -m unittest discover -s tooling/tests -v
node tooling/check_canonical_vectors.mjs
node tooling/check_canonical_vectors.mjs test-corpus/execution-v03
```

Node.js 24.21.0 independently checks canonical bytes/hashes as test tooling only. The full Python suite includes all earlier authoring/canonical checks, Phase 4 compiler-stage/determinism/cache/ownership tests and Phase 3 transactions, crash/concurrency, approval, history and two-domain evolution tests. [Corpus documentation](test-corpus/README.md) identifies the fixtures. Run `.venv/bin/python3.14 tooling/history_experiment.py` for synthetic storage-size and reopened-history observations.

Optional individual model checks:

```bash
.venv/bin/python3.14 tooling/validate.py test-corpus/semantic/reference.json
.venv/bin/python3.14 tooling/validate.py test-corpus/semantic/approved.json --mode compile
.venv/bin/python3.14 tooling/validate.py test-corpus/phase1/payment.json
.venv/bin/python3.14 tooling/validate.py test-corpus/phase1/case-management.json
```

Validation is offline after dependency installation. CLI exits: 0 valid for the selected authoring profile, 1 validation errors, 2 invalid/unreadable input. The legacy CLI envelope label `scope: kernel` is retained for both versions; `modelVersion` selects the contract. The `compile` profile checks necessary approval closure only: it does not normalize IR, authenticate approval or certify production readiness. Fixtures and attestations are synthetic.

Validate a canonical candidate with `.venv/bin/python3.14 tooling/canonical_ir.py validate test-corpus/canonical/payment.json`. Separate `normalize` and `migrate` operations require compile-eligible authoring 0.2.0 input and produce candidates only; see the [canonical commands](docs/canonical-ir.md#reproduction-and-diagnostics).

## Reference compiler pipeline

The Phase 4 structured reference frontend and synthetic test target produce an
immutable artifact plan with outstanding obligations; they do not generate or
write application source. No AI, production parser or target framework is required.

```bash
.venv/bin/python3.14 tooling/compiler_reference.py test-corpus/phase1/payment.json
.venv/bin/python3.14 tooling/compiler_reference.py test-corpus/phase1/case-management.json
```

These commands use explicitly synthetic fixture approvals. See the
[compiler corpus](test-corpus/compiler/README.md) for vectors and test boundaries.
