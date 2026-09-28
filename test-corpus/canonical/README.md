# Canonical Application 0.1.0 corpus

The [Phase 2 contract](../../docs/canonical-ir.md) pins semantic model 0.2.0. All examples are synthetic content candidates, not authenticated application specifications.

| Artifact | Purpose |
| --- | --- |
| [payment.json](payment.json), [case-management.json](case-management.json) | Normalized framework-neutral content; their union exercises all 69 semantic kinds. |
| [manifest.json](manifest.json) | Expected complete canonical-content digests and full synthetic authoring-source digests. |
| [byte-vectors.json](byte-vectors.json) | Nine explicit expected byte strings/hashes and thirteen invalid wire inputs, portable across runtimes. |

Vectors cover object ordering, numeric-looking keys, UTF-16 versus code-point ordering, exact Unicode preservation, string escaping, safe integers and negative zero; rejection covers duplicate/escaped keys, unsafe/non-integer numbers, invalid surrogates, BOM, nesting and trailing input. Both implementations additionally reject malformed UTF-8 and oversized input. The independent Node checker verifies both complete snapshot hashes as well as the byte vectors.

[test_canonical.py](../../tooling/tests/test_canonical.py) adds semantic tests for graph/set permutations, ordered steps/Lists/operands, exact decimals, nominal/nullable/value types, numeric-looking literal metadata, quality thresholds, reference and schema failures, tampered/non-normal content, lifecycle/blocking issues, missing/denied authority, immutable admission, explicit migration, identity continuity and digest-bound reapproval. These are in-test migration/evolution fixtures rather than a claim that a future canonical version exists. Historical 0.1 authoring and all Phase 1 tests remain unchanged regressions.

[canonical_fixtures.py](../../tooling/canonical_fixtures.py) regenerates example candidates and manifests from copies of the two Phase 1 domains. Its helper explicitly marks records active and creates **fixture-only** attestations. It is never called by the normalizer to approve user input. Review fixture changes before accepting new golden hashes. Tests compare committed fixtures to regenerated data without rewriting files. Node.js independently derives bytes/hashes; it does not implement the 69-kind semantic analyzer.
