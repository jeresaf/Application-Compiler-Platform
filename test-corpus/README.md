# Portable semantic corpus

`semantic/reference.json` is a fully synthetic authoring draft containing all 20 executable kernel kinds. It describes typed money, tenant-scoped payment authorization, and a two-state workflow. It is not an approved business design or full financial system.

`semantic/approved.json` contains synthetic attestation records and APPROVED lifecycles to exercise necessary compile-closure checks. No fixture reviewer is a real authority; no fixture can authorize release.

`semantic/cases.json` contains named valid/invalid cases. Each selects a base and validation mode, applies edits, and lists the exact expected `(code, subject)` diagnostics, including multiplicity. Empty expectations mean kernel-valid only.

## Edit notation

An edit has `op`, `node`, `path`, and (except delete) `value`. `node: null` addresses the document; otherwise it selects a node by semantic ID. `path` is an array of object keys/list indices relative to that selection. `set` assigns the last property/index, `delete` removes it, `append` appends to the list at that path. Operations run in order against a deep copy. This is test-fixture notation, **not** the production change-set protocol or an implementation of JSON Patch.

The runner compares stable codes/subjects, checks input immutability and repeatability, and separately tests schema coverage, malformed input, rename continuity, ordering and closed-world properties. Compiler implementations in other runtimes should reuse these fixtures and diagnostic expectations. Future target golden/property/migration/integration/security/drift suites belong here only when their respective stages become executable.
