# Batch 03R integrated cardinality candidate

The opt-in CardinalityCandidate reuses the existing 0.6.0 generator transformation, exact release verification, ArtifactPlan and provenance contracts. Its separate generator fingerprint binds the base source, overlay and Java coordination bytes. The regular successor entrypoint and sealed 0.5.0 are preserved.

The generated transaction enters coordination before a shared endpoint lock. Locking generated operations, composite steps and the lifecycle action use that store seam. Ordinary nonlocking queries retain their existing path. V10 replaces the deferred scan with tenant-scoped validation, checks retained rows under migration locks and rejects writes without coordination. V1 through V3 are byte-identical. This candidate has no accepted semantic migration route or operational deployment authority.

In owned PostgreSQL on Payment and Case Management, two baseline transactions reached separate write barriers before commit. Each baseline run had one deadlock and one committed write. Each coordinated run observed the second writer waiting for coordination, then committed both writes with zero deadlocks. An uncoordinated update was rejected. The generated backends were compiled offline and passed startup, query, action, replay and exact business-event checks.

The engineering scope is bounded. The test does not establish a complete permission boundary for arbitrary SQL, guarantee a safe lock order for every old or privileged writer, demonstrate interrupted migration recovery, or qualify tenant serialization overhead under the full workload. Old writers require fencing for upgrade. H1–H7, R8 and the existing V3 checks remain separate from this opt-in candidate. Do not deploy or promote it.

Batch 03R remains PARTIALLY_QUALIFIED. SEC-01, SEC-02, and Phase 6 release closure remain BLOCKED. Phase 11 remains IN_PROGRESS. Phase 12 remains NOT_STARTED.
