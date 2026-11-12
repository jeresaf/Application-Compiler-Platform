# Phase 11 H6 operational observability

H6 is an unsealed, source-bound successor of H5. Its evidence is
`QUALIFICATION_ONLY`; production operations are not approved. Phase 12 is not
started. The original H3 intermittent CREATE HTTP 500 remains unresolved.

`engineering.operations.target.OperationalTarget` reuses the existing compiler,
ArtifactPlan publisher, Source Intelligence and Phase 8 verification. H5 source,
Canonical semantics, prior seals and the 39 release predicates remain unchanged.

The closed `acp-operational-lab/1` profile is supplied through
`ACP_OPERATIONAL_CONFIG` and its exact `ACP_OPERATIONAL_CONFIG_SHA256`.
`engineering.operations.configuration.profile()` defines supported settings.
Credentials are environment references, not profile values. Only development
mode and loopback disposable PostgreSQL are supported. Conflicting settings,
unsafe logging, unknown fields, missing references and altered profile bytes
fail startup. Canonical session, worker lease and retry policies are retained.
Heap configuration is checked against the actual JVM; the processor setting is
a JVM parallelism bound, not a claim of operating-system CPU isolation.

Health groups distinguish process liveness, workload readiness, database,
identity-key integrity and worker progress. An explicitly disabled worker is
optional. Health responses expose only status and perform read-only dependency
probes. Readiness requires available dependencies, valid pinned keys and, when
enabled, a running worker whose queue remains within the configured observation
bound. This bound reports health; it does not change job retry semantics.

Operational events use the existing classified Observability port, server-made
correlation identifiers, fixed event/outcome vocabularies and semantic origins.
Domain values and audit content are not exported. Logs are rate bounded.
`/internal/operations/metrics` requires H5 cryptographic authentication, native
principal/session authorization, loopback access and a separate host-held read
capability supplied by `ACP_METRICS_READ_KEY`. Its names and route/status labels
are fixed. Metrics reads retain ordinary authentication/session bookkeeping;
unauthenticated health probes must not write business state. No monitoring
provider or production secret-management authority is enrolled.

Run the bounded executor, after isolated dependency provisioning is authorized:

```sh
PYTHONPATH=tooling:. python3.14 -B -m engineering.operations.run \
  --workspace /tmp/acp-h6-unique \
  --maven-seed /approved/cache/m2 --npm-seed /approved/cache/npm --offline
```

Use a new workspace name. The executor generates and builds actual application
source, runs configuration tests, reuses H5 signed-token security tests and
creates an ownership-checked disposable PostgreSQL container. It tests database
pause, pool pressure, key loss/substitution, worker stop/stall/recovery, invalid
startup, restart and shutdown. It retains actual outcomes and cleanup evidence.
Only successfully secret-scanned output is exported to the sibling `-public`
directory. Do not publish failed/raw working directories or private keys/tokens.
The dedicated H6 workflow uses Ubuntu 24.04 and the existing pinned toolchains.

Runtime experiments and exact-commit hosted qualification must complete before
claiming engineering observability verified. Durable evidence requires its own
approved custody destination. Production provider/principal enrollment, service
authentication, transport/TLS, monitoring access policy, key custody, deployment
acceptance and G-16–G-19 remain independent decisions. H6 success does not close
Phase 6 release blockers or establish production readiness.

## Hosted failure remediation

The first H6 runs observed no real pressure waiters. The external fixture started
34 connection acquisitions concurrently against a cold pool with a 750 ms
acquisition timeout; discarded futures hid acquisition failures. A focused real
PostgreSQL reproduction exposed `SQLTransientConnectionException` and partial
occupancy. The correction acknowledges each successful acquisition before
starting the next borrower, while retaining all borrowed connections on the
same PostgreSQL lock. Independent `pg_locks` checks still require 34 overlapping
waiters. Failed acquisitions propagate; completion errors are checked after
release. This changes fixture setup, not application pool or timeout policy.

The original H3 failure artifact records a unique-key violation at
2026-11-09 07:00:20 UTC for occurrence 1794204000 and the reserved H2 document.
The reused H2 fixture computed positions relative to the current hour, allowing
an hour rollover to reuse an existing document occurrence. The external H2
adapter now accepts an exact test-only occurrence; the helper selects positions
strictly before the retained minimum and current database time. Existing
relative-offset callers remain supported. No migration or uniqueness constraint
changes. Native overlap, owner fencing, lease recovery and single-result
assertions remain active.

Failure exports contain closed operational events, exception classes/SQLSTATE,
HTTP status and response digests, source/log digests, control observations and
cleanup status. Raw logs, response bodies, SQL parameters, credentials and keys
stay private. Failed exports are never successful qualification records.
Neither correction establishes a cause for the historical H3 CREATE HTTP 500.

The inherited generic `Errors` handler maps unmatched MVC resource exceptions to
HTTP 500. H6 preserves that behavior and records it explicitly while testing
fixed metric cardinality across distinct unknown paths. H6 does not claim this
pre-existing HTTP limitation is corrected.

A local H6 rerun independently encountered SQLSTATE 23505 when its own relative
worker offsets crossed an hour. H6 now reuses the same absolute-position helper
as H2. PostgreSQL failure logs remain private; the failure exporter retains only
closed error classifications and timestamps, with hashes of the raw evidence.
