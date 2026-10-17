# Stage B0 implementation boundary

This file retains the Stage A design below as design text. B0 implements a laboratory-only subset; the original Stage A artifact outside the repository is unchanged.

Implemented: closed companion schemas, immutable synthetic context, exact ordinary-Git witness provenance, descriptor-based bounded artifact capture, distinct executor/collector Ed25519 laboratory signatures, synthetic review grants/decisions, and an explicit optional laboratory JUnit registration parameter. Every successful prototype result is QUALIFICATION_ONLY. The release bridge rejects all inputs. The audit's added structural-notice helper does not merge criterionEvidence or accepted_reviews; no CLI/workflow activates admission.

Native default behavior: all 39 effective SPECS and every semantic predicate function remain byte/AST-equivalent to commit 17ab4b2a533bc112cfbc8d73796347de94d938b6. Only junit receives an explicit keyword-only external_registration hook. Without it, native source registration is unchanged. Differential tests compare legacy successes/rejections and all 39 missing/unrelated-evidence outcomes. No monkeypatch or mutable global trust context is used by implementation.

Prototype limitations: contexts, registry/checkpoint observations, grants and observed executions are independently injected **synthetic laboratory fixtures**, not real trust services or proofs of actual candidate execution. They do not establish operational reviewer independence, confinement, durable cross-host anti-rollback or authenticated real execution. Source and application exports share one small fixture Git repository in this increment. Only one observed execution per submission and the two original application identities are supported. Prior semantic/migration authorization references are rejected as unsupported. Candidate v2 attestation schema checking and public laboratory signatures do not activate any v1 or operational trust profile. Real providers, enrollment, registry writes, collector/signing custody, durable execution-ledger progression and CI activation remain separately authorized work.

Synthetic reviewer records use a separate acp-phase6-lab-human-review/1 model; accepted v1 schemas/semantics remain unchanged. No accepted_reviews capability is returned. Reservations/exclusions cannot be silently erased. The public private keys are generated from fixed test-only seeds solely inside the test fixture; no operational credentials exist.

Validation and exact per-file hashes are supplied in the external B0 engineering evidence package, not written into historical audit evidence. No live infrastructure, PostgreSQL, application builds, dependencies or CI settings are changed by B0. No commit or push is authorized by this checkpoint. All closure blockers and T09 reservations remain.

---

# ACP Phase 6 — Stage A evidence-admission engineering design

Status: PROPOSED FOR HUMAN ENGINEERING REVIEW. Design only; no implementation or operational authorization.

Reviewed source: `17ab4b2a533bc112cfbc8d73796347de94d938b6`, branch `codex/phase6-generator-0.6-runtime`.

The qualified trusted-JWT concurrency correction remains accepted within its bounded component-test scope. Phase 6 remains IN_PROGRESS, Phase 7 NOT_STARTED, operational security NOT_ESTABLISHED, release closure BLOCKED. No criterion is resolved by this design.

## 1. Evidence baseline and invariants

Source audit: GitHub run `39022667266`, attempt 1, artifact `12098715854`, member `phase6-final-closure.json`.

- Archive SHA-256: `c2c7ccc6116721429a4a9e25fd1ff0dfbd9cf82e951b98f24199ae074d05ed5e`.
- Report SHA-256: `cdacdc6772101092292b8a9b0b250813585c101a60323a8ac38ee6b9b801eb0f`.
- Audit's merged baseline: `7e4e3438179e7a446c5f3737ad1d6d9cb07a96ea`; execution/evaluation commit: reviewed source above. This is not silently replaced by the later frozen engineering checkout baseline.
- 39 criteria, 18 PASS, 21 BLOCKED. Blockers: 5, 8, 9, 10, 12, 13, 14, 15, 18, 20, 21, 22, 24, 25, 26, 27, 28, 30, 31, 32, 33. Each reports MISSING_EVIDENCE.
- All 49 distinct artifacts referenced by admitted criterion records were found in the uploaded archive and matched their hashes.
- Sealed 0.5.0 bundle: `sha256:ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb`.
- Approved Payment Canonical digest: `sha256:d0f6e8d96a07e8e8358ad8f1f558f9ec3d69fd8008cceb75e82f4f695e3cf47d`.
- Approved Case Management Canonical digest: `sha256:5b3a69bb1d6e0e69ed620cd1dd32d10e8a07cec276583055b53ec03bfdcc6b90`.

Invariant: release identity, evidence eligibility, observed execution, predicate satisfaction and human closure authority are separate decisions. Admission cannot alter semantic meaning or authorize migration, deployment, history genesis, a data binding or release promotion.

0.6.0 remains UNSEALED_CANDIDATE. Its existing source fingerprint is not a release seal; its reuse of sealed parent code does not make the candidate equivalent to 0.5.0. Historical V3 physical evidence remains bound to its original exact candidate and archive.

## 2. Existing architecture and precise admission failures

### 2.1 Producer and evaluator

`tooling/audit/phase6.py` runs admission, browser, fault/history, remediation, OIDC, release-upgrade and package producers. In its finalization block it constructs fresh criterion evidence only for 1,2,3,4,6,7,11,16,17,19,23,29,34,35,36,37,38,39. It does not ingest authenticated external records for the remaining criteria.

`tooling/audit/criteria.py`:

- `current_binding()` derives the active bundle, approved Canonical inputs, approval digest and Git execution commit from local trusted audit code.
- `validate_record()` requires matching criterion and binding, an aware evaluation timestamp no more than 24 hours old or five minutes ahead, actual contained artifact files and exact SHA-256 hashes.
- `validate()` dispatches the existing 39 criterion predicates. Status strings alone do not satisfy them.
- `assess()` fails closed and returns individual BLOCKED records. A missing record is MISSING_EVIDENCE, not evidence that an implementation necessarily does not exist.

### 2.2 Native JUnit registration

`junit()` verifies required case names and rejects failed/error/skipped cases. With an execution commit, it resolves the class's simple filename under `targets/spring-vue-postgres/templates/backend/src/test/java`, checks the named method, and requires exact committed source bytes.

Consequences:

1. A correct external test outside that root is unregistered.
2. A similarly named test is not equivalent merely because JUnit says PASS.
3. Adding new witnesses under that root changes sealed generator inputs.
4. Existing source-registration logic does not authenticate an external runner or prove it consumed the registered source. The proposed path must add those checks, not replace source provenance with a name allowlist.

### 2.3 Human review

For criteria 12,13,15,20,26,27,28, `deployment()` requires `deployment-review.json`, explicit human-acceptance/external-obligation fields, and `accepted_reviews[str(criterion)]` equal to SHA-256 of the exact raw review document. `assess()` defaults to an empty map. Current producer calls do not independently populate it.

A candidate-supplied map, review document saying ACCEPT, digest equality, chat message, CI label or test fixture cannot establish reviewer authority.

### 2.4 Existing evidence engineering must be preserved

The existing twelve version-1 record schemas and common definitions provide envelopes, artifact manifests, registrations, challenges, attestations, decisions, registries and trust snapshots. Stage 1 validates structure only. Stage 2A authenticates laboratory registrations against an independently injected laboratory context. Stage 2B-1 reserves laboratory challenges; it does not launch execution, authenticate completed execution or admit closure evidence. The isolation prototype remains blocked for runtime qualification.

The existing reservation ledger cannot record a successful independent execution by itself; a terminal execution/collection proof and any new ledger progression require their separately reviewed execution-stage implementation. This admission design consumes verified proof and does not add success states to the accepted ledger.

No LAB_REGISTRATION_VERIFIED result, reservation, public test signature or synthetic isolation result is upgraded into operational authority. Existing laboratory APIs and schemas retain their current meaning.

## 3. Proposed architecture and outputs

Use an admission gateway outside the generator, with these independently controlled inputs:

1. Immutable audit session context: repository identity, evaluation commit, exact release descriptor, 39-contract set, policy/registry/revocation checkpoints, source/dependency/runner pins, trusted time and permitted purpose.
2. Version-scoped verifier registrations approved by independently authorized custodians and technical/security reviewers.
3. Immutable artifacts plus authenticated independent execution observations.
4. Where applicable, authenticated human decisions and reviewer grants, independent of the test author and candidate workload.

Processing:

`quarantined submission -> structural verification -> trusted-context and registration verification -> independent execution/artifact verification -> per-criterion eligibility -> unchanged semantic predicate evaluation -> bound report`

Workload output is untrusted data. It cannot choose the trust root, evaluator module, registration, scope, expected test list, clock, revocation head, checker executable or human-review registry.

The evaluator must execute from a separately pinned, read-only trusted source/dependency environment, not from imports selected by the candidate checkout or its PYTHONPATH. Candidate and verifier workloads cannot access collector administration, signing credentials, registry writes or ledger writes. A Python context object alone does not enforce this separation.

Outputs:

- `REJECTED`: malformed, unauthenticated, stale, mismatched, revoked or unregistered evidence; reason retained per criterion.
- `ELIGIBLE_FOR_PREDICATE_EVALUATION`: an internal verified input, not PASS or release acceptance.
- `QUALIFICATION_ONLY`: candidate/laboratory observations and applicable predicate evaluations, never release clearance.
- Existing audit PASS/BLOCKED rows: only the original semantic predicate decides satisfaction for an eligible sealed-release context. Human closure remains separate.

No unsuccessful native record may be silently replaced by an external PASS. Registrations define the complete required source set: native and external obligations are conjunctive where both are required. Conflicting records, missing required sources or unexplained duplicate execution identities fail closed. No newest-PASS-wins rule.

## 4. Release scoping

The trusted host chooses one immutable descriptor; candidate declarations must match it.

| Context | Required identity | Permitted disposition |
|---|---|---|
| Sealed 0.5.0 | Exact profile, generator, release-contract bytes and existing bundle seal | Evidence may be evaluated for 0.5.0 only |
| Unsealed 0.6.0 | Exact candidate profile/generator, application source commit/tree, observed candidate fingerprint, parent 0.5.0 seal and ancestry bytes | QUALIFICATION_ONLY |
| Future sealed successor | Independently approved future release descriptor and seal | Unsupported until separately authorized and registered |

A 0.6 witness can test 0.5 only if it actually runs the exact 0.5 subject and has an explicit 0.5 registration. Its own source version is not the application release version. Candidate packages cannot be relabeled parent-release packages.

The release key is SHA-256 over domain-separated JCS of the complete release descriptor, including its SEALED_RELEASE or UNSEALED_CANDIDATE discriminator. No wildcard versions, digest-only aliases, implicit compatibility or inheritance of witness/human acceptance across releases.

Some current predicates contain literal release/baseline assumptions. This design does not generalize those assumptions: if a 0.6 context cannot satisfy an unchanged predicate, record `UNSUPPORTED_PREDICATE_CONTEXT` as BLOCKED in its qualification report. Do not inject a false baseline, substitute the parent seal, or count the result as a resolved release blocker.

## 5. Proposed manifest schema

Proposed companion schema ID: `acp-phase6-evaluation-manifest/1`, JSON Schema Draft 2020-12. This is a new document type; none of the twelve accepted schemas is edited or given a new interpretation.

The manifest is declarative and has no PASS, accepted, authority or waiver property. Its canonical bytes/digest are bound by independently authenticated execution/review proofs. Structural validity or a matching digest alone conveys no authority.

### 5.1 Closed normative data model

Every named object below is closed (`additionalProperties:false`); every listed property is required. Arrays have at most 4096 entries, total artifacts at most 256 MiB, source inventory limits remain the registered profile's existing limits, and the manifest itself is at most 1 MiB. Policy may tighten, never relax, these bounds.

Primitives:

- `Digest`: `sha256:` followed by 64 lowercase hexadecimal characters.
- `Commit`: 40 lowercase hexadecimal characters, verified against immutable Git objects; not a branch name.
- `Id`: existing 32-lowercase-hex record identity.
- `Time`: existing canonical UTC timestamp format, `YYYY-MM-DDTHH:MM:SSZ`, validated calendar/time semantics.
- `RecordRef`: `{schema, payloadDigest:Digest}`; only explicitly supported schemas.
- `ArtifactRef`: exact relative path into the manifest's artifact inventory; not a URL.
- `Criterion`: integer 1 through 39.
- `Application`: PAYMENT or CASE_MANAGEMENT.

```text
EvaluationManifest = {
  schema: "acp-phase6-evaluation-manifest/1",
  repository: "jeresaf/Application-Compiler-Platform",
  manifestId: Id,
  purpose: "SEALED_RELEASE_EVALUATION" | "CANDIDATE_QUALIFICATION",
  release: SealedRelease | CandidateRelease,
  applicationSource: {commit:Commit, treeDigest:Digest, inventory:ArtifactRef},
  evaluator: {commit:Commit, treeDigest:Digest, predicateSetDigest:Digest},
  auditSessionId: existing session identity,
  policyRef: RecordRef,
  registrationCheckpoint: {sequence:nonnegative-safe-integer, digest:Digest},
  applications: nonempty unique ApplicationSubject[],
  approvalReferences: unique PriorApproval[],
  executions: unique Execution[],
  criteria: nonempty unique CriterionSubmission[],
  artifacts: nonempty unique Artifact[],
  createdAt: Time,
  expiresAt: Time
}
SealedRelease = {
  kind:"SEALED_RELEASE", profile:string, generator:string,
  releaseContractDigest:Digest, bundleSeal:Digest
}
CandidateRelease = {
  kind:"UNSEALED_CANDIDATE", profile:string, generator:string,
  candidateSourceDigest:Digest, ancestryDigest:Digest,
  parentProfile:string, parentBundleSeal:Digest
}
ApplicationSubject = {
  application:Application, canonicalDigest:Digest,
  packageDigest:Digest, generatedSourceDigest:Digest, provenanceDigest:Digest
}
PriorApproval = {
  purpose:"SEMANTIC_CONTENT" | "DATA_BINDING" | "MIGRATION_EXECUTION",
  reference:RecordRef
}
Execution = {
  executionId:Id, contractDigest:Digest, challengeRef:RecordRef,
  executorId:existing executor identity, collectorId:existing collector identity,
  environmentDigest:Digest, startedAt:Time, finishedAt:Time,
  provider:HostedExecution | IsolatedExecution
}
HostedExecution = {
  kind:"GITHUB_ACTIONS", repository:string, runId:positive-safe-integer,
  attempt:positive-safe-integer, jobId:positive-safe-integer,
  workflowPath:relative-path, workflowCommit:Commit,
  testedCommit:Commit
}
IsolatedExecution = {
  kind:"ISOLATED_EXECUTOR", hostConfigurationDigest:Digest,
  supervisorDigest:Digest, sessionId:existing session identity
}
CriterionSubmission = {
  criterion:Criterion, predicateContractDigest:Digest,
  registrationRef:RecordRef | null,
  evidenceKind:"AUTOMATED" | "HUMAN_REVIEW" | "COMBINED",
  applicationScope:nonempty unique Application[],
  witnesses:unique WitnessExecution[],
  artifactPaths:nonempty unique ArtifactRef[]
}
WitnessExecution = {
  witnessId:existing witness identity, caseId:existing case identity,
  application:Application, executionId:Id,
  assertionArtifactPaths:nonempty unique ArtifactRef[]
}
Artifact = {
  path:relative-path, role:registered-role, mediaType:registered-media-type,
  size:nonnegative-safe-integer, sha256:Digest
}
```

Additional schema/semantic constraints:

- Source tree digests use the accepted canonical source-inventory algorithm over exact paths, permission modes, byte sizes and hashes, excluding Git metadata. Compare the complete authorized export to immutable Git objects; never silently hash only selected convenient files. Candidate sourceDigest retains its existing native fingerprint algorithm and is a separate typed field, not a substitute tree or seal digest.

- SEALED_RELEASE pairs only with SEALED_RELEASE_EVALUATION; candidate only with CANDIDATE_QUALIFICATION. Profiles/generators must match the independently pinned release descriptor exactly.
- Maximum two application subjects, unique by application; each predicate's complete application coverage is mandatory. Both reference domains remain required where established.
- All collections designated unique are checked by their semantic keys, not JSON Schema `uniqueItems` alone. Witness key: criterion/application/witness/case/execution. Artifact paths and execution IDs are unique. Set-like arrays use existing UTF-16 ordering; ordered command sequences retain order.
- AUTOMATED requires a registration and at least one execution-bound witness. HUMAN_REVIEW requires authorized decisions through the submission index; COMBINED requires both. The registry, not this field, decides which form is permitted for a criterion.
- Artifact roles/media types use the existing closed artifact role/type sets. New roles require separate registration, not arbitrary OTHER data. No executable checker path is accepted from a manifest.
- No symlinks, hardlinks, devices, traversal, absolute paths, duplicate archive members, normalized/case-colliding paths, XML external entities, unbounded entity expansion or oversized/decompression-bomb content. Artifacts are verified from an independently controlled immutable capture; descriptor-based reads avoid path-check/read races.
- Timestamps must be coherent, independently corroborated and current. The existing 24-hour evidence/scan age and five-minute future-skew ceilings are not increased. A recent evaluation timestamp cannot refresh old execution or scanner evidence. Trusted policy can require shorter validity. Human grant/proof time and current revocation are independently checked.
- Every artifact reference must resolve exactly once; all required collected outputs must be inventoried. Unexpected executables/outputs are quarantined, not silently ignored.
- Approval references are pre-existing authorizations with exact purpose. An empty list does not waive criterion 5's required semantic/data-binding/execution authorizations. Admission itself cannot issue those authorizations.
- No legacy record is rewritten, restamped, re-signed or normalized to appear current. Cross-source reuse requires an explicit applicable registration and independently proven subject equality; application changes otherwise require new execution.

### 5.2 Canonicalization, proofs and avoidance of digest cycles

Reuse accepted JCS encoding semantics and integer bounds. Manifest identity is `SHA256(UTF8("ACP-PHASE6-EVALUATION-MANIFEST") || 0x00 || JCS(manifest))`; the digest is external, not a self-referential field. This is distinct from raw artifact SHA-256 and existing record payload digests.

Use an unsigned submission index with exact manifest digest, execution-attestation references, human decision references, raw review-document hashes and trust-snapshot reference. Index entries are untrusted locators; every referenced object is independently verified. The index cannot supply trust roots, accepted_reviews or predicate results.

Dependency order is acyclic:

1. Prior policy/registration/approvals and an execution challenge bind known source/packages and the exact execution contract, not unknown future output hashes.
2. Execution produces immutable outputs. Manifest M inventories those outputs and prior authorizations, but contains no attestation that signs M and no review decision that depends on M.
3. Authenticated attestation A binds M, the challenge, registration, exact release, execution and independently observed source consumption.
4. Human review document R may reference M. Authorized decision H binds M and SHA-256 of the exact raw R bytes. Neither R nor H is inserted into M if doing so creates a cycle.
5. The submission index links M, A, R and H. For existing v1 human records, an existing artifact-manifest/1 may inventory M and R; the human decision binds that inventory and raw R digest. That inventory is not made self-referential.

A candidate identity must not be forced into the sealed-release meaning of an existing v1 binding. Proposed `acp-phase6-evidence/execution-attestation/2` adds a typed release descriptor and manifest digest while retaining exact execution observations, challenge/registration references and termination data. Its complete draft field set is: existing record envelope fields; typed release; applicationSource; evaluator identity; auditSessionId; executionId; challengeRef; registrationRef; manifestDigest; executorId; collectorId; environmentDigest; startedAt; finishedAt; monotonicDurationNanoseconds; termination; resourceLimitEvents; descendantCleanup; observed command/source/dependency/package/assertion inventory digests; and isolation profile digest. Duration is a bounded nonnegative safe integer; resource events and cleanup are independently observed closed records, not candidate success labels. Every object is closed and signatures cover its schema-specific domain-separated canonical payload.

Version-2 attestation authentication and its allowed signing/execution profile require explicit independent contract/security approval. Version-1 policy schema enumerations are not widened silently; an approved externally pinned scope policy must explicitly authorize the new schema/profile. The accepted trust-policy/1 supportedSchemas list does not authorize this v2 type. Its decoder must continue rejecting it. Adoption requires a separately reviewed/authenticated scope-policy or successor policy contract and an independently pinned host context; a candidate cannot extend that list. Such operational policy rollout is outside the first laboratory implementation inventory below. Until that trust/profile authorization and implementation exist, candidate authenticated admission returns BLOCKED/UNSUPPORTED_PROOF_PROFILE. Existing v1 laboratory attestations cannot be relabeled v2 or used as operational proof.

## 6. Criterion-to-witness registration model

The normative criterion set remains exactly 1..39. Freeze a reviewed predicate-contract digest per criterion and a source/dispatch digest for the complete set. Each normative contract inventories the effective criterion definition, all applicable semantic checks/shared prerequisites and required witness identities from the trusted baseline; duplicate source assignments are resolved to the existing effective definition, not an earlier overwritten literal. Define contractDigest as SHA-256 of the domain-separated JCS contract, and predicateSetDigest as SHA-256 of the domain-separated ordered list of all 39 criterion/contractDigest pairs. The trusted evaluator module has an additional exact source hash. Contract adoption and any source-registration refactor require independent equivalence review; a candidate cannot recompute the normative registry from its own edited code. Registrations bind an existing criterion; they cannot define its meaning or lower its requirements.

Required registration view, resolved from independently pinned records:

| Element | Required binding |
|---|---|
| Criterion | Exact number and existing predicate-contract digest |
| Release scope | Exact typed release key and purpose; no version ranges/wildcards |
| Witness | Stable witness ID, complete case IDs and application coverage |
| Assertion contract | Exact reviewed assertions, required observable facts, negative expectations and artifact roles |
| Source | Witness repository/commit, full class/module/method identity, exact files/modes/tree, dependency lock and entrypoint/argv |
| Execution | Permitted executor/collector, exact environment/isolation contract, authorized proof profile and freshness |
| Reviews | Exact technical and security review bindings; required independent principals/grants |
| Registry state | Sequence, predecessor, validity, supersession and current revocation checkpoint |

Reuse verifier-registration/1 only where it accurately represents the registration. The signed `witnessContracts[].assertionContractDigest` can bind an exact companion release-witness-scope contract containing release keys, case identities, dependencies and the above restrictions. The scope document must not contain the digest of its enclosing registration, which would create a cycle. Bare scope documents or registration digests are not authority.

Do not modify the accepted `LabTrustContext` or convert its verification result into an active registration. A new trusted-context boundary verifies eligible registrations against independently authorized configuration. Missing real trust/custody remains BLOCKED. Synthetic laboratory context is separately tagged and can produce QUALIFICATION_ONLY at most.

Native path: default source registration remains unchanged. External path: require a verified registration, exact source and execution attestation, full class/module identity and expected case/assertion inventory. XML alone cannot prove execution. Match observed test identities and counts, reject zero cases, missing/duplicate cases, failures/errors/skips and unapproved reruns/flaky results. Candidate-emitted events are explicitly untrusted.

Examples of mapping, not registrations or approvals:

- #8 -> existing integratedCrossOwnerTransitions contract.
- #9 -> everyTargetObjectHasExactRevisionAndInputDigest.
- #10 -> representativeObjectRuntimeTraceability.
- #24 -> failedBackfillRollsBackDdl and requiredFieldRejectsNull, plus the full existing deployment recovery obligation; two named tests alone do not establish the entire matrix.
- #25 -> restartPreservesAllCommittedRuntimeFamilies.
- #30/#31/#32/#33 -> the existing performance/scaling/independent-clean-build/fresh-hosted witness contracts respectively.
- #5 retains exact approved snapshots/plans, historical authority verification and applied-vs-expected migration checks, plus its required runtime witness. Registration cannot approve a synthetic evolution.
- #12/#13/#15/#20/#26/#27/#28 retain the human deployment-review path; an automated witness cannot replace it.
- All remaining criteria preserve their current dispatch, artifacts and checks. No new criterion number, PASS alias or exception class is introduced.

## 7. Independent evidence verification

1. Acquire records/artifacts into bounded quarantine without running candidate commands or resolving arbitrary remote URLs. Verify safe paths, byte sizes and content hashes.
2. Resolve the evaluator, release and predicate set from trusted configuration. Independently verify Git object/file inventories and candidate parent/ancestry relationships. Do not import candidate code to decide its trust or release identity.
3. Resolve registry/policy/revocation heads from an authenticated source outside the submission. Enforce durable anti-rollback floors, continuity, expiry, supersession and fail-closed outages/conflicts. A supplied checkpoint is a claim until independently verified.
4. Verify registration signatures/roles/reviews/independence and exact criterion/release/application/executor scope. Cryptographic validity does not by itself establish an authorized signer.
5. Verify execution challenge reservation and authenticated terminal execution evidence. Compare actual executable/argv/cwd/environment/dependencies, observed source consumed, generated source/package hashes and isolation identity with the contract. Check normal exit/signal, limits and descendant cleanup. JUnit PASS cannot replace independently observed execution.
6. For GitHub evidence, authenticate repository/run/attempt/job/workflow-source identity and downloaded artifact digest. Successful jobs from a writable candidate workflow are not automatically independently trusted; trusted workflow/executor source must be pinned outside candidate control. GitHub metadata alone does not establish sandbox confinement or signed reviewer independence.
7. Verify expected assertion coverage and artifact contents, not submitted PASS fields. Registrations and criterion predicates remain the authority for expected assertions. Preserve all failed/negative observations.
8. Verify any required human decisions as below. No automatic approval from an engineering acceptance or T09 record.
9. Produce immutable eligible inputs and a per-criterion provenance index. Evaluate the original semantic predicate with the independently pinned audit code. Emit BLOCKED on any missing prerequisite or unsupported release context.

Do not execute a new verifier as part of merely reading a submission. A new execution requires its separately authorized supervised environment. Where independent collection/signing/custody is not implemented or qualified, the verification step fails closed; this design does not claim it exists.

## 8. Human-review registration

The subject is the exact repository, release key, criterion, application/package/snapshot identities, manifest and raw deployment review bytes. Scope cannot expand from laboratory review to operational security or deployment.

Before deriving accepted_reviews, verify:

- Independently trusted human-registry head and continuity, not a candidate-provided JSON registry.
- Reviewer identity, grant, purpose, criterion/application/release scope, validity and independence from authors/executor/custodian as required by policy.
- Authentic signed decision or independently authenticated approval channel, with proof-time key/grant validity and current revocation/compromise history.
- Exact raw `deployment-review.json` bytes, including exclusions/reservations; no newline or Unicode normalization before hashing.
- Decision inclusion in the trusted registry, correct supersession, fresh checkpoint and absence of conflicting current decisions.
- The decision does not exclude the very obligation being claimed satisfied. ACCEPT_WITH_RESERVATIONS cannot become unconditional operational PASS. Unresolved reservations relevant to the criterion keep it BLOCKED.

The legacy map is keyed only by criterion, not application. Its bridge must therefore require one exact deployment-review.json covering the complete required subject set, plus verified authorized decisions covering every applicable application. Several reviewers may approve that same exact document within their respective scopes. Separate per-application review bytes cannot be merged into an invented jointly accepted document or reduced to whichever hash passes; absent an independently authorized joint document, remain BLOCKED or request a separately reviewed contract extension.

Only then derive an ephemeral read-only `accepted_reviews[str(n)] = SHA256(raw_review_bytes)` for the eligible human criteria. Pass it directly to existing deployment predicates; never serialize a caller-trusted map as evidence. Preserve decision/proof/checkpoint references in the audit report. The hash alone remains insufficient.

Idempotent read/re-evaluation of the identical already verified decision is allowed after fresh read authorization and revocation checks. Reuse in a different release/application/criterion or a conflicting checkpoint fails. This mechanism does not issue decisions, grants, keys, operational receipts or journal entries.

T09 remains documentary, self-attested and laboratory-only. It cannot populate deployment acceptance. No identity or key is selected in this design.

## 9. Predicate preservation and infrastructure boundary

Keep the 39 SPECS entries, semantic assertion functions and pass/failure conditions unchanged. This includes:

- Current age/skew limits and exact source/artifact binding.
- Both-domain coverage where required.
- No failed/skipped/flaky cases accepted as successful execution.
- #21's exact coverage requirements and rejection of findings/unknown components.
- #5's existing approval, snapshot/plan and migration checks.
- Human-review hash/authority verification for the seven deployment-review criteria.
- Historical release immutability, support window and explicit human closure authority.

A real integration limitation must be approved, not hidden: the current `junit()` hard-codes the native source root. External registration cannot be supported merely by adding a manifest. Proposed infrastructure-only refactor: add an explicitly supplied immutable witness-verification context to the JUnit source-registration boundary and forward it through dispatch plumbing. Legacy calls use the original native path and behavior. The external path performs stronger authenticated provenance checks against a reviewed exact registration. No global context, monkeypatch, module replacement, status override or fabricated JUnit source file is allowed.

This changes source-registration plumbing, not the semantic assertions or predicate requirements. Independent review must explicitly accept that distinction before implementation. If the restriction is interpreted as freezing every byte of criteria.py, this bridge is not implementable in that scope: remain sidecar/qualification-only and request narrower explicit authorization. Do not claim external witnesses can clear the original evaluator unchanged.

`phase6.py` would accept only a verified, explicitly scoped admission result for additional records and accepted_reviews; it must preserve all native producers and the 18 current records. No input JSON can directly set criterionEvidence. Missing or rejected external evidence remains BLOCKED. Existing no-input invocation retains its current behavior and exit statuses.

Candidate qualification uses a separate explicit mode/entrypoint and cannot change current release rows or feed the mandatory aggregate as release success. Unknown/future sealed releases are unsupported until separately reviewed. No release-contract or version promotion occurs here.

## 10. Negative-test and threat matrix

All tests below are proposed. Pure synthetic fixtures may demonstrate rejection paths, but must be labeled laboratory and cannot generate real approval/admission evidence.

| ID | Adversarial input | Required outcome |
|---|---|---|
| N01 | Fabricated PASS JSON or JUnit without authenticated execution | Reject; no eligible criterion input |
| N02 | Changed artifact byte/size, missing artifact, duplicate archive path | Reject exact artifact binding |
| N03 | Old evidence with a newly written evaluatedAt, future execution or expired scan | Reject; original observations govern freshness |
| N04 | Wrong repository, source commit/tree, package or Canonical digest | Reject subject mismatch |
| N05 | 0.6 package labeled 0.5, parent seal used as candidate seal | Reject release mismatch |
| N06 | Candidate status changed to sealed, unknown future release | Reject; never promote |
| N07 | Unregistered external class/method, same-name unrelated method, extra source file | Reject registration/source mismatch |
| N08 | Replaced checker, dependency lock, executable, argv, cwd or environment | Reject execution-contract mismatch |
| N09 | Known witness registered for wrong criterion/application/release | Reject unrelated scope |
| N10 | Missing expected case, zero cases, duplicate case or assertion artifact | Reject incomplete/ambiguous execution |
| N11 | Failure/error/skip/flaky/rerun represented as clean success | Reject; preserve actual result |
| N12 | Candidate-generated runner event or altered cleanup/termination event | Reject absent authenticated collector observation |
| N13 | Exit/signal ambiguity, timeout, resource violation or surviving descendant | Reject successful execution classification |
| N14 | Unknown signer, changed signature/domain/schema, wrong role or duplicate principal | Reject authentication/threshold |
| N15 | Public laboratory key or LabRegistrationResult offered as operational authority | Reject mode/authority confusion |
| N16 | Stale/rolled-back/forked registry or revocation checkpoint; provider outage | Fail closed; no cached permissive fallback |
| N17 | Replayed nonce/execution for a different manifest; changed source on retry | Reject replay; immutable identical retrieval only after authorization |
| N18 | Review JSON says ACCEPT but no independently registered grant/decision | Reject; accepted_reviews stays empty |
| N19 | Raw review changed, wrong review digest, expired/revoked grant or compromised key | Reject, retain exact historical proof chronology |
| N20 | Author self-review, forbidden role combination or independence claim without proof | Reject independence |
| N21 | T09/laboratory reservations used for deployment, excluded obligation claimed satisfied | Reject scope/decision laundering |
| N22 | Semantic approval reused as data binding, SQL authorization or deployment permission | Reject authorization-purpose confusion |
| N23 | Criterion number/contract/dispatch/checker digest changed | Reject predicate substitution |
| N24 | Candidate-controlled PATH/PYTHONPATH/import or submitted verifier executable | Reject; do not execute from submission |
| N25 | Symlink/hardlink/traversal/device/XML entity/bomb or concurrent artifact replacement | Reject safe capture/integrity |
| N26 | Fresh passing subset hides native failure or earlier failed attempt | Reject incomplete/conflicting evidence; no PASS selection |
| N27 | Old hosted run, wrong attempt/job/workflow, or successful candidate-modified workflow | Reject source/executor trust mismatch |
| N28 | Partial coverage of required Payment/Case domains or deployment obligation rows | Reject incomplete coverage |
| N29 | Hash-cyclic record references or unsupported schema coercion | Reject unsupported/malformed graph |
| N30 | Host/evaluator restart loses checkpoint floor; stale receipt after recovery | Fail closed pending independently verified reconciliation |
| N31 | Caller injects accepted_reviews or an eligible-result object without gateway verification | Reject at trusted entrypoint; object shape alone confers no authority |
| N32 | Candidate qualification result offered to final release aggregate | Reject purpose mismatch; preserve blocked closure |

Security consequence: cryptographic hashes identify content, signatures identify authorized signed statements only after trust verification, and neither alone proves test execution or real-world control effectiveness. Independent execution, collection and custody are separate prerequisites.

## 11. Exact proposed file-change inventory

This is a proposed future first implementation increment, not files changed by Stage A. No new top-level `tooling/*.py` file is permitted: the current generator bundle enumerates those files, so even an unrelated helper there would change the 0.5.0 seal.

New files:

1. `engineering/evidence_admission/scoped/manifest.py` — closed companion parsing and cross-record binding.
2. `engineering/evidence_admission/scoped/context.py` — immutable independently injected scope/trust interfaces; no real provider enrollment.
3. `engineering/evidence_admission/scoped/witnesses.py` — version-scoped source/registration/assertion eligibility.
4. `engineering/evidence_admission/scoped/human_reviews.py` — authenticated review verification and ephemeral accepted-review mapping.
5. `engineering/evidence_admission/scoped/verify.py` — bounded quarantine verification and qualification-only orchestration.
6. `engineering/evidence_admission/scoped/schemas/evaluation-manifest.schema.json` — proposed companion schema.
7. `engineering/evidence_admission/scoped/schemas/release-witness-scope.schema.json` — closed release/registration contract; no trust-root activation.
8. `engineering/evidence_admission/scoped/schemas/execution-attestation-v2.schema.json` — typed candidate/release execution proof proposal, preserving v1.
9. `tooling/audit/scoped_admission.py` — separate audit-side gateway/qualification entrypoint; no candidate code launch.
10. `verification/evidence_admission/scoped/test_manifest.py`.
11. `verification/evidence_admission/scoped/test_witnesses.py`.
12. `verification/evidence_admission/scoped/test_human_reviews.py`.
13. `verification/evidence_admission/scoped/test_adversarial.py`.
14. `verification/evidence_admission/scoped/test_bridge.py`.
15. `docs/phase6-evidence-admission-version-scoping.md` — reviewed specification and compatibility contract.

Existing files proposed for modification:

16. `tooling/audit/criteria.py` — only reviewed source-registration/context plumbing; freeze all SPECS and semantic predicate assertion bodies. Legacy path unchanged.
17. `tooling/audit/phase6.py` — explicit verified admission input and provenance reporting; preserve producers, native records, exit semantics and release boundary.
18. `verification/evidence_admission/test_preservation.py` — exact authorized path/hash/AST allowances only; retain all original baseline/seal/Canonical/history/39-criteria tests.

No changes to the twelve accepted schemas/common definitions, existing Stage 1/2A/2B-1 code or ledger, top-level tooling modules, tooling/tests frozen writer inventory, target templates/worker, release contracts, Canonical IR/vectors or historical reports/decisions.

No dependency installation or new dependency is proposed in this increment. Reuse reviewed encoding/schema/cryptographic primitives where compatible, without changing their existing laboratory API meaning.

CI activation is a separate later authorization. Its proposed exact existing-file scope is `.github/workflows/acp-contracts.yml`, `engineering/ci/parity.py` and `verification/evidence_admission/test_preservation.py`, solely to insert focused isolated tests and exact preservation allowances. No replacement of required commands/jobs/artifacts/services, continue-on-error, weakened aggregate or repository-setting change. The exact CI diff must be reviewed after the source design and prototype pass.

Any need for more files, a new trust-policy wire contract, operational provider implementation, platform changes or dependency changes stops that increment for separate scope review; it is not silently included here.

## 12. Minimal implementation and qualification sequence

1. Human review resolves the admission-plumbing boundary, companion/v2 proof formats, release scopes, authentication profile and required independent roles. Design approval does not activate registrations or trust roots.
2. If explicitly authorized, implement closed parsing, immutable scoped context and pure negative tests. Keep results QUALIFICATION_ONLY using clearly synthetic fixtures. No live workloads, services or signing authority.
3. Implement registration/review verification and the default-preserving bridge only after interface/security review. Differential tests prove every existing legacy input produces its previous result; all negative legacy cases remain rejected. Assert exact 39-contract identity and native no-input 18/21 outcome.
4. Independently review source provenance, role separation, manifest graph, freshness, anti-rollback, filesystem capture, execution-proof authenticity and all N01–N32 cases. This does not establish host confinement or operational custody.
5. Separately authorize focused CI integration. Preserve existing Stage 1/2A/2B and full compiler/Phase 5/Phase 6/closure gates. Demonstrate that a focused test failure fails contracts and aggregation.
6. Separately select/authorize real trust/execution/collection infrastructure, attestations and reviewer enrollment only if required. Existing blocked isolation/security gates remain in force. No real acceptance may be produced before those controls are qualified.
7. After substantive remediation, perform full exact-source hosted qualification and evaluate every criterion. Admission success alone neither resolves a criterion nor closes Phase 6.

## 13. Independent engineering-review checklist

- [ ] Exact reviewed source, audit artifact/report hashes and 39 criterion identities match this baseline.
- [ ] All semantic predicate bodies and SPECS remain unchanged; context forwarding contains no alternative PASS route.
- [ ] Native JUnit behavior remains identical by default; external lookup is exact-source and fully scoped, not a name allowlist.
- [ ] No submitted source/configuration controls evaluator imports, policy, trust roots, clocks or expected assertions.
- [ ] Candidate/parent/released identities cannot alias; historical evidence cannot be transferred or restamped.
- [ ] Manifest schema is closed, bounded and canonical; reference graph has no self-hash/signature/review cycles.
- [ ] Version-1 record semantics and laboratory-only guarantees are preserved; version-2 acceptance requires explicit independent approval.
- [ ] Execution and collection authenticity prove actual source/package consumption; JUnit and candidate events are not treated as independent proof.
- [ ] Human authority, grants, independence, exact raw-review hash, reservations and current/historical revocation are verified.
- [ ] Admission cannot create credentials, approvals, accepted history, migration permission or deployment permission.
- [ ] Replay, fork, stale checkpoint, outage and restart recovery fail closed.
- [ ] Expected domains/cases/artifacts are complete; failures, skips, reruns and conflicting records cannot be hidden.
- [ ] N01–N32 reject the intended inputs; positive laboratory fixtures cannot pass operational or release mode.
- [ ] Original checkout, 0.5.0 seal, 0.6.0 unsealed status, frozen ledger/inventories and historical physical evidence remain unchanged.
- [ ] All T09 reservations and outstanding operational controls remain; the separate opt-in PostgreSQL skip is not inferred PASS.
- [ ] Required CI jobs/artifacts/gates are unchanged until their exact separate integration authorization.
- [ ] No blocker is marked resolved by design, structural validity, registration validity or admission eligibility.

## 14. Decisions required before implementation

1. Approve or reject the exact infrastructure-only source-registration refactor, including the interpretation of “no predicate changes.”
2. Approve or revise the companion manifest, typed release scope, v2 execution-proof draft and acyclic submission graph. This is contract review, not trust-root approval.
3. Confirm that candidate mode is always qualification-only and unsupported literal release contexts remain BLOCKED.
4. Designate the roles responsible for registration custody, technical/security review, execution/collection trust and human-review verification; do not infer appointments from this document.
5. Authorize the exact 18-file laboratory implementation scope, or narrow it. This is a future authorization request, not authorization supplied by Stage A.

No policy, registration, reviewer, endpoint, key, execution, approval, receipt or evidence was created. No engineering regression suite, build, live infrastructure operation or destructive operation was run for Stage A. Only read-only source inspection and document consistency checks were performed. Repository files are unchanged; this specification is outside the checkout.

PHASE6_CLOSURE_BLOCKED

PHASE6_RELEASE_CLOSURE_BLOCKED
