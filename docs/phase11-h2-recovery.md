# H2 concurrency and recovery qualification

H2 reuses the H1 source-bound generator without changing it. The R8 planner has
one explicit, exact H1 successor binding; its default R6/R7 behavior remains
unchanged. H2 explicitly permits only the byte-pinned H1 `backend/pom.xml`
framework upgrade through the native publisher, after proving that an ordinary
publication is rejected without changing source. Other framework updates and
substituted POM bytes remain rejected. This is an engineering preview, not accepted history or migration
approval. Historical migration files, H1 records and sealed 0.5.0 remain intact.

Run with the existing isolated SDK/compiler environment:

```sh
PYTHONPATH=tooling:. python3.14 -B -m unittest discover -s verification/reliability -v
PYTHONPATH=tooling:. python3.14 -B -m engineering.reliability.run --workspace /tmp/acp-h2-new
```

Optional `--maven-seed`, `--npm-seed`, `--browser-seed` and `--offline` reuse the
approved caches. Provisioning requires the applicable authorization. Use a fresh
workspace and free loopback ports 18081/18082/4174. No retained application DB is
addressed. Every PostgreSQL container and temporary restart-persistent volume has
a new execution identity and ownership label, checked before cleanup. Readiness
uses TCP so the image's temporary initialization postmaster cannot satisfy it.

The first stage runs the existing R8 stop–fence–migrate–restart and independently
verified restore procedure, selecting the exact H1 successor for the current
application. It rejects wrong/stale source, population and schema observations,
rolls back failed/interrupted DDL, restarts the owned database between stages,
preserves V1–V4 and installs V5 once. The actual older writer cannot reconnect.
Restore verification authenticates a fresh, uniquely named test session instead of
reviving a captured session after its idle timeout. Captured session rows and the
900-second policy remain unchanged. There is no zero-downtime claim. The historical R6 predecessor is not promoted or
relabelled as H1; its existing security findings remain open.

A second freshly owned database restores the hash-verified synthetic R7 capture.
The exact generated source and consumed compiled-class inventories are verified
before reuse. Four valid durable sessions, two users and two tenants are initialized
before barriers. Four concurrent CREATE requests and four uploads contend at real
PostgreSQL transaction barriers. Case/idempotency/audit counts and every declared
classification field must match; uploads must publish one exact document per key
and reject foreign-tenant access.

External test controls terminate real JVMs before commit and after commit while
responses are buffered. PostgreSQL proves aborted transactions; durable rows and
idempotency replay prove committed outcomes without duplicate effects. A backend
connection is terminated inside an upload, and both database and application are
restarted. Interrupted readiness cannot count as successful recovery.

Two independent worker JVMs claim four queues while execution gates are held.
Lease reclamation requires a different owner; the original completion must be
fenced. A worker is killed after claim and the surviving JVM must recover the
queue. Every terminal result requires its unique audit link. Attempts are at least
once; only the declared, fenced terminal effects are deduplicated. H2 does not
claim exactly-once processing.

Measurements retain request counts, raw latency, explicit replay/attempt counts,
connection observations, queue state and recovery durations. Four-request metrics
include controlled barrier time and provide no production SLO or tail-latency claim.
Source Model validation constructs its identical known-symbol set once per call,
preserving all rejection rules and the existing 30-second MCP timeout.
Unit receipts are labelled synthetic and cannot replace actual runtime evidence.

Phase 7 Source Models and Phase 8 verification bind source, Canonical candidate,
ArtifactPlan, configuration, database and retained assertions. Missing scenarios,
changed evidence, stale identities, serial counterexamples, skipped cases and
unverified cleanup fail closed. Missing semantic obligations remain NOT_RUN or
BLOCKED. Authentication uses the existing trusted-JWT component adapter; H2 makes
no issuer-signature or production identity-provider claim.

The dedicated hosted workflow uses Ubuntu 24.04, CPython 3.14.7, Node 24.21.0,
Java 21 and digest-pinned PostgreSQL 18.6. Evidence is QUALIFICATION_ONLY. Other
security findings, operational authority and production acceptance remain open.
Phase 11 is IN_PROGRESS; Phase 12 is NOT_STARTED; release closure remains BLOCKED.
