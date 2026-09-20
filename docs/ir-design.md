# IR and compiler architecture contracts

Status: normative boundaries; serialization details marked proposed. Basis: charter §§2, 8–11, 15, 20–24, 27, 30, 36–37. No compiler pipeline is implemented in Phase 1.

## Stages and invariants

Every pass accepts immutable versioned inputs, an explicit capability/configuration manifest, and cancellation/resource limits. It returns either `Success(output, provenance, obligations, diagnostics)` or `Failure(diagnostics)`; failed output cannot feed production stages. Recovery ASTs may be returned separately for editor use, never as successful Canonical IR. Passes do not mutate inputs or resolve undeclared network/environment state.

| Stage | Input → output | Preconditions → postconditions / failure |
| --- | --- | --- |
| Ingest | Structured/text source → parser output | Bounded input; explicit dialect/version → syntax representation and source map, or input diagnostics |
| Elaborate | Parser output → semantic AST | Valid parse → frontend-independent typed candidates, unresolved names/ambiguity retained; no parser classes escape |
| Analyze | AST + approved dependency snapshots → resolved semantic model | Complete type registry and scope → exact refs, type checks, conflicts, policy/workflow checks, obligation set; unresolved blocking meaning fails |
| Normalize | Resolved model + approval proofs → Canonical IR | Verified approvals and dependency closure → deterministic immutable canonical form, with no target choices or unchecked extensions |
| Project | Canonical IR → Product/Domain/Application projections | Same canonical identity and snapshot → typed views; no new authority or silent semantic rewrite |
| Realize | Canonical projections + approved architecture/design choices → Architecture/Design IR | Required decisions accepted → topology, transaction/delivery strategy, UI design binding, enforcement plan, new derived obligations |
| Negotiate/lower | Architecture IR + target capability manifests → Target IR | Version/capability compatibility → target-specific realization for every required capability; unsupported/partial capability fails |
| Generate | Target IR + locked generator inputs + ownership map → artifact plan | Declared inputs and safe extension strategy → staged files, hashes, source maps, ownership, test/migration obligations; no direct overwrite |
| Analyze source | Source snapshot + native/syntax analyzers → Source Model | Content digest and analysis capability → symbols, relationships, ownership and confidence; incomplete analysis marked unknown |
| Verify | Artifact + source model + obligations + evidence → gate results | Isolated executor and locked tools → exact-input evidence, PASS/FAIL/BLOCKED/NOT_RUN; no unexecuted pass |
| Package / observe | Verified artifact + environment profile → package/runtime evidence | Baseline plus profile gates satisfied → reproducible package/provenance; deployment is separately authorized |
| Compare | Canonical/target + source/runtime observations → drift + proposed changes | Compatible versions, known completeness → mismatch records and impact; no automatic intent replacement |

Domain/Application projection and Architecture lowering may be multiple independently tested passes. Pure passes depend on data/ports, never on storage, parser runtime, source tool, AI vendor, or target framework.

## Core port contracts

These are logical interfaces, not a selected language API or ABI.

| Port | Request / response | Required behavior |
| --- | --- | --- |
| SnapshotRepository | read exact snapshot; compare-and-append(base, change, snapshot) | Atomic revision check; no partial writes; retry token; history retained |
| Frontend | source bytes + dialect/version → AST + source map | Deterministic valid-input mapping; incomplete input diagnostics; no business approval |
| ApprovalAuthority | subject digest + evidence + scope → decision | Authenticate principal, permissions, expiry/revocation; unavailable means blocked |
| TargetCompiler | capability manifest; lower/plan methods | Stable version negotiation; pure plans; explicit unsupported capability diagnostics |
| ArtifactStore | stage/read by digest; publish manifest | Reject traversal/collisions; verify content; ownership check before applying plan |
| SourceAnalyzer | content snapshot + query → observations + completeness | Distinguish syntax, resolved symbols/types, inferred links; unknown is not absent |
| EvidenceExecutor | isolated plan + input digests → evidence | Sandbox/resource/network/secret policy, controlled outputs, failure provenance |
| AIProvider | bounded context + task policy → candidate | Record model/config/input/output provenance; cannot apply approved semantic changes |
| Clock/secret/environment providers | explicit runtime binding → scoped result | Never accessible from pure canonical expressions or deterministic passes |

## Canonical and lowered envelopes

Proposed stable envelope: `{irKind, schemaVersion, applicationId, snapshotDigest, inputDigests, producer, requiredFeatures, payload, provenanceMap, obligations}`. Neither the current [Phase 1 authoring model 0.2.0](metamodel.md) nor the historical kernel 0.1 implements this envelope. Final serialization is P-07; Phase 2 has not begun.

ADR-0006 through ADR-0010 define accepted bounded domain, security/privacy, execution, task UI and quality/operations semantics for a future Canonical IR. They do not choose its serialization or implement normalization. The separate design-binding sidecar associates semantic UI with catalogue handles; it is not Design IR. Evidence observations validate bindings/freshness in the harness; they are not canonical approval proofs. Exact-input digest strings in fixtures are supplied values, not a canonical hashing specification. Architecture/Design/Target realization and authenticated authority must remain separate from framework-neutral canonical meaning.

- Canonical references are exact and closed; approved policy/invariant meaning is preserved.
- Architecture IR may introduce logical APIs, persistence strategies, delivery mechanisms, topology, and enforcement locations, each justified by decisions/requirements.
- Target IR may contain framework models, database types, component trees, toolchain-specific tests, and manifests. Those types may not flow backward into canonical payloads.
- Lowered identity uses a stable origin set plus an explicit role/discriminator; implementation must demonstrate collision handling and rename continuity before adoption.
- A mapping is many-to-many: one requirement can have several enforcement sites, and one constraint can implement several requirements. Unmapped obligations fail capability/lowering verification.

Example: canonical `Money<UGX>` remains typed money. A target may select a precise decimal database type and runtime representation after checking scale/rounding requirements. A target lacking safe representation emits a capability error; it cannot substitute a float. A canonical policy constrains reads/exports/actions; hiding a UI button alone does not discharge authorization.

## Determinism contract

Input manifest includes semantic snapshot, compiler/pass versions, target/profile/design versions, generator/plugin digests, dependency/toolchain locks, configuration schema and declared values, feature flags, and accepted AI candidate artifact digests. Locale, clock, filesystem order, machine paths, random state, network responses, and ambient environment are forbidden undeclared inputs.

Canonical equivalence will ignore map/set ordering and insignificant serialization whitespace, but preserve ordered workflows/operands, exact semantic numbers, identities, and meaning. Byte canonicalization, Unicode policy, and digest algorithms require P-07 vectors before hashes become authoritative. Never claim ordinary sorted JSON is a complete cross-runtime canonicalization scheme.

Deterministic artifact plans require stable relative paths, line endings, encoding, generated names, and source-map treatment. Separate nondeterministic timestamps/signatures into attestation envelopes. Cache key = all declared inputs and stage identity; cache reuse verifies output digests and trust. Failed or incomplete evidence cannot be reused as success. AI cache reuse requires matching candidate input/policy/version provenance and approval; it does not make sampling deterministic.

## Versioning and compatibility

Meta-model version, application snapshot revision, concept revision, producer version, plugin version, and artifact digest are distinct. Kernel tooling accepts exactly `0.1.0`. Before 1.0, every shape/semantic change needs a versioned fixture migration, no implicit compatibility promise.

Proposed stable policy: major for incompatible meaning/shape, minor for explicitly negotiated additive capabilities, patch for meaning-preserving corrections. Unknown required features fail closed even with matching major version. Readers must not discard unknown security/behavior fields. Schema migrations take immutable old snapshots to new candidates with ID continuity, provenance, semantic diff, migration diagnostics, and reapproval when meaning changes. Migrations cannot overwrite history or imply database migration completion. Bidirectional/downgrade guarantees must be explicitly declared, never assumed.

## Source intelligence and ownership

Source Model records `{sourceDigest, analyzerVersion, symbols, references, inferredSemanticLinks, ownership, completeness}`. Each symbol has language, artifact locator, stable analyzer key where available, and resolution confidence. Syntax extraction cannot prove call binding, types, authorization, or absence of drift; native analyzers may add that evidence. Ambiguous source-to-semantic matches create review issues.

Ownership manifest covers paths or nonoverlapping digest-bound regions, with one owner class: COMPILER_OWNED, FRAMEWORK_OWNED, AI_MANAGED, HUMAN_OWNED. Missing/overlapping ownership blocks writing. Human-owned regions are preserved; compiler-owned edits require a reviewed adoption or regeneration plan. Extension hooks must describe callable contracts and verification needs. No claim of arbitrary legacy round-trip regeneration.

Provenance should be sidecar mappings bound to artifact digests (P-09), with optional target-supported markers. Renames, formatting, or manual edits invalidate location-based mappings until reanalyzed. Context bundles carry dependency closure, snapshot/completeness markers, relevant constraints/locked decisions, and omissions; token budgets must not silently truncate necessary security or change impact.
