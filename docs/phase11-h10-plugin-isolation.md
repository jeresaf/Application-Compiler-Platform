# H10 — hostile plugin execution boundary assessment

Review baseline: `396b263683f0e57aa9ed0be431d863304279aafb`, `codex/phase11-hardening`.
Date: 2026-11-23, Africa/Kampala. **Architecture recommendation only. SEC-01 remains BLOCKED.**
No security-owner decision, operational approval, new generator, execution profile or authority is created.
H9 and H9.1 remain engineering-qualified. Phase 11 remains IN_PROGRESS; Phase 12 NOT_STARTED;
Phase 6 release closure remains BLOCKED (39 predicates: 18 PASS, 21 BLOCKED).

## Decision requested

Recommend **B: independently supervised, isolated execution for an optional hostile-plugin capability**,
initially qualified only in an explicitly approved disposable VM laboratory. Keep trusted internal
candidate execution as its existing, explicitly trusted engineering API. Never route an untrusted
candidate into that API as a fallback. This is a recommendation, not selection or activation.
The owner can instead select A and explicitly exclude hostile executable extensions from the
supported product profile. A must enforce authentic pre-import admission; today's fingerprints
and hard-coded imports alone do not implement that policy.

B suits charter §§30,36 and open investigations P-08/P-11: extension adapters remain outside the
semantic core and return Target IR/ArtifactPlan data through existing ports. A smaller reviewed
trusted-only offering is also architecturally valid; the charter does not require arbitrary uploaded
code to execute. B introduces security, maintenance and performance costs that need approval.
Do not promise unrestricted plugin language or native executable compatibility in its first scope.

The exact owner requests and proposed test inputs/outcomes are in
[assessment.json](../reviews/phase11-h10-20261123/assessment.json) and
[adversarial-tests.json](../reviews/phase11-h10-20261123/adversarial-tests.json).
Neither file is an approval, signed attestation or operational admission record.

## Existing execution paths and where trust begins

The [source index](../reviews/phase11-h10-20261123/source-index.json) pins complete baseline
files and identifies exact symbols; tests check these against Git objects and the current tree.
These are inspected implementations, not claims of exhaustive language/runtime coverage.

| Path | Selection, loading and inputs | Host exposure and outputs | Boundary and failure handling |
| --- | --- | --- | --- |
| Compiler target port | `compiler_core._perform`, `CompilationContext.target` and `ProductionTarget.lower/plan`; the trusted caller supplies adapters and request/Canonical/decisions/inventory | Immutable Documents, semantic IDs/revisions, Target IR, ArtifactPlan, obligations; host retains publisher authority | Compiler validation, provenance and CAS are correctness checks. An in-process target method is already trusted executable code. |
| Sealed 0.5.0 worker | `ProductionTarget.__init__/_call` verifies release bundle; `TargetWorker` launches fixed Python `-I -B worker/main.py`; trusted host may override `command` | Worker preloads repository modules, validators, tzdata, profile/templates and bundle; input <=4,000,000 bytes, stdout <=16,000,000, stderr <=8192 | `main` calls `sandbox()` before reading the request, **after module/template loading**. Imports, Python startup, dynamic loader and library constructors therefore precede filtering. It is not a loader for hostile modules. |
| Historical 0.6.0 candidate | Importing `candidate.py` executes relative imports before `SuccessorCandidate.__init__`; constructor verifies source/parent then `importlib.import_module('model'/'generation')` | Same process, UID, address space, environment, working directory, inherited handles and filesystem authority as caller; templates and inventory read in process | Module-path check occurs after import; cached modules may already have executed. `_verify` before/after operations detects certain source changes, cannot undo side effects or contain CPU/memory/crashes. Source digest is observed identity, not authenticated admission. |
| Compiler/demo and H1/H5/H6/H9 chain | `PipelineCandidate`, `CandidatePort`, hard-coded target classes and Python `candidate_factory` callbacks; H9 inherits H6 -> H5 -> H1 -> existing compilation/candidate plumbing | Template rewriting and validation execute in trusted host process; immutable parent/source fingerprints bind known code | These callbacks are trusted Python APIs, not client-authorized extension loaders. No arbitrary module upload/filename request path was identified in the bounded MCP service. This is not a proof of whole-repository reachability or absence of vulnerabilities. |
| Source Intelligence / Phase 8 | Native Java/TypeScript adapters and existing verification Session consume generated source, classpaths, Source Models, obligations and retained execution results | `native.run` filters selected Java/Node option variables, inherits other environment entries; Java uses `-proc:none`; subprocesses have output/time bounds | Not hostile-source/build confinement. Native parsers, dependencies and generated build scripts are additional execution boundaries. Phase 8 digest/status checks cannot retroactively sandbox a generator. |
| Publication | Host `validate_plan`, `FilesystemArtifactStore.apply`, `adopt_human` and candidate provenance checks | Safe relative paths, typed ownership, content digests, CAS, framework/AI approval checks, no-follow directory walks, staging/rename/fsync | Useful cooperating-writer/path-conflict protections. Same-process hostile code can bypass or monkey-patch the publisher. Host-root, hostile same-UID mutation and physical power-loss guarantees remain outside this evidence. Candidate self-verification is not independent verification. |

Sealed supervisor environment is `{LC_ALL:C, PYTHONHASHSEED:0}` (Python may add LC_CTYPE),
with `close_fds=True` and stdio as protocol. It uses a host monotonic deadline <=30 seconds,
nonblocking bounded IO, and kills the process group in `finally`. This does not establish
cgroup-wide cleanup of adversarial descendants that escape a process group.
The sandbox sets address-space 512 MiB, CPU 20 s and file-size zero; it uses an EPERM
**denylist** with default ALLOW, not a complete syscall allowlist or filesystem namespace.
Inherited readable/mapped data and stdio are not made confidential by denying `openat`.
No namespace, dedicated-UID or cgroup boundary is established by this worker.

The successor inherits any credentials present in its caller (database environment, signing
material, repository access and open descriptors included), not evidence that any such
credential was actually leaked. Top-level imports, constructors, overridden methods and
candidate-supplied verifier callbacks are all pre-confinement execution points. Exceptions
cannot roll back arbitrary host side effects; `os._exit`, signals, native faults, thread creation
or an infinite loop in a candidate have no independent supervisor in that path.

## Existing evidence and its limits

`engineering/security/qualification.confinement` tests the exact sealed sandbox function in
fresh child processes with direct syscall probes, RLIMIT checks and a filtered-environment
component. Its own receipt explicitly excludes hostile successor containment. Direct
`clock_gettime`/`getrandom` EPERM does not prove absence of clocks or entropy generally.
These historical probes are not repeated on the development host in H10.

`engineering/evidence_admission/isolation.py` is fixed synthetic laboratory scaffolding,
not an arbitrary candidate executor. Its allowlist explicitly permits clock and randomness
calls and `execve`; its proposed AppArmor profile and broad read-only `/usr` mounts must not
be silently promoted. Runtime pinning is separate from patch/security acceptance.
`qualification_result` remains ISOLATION_QUALIFICATION_BLOCKED even for complete synthetic
observations. H10 preserves that behavior and earlier runtime/security-gate decisions.

The read-only [host observation](../reviews/phase11-h10-20261123/host-observation.json)
records Ubuntu **26.04.1**, kernel **7.0.0-43-generic**, x86_64, Bubblewrap **0.11.1-1ubuntu0.3**
and libseccomp2 **2.6.0-2ubuntu5**. User namespaces are configured, AppArmor restrictions are
1, and the observed editor profile is in complain mode. Visible cgroup controllers do not
prove delegation. `systemctl --user show` exited 1 because the observer's sanitized environment
has no user-bus variables; this does **not** establish that the host's user manager is absent.
This is not the proposed Ubuntu 24.04 qualification host. No sandbox was launched, profile
loaded, resource controller changed, privileged service provisioned or hostile payload run.
Local source binding is the baseline commit plus exact collector hash before commit;
new hosted read-only observations bind their own actual checkout commit. Neither is an
isolation PASS. Cleanup: no disposable execution resources were created.

H9.1's approved Maven SHA-256/SHA-512, exact 113-file distribution and two clean offline
builds remain unchanged. Source index references the successful exact-source hosted artifact;
this review does not rerun or reclassify its evidence. H3's original CREATE 500 remains unresolved.

## Threat model

Untrusted plugin code may include arbitrary Python/native-library behavior and intentionally
malformed output. It is not trusted because it has a version, hash, signature, valid JSON or
successful test result. A signature authenticates provenance under an approved policy; it
does not make hostile code safe. Parser/loader vulnerabilities and dependencies are in scope.

Protect Canonical bytes/revisions, reviewed generator source, repository and history, release
evidence, signing/identity/database credentials, ArtifactPlan identity, generated output,
HUMAN/approved-AI extensions, other tenants/applications and host integrity. The hostile
worker receives only the particular specification data it is authorized to process; data
intentionally sent to it cannot be kept secret from that worker. Sensitive fields must be
minimized before dispatch. Plugin canaries must be synthetic, never real credentials.

Trusted components: immutable supervisor/bootstrap/rootfs/policy, authenticated source
resolver and approval configuration, host-owned validators/publisher and independent
collector. Assume a patched host/guest kernel and honest security/operator authorities.
A plugin-controlled process, artifact, manifest or PASS statement cannot choose these roots.
A compromised supervisor, host-root/VM-host administrator, kernel/hypervisor vulnerability,
colluding authority or privileged backup/custody compromise is not defeated by namespaces.
Cross-tenant side channels, speculative execution and microarchitectural timing require
separate risk decisions; do not claim their elimination. A VM limits which kernel is shared,
not all hypervisor risk. A same-UID plugin outside an enforceable namespace/LSM boundary
could attack parent state; a plain subprocess or virtualenv is inadequate.

## Alternatives and recommended boundary

| Question | A — enforced trusted-only | B — separately supervised hostile workers |
| --- | --- | --- |
| Admission | Independently authenticated exact source, dependencies, review and registration **before import**; reject unknown sources before loading | Same immutable identity resolution, but admitted identity is not assumed safe; never import plugin in parent |
| Risk | Compromise of any trusted generator becomes compiler compromise | Boundary can limit plugin impact; supervisor/kernel/VM remain trusted |
| Compatibility | Smallest change, retains native trusted APIs; excludes arbitrary hostile executables explicitly | Data-only adapter preserves Canonical/Target IR/ArtifactPlan; Python object callbacks cannot cross boundary |
| Reproducibility | Reviewed code + locked inputs; ambient nondeterminism still possible | Fixed inputs/rootfs + verified outputs; process isolation alone does not make hostile code deterministic |
| Cost | Admission/custody/review overhead for every executable change; no hostile-plugin support claim | Extra startup, serialization, memory and runtime maintenance; measure, do not invent overhead figures |
| Supply chain | Every imported module/dependency is trusted code | Bootstrap/runtime image/policy also require patching, provenance and approved custody; plugin dependency closure is immutable |
| Exit | Real pre-import deny tests, authenticated admissions and explicit excluded threat scope | All independent kernel/VM/IPC/publication tests and recovery under the approved threat model |

For B, recommend a fixed trusted supervisor outside the payload's dedicated guest execution
identity and namespaces. Initially qualify on a newly authorized disposable VM with no
shared development home, repository, vault, credentials or Docker socket. Do not create it
under H10. A patched namespace+LSM+cgroup runner can be sufficient only if the owner accepts
shared-kernel risk; rootless OCI alone is not qualification. gVisor can reduce host-kernel
exposure at additional compatibility cost; a microVM can separate guest kernels but needs
virtualization and approved image/runtime supply chains. Neither is currently qualified.
Runtime/vendor/version selection remains a separate exact-bound approval, not H10 policy.
Ubuntu 24.04 x86_64 is the proposed first laboratory profile; local Ubuntu 26.04 and GitHub's
Ubuntu 24.04 are separate environments, neither automatically interchangeable. Other OSs and
ABIs remain unsupported for hostile execution until qualified. These are execution-host
constraints, never Canonical semantics or generated-target requirements.

### Controls and guarantees required for B

| Control | Required enforcement / independent observation | Limit |
| --- | --- | --- |
| Launch and identity | Host-owned fixed launcher/argv/interpreter/rootfs hashes; supervisor creates cgroup, namespace/mount/UID state, closes FDs, drops capabilities and sets no_new_privs **before any plugin import** | A candidate-supplied entrypoint or shell command cannot choose host launch state |
| Filesystem | Private mount/user/PID/IPC/UTS/network namespace; minimal verified runtime + immutable input mounts, private bounded tmpfs; no home/repository/vault/proc-host-root/socket mounts | Read-only host root is too broad; approved input contents remain visible |
| OS identity / LSM | Dedicated guest identity, no host capabilities; host-owned enforce-mode AppArmor rules, qualified attachment and deny tests; no policy writes from payload | AppArmor proposal text is not an attached enforcement profile |
| Network | No interfaces/routes except qualified loopback if needed; seccomp denies socket families and inherited sockets absent; no DNS/cloud metadata/collector controls | Denial must be observed at syscall and peer endpoints, not inferred from timeout |
| Syscalls / exec | ABI-specific default-deny allowlist, kill/reject wrong ABI; trusted bootstrap installs final filter before loading Python plugin; deny clone/exec/ptrace/mount/setns/bpf/io_uring as appropriate | Initial trusted interpreter startup has different syscall needs; arbitrary native entrypoint launching requires a separately reviewed design |
| Credentials / IPC | No credentials, tokens, ambient environment, ssh-agent or inherited nonprotocol descriptors; one bounded request/result pipe with exact launch identity and request nonce | Separate objects/threads in one process provide no isolation; candidate may forge stdout |
| Resources | Guest cgroup v2 memory.max, memory.swap.max, pids.max, cpu.max plus CPU budget, wall deadline, IO/tmpfs quotas; supervisor observes peaks/events | RLIMIT_AS is per-process virtual space; CPU quota controls consumption, not confidentiality or cumulative CPU budget |
| Cleanup | Supervisor outside payload cgroup; kill/reap all members via cgroup.kill or qualified equivalent, verify empty cgroup and reap namespace init; quarantine guest on uncertainty | A process-group kill alone does not catch adversarial setsid descendants |
| Output | Data only; independent host schema/type/path/digest/semantic-origin/ownership/CAS validation, staged publication and post-publication Source Model/Phase 8 binding | Worker-supplied verification flags or symlink paths carry no write authority |
| Time / entropy | Measure direct syscalls, libc/vDSO and native instructions in approved VM; fixed declared deterministic inputs; constrain supported runtime and reject unsupported deterministic claims | seccomp cannot intercept vDSO userspace clock reads, RDTSC/RDTSCP or RDRAND/RDSEED. Time namespaces shift clocks; they do not remove clocks. Removing device nodes alone does not remove entropy |

vDSO and CPU timing are a **decision blocker for an absolute no-clock/no-entropy claim**.
For a general native-capable process, do not promise that claim. Either approve a bounded
confinement claim excluding timing/randomness secrecy, with reviewed deterministic-stage
eligibility and independent repeat checks, or authorize evaluation of a mediated restricted
language/runtime and CPU/VM policy. Repeat equality detects divergence, not a proof that a
hostile program can never behave nondeterministically. No determinism gate is relaxed here.

### Trusted compiler and protocol integration (proposed, not implemented)

Reuse existing compiler target ports. Host resolves an approved data manifest containing
candidate source/dependency/rootfs/policy/ABI identities without importing candidate code.
Recheck immutable inputs immediately before launch; mount content-addressed snapshots, not
candidate-writable paths. Fixed bootstrap establishes all restrictions, confirms readiness,
then loads the candidate. Any setup failure is BLOCKED; no in-process fallback.

Request: protocol/version, host-generated execution ID and nonce, exact Canonical snapshot
and digest, request compiler/pipeline/profile/source identities, current Target IR when
applicable, declared capabilities/limits, and sanitized ownership inventory. Treat all
untrusted content as bytes. Proposed initial ceilings reuse existing worker limits:
4 MB request, 16 MB result, 8 KiB redacted diagnostic channel, JSON depth 128 / 200,000 nodes;
512 MiB memory, 20 CPU seconds, 30 wall seconds, cgroup pids budget 8. These are **proposals**,
not new activated capacities. Per-artifact/path/count budgets must fit these ceilings;
owner must approve exact profile and actual workload suitability before implementation.

Response: exact protocol, execution/nonce/input/source identities, explicit success/error
variant, and bounded artifact content records. Reject duplicate/nonfinite/deep JSON, unknown
fields, trailing data, absolute/traversal/colliding paths, symlinks/devices/external references,
executable instructions, stale/nonmatching IDs and output beyond budget. Never deserialize
pickle or call plugin callbacks in the parent. No arbitrary host path in a response is an
authorization. A stream cannot authenticate itself: supervisor binds it to the launched
PID/isolation identity and immutable request; only independently measured execution facts
are trusted. A future signer/collector stays outside the worker with separate authorization.

Host reconstructs typed Target IR/ArtifactPlan; independently derives expected Canonical
origins/revisions/input digests and obligations, compares unchanged lowering constraints,
then uses existing validate_plan and FilesystemArtifactStore CAS/ownership gates. Candidate
`validate-plan` or `verify_materialized` results are advisory, never sole approval. Source
Intelligence reads only verified staged bytes with locked native analyzer tools; Phase 8
links real results, not worker-reported PASS. Analyzers, Maven/npm scripts and generated
application execution need their **own** approved containment; successful generator
isolation cannot establish the whole build/application boundary.

Crash/incomplete/timeout/invalid output: no publication. Interrupted valid-plan publication
uses existing staging/CAS recovery guarantees, independently measured in a disposable VM;
unknown durability remains indeterminate and blocks reuse. Do not claim atomicity across
independent result stores and filesystem publication. Preserve human extensions and old
output bytes on rejected plans; verify exact provenance after successful publication.

## Approval boundary, implementation order and acceptance

The security and architecture owners must explicitly choose A or B, attacker/OS/runtime
scope, shared-kernel versus VM protection, time/entropy claims, trusted source/admission
custody, and the exact disposable laboratory/profile/test plan. Infrastructure owners
separately approve any VM provisioning, identity/cgroup delegation, AppArmor attachment
and service changes. Qualification/review authority must be independent of plugin authors;
no reviewer, key, host, profile or endpoint is invented here. See exact requests in the
machine package. None is approved by this assessment.

After that approval only: implement pre-load admission and fixed supervisor; independently
review the data protocol and host validator; qualify setup/escape and resource/recovery
matrix in disposable guests; integrate through existing compiler ports and compare both
reference ArtifactPlans/source/provenance/ownership/Phase 8 results; measure overhead and
repeat determinism; obtain independent security disposition. These are implementation
milestones within existing P-08/P-11 and Phase 11, not new project phases.

Acceptance requires every applicable adversarial row to retain actual input/expected deny,
independent observation, source/candidate/runtime/profile/policy digests, OS/kernel,
execution identity, resource counters, exit/signal, cleanup and evidence hashes. Missing
controls, stale/substituted inputs, unsupported hosts or unapproved policies must block
execution; no skipped test can satisfy a required control. A test-suite PASS for this H10
review proves review consistency/preservation, **not** hostile isolation. SEC-01 remains
BLOCKED until the approved boundary is implemented and independently verified.

## Primary technical references

Accessed 2026-11-23. These explain mechanisms, not ACP qualification or version approval.

- [Linux seccomp documentation](https://docs.kernel.org/userspace-api/seccomp_filter.html): syscall filtering reduces kernel surface; combine with other controls.
- [Linux cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html): controller semantics, limits, counters and cgroup-wide process management.
- [Linux vDSO manual](https://man7.org/linux/man-pages/man7/vdso.7.html): userspace fast paths and seccomp visibility limits.
- [Ubuntu AppArmor](https://documentation.ubuntu.com/security/security-features/privilege-restriction/apparmor/): user-namespace restriction is policy-dependent.
- [gVisor security architecture](https://gvisor.dev/docs/architecture_guide/intro/): distinct application-kernel boundary, with compatibility and residual risks.

No host global settings, accepted evidence, Canonical contracts, worker restrictions,
generator identities, historical migrations or release predicates are changed by H10.
