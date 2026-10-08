# Bounded Phase 6 task-interface implementation plan

Status: PLAN ONLY. Phase 6 IN PROGRESS; Phase 7 NOT STARTED. No capability promotion or generic CRUD implementation. Authority is accepted [ADR-0009](adr/0009-task-interfaces.md) and [ADR-0015](adr/0015-explicit-operation-effects-and-dataflow.md), not proposed lifecycle/rate semantics. The 11 UI families remain UNSUPPORTED. The target must reject declarations outside its eventual tested subset rather than render a misleading partial screen.

## Scope and sequence

First build a reproducible generated Vue browser harness against approved Canonical 0.2 fixture applications, with explicit component-only status while full admission remains blocked. Pin browser/test dependencies in a target-profile lock and record versions, snapshot digest, generation bundle, screenshots, accessibility results and browser failures. Separate production negotiation from harness generation. Browser tests must exercise generated output, not hand-written substitute pages; component tests alone cannot promote UI support.

Next lower exact task bindings into a validated view model: screen ownership, use-case input/output, query result fields, operation permissions, step prerequisites and state recovery. Preserve exact revisions and reject stale references, missing projections or unsupported control types before generation. Generate state, forms/actions, query tables/filter/search, then wizard navigation. Do not derive an Entity editor or fabricate operation input values from column names. Authenticated browser sessions use backend-authorized endpoints; no frontend permission decision can discharge server enforcement.

| Family | Bounded implementation contract | Required generated browser evidence before support |
| --- | --- | --- |
| Screen | Own declared task, states and responsive reading/action order; stable semantic labels. | Both fixture task screens load; compact/expanded preserve declared actions, focus and reading order. No undeclared entity editor. |
| Form | Bind exact UseCase input ValueObject; construct its typed payload; preserve optional absence versus explicit nullable value. | Correct submission reaches the declared task; required, missing, nullable and invalid typed values show declared errors without accidental mutation. |
| InputControl | Bind an input field through the declared Form; match exact type/requiredness and input purpose. Initially reject types without an exact codec. | Label association, keyboard input, type boundaries, currency/precision and optional/null behavior; secret values never enter diagnostics. |
| Table | Render declared Query output projection and columns, never raw Entity fields. Use approved query contract without inventing proposed deterministic ordering. | Rows show exact projected values, no undeclared fields; empty/loading/error/success and accepted pagination subset work. Reject unsupported pagination semantics rather than infer total order. |
| Filter | Bind exact Query input field, including ADR-0015 `inputField`; construct typed query input. | Changing/resetting filter submits the correct field/value and refreshes results without hidden entity-field binding. |
| Search | Use declared Query/search binding and typed query input; reject unsupported matching modes. | Search invokes the declared query and handles results, no-results and errors; no guessed full-text semantics. |
| Wizard | Own ordered durable WizardSteps; maintain explicit navigation/prerequisite state. | Forward/back/failure/reload cases preserve declared prerequisites; direct navigation cannot skip required steps. |
| WizardStep | Own the declared form/action participation and exact sequence position. | Required input validation and completion gates prevent entering a later step prematurely; keyboard/focus follow transitions. |
| Action | Invoke the declared UseCase with exact bindings and permissions covering every operation; no fabricated success message. | Inspect actual request/typed response, success/failure rendering and repeated-click behavior within accepted semantics; backend denial remains effective. Do not claim proposed idempotency enforcement. |
| ViewState | Render EMPTY, LOADING, ERROR and SUCCESS; ERROR exposes declared recovery action. | Controlled network/error fixtures exercise all states, aria-live error announcement, focus recovery and successful retry. |
| PermissionBoundary | Preserve declared actor/scope for visibility and available actions; backend always rechecks exact permission/tenant. | Hidden/disabled actions plus direct forged HTTP invocation, wrong tenant and stale session deny; switching actors cannot expose prior data. |

Implement vertical fixture tasks, not isolated look-alike controls. Payment and case task flows must consume real declared Query outputs and UseCase inputs/results. A capability's eventual constraints must be machine-readable, reject all outside-subset declarations, and cite generated code sites plus browser tests. All 11 entries remain unsupported until those behaviors and tests exist. No new canonical version is needed for this bounded plan; a newly discovered missing meaning must be recorded before implementation.

## Admission and evidence

Use generated browser tests for keyboard operation, focus management, labels, error announcements, responsive action preservation and server denial. Automated accessibility tooling and manual accessibility review are separate evidence. Record unsupported input types, offline/reload persistence limits, browser versions and deployment session requirements honestly. Support is not inferred from a successful Vite build or screenshots.

Keep the 27-blocker expected-open manifest unchanged throughout this planning work. Before any later promotion, require human-approved relevant semantics, real implementation, exact negative negotiation tests, browser/runtime evidence and a deliberate blocker-contract revision. The proposed Canonical 0.3 candidates are never substituted into the current production gate.
