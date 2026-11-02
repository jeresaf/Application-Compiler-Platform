# R7 proposed native background jobs

R7 is an unapproved synthetic Case Management preview. It adds Authoring 0.8 / Canonical 0.7 `IntegrityJob`, `WorkerGrant`, `JobReadPermission` and `JobView`, using the existing INTERVAL Schedule and bounded RetryPolicy. Existing interactive Job/UseCase semantics remain unchanged. Structural eligibility is not human approval.

The generated worker verifies exact R6 document bytes against their recorded SHA-256. A PostgreSQL schedule and queue provide durable occurrences, transactional SKIP LOCKED claims, expiring leases, attempt records and fenced result transactions. Execution attempts are at least once; one queue identity can commit only one result and linked audit event. Mismatches are failures, never repairs. The recorded digest is not independent custody authentication.

The bounded reference schedules hourly in UTC, skips historical/missed occurrences, handles at most 20 documents per tenant, allows three attempts with 1/2 second retry delays, a two-second execution timeout and four-second lease. Initial activation schedules only the current occurrence. Unsupported schedules, policies, resource scope and privileges fail closed. No manual trigger exists.

Workers require explicit preview configuration: `acp.integrity.mode=preview`, `acp.integrity.enabled=true`, `acp.integrity.worker-identity=service:reference-integrity`, and `acp.integrity.worker-tenants=tenant-one,tenant-two`. These must match the generated grant. They are host-provided service context, not JWT impersonation or production identity enrollment. Database custody and host configuration remain trusted infrastructure requirements.

Authorized owners can inspect safe statuses through the generated Vue JobPanel. The endpoint enforces authenticated role, owner and tenant bindings; it never returns content, worker paths or payloads.

Run focused tests with the existing SDK Python environment:

```sh
PYTHONPATH=tooling:. python3.14 -B -m unittest discover -s verification/jobs -v
PYTHONPATH=tooling:. python3.14 -B -m engineering.jobs.run --workspace /tmp/acp-r7-new
```

The runtime command requires the existing pinned Maven/npm/browser inputs and disposable Docker PostgreSQL infrastructure. It owns only newly created databases and processes. `--maven-seed`, `--npm-seed`, `--browser-seed`, and `--offline` reuse retained inputs. Do not point it at existing databases.

Qualification covers actual generated workers in independent JVMs, real uploads, retry/exhaustion, timeout, malformed payload, missing/corrupt/cross-tenant documents, rollback, lease fencing, process kill/recovery and ownership-safe regeneration. Test-only fault controls remain outside generated production source. Phase 7/8/MCP observations remain candidate-only; missing semantic verification never becomes approved PASS.

Full Canonical and Target IR metadata and provenance remain retained. The runtime model omits non-executable basis/origins/steward metadata, with an explicit digest-bound runtime projection, to remain within the unchanged ArtifactPlan budget.

No production deployment, semantic acceptance, release approval or Phase 11 is authorized. Historical 0.5.0/0.6.0 identities and R0–R6 evidence remain protected.
