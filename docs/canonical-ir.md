# Canonical Application IR 0.1.0

Status: normative bounded Phase 2 contract, [ADR-0011](adr/0011-canonical-interchange.md). Semantic meaning is pinned to [authoring model 0.2.0](metamodel.md). The [schema](../contracts/canonical.schema.json) and [reference harness](../tooling/canonical_ir.py) implement shape, normal-form, digest and semantic checks. They are not a production compiler, state repository or approval authority.

## Envelope and typed content

The only envelope properties are `content` and `contentDigest`. A digest covers the entire content object, excluding the digest itself; there is no circular hash input. A pretty-printed envelope is valid interchange when its decoded content is already in semantic normal form. Canonical wire bytes are available separately through the byte encoder.

| Content property | Required value / meaning |
| --- | --- |
| `irKind` | `CanonicalApplication` |
| `schemaVersion` | `0.1.0`, version of this envelope/normalization contract |
| `semanticModelVersion` | `0.2.0`, independent version of the 69-kind semantic algebra |
| `canonicalProfile` | `acp-jcs-safe-v1` |
| `applicationId` | Stable application-scoped identity, using the Phase 1 ID grammar |
| `requiredFeatures` | Exactly `["acp.phase1.0.2"]`; omission, extras or unknown features fail closed |
| `nodes` | Nonempty closed typed node records; exactly one current revision per semantic ID |
| `issues` | Retained closed issue records; unresolved blocking issues are forbidden |

Every node retains `id`, `revision`, `kind`, `name`, `lifecycle`, `steward`, `origins`, `basis` and typed `data`. Only APPROVED and DEPRECATED lifecycle labels are eligible; these labels are assertions requiring independent authority. All exact references must resolve within the same application content, to the right revision/kind/owner. No implicit imports or network lookup are permitted. `supersededBy` is absent because superseded nodes cannot be active content. Historical records belong in the future repository, not the selected current graph.

The schema embeds a pinned copy of the existing closed semantic types, generated reproducibly from the Phase 1 schema. Schema validation alone cannot prove ownership, type consistency, security, execution, issue or evidence-obligation validity. The reader reruns all applicable Phase 1 semantic checks. Requirements, decisions, origins, basis edges and all modeled obligations survive import; there is no lossy projection to entities alone. Product/Domain/Application views and Architecture/Design/Target envelopes remain later compiler contracts.

## Normal form

Normalization is defined only after successful authoring `compile` eligibility checks. It never repairs invalid references, silently rounds input or approves proposals. Source objects are not mutated. Readers reject non-normal content even if a sender recomputes its digest.

| Data | Normalization rule |
| --- | --- |
| Nodes and issues | Ascending ASCII semantic ID. Duplicate IDs fail validation. |
| Reference arrays, including basis and issue subjects | Sort by each element's canonical UTF-8 byte sequence. Retain exact revision. Duplicates are invalid. |
| `UseCase.steps`, `Wizard.steps` | Preserve sequence; these are the two ordered reference arrays in semantic model 0.2.0. |
| `Query.projection` | Sort entries by canonical bytes; output-field mapping has no execution order. Existing validation rejects repeated output fields. |
| `Invariant.enforcement`, `AuthenticationModel.mechanisms`, `ResponsivePolicy.modes`, `AccessibilityRequirement.checks`, `EvidenceRequirement.methods`, `CompatibilityRequirement.supportedVersions`, `ObservabilityRequirement.signals` | Unique sets, sorted by element canonical bytes. |
| `origins` | Sorted multiset of full origin records; preserve multiplicity and every evidence handle. |
| `Decision.alternatives` | Preserve authored order and multiplicity; no equivalence of reorderings is assumed. |
| Decimal/Money literals and numeric RANGE bounds | Remove fractional trailing zeros and an empty decimal point; negative zero becomes `"0"`. Never change currency, precision, scale or rounding policy. |
| Quality thresholds | Render exact positive decimal value as minimal plain decimal, without exponent, leading plus or fractional trailing zeros. Reject canonical expansion exceeding 128 characters before allocation. This is an explicit additional IR resource restriction. |
| Instant/LocalDateTime literals | Remove fractional trailing zeros and empty decimal point. Preserve UTC `Z` or local-time distinction; no timezone conversion. |
| Named, Nullable, List, Set and Value literals | Recurse using declared types and exact definitions. Preserve nominal types, null, List order, missing optional fields and literal field-ID keys; sort Set values by normalized element bytes. Duplicate typed Set values are rejected before normalization. |
| All other text, scalar declarations and expressions | Preserve exactly; map key order is handled by the byte layer. No Unicode NFC conversion, trimming, case folding, algebraic rewriting or operand swapping. |

UI reference lists other than Wizard steps are semantic sets under Phase 1; visual column/control/reading order must be supplied by future Design IR, not inferred from their incoming array order. Plain prose can retain ambiguity in nonblocking issues. Equivalence here means these explicit normalization rules, not arbitrary behavioral equivalence of prose or expressions.

## Byte profile and digest

`acp-jcs-safe-v1` uses the [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html) serialization rules for its restricted input domain:

1. Strict UTF-8 without BOM; at most 1,048,576 input/output bytes and 48 nested value levels. Malformed UTF-8, duplicate decoded property names, lone surrogates, nonfinite values and trailing content are rejected.
2. JSON number tokens are integers with absolute value <= 9,007,199,254,740,991. Decimal-point and exponent tokens are rejected even when mathematically integral. `-0` becomes `0`. Domain numeric strings are normalized only by the typed layer above.
3. Recursively sort object property names lexicographically by unsigned UTF-16 code units. Do not use Unicode code-point order, locale collation or JavaScript integer-key enumeration order. Arrays retain the order supplied by semantic normalization.
4. Emit compact JSON without token whitespace or trailing newline. Escape quote/backslash and controls using JCS string rules, with lowercase hexadecimal escapes where needed; preserve other Unicode scalars, including U+2028/U+2029. Emit UTF-8, not ASCII-escaped Unicode. Booleans and null have their lowercase JSON spellings.

The digest is `"sha256:" + lowercase_hex(SHA256(prefix || canonical_bytes(value)))`, where `prefix` is ASCII `ACP`, NUL, ASCII `acp-jcs-safe-v1`, NUL, ASCII domain, NUL. Domain is `canonical` for the content object, `authoring` for complete migration source records, or `vector` for byte-test vectors. Example prefix notation: `ACP\0acp-jcs-safe-v1\0canonical\0`. A profile/version change requires a new contract; these bytes cannot be silently reinterpreted.

Application ID, semantic IDs/revisions, names, stewardship, origins, lifecycle assertions, issues, required features and all typed meaning participate in content identity. Changes to any of those produce a new digest unless covered by an explicit normalization equivalence. `snapshotId` is an authoring export label and is excluded; canonical content identity is its digest. Approval records are excluded and independently bound to that digest. Producer versions, timestamps, signatures, artifact observations and build-input manifests belong in external attestations or later build envelopes, not in this semantic content.

Origin handles are preserved and hashed, but not fetched. Authoring-source digests canonicalize object keys only; unlike canonical content, they preserve the original node/approval arrays and numeric spelling, so they identify a complete source record rather than a semantic equivalence class. They are not hashes of source-file whitespace.

## Approval boundary

`normalize_candidate` requires every input node to have an active lifecycle and a matching exact-revision authoring attestation, and rejects open blocking issues. Those checks establish eligibility only: fixture reviewer/evidence strings are not trusted proofs. `validate_snapshot` checks content without creating authority. Its internal structural witnesses allow reuse of the Phase 1 eligibility checker; they are never exported as approval evidence.

`admit` deep-copies the candidate, validates it, freezes its content bytes, and invokes a trusted host-supplied ApprovalAuthority with application ID, exact content digest and those bytes. Only literal Boolean `True` admits; missing authority, denial, malformed result or exception blocks. The trusted adapter must independently authenticate principal, scope, approval record, expiry and revocation for the request. Input JSON cannot configure this adapter. A test lambda is a test double, not authentication. Production authority implementation and durability are deferred to the change/provenance and evidence phases.

Admission returns immutable bytes and digest. Later mutation of the caller's objects cannot alter the admitted value. Admission is a point-in-time result, not a persistent authorization lease: future execution must enforce its own freshness/revocation policy. No production command is enabled by this harness or CLI. Neither an active lifecycle label nor a recomputed digest grants authority.

## Compatibility and migration

Versions of semantic models, canonical envelopes, normalization profiles, node revisions, source export labels and future producer/plugins are distinct. This reader accepts only the declared exact combination. Even unknown patch versions fail. A same-major version is not permission to drop unknown properties or ignore new security requirements. Required-feature removal, addition and unknown schema versions fail before content use. There are no implicit up/down conversions.

The sole registered migration, `authoring-0.2-to-canonical-0.1-v1`, is a pure import to a candidate. Its receipt records the complete source digest, target digest, exact preserved ID/revision subjects and `requiresApproval: true`. It preserves node kind, identity, revisions, references and modeled meaning under the rules above; the old source remains untouched. It does not carry authoring approvals forward. The source must remain available by digest to retain excluded attestations and export labels. Storage, audit persistence, rollback execution and atomic publication are Phase 3 work.

Historical authoring 0.1.0 cannot be upgraded automatically because it lacks mandatory Phase 1 0.2 security/execution semantics. Unsupported source/target pairs fail closed. Future canonical migrations must declare source/target versions, compatibility classification, transformation, preservation/loss constraints and reapproval rules, with immutable before/after vectors and rejection cases. Meaning-changing migrations require semantic revision/reference updates and fresh content approval; no implementation for such a future version is claimed. Phase 3 must enforce revision advancement against history: snapshot validation alone cannot detect a same-revision edit, but its changed content digest already invalidates old exact-content approval.

## Reproduction and diagnostics

```powershell
.venv/Scripts/python -m unittest discover -s tooling/tests -p test_canonical.py -v
.venv/Scripts/python tooling/canonical_ir.py validate test-corpus/canonical/payment.json
node tooling/check_canonical_vectors.mjs
```

`normalize <authoring.json>` and `migrate <authoring.json>` print candidates/receipts. The committed Phase 1 examples are proposals, so direct normalization of those files correctly fails; [synthetic fixture construction](../tooling/canonical_fixtures.py) creates explicit test-only active versions for the [canonical corpus](../test-corpus/canonical/README.md). No CLI flag overrides the authority gate. Exit codes: 0 successful contract operation, 1 contract rejection, 2 undecodable/unreadable input. `validate` explicitly prints `authorityVerified: false`.

Errors use `ACP-IR-INPUT`, `VERSION`, `FEATURE`, `SHAPE`, `SEMANTIC`, `NORMAL`, `DIGEST` and `AUTHORITY` (each with the `ACP-IR-` prefix). Messages do not echo untrusted values or backend exceptions. For source shape/semantic detail, run the existing authoring checker in `--mode compile`; its subject/path diagnostics remain authoritative. No partial success is passed to another stage.

## Canonical Application 0.2.0 successor

[ADR-0015](adr/0015-explicit-operation-effects-and-dataflow.md) introduces a separate [closed schema](../contracts/canonical-0.2.schema.json) with `schemaVersion: 0.2.0`, `semanticModelVersion: 0.3.0` and exact feature `acp.execution.0.3`. The byte profile and digest domains are unchanged; version and explicit effects are included in the content hash. Historical 0.1 vectors remain untouched. [Successor vectors](../test-corpus/execution-v03/manifest.json) are independent. Node verifies both directories separately.

Assignment and execution-step arrays are ordered semantic programs. Input/output/payload mappings are unordered unique-destination maps; event mappings are unordered unique-event maps. References, origins and nodes retain their prior normalization rules. A 0.2 authoring migration with missing behavior returns review-required blockers and no guessed candidate. Exact new approval is required even for stable semantic IDs.
