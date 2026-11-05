# H4 CREATE reliability and resource exhaustion

H4 preserves H1–H3 and the original unresolved H3 CREATE HTTP 500. A successful
later execution never establishes that the intermittent failure was fixed.

The H4 external test adapter adds an ordered exception observer. It logs exception
class identities and SQLState only, then returns null so the native handlers
retain control of HTTP responses. It does not log exception messages or resource
values, change JWT/session authorization, grant authority or modify production
classes. A real invalid-input request must still return the native 400 response.

The full runner reuses the existing H3 generation, builds, source analysis,
4/8/16-client workloads, security negatives, workers and recovery checks. H4 adds
two fresh disposable PostgreSQL experiments against the exact resulting classes:

- Two connections: hold the first authorized CREATE in the existing SQL action
  gate. The competing CREATE exhausts its 750 ms connection acquisition budget.
  Observe the native 500 and underlying connection exception, release the first
  transaction, then explicitly replay the failed operation once.
- Four connections: demonstrate both CREATE operations reaching the held SQL
  action concurrently, then release them. Both operations must commit.

Each experiment verifies independent database counts, exact tenant ownership,
classification/audit counts, idempotency and cleanup. These synchronized resource
experiments are not ordinary application latency measurements. The retained H3
failure's approximately one-second response and thirty-second configured pool
acquisition timeout do not establish the same cause. Original attribution stays
UNRESOLVED unless actual causal evidence is captured.

```sh
PYTHONPATH=tooling:. python3.14 -B -m unittest discover -s verification/create_reliability -v
PYTHONPATH=tooling:. python3.14 -B -m engineering.create_reliability.run --workspace /tmp/acp-h4-new
```

Retained-class diagnostics require the separately pinned SHA-256 of their original
result, its bound consumed-build inventory and exact main/test class bytes. They
create a disposable copy and compile only the observational test adapter. They
never mutate the retained source. Full qualification generates and builds anew.

Finite pool size alone does not establish safe admission for arbitrary request
concurrency: native invocation/session transactions can require additional
connections. Deployment concurrency/headroom, acquisition deadlines and bounded
infrastructure queues require an explicit tested deployment profile. H4 does not
activate a new semantic rate policy, 503 retry contract or pending-job cap. The
existing two worker loops/JVM and 20 eligible documents/tenant remain unchanged;
H3's pending-capacity proposal remains unapproved and unimplemented.

All evidence is QUALIFICATION_ONLY. Sealed 0.5.0, historical 0.6.0, approved
Canonical contracts, H1 security changes, H2/H3 code and all 39 release predicates
remain unchanged. Phase 11 is IN_PROGRESS; H5 and Phase 12 are NOT_STARTED.
Operational security is NOT_ESTABLISHED; G-22 and release closure remain BLOCKED.
