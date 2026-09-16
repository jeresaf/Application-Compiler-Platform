# Contract types

`kernel.schema.json` is the closed JSON Schema 2020-12 **authoring kernel** at version `0.1.0`. It defines 20 semantic kinds, typed expressions, exact references, origins, candidate lifecycles, fixture attestations, and explicit issues.

Shape validation is necessary but insufficient. `docs/metamodel.md` defines cross-record meaning, and `tooling/validate.py` implements the supported subset listed in `docs/coverage.md`. No schema reference is loaded from input or fetched over the network. Unknown fields/kinds/versions are rejected.

This is not the final Canonical IR envelope, persistence format, plugin ABI, or approval proof format. Changes require an ADR when material, a versioned contract change, corresponding positive/negative fixtures, and migration reasoning. Keep framework/runtime/vendor constructs out of these semantics.
