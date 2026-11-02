# Case Management reference lifecycle

Phase 10 is IN_PROGRESS. This increment runs the original approved Case Management
Canonical 0.3 through the existing eight-stage compiler and unsealed 0.6.0 candidate.
It does not close Phase 6, approve a semantic transition or authorize production.
Phases 11–12 remain NOT_STARTED. Operational security is NOT_ESTABLISHED.

The generated Vue task interface searches existing assigned cases and updates the
summary through `UC-TASK`: **CMD-REVIEW → CMD-APPROVE → CMD-ARCHIVE**. It uses
existing organizations/users/tenant and role rules, durable idempotency and audit.
The disposable development identity is the existing trusted-JWT test adapter, not
cryptographic issuer qualification. Generated production packages do not contain
this adapter. Browser test bundles contain it and are explicitly test-only.

This is a bounded first vertical slice. There is no generated create-record screen,
attachment/blob service, reporting UI or audit-history screen. Initial records use
existing authorized synthetic provisioning. Full audit rows are retained in the
version-bound database snapshots; they are not presented as a generated audit UI.
No handwritten business controller substitutes for missing generator capabilities.

## Run

Use the existing workspace and the Phase 9 isolated SDK environment (its hash-locked
requirements include the unchanged compiler dependencies), Java 21, Node 24.21.0,
Maven, Docker and the existing pinned PostgreSQL image. Provisioning dependencies
requires operator authorization. The runner creates private Maven/npm/browser
inputs, verifies Maven artifacts against the existing immutable lock before use,
uses Maven offline, and installs npm's existing integrity-locked packages without
package scripts. Existing caches may seed those private inputs; originals are not
modified. No system packages or operational services are configured.

Acquire the exact Phase 7/8 artifacts using the Phase 9 runbook. Then use a new
workspace path; existing directories are rejected:

```bash
python3.14 -B -m engineering.reference_application.lifecycle qualify \
  --workspace /tmp/acp-reference-lifecycle \
  --phase7-archive /tmp/acp-phase9-phase7.zip \
  --phase8-archive /tmp/acp-phase9-phase8.zip \
  --maven-seed /absolute/retained/private/m2 \
  --npm-seed /absolute/retained/private/npm \
  --browser-seed /absolute/retained/private/browsers
```

Seeds are optional; missing pinned Maven/npm/browser inputs can be obtained after
operator authorization. `--offline` forbids Maven/npm acquisition; Chromium must
already be available through the browser seed in a fully offline execution.
The runner rejects occupied ports 18081/4174 before fixture requests. All database
access is bound by the existing adapter to its newly created loopback-only,
tmpfs-backed `acp-06-runtime-*` PostgreSQL container. It cannot select an existing
application database. Historical VM-lab/vault resources are not used or removed.

Replace `qualify` with `serve` and use a fresh workspace for an interactive
reviewer session. After the same R0/R1 sequence, open **http://127.0.0.1:4174**.
The disposable identity is supplied by the test extension; no production credentials
are needed. Inspect the search results and persisted task summary. The original case is archived after the automated workflow; a terminal-state
transition is correctly rejected. An additional `reviewer-resource` open case is
explicitly provisioned by the existing synthetic fixture helper for hands-on use.
Select it, enter a task note, confirm the workflow, and inspect the persisted result.
This is not a generated create API. `r` restarts the backend; `q` stops this session.
The final interactive database state and a newly bound R2 request are retained
before cleanup. No reset is performed after business records exist.

## R0 and R1

R0 preserves the exact specification, compiler audits, generated source, package
and executed class/frontend hashes, human identity extension, native Source Model,
impact information, actual Phase 8 offline verification, real MCP transcript,
browser results/screenshots, migration history and a PostgreSQL dump/row inventory.
The HUMAN-owned extension contains an AI-authored nonsemantic comment under the
user-authorized ownership seam; ownership does not assert human authorship or
semantic approval. Its new baseline is a
separate source observation, not a modification of the original Phase 7 baseline.
Only that HUMAN-owned field observation can be updated; managed changes fail closed.

R1 first proves manual source drift invalidates the native model and ArtifactStore
inventory without publication. It restores the rejected test mutation, runs the
native compiler again and publishes through the existing atomic/CAS artifact store.
Managed bytes remain deterministic, and reviewer-owned source survives exactly.
This is **unchanged-specification regeneration**, not semantic evolution. Root inode replacement records the actual atomic publication.

The same database is retained while R1 is rebuilt and a fresh JVM starts. Flyway
validates the unchanged checksums/version history. Every prior committed business
row remains, the saved idempotency request replays without duplicate effects,
unauthorized/expired credentials are rejected, and a reset against populated data
is rejected. A second explicitly provisioned case then executes a fresh workflow
through the rebuilt UI/backend, while all original rows remain intact. Classification READ audits and PostgreSQL-observed lazy commit-time
materialization are assessed by the existing exact replay-state verifier.

Phase 7 analyzes actual generated Java/TypeScript sources before and after R1 and
reports impact, drift and the existing Vue/dynamic-analysis limitations. Phase 8
runs its existing offline predicates against each exact source/model binding.
Generated outputs remain equivalent. R1 CAS expected digests/publication intents
can differ from the original ArtifactPlan; both full plans are verified separately
and retained with their distinct identities. No other plan field is ignored in
the output-equivalence check. New compiler execution audits and the original
publication identity are retained. Runtime/browser records are bound
separately to actual source/build/database versions. They do not automatically
promote unregistered Phase 8 semantic obligations. Missing results remain
NOT_RUN/BLOCKED. Existing historical security FAILs are retained and retrieved
through a separate real MCP inspection; this run does not rescan or clear them.

## R2 authority boundary

The retained `EVOLVE-REFERENCE-NOTE` proposal has APPROVED_CONTENT, candidate
`sha256:e57eaee3f979f3b77feb255dde470772321b3354001547e71e02fbaadca2b59d`,
and ChangeSet file digest
`sha256:55a53d04dfc196505880699f51e68d039232a8a37de88d4f9102c9c61f8fbcc0`.
Its authenticated proof is still PENDING_HUMAN_SIGNING. Authentic accepted history,
an exact rebased plan, an independent binding for this newly measured population,
and exact writer/SQL/recovery/execution authorization are absent. Historical
three-row/two-tenant approvals or synthetic preview anchors cannot be transferred.
The existing pipeline also deliberately admits only the original approved snapshots.

`r2-approval-request.json` pins the existing candidate/ChangeSet/decision and the
new R1 population digest. It requests those exact missing authority inputs; it does
not issue a signature, fabricate a journal, choose a default or execute SQL. The
reference note is synthetic, not a newly approved production business requirement.
The original unusual Unicode/NUL binding is not a new-record default and is not
applied to this database. No later evolution is claimed as executed.

`lifecycle-results.json` and the hosted artifact retain the outcome. Browser/JVM
processes and only the owned disposable database are removed at exit. Source,
packages, dumps and results remain for custody review; retain required evidence
under the existing vault rules before removing temporary execution directories.

## R6 document preview

The separate [R6 runbook](phase10-r6-documents.md) describes the proposed versioned
transactional document capability, real upload/download qualification, ownership-safe
regeneration and candidate-only verification/MCP namespace. R0–R5 remain preserved;
no R4/R5 proposal gains semantic approval. Document security and production release
obligations remain open. Run R6 only in a newly owned disposable environment.
