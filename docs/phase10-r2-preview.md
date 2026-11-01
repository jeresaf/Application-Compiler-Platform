# R2 synthetic evolution preview

This increment exercises the existing Case Management proposal without accepting
history or authorizing migration of the retained R1 population. The 0.5.0 seal,
0.6.0 candidate fingerprint, Canonical contracts and release predicates remain
unchanged. R0/R1 evidence is immutable.

Run focused tests with the existing isolated compiler/SDK environment:

```bash
python3.14 -B -m unittest verification.reference_application.test_evolution -v
python3.14 -B -m engineering.reference_application.evolution \
  --workspace /tmp/acp-r2-preview \
  --maven-seed /absolute/retained/m2 --npm-seed /absolute/retained/npm --offline
```

Use a new execution directory. Installation permission is required for missing
pinned inputs; `--offline` uses retained inputs only. Docker must have the pinned
PostgreSQL 18.6 image from the existing runtime. No existing database URL is
accepted. All processes and newly allocated containers are removed; evidence
files remain. The workflow uses Ubuntu 24.04, CPython 3.14.7, Node 24.21.0 and
Java 21. Local environment versions are recorded without claiming equivalence.

Native `changes.prepare` reproduces the exact historical proposal and candidate.
The existing unsealed successor supplies lowering, schema and ArtifactPlans.
Native CAS publication preserves HUMAN-owned identity code. No accepted-history
adapter or fake approval receipt is supplied. The bounded SQL preview exposes
EXPAND, population-specific synthetic BACKFILL, VERIFY and CONTRACT separately.
An independently restricted old-writer role is fenced before final enforcement.
The final schema has no default and rejects omitted/null values. The synthetic
Unicode/NUL vector is a test mapping, never an approved retained-row binding.

The actual evolved generated backend and frontend are built. Disposable runtime
configuration points Flyway to the exact original generated initial migrations;
the evolved fresh-schema V1 is not substituted into historical migration history.
The preview ALTER statements run separately, outside any accepted migration plan.
Generated Commands, authorization, tenant isolation and idempotency are exercised
against the final schema, including a fresh JVM restart. There is no create API;
new records use explicitly identified synthetic fixture provisioning.

The original approved application is analyzed with Phase 7 and Phase 8, and the
proposal's semantic impact is joined to that model and exact changed artifacts.
Those existing adapters bind original approved snapshots. They cannot admit a
candidate Source Model or candidate semantic PASS without genuine ancestry.
Candidate obligations remain BLOCKED/NOT_RUN; the preview does not graft new
origins onto an approved model. Historical security findings remain outstanding.

Optional `--restore` accepts only the exact preserved Phase 10 custody archive
(SHA-256 `4d423b70bf57042aa1441add414cfdbfa9019de463ba61d9b0148226ccfdae61`).
The verified dump is restored into a second new container, never an existing DB.
Schema/history, complete stored rows, tenant bytes, audit and idempotency state
are compared with the frozen capture. The original archive is rehashed unchanged.
This is recovery evidence, not R2 execution permission.

`authorization-package.json` binds proposal, documentary decision, preview SQL,
synthetic population and remaining decisions. An actual R1 execution additionally
requires authenticated exact content approval, genuine accepted history/rebased
plan, independently approved current-population values, exact writer rollout,
SQL/recovery and execution approval. No previous three-row binding applies.
Semantic content approval, authenticated acceptance, data binding, migration and
deployment authorization are separate decisions. No deployment is authorized.

Phase 10 remains IN_PROGRESS. Phase 11/12 are not started.
PHASE6_CLOSURE_BLOCKED; PHASE6_RELEASE_CLOSURE_BLOCKED.
