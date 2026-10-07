"""Bounded reference compiler kernel. Pure transformations, explicit trusted ports."""
from dataclasses import fields, is_dataclass, replace
from pathlib import PurePosixPath
import re

from canonical_ir import CanonicalError, admit, normalize_candidate, validate_snapshot
from canonical_json import canonical_bytes, loads, MAX_BYTES, MAX_DEPTH
from changes import graph, references, reverse
from compiler_contracts import (VERSION, COMPILER, PIPELINE, STAGES, Stage,
    Document, Subject, Provenance, Diagnostic, Obligation, Metrics, Success,
    Failure, Source, Ingested, SemanticAST, ResolvedModel, CanonicalModel,
    Derived, Projection, Projections, Realization, TargetIR, Artifact, ArtifactPlan,
    Owner, StageAudit, CompilationAudit, Compilation, CacheEntry, Impact,
    fingerprint, wire)
from compiler_ports import CompilationContext
from validate import validate

# Every listed code has an executable failure path and regression test.
MESSAGES = {
    "INPUT": ("Stage input or manifest is invalid.", "Supply the exact immutable stage contract and declared inputs."),
    "VERSION": ("Stage, compiler or manifest version is unsupported.", "Use the exact registered versions and features."),
    "DEPENDENCY": ("An exact dependency is missing, invalid or cyclic.", "Supply validated exact snapshots and an acyclic dependency manifest."),
    "ANALYSIS": ("Semantic analysis failed.", "Repair authoring references, types, blocking issues or policies."),
    "SNAPSHOT": ("Canonical snapshot does not match the declared compilation base.", "Compile against the exact validated canonical digest."),
    "APPROVAL": ("Exact-content approval is unavailable or rejected.", "Supply independently approved exact-content evidence through the authority port."),
    "PROJECTION": ("Projection does not preserve the canonical concepts.", "Retain exact concepts, revisions and projection partition."),
    "DECISION": ("Required approved architecture/design decisions are missing or invalid.", "Bind independently approved decisions to exact canonical origins."),
    "CAPABILITY": ("The target does not support every required capability.", "Use an exact target manifest supporting every required capability."),
    "OBLIGATION": ("A required obligation was dropped, changed or incorrectly discharged.", "Carry every obligation outstanding until an authorized evidence stage discharges it."),
    "NONDETERMINISM": ("Repeated deterministic execution disagreed.", "Remove ambient inputs from the stage and pin all producer inputs."),
    "CACHE": ("A deterministic cache entry failed integrity verification.", "Discard the damaged cache through its adapter and recompute."),
    "PROVENANCE": ("Derived identity or provenance is invalid or collides.", "Use exact canonical origins, producer versions and an explicit role/discriminator."),
    "ARTIFACT": ("Artifact path, digest or plan is unsafe or collides.", "Use unique normalized relative paths and digest-bound content."),
    "OWNERSHIP": ("Artifact ownership or expected content conflicts with the plan.", "Preserve human-owned content and review ownership adoption separately."),
    "CANCELLED": ("Compilation was cancelled.", "Submit a new uncancelled compilation request."),
    "RESOURCE": ("A declared execution budget was exhausted.", "Reduce input/work or explicitly revise the execution policy."),
    "PORT": ("A declared port failed its reference contract.", "Repair the adapter; no partial output is compilable."),
}
DOMAIN_KINDS = frozenset({"Entity", "Field", "Parameter", "Invariant", "ValueObject", "Relation", "Aggregate", "TypeDefinition", "Command", "Event"})
APPLICATION_KINDS = frozenset({"Service", "Query", "UseCase", "ExecutionStep", "Transaction", "Failure", "RetryPolicy", "IdempotencyPolicy", "DeliveryPolicy", "Schedule", "Job", "Policy", "PolicySet", "Permission", "Scope", "Actor", "Role", "RoleAssignment", "AuthenticationModel", "SessionPolicy", "RatePolicy", "StateMachine", "State", "Transition", "Screen", "Form", "InputControl", "Action", "Wizard", "WizardStep", "Table", "Search", "Filter", "ViewState", "PermissionBoundary", "ResponsivePolicy"})
CATEGORIES = {
    "authorization": {"Permission", "Policy", "PolicySet", "Scope", "PermissionBoundary"},
    "audit": {"DataClassification"},
    "privacy": {"Retention", "DeletionPolicy", "LegalHold", "DataLifecycle", "DataClassification"},
    "accessibility": {"AccessibilityRequirement"},
    "tests": {"TestRequirement", "AcceptanceCriterion", "EvidenceRequirement"},
    "reliability": {"ReliabilityRequirement", "Backup", "Recovery"},
    "observability": {"ObservabilityRequirement"},
    "compatibility": {"CompatibilityRequirement"},
    "performance": {"PerformanceRequirement"},
    "constraint": {"Constraint", "Invariant", "Requirement"},
}


class CompilerFault(ValueError):
    def __init__(self, code, subjects=(), location=None):
        super().__init__(code)
        self.code, self.subjects, self.location = code, tuple(sorted(subjects)), location


def fail(code, subjects=(), location=None):
    raise CompilerFault(code, subjects, location)


def role_for(kind):
    return "Domain" if kind in DOMAIN_KINDS else "Application" if kind in APPLICATION_KINDS else "Product"


def derived_id(origins, role, discriminator="record"):
    if not origins or len(set(origins)) != len(origins):
        fail("PROVENANCE")
    # Revisions affect content and cache keys, not durable derived identity.
    identities = sorted({(s.application, s.id) for s in origins})
    return fingerprint((tuple(identities), role, discriminator), "derived-identity")


def _subjects(model):
    app = model["applicationId"]
    return tuple(sorted(Subject(app, n["id"], n["revision"]) for n in model["nodes"]))


def _obligations(value):
    if isinstance(value, Realization):
        return value.projections.obligations
    return getattr(value, "obligations", ())


def _immutable(value):
    if is_dataclass(value):
        if not value.__dataclass_params__.frozen:
            fail("INPUT")
        for f in fields(value):
            _immutable(getattr(value, f.name))
    elif isinstance(value, tuple):
        for item in value:
            _immutable(item)
    elif type(value) not in (str, bytes, int, bool, type(None)) and not isinstance(value, (Stage, Owner)):
        fail("INPUT")


class Budget:
    def __init__(self, context):
        self.context, self.used = context, 0

    def tick(self, amount=1):
        self.used += amount
        request = self.context.request
        c, r = request.cancellation, request.resources
        if c.cancelled or (c.after_work is not None and self.used >= c.after_work):
            fail("CANCELLED")
        if "control" in request.allowed_ports:
            if self.context.control.cancelled():
                fail("CANCELLED")
            if self.context.control.elapsed_ms() >= r.timeout_ms:
                fail("RESOURCE")
        if self.used > r.work:
            fail("RESOURCE")

    def inspect(self, value, output=False):
        """Iterative depth/work bound before any recursive codec/semantic helper."""
        r = self.context.request.resources
        stack = [(wire(value), 0)]
        while stack:
            item, depth = stack.pop()
            self.tick()
            if depth > r.depth:
                fail("RESOURCE")
            if isinstance(item, dict):
                if type(item.get("nodes")) is list and len(item["nodes"]) > r.nodes:
                    fail("RESOURCE")
                stack.extend((v, depth + 1) for v in item.values())
            elif isinstance(item, list):
                stack.extend((v, depth + 1) for v in item)
        try:
            size = len(canonical_bytes(wire(value)))
        except (ValueError, RecursionError, MemoryError):
            fail("RESOURCE")
        if size > (r.output_bytes if output else r.input_bytes):
            fail("RESOURCE")


def _manifest(ctx):
    r = ctx.request
    _immutable(r)
    _immutable(ctx.inventory)
    if ctx.approval is None:
        fail("APPROVAL")
    if ctx.frontend is None or ctx.target is None:
        fail("PORT")
    if (r.version != VERSION or r.compiler != COMPILER or r.pipeline != PIPELINE or
            r.features != ("acp.phase1.0.2",) or ctx.frontend.identity != r.frontend or ctx.approval.identity != r.authority or
            ctx.target.identity != r.target or ctx.target.generator != r.generator):
        fail("VERSION")
    if (type(r.start) is not Stage or type(r.end) is not Stage or
            STAGES.index(r.start) > STAGES.index(r.end) or r.repository_root != "."):
        fail("INPUT")
    if any(type(getattr(r.resources, f.name)) is not int or getattr(r.resources, f.name) < 1 for f in fields(r.resources)):
        fail("INPUT")
    if r.resources.input_bytes > MAX_BYTES or r.resources.output_bytes > MAX_BYTES or r.resources.depth > MAX_DEPTH:
        fail("INPUT")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", r.snapshot_digest) or not re.fullmatch(r"sha256:[0-9a-f]{64}", r.source_digest):
        fail("INPUT")
    for values in (r.features, r.required_capabilities, r.accepted_ai_candidates, r.required_decisions, r.allowed_ports):
        if tuple(sorted(set(values))) != tuple(sorted(values)):
            fail("INPUT")
    if set(r.allowed_ports) - {"frontend", "snapshots", "approval", "target", "cache", "control"}:
        fail("INPUT")
    if tuple(sorted(fingerprint(d, "decision") for d in r.decisions)) != tuple(sorted(r.decision_digests)):
        fail("DECISION")
    if any(not re.fullmatch(r"sha256:[0-9a-f]{64}", d) for d in r.accepted_ai_candidates):
        fail("INPUT")
    if type(r.configuration) is not Document or type(r.approval_evidence) is not Document or type(r.configuration.read()) is not dict or type(r.approval_evidence.read()) is not dict:
        fail("INPUT")
    if type(r.cancellation.cancelled) is not bool or (r.cancellation.after_work is not None and (type(r.cancellation.after_work) is not int or r.cancellation.after_work < 0)):
        fail("INPUT")


def _port(ctx, name):
    if name not in ctx.request.allowed_ports:
        fail("PORT")


def _provenance(ctx, stage, inputs, origins=()):
    return Provenance(tuple(sorted(set(origins))), stage, ctx.request.compiler,
                      ctx.request.pipeline, tuple(sorted(set(inputs))))


def _stage_key(stage, value, ctx):
    # All request declarations participate. Root is a logical locator, never an OS path.
    return fingerprint((stage, ctx.request, value, ctx.inventory if stage == Stage.GENERATE else ()), "stage-identity")


def _dependencies(ctx, budget):
    _port(ctx, "snapshots")
    entries = ctx.request.dependencies
    by_id = {e.identity: e for e in entries}
    if len(by_id) != len(entries):
        fail("DEPENDENCY")
    # Kahn traversal; dependency-manifest cycles fail, semantic reference cycles may be legal.
    remaining = {e.identity: set(e.requires) for e in entries}
    if any(set(e.requires) - set(by_id) for e in entries):
        fail("DEPENDENCY")
    while remaining:
        budget.tick(len(remaining))
        ready = sorted(k for k, v in remaining.items() if not v)
        if not ready:
            fail("DEPENDENCY")
        for key in ready:
            entry = by_id[key]
            try:
                snapshot = ctx.snapshots.read_exact(entry.identity, entry.digest).read()
                budget.inspect(snapshot)
                validate_snapshot(snapshot)
                if snapshot["contentDigest"] != entry.digest or snapshot["content"]["applicationId"] != entry.identity:
                    fail("DEPENDENCY")
                _approve(snapshot, ctx)
            except (KeyError, ValueError):
                fail("DEPENDENCY")
            del remaining[key]
        for deps in remaining.values():
            deps.difference_update(ready)
    return tuple(sorted(e.digest for e in entries))


def _approve(snapshot, ctx):
    _port(ctx, "approval")
    try:
        admitted = admit(snapshot, lambda query: ctx.approval.approve_content(query, ctx.request.approval_evidence))
    except CanonicalError:
        fail("APPROVAL")
    return Document.of({"contentDigest": admitted.content_digest,
                        "evidenceDigest": fingerprint(ctx.request.approval_evidence, "approval-evidence")})


def _closure(seeds, edges, budget):
    seen, pending = set(), list(sorted(seeds))
    while pending:
        budget.tick()
        key = pending.pop()
        if key not in seen:
            seen.add(key)
            pending.extend(sorted(edges.get(key, set()) - seen))
    return seen


def extract_obligations(model):
    result = []
    for n in model["nodes"]:
        origin = (Subject(model["applicationId"], n["id"], n["revision"]),)
        for category, kinds in CATEGORIES.items():
            if n["kind"] in kinds:
                result.append(Obligation(derived_id(origin, "obligation", category), category, origin))
    return tuple(sorted(result, key=lambda o: o.id))


def expected_obligations(model, request):
    current = set(_subjects(model))
    extra = request.change_obligations
    if extra and (request.change_plan_digest is None or any(not o.origins or not set(o.origins) <= current or o.status != "OUTSTANDING" for o in extra)):
        fail("OBLIGATION")
    if request.change_plan_digest is not None and not re.fullmatch(r"sha256:[0-9a-f]{64}", request.change_plan_digest):
        fail("INPUT")
    all_obligations = (*extract_obligations(model), *extra)
    if len({o.id for o in all_obligations}) != len(all_obligations):
        fail("OBLIGATION")
    return tuple(sorted(all_obligations, key=lambda o: o.id))


def _project(snapshot, ctx, budget):
    nodes = {n["id"]: n for n in snapshot["content"]["nodes"]}
    edges = graph(snapshot)
    app = snapshot["content"]["applicationId"]
    views = {role: [] for role in ("Product", "Domain", "Application")}
    hits = misses = 0
    for id, n in sorted(nodes.items()):
        budget.tick()
        role = role_for(n["kind"])
        origins = (Subject(app, id, n["revision"]),)
        used = tuple(nodes[k] for k in sorted(_closure({id}, edges, budget)))
        # Only declared dependencies/config/versions and exact semantic closure affect this pure projection.
        declaration = (ctx.request.compiler, ctx.request.pipeline, ctx.request.features,
                       ctx.request.configuration, tuple(sorted(ctx.request.dependencies)))
        input_digest = fingerprint((used, declaration), "projection-input")
        key = fingerprint((role, app, id, input_digest), "projection-cache")
        expected = Derived(derived_id(origins, role), role, Document.of(n),
                           _provenance(ctx, Stage.PROJECT, (input_digest,), origins))
        _port(ctx, "cache")
        cached = ctx.cache.get(key)
        if cached is not None:
            if type(cached) is not CacheEntry or cached.key != key or cached.digest != fingerprint(cached.value) or cached.value != expected:
                fail("CACHE", origins)
            obj = cached.value
            hits += 1
        else:
            obj = expected
            ctx.cache.put(CacheEntry(key, obj, fingerprint(obj)))
            misses += 1
        views[role].append(obj)
    return tuple(Projection(role, tuple(objects)) for role, objects in views.items()), hits, misses


def validate_projections(value, ctx, budget):
    snapshot = value.snapshot.read()
    validate_snapshot(snapshot)
    if snapshot["contentDigest"] != ctx.request.snapshot_digest:
        fail("SNAPSHOT")
    nodes = {n["id"]: n for n in snapshot["content"]["nodes"]}
    seen = set()
    if tuple(v.role for v in value.views) != ("Product", "Domain", "Application"):
        fail("PROJECTION")
    for view in value.views:
        for obj in view.objects:
            budget.tick()
            n = obj.semantic.read()
            if n.get("id") not in nodes or n != nodes[n["id"]] or role_for(n["kind"]) != view.role or n["id"] in seen:
                fail("PROJECTION")
            seen.add(n["id"])
            origin = (Subject(ctx.request.application, n["id"], n["revision"]),)
            if obj.role != view.role or obj.id != derived_id(origin, view.role) or obj.provenance.origins != origin:
                fail("PROVENANCE")
    if seen != set(nodes):
        fail("PROJECTION")
    if value.obligations != expected_obligations(snapshot["content"], ctx.request):
        fail("OBLIGATION")


def safe_path(path):
    if type(path) is not str or not path or "\\" in path or ":" in path or "\x00" in path or any(ord(c) < 32 for c in path):
        fail("ARTIFACT")
    parts = path.split("/")
    if PurePosixPath(path).is_absolute() or any(p in {"", ".", ".."} for p in parts):
        fail("ARTIFACT")
    return path


def validate_plan(plan, inventory, obligations, budget=None):
    _immutable(plan)
    _immutable(inventory)
    if type(plan) is not ArtifactPlan or plan.version != VERSION:
        fail("VERSION")
    if plan.obligations != obligations or any(o.status != "OUTSTANDING" for o in plan.obligations):
        fail("OBLIGATION")
    existing = {}
    for item in inventory:
        path = safe_path(item.path)
        if path in existing or type(item.owner) is not Owner:
            fail("OWNERSHIP")
        existing[path] = item
    seen = set()
    for a in plan.artifacts:
        if budget:
            budget.tick()
        path = safe_path(a.path)
        # File/directory prefix collisions are also ownership conflicts.
        if path in seen or any(path.startswith(p + "/") or p.startswith(path + "/") for p in seen):
            fail("ARTIFACT")
        seen.add(path)
        if a.content_digest != fingerprint(a.content, "artifact-content") or a.write_policy != "COMPARE_AND_SWAP" or not a.verification:
            fail("ARTIFACT")
        if not a.mappings or a.mappings != a.provenance.origins:
            fail("PROVENANCE")
        prior = existing.get(path)
        if any(path.startswith(p + "/") or p.startswith(path + "/") for p in existing if p != path):
            fail("OWNERSHIP")
        if type(a.owner) is not Owner or a.intent not in {"CREATE", "UPDATE", "NO_OP"}:
            fail("OWNERSHIP")
        if prior:
            if a.expected_digest != prior.digest or a.owner != prior.owner:
                fail("OWNERSHIP")
            expected = "NO_OP" if prior.digest == a.content_digest else "UPDATE"
            if a.intent != expected or (prior.owner == Owner.HUMAN and a.intent != "NO_OP"):
                fail("OWNERSHIP")
        elif a.expected_digest is not None or a.intent != "CREATE" or a.owner == Owner.HUMAN:
            fail("OWNERSHIP")


def _perform(stage, value, ctx, budget):
    r = ctx.request
    if stage == Stage.INGEST:
        if fingerprint(value, "source") != r.source_digest:
            fail("INPUT")
        model = value.document.read()
        if type(model) is not dict or model.get("modelVersion") != "0.2.0":
            fail("VERSION")
        if len(model.get("nodes", [])) > r.resources.nodes:
            fail("RESOURCE")
        locations = value.source_map.read()
        if set(locations) - {n.get("id") for n in model.get("nodes", []) if isinstance(n, dict)}:
            fail("INPUT")
        if type(locations) is not dict or any(type(v) is not str or v.startswith("/") or "\\" in v or ":" in v or ".." in v.split("/") for v in locations.values()):
            fail("INPUT")
        _port(ctx, "frontend")
        result = ctx.frontend.ingest(value)
        if type(result) is not Ingested or result.representation != value.document or result.source_map != value.source_map or result.dialect != r.frontend:
            fail("INPUT")
        return result, 0, 0
    if stage == Stage.ELABORATE:
        if value.dialect != r.frontend:
            fail("VERSION")
        model = value.representation.read()
        if type(model) is not dict or model.get("modelVersion") != "0.2.0":
            fail("VERSION")
        # Structured representation is copied into the frontend-independent contract.
        return SemanticAST(Document.of(model), value.source_map), 0, 0
    if stage == Stage.ANALYZE:
        deps = _dependencies(ctx, budget)
        model = value.model.read()
        if len(model.get("nodes", [])) > r.resources.nodes:
            fail("RESOURCE")
        if model.get("applicationId") != r.application:
            fail("INPUT")
        diagnostics = validate(model, "compile")
        if diagnostics:
            # Do not echo third-party wording or input values. Translate only subjects and safe locations.
            subjects = {n["id"]: Subject(r.application, n["id"], n["revision"]) for n in model.get("nodes", []) if type(n) is dict and type(n.get("id")) is str and type(n.get("revision")) is int}
            chosen = tuple(sorted({subjects[d["subject"]] for d in diagnostics if d["subject"] in subjects}))
            locations = value.source_map.read()
            fail("ANALYSIS", chosen[:r.resources.diagnostics], next((locations[s.id] for s in chosen if s.id in locations), None))
        return ResolvedModel(value.model, value.source_map, deps, expected_obligations(model, r)), 0, 0
    if stage == Stage.NORMALIZE:
        if value.dependency_digests != tuple(sorted(d.digest for d in r.dependencies)):
            fail("DEPENDENCY")
        _dependencies(ctx, budget)
        candidate = normalize_candidate(value.model.read())
        if candidate["contentDigest"] != r.snapshot_digest:
            fail("SNAPSHOT")
        if value.obligations != expected_obligations(candidate["content"], r):
            fail("OBLIGATION")
        admission = _approve(candidate, ctx)
        return CanonicalModel(Document.of(candidate), admission, value.obligations, value.source_map), 0, 0
    if stage == Stage.PROJECT:
        snapshot = value.snapshot.read()
        validate_snapshot(snapshot)
        if snapshot["contentDigest"] != r.snapshot_digest or snapshot["content"]["applicationId"] != r.application:
            fail("SNAPSHOT")
        if value.admission != _approve(snapshot, ctx):
            fail("APPROVAL")
        if value.obligations != expected_obligations(snapshot["content"], ctx.request):
            fail("OBLIGATION")
        views, hits, misses = _project(snapshot, ctx, budget)
        return Projections(value.snapshot, views, value.obligations, value.source_map), hits, misses
    if stage == Stage.REALIZE:
        validate_projections(value, ctx, budget)
        _approve(value.snapshot.read(), ctx)
        roles = {d.role for d in r.decisions}
        if not set(r.required_decisions) <= roles or set(r.required_decisions) != {"architecture", "design"}:
            fail("DECISION")
        current = set(_subjects(value.snapshot.read()["content"]))
        if len({d.id for d in r.decisions}) != len(r.decisions) or any(not d.origins or not set(d.origins) <= current or d.role not in {"architecture", "design"} for d in r.decisions):
            fail("DECISION")
        _port(ctx, "approval")
        if ctx.approval.approve_decisions(r.snapshot_digest, r.decisions, r.approval_evidence) is not True:
            fail("DECISION")
        decision_inputs = r.decision_digests
        objects = tuple(Derived(derived_id(o.provenance.origins, "Realization", o.role), "Realization", o.semantic,
            _provenance(ctx, stage, (fingerprint(o), *decision_inputs), o.provenance.origins)) for v in value.views for o in v.objects)
        return Realization(value, tuple(sorted((d for d in r.decisions if d.role == "architecture"), key=lambda d: d.id)), tuple(sorted((d for d in r.decisions if d.role == "design"), key=lambda d: d.id)), objects), 0, 0
    if stage == Stage.LOWER:
        validate_projections(value.projections, ctx, budget)
        _approve(value.projections.snapshot.read(), ctx)
        expected_decisions = tuple(sorted(r.decisions, key=lambda d: d.id))
        if tuple(sorted((*value.architecture, *value.design), key=lambda d: d.id)) != expected_decisions or ctx.approval.approve_decisions(r.snapshot_digest, r.decisions, r.approval_evidence) is not True:
            fail("DECISION")
        projected = tuple(o for v in value.projections.views for o in v.objects)
        expected_objects = tuple(Derived(derived_id(o.provenance.origins, "Realization", o.role), "Realization", o.semantic,
            _provenance(ctx, Stage.REALIZE, (fingerprint(o), *r.decision_digests), o.provenance.origins)) for o in projected)
        if value.objects != expected_objects:
            fail("PROVENANCE")
        _port(ctx, "target")
        if not set(r.required_capabilities) <= set(ctx.target.capabilities):
            fail("CAPABILITY")
        result = ctx.target.lower(value, r)
        if type(result) is not TargetIR or result.target != r.target or result.capabilities != tuple(sorted(r.required_capabilities)):
            fail("CAPABILITY")
        if result.source_map != value.projections.source_map:
            fail("PROVENANCE")
        if result.obligations != value.projections.obligations:
            fail("OBLIGATION")
        _check_derived(value.objects, result.objects, stage, ctx)
        return result, 0, 0
    if stage == Stage.GENERATE:
        _port(ctx, "snapshots")
        snapshot = ctx.snapshots.read_exact(r.application, r.snapshot_digest).read()
        validate_snapshot(snapshot)
        if snapshot["contentDigest"] != r.snapshot_digest:
            fail("SNAPSHOT")
        _approve(snapshot, ctx)
        if value.obligations != expected_obligations(snapshot["content"], ctx.request):
            fail("OBLIGATION")
        nodes = {n["id"]: n for n in snapshot["content"]["nodes"]}
        if len(value.objects) != len(nodes) or len({o.id for o in value.objects}) != len(nodes):
            fail("PROVENANCE")
        for obj in value.objects:
            n = obj.semantic.read()
            origin = (Subject(r.application, n["id"], n["revision"]),)
            if n != nodes.get(n["id"]) or obj.provenance.origins != origin or obj.id != derived_id(origin, str(Stage.LOWER)):
                fail("PROVENANCE")
        _port(ctx, "target")
        if value.target != r.target or not set(r.required_capabilities) <= set(value.capabilities):
            fail("CAPABILITY")
        result = ctx.target.plan(value, r)
        result = _ownership(result, ctx.inventory)
        validate_plan(result, ctx.inventory, value.obligations, budget)
        source_origins = {o.provenance.origins for o in value.objects}
        if {a.mappings for a in result.artifacts} != source_origins:
            fail("PROVENANCE")
        by_origin = {o.provenance.origins: o for o in value.objects}
        if len(result.artifacts) != len(value.objects):
            fail("PROVENANCE")
        for a in result.artifacts:
            expected_locations = tuple(sorted({value.source_map.read()[s.id] for s in a.mappings if s.id in value.source_map.read()}))
            if a.source_locations != expected_locations:
                fail("PROVENANCE")
            if a.provenance.inputs != tuple(sorted((fingerprint(by_origin[a.mappings]), fingerprint(r.generator, "generator-manifest")))):
                fail("PROVENANCE")
            if a.provenance.stage != Stage.GENERATE or a.provenance.compiler != r.compiler or a.provenance.pipeline != r.pipeline or not a.provenance.inputs:
                fail("PROVENANCE")
        return result, 0, 0
    fail("INPUT")


def _check_derived(before, after, stage, ctx):
    if len({o.id for o in after}) != len(after) or len(before) != len(after):
        fail("PROVENANCE")
    by_origin = {o.provenance.origins: o for o in before}
    for obj in after:
        prior = by_origin.get(obj.provenance.origins)
        if prior is None or obj.semantic != prior.semantic or obj.provenance.stage != stage or obj.provenance.compiler != ctx.request.compiler or obj.provenance.pipeline != ctx.request.pipeline or obj.provenance.inputs != tuple(sorted((fingerprint(prior), fingerprint((ctx.request.target, ctx.request.required_capabilities), "target-manifest")))) or obj.id != derived_id(obj.provenance.origins, str(stage)):
            fail("PROVENANCE")


def _ownership(plan, inventory):
    if type(plan) is not ArtifactPlan:
        fail("ARTIFACT")
    by_path = {a.path: a for a in inventory}
    artifacts = []
    for a in plan.artifacts:
        prior = by_path.get(a.path)
        if prior is not None:
            a = replace(a, expected_digest=prior.digest, intent="NO_OP" if prior.digest == a.content_digest else "UPDATE")
        artifacts.append(a)
    return replace(plan, artifacts=tuple(artifacts))


INPUT_TYPES = dict(zip(STAGES, (Source, Ingested, SemanticAST, ResolvedModel, CanonicalModel, Projections, Realization, TargetIR)))
OUTPUT_TYPES = dict(zip(STAGES, (Ingested, SemanticAST, ResolvedModel, CanonicalModel, Projections, Realization, TargetIR, ArtifactPlan)))


def _source_map(value):
    if not hasattr(value, "source_map"):
        return
    mapping = value.source_map.read()
    if type(mapping) is not dict:
        fail("INPUT")
    for key, locator in mapping.items():
        if type(key) is not str or type(locator) is not str:
            fail("INPUT")
        try:
            safe_path(locator.split("#", 1)[0])
        except CompilerFault:
            fail("INPUT")


def _result_origins(value):
    if isinstance(value, Ingested):
        model = value.representation.read()
    elif isinstance(value, (SemanticAST, ResolvedModel)):
        model = value.model.read()
    elif isinstance(value, (CanonicalModel, Projections)):
        model = value.snapshot.read()["content"]
    elif isinstance(value, Realization):
        model = value.projections.snapshot.read()["content"]
    elif isinstance(value, TargetIR):
        return tuple(sorted({s for o in value.objects for s in o.provenance.origins}))
    elif isinstance(value, ArtifactPlan):
        return tuple(sorted({s for a in value.artifacts for s in a.mappings}))
    else:
        return ()
    if type(model) is not dict or type(model.get("nodes")) is not list:
        fail("INPUT")
    return tuple(sorted(Subject(model["applicationId"], n["id"], n["revision"]) for n in model["nodes"]
                        if type(n) is dict and type(n.get("id")) is str and type(n.get("revision")) is int))


def execute(stage, value, context: CompilationContext, *, repeat=False):
    """Independently executable stage boundary; failures have no output member."""
    budget = Budget(context)
    provenance = _provenance(context, stage, ())
    try:
        _manifest(context)
        if type(stage) is not Stage or type(value) is not INPUT_TYPES[stage]:
            fail("INPUT")
        _immutable(value)
        _source_map(value)
        if hasattr(value, "version") and value.version != VERSION:
            fail("VERSION")
        budget.inspect(context.request)
        budget.inspect(value)
        identity = _stage_key(stage, value, context)
        provenance = _provenance(context, stage, (identity, fingerprint(value)),
                                 tuple(s for o in _obligations(value) for s in o.origins))
        result, hits, misses = _perform(stage, value, context, budget)
        if type(result) is not OUTPUT_TYPES[stage]:
            fail("INPUT")
        _immutable(result)
        budget.inspect(result, output=True)
        origins = _result_origins(result)
        provenance = replace(provenance, origins=origins)
        if any(o.status != "OUTSTANDING" for o in _obligations(result)):
            fail("OBLIGATION")
        if _obligations(value) and _obligations(result) != _obligations(value):
            fail("OBLIGATION")
        if repeat:
            other, _, _ = _perform(stage, value, context, budget)
            if fingerprint(other) != fingerprint(result):
                fail("NONDETERMINISM")
        return Success(result, fingerprint(result), provenance, _obligations(result), (), Metrics(budget.used, hits, misses))
    except CompilerFault as error:
        code = error.code
        explanation, repair = MESSAGES[code]
        diagnostic = Diagnostic("ACP-COMPILER-" + code, "ERROR", stage, error.subjects,
                                error.location, (), explanation, repair, provenance)
    except CanonicalError:
        diagnostic = Diagnostic("ACP-COMPILER-SNAPSHOT", "ERROR", stage, (), None, (),
                                *MESSAGES["SNAPSHOT"], provenance)
    except (RecursionError, MemoryError):
        diagnostic = Diagnostic("ACP-COMPILER-RESOURCE", "ERROR", stage, (), None, (),
                                *MESSAGES["RESOURCE"], provenance)
    except (ValueError, TypeError, KeyError, AttributeError):
        diagnostic = Diagnostic("ACP-COMPILER-INPUT", "ERROR", stage, (), None, (),
                                *MESSAGES["INPUT"], provenance)
    except Exception:
        # Adapter exception text is untrusted and may contain secrets.
        diagnostic = Diagnostic("ACP-COMPILER-PORT", "ERROR", stage, (), None, (),
                                *MESSAGES["PORT"], provenance)
    return Failure((diagnostic,), provenance, Metrics(budget.used))


def compile_pipeline(value, context, *, repeat=False):
    audits = []
    r = context.request
    try:
        _manifest(context)
        selected = STAGES[STAGES.index(r.start):STAGES.index(r.end) + 1]
    except Exception:
        result = execute(Stage.INGEST, value, context)
        return Compilation(result, (), None)
    for stage in selected:
        result = execute(stage, value, context, repeat=repeat)
        if isinstance(result, Failure):
            return Compilation(result, tuple(audits), None)
        audits.append(StageAudit(stage, _stage_key(stage, value, context), fingerprint(value),
                                 result.output_digest, fingerprint(result.provenance), result.metrics))
        value = result.output
    audit = CompilationAudit(r.snapshot_digest, r.compiler, r.pipeline, tuple(audits),
        tuple(sorted(r.dependencies)), r.configuration, result.obligations,
        result.output_digest if isinstance(value, ArtifactPlan) else None,
        fingerprint(tuple(a.provenance_digest for a in audits)), "COMPLETE" if r.end == Stage.GENERATE else "RANGE_COMPLETE")
    return Compilation(result, tuple(audits), audit)


def incremental_impact(before, after, context, phase3_impact=()):
    """Conservative Phase 3 exact-reference invalidation; never trust caller impact alone."""
    validate_snapshot(before)
    validate_snapshot(after)
    if before["content"]["applicationId"] != after["content"]["applicationId"]:
        fail("SNAPSHOT")
    old = {n["id"]: n for n in before["content"]["nodes"]}
    new = {n["id"]: n for n in after["content"]["nodes"]}
    changed = {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}
    edges = graph(before)
    for key, deps in graph(after).items():
        edges.setdefault(key, set()).update(deps)
    budget = Budget(context)
    affected = _closure(changed | set(phase3_impact), reverse(edges), budget)
    roles = {role_for((new.get(k) or old[k])["kind"]) for k in affected if k in old or k in new}
    return Impact(tuple(sorted(changed)), tuple(sorted(affected)), tuple(sorted(roles)), STAGES if changed else ())
