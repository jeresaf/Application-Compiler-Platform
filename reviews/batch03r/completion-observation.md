# Batch 03R completion checkpoint

Baseline `a5a7064d448df0153d11e7f19d27cfe5227660b1`. This record supplements the earlier review.

## Recovery and performance

[Hosted performance](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/45774835913/job/139757217626) passed on the baseline after same-run Maven input verification. [Hosted recovery](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/45774835913/job/139757217536) passed Maven verification and compilation, then failed Payment's four-query assertion before reaching Case Management. The retained recovery archive 15096131321 matched its published SHA-256 `7bdaa7d2b2ee8d88c07f7e6120f2fa32cce740b105a2922e406bff6d308086ba`. Its failure record lacks individual query responses. The authentication exceptions in the application log correspond to explicit negative checks preceding the four-query batch. They provide no attribution for the failed batch.

The harness now writes bounded per-request statuses, allowlisted failure fields, correlation IDs, monotonic durations and application process/log identities before evaluating the same four-request assertion. It captures aggregate bucket clocks and tokens, transaction rollback and deadlock counters, and database connection and lock-waiter counts. These are aggregate observations. They do not establish per-request SQLSTATE or pool-internal activity. Transport and timeout failures retain evidence without copying exception text or response bodies. The underlying failure remains unresolved.

The successor rate implementation takes ordered transaction-scoped locks before sampling admission time, then initializes and debits the bucket in the same isolated transaction. Recovery restarts the JVM against the same database. The original report cannot distinguish a rate denial, clock failure, session failure, connection starvation, or query failure.

## Cardinality design assessment

| Approach | Consequence |
| --- | --- |
| Global serialization | Can prevent overlapping writes with complete participation, at the cost of cross-tenant contention. |
| Tenant serialization | Preserves cross-tenant concurrency. Every multi-tenant transaction must take its full ordered tenant set before writes. Disjoint relationships of one tenant still contend. |
| Endpoint coordination | Limits contention, but must cover both roles, old/new keys and endpoints referenced by deletes or reassignment. |
| Relationship coordination | Gives a simpler lock inventory, but all endpoint writers must participate and multi-relationship transactions must coordinate before writes. |
| Database-native constraints | Preserve foreign keys and deferred uniqueness. Minimum-degree counts across rows still require cross-transaction coordination. |
| Serializable with bounded recovery | Can reject a conflicting transaction. Only a proven rollback permits retry, and external effects plus ambiguous commits need separate reconciliation. |
| Hybrid pre-write coordination with deferred validation | Preferred design candidate. Requires complete writer coverage and invariant coverage before selecting it for implementation. |

The lock inventory would include the canonical tenant, relationship identity, endpoint role and exact endpoint key for both old and new values, plus all relationships affected by an endpoint insert, update or deletion. Normalize self-relations without conflating unequal endpoint roles. Order and deduplicate the full set before the first conflicting write in a multi-relationship transaction. Encode as a domain-separated, length-delimited tuple. Advisory hash collisions may serialize unrelated transactions and must never merge identities or replace actual key checks. A lock acquisition cannot refresh a repeatable-read snapshot. Qualification must prove the supported isolation and visibility rules and enforce the writer contract for direct SQL. Preserve deferred minima, maxima, same-tenant foreign keys, uniqueness and restricted deletes.

No successor migration or concurrency correction is in this checkpoint. The baseline inversion still lacks an independently retained deterministic PostgreSQL reproduction and the proposed coordination lacks writer-coverage proof. Required evidence includes legitimate temporary invariant violations, competing commits, direct SQL, multiple JVMs, tenant independence, rollback and unknown commit outcomes, plus fresh and retained-data upgrade qualification with unchanged original Flyway checksums.

## Input custody

The 832-member lock and offline Maven selection remain intact. Same-run transfer and exact member verification constrain consumed bytes. On later attempts the producers and consumers select an attempt-specific artifact name within the same workflow run. A consumer-only rerun fails closed if the producer did not publish for that attempt. Exact member verification still runs before consumption. Maven Central remains an upstream availability dependency. Durable storage requires separate custody authorization.

**PARTIALLY_QUALIFIED.** SEC-01, SEC-02 and Phase 6 release closure remain BLOCKED. Phase 11 remains IN_PROGRESS. Phase 12 remains NOT_STARTED.
