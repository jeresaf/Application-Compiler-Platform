# Phase 6 generated task-interface tranche — AUTOMATED GREEN

This tranche consumes the exact human-approved Canonical 0.3 snapshots and ADR-0016. Phase 6 is IN PROGRESS / NOT CLOSED; Phase 7 is NOT STARTED. The sealed target/generator identities are `acp-spring-vue-postgres/0.4.0` and `acp-spring-vue-generator/0.4.0`. Releases 0.1, 0.2 and 0.3 remain immutable.

Target IR stays 0.2.0: its `nodes`, `screens` and `api` already retain exact semantic IDs/revisions and operation contracts. The validated Task UI Model is a derived generation artifact, not a new Target IR shape or semantic authority. `task_ui.py` validates before Vue emission; stale references and unsupported declarations reject negotiation. The model's digest, browser profile, deployment requirements and unchanged V1/V2/V3 digests enter provenance. No V4 is needed.

The supported subset is one UseCase-backed Screen with declared Search → Table → one-step Wizard order, one Form, two required String/Identifier controls, one String CONTAINS filter, one required String projection column, one REQUIRED-confirmation Action, four ViewStates and one exact actor/permission boundary. Controls support TEXT for String/Identifier and MULTILINE for String. WizardStep requiresPrevious is false. Each family has a distinct constraint; other forms reject. The automated evidence below supports this exact subset; manual accessibility remains outstanding.

The typed Query POST sends the exact QUERY-TEXT String, including empty String and unnormalized Unicode, at offset zero with page size min(50, maximumResults). The backend is the matching/order authority. There are no cross-page snapshot claims. Selection explicitly binds the Query completion's resourceId to the UseCase's resource input and version to expectedVersion. Only declared output projection fields are data columns; selection metadata is separate target chrome.

Form validation distinguishes undefined and empty String; it does not trim or normalize values. Required control error messages and ViewState messages come from Canonical. The Action uses one cryptographically random opaque key per confirmed logical submission, suppresses duplicate clicks and retains the same request/key through explicit recovery after network uncertainty, IN_PROGRESS, rate denial or semantic Failure. Recovery is explicit user intent; no automatic mutation retry occurs. Success renders exact typed output and reloads Query state. Stale/conflicting results do not overwrite backend state.

The deployment-owned `frontend/src/extensions/identity.ts` must implement the OIDC adapter, identity hints and identity-change notification. The default fails closed. Target 0.4 intentionally requires identity hints and change notifications in addition to the 0.3 `accessToken()`/`permissions()` interface. A deployment owner must prepare those exports before upgrading; the generator does not edit human-owned adapters. The actual upgrade fixture prepares this interface while still on 0.3, builds that old frontend, then proves the identical customized file survives 0.4 regeneration and its frontend typecheck/tests/production build. This synthetic preparation does not certify a production OIDC integration. `permissions()` does not prove authorization. The backend independently authorizes signed identity, session, actor, tenant and permissions. Login/logout/tenant/session changes must notify the UI, which clears results, selection, form values, pending logical keys and outcome state. Unsubmitted form persistence across reload is unsupported.

The browser profile is version 1.0.0: pinned Playwright 1.63.0, Chromium only, axe 4.13.0; COMPACT 390×844 and EXPANDED 1280×900. Production DOM order is unchanged across breakpoints. Tests use actual generated production Vite output, real Spring HTTP and PostgreSQL 18.6. A separate ephemeral browser build replaces only the identity extension with a deterministic test adapter; no test credential or decoder is included in release production output. The loopback test authority exists only under backend test classpath. There is no mocked fetch acceptance layer. Response-loss testing forwards and commits the actual request, then interrupts its response before explicit same-key recovery.

Browser evidence must cover keyboard-only flow, control labels, validation focus, confirmation cancellation/restoration, success/error focus, permission denial, wrong tenant, stale version, semantic Failure rollback, revoked session, duplicate-click suppression, committed network-loss replay and actual database/event facts. Axe serious/critical violations fail; all findings are attached, without blanket rule exclusions. Manual accessibility review remains OUTSTANDING. Firefox/WebKit evidence remains OUTSTANDING.

OIDC production configuration, CSP/security headers, HTTPS/TLS, manual accessibility, supported-browser disposition and telemetry/exporter review are explicit OUTSTANDING deployment obligations. Existing privacy encryption/destruction/backup/WAL/replica obligations remain OUTSTANDING. Automated browser results are not general WCAG certification or infrastructure verification.

The full-admission gate must compile through the real compiler/worker, compare repeated generation, materialize deterministically, preserve human-owned identity customization, build/test actual backend/frontend and execute browser journeys. The host execution policy retains the compiler's 1 MiB document limit and uses an explicit bounded work allowance. Shared generated artifacts bind the full Target IR digest; whole-model artifacts retain complete coverage, and compact per-artifact bindings avoid redundant host plan provenance. Provenance sidecar 0.3.0 deduplicates exact origins through versioned origin sets; the reader expands them without losing IDs/revisions. Legacy Canonical 0.1/0.2 artifact origin bindings remain complete. Historical sidecar origin lists are retained.

Historical blocker contracts 1.1.0, 2.0.0, 3.0.0 and 4.0.0 remain unchanged. New admission evidence must come from actual negotiation and must not be represented as an empty expected-blocker allowance. Even zero blockers and passing full admission leave Phase 6 closure pending a separate audit.

A separate final closure audit will need complete accepted-history target evolution, ownership/regeneration integration, final browser coverage, packaging/configuration, dependency/license/supply-chain evidence, worker/materializer fault integration, deployment-obligation disposition, traceability and hosted CI review. This tranche does not perform or approve closure and does not begin Phase 7.

The [separate closure audit plan](phase6-closure-audit-plan.md) records required review areas and outstanding evidence without claiming closure.

## Reproduce the tranche

Use the Linux environment in [DEV_LINUX.md](../DEV_LINUX.md), the pinned Node/Java toolchains and PostgreSQL 18.6 with `track_commit_timestamp=on`. Set `ACP_TEST_DATABASE_URL`, `ACP_TEST_DATABASE_USER` and `ACP_TEST_DATABASE_PASSWORD` to a disposable test database. The generated tests clean their own schemas; these commands are not deployment commands.

```bash
.venv/bin/python3.14 tooling/check_target_release.py
.venv/bin/python3.14 -m unittest discover -s tooling/tests -v
.venv/bin/python3.14 tooling/tests/phase6_gates.py target --output /tmp/acp-ui-check --run-builds --full-admission
.venv/bin/python3.14 tooling/tests/task_ui_upgrade.py --output /tmp/acp-ui-upgrade --new-projects /tmp/acp-ui-check
```

Choose fresh output directories for full admission. Chromium must be installed through the pinned generated Playwright dependency; CI installs its Ubuntu system dependencies. The GitHub workflow also runs the focused late-identity-refresh regression and retains every historical invocation, delivery/job, privacy/lifecycle, upgrade and evolution gate. `/tmp` reports are ephemeral local evidence; retained repository summaries and uploaded CI artifacts identify their exact bundle.

The test-only gate entrypoints preserve the sealed runtime while adapting the historical delivery recovery fixture to later calendar days: assertions select the original occurrence identity and require exactly one non-skipped occurrence. Later daily occurrences may correctly be recorded as skipped. Both domains passed this focused real-PostgreSQL check. The historical invocation upgrade harness separately reads original 0.1 inline provenance without rewriting it; both actual upgrades passed locally. These adapters do not change generated production bytes or weaken runtime gates.

## Final Linux validation — 2026-10-09

Target/generator 0.4.0 are sealed to bundle `61c4647cfbe38cdbd97d03305685b3903f3ff24cfdb20d7c5b4502b478a0e06a`. Real worker negotiation accepts both exact approved applications with zero blockers. [Admission evidence contract 5.0.0](../targets/spring-vue-postgres/admission-contract-v5.json) records those actual responses; it is not an expected-blocker allowance. Historical contracts 1.1.0 through 4.0.0 remain unchanged.

| Check | Final local result |
| --- | --- |
| Complete Python regression suite | 233 PASS |
| Generated backend regressions | Payment 72 + Case 73 = 145 PASS, PostgreSQL 18.6 |
| Frontend | Both typechecks, five component tests per domain and production builds PASS |
| Focused component regressions | Identity race and same-key rate recovery: two per domain PASS |
| Full production-build browser journeys | 12 per domain, 24 PASS across both viewports |
| Supplemental real HTTP outcomes | Eight per domain, 16 PASS; exact 422/409/401 and revoked-session denial |
| axe | Zero reported violations; no rule suppressions; incomplete findings retained for manual review |
| Actual sealed 0.3 upgrade | Both old/new frontend builds, new component tests, human adapter byte preservation, all-table row comparison, zero migrations and V1/V2/V3 byte equality PASS |
| Independent canonical verification | All three corpora PASS; approved bytes/hashes unchanged |
| Dependencies, repository and release identity | PASS; released 0.1/0.2/0.3 bindings unchanged |

[Machine-readable Linux evidence](../targets/spring-vue-postgres/evidence/task-interface-linux.json) records exact UI IDs/revisions, UI model digests, browser version/profile, viewport results, axe findings, real HTTP/database facts, deterministic browser fixture hashes, ownership checks and upgrade evidence. [Capability inventory](../targets/spring-vue-postgres/evidence/task-interface-capability-audit.json) retains distinct constraints for every family. Chromium 153.0.8010.12 was exercised through pinned Playwright 1.63.0. Firefox/WebKit and manual accessibility remain OUTSTANDING.

The [Ubuntu workflow](https://github.com/jeresaf/Application-Compiler-Platform/actions/workflows/acp-contracts.yml) reproduces these gates for the exact pushed commit and uploads raw reports, browser attachments, logs and JUnit evidence. It also retains all historical component, upgrade and evolution gates. Repository summaries describe local validation; hosted run artifacts independently identify their commit and bundle.

Full admission is GREEN for these two approved applications. Phase 6 remains IN PROGRESS / NOT CLOSED, its separate final closure audit remains BLOCKED, and Phase 7 remains NOT STARTED. OIDC adapter preparation/configuration, manual accessibility and unverified deployment infrastructure obligations remain OUTSTANDING.
