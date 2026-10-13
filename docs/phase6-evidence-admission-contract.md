# Phase 6 evidence contracts — Stage 1

Version: `acp-phase6-evidence/*/1`. Authorization baseline:
`c1a201c779621963b0334a1bee4423b23315884f`.

This implementation validates structures only. A matching digest, correctly
encoded signature, asserted reviewer, declared test outcome or synthetic policy
never grants authority. No signature is verified, no clock/revocation/trust
service is consulted, no admission receipt or human decision is issued, and no
`accepted_reviews` mapping is created. Existing audit producers and predicates
are untouched. The synthetic fixtures include documents *shaped like* decisions
and receipts; they are not human acceptance records or operational receipts.

## F05–F09 dispositions

| Finding | Stage 1 resolution |
| --- | --- |
| F05: machine-readable contracts | Twelve Draft 2020-12 closed record schemas plus common definitions under `engineering/evidence_admission/schemas/`. Every object rejects additional properties; every listed property is required. Nullable fields use explicit unions. |
| F06: RFC 8785 interoperability | UTF-8 JCS for null, booleans, strings, arrays, objects and signed safe integers. UTF-16 code-unit property sorting; no normalization. RFC property-order/escaping vectors and independently implemented Node serialization exercise compatibility. Noninteger numbers are outside the approved contract domain, not approximated. |
| F07: process termination | Closed disjoint `NORMAL_EXIT {exitCode:0..255}` and `SIGNAL {signalNumber:1..255,coreDumped:boolean}` unions. Negative exit-code shorthand, missing signal data, and mixed exit/signal properties are invalid. A signal/nonzero exit is structurally representable but cannot establish successful execution. |
| F08: reference identity | Every record reference contains exact `schema` and `payloadDigest`. A policy has `predecessorPolicyRef`, not a reference to its own digest. Other records reference the applicable policy. Raw artifact digests and record-payload digests are distinct typed positions. Structural graph checking rejects missing/type-confused/binding-confused references. |
| F09: validity vs authority | Public validators return only `STRUCTURE_VALID_UNTRUSTED` or `STRUCTURE_INVALID`. No authentication, registration, admission, release disposition or operational activation exists in this stage. |

F05–F09 are bounded structural engineering resolutions. Verifier equivalence,
real trust roots, executor authentication, human independence and offline
revocation remain separate decisions and implementation stages.

## Wire contract and digest construction

Every record is a closed object with exactly:

```
payload: closed record-specific object
payloadDigest: "sha256:" + 64 lowercase hex digits
signatures: nonempty ordered set of signature structures
```

Every payload includes `schema`, `recordId`, `repository`, `issuedAt`, `expiresAt`.
All except trust policy also require `policyRef`. Wire identifiers and schema
`$id` values are exactly `acp-phase6-evidence/<record-type>/1`.

`recordId` is 32 lowercase hex digits; commits are 40 lowercase hex digits.
Repository is exactly `jeresaf/Application-Compiler-Platform`. UTC timestamps
are real calendar dates in `YYYY-MM-DDTHH:MM:SSZ`; offsets, fractions, leap-second
shorthand and trailing characters are invalid. Issue time must precede expiry.
Date order is structural; present-time validity is not checked in Stage 1.

Identity strings use closed ASCII namespaces (`principal:`, `key:`, `verifier:`,
`executor:`, `registry:`, `grant:`, `session:`, `admission:`, `collector:`) followed
by 1–64 lowercase alphanumeric/hyphen characters, beginning alphanumeric.
Role-specific properties require their exact namespace. Case/witness IDs have
separate closed patterns in common definitions; no whitespace aliases occur.

Signature structures contain exactly `signerId`, `keyId`, `algorithm`,
`signature`. Algorithm is the literal `Ed25519`. Signature encoding is canonical
unpadded base64url for exactly 64 bytes; nonce encoding is canonical unpadded
base64url for exactly 32 bytes. Padding and alternate trailing-bit encodings
are rejected. These are syntax checks only; zero signature bytes in fixtures
are intentionally unauthenticated.

```
P = RFC8785_JCS(payload)
payloadDigest = "sha256:" + hex(SHA256(P))
signatureInput = UTF8("ACP-PHASE6-EVIDENCE\0" + payload.schema + "\0") || P
```

The digest excludes outer signatures and itself. Signatures are proposed to
cover the entire payload and schema-specific domain prefix; Stage 1 only
prepares bytes. `payloadDigest` matching is structural consistency, not authority.
Different signature sets can share a payload identity. Policy authorization of
signers and signature thresholds belongs to later stages.

Record references are `{schema,payloadDigest}`. A reference never means a raw
archive hash or hash of the signed outer wrapper. Artifact hashes are over exact
artifact bytes; `deploymentReviewDigest` is over the entire exact raw review
document as required by the existing validator. Stage 1 does not read artifacts.

The first policy has sequence 0 and null predecessor; later policies refer to
the preceding policy, which would govern authorization of the update. An
external trust anchor would govern the initial policy. No initial policy becomes
trusted merely by using null. Human grants use IDs, with decisions indexed by a
later registry checkpoint, avoiding a registry/decision content-hash cycle.
Subjects contain package/snapshot identities, not their own manifest reference.
Bootstrap and revocation sequence shapes are checked, not their authenticity.

## Schema inventory

The JSON schemas are the normative complete field/type definitions. Common
definitions are shared through the explicit local alias
`urn:acp-phase6-evidence:common:1`; no network retrieval is permitted. The alias
is a schema-resolution name, not an issuer or authority identity.

| Record type | Required record-specific fields |
| --- | --- |
| `engineering-envelope` | binding, subjects, criteria, registrationRef, attestationRef, manifestRef, challengeRef |
| `verifier-registration` | verifierId, source, criteria, witnessContracts, requiredApplications, environmentContractDigest, executorIds, technicalReviewDigests, securityReviewDigests, supersedes |
| `execution-attestation` | executionId, challengeRef, registrationRef, binding, subjects, executorId, collectorId, environmentManifestDigest, startedAt, finishedAt, termination, cases, manifestRef, collectorSourceDigest, candidateEventDigest |
| `artifact-manifest` | executionId, binding, artifacts |
| `human-decision` | reviewerId, grantId, scope, disposition, reservations, exclusions, independenceEvidenceDigest, supersedes |
| `human-registry` | registryId, sequence, predecessorRef, grants, decisionRefs, revocationHeadRef, revocationSequence |
| `revocation` | registryId, sequence, predecessorRef, action, targetRef, replacementRef, effectiveAt, reasonCode |
| `admission-receipt` | admissionId, auditSessionId, envelopeRef, binding, subjects, criteria, verifierRegistrationRef, trustSnapshotRef, humanDecisionRefs, manifestRef, predicateResults, ledgerSequence, predecessorReceiptRef |
| `admission-rejection` | auditSessionId, submittedObjectDigest, stage, reasonCodes, relatedRefs, trustSnapshotRef, ledgerSequence, predecessorRecordRef |
| `trust-policy` | predecessorPolicyRef, sequence, supportedSchemas, signerRoles, thresholds, criterionContracts, freshness, independenceContractDigest |
| `trust-snapshot` | snapshotSequence, predecessorRef, verifierRegistrationRefs, humanRegistryRef, revocationHeads |
| `execution-challenge` | auditSessionId, nonce, binding, subjects, criteria, registrationRef, issuerId |

`Binding` contains execution/evaluation commits, source-tree/bundle/approval
digests and an exact two-key Canonical digest object. `Subject` contains one
application identity (PAYMENT or CASE_MANAGEMENT), snapshot and package digests.
`SHARED_HOST` is representable only on case results; registration/policy must
later establish whether that coverage is sufficient. Every criterion is 1–39;
human decision scope is restricted to deployment criteria 12,13,15,20,26,27,28.
The existence of a scope field cannot authorize that scope.

All arrays are bounded to 4096 elements and are unique. Set arrays additionally
declare `x-set-key`, which this structural validator enforces. Empty key lists
mean scalar identity. Compound keys are compared lexicographically with UTF-16
string ordering. Applications sort by application identity; artifacts by path;
case results by application/witness/case; signatures by signer/key; registrations
by criterion/witness; grants by grant ID; references by payload digest (or by
schema/digest for heterogeneous references). This dialect requirement is in
addition to standard JSON Schema `uniqueItems`; using an ordinary validator
without the custom set checks is insufficient.

Manifest/entrypoint paths are bounded ASCII relative paths with portable
alphanumeric/underscore/hyphen-leading segments and optional dots thereafter.
Absolute paths, drive prefixes, backslashes, empty/dot/dot-dot segments, control
characters and trailing separators are rejected. No file is opened or extracted.

`REVOKE` requires null replacement; `REPLACE` requires a different reference of
the same record type. This is shape checking, not permission to revoke anything.
Registration criteria must match witness-contract criteria; receipt criteria
must match predicate-result criteria. Every result remains an untrusted claim.

## Canonicalization and API

RFC source: https://www.rfc-editor.org/rfc/rfc8785, particularly 3.2.2 and 3.2.3.
The RFC's supplementary-character property-order vector is checked against its
published expected order, not Python `sort_keys`. String escaping is checked
byte-for-byte. Independent Node primitive serialization and UTF-16 sorting
check nested objects, integer-like keys, Unicode, control characters and both
safe-integer boundaries.

The permitted numeric subset is signed integers from -(2^53-1) to 2^53-1.
Record schema numeric properties further restrict them to nonnegative ranges.
Fractions, exponent notation, Python floats, NaN/Infinity, unsafe integers and
negative-zero input are rejected. This is JCS compatibility for the approved
value subset, not a general floating-point JCS implementation.

```
canonicalize(value) -> canonical UTF-8 bytes or EncodingError
parse_canonical(bytes) -> permitted JSON value or EncodingError
payload_digest(payload) -> content digest (no authority)
signature_input(payload) -> proposed bytes (no signing)
validate_structure(bytes) -> StructuralResult
validate_bundle(list[bytes]) -> StructuralResult
```

`validate_structure` validates a single record without resolving referenced
objects. `validate_bundle` checks a closed supplied reference graph, duplicate
record identities, exact reference types/digests and common binding agreement.
Both return only `STRUCTURE_VALID_UNTRUSTED` or `STRUCTURE_INVALID` plus reasons.
They do not read artifact paths, verify signatures, check present-time freshness,
make grants, execute tests, register records or modify audit state. A failed test,
signal termination or historically expired claim can be structurally valid.
Later authenticated admission must reject it when inappropriate for acceptance.

The parser accepts bytes only, rejects duplicate keys before schema evaluation,
preserves Unicode without normalization and verifies exact canonical byte
equality. It rejects malformed UTF-8, lone surrogates, unsupported versions and
unknown fields at every depth. Limits: 4 MiB per serialized record, 64 nested
levels, and 128 records per supplied bundle. These are local structural bounds,
not operational workload policy. No files are extracted and no URLs fetched.

## Local verification and preservation

Run from the repository root using the existing pinned isolated environment:

```sh
.venv/bin/python3.14 -m unittest discover -s verification/evidence_admission -v
git diff --check
git diff --exit-code --diff-filter=MDRT c1a201c779621963b0334a1bee4423b23315884f --
```

The last command checks modifications, deletions, renames and type changes to
tracked baseline files; preservation tests also restrict tracked and untracked
additions to this stage's authorized paths. This works before and after commit.
Tests check all
852 baseline files, all 39 criterion definitions, the preserved 18-pass/21-blocked
historical report, approved snapshot digests and the actual sealed bundle hash.
They do not rerun the closure audit or claim a fresh closure verdict.

Final local command observations are recorded below. The Python executable in
the existing environment is 3.14.4, not hosted CI's pinned 3.14.7; no toolchain or
workflow pin was changed. Node is 24.21.0 and jsonschema is 4.26.0. This local
checkpoint is not hosted exact-toolchain validation.

| Command | Exit/result |
| --- | --- |
| `.venv/bin/python3.14 -m unittest discover -s verification/evidence_admission -v` | 0; 27 tests, no skips; includes all 12 schema fixtures, adversarial mutations, Node interoperability and preservation |
| `git diff --check` | 0 |
| `git diff --exit-code --diff-filter=MDRT c1a201c779621963b0334a1bee4423b23315884f --` | 0; no baseline modifications/deletions/renames/type changes |

The temporary local test log is `/tmp/acp-stage1-tests.log`; it is ephemeral,
not immutable hosted evidence. The full hosted audit was deliberately not run
for this isolated Stage 1 checkpoint. No commit or push is authorized here.

Eleven existing corpus JSON checkout representations contain CRLF differences
from their Git blobs. They were not rewritten by this task. Their exact local
SHA-256 hashes are pinned in `test_preservation.py`; only the exact baseline blob
or that exact pre-existing representation is accepted, with an additional
line-ending-equivalence check. This qualification is explicit, not a claim that
every local raw byte already equals the Git blob. All other baseline files must
match raw Git bytes exactly. No approved Canonical content is changed.

New paths are confined to `engineering/evidence_admission/`,
`verification/evidence_admission/` and this document. These are excluded by the
current sealed bundle enumeration. No top-level tooling, contracts, target
templates, workflow, historical evidence or approval records are modified.

## Unresolved human decisions and Stage 2 boundary

No actual issuer, key, reviewer, host, custodian, service or registry is enrolled.
Threshold/freshness values in synthetic fixtures are illustrative data, not
selected operational policy. The earlier proposed 15-minute offline horizon is
not activated. Real trust, execution provenance, policy distribution, reviewer
independence, revocation completeness, rollback/replay storage and recovery
remain separately authorized work.

Recommended Stage 2: independently review each criterion equivalence contract
and authorize a narrowly scoped laboratory verifier-registration/authentication
prototype with synthetic identities. Keep audit integration, real signing,
human acceptance registration, authority provisioning, genesis, data bindings,
migration SQL, deployment and repository settings excluded until separately
approved. Stage 1 does not prove any of those properties.

T09 remains HUMAN_DECISION_RECORDED / ACCEPT_DELIVERABLES_WITH_RESERVATIONS,
laboratory only and not independently authenticated. A06-06, A14-06 and A17-16
remain INCOMPLETE; A09-08 remains BLOCKED. All 21 closure blockers remain.

Phase 6 = IN_PROGRESS

Phase 7 = NOT_STARTED

Operational security = NOT ESTABLISHED

Release closure = BLOCKED
