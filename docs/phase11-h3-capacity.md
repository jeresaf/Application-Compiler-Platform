# H3 bounded application capacity

H3 measures the existing H1 generator; it does not promote or change that generator.
The fixed [workload](../engineering/capacity/profile.json) binds the offered mix,
client counts, payload, measurement populations and resource configuration.

```sh
PYTHONPATH=tooling:. python3.14 -B -m unittest discover -s verification/capacity -v
PYTHONPATH=tooling:. python3.14 -B -m engineering.capacity.run --workspace /tmp/acp-h3-new
```

Use a fresh isolated workspace and free loopback ports 18081/18082. Cache reuse is
available through `--maven-seed`, `--npm-seed` and `--offline`. Provisioning and
each new evidence-vault destination require their separate authorization.

The actual generated Spring Boot service uses a newly owned PostgreSQL 18.6
container and volume through the existing H2 adapter. The workload initializes
16 durable, distinct test sessions for two existing authorized principals in two
tenants. These are trusted-JWT component tests, not cryptographic issuer evidence.

Normal closed-loop workloads use 4, 8 and 16 clients. Each has one warmup cycle
and eight measured cycles of CREATE, query, report, history, upload, download and
metadata. There are no held database gates in these measurements. Request timing
includes the client response read and JSON decoding; server job timings are
separately observed in PostgreSQL. Correctness checks run after each level.

The CREATE and query rate policies remain unchanged. Expected 429 responses have
their own counts and latency distributions; they never count as successful
business effects. The policy-admitted CREATE experiment additionally offers four
clients over six explicitly paced rounds. Its pacing interval is outside request
latency and does not reset the bucket. This supplies 24 successful CREATE samples
without inventing a business rate policy.

Each normal client creates one document per level on its first measured cycle,
then replays the identical upload key and bytes. This explicitly measures both
first publication and idempotent replay while staying within the existing
20-document-per-tenant worker scope before the separate boundary experiment.

Raw samples retain operation, client, phase, status, disposition and monotonic
timestamps. Statistics identify their population. Empirical p95 requires at least
20 observations, and p99 requires at least 100; smaller populations retain null
tails. These are small engineering populations, not production SLOs or confidence
guarantees. Throughput is observed offered-mix HTTP requests/second, including
policy rejections; successful requests are separately identified.

Resource evidence combines independently sampled `/proc` RSS, CPU tick deltas,
threads and descriptors, PostgreSQL activity/locks/queue states, and read-only
Hikari/JVM heap inspection in the external test adapter. The JVM heap/direct-memory
limits are 512/128 MiB. The H3 profile explicitly configures a finite 34-connection
pool: two connections per 16 concurrently nested invocations plus two observer
headroom connections. The original default pool of ten demonstrably starved at
16 clients; its failed raw workload, Hikari state, PG waits and JVM thread dump
are retained separately. This is bounded test-profile tuning, not a production
capacity recommendation or a generator change. `ActiveProcessorCount=2` is a JVM sizing hint, not an OS CPU
quota or an RSS ceiling. Sampler connections are excluded from PG activity counts.

Separate fault experiments cover a two-connection pool with a 750 ms acquisition
timeout, document size/format/authentication boundaries, client timeouts, graceful
shutdown and SIGKILL during uploads. PostgreSQL distinguishes committed and
rolled-back outcomes; explicit recovery/replay must produce one document and one
upload audit per key. Client timeout alone never proves server cancellation.

Worker evidence measures 48 explicitly provisioned queue occurrences, real claim
and completion timestamps, retries, timeout exhaustion, restart and durable audit
links. The original H2 two-JVM fencing/death assertions run unchanged. Execution
is at least once; only the declared terminal effects are fenced and deduplicated.
The worker must reject more than 20 eligible documents per tenant without
expanding that limit. Actual read-only PostgreSQL plans are retained; no index or
historical migration is changed on an assumption.

The current runtime has no accepted finite pending-occurrence bound. Pool
exhaustion currently returns a generic 500 rather than an approved retry contract.
The [exact proposal](../engineering/capacity/resource-contract-proposal.json) is
unapproved and unimplemented. Neither observed bounded workloads nor that proposal
establish production admission, a new semantic limit or G-22 PASS.

Phase 7/8 bind source, specification, generator, ArtifactPlan, Source Model,
workload, database, raw observations and independently checked data invariants.
Missing or altered evidence, incomplete populations, skipped required scenarios,
incorrect dispositions and missing cleanup fail qualification. Unsupported
semantic obligations remain NOT_RUN/BLOCKED. The dedicated hosted workflow keeps
Ubuntu 24.04, CPython 3.14.7, Node 24.21.0, Java 21 and the existing PG digest.

Phase 11 remains IN_PROGRESS. Phase 12 is NOT_STARTED. Operational security is
NOT_ESTABLISHED and release closure remains BLOCKED.

An intermittent normal CREATE HTTP 500 was observed in an earlier local full
run and remains an unresolved FAIL. Ten separately retained instrumented
diagnostic specimens did not reproduce it; a later complete run passed. Neither
that pass nor a hosted pass establishes that the intermittent defect is fixed.
The runner now retains PostgreSQL diagnostics before cleanup on failure.
