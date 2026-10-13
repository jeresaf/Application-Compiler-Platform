# T08 — isolated PostgreSQL compiler regression authorization request

Status: **PROPOSED_NOT_GRANTED — DO NOT EXECUTE**. Exact reviewed source:
`f5793fbab115ceb3ea814a73c38434dd2335be50`. The machine-readable request binds
the test and dependency hashes, existing fixture semantics, command and exclusions.
This document neither authorizes the test nor provisions its database.

## Exact execution proposed after separate authorization

Repository-root command, shown for review only:

```sh
.venv/bin/python3.14 -m unittest tooling.tests.test_canonical03_migrations.PostgreSQL03MigrationTests.test_real_postgresql_storage_presence_required_and_rollback -v
```

Required environment variables are `ACP_TEST_DATABASE_URL`, `ACP_TEST_DATABASE_USER`
and `ACP_TEST_DATABASE_PASSWORD`. Their values must come from an independently verified,
explicitly authorized, empty disposable fixture database. No value or endpoint is selected
here. The test strips a `jdbc:` prefix for psql and passes its user/password through the
child environment. Secrets must be redacted from evidence. Use the existing pinned Python
environment and psql; a version-compatible disposable server must report `180006`
(PostgreSQL 18.6). No download, container creation, role creation or credential issuance
is authorized by preparing this request.

## Actual effects and fixture authority

This is not a read-only test. It executes real SQL through psql with ON_ERROR_STOP:

- Creates random `acp_migration_<uuid>` schemas, fixture tables and one synthetic row
  per required/optional × nullable/non-nullable case.
- Runs the compiler-generated transaction containing fixture DDL/backfill/verification
  and required-field constraints. For the required non-nullable field it checks exact
  bytea value `65cc8100f09fa68b27` and rejection of a new row omitting the required field.
  This value is synthetic test data, never a tenant default or a new-record default.
- Checks nullable/presence storage, the invalid presence/value combination and rejection
  of incompatible pre-existing text storage.
- Replaces the fixture backfill decode argument with invalid hex `zz` to force a database
  error, then verifies transactional DDL rollback by checking absence of the new column.
- Drops only its own random schemas with CASCADE in finally blocks. Process termination
  can interrupt finally; cleanup/recovery obligations therefore remain explicit.

`fixture()` uses the unchanged approved PAYMENT snapshot as compiler input, constructs
a **test-only** required-field proposal, and passes the local `FixtureAcceptedHistory`
stub. That class is an in-memory test oracle; it is not a genuine accepted-history
repository, independent data-binding approval, human authorization or migration receipt.
No persistent approved Canonical, ChangeSet or sealed artifact may be changed. No
synthetic approval may be relabelled as operational history. A passing test proves only
this bounded storage/constraint/rollback regression, not arbitrary production populations,
accepted semantic evolution, deployment or operational security.

## Prerequisites for an explicit T08 grant

1. A human identifies the actual empty disposable database/server and verifies ownership,
   server version, isolation from application stores and absence of production data.
   Bind database identity, environment attestation and exact reviewed source/request digests.
2. A separate reviewer confirms the intended fixture SQL, role privilege boundary,
   connection destination and exclusive use. A driver/endpoint operator cannot silently
   substitute an application database. If the empty disposable environment does not exist,
   its provisioning needs a separate explicit scope; this request does not grant it.
3. Confirm the test source and all bound dependencies match the reviewed bytes. Resolve
   Python/psql version evidence. Supply ephemeral credentials through the approved local
   mechanism, never checked-in files or production accounts.
4. Authorize only one named test invocation and its enumerated fixture SQL/cleanup, with
   evidence capture. Any retries, alternate source or changed fixture require review of
   the applicable grant; no blanket migration permission is implied.

## Required evidence and acceptance

Capture exact source/test/request hashes, server version and verified disposable database
identity, redacted command/environment-variable names, full unittest result, start/end time,
return code and schema inventory before/after. A PASS needs the named test to execute once
without skipping and finish OK with all assertions satisfied. Retain unexpected SQL errors
and classify failure, interruption or skip honestly. Capture orphan schema/transaction
evidence after a crash; discard the dedicated disposable environment or obtain explicit
cleanup authorization. Do not infer successful rollback/cleanup from a missing response.

This request authorizes nothing now. It excludes application migration, existing retained
inventories/data, real accepted-history repositories, data-binding approvals, real
authority/proofs/keys, PAYMENT or CASE genesis, deployment, semantic changes and release
closure. A17-16 remains INCOMPLETE until exact execution evidence and explicit disposition
exist. No other control is promoted. All 21 Phase 6 blockers remain.
