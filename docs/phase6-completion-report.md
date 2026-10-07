# Phase 6 implementation status — NOT CLOSED

Phase 6 is IN PROGRESS. This file is not an acceptance or completion claim. Phases 1–5 retain their approved historical status. Phase 7 is NOT STARTED. No generated application is claimed production-ready.

Work is on `codex/phase6-first-production-target`. The [target contract](phase6-target.md) records exact implementation boundaries and [ADR-0014](adr/0014-first-production-target.md) records the engineering direction.

Local Linux evidence collected on 2026-10-07: Ubuntu 26.04.1 LTS, CPython 3.14.4, Node 24.21.0, Temurin Java 21+35, Maven 3.10.0 and libseccomp 2.6.0-2ubuntu5. Official Ubuntu 24.04 / CPython 3.14.7 CI is still outstanding. The [reproducible template report](../targets/spring-vue-postgres/evidence/template-checks-linux.json) records both domains and their explicit admission failures.

| Check | Result and limits |
| --- | --- |
| Existing regression suite | 94 tests PASS, 349.550 seconds, before the final prototype refinements |
| Canonical byte/hash verification | PASS: 9 positive, 13 negative, 2 snapshot hashes; canonical corpus unchanged |
| Repository/document checks | PASS before final documentation updates |
| Worker/store/provenance foundations | 15 tests PASS, including atomic staging failure and negotiated project-capability enforcement |
| Final Compiler Core regression rerun | 29 tests PASS after the project-artifact extension; synthetic vectors unchanged |
| Target upgrade planner | 4 tests PASS, including required backfill, stale/unauthorized history, rename continuity and destructive blocking |
| Payment backend template fixture | Java 21 / Spring Boot 4.1.1 compile and 5 JUnit tests PASS, including real Flyway/PostgreSQL 18.6 |
| Case-management backend template fixture | Independently compiled; same 5 tests PASS against real PostgreSQL 18.6 |
| Payment frontend template fixture | Type checking PASS; 4 component tests PASS; Vite production build PASS |
| Case-management frontend template fixture | Clean npm lockfile install, type checking, 4 component tests and Vite production build PASS |
| Complete production-target compilation | BLOCKED by explicit unsupported capability errors for both domains |
| Six-step accepted-history target evolution | NOT COMPLETE |
| Browser journeys / API integration | NOT RUN |
| Ubuntu Phase 6 CI | NOT RUN; full target job not yet implemented |

The application-template checks bypassed capability admission deliberately to test source templates in isolation. Their `/tmp` files/logs and PostgreSQL container are ephemeral local evidence. They do not show that either complete canonical reference domain has passed the target pipeline.

Remaining exit gates include complete fail-closed capability enforcement; canonical authentication assurance/session/idempotency/rate semantics; relation/cardinality persistence; jobs/schedules/retry with declared timezone data; privacy lifecycle enforcement; event delivery; approved migration integration and the complete evolution sequence; all generated security/tenant/workflow/API/database tests; selected real browser journeys; full design-role and extension coverage; versioned configuration/observability contracts; deterministic container packaging; complete dependency inventory/license provenance and locking; adversarial worker/materializer supervision; full Ubuntu CI and final regression evidence.

P-08 and generated-source P-09 have prototype contracts and tests, but their required Phase 6 acceptance remains outstanding. ADR-0004's production-core runtime and textual frontend remain independently DEFERRED. No Phase 7, 8, 9 or 10 implementation has begun.
