# H11.2 evidence review

Baseline and package evidence producer `b480983979511efffce95d10d42da9724ec4f0b0`. H11.1 run 45585976508 succeeded in dependency determinism, application builds and security readiness. Its reference demonstration failed separately. The H11.2 verifier checks the pinned archive and each manifest entry before using the evidence.

The existing pinned JSON Schema validator independently checks the three BOMs against the official CycloneDX 1.6 schema and pinned companion schemas. It then compares the BOM component multisets with package and lock evidence, requires unique references, and checks package and revision bindings. The incomplete compositions reflect missing graph edges, frontend attribution and shaded-code relationships. The emitted JavaScript, CSS and HTML are hash-bound. No source maps were retained in these packages. Lockfile entries provide no proof of bundle membership.

The native report identifies recorded Java, javac, Maven, Python, Node and npm bytes. Its file inventory describes installed runtime files. Actual shared library loads, native bundler identities and publisher provenance beyond existing pins still need separately observed evidence. The scoped Maven distribution authorization remains the authority for that archive.

The 38 original advisories retain exact version and scope dispositions. Nested JAR observations and license/notice member hashes identify evidence for legal review. Shaded components, frontend exposure, precise build-time applicability and distribution obligations are unresolved. Security and dependency owners must approve exact remediation and compatibility changes. Legal owners must review component texts and obligations. Release authorities decide acceptance only after those reviews and independently verified technical evidence.

The H9 and reference demonstration HTTP 429 interruptions remain separate. Reusing the V3 Maven transfer across these paths would require lifecycle and source-bound cross-workflow custody design. The narrow proposed change is a reusable same-run Maven acquisition producer for each workflow and a hash-verifying offline consumer, retaining the separate npm and browser provisioning controls.

No additional publisher, executable dependency or trust root was enrolled. SEC-01, SEC-02 and Phase 6 release closure remain BLOCKED. Phase 11 remains IN_PROGRESS and Phase 12 remains NOT_STARTED.
