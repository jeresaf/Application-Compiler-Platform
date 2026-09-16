# Production quality gates

Status: mandatory logical baseline from charter §§31–35; no production gate executor exists yet. The Phase 1 repository cannot certify an application production-ready.

Each gate result binds `{gateId, profileVersion, semanticSnapshot, artifactDigest, tool/input/config/environmentDigests, evidence, result}`. Results: PASS, FAIL, BLOCKED, NOT_RUN. Only fresh PASS satisfies a required gate. Unknown, missing, stale, or untrusted evidence blocks. Profile extensions may strengthen thresholds/add gates; they may not remove or silently weaken baseline obligations.

| Gate | Required evidence |
| --- | --- |
| G-01 Specification valid | Complete supported meta-model validation and approved dependency closure |
| G-02 No blocking ambiguity/conflicts | Issue resolution and formal semantic checks for supported rules; explicit reviewed handling of remaining uncertainty |
| G-03 Decisions accepted | Required/locked decisions current and authority verified |
| G-04 Traceability complete | Requirement/decision → realization → source → verification → deployment/runtime-control mappings for applicable obligations |
| G-05 Architecture/capabilities valid | Target capability negotiation and complete lowering/enforcement plan |
| G-06 Security policies compiled | Backend/query/UI/export/audit control mappings; no unimplemented required policy |
| G-07 Authorization tested | Positive and negative authorization/tenant tests pass |
| G-08 Migration validated | Data impact, compatibility windows, phase preconditions, recovery and migration tests |
| G-09 Build succeeds | Isolated locked-toolchain successful build for exact artifact |
| G-10 Unit tests pass | All required unit evidence |
| G-11 Integration tests pass | All required integration evidence |
| G-12 E2E tests pass | Required user journeys across responsive/error/permission states |
| G-13 Acceptance satisfied | Fresh evidence for each applicable criterion, including critical requirements |
| G-14 Dependencies compliant | Locks, vulnerability policy, SBOM; applicable license policy |
| G-15 Security scans pass | Configured static/security analysis and reviewed findings |
| G-16 Secrets scan passes | Source/artifact/config/log secret scanning |
| G-17 Configuration valid | Versioned config schema, environment bindings, secret handles resolved under scoped authority |
| G-18 Health/observability present | Health/readiness probes, required structured logs/traces/metrics/audit/alerts, redaction evidence |
| G-19 Backup/recovery satisfied | Backup and measured restore/recovery evidence for RPO/RTO requirements |
| G-20 Package reproducible | Artifact hashes, compiler/generator provenance, reproducibility verification, applicable signatures |
| G-21 Accessibility satisfied | Automated checks plus required manual keyboard/focus/assistive-use evidence |
| G-22 Performance/reliability satisfied | Measured workload/latency/scale, timeout/retry/idempotency/failure tests for specified thresholds |
| G-23 Ownership/drift acceptable | Human extension preservation; source/infrastructure/runtime differences explicitly assessed |

Conditional obligations (e.g. a database migration for an unchanged data model) require an applicability proof bound to the semantic diff/profile. They are not satisfied by a caller-supplied `skip` flag. An applicability proof is gate evidence, reviewed under the profile; baseline rules remain present. Exceptions/security risk acceptance require explicit governance and cannot be invented by the generator.

Minimum viable production profile selection remains P-12. It must instantiate this entire baseline for one serious reference target, specify evidence trust/freshness and criticality thresholds, and demonstrate repeated releases including schema, policy, workflow, UI, and compatibility changes. A one-time scaffold or successful compilation cannot meet that criterion.
