# Native CREATE preview

Authoring **0.5.0** and Canonical **0.4.0**, with mandatory
`acp.native-create/1`, add closed `CreateOperation`, `CreatePermission` and
`CreateForm` nodes. Earlier contracts and their default admission remain unchanged.
This is an unapproved synthetic semantic proposal, not an accepted transition.
The `APPROVED` lifecycle flag is structural compiler eligibility only: the local
fixture authority is explicitly test-only and cannot issue human acceptance.

A CREATE binds one scoped resource, its identity, authenticated tenant and subject,
initial state, separate permission, complete field bindings, idempotency, rate
policy, mandatory audit and explicit empty business-event effects. The bounded
target supports one CREATE/form, a single identity (generated UUID or supplied
Identifier), required String inputs or singleton String ValueObjects, and explicit
absence of optional fields. Unsupported types, optional request inputs, multiple
CREATE operations, unscoped resources and unsupported versions fail closed.
The proposed CreatePermission explicitly grants the new operation to an exact actor/role/scope assignment. It does not reinterpret the old Role.permissions list or grant CREATE in old snapshots. Human review must approve this new permission meaning. String lengths count Unicode code points; stored text is neither trimmed nor normalized. Required inputs must be present and correctly typed. Optional ABSENT bindings persist absence rather than inventing defaults. No selection of an existing resource is needed. The old ordered workflow remains
Review → Approve → Archive; CREATE does not alter UPDATE semantics.

The existing compiler kernel supplies every stage, its budgets, approval ports,
projection/provenance checks and ownership/CAS validation. A private version
binding specializes only its fixed frontend dispatch tables; no root module state
is patched. The application target reuses the existing deterministic execution
renderer as an explicit **0.3 rendering ABI**. Exported specifications and runtime
models retain Canonical 0.4 identity. `contracts/target-ir.json` is a hash-bound
reference to the full runtime model, avoiding duplicate model bytes within the
unchanged compiler budget. This interface does not authorize migration of an
existing database.

Run focused checks with the existing compiler/MCP environment:

```sh
python3.14 -B -m unittest discover -s verification/native_create -v
python3.14 -B -m engineering.native_create.run --workspace /tmp/acp-r4-new
```

The second command builds and executes a freshly generated application and owns
its disposable PostgreSQL container. It must not point at retained databases.
Existing pinned provisioning policy applies. Its test identity adapter tests trusted
JWT/session behavior, not issuer cryptographic validation. Source Intelligence
retains its documented partial Vue/dynamic-analysis limits. Phase 8 missing
behavior witnesses remain NOT_RUN or BLOCKED; an artifact-integrity PASS is not
semantic acceptance.

A separate MCP entrypoint, `engineering.native_create.mcp`, serves only
`case-management-create-preview`. Default approved-application services reject this
candidate. The preview provides read-only specification, source, impact, plan and
verification inspection; no acceptance or execution authority.

Review `proposals/phase10-r4-create/review.json` and the exact candidate digest
before granting semantic approval. No data binding, accepted journal, retained-data
migration, production deployment or release approval is included. The sealed
0.5.0 bundle, historical unsealed 0.6.0 identity, R0–R3 evidence and Phase 6 closure
criteria remain unchanged. Phase 6 release closure remains BLOCKED; no Phase 11
or later work is authorized by this increment.

Inherited security findings remain open. This increment does not rescan, suppress or resolve them.
