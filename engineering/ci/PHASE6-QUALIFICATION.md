# Controlled qualification candidate — staged only

Proposed branch: `codex/phase6-controlled-integration-candidate`. No ref is created.
The active workflow and all release gates are unchanged. This standalone JSON job
specification is not a GitHub workflow and has no automatic triggers.

The source manifest binds frozen HEAD, all 895 original bytes, six exact Wave 3
files, integration additions and explicit selected tests. An operator must obtain
its SHA256 and the complete candidate source digest independently from the reviewed
evidence. Never replace a mismatch with a newly computed trusted value. The exact
Wave 3 patch must be supplied separately (SHA256 is pinned in code and manifest).
No earlier-wave fallback, venv creation, setup action or package install is used.

Offline command (argument placeholders are mandatory operator-bound identities):

```text
<pinned-or-existing-python> engineering/ci/phase6_qualification.py --offline --source <candidate> --patch <exact-wave3-patch> --manifest <candidate>/engineering/ci/phase6-qualification-manifest.json --manifest-sha256 <reviewed-manifest-hash> --candidate-sha256 <reviewed-source-digest> --scratch <private-scratch-outside-source> --output <private-results>/offline.json --python <same-interpreter>
```

Use `--plan-physical` instead of `--offline` to emit the exact bounded future
sequence without executing any binary or connecting to a database. The current
CLI exposes no physical execution option. Exit 0 from offline means only that all
32 explicitly selected tests passed with no skips. Python 3.14.4 is allowed for
local offline feedback but reports LOCAL_VERSION_NOT_PINNED; intended CI pin is
CPython 3.14.7. All qualification reports remain NOT_QUALIFIED while required
physical, application, history, source-trust and release evidence is pending.

## Single next execution authorization

Authorize one newly provisioned ephemeral Ubuntu 24.04 qualification host, its
identity, exact candidate/manifest/policy digests, preinstalled CPython 3.14.7 and
PostgreSQL 18.6 binary paths/SHA256, one exclusive task root and private socket,
port 55439 and a short new `/tmp/acp-phase6-wave2-q-<reviewed-id>` root
(the complete Unix socket pathname must be fewer than 108 UTF-8 bytes), role `acp_wave2_qualification_role`, database
`acp_wave2_qualification_db`, and only the four synthetic migration test methods.
Review/approve the host-only authorization callback binding that exact scope and
policy digest before invoking `phase6_postgresql.execute_future`. No callback,
credential, signature or approval is created here. A boolean in a client request
is not an authenticated project-authority grant. The callback is an execution
interlock, not a new operational trust service or proof format.

The launcher rejects existing roots, relative/default binaries and mismatches;
requires exact runtime/tool versions and an explicit pg_ctl -p binding to the
reviewed postgres executable; disables TCP and host authentication; uses
0700 paths with a new nondefault role/database; binds PID, process start token,
command, UID, data directory, socket, version and DB identity before schema SQL.
The explicit initial `postgres` database is only the brand-new owned cluster's
bootstrap database, never a default connection to an existing service. All client
connections include private socket/port/role/db; pass/service files are disabled.
It can stop only the exact newly owned PID/start token and retains pgdata/logs.
Identity uncertainty refuses stop and yields BLOCKED_UNSAFE_TEARDOWN for review.
This does not establish cross-host or privileged same-UID/root confinement.

Future physical tests (all NOT_RUN now):

1. `test_real_postgresql_storage_presence_required_and_rollback`
2. `test_missing_persisted_column_rejects_before_expand`
3. `test_wrong_text_storage_rejects_without_catalog_change`
4. `test_cross_version_retained_bytes_and_rollback_both_domains`

The physical capture subclass inherits those exact methods and preserves SQL,
row/catalog stdout and digests for controlled positive and negative observations.
These are test-client observations, not independent cryptographic attestations.
Expected rejection is a test pass only after its byte/catalog assertions succeed.
No missing/skip count can establish a four-case physical pass.

Generated Spring/Vue application integration is a separate status and requires a
separate bounded execution scope within that next authorization: preprovisioned
approved Java/Maven/Node/npm dependencies and caches, exact retained sealed 0.2,
0.3 or 0.4 predecessor artifacts, new isolated application directories and database,
explicit Java/JDBC identity fencing, bounded local ports/process cleanup and exact
build/test commands. See `phase6-qualification-ci.json` for existing entrypoints
and required outputs. Do not invoke its application scripts unadapted: they use
Git history and ambient JDBC variables; the source copy has neither. The current
candidate changes bundle inputs, so production 0.5.0 admission correctly rejects
it. A reviewed lab-only admission mechanism is still needed before candidate app
generation, not an alteration of the sealed release or a fabricated successor.
Target 0.1 remains outside the production upgrade window. A same-specification
0.4-to-0.5 run does not prove semantic evolution.

Both domains retain historically approved reference semantic snapshots/ChangeSets,
not authenticated deployed predecessors or accepted append-only histories. New
backfills remain synthetic test-only; independent bindings are not approved.
ACCEPTED_DEPLOYED_UPGRADE_NOT_PROVEN remains explicit. No app execution, Maven,
npm, Flyway, network, service, database, VM, signing, CI dispatch or release action
is performed by this assignment. Security gates/T09 and all 21 blockers remain.

## Section A executable-binding correction

The physical test client no longer has a hard-coded psql path. The launcher
conveys exact verified psql path/hash and the hash of an exclusive 0600
`acp-owned-postgresql/2` identity record through sanitized task-specific context.
The record binds executable path/hash/UID/mode for psql, postgres and the resolved
interpreter, the exact policy/candidate digests and postmaster start token. Before
every connection, and again between the server probe and schema SQL, the client
rejects missing/mismatched handoff, symlinks, unexpected owners/permissions,
changed bytes and interpreter/process substitution. Explicit socket/port/role/DB
and existing PID/data-directory/version checks remain mandatory. No PATH, default
libpq or workstation-client fallback exists.

This is source-level accidental/stale/substituted input protection, not immutable
execution attestation. A privileged same-UID/root observer can alter code, files,
environment or process observations; path/hash checking has a residual race
between observation and exec, and this assignment does not establish confinement.
No physical launch has occurred. Independently approved ephemeral host/operator,
CPython 3.14.7/PostgreSQL 18.6 paths and hashes, trusted scoped host callback and
new explicit execution authorization remain prerequisites. Source remains
UNSEALED_CANDIDATE and physical status BLOCKED_MISSING_AUTHORIZED_RUNNER.
