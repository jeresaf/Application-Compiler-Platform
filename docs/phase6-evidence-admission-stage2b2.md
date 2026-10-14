# Stage 2B-2A runtime qualification — BLOCKED

Accepted baseline: `91181e1c62cfc6be6b82d64bc86f8d4f7166d09c`.

This increment implements fixed synthetic diagnostic probes, read-only host/runtime
identification and closed configuration verification. It does not execute
candidate applications or registered verifiers, provide arbitrary argv/code/mount
inputs, collect release evidence, sign attestations or issue acceptance.

## Runtime decision and security blocker

Evaluate Ubuntu Noble's packaged `bubblewrap 0.9.0-1ubuntu0.3` first. Its package
manpage advertises all 14 controls used by the fixed namespace probe: user/PID/
network/IPC/UTS/cgroup namespaces, disable/assert-disabled nested user namespaces,
seccomp, parent-death handling, new session, cap-drop, clearenv and ro-bind.
Feature presence is static compatibility evidence, not kernel enforcement.

Package source: https://security.ubuntu.com/ubuntu noble-security/main, amd64.
SHA-256 of the Packages.xz index was checked against the Ubuntu-signed InRelease;
gpgv verified the Ubuntu Archive Automatic Signing Key (2018), fingerprint
F6ECB3762474EDA9D21B7022871920D1991BC93C. The downloaded package matched its index
entry. No package installation or execution of the extracted binary occurred.

- Package: `bubblewrap_0.9.0-1ubuntu0.3_amd64.deb`
- Package SHA-256: `2461f1beee9cb04c8942739fe1a2b37e7b7c2a3d518f0779dc75f9245baa3094`
- Executable SHA-256: `e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71`
- ELF NEEDED: libselinux.so.1, libcap.so.2, libc.so.6.
- Declared minimums: libc6 >=2.38, libcap2 >=1:2.10, libselinux1 >=3.1~.
- Resolved Ubuntu 24.04 library hashes/kernel identities: UNAVAILABLE; no matching
  disposable host was executed. Local Ubuntu 26 libraries are not substituted.

USN-8779-2 explicitly states that the symlink fix for CVE-2026-87766 was reverted
because it caused a regression. It lists both Noble 0.9.0-1ubuntu0.3 and Resolute
0.11.1-1ubuntu0.3. Therefore neither package is declared security-qualified.
A fixed Ubuntu 24.04-compatible package/backport and its full dependency manifest
need separate review. No unreviewed runtime was installed or silently substituted.

Primary sources:

- https://ubuntu.com/security/notices/USN-8779-2
- https://ubuntu.com/security/notices/USN-8779-1
- https://manpages.ubuntu.com/manpages/noble/man1/bwrap.1.html
- https://raw.githubusercontent.com/containers/bubblewrap/v0.9.0/bubblewrap.c

## Exact authorized inventory

New source: `engineering/evidence_admission/host_capabilities.py`, `isolation.py`.
New tests: `verification/evidence_admission/stage2b2/lab_fixtures.py`,
`test_host_capabilities.py`, `test_isolation.py`. New documentation: this file.
Only existing-file change: `verification/evidence_admission/test_preservation.py`,
for the exact six-file inventory and corresponding historical inventory
predicates. No broad exclusion. No workflow/ledger/authentication changes.

## Identity and host detection

`runtime_identity()` observes only the fixed root-owned nonwritable system
/usr/bin/bwrap. It records package/version/architecture, binary SHA-256, kernel,
OS identity, supported flags, actual linked-library SHA-256 values, libseccomp,
and the qualification interpreter and libpython identities. Exact library
identities and raw commands reside in the local machine-readable host report.
`verify_runtime` requires exact equality with independently supplied immutable
canonical bytes and their digest; no candidate-driven trust discovery occurs.
The fixed synthetic interpreter is the existing official CPython 3.14.7
installation. No new Python dependencies are introduced.

Local observations: Ubuntu 26.04.1; kernel 7.0.0-38-generic; Bubblewrap
0.11.1-1ubuntu0.3; systemd 259.5-0ubuntu3.4; libseccomp2 2.6.0-2ubuntu5.
Local runtime pins used for diagnostics are current observations, NOT a human
security approval. Exact hashes in the local host report must not be transferred
to Ubuntu 24.04. The accepted Python environment uses the unchanged Stage 2A lock.

`detect_host()` is read-only and reports visibility separately from enforced
capability. It never creates scopes, modifies AppArmor, sets sysctls, registers
identities or returns a qualification PASS.

## AppArmor

Ubuntu's unprivileged-user-namespace restriction is enabled locally. The installed
/etc/apparmor.d/bwrap-userns-restrict profile grants broad setup access and stacks
an unprivileged child profile; it is not the proposed restrictive lab profile.
The profile-set query via aa-status was denied to the current host user; loaded
profile-set inspection is therefore UNAVAILABLE, not assumed enforced.

The exact proposed profile bytes are the `APPARMOR_PROPOSAL` constant in
isolation.py and `/tmp/acp-isolation-qualification/apparmor.proposed`. Its digest
is bound in the closed isolation profile. It targets a separately reviewed
/usr/libexec/acp-lab/bwrap path, grants setup capabilities and namespace/mount
operations, restricts filesystem access, and denies network/home/run access.
It is a review proposal, not an installed profile or proven minimal final policy.
`apparmor_parser -Q -T` syntax-checks it without loading kernel policy or writing
a cache. The profile's ABI/path/stacking and runtime access need actual Noble
validation. No privileged configuration was applied; no restriction was disabled.
The extracted package includes a sysctl snippet; extraction did not apply it.

## Closed configuration and seccomp

The profile binds exact runtime digest, x86-64 architecture, seven namespace
identities, four fixed read-only runtime mount roots, empty capability set,
exact environment, seccomp/profile digests and fixed resource bounds.
Unknown/changed fields, mounts, environment, versions, architectures, library
hashes or profile identities fail closed. Callers cannot provide workload code.

The exact syscall inventory is the sorted `SYSCALLS` tuple in isolation.py and
`/tmp/acp-isolation-qualification/seccomp.json`. Default action is ERRNO EPERM;
libseccomp's architecture check kills incompatible architectures. There is no
unrestricted fallback. `seccomp_fd()` exports this fixed allowlist as BPF using
the measured libseccomp library; no caller-supplied rules are accepted.
The profile permits only the fixed Python diagnostic's runtime operations.
mount, unshare, setns, socket, ptrace and bpf are outside the allowlist.
This is NOT a registered-verifier/general-application seccomp policy.

## Actual local synthetic enforcement

The fixed Bubblewrap probe creates distinct user/mount/PID/net/IPC/UTS/cgroup
namespaces; drops capabilities; disables further user namespaces; clears the
environment; exposes only runtime roots read-only, private proc/dev; loads the
closed BPF filter and executes a fixed synthetic Python program.

Observed checks: distinct namespace IDs; private PID visibility (1 and 2);
host home and real synthetic-canary path inaccessible; no supervisor run path;
no inherited extra descriptors; exact environment; no network routes/access;
zero effective capabilities; no_new_privs; mount/unshare/setns return EPERM.
Runtime-opened library descriptors are recorded separately from inherited
privileged descriptors. An initial conservative descriptor check detected a
libffi file opened by the probe itself; the corrected check snapshots descriptors
before ctypes import. Prior report copies are retained in the local report folder.

The actual resource probes use four disposable randomly named user systemd
services. These are not persistent infrastructure. Each uses MemoryMax=96M,
MemorySwapMax=0, TasksMax=8, CPUQuota=20%, RuntimeMaxSec=4, KillMode=control-group,
TimeoutStopSec=1, SendSIGKILL=yes and OOMPolicy=kill. They verify values from the
actual workload cgroup, not merely command arguments. Every scope is stopped
and reset after the probe; no global controller settings change.

- Memory: allocation bounded to 192 MiB attempts within a 96 MiB cgroup; observed
  oom-kill, not successful allocation beyond the limit.
- PIDs: at most 12 fork attempts; EAGAIN and pids.events show enforcement. Created
  children are killed/reaped; PID count remains bounded by 8.
- CPU: 2 monotonic seconds of bounded busy work, about 0.4 CPU seconds with actual
  throttling counters under the 20% quota.
- Deadline: parent/child sleeps are terminated by the 4-second service limit;
  observed timeout and complete cgroup cleanup.
- Swap: actual memory.swap.max is zero; no uncontrolled swap stress is performed.
- Normal and bounded-failure cleanup: cgroup empty/removed and known process
  identities no longer live. This is synthetic evidence, not general cleanup
  assurance for arbitrary workloads.

Namespace and resource probes are separate diagnostics. Their success does not
prove a composed supervisor, AppArmor confinement, library vulnerability safety
or Ubuntu 24.04 compatibility. `qualification_result` intentionally cannot issue
a positive qualification while the runtime advisory/platform/profile review is
unresolved. It never issues execution/admission/release authority.

## Platform evidence separation

| Environment | Evidence | Qualification |
|---|---|---|
| Local Ubuntu 26.04 | Actual fixed namespace/seccomp/resource probes | BLOCKED by advisory and unqualified AppArmor/composition |
| Disposable Ubuntu 24.04 host | Package static inspection only; no execution | HOST_CAPABILITY_UNAVAILABLE |
| GitHub Ubuntu 24.04 | Accepted run's 47 Stage 2B-1 tests, not isolation probes | HOST_CAPABILITY_UNAVAILABLE |

Accepted hosted run 38543908961 bound to 91181e1c62cfc6be6b82d64bc86f8d4f7166d09c
passed all four engineering jobs; closure returned PHASE6_CLOSURE_BLOCKED exit 2,
final aggregation failed. No hosted isolation result is inferred from that run.
Existing workflow remains unchanged. Standard runners' actual cgroup delegation,
AppArmor profile enforcement and updated runtime safety remain unverified.
If these cannot be established, use a separately authorized independently
administered disposable laboratory runner; no persistent runner is provisioned.

## Verification and evidence boundaries

Unit regressions cover exact runtime identity, wrong version/binary/library/
architecture/kernel/features/pin, missing namespace flags, unknown profile,
unapproved mounts/environment/capabilities/limits, seccomp/AppArmor/runtime
substitution and absence of arbitrary probe/admission APIs. Unit tests do not
pretend mock/configuration evidence demonstrates kernel enforcement. Actual
probes are run explicitly outside the Codex sandbox and their status is reported
separately. No required probe is silently skipped; unavailable control blocks
qualification. Network, filesystem, canary, descriptor, nested-namespace and
cleanup observations are present in the actual local report. Unauthorized mount
attempts are denied by the actual seccomp filter; symlink attacks against a
reviewed patched runtime remain a qualification blocker.

Machine-readable reports and raw argv/stdout/stderr:
`/tmp/acp-isolation-qualification/host.json`, `report.json`, `profile.json`,
`seccomp.json`, `apparmor.proposed`, plus prior report copies.
Package authentication report: `/tmp/acp-noble-bwrap-package.json`.
These are ephemeral local laboratory evidence, not signed receipts or immutable
hosted admission. Their exact hashes are included in the completion artifact.

All existing Stage 1/2A/2B-1 and CI tests must remain passing under Python 3.14.7.
Preservation checks retain all 39 criteria, Canonical snapshots, historical
approvals, T09 reservations and generator seal:
`sha256:ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb`.
All 21 closure blockers remain.

## Proposed Stage 2B-2B boundary and decisions

Before further execution work: independently review the reverted security fix,
select a fixed Noble-compatible runtime/backport, authenticate its full package/
binary/library identities, authorize a disposable Ubuntu 24.04 qualification
host, review/load the exact narrow AppArmor policy and run actual attack and
composed resource/namespace/cleanup tests there. No automatic runtime upgrade,
global AppArmor/sysctl disabling or unenforced fallback is allowed.
Only after that evidence passes should a separately authorized supervisor be
considered. supervision.py, observations.py, registered-verifier execution,
collection, signing, operational activation, data binding, migration, deployment,
Stage 2B-3/2C and Phase 7 remain unimplemented. No commit or push is authorized
by this qualification request.

Stage 1 = ENGINEERING ACCEPTED
Stage 2A = ENGINEERING ACCEPTED
Stage 2B-1 = ENGINEERING ACCEPTED
Stage 2B = IN_PROGRESS
Phase 6 = IN_PROGRESS
Phase 7 = NOT_STARTED
Operational security = NOT ESTABLISHED
Release closure = BLOCKED


## Exact local profile identities and negative coverage

AppArmor proposal SHA-256:
`e64cf986ea9e067ced3c8560fd82028afd60563d2ae04cf7b7c3d825b94ed4be`.
Closed seccomp JSON SHA-256:
`3f7570dc0913030e95399a5e32a0f92e7b2275257072ec3653e3ff637947af91`.
Observed local /usr/bin/bwrap SHA-256:
`523da3e7399044be5163aee6f57a77a6bef7454376e28f0a0627920bae1b76b6`.
The Noble executable identity above is different; neither is transferred across
platforms. Full linked-library SHA-256 values are in host.json. The fixed filter
explicitly sets libseccomp ACT_BADARCH to KILL_PROCESS, and actual harmless
ptrace and bpf probes also return EPERM. The proc-root canary alias is denied.

`negative-coverage.json` in the ephemeral report directory maps all 20 requested
negative requirements to unit rejection, actual local observations or explicit
unavailable evidence. A missing/false enforcement check or surviving descendant
cannot satisfy the diagnostic completeness check. Even complete caller labels
cannot obtain a positive qualification; pending independent security/platform/
AppArmor review keeps the result blocked. This avoids treating configuration
strings or fabricated labels as proof. Actual AppArmor-denial testing under the
proposed profile and a patched runtime's symlink/mount attack qualification remain
BLOCKED, not passed or skipped. No library-only/stdout-only claim becomes an
execution capability.

New unit suite: 26 tests, no skips. All required actual fixed probe groups were
attempted locally: namespace/seccomp plus memory/PID/CPU/deadline. No required
isolation probe was silently skipped. The separate default compiler PostgreSQL
regression remains opt-in and is not enabled by this task. That existing skip
must be reported separately from isolation qualification.


Current local BPF bytes SHA-256:
`bc0cd6bfa74cdbb2dbaef844cb927e25eea710448ab3810f25b6c054a7386360`.
The BPF artifact and compiler-library identity are separate from the canonical
JSON rule inventory digest. The loaded profile is closed, not a permissive
replacement. Reports distinguish all 20 negative requirements and do not label
unperformed Ubuntu 24.04/AppArmor attack tests as passing.

Focused regressions: 47 Stage 1/preservation, 52 Stage 2A, 47 Stage 2B-1,
26 CI parity/aggregation and 26 new unit cases pass (198 cases, no skips in
these suites). Repository checks and all three independent Node byte/hash
vector profiles pass under Node 24.21.0. CPython is 3.14.7; pip check succeeds.
Raw regression logs are `/tmp/acp-stage2b2-*.log`. The existing Route A suite
initially hit sandbox-denied localhost sockets and is rerun outside the sandbox;
that initial failure is preserved and is not classified as passing.
All qualification results remain blocked irrespective of engineering test counts.


The existing Route A suite completed outside the sandbox: 112 tests passed,
zero failures/skips (794.284 seconds). Initial sandbox failures were denied
localhost sockets, not compiler regressions; their raw log remains preserved.
The broad compiler suite is reported separately once complete. No operational
identity, accepted application history or real authority was constructed by the
Route A synthetic regression fixtures.


## Final local regression results

| Suite | Cases | Passed | Failed | Skipped |
|---|---:|---:|---:|---:|
| Existing compiler suite | 270 | 269 | 0 | 1 |
| Existing Route A suite, host rerun | 112 | 112 | 0 | 0 |
| Stage 1/preservation | 47 | 47 | 0 | 0 |
| Existing Stage 2A | 52 | 52 | 0 | 0 |
| Existing Stage 2B-1 | 47 | 47 | 0 | 0 |
| Existing CI regressions | 26 | 26 | 0 | 0 |
| New qualification unit regressions | 26 | 26 | 0 | 0 |
| Total unique cases | 580 | 579 | 0 | 1 |

Compiler command: accepted CPython 3.14.7 `-m unittest discover -s tooling/tests
-v`; elapsed 2007.236 seconds. The sole skip is
`test_real_postgresql_storage_presence_required_and_rollback`: requires explicit
disposable PostgreSQL. It was not enabled, and is not counted as passing.
Route A uses the same accepted Python environment and `-m unittest discover -s
verification/route_a -v`, outside the sandbox for localhost sockets. The other
suites use their explicit discovery directories. No new isolation unit test is
skipped. Actual fixed kernel probes remain separately reported local diagnostics.

No source changes outside the exact authorized inventory, no workflow change,
no ledger change and no sealed input change are present. Canonical digests and
all 39 criteria/21 historical blockers remain checked. The full hosted release
workflow was not rerun for these uncommitted changes. No claim of hosted runtime
qualification or operational security is made.

Local package-index-only observation for installed Resolute 0.11.1-1ubuntu0.3:
SHA-256 `d3a6c1b6b0e0474eaed6dbd055c0d601fd875af153976a0dc4aae75f4ea10868`.
This is APT metadata, not an independently downloaded/verified local package.
Noble's package bytes were independently verified against signed archive metadata
as described above. Both remain subject to the reverted security fix.

Final runtime qualification: ISOLATION_QUALIFICATION_BLOCKED.
Required next decisions: patched Noble runtime/package review; authorized
Ubuntu 24.04 disposable-host qualification; independently reviewed AppArmor
policy/application; composed namespace/cgroup/cleanup attack tests. A dedicated
administered lab runner is an option only if standard hosted controls cannot be
qualified. None is provisioned. No general supervisor implementation is authorized.

Stage 1 = ENGINEERING ACCEPTED
Stage 2A = ENGINEERING ACCEPTED
Stage 2B-1 = ENGINEERING ACCEPTED
Stage 2B = IN_PROGRESS
Phase 6 = IN_PROGRESS
Phase 7 = NOT_STARTED
Operational security = NOT ESTABLISHED
Release closure = BLOCKED
