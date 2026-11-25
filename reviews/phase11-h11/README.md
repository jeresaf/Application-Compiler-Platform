# H11 supply-chain observation

Baseline `53626cc5d017e7b4b5506cca667451e4b12ac6e1`. SEC-02 remains BLOCKED. This increment adds source-bound lock inventory, Maven dependency and plugin records, embedded identity tracking, partial CycloneDX inventory views and current OSV observations. Temporary materialization produces npm locks for both reference applications. The evidence manifest assigns SHA-256 to every report. The CI conclusion describes execution of these checks. The assessment describes coverage and its remaining gaps.

The integrity boundary is the committed Maven, Python and generated npm locks. Exact bytes defend against substitution, cache poisoning and resolution drift. Publisher compromise and bad initial pins remain possible. OSV HTTPS observations do not authenticate package publishers. A missing or malformed response blocks scanner coverage. A reported match requires affected-version, applicability and severity review. Exact plugin realm records describe what the lock covers. They do not establish safe execution of build plugins or npm scripts.

| Remaining evidence | Responsible owner |
| --- | --- |
| Compare both built packages and their actual runtime components against independently checked SBOMs. Resolve embedded and shaded identities where metadata is absent. | Dependency and compiler maintainers |
| Enumerate native analyzer binaries, runtime libraries and toolchain dependencies actually consumed. Supply source and artifact provenance for each. | Compiler architecture and supply-chain owners |
| Obtain component-specific license texts, notices and distribution obligations for every applicable identity. Resolve reciprocal obligations and ambiguity. | Legal reviewers and dependency maintainers |
| Review current advisories with exact version and packaged applicability evidence. Decide risk policy, including scanner gaps and trust-key compromise. | Security owners |
| Decide admission and release scope against applicable predicates once evidence and owner reviews are complete. | Release authority |

Historical H1 findings and prior qualification remain separately retained. SEC-01 remains BLOCKED and hostile plugin execution remains disabled. Phase 11 remains IN_PROGRESS. Phase 12 remains NOT_STARTED.
