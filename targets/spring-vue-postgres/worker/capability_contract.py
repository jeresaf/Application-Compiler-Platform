"""Reviewed exact capability scope; retained obligations are not enforcement."""

OBLIGATIONS = set('Requirement Decision Fact Goal Assumption Preference AcceptanceCriterion Applicability EvidenceRequirement TestRequirement Backup Recovery PerformanceRequirement ReliabilityRequirement CompatibilityRequirement Constraint Service ResponsivePolicy AccessibilityRequirement ObservabilityRequirement'.split())
UI_PENDING = set('Screen Form InputControl Table Filter Search Wizard WizardStep Action ViewState PermissionBoundary'.split())
PENDING = UI_PENDING | set('DataClassification Job Schedule RetryPolicy DataLifecycle Retention DeletionPolicy LegalHold RatePolicy IdempotencyPolicy DeliveryPolicy Failure'.split())

# Each group states implemented behavior, executable restriction and evidence.
GROUPS = [
    ('Entity Field ValueObject TypeDefinition Parameter',
     'Closed typed records; explicit absence/null; scalar-preserving UTF-8 bytea; exact decimals; NONE/String LENGTH nominal refinements; operation resources SCOPED with one identity; unsupported row/DTO forms reject negotiation',
     'typed_contracts.py; execution_codegen.py; ExplicitExecutionTest; TypedHttpTest'),
    ('Aggregate Transaction UseCase ExecutionStep Command',
     'Canonical 0.2 explicit typed bindings/effects only; no inferred mutation semantics; one root and one atomic STOP boundary; expected-version locking; declared ordered assignments and post-state invariants; ordered comparisons only Integer/Duration/Money/Decimal/Percentage with explicit coalesce for null; other comparator types reject; no compensation/distributed/multi-commit effects',
     'execution_codegen.py; ExecutionStore.java; ExplicitExecutionTest rollback/effects/coordination'),
    ('Query',
     'Explicit typed projections and bounded textContains predicates; exact maximum/offset; tenant authorization; paginated admission BLOCKED until canonical total order is approved',
     'execution_codegen.py; TypedHttpTest; QUERY_ORDERING_REVIEW_REQUIRED'),
    ('Relation',
     'SCOPED same-tenant single-identity endpoints; min 0/1, max 1/UNBOUNDED, RESTRICT; deferred SQL cardinality, FK and uniqueness enforcement',
     'relations.py; ExplicitExecutionTest real PostgreSQL relation constraints'),
    ('Invariant',
     'WRITE required in resource invariant enforcement; explicitly attached to each mutating command; compiled supported typed expression subset; validation rejects other enforcement-only forms and missing applicable attachments',
     'execution_codegen.py; ExplicitExecutionTest post-state rollback'),
    ('Actor AuthenticationModel SessionPolicy Role RoleAssignment Permission Scope Policy PolicySet',
     'One authentication actor with SCOPED single-identity subject; actor expressions use identity/tenant only; signed issuer pwd/otp MFA claims; durable session idle/absolute/reauth/revocation; SAME_TENANT scopes; exact assignment/permission/action; DENY_OVERRIDES default DENY; policy literals/parameters/required fields, and/or, String/Identifier/Boolean equality and Integer/Duration/Money/Decimal/Percentage gt/gte only; optional/nullable/compound/nominal comparisons reject',
     'ApplicationPolicy.java; SessionGate.java; ApplicationPolicyTest; SessionGateTest; TypedHttpTest'),
    ('StateMachine State Transition',
     'One machine per resource; at most one transition per (machine,from,command); compiled guards; atomic state/version changes and denial rollback; no inferred lifecycle closure',
     'execution_codegen.py; ExplicitExecutionTest workflow/guard rollback'),
    ('Event',
     'Explicit typed payload construction and transactional durable staging only; event delivery remains UNSUPPORTED; no exactly-once or transport claim',
     'execution_codegen.py; ExecutionStore.event; ExplicitExecutionTest payload/rollback'),
]


def capabilities():
    result = {}
    for kinds, constraint, evidence in GROUPS:
        for kind in kinds.split():
            result[kind+'/0.2.0'] = {'status':'SUPPORTED_WITH_CONSTRAINT', 'constraints':[constraint], 'evidence':[evidence]}
    result.update({k+'/0.2.0':{'status':'OBLIGATION_ONLY', 'constraints':['Retained provenance/requirement; satisfaction OUTSTANDING; no runtime capability claimed'],
        'evidence':['compiler obligation projection; target runtime does not certify this requirement']} for k in sorted(OBLIGATIONS)})
    result.update({k+'/0.2.0':{'status':'UNSUPPORTED', 'constraints':[
        'Runtime semantics/enforcement or exact generated evidence incomplete; no admission based on representation alone'],
        'evidence':['docs/phase6-semantic-underspecification-audit.md; capability honesty review']} for k in sorted(PENDING|{'File','Blob','DistributedTransaction'})})
    result['semantic.execution-dataflow/0.3']={'status':'SUPPORTED_WITH_CONSTRAINT',
        'constraints':['Canonical 0.2 only; typed explicit root effects/results/payloads; atomic STOP; constrained expressions/types; unsupported forms reject negotiation'],
        'evidence':['execution_codegen.py; ExplicitExecutionTest; TypedHttpTest']}
    return result
