# R8 synthetic multi-release evolution

R8 evolves the proposed R6 document candidate to the proposed R7 jobs candidate on one newly allocated PostgreSQL database. It does not accept either specification into history, authorize retained R1 migration, or grant production deployment authority.

The preview adapter uses native `changes.semantic_diff`, dependency graph/closure, existing versioned compiler registrations, ArtifactPlan/CAS and generated Flyway migrations. Native accepted-history `changes.prepare` does not admit Canonical 0.6/0.7; that operation stays blocked. The distinct engineering preview record is not an accepted ChangeSet or journal. Exact semantic and migration approval remain required independently.

The supported policy is controlled **stop → fence previous writer → migrate → restart**. No simultaneous old/new operation or zero-downtime compatibility is claimed. A real dedicated R6 database writer is used before transition, then disabled in the disposable cluster. Reconnection with the actual old binary is rejected. The new application retains previous HTTP authorization and functionality. This is laboratory database-role fencing, not production credential custody or infrastructure approval.

All four historical migration files must remain byte-identical. Only the generated V5 jobs migration is eligible. Preflight binds both candidate/generator/compiler/ArtifactPlan identities, exact SQL, database/cluster/schema identity, full successful Flyway history and frozen population. A stale or altered observation fails closed. Transactional DDL failure and interruption must leave all original rows/history intact. Successful migration appends V5 through actual Spring/Flyway startup. Recovery restores the verified R6 capture into a second new cluster and rebinds the preview to that observed database before starting R7.

Through real browsers, R6 creates cases, runs Review → Approve → Archive, reports and uploads documents. R7 must preserve those exact records, audit and business-idempotency state, discover existing documents with real workers, fence expired claims, detect corrupted bytes without repair, and retain results through restart. Native commit-timestamp cache enrichment is permitted only with the existing independent PostgreSQL oracle; it is not counted as a business mutation. Restored rows are verified exactly; original cluster commit-clock continuity is not claimed.

Native source analysis, semantic/artifact impact, managed drift rejection and HUMAN-owned extension preservation remain mandatory. Cross-baseline native Source Model comparison stays blocked; models are not rebound to fabricate equivalence. Both independently bound models provide actual semantic impact and read-only MCP inspection. Artifact integrity and candidate runtime observations do not convert missing semantic obligations into PASS. Existing security findings remain unchanged.

Run with the existing pinned SDK environment and disposable PostgreSQL/browser infrastructure:

```sh
python3.14 -B -m unittest discover -s verification/application_evolution -v
python3.14 -B -m engineering.application_evolution.run --workspace /tmp/acp-r8-new
```

Optional `--maven-seed`, `--npm-seed`, `--browser-seed` and `--offline` reuse retained inputs. Missing dependency provisioning requires the applicable existing authorization. No existing database URL is accepted. Required execution evidence must be preserved in the separately approved R8 vault destination before removing execution directories.

Sealed 0.5.0, historical generator 0.6.0, approved Canonical snapshots, R2–R7 review decisions and all release predicates are unchanged. Phase 10 remains IN_PROGRESS; Phase 11/12 are NOT_STARTED. PHASE6_CLOSURE_BLOCKED; PHASE6_RELEASE_CLOSURE_BLOCKED.
