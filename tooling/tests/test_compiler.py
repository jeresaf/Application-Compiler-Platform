"""Phase 4 compiler boundary, determinism, resource and ownership regressions."""
import copy
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_fixtures import synthetic_approved
from canonical_ir import normalize_candidate
from canonical_json import canonical_bytes, load
from change_fixtures import change, revise
from changes import prepare
from compiler_contracts import (STAGES, Stage, Document, Success, Failure, Source,
    Subject, Provenance, Resources, Cancellation, Dependency, Owner, ExistingArtifact,
    CacheEntry, ArtifactPlan, fingerprint, wire)
from compiler_core import (compile_pipeline, execute, incremental_impact, derived_id,
    CompilerFault, safe_path, validate_plan, MESSAGES)
from compiler_fixtures import small_model
from compiler_reference import (fixture_context, SyntheticTarget, StructuredFrontend,
    MemoryCache, MemorySnapshots, MemoryArtifactStore, ReferenceControl)
from validate import ROOT


def authoring(snapshot):
    c = snapshot["content"]
    return synthetic_approved({"modelVersion": "0.2.0", "applicationId": c["applicationId"],
        "snapshotId": "SNAP-COMPILER-EVOLUTION", "nodes": c["nodes"], "issues": c["issues"], "approvals": []})


class CompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = {name: synthetic_approved(load(ROOT / "test-corpus/phase1" / name))
                      for name in ("payment.json", "case-management.json")}

    def setup_small(self, **kwargs):
        return fixture_context(small_model(), **kwargs)

    def success(self, result):
        self.assertIsInstance(result, Success, getattr(result, "diagnostics", ()))
        return result.output

    def error(self, result, code):
        self.assertIsInstance(result, Failure)
        self.assertFalse(hasattr(result, "output"))
        self.assertFalse(hasattr(result, "output_digest"))
        self.assertEqual(["ACP-COMPILER-" + code], [d.code for d in result.diagnostics])
        self.assertTrue(all(d.severity == "ERROR" for d in result.diagnostics))
        return result

    def stages(self, source, ctx):
        inputs, outputs = {}, {}
        value = source
        for stage in STAGES:
            inputs[stage] = value
            result = execute(stage, value, ctx)
            value = self.success(result)
            outputs[stage] = result
        return inputs, outputs

    def test_complete_both_domains_and_golden_vectors(self):
        vectors = load(ROOT / "test-corpus/compiler/vectors.json")
        for name, model in self.models.items():
            with self.subTest(domain=name):
                source, ctx = fixture_context(model)
                compilation = compile_pipeline(source, ctx)
                plan = self.success(compilation.result)
                self.assertEqual("COMPLETE", compilation.audit.status)
                self.assertEqual(STAGES, tuple(a.stage for a in compilation.stages))
                self.assertEqual(vectors["domains"][name]["artifactPlanDigest"], compilation.result.output_digest)
                self.assertEqual(vectors["domains"][name]["obligations"], len(plan.obligations))
                self.assertEqual(len(model["nodes"]), len(plan.artifacts))
                self.assertTrue(all(o.status == "OUTSTANDING" for o in plan.obligations))
                self.assertTrue({"authorization", "audit", "privacy", "accessibility", "tests", "reliability", "observability", "compatibility", "performance"} <= {o.category for o in plan.obligations})
                kinds = {a.content.read()["semantic"]["kind"] for a in plan.artifacts}
                self.assertTrue({"Entity", "ValueObject", "Command", "Query", "Permission", "Policy", "UseCase", "StateMachine", "Screen", "TestRequirement"} <= kinds)
                self.assertEqual(ctx.request.snapshot_digest, compilation.audit.input_canonical_digest)
                self.assertEqual(compilation.result.output_digest, compilation.audit.artifact_plan_digest)

    def test_stages_independently_testable_and_provenance_complete(self):
        source, ctx = self.setup_small()
        inputs, outputs = self.stages(source, ctx)
        expected = {Subject(ctx.request.application, n["id"], n["revision"]) for n in small_model()["nodes"]}
        for stage in STAGES:
            result = execute(stage, inputs[stage], ctx)
            output = self.success(result)
            self.assertEqual(fingerprint(output), result.output_digest)
            self.assertEqual(expected, set(result.provenance.origins))
            self.assertEqual(stage, result.provenance.stage)
            self.assertTrue(result.provenance.inputs)
        context = replace(ctx, request=replace(ctx.request, start=Stage.PROJECT, end=Stage.REALIZE))
        partial = compile_pipeline(inputs[Stage.PROJECT], context)
        self.success(partial.result)
        self.assertEqual("RANGE_COMPLETE", partial.audit.status)
        self.assertEqual((Stage.PROJECT, Stage.REALIZE), tuple(a.stage for a in partial.stages))

    def test_failure_at_every_stage_and_no_output(self):
        source, ctx = self.setup_small()
        inputs, _ = self.stages(source, ctx)
        self.error(execute(Stage.INGEST, replace(source, document=Document.of({})), ctx), "INPUT")
        self.error(execute(Stage.ELABORATE, replace(inputs[Stage.ELABORATE], dialect="unknown"), ctx), "VERSION")
        model = small_model()
        model["nodes"][1]["basis"] = [{"id": "MISSING", "revision": 1}]
        self.error(execute(Stage.ANALYZE, replace(inputs[Stage.ANALYZE], model=Document.of(model)), ctx), "ANALYSIS")
        stale = replace(ctx, request=replace(ctx.request, snapshot_digest="sha256:" + "0" * 64))
        self.error(execute(Stage.NORMALIZE, inputs[Stage.NORMALIZE], stale), "SNAPSHOT")
        self.error(execute(Stage.PROJECT, inputs[Stage.PROJECT], stale), "SNAPSHOT")
        missing = replace(ctx, request=replace(ctx.request, decisions=(), decision_digests=()))
        self.error(execute(Stage.REALIZE, inputs[Stage.REALIZE], missing), "DECISION")
        unsupported = replace(ctx, request=replace(ctx.request, required_capabilities=("impossible/1",)))
        self.error(execute(Stage.LOWER, inputs[Stage.LOWER], unsupported), "CAPABILITY")
        class Unsafe(SyntheticTarget):
            def plan(self, target, request):
                plan = super().plan(target, request)
                return replace(plan, artifacts=(replace(plan.artifacts[0], path="../secret"), *plan.artifacts[1:]))
        self.error(execute(Stage.GENERATE, inputs[Stage.GENERATE], replace(ctx, target=Unsafe())), "ARTIFACT")

    def test_no_downstream_execution_after_failure(self):
        source, ctx = self.setup_small()
        class Broken(StructuredFrontend):
            def ingest(self, source):
                raise RuntimeError("secret-value-must-not-appear")
        class Unreachable(SyntheticTarget):
            def lower(self, *args):
                self.fail("lower reached")
            def plan(self, *args):
                self.fail("generate reached")
        result = compile_pipeline(source, replace(ctx, frontend=Broken(), target=Unreachable()))
        failure = self.error(result.result, "PORT")
        self.assertEqual((), result.stages)
        self.assertIsNone(result.audit)
        self.assertNotIn("secret-value", canonical_bytes(wire(failure)).decode())

    def test_immutable_inputs_and_detached_document_reads(self):
        model = small_model()
        source, ctx = fixture_context(model)
        original = source.document.data
        model["nodes"].clear()
        detached = source.document.read()
        detached["nodes"].clear()
        self.assertEqual(original, source.document.data)
        self.success(compile_pipeline(source, ctx).result)
        with self.assertRaises(FrozenInstanceError):
            ctx.request.compiler = "changed"
        with self.assertRaises(FrozenInstanceError):
            source.document.data = b"{}"
        self.error(execute(Stage.INGEST, replace(source, source_map={}), ctx), "INPUT")

    def test_exact_versions_features_and_port_access(self):
        source, ctx = self.setup_small()
        for field in ("version", "compiler", "pipeline", "frontend", "authority", "target", "generator"):
            with self.subTest(field=field):
                bad = replace(ctx, request=replace(ctx.request, **{field: "0.1.1"}))
                self.error(compile_pipeline(source, bad).result, "VERSION")
        self.error(execute(Stage.INGEST, source, replace(ctx, request=replace(ctx.request, features=("unknown",)))), "VERSION")
        self.error(execute(Stage.INGEST, source, replace(ctx, request=replace(ctx.request, allowed_ports=()))), "PORT")
        inputs, _ = self.stages(source, ctx)
        self.error(execute(Stage.ANALYZE, replace(inputs[Stage.ANALYZE], version="0.1.1"), ctx), "VERSION")
        self.error(execute(Stage.PROJECT, inputs[Stage.REALIZE], ctx), "INPUT")

    def test_dependency_snapshots_and_cycles(self):
        source, ctx = self.setup_small()
        dep_model = small_model()
        dep_model["applicationId"] = "APP-DEPENDENCY"
        snapshot = Document.of(normalize_candidate(dep_model))
        entry = Dependency("APP-DEPENDENCY", snapshot.read()["contentDigest"])
        source, ctx = self.setup_small(dependencies=(entry,), dependency_snapshots=(snapshot,))
        self.success(compile_pipeline(source, ctx).result)
        missing = replace(ctx, snapshots=MemorySnapshots())
        self.error(compile_pipeline(source, missing).result, "DEPENDENCY")
        cycle = replace(entry, requires=(entry.identity,))
        self.error(compile_pipeline(source, replace(ctx, request=replace(ctx.request, dependencies=(cycle,)))).result, "DEPENDENCY")
        unknown = replace(entry, requires=("UNKNOWN",))
        self.error(compile_pipeline(source, replace(ctx, request=replace(ctx.request, dependencies=(unknown,)))).result, "DEPENDENCY")
        wrong = replace(entry, digest="sha256:" + "0" * 64)
        self.error(compile_pipeline(source, replace(ctx, request=replace(ctx.request, dependencies=(wrong,)))).result, "DEPENDENCY")

    def test_blocking_issue_unresolved_reference_and_redacted_diagnostics(self):
        source, ctx = self.setup_small()
        inputs, _ = self.stages(source, ctx)
        model = small_model()
        model["nodes"][1]["basis"] = [{"id": "MISSING", "revision": 1}]
        model["nodes"][1]["name"] = "sensitive-value-do-not-echo"
        ast = replace(inputs[Stage.ANALYZE], model=Document.of(model))
        a = self.error(execute(Stage.ANALYZE, ast, ctx), "ANALYSIS")
        b = self.error(execute(Stage.ANALYZE, ast, ctx), "ANALYSIS")
        self.assertEqual(a, b)
        self.assertNotIn("sensitive-value", canonical_bytes(wire(a)).decode())
        # Existing compile gate rejects unresolved issues; no warning promotion.
        model = small_model()
        model["issues"] = [{"id": "ISSUE-BLOCK", "kind": "CONFLICT", "question": "secret", "blocking": True, "resolution": "OPEN",
                            "subjects": [{"id": model["nodes"][0]["id"], "revision": 1}]}]
        self.error(execute(Stage.ANALYZE, replace(ast, model=Document.of(model)), ctx), "ANALYSIS")

    def test_cancellation_and_operational_timeout(self):
        source, ctx = self.setup_small()
        for c in (Cancellation(True), Cancellation(False, 2)):
            self.error(compile_pipeline(source, replace(ctx, request=replace(ctx.request, cancellation=c))).result, "CANCELLED")
        self.error(compile_pipeline(source, replace(ctx, control=ReferenceControl(cancelled=True))).result, "CANCELLED")
        self.error(compile_pipeline(source, replace(ctx, control=ReferenceControl(elapsed=60_000))).result, "RESOURCE")
        inputs, _ = self.stages(source, ctx)
        for stage in STAGES:
            self.error(execute(stage, inputs[stage], replace(ctx, request=replace(ctx.request, cancellation=Cancellation(True)))), "CANCELLED")

    def test_bounded_input_nodes_depth_work_output_and_manifest(self):
        source, ctx = self.setup_small()
        for field, bound in (("input_bytes", 8), ("output_bytes", 8), ("nodes", 1), ("depth", 1), ("work", 1)):
            with self.subTest(bound=field):
                r = replace(ctx.request, resources=replace(Resources(), **{field: bound}))
                self.error(compile_pipeline(source, replace(ctx, request=r)).result, "RESOURCE")
        self.error(compile_pipeline(source, replace(ctx, request=replace(ctx.request, resources=replace(Resources(), diagnostics=0)))).result, "INPUT")
        self.error(compile_pipeline(source, replace(ctx, request=replace(ctx.request, repository_root="/tmp/absolute"))).result, "INPUT")

    def test_authority_rechecks_cache_and_rejects_forged_admission(self):
        source, ctx = self.setup_small()
        inputs, _ = self.stages(source, ctx)
        self.success(execute(Stage.PROJECT, inputs[Stage.PROJECT], ctx))
        ctx.approval.revoked = True
        self.error(execute(Stage.PROJECT, inputs[Stage.PROJECT], ctx), "APPROVAL")
        ctx.approval.revoked = False
        self.error(execute(Stage.PROJECT, replace(inputs[Stage.PROJECT], admission=Document.of({"approved": True})), ctx), "APPROVAL")
        self.error(execute(Stage.NORMALIZE, inputs[Stage.NORMALIZE], replace(ctx, request=replace(ctx.request, approval_evidence=Document.of({})))), "APPROVAL")

    def test_decision_digest_binding_scope_and_required_choices(self):
        source, ctx = self.setup_small()
        inputs, _ = self.stages(source, ctx)
        self.error(execute(Stage.REALIZE, inputs[Stage.REALIZE], replace(ctx, request=replace(ctx.request, decision_digests=()))), "DECISION")
        bad = replace(ctx.request.decisions[0], origins=(Subject(ctx.request.application, "MISSING", 1),))
        choices = (bad, ctx.request.decisions[1])
        r = replace(ctx.request, decisions=choices, decision_digests=tuple(sorted(fingerprint(d, "decision") for d in choices)))
        self.error(execute(Stage.REALIZE, inputs[Stage.REALIZE], replace(ctx, request=r)), "DECISION")

    def test_projection_cannot_drop_or_modify_semantics(self):
        source, ctx = self.setup_small()
        inputs, _ = self.stages(source, ctx)
        p = inputs[Stage.REALIZE]
        self.error(execute(Stage.REALIZE, replace(p, views=p.views[1:]), ctx), "PROJECTION")
        view = p.views[0]
        obj = view.objects[0]
        wrong = replace(obj, semantic=Document.of({"id": "MISSING"}))
        broken = replace(p, views=(replace(view, objects=(wrong, *view.objects[1:])), *p.views[1:]))
        self.error(execute(Stage.REALIZE, broken, ctx), "PROJECTION")
        broken = replace(p, views=(replace(view, objects=(replace(obj, id="collision"), *view.objects[1:])), *p.views[1:]))
        self.error(execute(Stage.REALIZE, broken, ctx), "PROVENANCE")

    def test_obligations_propagate_and_target_cannot_discharge(self):
        source, ctx = self.setup_small()
        inputs, outputs = self.stages(source, ctx)
        obligations = outputs[Stage.ANALYZE].obligations
        self.assertTrue(obligations)
        for stage in STAGES[3:]:
            self.assertEqual(obligations, outputs[stage].obligations)
        class Dropping(SyntheticTarget):
            def lower(self, realization, request):
                return replace(super().lower(realization, request), obligations=())
        self.error(execute(Stage.LOWER, inputs[Stage.LOWER], replace(ctx, target=Dropping())), "OBLIGATION")
        wrong = replace(inputs[Stage.GENERATE], obligations=())
        self.error(execute(Stage.GENERATE, wrong, ctx), "OBLIGATION")
        changed = replace(obligations[0], status="SATISFIED")
        wrong = replace(inputs[Stage.GENERATE], obligations=(changed, *obligations[1:]))
        self.error(execute(Stage.GENERATE, wrong, ctx), "OBLIGATION")

    def test_target_provenance_and_identity_collisions_rejected(self):
        source, ctx = self.setup_small()
        inputs, _ = self.stages(source, ctx)
        class Collision(SyntheticTarget):
            def lower(self, realization, request):
                result = super().lower(realization, request)
                return replace(result, objects=(result.objects[0],) * len(result.objects))
        self.error(execute(Stage.LOWER, inputs[Stage.LOWER], replace(ctx, target=Collision())), "PROVENANCE")
        origins = (Subject("APP", "SEM", 1),)
        self.assertEqual(derived_id(origins, "Domain"), derived_id((Subject("APP", "SEM", 2),), "Domain"))
        self.assertNotEqual(derived_id(origins, "Domain"), derived_id(origins, "Application"))
        with self.assertRaises(CompilerFault):
            derived_id(origins * 2, "Domain")
        r = inputs[Stage.LOWER]
        self.error(execute(Stage.LOWER, replace(r, objects=r.objects[1:]), ctx), "PROVENANCE")

    def test_artifact_paths_collisions_digest_and_ownership(self):
        source, ctx = self.setup_small()
        plan = self.success(compile_pipeline(source, ctx).result)
        first = plan.artifacts[0]
        for path in ("../escape", "/absolute", "C:/windows", "a\\b", "a//b", "./a", "a/../b", "a/", "a\x00b"):
            with self.subTest(path=path), self.assertRaises(CompilerFault):
                safe_path(path)
        for artifacts in ((first, first), (replace(first, path="a"), replace(first, path="a/b")), (replace(first, content_digest="sha256:" + "0" * 64),)):
            with self.assertRaises(CompilerFault) as caught:
                validate_plan(replace(plan, artifacts=artifacts), (), plan.obligations)
            self.assertEqual("ARTIFACT", caught.exception.code)
        human = ExistingArtifact(first.path, "sha256:" + "0" * 64, Owner.HUMAN)
        self.error(compile_pipeline(source, replace(ctx, inventory=(human,))).result, "OWNERSHIP")
        framework = replace(human, owner=Owner.FRAMEWORK)
        self.error(compile_pipeline(source, replace(ctx, inventory=(framework,))).result, "OWNERSHIP")

    def test_reference_store_atomic_apply_noop_update_and_race(self):
        source, ctx = self.setup_small()
        plan = self.success(compile_pipeline(source, ctx).result)
        store = MemoryArtifactStore()
        store.apply(plan)
        self.assertEqual(len(plan.artifacts), len(store.records))
        repeat = self.success(compile_pipeline(source, replace(ctx, inventory=store.inventory())).result)
        self.assertTrue(all(a.intent == "NO_OP" for a in repeat.artifacts))
        store.apply(repeat)
        with self.assertRaises(CompilerFault):
            store.apply(plan)  # stale create vs now-present inventory, atomic denial
        original = dict(store.records)
        bad = replace(repeat, artifacts=(replace(repeat.artifacts[0], path="../bad"), *repeat.artifacts[1:]))
        with self.assertRaises(CompilerFault):
            store.apply(bad)
        self.assertEqual(original, store.records)
        first = repeat.artifacts[0]
        human = replace(first, owner=Owner.HUMAN)
        human_plan = replace(repeat, artifacts=(human, *repeat.artifacts[1:]))
        inventory = tuple(replace(a, owner=Owner.HUMAN) if a.path == human.path else a for a in store.inventory())
        validate_plan(human_plan, inventory, human_plan.obligations)  # human no-op is safe

    def test_incremental_revision_rename_continuity_and_unrelated_cache_reuse(self):
        source, ctx = self.setup_small()
        before = normalize_candidate(small_model())
        first = compile_pipeline(source, ctx)
        plan = self.success(first.result)
        base = {"sequence": 0, "digest": before["contentDigest"], "journalDigest": "sha256:" + "0" * 64}
        change_plan = prepare(before, change("CHANGE-RENAME", base, [revise(before, "PARAM-A", name="Renamed display label")]))
        after = change_plan["candidate"]
        impact = incremental_impact(before, after, ctx, change_plan["impact"]["semanticIds"])
        self.assertEqual(("PARAM-A",), impact.changed)
        self.assertEqual(("PARAM-A",), impact.closure)
        self.assertEqual(("Domain",), impact.projections)
        source2, ctx2 = fixture_context(authoring(after), cache=ctx.cache)
        next_compilation = compile_pipeline(source2, ctx2)
        next_plan = self.success(next_compilation.result)
        project = next(a for a in next_compilation.stages if a.stage == Stage.PROJECT)
        self.assertEqual(len(small_model()["nodes"]) - 1, project.metrics.cache_hits)
        self.assertEqual(1, project.metrics.cache_misses)
        paths = lambda p: {a.mappings[0].id: a.path for a in p.artifacts}
        self.assertEqual(paths(plan), paths(next_plan))
        self.assertNotEqual(fingerprint(plan), fingerprint(next_plan))
        self.assertEqual((), incremental_impact(before, before, ctx).passes)
        # Changing the root decision invalidates the dependency closure of both parameters.
        root_plan = prepare(before, change("CHANGE-ROOT", base, [revise(before, "DEC-ROOT", name="New root label")]))
        root_impact = incremental_impact(before, root_plan["candidate"], ctx)
        self.assertEqual({n["id"] for n in small_model()["nodes"]}, set(root_impact.closure))
        source3, ctx3 = fixture_context(authoring(root_plan["candidate"]), cache=ctx.cache)
        root_result = compile_pipeline(source3, ctx3)
        self.success(root_result.result)
        self.assertEqual(0, next(a.metrics.cache_hits for a in root_result.stages if a.stage == Stage.PROJECT))

    def test_corrupted_and_rehashed_cache_entries_rejected(self):
        for rehash in (False, True):
            source, ctx = self.setup_small()
            self.success(compile_pipeline(source, ctx).result)
            key, entry = next(iter(ctx.cache.entries.items()))
            modified = replace(entry.value, id="forged")
            ctx.cache.entries[key] = CacheEntry(key, modified, fingerprint(modified) if rehash else entry.digest)
            self.error(compile_pipeline(source, ctx).result, "CACHE")

    def test_declared_inputs_affect_stage_identity_and_cache(self):
        source, ctx = self.setup_small()
        original = compile_pipeline(source, ctx)
        self.success(original.result)
        changed = replace(ctx, request=replace(ctx.request, configuration=Document.of({"profile": "alternate"})))
        result = compile_pipeline(source, changed)
        self.success(result.result)
        self.assertNotEqual(original.stages[0].identity, result.stages[0].identity)
        self.assertNotEqual(original.result.output_digest, result.result.output_digest)
        self.assertEqual(0, next(a.metrics.cache_hits for a in result.stages if a.stage == Stage.PROJECT))

    def test_repeated_pipeline_and_order_insensitive_authoring(self):
        for name, model in {"small": small_model()}.items():
            with self.subTest(domain=name):
                source, ctx = fixture_context(model)
                a = compile_pipeline(source, ctx)
                b = compile_pipeline(source, ctx)
                self.success(a.result)
                self.success(b.result)
                self.assertEqual(a.result.output_digest, b.result.output_digest)
                self.assertTrue(next(x.metrics.cache_hits for x in b.stages if x.stage == Stage.PROJECT))
                shuffled = copy.deepcopy(model)
                shuffled["nodes"].reverse()
                for node in shuffled["nodes"]:
                    node["basis"].reverse()
                    node["origins"].reverse()
                s, c = fixture_context(shuffled)
                d = compile_pipeline(s, c)
                self.success(d.result)
                self.assertEqual(a.result.output_digest, d.result.output_digest)

    def test_ordered_semantic_change_changes_artifact_digest(self):
        source, ctx = self.setup_small()
        a = compile_pipeline(source, ctx)
        model = small_model()
        model["nodes"][0]["data"]["alternatives"].reverse()
        s, c = fixture_context(model)
        b = compile_pipeline(s, c)
        self.success(b.result)
        self.assertNotEqual(a.result.output_digest, b.result.output_digest)

    def test_nondeterministic_adapter_detection(self):
        source, ctx = self.setup_small()
        inputs, _ = self.stages(source, ctx)
        class Flaky(SyntheticTarget):
            count = 0
            def plan(self, target, request):
                self.count += 1
                plan = super().plan(target, request)
                first = replace(plan.artifacts[0], path="reference/run-" + str(self.count) + ".json")
                return replace(plan, artifacts=(first, *plan.artifacts[1:]))
        self.error(execute(Stage.GENERATE, inputs[Stage.GENERATE], replace(ctx, target=Flaky()), repeat=True), "NONDETERMINISM")

    def test_cross_process_cwd_locale_environment_hashseed_and_discovery_order(self):
        code = '''
import json, os
from compiler_fixtures import small_model
from compiler_reference import fixture_context
from compiler_core import compile_pipeline
from compiler_contracts import Success, wire
from canonical_json import canonical_bytes
model = small_model()
# Frontend discovery order differs, yet the semantic snapshot remains equivalent.
if os.environ['ACP_TEST_REVERSE'] == '1':
    model['nodes'].reverse()
source, context = fixture_context(model)
result = compile_pipeline(source, context)
assert isinstance(result.result, Success), result.result
print(canonical_bytes(wire(result.result.output)).hex())
'''
        outputs = []
        for seed, locale in (("1", "C"), ("42", "C.UTF-8"), ("random", "C")):
            with tempfile.TemporaryDirectory() as cwd, tempfile.TemporaryDirectory() as tmp:
                env = {**os.environ, "PYTHONPATH": str(ROOT / "tooling"), "PYTHONHASHSEED": seed,
                       "LC_ALL": locale, "LANG": locale, "TMPDIR": tmp, "ACP_IRRELEVANT": cwd,
                       "ACP_TEST_REVERSE": "1" if seed == "42" else "0"}
                process = subprocess.run([sys.executable, "-c", code], cwd=cwd, env=env,
                                         capture_output=True, text=True, timeout=60)
                self.assertEqual(0, process.returncode, process.stderr)
                outputs.append(process.stdout)
        self.assertEqual(1, len(set(outputs)))

    def test_source_maps_remain_sidecars_and_reach_artifacts(self):
        source, ctx = self.setup_small()
        source = replace(source, source_map=Document.of({"PARAM-A": "models/source.json#PARAM-A"}))
        ctx = replace(ctx, request=replace(ctx.request, source_digest=fingerprint(source, "source")))
        compilation = compile_pipeline(source, ctx)
        plan = self.success(compilation.result)
        artifact = next(a for a in plan.artifacts if a.mappings[0].id == "PARAM-A")
        self.assertEqual(("models/source.json#PARAM-A",), artifact.source_locations)
        self.assertEqual(normalize_candidate(small_model())["contentDigest"], ctx.request.snapshot_digest)
        bad = replace(source, source_map=Document.of({"PARAM-A": "/home/host/private"}))
        bad_ctx = replace(ctx, request=replace(ctx.request, source_digest=fingerprint(bad, "source")))
        self.error(execute(Stage.INGEST, bad, bad_ctx), "INPUT")

    def test_declared_change_migration_obligations_remain_outstanding(self):
        from compiler_contracts import Obligation
        source, ctx = self.setup_small()
        obligation = Obligation("fixture-migration", "migration", (Subject(ctx.request.application, "PARAM-A", 1),))
        request = replace(ctx.request, change_plan_digest="sha256:" + "1" * 64, change_obligations=(obligation,))
        compilation = compile_pipeline(source, replace(ctx, request=request))
        plan = self.success(compilation.result)
        self.assertIn(obligation, plan.obligations)
        self.assertIn(obligation, compilation.audit.obligations)
        self.error(compile_pipeline(source, replace(ctx, request=replace(request, change_plan_digest=None))).result, "OBLIGATION")

    def test_no_ai_storage_or_environment_port_required(self):
        source, ctx = self.setup_small()
        self.assertFalse(hasattr(ctx, "ai"))
        self.assertFalse(hasattr(ctx, "secret"))
        self.assertFalse(hasattr(ctx, "environment"))
        self.success(compile_pipeline(source, ctx).result)
        core = (ROOT / "tooling/compiler_core.py").read_text()
        for forbidden in ("import sqlite", "import os", "import random", "import time", "import socket", "import requests"):
            self.assertNotIn(forbidden, core)

    def test_missing_ports_and_invalid_range_fail_closed(self):
        source, ctx = self.setup_small()
        self.error(compile_pipeline(source, replace(ctx, approval=None)).result, "APPROVAL")
        self.error(compile_pipeline(source, replace(ctx, frontend=None)).result, "PORT")
        request = replace(ctx.request, start=Stage.GENERATE, end=Stage.INGEST)
        self.error(compile_pipeline(source, replace(ctx, request=request)).result, "INPUT")
        inputs, _ = self.stages(source, ctx)
        bad = replace(inputs[Stage.ANALYZE], source_map=Document.of({"PARAM-A": "/private/source"}))
        self.error(execute(Stage.ANALYZE, bad, ctx), "INPUT")

    def test_every_documented_diagnostic_has_executable_path(self):
        # Coverage links the finite catalogue to explicit regression assertions above.
        source = Path(__file__).read_text()
        for code in MESSAGES:
            self.assertIn('"' + code + '"', source)


if __name__ == "__main__":
    unittest.main()
