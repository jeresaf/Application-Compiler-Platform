# Contract and implementation coverage

Phase 1 baseline, 2026-09-16. This table distinguishes executable checks from requirements and proposed work. Passing the kernel is deliberately narrower than validating a production application.

| Area | Executable now | Contract/proposal still required |
| --- | --- | --- |
| Meta-model shape | 20 discriminated kinds, shared envelope, strict unknown-field/version rejection | Extensions in meta-model §7 and P-01–P-05 |
| Identity/references | Duplicate IDs, exact local revisions, reference kind checks | Persistent allocation/history, cross-snapshot/app references, atomic revisions |
| Intent/provenance | Seven intent kinds; origins; derived basis; justification cycles | Trusted origins, meaning interpretation, conflict inference |
| Lifecycle | Current approval-record binding, eligible compile snapshot, supersession consistency | Transition engine, authenticated/revocable digest-bound approvals, separation of duties |
| Types/rules | Primitive/nominal types, money currencies, literal types, pure operators, Boolean predicates, field bindings | Currency registry, email/time lexical checks, rounding, nullable/collections/refinements, evaluation/enforcement |
| Security | Actor/role/action/resource relationships; secret type/classification; tenant expression typing | Authentication, role assignment, mandatory tenant-scope proof, policy composition/evaluation, authorization tests across targets |
| Workflow | State ownership, initial state, terminal transitions, duplicate triggers, graph reachability | Guard satisfiability/disjointness, effect execution/order/consistency, concurrency |
| Acceptance | Requirement/criterion reciprocity | TestRequirement/evidence schema, generated tests, freshness and trusted results |
| Conflict/uncertainty | Explicit issue storage; blocking open issues fail compile; resolved issues require an approved decision record | Formal contradiction detection and verification that a decision substantively resolves the issue |
| Compiler stages | Shape/reference/type/approval checker only | Canonical normalizer, projections, lowering, target IR, generation, stage conformance |
| Determinism | Stable diagnostics, no input mutation, valid node/key/approval reorder cases | Cross-runtime canonical bytes/digests, deterministic target artifacts, full cache/input manifests |
| Evolution/provenance/source | Rename reference fixture; origin/basis references | Change engine, journal, semantic diff, migration planner, source intelligence, ownership maps, drift |
| Production/security | Input bounds, strict decoding, non-echo error messages | Sandbox, supply chain, production profile, runtime evidence and all production gate execution |

## Charter coverage map

| Charter sections | Primary contract |
| --- | --- |
| 1–6, 27 | Constitution, identity/lifecycle ADR, meta-model intent |
| 7–16 | Meta-model kernel and extension proposals; IR boundaries |
| 17–22 | Change model, provenance, versioning, P-06/P-07 |
| 23–25 | Technology evaluation ADR; source-analysis port |
| 26 | Ownership/provenance contract, P-09 |
| 28–29 | Future MCP adapter boundary and context completeness; no MCP implementation |
| 30–35 | Threat model and production gates, P-05/P-11/P-12 |
| 36–37 | Target port, capability negotiation, P-08 |
| 38–40 | Roadmap and reference corpus strategy |
| 41–48 | Minimal repository, ADR index/proposal register, explicit phase gates |

## Regression policy

Every meaningful semantic validator bug adds a reproducing portable case or property before its fix. New executable kinds require valid and invalid fixtures, diagnostics, owner/reference/type/lifecycle rules, and coverage updates in the same change. A schema addition alone cannot make a capability supported. Do not label a future test plan as an executed test.
