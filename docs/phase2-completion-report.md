# Phase 2 Canonical IR report

Date: 2026-09-28. Scope: Canonical Application `0.1.0`, semantic model `0.2.0`, byte profile `acp-jcs-safe-v1`.

Status: implementation and local validation complete; hosted Ubuntu/Windows CI pending. Phase 3 has not begun. Closure requires both hosted jobs to pass.

## Delivered scope

- [ADR-0011](adr/0011-canonical-interchange.md) resolves P-07 for bounded JSON interchange, semantic normalization, digest separation, exact version compatibility and immutable candidate import.
- [Canonical contract](canonical-ir.md) and [closed schema](../contracts/canonical.schema.json) retain all 69 typed semantic kinds, exact references, security constraints, issues, provenance and modeled obligations.
- [Reference harness](../tooling/canonical_ir.py) provides candidate normalization, full semantic/normal-form/digest validation, immutable admission through an external trusted authority port, and a registered authoring-to-canonical migration receipt.
- [Portable corpus](../test-corpus/canonical/README.md) includes both domains, expected hashes and positive/negative byte vectors. [Tests](../tooling/tests/test_canonical.py) cover strict ingestion, semantic equivalence and meaningful order, tampering, compatibility, migration, approval rejection and input immutability.
- An independent [Node.js implementation](../tooling/check_canonical_vectors.mjs) checks bytes/hashes and strict input rejection. It does not select Node.js as a production runtime.

## Validation evidence

Local Windows/CPython 3.14.7 full regression suite: **39 tests passed in 145.537 seconds**, comprising the original 23 tests and 16 Phase 2 tests. Repository link/whitespace checks, dependency consistency and diff checks passed. Both canonical examples also passed the CLI with `authorityVerified: false`.

Independent Node.js 24.21.0 in the local Linux tooling container: **PASS** for 9 positive byte/hash vectors, 13 negative inputs, malformed UTF-8, oversized input, and both complete example content hashes. Hosted Ubuntu/Windows evidence is pending. The CI workflow runs all Python tests and the independent Node checker on both OSs.

## Exit criteria

| Criterion | Status / evidence |
| --- | --- |
| Framework-neutral typed schema and semantic closure | Implemented; both domain examples cover 69 kinds |
| Explicit serialization and canonical hash vectors | Implemented; independent Node.js check passed |
| Set/sequence, exact number, Unicode and round-trip rules | Implemented with positive and negative tests |
| Exact version/feature rejection and migration/reapproval | Implemented for the only registered source/target pair |
| Authenticated approval remains independent of content validity | Contract and fail-closed port tested with synthetic authority doubles; real authority is later work |
| Local regression suite and repository checks | PASS: 39 tests, repository/diff checks and dependency consistency |
| Ubuntu and Windows CI including independent byte checks | Pending push |

## Limits and next phase

Only authoring 0.2.0 -> canonical candidate 0.1.0 migration is registered. No speculative future-version migration, downgrade, history engine, state storage, journal, concurrency/merge, authenticated authority implementation, compiler pipeline, target generation or production signature format is provided. The reader detects edited content through digest mismatch or stale exact-content approval; history-aware revision enforcement is Phase 3 work. Cross-runtime evidence validates the byte profile, not independently reimplemented semantic analysis.

The bound on quality-threshold expansion is an explicit canonical input restriction, not a change to historical Phase 1 fixtures. Unicode normalization, arbitrary expression/prose equivalence and visual UI order are not inferred. Source records excluded from canonical identity must be retained by a future repository using the migration receipt's source digest.

Next is Phase 3 change/provenance design: P-06 immutable snapshots and atomic journal, revision/read-set conflicts, provenance retention and approval integration. P-09 and P-12 retain their ownership/evidence authority work. ADR-0004 remains PROPOSED; no production language/parser is selected.
