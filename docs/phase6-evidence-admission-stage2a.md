# Stage 2A laboratory registration verification

Accepted Stage 1 baseline: `f44f8952ba7e86f879b0c21e1b56de9fbd3d01aa`.

This is laboratory-only engineering. It verifies signed registrations against
an explicitly injected, immutable laboratory context. It does not discover trust
from candidate files/environment variables, enroll keys, activate registrations,
authenticate execution, admit evidence, issue human deployment acceptance or
integrate with the closure evaluator. Test keys and reviews are public synthetic
fixtures and convey no operational authority.

## Implementation inventory

New source:

- `engineering/evidence_admission/signatures.py`
- `engineering/evidence_admission/trust.py`
- `engineering/evidence_admission/registration.py`
- `engineering/evidence_admission/requirements.txt`

New tests:

- `verification/evidence_admission/stage2a/lab_fixtures.py`
- `verification/evidence_admission/stage2a/test_signatures.py`
- `verification/evidence_admission/stage2a/test_trust.py`
- `verification/evidence_admission/stage2a/test_registration.py`

This document is the ninth new file. The only existing file changed is
`verification/evidence_admission/test_preservation.py`: one exact Stage 2A file
inventory, two exact file-membership predicates, and one additional preservation
test. Every existing method and module statement is compared by AST with the
accepted baseline, permitting only those two predicate additions.
Existing broad Stage 1 allowances are not expanded; Stage 2A additions must
match the nine exact paths. Existing transient contracts-binding validation,
the 852-file baseline checks, exact authorized Stage 1 workflow insertion,
39 criteria, Canonical digests, seal and historical blocker checks remain.

No workflow, audit, schemas, Stage 1 encoding/structural validators, top-level
tooling, generator source, Canonical artifact or historical decision is changed.
The new paths are outside the current generator bundle enumeration.

## Verification and authority separation

The existing `parse_canonical`, `payload_digest`, `signature_input`,
`validate_structure` and closed schemas are reused without modification.
The Stage 1 result remains `STRUCTURE_VALID_UNTRUSTED` or `STRUCTURE_INVALID`.

`verify_ed25519(public_key, signature, message)` uses PyCA's Ed25519 verification
and exposes no signing operation. `verify_record_signatures` verifies every
signature over the existing domain-separated bytes. It rejects unknown keys,
wrong principal ownership/roles, duplicate principals, ambiguous public-key or
key-ID aliases, expired/revoked keys, invalid surplus signatures and insufficient
thresholds. Two keys belonging to one principal cannot satisfy two signers.
Only tests import private-key/signing APIs.

`LabTrustContext` is a frozen object supplied by an independently controlled
laboratory harness. It copies collections to tuples/frozensets, rejects mutable
byte buffers and ambiguous heads/key identities, and binds repository, policy
digest/sequence/floor, old policy, public-key fingerprints/ownership, roles,
thresholds, reviewers, author exclusions, trusted UTC time, revocation checkpoint,
expected registration head, source/dependencies/witnesses/environment and scope.
Public-key fingerprints are SHA-256 over exact 32-byte Ed25519 public keys.

Python object construction is not proof of harness independence. A malicious
caller with control of the verifier process can construct its own context. This
implementation assumes the stated external injection boundary; it does not claim
to enforce process isolation or operational authority custody. No environment
variable or candidate record automatically becomes a trusted context.

`verify_lab_policy` requires the exact externally pinned policy digest, sequence
and checkpoint floor, explicit authorized policy signers, thresholds, role map,
criterion contracts and independence contract. A null predecessor does not
establish initial trust. Replacement requires the independently pinned previous
policy, exact predecessor digest, sequential version and previous policy's
custodian authorization. The new policy cannot authorize its own adoption.

Revocation is an immutable laboratory view, not a network service or operational
registry. Its content digest covers sequence, observation/expiry, complete flag,
revoked keys/principals/records. It must match the external checkpoint exactly;
missing, incomplete, stale, rolled-back or conflicting views fail closed. Trusted
time is injected; candidate time is never authoritative. The policy freshness
limit also bounds checkpoint age. No durable rollback/replay guarantee is claimed.

## Registration and review binding

`authenticate_lab_registration(raw, policy_raw, source_root, context)` validates
Stage 1 structure/schema, external policy/revocation, all custodian signatures,
independent review context, exact source/dependencies/entrypoint, criterion and
witness scope, required applications, executor/environment scope, validity,
revocation, expected head and supersession. Success returns only:

```
LabRegistrationResult(
    registration_digest, verifier_id, policy_digest, signer_ids,
    status="LAB_REGISTRATION_VERIFIED", laboratory=True
)
```

It is a plain laboratory result, not a signed receipt or authorization capability.
No activation/registry-writing API exists. Exact re-verification is idempotent;
old or mismatched registration heads fail. Head checkpoints are supplied by the
harness; no registration sequence is invented in the existing version-1 schema.

The review subject excludes exactly `technicalReviewDigests` and
`securityReviewDigests` from the otherwise complete registration payload:

```
SHA256("ACP-PHASE6-REGISTRATION-REVIEW-SUBJECT\0" || JCS(projected payload))
```

The whole final registration, including review references, is signed by
custodians. This avoids a review/registration digest cycle without unbinding
source, policy, scopes, validity or supersession.

Bare review digests are never sufficient. They must resolve to exact review
bytes already supplied through the independent synthetic review context.
The closed laboratory review object binds schema, subjectDigest, purpose,
reviewerId, criteria, applications, issuedAt and expiresAt. Its SHA-256 is the
registration's review reference. Eligibility, purpose grants, independence,
scope, validity, reviewer keys/roles and revocation are checked. Technical and
security reviewers must be distinct. Candidate authors cannot substitute.
Custodian/reviewer combination is forbidden unless the independently pinned
independence contract explicitly permits it. Both permitted and forbidden
laboratory combinations are tested.

This is not cryptographic authentication of a real human review. The review
context is trusted test input; real human identities, signatures, enrollment and
deployment acceptance remain separately authorized later work.

## Source identity and nonexecution

The canonical source inventory contains `schema` and `files`. Every file row
contains exactly relative path, full permission mode, byte size and SHA-256.
Files sort by UTF-16 path ordering. The tree identity is:

```
SHA256("ACP-PHASE6-VERIFIER-SOURCE\0" || JCS(source inventory))
```

The actual inventory must equal the externally pinned inventory, not merely a
candidate-supplied digest. Missing/additional/replaced files, executable-mode
changes, links, traversal, ambiguous paths and unreadable enumeration fail.
Source is bounded to 4096 files/8 MiB for this laboratory profile.

Require an ordinary Git checkout at the exact supplied root. Read HEAD/tree/blob
objects and compare actual bytes and executable modes with the pinned source
commit. Entrypoint, dependency manifest and assertion-contract files must be
present with exact identities. No status/checkout/clean-filter/hook/submodule
operation or candidate entrypoint runs. `/usr/bin/git` is invoked for built-in
read operations with a constrained environment, global/system configuration
disabled, hooks/fsmonitor disabled and replacement objects disabled. Candidate
Git/PATH/loader environment redirection is not inherited.

Git metadata is excluded from the source inventory. Submodules, linked worktrees
and source-build fallbacks are not supported by this profile. Concurrent hostile
filesystem mutation, privileged same-UID/root attacks and production confinement
are not established; the source must be independently controlled during inspection.

## Isolated dependency profile

The lock retains all six Stage 1 dependencies and adds only cryptography 50.0.2,
cffi 2.1.1 and pycparser 3.11. It pins one publisher-verified wheel hash per package
for Ubuntu 24.04 x86-64 / ordinary CPython 3.14.7. Free-threaded Python, other
architectures and source builds are outside this lock's support.

Installation used a disposable `/tmp/acp-stage2a-3147-venv`, the official Actions
Python 3.14.7 distribution, and a local wheelhouse. All nine actual wheel digests
were compared to their exact PyPI release metadata before installation.

```sh
env LD_LIBRARY_PATH=/tmp/acp-stage1-python3147/lib \
  /tmp/acp-stage1-3147-venv/bin/python3.14 -m venv /tmp/acp-stage2a-3147-venv
env LD_LIBRARY_PATH=/tmp/acp-stage1-python3147/lib \
  /tmp/acp-stage2a-3147-venv/bin/python3.14 -m pip install \
  --no-index --find-links=/tmp/acp-stage2a-wheels \
  --require-hashes --only-binary=:all: \
  -r engineering/evidence_admission/requirements.txt
```

The downloaded Actions interpreter requires
`LD_LIBRARY_PATH=/tmp/acp-stage1-python3147/lib` in this local environment. Its
version is CPython 3.14.7 (GCC 13.3.0). Hosted setup-python normally configures its
own library path. No system installation or sealed dependency file was changed.

License inventory: attrs/jsonschema/jsonschema-specifications/referencing/rpds-py
MIT; cffi MIT-0; cryptography Apache-2.0 OR BSD-3-Clause; pycparser BSD-3-Clause;
tzdata Apache-2.0. Wheel license-file paths and package hashes are retained in
the ephemeral local dependency report. No legal approval is issued.

Installed cryptography reports `OpenSSL 4.0.3 29 Sep 2026`. A fresh OSV querybatch
of the nine exact Python package versions returned nine results with no matched
advisories. This is a dated observation, not a vulnerability-free guarantee.
OpenSSL's published 4.0 advisory page identifies 4.0.3 as the September security
update. Reassess before a hosted or operational checkpoint; preserve future
findings rather than suppressing them.

Sources:

- https://cryptography.io/en/50.0.2/hazmat/primitives/asymmetric/ed25519/
- https://cryptography.io/en/50.0.2/installation/
- https://pypi.org/pypi/cryptography/50.0.2/json
- https://api.osv.dev/v1/querybatch
- https://www.openssl-library.org/news/vulnerabilities-4.0/
- https://www.rfc-editor.org/rfc/rfc8032 (section 7.1 TEST 1 and TEST 2)

## Regression coverage and verification commands

The tests cover the preparation report's 26 cases: valid signature; changed
payload/source/dependency digest; unknown key; wrong role; self-registration;
unauthorized custodian; duplicate principals; insufficient threshold; wrong
algorithm/domain; expired/revoked registration; revoked key; unavailable policy;
policy rollback; conflicting checkpoints; unsupported version; missing technical
or security review; wrong criterion/application scope; replaced source;
superseded replay; candidate-controlled policy. Additional cases cover invalid
surplus signatures, key aliases, immutable context, missing revocation, permission
modes, Git object/source mismatch, symlinks, untracked source, environment
redirection, exact review projection, role combinations and idempotence.

```sh
env LD_LIBRARY_PATH=/tmp/acp-stage1-python3147/lib \
  /tmp/acp-stage2a-3147-venv/bin/python3.14 \
  -m unittest discover -s verification/evidence_admission/stage2a -v
env LD_LIBRARY_PATH=/tmp/acp-stage1-python3147/lib \
  /tmp/acp-stage2a-3147-venv/bin/python3.14 \
  -m unittest discover -s verification/evidence_admission -v
env LD_LIBRARY_PATH=/tmp/acp-stage1-python3147/lib \
  /tmp/acp-stage2a-3147-venv/bin/python3.14 \
  -m unittest discover -s verification/ci -v
git diff --check
```

`stage2a/` deliberately has no `__init__.py`; the original Stage 1 invocation
continues to run every original test without importing optional cryptographic
dependencies. Stage 2A requires the explicit separate invocation above.

Local checkpoint results: 52 Stage 2A tests, 42 Stage 1/preservation tests
(all 41 existing tests plus the exact-inventory test), and 26 CI regression
tests pass, with no skips. RFC 8032 TEST 1 and TEST 2 pass and reject changed
messages. `pip check` and whitespace validation exit 0. The full hosted audit
has not been run for this checkpoint.

Dependency versions and exact selected wheel SHA-256 hashes are in the isolated
requirements file. Python is 3.14.7; pip is 26.2.1; Node is 24.21.0. Temporary
local logs are `/tmp/acp-stage2a-final-tests.log`,
`/tmp/acp-stage2a-stage1-regressions.log`, `/tmp/acp-stage2a-ci-regressions.log`.
The dependency/license inventory and dated advisory response are
`/tmp/acp-stage2a-dependencies.json` and `/tmp/acp-stage2a-osv-response.json`.
These are ephemeral local observations, not immutable hosted acceptance evidence.

The implementation request names F13–F15 without supplying their numbered
definitions. This checkpoint does not invent historical finding dispositions.
For technical review, the implemented coverage is signature/key/role integrity,
external policy/review/checkpoint binding, and exact source/dependency integrity.
Confirmation of any external F13–F15 numbering remains a review item.

## CI proposal — not applied

Preserve the current Stage 1 command. After it, propose two mandatory contracts
steps: create an isolated evidence-admission `.venv` and install this complete
lock with `--require-hashes --only-binary=:all:`; then run explicit Stage 2A
discovery with that environment's Python. Keep all existing jobs, commands,
artifacts, services, pins and release/aggregation gates. Update preservation
checks only for the exact separately approved additions, and test intentional
Stage 2A failure propagation. No workflow or repository settings are changed now.

Recommended next hosted checkpoint: independent review of this source and lock,
separate authorization of the exact CI diff, focused regressions, then one
substantive commit/push and complete hosted verification. No evidence-only push
chain or full Phase 6 audit is needed solely for this local laboratory checkpoint.

## Preserved boundaries

No operational keys, identities, registration activation, execution attestation,
human deployment decision, external evidence admission, accepted-history genesis,
data binding, migration SQL or deployment is authorized or performed. The external
context boundary, synthetic reviewer independence, in-memory rollback checkpoints,
hosted execution and operational custody still require independent review.

T09 remains HUMAN_DECISION_RECORDED / ACCEPT_DELIVERABLES_WITH_RESERVATIONS,
laboratory only. A06-06/A14-06/A17-16 remain INCOMPLETE; A09-08 remains BLOCKED.
All 21 Phase 6 closure blockers remain. No Stage 2B, Stage 2C or Phase 7 work begins.

Phase 6 = IN_PROGRESS

Phase 7 = NOT_STARTED

Operational security = NOT ESTABLISHED

Release closure = BLOCKED
