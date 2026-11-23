# H9 HTTP classification and CREATE diagnostics

H9 addresses H8 REL-02 and REL-01 independently. It is a source-fingerprinted,
unsealed successor over H6, using the existing Canonical compiler, Target IR,
ArtifactPlan publisher, provenance, native Source Intelligence and Phase 8
verification. Historical 0.5.0/0.6.0, H1/H5/H6 sources and identities, migrations,
all 39 release predicates and the entire H8 review remain unchanged.

## HTTP compatibility

The sealed target fault map `acp-failure-mapping.json` version 1.1.0 lists exact
exceptions and SQLSTATE mappings; unknown conditions default to INTERNAL_ERROR
500. Spring's exact `NoResourceFoundException` is not listed. The unchanged H6
application therefore returns a redacted 500 for authenticated unknown API and
static resource paths. Anonymous access is still rejected by Spring Security
before MVC. H9 first generates/builds and tests this baseline independently.

The user explicitly approved only the H9 transport extension: exact concrete
`org.springframework.web.servlet.resource.NoResourceFoundException` → 404,
`RESOURCE_NOT_FOUND`, `HTTP`, `retryable:false`. This is not a Canonical business
failure or a release approval. The H9 Errors successor adds this one branch and
falls through to the unchanged native mapping otherwise. There is no message
matching, arbitrary cause unwrapping or blanket replacement of 500. The parent
fault map remains byte-identical.

| Condition | H9 contract |
| --- | --- |
| Authenticated unknown API/static resource | Approved exact-class 404 envelope |
| Anonymous route or CREATE | Existing 401 security boundary |
| Authenticated principal without applicable grant | Existing 403; token roles grant nothing |
| Cross-tenant or unavailable business resource | Existing 404 without existence disclosure |
| Malformed JSON | Existing mapped 422; generated request validation retains its 400 |
| Unsupported method/media type/missing servlet parameter | Existing generic 500 retained; no approval to broaden this correction |
| Unexpected injected NullPointerException | Existing INTERNAL_ERROR 500; no exception message leaked |
| Successful CREATE and document upload/download | Unchanged native result and exact data behavior |
| Pool exhaustion, rate policy and retry | Unchanged; no new 503 or automatic retry policy |

## Execute

With separately approved isolated provisioning and existing pinned inputs:

```sh
PYTHONPATH=tooling:. python3.14 -B -m unittest discover -s verification/http_reliability -v
PYTHONPATH=tooling:. python3.14 -B -m engineering.http_reliability.run \
  --workspace /tmp/acp-h9-unique --maven-seed /approved/m2 --npm-seed /approved/npm --offline
```

Use a new isolated execution directory. The runner accepts no production DB URL.
All PostgreSQL 18.6 containers and volumes have fresh ownership identities and
must be removed; JVMs and ephemeral issuer resources must be closed. Raw runtime
logs stay private. Native generation and builds consume the generated source.
The public export has an exact allowlist and is scanned against actual issued
credentials/private keys, metrics capability and test database password.

The dedicated Ubuntu 24.04 workflow pins CPython 3.14.7, Node 24.21.0, Java 21 and
the existing PostgreSQL image digest. It requires baseline reproduction, the H9
HTTP matrix, genuine H5 cryptographic security regressions, finite CREATE
observations, unchanged parent identities/migrations, provenance and cleanup.
An unresolved historical finding is distinct from a failed required assertion.

## CREATE diagnostic boundary

`workload.json` specifies nine finite variants and 44 one-submit attempts,
maximum eight clients, 34 pool connections, 64 new cases and a bounded study
deadline. It varies client count, session sharing, tenant/key distribution,
replay, pool size and fresh process startup without resetting native rate buckets.
All statuses, including expected rate rejection and unexpected failures, remain
recorded. There is no automatic retry or repetition until success.

H4's external exception observer is reused with H6's server-generated correlation.
External observations retain exception class/SQLSTATE, hashed authenticated
principal/tenant, request start/completion, aggregate Hikari acquisition timings/counts, occupancy/awaiting state and
H6 transaction/idempotency/HTTP events. Raw token, key, session cookie, payload,
SQL parameters or exception messages must not enter the public record. Client
correlation headers are not trusted. Read-only PostgreSQL transaction/lock/worker samples and exact native
idempotency identities reconcile committed results, ownership, CREATE and audit effects; HTTP status alone is insufficient. The database outcome describes an exact
idempotency key, not which concurrent replay created it. A 202 or 429 replay can
observe a key committed by another request; effect counts use unique committed
keys. Missing committed evidence is not mislabeled as a proven rollback.

The original H3 normal CREATE 500 record remains immutable at
`.audit-artifacts/phase11-h3-20261103/runtime-5/failure.json`. It records a measured
four-client CREATE failure at approximately 1.107 seconds; it lacks a complete
correlated exception/acquisition/transaction trace. H4 controlled pool exhaustion
is an analogous failure, not proof of the original cause. Current H9 signed
identity and 750 ms laboratory pool settings also differ from historical H3.

REL-01 stays `UNRESOLVED_NOT_CAUSALLY_ATTRIBUTED` unless independent causal
execution establishes otherwise. `NO_REPRODUCTION_OBSERVED` means only the
finite study did not reproduce a 500. `INJECTED_ANALOGOUS_FAILURE` identifies errors confined to the deliberately
smaller pool; it is not labeled a normal-profile or original reproduction.
`CURRENT_PROFILE_FAILURE_CAUSE_UNRESOLVED` retains a failure in an ordinary
current-profile variant. A later normal failure is retained as a
new observation with unresolved historical attribution, not silently labeled the
same original defect. No claim of per-connection acquisition instrumentation,
production SLO, arbitrary load support or exactly-once processing is made.

## Authority and remaining limits

H9 does not implement H8 REL-03/REL-04. Pending-job bounds, overload responses,
transaction deadlines and unsupported deployment profiles require separate
explicit decisions. Existing worker fencing/recovery is preserved and remains
qualified separately by H2/H7; no synthetic production worker identity is issued.
The separately approved append-only evidence destination is
`/home/aiko-jerry/ACP-Evidence-Vault/phase11-h9-http-reliability-20261115/`.
Existing vault entries must remain unchanged; raw database captures, bearer
tokens and private keys are excluded.

All results are QUALIFICATION_ONLY. Phase 11 remains IN_PROGRESS; Phase 12 is
NOT_STARTED; operational security is NOT_ESTABLISHED; release closure remains
BLOCKED. Neither a 404 correction nor a passing diagnostic study resolves the
historical CREATE finding or grants production acceptance.
