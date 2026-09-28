# Phase 3 evolution and history corpus

[evolution.json](evolution.json) contains six content-digest/write-set/risk/compatibility stages for each existing reference domain: initial, stable-ID rename, optional relation, required field, session-policy tightening, workflow guard change. [change_fixtures.py](../../tooling/change_fixtures.py) builds these vectors; tests reproduce them and commit each transition through the authenticated reference repository. These are synthetic specifications, not deployed releases. Workflow restrictions are semantically validated but satisfiability is not proved.

[test_changes.py](../../tooling/tests/test_changes.py) has 24 methods with positive/negative subcases: exact revisions, retirement/supersession, isolated proposals, stale reads/head, independent rebase and conflicting merge, security fences, actual competing SQLite connections, HMAC scope/expiry/revocation/separation, approval invalidation, subprocess crash/retry, rollback, provenance, receipts, stale/failed observations and tampering. A seeded permutation property checks independent operation and map ordering. This is representative coverage, not exhaustive model checking.

[storage-observations.json](storage-observations.json) records one Windows CPython 3.14.7 / SQLite 3.50.4 measurement: six snapshots per domain, physical database and serialized payload bytes, then reopen and anchored audit. Reproduce with `python tooling/history_experiment.py`. Filesystem sizes are observations, not portable golden values or performance targets. Full snapshots and proposal plans intentionally duplicate content.

Run `python -m unittest discover -s tooling/tests -v` for all phases. Test credentials and timestamps are synthetic. Independent Phase 2 canonical byte/hash vectors remain unchanged.
