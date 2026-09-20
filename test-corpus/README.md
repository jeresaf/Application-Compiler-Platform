# Phase 1 semantic corpus

The corpus contains two separate authoring versions. Historical validation remains regression evidence; it is not a shortcut around current model requirements.

| Asset | Version / coverage |
| --- | --- |
| [semantic/reference.json](semantic/reference.json) | Historical kernel 0.1.0 draft, all 20 original kinds: tenant/payment authorization and two-state workflow. |
| [semantic/approved.json](semantic/approved.json) | Historical kernel 0.1.0 with synthetic APPROVED lifecycles and attestations for necessary compile closure. |
| [semantic/cases.json](semantic/cases.json) | 54 portable historical cases, positive and negative, with exact expected code/subject pairs including multiplicity. |
| [phase1/payment.json](phase1/payment.json) | Current 0.2.0 financial reference: explicit money precision/rounding, tenant permissions, aggregate command, delivery/retry, task UI and quality/evidence declarations. |
| [phase1/case-management.json](phase1/case-management.json) | Current 0.2.0 non-financial reference: Organization, User, Case, Document, Assignment, Review, Approval, Comment; relations/cardinality, assigned-review authorization, review/approval/archive workflow and task UI. |
| [phase1/cases.json](phase1/cases.json) | 100 portable current cases: two positive domains, 49 per-promoted-kind shape/leakage negatives and 49 per-promoted-kind semantic/reference/bounds negatives. |

The current models together contain all 69 supported kinds: payment has 101 nodes/68 kinds and case-management has 149 nodes/63 kinds. Case-management has no money/payment dependency. Both are synthetic semantic specifications, not approved production business designs or generated applications.

## Sidecar and focused fixtures

[phase1.schema.json](../contracts/phase1.schema.json) is the current authoring shape. [design-bindings.schema.json](../contracts/design-bindings.schema.json) and [evidence.schema.json](../contracts/evidence.schema.json) are separate 0.1.0 sidecar/observation contracts used with 0.2 models.

Positive and negative design/evidence fixtures are constructed inside [test_phase1.py](../tooling/tests/test_phase1.py), not committed as standalone corpus JSON. Two design catalogues bind the same semantic UI unchanged; negative cases exercise wrong kinds and unknown CSS properties. Evidence vectors exercise passing performance observations, stale/future dates, artifact mismatch, NOT_RUN, wrong method, failing thresholds, missing evidence and applicability approval. Additional implemented binding/measurement checks are described in [coverage](../docs/coverage.md); exhaustive branch coverage is not claimed. These are contract tests, not real measurements or authenticated evidence.

The same test module covers types/precision/rounding/equality, presence, tenant denial and hold precedence, retry horizons and timezone gap/overlap policies, task UI ownership and quality/recovery constraints. It tests current approved-snapshot closure and focused Scope lifecycle/basis failures. Schema and reference-model builders are compared against committed JSON to detect drift.

## Portable edit notation

Each case selects a base model and validation mode, applies ordered edits to a deep copy and lists expected diagnostics. Empty expectations mean authoring-profile validity only.

An edit has `op`, `node`, `path` and, except delete, `value`. A null node addresses the document; otherwise it selects by semantic ID. Path is an array of object keys/list indices. Set assigns a property/index, delete removes it, and append adds to a list. This is test-fixture notation, not the production change-set protocol or JSON Patch.

The historical runner checks exact code/subject results and multiplicity, input immutability and repeatability. The current corpus requires named code/subject pairs and permits additional independent errors; positive cases must have no errors. Additional tests cover strict input, graph/object ordering, stable-ID rename behavior, diagnostics and closed shapes. Port these assets to future implementations; no grammar or runtime dependency is encoded in them.

## Run

Use the installation instructions in the [root README](../README.md), then run:

```powershell
.venv/Scripts/python tooling/check_repository.py
.venv/Scripts/python -m unittest discover -s tooling/tests -v
```

This is the same repository-check/full-suite sequence used by the Ubuntu and Windows CI matrix. Future target, migration, integration, drift and generated application suites must supply their own evidence when those stages become executable. No fixture reviewer is a real approval authority.
