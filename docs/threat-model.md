# Initial threat model

Status: architecture threat register, not a completed security assessment. Basis: charter §§3.4, 3.7–3.10, 13–14, 26–27, 30–33. Runtime sandbox and detailed security algebra remain proposals.

## Assets and boundaries

Assets: approved intent, decision locks, tenant/sensitive data, secret bindings, provenance and approval evidence, human-owned source, build workers, deployment credentials, artifact/evidence integrity, and restore capability.

Untrusted inputs include conversations, AI candidates, structured/text specs, imported source, plugins, dependencies, build logs, and runtime telemetry. Authoring → authority → compiler → plugin/worker → artifact store → release environment are distinct trust boundaries. Repository content is not an authorization credential. Runtime applications have their own caller/tenant/external-system boundaries.

| ID / threat | Control / failure behavior | Verification obligation |
| --- | --- | --- |
| T-01 Proposal or AI claim promoted to approved intent | Approval closure plus authenticated digest-bound authority; no self-approval | Kernel closure tests now; forged/revoked authority tests before Phase 3 |
| T-02 Prompt injection in imported docs/logs | Treat content as data; bounded AI tool rights; output remains candidate | Adversarial imported content tests before AI adapter |
| T-03 Cross-tenant access, policy gaps, UI-only authorization | Shared semantic scopes; backend/query/export enforcement; deny by default | Negative policy tests across all generated surfaces before target readiness |
| T-04 Secret disclosure through IR, diagnostics, logs or cache | Symbolic references; isolated resolution; redaction/classification; scoped secret access | Kernel shape/type and non-echo diagnostics tests now; runtime leakage tests later |
| T-05 Malicious or defective generator/build/dependency | Capability-constrained plugin execution; filesystem/network/resource limits; locked tools | Escape, traversal, symlink, resource exhaustion and network policy tests before workers |
| T-06 Human-owned code overwritten | Digest-bound nonoverlapping ownership map and staged write plan | Deliberate manual edit/drift and region collision tests before regeneration |
| T-07 Data loss or incompatible live clients | Impact and migration phases, explicit destructive approval, restore plan | Existing-data narrowing, interrupted backfill, client coexistence, restore drills |
| T-08 Approval/evidence replay or forged provenance | Exact subject/input/artifact digests, authority verification, freshness and immutable records | Stale test, changed candidate, revoked identity and forged report tests |
| T-09 Concurrent updates corrupt authoritative state | Atomic compare-and-append, read-set checks, semantic merge | Race/retry/crash injection tests before durable state |
| T-10 Non-reproducible or compromised supply chain | Complete input manifest, dependency policy, SBOM, hashing, isolated rebuild | Independent rebuild and dependency/secret scans before release |
| T-11 Parser/schema denial of service or external reference retrieval | Bounded input/depth; local trusted schema only; no input-directed schema loading | Strict-decoding/resource-budget tests now; fuzzing before frontend adoption |
| T-12 Incomplete source/runtime analysis treated as proof | Explicit completeness/confidence; unknown blocks dependent gates | Missing analyzer, unresolved calls, partial telemetry and stale maps tests |

Remaining risk: the kernel is a development validator, not a hostile multi-user service. It checks attestation structure, not identity authenticity; it does not prove business policy correctness, tenant isolation, cryptographic trust, or worker confinement. These are recorded gate obligations, never implied by a green kernel test run.
