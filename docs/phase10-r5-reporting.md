# Phase 10 R5: reporting and audit preview

This is a proposed synthetic reference, not accepted application history or release evidence. Authoring 0.6 / Canonical 0.5 adds `ReportDefinition`, `ReportPermission`, `AuditHistory` and `ReportView`. Existing R4 CREATE semantics and all approved Canonical snapshots remain unchanged. The original Query/Search/Table contracts do not establish COUNT or audit-read authority; the new permissions are explicit proposals.

`engineering.compiler_extensions.dispatch` registers a private version-scoped binding of the existing eight compiler stages. It preserves their code objects and validates the actual frontend, compiler, pipeline, features and target identities. The transport compatibility view is used only by existing manifest validation. It does not change source snapshots, stage outputs or evidence. No new constant rewriting is used.

The reporting target derives SQL columns, endpoints, projections and Vue contracts from declared resource/field/permission identities. It reuses the existing generator, ownership, ArtifactPlan and provenance implementations. The target identity includes its reporting templates, contracts and extension dispatch; historical generator 0.6 and sealed 0.5 identities are unchanged.

## Bounded semantics

Selected fields must belong to the report resource and have PUBLIC or INTERNAL classification. The current backend supports required String/Identifier fields and a single member of a required singleton value. Optional fields, joins, exports, arbitrary SQL, general aggregates and arbitrary nested projections are unsupported. Typed STRING EQ/CONTAINS and STATE EQ filters are closed; order keys must be selected fields, STATE or IDENTITY. Pagination has an explicit maximum and deterministic identity tie-break. COUNT groups the filtered authorized population by workflow state.

Each report and audit read requires its own exact actor/role/scope grant. The synthetic second tenant uses a distinct globally identified user, `fixture:reporter-two`, and the explicitly proposed `ASSIGN-R5-TENANT-TWO` role assignment; no approved assignment is modified. The proposed reference restricts both to the authenticated tenant and assigned owner. Tenant/subject predicates come from authenticated context, never request filters. Authorization precedes projection. A case must be accessible before its audit rows are queried. History is restricted to the declared resource operations and exposes operation/time only, not private payloads, actor credentials or unrestricted audit exports. Disposed/indeterminate resources are excluded. SQL parameters carry all request values. Reads use a consistent read-only transaction; session validation remains active outside it.

The preview requires development runtime plus `ACP_REPORTING_MODE=preview`. It grants no production deployment authority. The test identity adapter supplies trusted JWT component-test claims; this is not cryptographic OIDC qualification.

## Reproduce

Use the existing pinned SDK/compiler environment, Python 3.14.7 in hosted Ubuntu 24.04, Node 24.21.0, JDK 21 and the digest-pinned PostgreSQL 18.6 image from `.github/workflows/phase10-r5.yml`.

```sh
python3.14 -B -m unittest discover -s verification/reporting -v
python3.14 -B -m engineering.reporting.run --workspace /tmp/acp-r5-new
```

Use a fresh workspace. The runner refuses occupied application ports and existing workspaces. Local offline runs can pass retained `--maven-seed`, `--npm-seed`, `--browser-seed` and `--offline`; provisioning requires the applicable dependency permission. Dependencies stay in disposable execution directories. The runner creates and removes only its own tmpfs PostgreSQL container; it never accesses production databases.

It generates actual backend/frontend source, compiles it, creates cases through native CREATE, runs Review → Approve → Archive, and executes genuine report/history HTTP and browser queries across two tenants. A separately labelled non-owner fixture tests ownership exclusion. It checks invalid requests, auth failures, isolation, field exposure, page boundaries, persistent results, regeneration, source drift and unchanged audit rows. A new JVM uses the same disposable database after regeneration. HUMAN code remains byte-identical. Results include source hashes, plans, source models, database captures, test logs and screenshots.

Phase 7 source analysis, Phase 8 verification and the existing nine read-only MCP tools use the separate `case-management-report-preview` namespace. Missing obligations remain BLOCKED or NOT_RUN. No laboratory evidence resolves Phase 6 release blockers. Hosted results must bind the exact committed source; local precommit execution is identified separately.

Review `proposals/phase10-r5-reporting/review.json` for the exact semantic candidate and decisions. Structural `APPROVED` node lifecycle permits compiler validation only; it is not human acceptance. Migration, accepted-history insertion, production authority and deployment remain unauthorized. Phase 10 is IN_PROGRESS; Phase 11/12 are NOT_STARTED; operational security is NOT ESTABLISHED and production release is NOT AUTHORIZED.
