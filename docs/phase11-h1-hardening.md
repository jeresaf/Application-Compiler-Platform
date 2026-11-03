# H1 plugin dependency hardening

This unsealed engineering successor preserves the R7 Canonical candidate, compiler
registration, runtime implementation and migrations. It changes the generated
Maven plugin dependency configuration under a new source-fingerprinted generator
identity. It neither modifies nor promotes historical 0.5.0/0.6.0 releases.

The retained 2026-10-30 assessment contains Commons IO 2.11.0 in the conservative
Maven build inventory, originating through `maven-shared-utils:3.4.2`.
GHSA-78wr-2p64-hpwj / CVE-2024-47554 affects `XmlStreamReader` before 2.14.0.
The retained GHSA severity is HIGH; Apache labels it Low. Both classifications
remain recorded, without inventing a risk acceptance or claiming exploitability
of every ACP plugin operation. Sources: [Apache security advisory](https://commons.apache.org/proper/commons-io/security.html)
and [GHSA record](https://github.com/advisories/GHSA-78wr-2p64-hpwj).

Project dependency management does not override Maven plugin realms. H1 supplies
explicit Commons IO 2.22.0 plugin dependencies for the nine pinned lifecycle and
dependency plugins and Spring Boot's packaging plugin. The replacement is already in the existing exact input lock;
`engineering/hardening/plugin-inputs.lock.json` binds its bytes and the unchanged
parent lock. No new publisher, repository or installation script is introduced.
Historical cached artifacts and their findings are retained, not suppressed.

Run focused tests with the existing environment:

```sh
PYTHONPATH=tooling:. python3.14 -B -m unittest discover -s verification/hardening -v
PYTHONPATH=tooling:. python3.14 -B -m engineering.hardening.run --workspace /tmp/acp-h1-new
```

The executor privately binds the existing R7 qualification function to the H1
candidate. It preserves all original assertions, real browser/worker/database
operations, regeneration, restart, source analysis and Phase 8 result handling.
Optional `--maven-seed`, `--npm-seed`, `--browser-seed` and `--offline` reuse retained
inputs. Provisioning requires the applicable authorization. Only newly owned
disposable databases and processes are used. Authentication remains the explicit
trusted-JWT component adapter, not a production token-validation claim.

Actual Maven debug realm population must show the pinned replacement for the
compiler and resources plugins and no older Commons IO in any observed plugin
realm. The replacement JAR hash is independently checked. A fresh authenticated
OSV query retains both old/new responses and full advisory details; unavailable
or invalid assessment evidence cannot yield a successful qualification.

The narrow PASS concerns only this selected dependency in the observed H1 realms.
Other retained vulnerabilities, unexecuted plugin goals and external deployment
requirements remain unresolved. Patched Jackson versions already present in the
current generated POM do not clear historical build-inventory findings by inference.
Missing semantic obligations remain NOT_RUN/BLOCKED. Candidate evidence is
QUALIFICATION_ONLY; Phase 6 release closure stays blocked, operational security is
NOT ESTABLISHED and production deployment is NOT AUTHORIZED. Phase 11 is IN_PROGRESS;
Phase 12 is NOT_STARTED. No security gate or release predicate is waived.
