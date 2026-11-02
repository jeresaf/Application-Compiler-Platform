# Phase 10 R6: transactional document preview

R6 is an unapproved synthetic reference candidate. It adds Authoring 0.7 / Canonical 0.6 and mandatory `acp.documents/1`. This version is distinct from generator release 0.6. The exact R0–R5 nodes and their review records remain unchanged; their proposals have not acquired semantic approval. The kernel's immutable JSON `Document` carrier and existing Evidence/Entity constructs do not grant application upload or binary-storage authority.

`DocumentDefinition` declares the owning resource, generated identity, authenticated tenant, metadata and content SHA-256, permitted type, byte bound, storage consistency, exact association, upload/read permissions, auditing, idempotency and retrieval. `DocumentPermission` binds actor/role/scope and the resource's principal field. `DocumentView` binds the screen and both grants. Unknown policies, types, versions, permissions and mismatched references fail closed. The current target supports one definition/view for one tenant-scoped single-identity resource. R4/R5 remain separately proposed dependencies of this candidate.

The target reuses explicit compiler registration, all eight stages, ArtifactPlan/CAS, existing rendering, ownership and provenance. The compatibility rendering view contains the original R5 nodes; document artifacts and the full runtime model retain the new exact origins. No constant rewriting is added. Insignificant leading Java indentation/blank lines are removed in this new target (text-block files are excluded) to respect the unchanged 1 MiB stage limit. The generated code is analyzed and built after this transformation; no sealed source or historic generator file is rewritten.

## Supported policy

The bounded preview stores exact bytes in PostgreSQL `bytea`, transactionally with metadata, idempotency and upload auditing. Download audits link the exact document and content hash to the existing audit record. Foreign keys preserve association with the resource. Resource row locking and a unique resource-scoped idempotency key fence concurrent retries. Changed requests conflict; failed transactions publish neither partial content nor audit links. Retrieval checks stored byte length and SHA-256 before returning content. This is corruption detection within the trusted test database, not independently signed storage custody or resistance to a privileged database attacker changing both content and metadata.

Only nonempty, strict UTF-8 `text/plain` `.txt` files are supported, with no NUL or prohibited control characters. The semantic maximum is 65,536 bytes. the `acp.documents.maximum-bytes` runtime property may lower that bound; an invalid or higher configured value rejects startup. Zero selects the semantic default. The multipart parser also has bounded request/file limits. Text MIME and encoding checks do not constitute antivirus or a general file-safety guarantee.

Filenames must be bounded ASCII basenames ending in `.txt`; traversal, separators, control characters and unsupported names are rejected. They are metadata, never storage paths. Resource identifiers use the declared ASCII-token policy (at most 128 characters). Document identifiers are canonical UUIDs. The server ignores no extra metadata: unknown request fields are rejected. Tenant and principal come only from authenticated context. Every operation revalidates the exact grant and current resource owner; knowing a UUID grants no access. Disposed/indeterminate resource content cannot be retrieved.

Downloads use attachment disposition, octet-stream, `nosniff`, `no-store` and a sandbox CSP. There is no public/static document directory or sharing endpoint. The frontend hashes uploaded and downloaded bytes, exposes loading/validation/error states and preserves a failed unchanged upload's retry key. Tenant/principal changes remount the protected panel and discard previous state. The generated controller requires both development runtime and `ACP_DOCUMENTS_MODE=preview`; it is disabled by default.

## Run

Use the isolated pinned SDK/compiler environment and the toolchains from `.github/workflows/phase10-r6.yml` (hosted Ubuntu 24.04 / CPython 3.14.7 / Node 24.21.0 / JDK 21 / digest-pinned PostgreSQL 18.6).

```sh
python3.14 -B -m unittest discover -s verification/documents -v
python3.14 -B -m engineering.documents.run --workspace /tmp/acp-r6-new
```

A fresh workspace and free loopback ports are required. Optional retained `--maven-seed`, `--npm-seed`, `--browser-seed` and `--offline` reuse existing inputs. Do not install dependencies without the applicable permission. The runner uses a new owned disposable database only. It runs R4 CREATE/workflow and R5 report journeys before adding new data, then performs real UI upload/download and native CREATE → upload → Review → Approve → Archive. It checks exact bytes, scoped metadata/listing, two-tenant denial, malformed/unsupported/oversized inputs, concurrent retries, conflicting retries, rollback after injected audit failure and detection of altered content. Test administration endpoints exist only in the external disposable test adapter; they are excluded from the production application package.

The application is regenerated, HUMAN source is preserved, managed drift is rejected, and a freshly built JVM/frontend replays against the same database. Existing rows and content must remain exact. The only allowed new audit/link rows during replay are the two measured legitimate document downloads; original audit records must be unchanged. Actual browser JSON and database observations are hash-bound through the existing Phase 8 execution interface. Four `CANDIDATE_RUNTIME_OBSERVATION` records describe measured behavior; they do not turn semantic obligations or human decisions into PASS. Missing obligations remain NOT_RUN/BLOCKED.

Phase 7 source analysis and the nine existing read-only MCP tools use `case-management-document-preview`; accepted aliases remain rejected. Vue analysis retains the existing completeness limitations. Local precommit execution and exact committed hosted execution are recorded separately. Required evidence must be preserved under the approved append-only R6 vault destination before removing any execution directory.

## Review and production boundary

`proposals/phase10-r6-documents/review.json` binds the exact new requirement, six new objects, candidate, contracts and proposed permissions. Node lifecycle `APPROVED` is structural compiler eligibility, not human acceptance. No accepted history, retained R1 migration, deployment or production authority is created.

Production obligations remain unresolved: independently accepted semantics and authority; real OIDC/transport/TLS and key custody; quotas and abuse/rate controls; malware/content safety; retention/erasure/backup policy and operational restore evidence; storage encryption/access administration and independently protected integrity/custody. This increment provides no antivirus, external object store, OCR, asynchronous processing, public sharing or production storage approval. Historical security findings and all Phase 6 release blockers remain unchanged. Phase 10 is IN_PROGRESS, Phase 11/12 NOT_STARTED; operational security NOT ESTABLISHED; production release NOT AUTHORIZED.
