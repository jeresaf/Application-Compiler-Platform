# ADR-0009: Task interfaces and independent design bindings (P-04)

Status: ACCEPTED. Date: 2026-09-16. Supersedes P-04 in ADR-0005.

## Decision

Promote Screen (the task-oriented page concept), Form, InputControl, Action, Wizard, WizardStep, Table, Search, Filter, ViewState, PermissionBoundary and ResponsivePolicy. Shared identity/lifecycle/steward/origin/basis/reference contracts apply. Screen owns its view states, wizard and responsive policy. Wizards own ordered durable steps; forms bind to a use case's input ValueObject. Tables/search/filter bind to a Query's typed output projection. Binding a UI control/column/filter directly to an Entity field is rejected.

Actions invoke use cases, naming permissions covering every invoked operation. Permission boundaries preserve actor/scope semantics; hiding content never discharges backend authorization. Screens explicitly cover EMPTY, LOADING, ERROR and SUCCESS, with recovery action for errors. Forms name labels/error messages/input purpose; requiredness must match the input contract. Wizards cannot skip prerequisite steps. Responsive COMPACT/EXPANDED modes preserve available actions and reading order. Accessibility checks require labels, keyboard operation, focus management and error announcement; automated and manual evidence remain separate from declaration.

Design bindings live in a separate closed sidecar containing semantic subject references and a versioned design catalogue handle. They may not contain business rules, security overrides, entity bindings or framework code. Two fixture catalogues bind the same semantic UI unchanged. This is an authoring association contract; no Design IR payload, renderer or Canonical IR is implemented.

## Alternatives and deferrals

Entity-to-form generation is rejected because it cannot model tasks, errors, workflow or authorization. Arbitrary component trees/CSS/framework annotations would leak realization into intent. Layout algorithms, visual tokens, rich media, charts, native gesture semantics and frontend code generation are deferred to separately bounded design/target work. Screen is the accepted page concept; a second Page alias is unnecessary. These deferrals do not block expressing accepted UI semantics in a future IR.
