# ADR-0016 and deterministic-v04 approval

On 2026-10-08 the user explicitly instructed:

> Approve ADR-0016 and the complete deterministic-v04 fixture decisions, including the F-01 failure bindings.

ADR-0016 is ACCEPTED. Approval covers the complete synthetic Payment and Case reference decisions reviewed at commit `76e7700758454b5cfd00c39a68475439c1a1e6ca`, including ordered F-01 failure bindings, all lifecycle, query, rate, retry, invocation and delivery decisions. No repeat approval is required for those exact decisions.

The [machine-readable record](../test-corpus/deterministic-v04/human-approval.json) pins each exact canonical content digest, ChangeSet plan digest, authoring source digest and successor schema bytes. It also pins the ADR with its acceptance notice. The bounded reference authority represents this explicit act without inventing a reviewer identity or production credential. Its dated reference clock is not a claimed wall-clock event timestamp.

All previously reviewed fixture JSON, canonical vectors, schemas, AI origins and prior approval records remain unchanged. Proposal lifecycle and manifest metadata remain historical; the new record supplies the subsequent approval overlay. Historical proposal and validation reports retain their original status. Changed content or plans require fresh approval.

`tooling/deterministic_approval.py` reproduces and verifies the record and admits only the exact approved reference snapshots. Focused tests verify deterministic reproduction, exact admission, tamper rejection and preservation of reviewed bytes and target gates. This approval does not write a semantic journal or implement target support.

Target capability remains INCOMPLETE, with Failure UNSUPPORTED and the existing expected-open gate unchanged. Phase 6 remains IN PROGRESS. Phase 7 is NOT STARTED.
