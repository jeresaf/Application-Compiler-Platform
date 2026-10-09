# Phase 6 production remediation — first corrective tranche

Status: IN_PROGRESS. Phase 6 remains IN_PROGRESS. Phase 7 is NOT_STARTED.
Reviewed baseline: `7e4e3438179e7a446c5f3737ad1d6d9cb07a96ea`.
Corrective branch: `codex/phase6-production-remediation`.

The first blocked closure audit, its findings and its original machine record
remain historical evidence at `phase6-final-closure-audit.md` and
`targets/spring-vue-postgres/evidence/phase6-final-closure.json`. They are not
rewritten by this tranche. Hosted run
[37910102322](https://github.com/jeresaf/Application-Compiler-Platform/actions/runs/37910102322)
performed that audit: contracts, phase5-experiments, phase5c-hard-gates and
phase6-target passed; phase6-closure-audit deliberately exited 2 with
PHASE6_CLOSURE_BLOCKED. The overall hosted run was blocked, not successful and
not an unexplained compiler failure.

## Release and compatibility

Target `acp-spring-vue-postgres/0.5.0` and generator
`acp-spring-vue-generator/0.5.0` are an intentional output-affecting successor.
All prior registry entries are preserved. Target IR stays at 0.2.0: runtime
configuration enforcement and storage correction change generated implementation,
not the meaning or structure of that compiler contract. Admission contract 5.0.0
and approved Canonical/ChangeSet/Authoring bytes are unchanged.

Policy C remains in force. The production target evolution window explicitly
allows 0.2.0, 0.3.0 and 0.4.0 to 0.5.0, subject separately to exact accepted
semantic/migration authority and storage compatibility. Target 0.1 is excluded;
its retained reader adapter is forensic/test-only. This window does not authorize
an arbitrary semantic change or an unapproved data binding.

## Storage and authority

The planner chooses semantic compatibility, scalar storage, relationship forms
and approved backfill encoding separately. Canonical 0.3 String additions use
bytea with exact UTF-8 backfills. Optional Nullable fields retain an independent
presence column; optionality and nullability are not collapsed. Existing String
columns with incompatible PostgreSQL storage cause an explicit migration failure.
No backfill is inferred. The PostgreSQL test suite uses synthetic test authority
and labels that scope explicitly.

The deployed 0.4→0.5 release journey keeps both existing approved snapshots
unchanged, commits old application state, upgrades without cleaning and checks
new behavior and origin retention. It does not manufacture a semantic ChangeSet.
The new String addition/backfill cases lack human business approval and cannot
satisfy the full accepted semantic-evolution closure criterion. Existing approved
reference authority remains bounded to its exact recorded digests.

## Dependency correction

Spring Boot 4.1.1 imports both Jackson BOMs. The successor overrides its
`jackson-2-bom.version` to 2.21.7 and `jackson-bom.version` to 3.1.7 rather than
mixing individual module versions. The direct Jackson 2 databind declaration
inherits that BOM. Patched versions are established by upstream advisories,
including [jackson-core](https://github.com/FasterXML/jackson-core/security/advisories/GHSA-7hhh-6rmp-j9qf)
and [jackson-databind](https://github.com/FasterXML/jackson-databind/security/advisories/GHSA-cxp5-3px4-pw24),
and Boot's [dependency-management contract](https://docs.spring.io/spring-boot/how-to/build.html).
Resolved Maven graph, packaged JAR inventory, SBOM, fresh scans and individual
advisory dispositions must be retained before claiming remediation. Build-plugin
and compiler security coverage and legal review remain separate obligations.

## Production runtime contract

`acp-runtime-configuration/1.0.0` selects a PostgreSQL, HTTPS OIDC,
trusted TLS proxy and single-instance PostgreSQL-claims scheduler profile.
The packaged resource lists required properties. Job credential handles and
principal adapters remain deployment owned. Active delivery requires a transport
adapter at startup. Configuration validation precedes activation and polling;
production cannot disable polling to bypass it. No default credentials are emitted.

Explicit `acp.runtime.mode=development` with polling disabled supports isolated
integration fixtures. It is not production startup evidence. Enabling polling in
development still requires complete valid runtime configuration and transport.
Proxy-network restriction, TLS operation and provider assurance require deployment
verification; declaring properties does not verify external infrastructure.

`fixtures/deployment-oidc/identity.ts` is a HUMAN_OWNED integration example using
issuer discovery, authorization-code PKCE, state and nonce. Its token and identity
hints are disposable in the integration exercise; backend signature, issuer,
audience, expiry, permission and tenant validation remain authoritative. Production
provider acceptance and identity assurance still require review.

## Audit gate

Each criterion declares required evidence, a verifier, pass/block conditions,
exact failure reason, deployment disposition and evaluation provenance. Files
must exist, match hashes, belong to the criterion and bind current approved
inputs, approval record, execution commit and sealed bundle. Evidence expires;
self-reported PASS is ignored. Deployment obligations require an externally
accepted human review digest, never a runner-created approval.

Exit 1 represents an audit execution exception. Exit 2 represents a performed
blocked closure recommendation. Dedicated CI preserves both machine evidence
and artifacts on either outcome and has no continue-on-error waiver. The
successor audit uses a new evidence identity. Final counts, exact seal, scans and
remaining blockers will be added after the complete run.
