# ADR-0011: Canonical interchange and exact-content approval boundary

Status: ACCEPTED for the bounded Phase 2 contract and reference harness. Date: 2026-09-28. Resolves P-07 at Canonical Application `0.1.0` / semantic model `0.2.0` scope. Production implementation language, storage and authenticated approval services remain unselected.

## Problem and alternatives

Authoring model 0.2.0 admits candidates and fixture attestations. Its JSON representation does not establish canonical bytes, immutable content identity or trusted approval. Phase 2 needs portable types, normal forms, version rejection and migration tests before later compiler/storage work can depend on digests.

| Alternative | Assessment |
| --- | --- |
| Versioned JSON with a constrained JCS byte profile | Reuses inspectable JSON fixtures and closed schemas. Requires explicit semantic normalization, integer restrictions and Unicode vectors. Selected. |
| Deterministic CBOR | Supports a binary interchange with deterministic encoding options, but requires an additional codec and application profile. No measured compactness or throughput requirement currently justifies that cost. Deferred. |
| Native runtime serialization only | Does not supply a language-neutral interchange contract and would prematurely couple the model to a production language. Rejected. |

[RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html) defines JCS property ordering by UTF-16 code units, exact string escaping and preservation of Unicode strings. ACP restricts JSON number tokens to safe integers; arbitrary-precision domain numbers remain strings. ACP does not implement JCS's general floating-point number domain. [RFC 8949 section 4.2](https://www.rfc-editor.org/rfc/rfc8949.html#section-4.2) specifies deterministic CBOR requirements; that is an alternative encoding, not a substitute for deciding ACP semantic equivalence.

## Decision

Adopt the [canonical contract](../canonical-ir.md), the closed [schema](../../contracts/canonical.schema.json), and byte profile `acp-jcs-safe-v1`. The envelope contains canonical content plus its domain-separated SHA-256 digest. The content includes application identity, exact semantic/schema/profile versions, required features, typed nodes and retained issues. References and node revisions remain exact. All 69 Phase 1 kinds retain their constraints and framework-neutral meaning.

Normalize sets, keyed collections, numeric literals and temporal fractions under explicit rules. Preserve ordered steps, operand order, Lists, absence/null distinctions, nominal identity, security settings, evidence obligations and text. Do not erase provenance to improve cache reuse. Unicode normalization is not implicit. No behavioral theorem proving or general expression equivalence is claimed.

Content identity excludes export snapshot labels and external approval attestations. Import retains a digest of the complete authoring source in its migration receipt so excluded source records remain traceable. Source must be archived by the future repository service; this harness does not persist history. A content digest is never an approval. The CLI creates candidates and checks content; only a trusted host-supplied ApprovalAuthority can admit exact-content bytes. No JSON property selects an authority or approves itself.

Version readers are exact, including patch versions. No automatic 0.1 authoring upgrade, unknown feature negotiation, or canonical downgrade is available. The sole registered migration imports authoring 0.2.0 into canonical 0.1.0 candidates with stable identities and mandatory new digest-bound approval. Later semantic migrations require their own ADR, immutable fixtures, comparison and approval evidence before registration.

## Evidence and limits

The [Python suite](../../tooling/tests/test_canonical.py) exercises both reference domains, all 69 kinds, ordering, value equivalence, strict decoding, schema/semantic rejection, content tampering, immutable admission and migration/reapproval. [Portable vectors](../../test-corpus/canonical/byte-vectors.json) have explicit expected byte strings and digests; an independent [Node.js checker](../../tooling/check_canonical_vectors.mjs) checks those vectors and both complete example hashes. Cross-runtime evidence covers strict byte encoding/hashing, not a second implementation of the semantic analyzer. [Phase 2 report](../phase2-completion-report.md) records actual local/CI results.

Python and Node.js are replaceable test tools under the scope of ADR-0003. This decision does not satisfy ADR-0004's production-language/parser experiments, P-06 storage/concurrency, P-09 provenance history, P-12 authenticated evidence, or a production signature/wire service. Signatures may eventually bind these bytes, but signature format, authority identity, revocation and transport remain separate decisions.
