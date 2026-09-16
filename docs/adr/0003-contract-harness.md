# ADR-0003: Executable contract notation and validation harness

Status: ACCEPTED for Phase 1 tooling only. Date: 2026-09-15.

## Evidence before selection

The repository initially contained only charter v0.2, with no implementation constraints or existing build. The local Python launcher resolved CPython 3.14.7; no Node command was on PATH. Availability is evidence for inexpensive test execution, not for selecting the production compiler runtime.

[JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-core) defines a language-independent JSON structure model, reusable definitions, and closed object validation. It does not resolve ACP semantic references or prove business behavior. [python-jsonschema](https://python-jsonschema.readthedocs.io/en/stable/validate/) exposes explicit draft validation, schema checking, and iterable errors. [Python unittest](https://docs.python.org/3/library/unittest.html) supplies standard test discovery. [Python JSON decoding](https://docs.python.org/3/library/json.html) permits duplicate-key hooks; strict decoding must explicitly reject repeated keys and nonfinite numbers.

## Decision and alternatives

Use a closed JSON Schema 2020-12 type prototype plus a small Python semantic validator and portable JSON fixtures. Pin the harness dependencies. Use standard `unittest`. No application source, DSL grammar, target compiler, or production service is introduced. JSON is fixture notation, not a final persistence, canonical hashing, or interchange decision.

Alternatives: prose alone cannot execute failure cases; language-specific core types prematurely constrain runtime; a custom schema language adds an unnecessary interpreter; full compiler scaffolding exceeds the phase. The selected schema notation remains usable by other language implementations.

| Concern | Support and limitation |
| --- | --- |
| Meta-model | Discriminated record shapes plus explicit semantic checks; only declared kernel kinds executable |
| Compiler stages | Shape, reference, type, and approval passes tested independently of any frontend |
| Diagnostics | Stable ACP codes and JSON pointers; no dependency on library message wording |
| Determinism | Sorted diagnostics, no network during validation, immutable inputs; production byte canonicalization deferred |
| Source intelligence | Preserved origin locators and semantic references; no syntax/type analyzer selected |
| Maintenance | Standard schema dialect, pinned validator, standard tests, reusable corpus; harness can be replaced without changing semantic contracts |

## Consequences

This adds a development dependency and a second validation layer for graph rules. It is not evidence that Python is the right production core. Production runtime, parser, IR transport, hashing, and plugin execution require separate measurements under [ADR-0004](0004-technology-evaluation.md). The harness must state its limits, reject unknown semantics, and never report a production-ready verdict.
