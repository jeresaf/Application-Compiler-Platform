# H10.3 owner decisions

Reviewed baseline `f94207dc346288875cba7fd243cd0cddd660703b` on `codex/phase11-hardening`. The H10 and H10.2 records identify all six decisions as NOT_APPROVED. No separately attributable approval was supplied for this increment. The existing protocol passed six local contract tests.

The proposed profile is Option B in a dedicated disposable Ubuntu 24.04 x86_64 VM. Its executable, guest image, policy and laboratory identities are pending. Each approval should name the responsible owner, the exact approved inputs and scope, and any exclusions. A recommendation or a content digest alone confers zero execution authority.

| Decision | Responsible owner | Approval requested |
| --- | --- | --- |
| H10-D1 | Security and compiler architecture | Select Option B for a bounded plugin capability. Explicitly scope malicious plugin code and specify how host-root, hypervisor compromise and side channels are treated. |
| H10-D2 | Security | Approve dedicated guest separation and provide the exact image, kernel, runtime, supervisor and dependency versions with verified digests and trust sources. |
| H10-D3 | Security and compiler architecture | Select the first supported plugin language and entry point. Specify the clock and entropy guarantees and deterministic-stage eligibility. Native execution requiring absolute denial remains blocked. Retain repeat-output equality as a separate check. |
| H10-D4 | Infrastructure and security | Identify the disposable guest and authorize the exact synthetic workload set, UID, mounts, network policy, namespaces, AppArmor and seccomp profiles, cgroup limits, deadline and cleanup procedure. Confirm whether the proposed 512 MiB, 20 CPU seconds, 30 wall seconds and eight tasks fit the laboratory scope. |
| H10-D5 | Project authority and independent security reviewer | Identify the trusted registry, source and dependency provenance policy, approval verification and revocation mechanism, evidence custody and independent acceptance reviewer. |
| H10-D6 | Compiler architecture and source ownership | Approve the narrow existing target-port adapter, version `acp-plugin-foundation/1`, host reconstruction of typed plans, independent semantic and ownership checks and use of the existing Phase 8 and CAS publication boundaries. |

Once authorized, the supervisor will resolve the immutable host-approved identity, establish and independently observe the approved controls, then admit the worker to one bounded request/response exchange. The host retains publication authority. Missing controls block load, and failed or incomplete exchanges block publication. Cleanup uncertainty quarantines the guest. Future evidence must identify the source, guest, policy, candidate and workload digests and retain actual process, resource and cleanup observations.

Supervisor implementation, compiler execution integration, OS enforcement, all 22 laboratory cases and cleanup qualification remain NOT_RUN. SEC-01 and Phase 6 release closure remain BLOCKED. Phase 11 remains IN_PROGRESS and Phase 12 remains NOT_STARTED.
