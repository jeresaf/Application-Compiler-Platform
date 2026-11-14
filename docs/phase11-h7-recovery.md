# H7 logical backup and recovery

H7 reuses the unchanged H6 generated application and native compiler, ownership,
provenance, Source Intelligence and Phase 8 verification. Backup is a deployment
obligation, not a new Canonical business semantic. Historical migrations, H1–H6
source-bound generators, sealed 0.5.0, historical 0.6.0 and all 39 release
predicates remain unchanged. Engineering results are `QUALIFICATION_ONLY`.

Run with the existing pinned SDK and approved caches:

```sh
PYTHONPATH=tooling:. python3.14 -B -m unittest discover -s verification/disaster_recovery -v
PYTHONPATH=tooling:. python3.14 -B -m engineering.disaster_recovery.run \
  --workspace /tmp/acp-h7-new --maven-seed /approved/m2 --npm-seed /approved/npm --offline
```

Provisioning and durable custody need their applicable authorization. The runner
creates only newly owned PostgreSQL 18.6 containers/volumes, validates ownership
and exact server version, and accepts no database URL or existing restore target.
Restore has no clean/drop-existing option. A reused, nonempty, wrong-identity or
unregistered target is rejected before restoration. A restore capability expires
with its owned database context; it is laboratory process state, not production
construction or deployment authority.

The logical profile uses `pg_dump --format=custom --snapshot=...` and
`pg_restore --single-transaction --exit-on-error --no-owner --no-privileges`.
A repeatable-read read-only transaction exports the snapshot and independently
reads every application table, including audit, idempotency, sessions and rate
state. An auxiliary **test-only** schema holds pg_dump at a real relation lock
while authenticated application writes commit. The dump remains in progress,
then completes from the original snapshot after the barrier is released. Two
post-boundary committed cases must be excluded from recovery. The auxiliary
schema also provides a bounded restore-interruption gate; it adds no business
contract or historical migration.

The capture pins source cluster identity, exact snapshot, migration history,
object-list digest, dump digest/size and timing. The laboratory profile rejects
backups above 32 MiB. Hashes bind an independently captured in-process record;
they provide neither encryption nor protection from a privileged compromised
recorder. No authenticity, retention, key-custody or production service is
silently enrolled. PITR is `NOT_RUN`: there is no physical backup or WAL replay
claim and no recovery of commits after the logical snapshot.

An independent cluster must reproduce the complete captured table population
and migration history before application launch. Successful pg_restore exit alone
is insufficient. A guarded laboratory launch rejects missing or changed verified
restore state. Corruption, substitution, missing components, nonempty targets,
partial state, native Flyway wrong-version rejection, bad database credentials and an
actually interrupted pg_restore transaction are negative cases. Interrupted
restoration must roll back its uncommitted schema. Repeated restoration uses a
fresh cluster; retrying over an already populated target is rejected.

Fresh H5 issuer keys, newly authenticated sessions and H6 host configuration are
used after restoration. Captured session rows are not authentication evidence.
Documents must download byte-for-byte; workflow history, tenant ownership,
report totals, audit links and idempotency replay must remain correct. Existing
native PostgreSQL commit-oracle cache enrichment is performed before the backup;
logical restore does not preserve the original cluster's transaction-clock
history. Restored workers must preserve a still-valid fault-extended lease and
reclaim only after explicit expiry, with a new fencing token and one terminal
result/audit. Native retry/lease policies are not reconfigured.

Timings distinguish backup, restore, JVM readiness and first authenticated
operation. Snapshot age and the measured excluded population describe this
engineering recovery point. Failure-to-operation timing includes the deliberately
performed fault tests; the primary restore-to-operation interval is reported
separately. Neither is an approved production RPO, RTO or SLO.

Raw dumps and corruption copies stay in a new mode-0700 private temporary
subdirectory and are removed on success or failure. This is logical deletion,
not secure media erasure. Backup data is not encrypted. Public evidence is an
explicit allowlist of source identities, classified metadata, digests, outcomes
and cleanup, scanned against actual credentials, tokens and private keys. No raw
backup, SQL population or application diagnostic log is uploaded. Preserve
approved evidence before removing other execution directories.

G-19 and production recovery remain unapproved. Production encryption/custody,
retention, recovery objectives, external service configuration and independent
operational acceptance are separate requirements. Both historical H3 CREATE 500
and inherited unmatched-resource HTTP 500 findings remain documented and
unresolved. Phase 11 remains IN_PROGRESS; Phase 12 is NOT_STARTED; release closure
is BLOCKED.
