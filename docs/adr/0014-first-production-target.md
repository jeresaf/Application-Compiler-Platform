# ADR-0014 — First production target engineering direction

Status: ACCEPTED for stack family, topology and engineering direction. Implementation and Phase 6 acceptance are IN PROGRESS. This record does not close P-08 or generated-source P-09 before their required integration evidence exists.

The authorized first target is a Java 21 Spring modular monolith, Vue task UI and PostgreSQL. The versioned draft profile is `acp-spring-vue-postgres/0.1.0`, with generator `acp-spring-vue-generator/0.1.0`. These identities and dependencies belong to target contracts, never Canonical IR.

Exact selected stable releases are recorded in [profile.json](../../targets/spring-vue-postgres/profile.json): Spring Boot 4.1.1, PostgreSQL 18.6, PostgreSQL JDBC 42.7.13, Flyway 12.4.0, Vue 3.5.43, TypeScript 6.0.3, Vite 8.3.3, Vue plugin 6.0.9, vue-tsc 3.3.12, Vitest 5.0.3, Vue Test Utils 2.5.1, Playwright 1.63.0, axe Playwright 4.13.0, happy-dom 20.14.5, JUnit 6.0.3, Maven compiler plugin 3.15.0 and Surefire 3.5.6. Node 24.21.0 remains pinned. No prerelease dependency is intentionally selected.

Sources: [Spring requirements](https://docs.spring.io/spring-boot/system-requirements.html), [Boot dependency BOM](https://repo.maven.apache.org/maven2/org/springframework/boot/spring-boot-dependencies/4.1.1/spring-boot-dependencies-4.1.1.pom), [PostgreSQL version policy](https://www.postgresql.org/support/versioning/), and [npm release metadata](../../targets/spring-vue-postgres/evidence/npm-stable-releases.json). TypeScript 7.0.2 was incompatible with the selected vue-tsc: its native package does not export `typescript/lib/tsc`. Stable 6.0.3 passes type checking. See the [upstream discussion](https://github.com/vuejs/language-tools/discussions/6121).

Spring JDBC is the bounded persistence direction. It exposes tenant predicates, SQL, transactions and database constraints directly, and avoids implicit ORM schema changes and lazy-loading behavior. JPA would reduce repetitive mapping, but introduces additional generated mapping and lifecycle behavior to verify. JDBC instead requires explicit DTO/type conversion, optimistic concurrency and migration coverage; those requirements remain target acceptance gates. Flyway versioned SQL is selected independently of persistence access. It consumes approved semantic changes, not live-schema guesses.

The prototype worker uses Python 3.14 with no third-party Python packages. This selects only this plugin implementation language; it does not select ACP's production compiler-core runtime. The host uses disposable processes and a versioned protocol. Linux libseccomp and atomic directory exchange are engineering adapters, not semantic or target architecture requirements. Future plugin runtimes may implement the same protocol. ADR-0004's production-core and textual-frontend decisions remain independently DEFERRED.

Authentication uses the standard resource-server OIDC/JWT boundary. Canonical application policies remain separate server-side checks. Test identities exist only in test sources. No generated production identity provider or token bypass is provided.

Compiler files require prior-digest CAS. Framework upgrades require an explicit host policy. AI candidates require bound provenance and host approval. Explicit human extension handoff prevents subsequent compiler writes. General source intelligence and production evidence authority remain Phase 7 and Phase 8 work.

See [target contract and limitations](../phase6-target.md) and the [Phase 6 status report](../phase6-completion-report.md). No production-ready certification is claimed.
