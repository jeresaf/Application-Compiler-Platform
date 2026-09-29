# Phase 3 Change and Provenance report

Implementation date: 2026-09-28; closure verified 2026-09-29. Scope: ChangeSet/reference history 0.1.0 over unchanged Canonical Application 0.1.0 and semantic model 0.2.0.

**PHASE 1 = CLOSED AND GREEN. PHASE 2 = CLOSED AND GREEN. PHASE 3 = CLOSED AND GREEN. PHASE 4 = NOT STARTED.** Local validation and both hosted jobs passed for implementation commit `d5dd58864c5ff9bfe078c56c81d522635dbd2016`. The documentation-only closure commit uses the same CI workflow.

## Delivered contract and decisions

[ADR-0012](adr/0012-change-history.md) evaluates mutable documents, event sourcing and immutable snapshots plus journal. The bounded implementation selects immutable snapshots with atomic semantic journal behind ports; it does not adopt full event sourcing or select production storage. P-06 and semantic-history P-09 are executable. Generated-source ownership and regeneration remain open.

The [logical change model](change-model.md), [executable protocol](change-reference.md), [closed schema](../contracts/change.schema.json), [planner/ports](../tooling/changes.py), [repository](../tooling/history_repository.py) and [reference authority](../tooling/reference_authority.py) define the reviewable implementation. [Tests](../tooling/tests/test_changes.py) and [corpus](../test-corpus/change/README.md) supply evidence.

## Requirement-to-evidence map

Numbers correspond to the authorized Phase 3 request. All behavior is bounded reference behavior, not a production-readiness claim.

| Requirements | Implementation and executable evidence |
| --- | --- |
| 1 immutable snapshots/history; 2 append-only journal | Full snapshots and historical revisions; SQL mutation guards; reopen, index/hash audit and tamper tests |
| 3 ChangeSet identity/lifecycle; 4 exact base | Isolated proposal event histories, terminal states, author checks; sequence/content/journal binding tests |
| 5 four operations; 6 prior/next revision; 7 stable identity | ADD/REVISE/DEPRECATE/SUPERSEDE, exact +1 rules, dependent reference propagation, rename, no-op/revision-skip and retired-ID tests |
| 8 read/write sets; 9 dependency concurrency; 10 stale base | Dependency closures, node digests and absent-ID reservations; stale-read/head tests and real competing connections |
| 11 semantic conflict; 12 branches; 13 independent rebase; 14 merge | Isolated candidates, incoming-dependency detection, security/workflow fences, fresh rebase approvals and persisted MERGE_REQUIRED tests |
| 15 diff; 16 transitive impact; 17 risk/compatibility | Before/after values and changed fields, exact-reference closure, explicit external NOT_ANALYZED and reviewed risk/migration classification; deterministic vectors and permutation tests |
| 18 provenance | Exact requirement -> locked decision -> concept -> change -> snapshot lineage, retained basis revisions/origins and scoped-review tests |
| 19 exact approval; 20 invalidation | Phase 2 content digest plus whole-plan digest; one-byte, impact/read-set and migration edits invalidate prior proof |
| 21 authority port; 22 scope/expiry/revocation/separation | Injected authenticated sessions, HMAC reference proof, independent reviewer, application-scoped grants; expiry/revocation/wrong-app/limited/unavailable-authority tests |
| 23 idempotency; 24 atomic snapshot+journal; 25 crash/retry | Single transaction includes snapshot/indexes/journal/retry/APPLIED; actual subprocess exits after snapshot insert, before commit and after commit; duplicate/key-conflict tests |
| 26 forward rollback | New revisions and journal entries, unchanged earlier history, explicit irreversible forward-repair requirement |
| 27 stale evidence | Exact snapshot/revision-bound observations become STALE after change; failed observations leave accepted history intact |
| 28 migration/irreversibility | Required structural migration plans, UNKNOWN/incomplete rejection, CRITICAL/IRREVERSIBLE approval and rollback safeguards |
| 29 receipts/source digests; 30 historical lookup | Complete input and reproducible Phase 2 import receipt retained; source digest, ID/revision, snapshot sequence/digest queries and export/restore tests |

## Validation evidence

Targeted local Windows suite: **24 Phase 3 tests passed in 245.413 seconds** under CPython 3.14.7. This includes subcases and seeded operation/map-order permutations. Earlier development failures (rename classification, Windows test-handle cleanup and mixed-version subprocess testing) were fixed; failed runs are not counted as closure evidence.

Full local Windows regression: **63 tests passed in 362.524 seconds** (39 earlier methods plus 24 Phase 3 methods). The final rebase transaction refinement and reviewed merge resolution were additionally checked by both rebase tests: **2 passed in 1.563 seconds**. Hosted CI will run the complete suite on the final implementation.

Independent Node.js 24.21.0 in the local Linux tooling container: **PASS**, 9 positive vectors, 13 negative inputs, malformed UTF-8, oversized input and both complete snapshot hashes. Repository links/whitespace, dependency consistency and diff checks passed. Canonical schema, implementation and corpus are byte-for-byte unchanged relative to accepted baseline `085a8d4b97692a148c732ff4d227cd3409c2058d`.

[GitHub Actions run 36435314943](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/36435314943) passed both hosted jobs for the final implementation, including dependency consistency, repository checks, all 63 Python tests and independent Node.js 24.21.0 byte/hash checks:

| Hosted runner | Observed full-suite result |
| --- | --- |
| Ubuntu 24.04 | [PASS: 63 tests in 84.835 seconds](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/36435314943/job/108971600446) |
| Windows 2025 | [PASS: 63 tests in 196.377 seconds](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/36435314943/job/108971600102) |

All required Phase 3 exit checks are satisfied. Canonical vectors remain unchanged, earlier regressions are green, both domain evolution sequences pass, and documentation accompanies the executable contracts. No Phase 4 work was begun.

Both domain sequences execute **initial -> stable-ID rename -> optional relationship -> required field -> security tightening -> workflow change**. Each accepted transition is authenticated and audited, with exact historical revisions retained. Golden content hashes/write sets/risk/compatibility are regenerated and compared. Session-policy tightening reduces the idle window; workflow change adds a restrictive guard. These are meaningful semantic changes, not executed application releases or a satisfiability proof.

The [storage experiment](../tooling/history_experiment.py) completed on Windows, Python 3.14.7, SQLite 3.50.4. [Raw observations](../test-corpus/change/storage-observations.json):

| Domain | Entries | Initial database bytes | Final database bytes | Snapshot / journal / proposal payload bytes | Reopen + anchored audit |
| --- | --- | --- | --- | --- | --- |
| Payment | 6 | 307,200 | 2,359,296 | 281,870 / 506,603 / 1,387,260 | PASS |
| Case-management | 6 | 442,368 | 3,235,840 | 420,609 / 710,315 / 1,895,720 | PASS |

This exposes the storage cost of duplicated full plans and snapshots. It supports an inspectable bounded reference model, not a production scale or throughput claim. Operational recovery is additionally tested by abrupt subprocess exit and portable restore into a fresh repository; no hardware power-loss experiment is claimed.

## Safe deferrals and trust limits

- SQLite is a single-application reference adapter with serialized writes. Production storage, multi-node concurrency, pagination, streaming export, retention, backup operations and capacity engineering remain unselected. Portable records and repository ports support future replacement.
- HMAC authority uses injected synthetic sessions/keys/grants and in-memory revocation. Production IAM, key rotation/custody, trusted clocks, durable revocation and remote signing are deferred. Historical proof checking is optional; later revocation never deletes history.
- Hash chains detect partial tampering; external trusted anchors detect coherent rewrites/truncation affecting an anchored prefix. A fully privileged actor can coherently rewrite unanchored data. This limit is demonstrated by a test, not hidden behind a checksum claim.
- Semantic impact is limited to exact-reference closure. Source, generated artifacts, live data, deployment and runtime impact are explicitly unanalysed. Conservative security/workflow conflict fences can require unnecessary manual merges.
- Migration plans bind review obligations and irreversible declarations; no data migration is executed and no live-data compatibility is certified. Rollback creates forward history and cannot undo deployed destruction or resurrect retired IDs. Membership/lifecycle repairs require explicit proposals.
- History observations are untrusted records; production evidence authority and full release orchestration remain later work. A failed build/test/release observation cannot mutate semantic history.
- P-09 source ownership/maps/drift/regeneration, P-08 plugin ABI, P-10 source intelligence, P-11 isolation, P-12 production authority/evidence and P-13 AI adapters remain open. ADR-0004 remains PROPOSED; no language/parser selection, MCP, target generation or application source was begun.

## Reproduction

Use the pinned environment from the [README](../README.md), then run:

```text
python -m pip check
python tooling/check_repository.py
python -m unittest discover -s tooling/tests -v
node tooling/check_canonical_vectors.mjs
python tooling/history_experiment.py
```

The CI matrix runs all tests plus independent Node.js canonical checks on Ubuntu 24.04 and Windows 2025. Repository documentation, schema, reference implementation and tests are committed together. Phase 4 requires a separate authorization and is not started in this task.
