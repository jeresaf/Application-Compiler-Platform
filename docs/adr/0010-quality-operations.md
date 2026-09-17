# ADR-0010: Measurable quality and operational obligations (P-05)

Status: ACCEPTED. Date: 2026-09-16. Supersedes P-05 in ADR-0005.

## Decision

Promote TestRequirement, PerformanceRequirement, AccessibilityRequirement, ReliabilityRequirement, CompatibilityRequirement, ObservabilityRequirement, Backup, Recovery, Applicability and EvidenceRequirement. All use shared identity/revision/lifecycle/ownership/basis/reference rules. Requirements bind typed subjects and verification methods; measurements use metric-specific units, explicit workload/window and thresholds. Backup/Recovery specify interval, retention, RPO/RTO and restore-test freshness without a storage/cloud implementation.

Applicability is an explicit pure Boolean expression backed by a Decision. False applicability is a reviewed proof obligation, not a skip flag. An EvidenceRequirement identifies exact subjects, required methods and maximum age. Evidence observations are a separate closed artifact, never an approved semantic node or a lifecycle shortcut. Evidence evaluation takes an explicit UTC evaluation instant and exact snapshot/artifact/config/tool/profile context; it never reads ambient time. Missing, failed, future-dated, stale, mismatched or incomplete evidence cannot pass. Every required method must have fresh passing evidence; performance evidence must satisfy metric/threshold/sample count and workload identity.

## Alternatives and limitations

Free-text acceptance and unbound test reports cannot establish freshness or reproducibility. A universal metrics bag would hide units and applicability. The bounded metric/method vocabulary is extensible only through explicit versioned schema changes. Reference evidence evaluation checks contract semantics, not cryptographic trust or actual target performance. Evidence signatures, executors, production gate orchestration and target measurement implementations remain later work. This is sufficient to represent obligations in a future IR; it does not implement that IR.
