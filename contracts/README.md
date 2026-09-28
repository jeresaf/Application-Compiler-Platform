# Machine-readable authoring and canonical contracts

| Schema | Exact version | Role |
| --- | --- | --- |
| [canonical.schema.json](canonical.schema.json) | Canonical Application 0.1.0 | Normalized content using semantic model 0.2.0, exact versions/features and digest; approval authority remains external. |
| [phase1.schema.json](phase1.schema.json) | Authoring model 0.2.0 | Current 69-kind bounded Phase 1 model: common identity/lifecycle/basis, P-01 through P-05 semantics and closed expression/type algebra. |
| [kernel.schema.json](kernel.schema.json) | Historical authoring kernel 0.1.0 | Frozen 20-kind regression contract; does not enforce 0.2 obligations. |
| [design-bindings.schema.json](design-bindings.schema.json) | Sidecar 0.1.0 | Exact application/snapshot/UI subject references, versioned catalogue and component handles, independent of semantic intent. |
| [evidence.schema.json](evidence.schema.json) | Observation artifact 0.1.0 | Exact obligation/requirement/subject references, artifact/configuration/tool/profile context, time, method, result and bounded measurements. |

All use JSON Schema 2020-12 as replaceable contract tooling. Sidecar version 0.1.0 is independent of the historical kernel version; current design/evidence tests bind to model 0.2.0. The [current meta-model](../docs/metamodel.md) defines cross-record meaning; the [historical specification](../docs/kernel-0.1.md) applies only to the original kernel.

Shape validation alone is insufficient. [validate.py](../tooling/validate.py) selects the authoring schema by exact modelVersion, checks references and shared contracts, then invokes the corresponding semantics. [design_bindings.py](../tooling/design_bindings.py) and [evidence_semantics.py](../tooling/evidence_semantics.py) check sidecar relationships against an already validated model. No input-supplied schema is fetched. Unknown versions, kinds and properties fail closed.

[phase1_contract.py](../tooling/phase1_contract.py) constructs the committed current schema from the retained kernel plus explicit typed additions; a test checks exact equality with the committed JSON. This is development tooling, not a parser, migration system or production-language choice. There is no automatic 0.1-to-0.2 migration.

The [payment](../test-corpus/phase1/payment.json) and [case-management](../test-corpus/phase1/case-management.json) fixtures use the current model. The [historical corpus](../test-corpus/semantic/cases.json) remains a separate regression suite. [Coverage](../docs/coverage.md) states the enforcement limits.

The [canonical contract](../docs/canonical-ir.md) and ADR-0011 select canonical serialization/hashing. [canonical_contract.py](../tooling/canonical_contract.py) generates the separate schema from pinned Phase 1 types; tests enforce reproducibility. Storage, target layout, plugin ABI and authenticated approval/evidence formats remain unselected. Material changes require an ADR, explicit contract version reasoning and positive/negative fixtures. Framework, parser, ORM, database, cloud, MCP and production-language annotations are outside semantic records.
