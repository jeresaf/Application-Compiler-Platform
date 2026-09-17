# ADR-0007: Explicit security and privacy obligations (P-02)

Status: ACCEPTED. Date: 2026-09-16. Supersedes P-02 in ADR-0005.

## Decision

Promote AuthenticationModel, Permission, Scope, RoleAssignment, PolicySet, DataClassification, SessionPolicy, RatePolicy, Retention, DeletionPolicy, LegalHold and DataLifecycle. Shared node identity, lifecycle, steward, origins and exact requirement/decision basis apply. References to roles, actors, actions, resources, fields and decisions are kind/revision checked before security analysis.

Every current-version entity declares GLOBAL, TENANT_ROOT or SCOPED tenancy. SCOPED resources require a nonoptional Identifier to a TENANT_ROOT. Authentication binds an actor; role assignment grants a modeled role within an explicit scope. Permissions name actor/action/resource. PolicySets compose only policies for the same action/resource; default DENY, DENY_OVERRIDES, and missing context means DENY. Explicit ALLOW+DENY is resolved by DENY, not priority or order. Cross-tenant administration is outside this bounded model and rejected; a permissive predicate cannot bypass mandatory same-tenant scope.

Classification produces audit, encryption, export and redaction obligations independent of implementation. Sensitive/secret data must be encrypted and audited; secret data is omitted and export denied. Session expiry and rate limits are semantic durations/counts, with no provider, token format, cache or gateway assumptions.

Retention declares its trigger/minimum duration. Deletion uses the same trigger and may not precede retention. Legal hold always blocks deletion/anonymization; release requires an explicit permission. Anonymization identifies fields and cannot remove identity/tenant keys. DataLifecycle binds these policies; omission for sensitive entity data is an error. A policy is a requirement, never proof that data was actually removed or encrypted.

## Alternatives, consequences and deferrals

Role-only ACLs and UI visibility cannot represent record/tenant isolation. Arbitrary policy precedence is order-dependent. A fixed deny-overrides algebra gives testable semantics. Full attribute/relationship access control, federation protocols, consent law, jurisdiction rules, cascading privacy policies and proof of irreversible anonymization are deferred/rejected until separately modeled. Their absence does not block an IR for the accepted scope/obligation algebra. Runtime credential verification, rate/session enforcement and privacy execution are later-stage obligations.
