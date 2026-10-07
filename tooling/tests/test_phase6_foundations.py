"""Phase 6 boundary tests; these do not certify complete target support."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compiler_contracts import Artifact, ArtifactPlan, Document, Owner, Provenance, Stage, Subject, fingerprint
from compiler_core import CompilerFault
from filesystem_artifacts import ApprovedAICandidate, FilesystemArtifactStore, StoreConflict
from target_worker import ROOT, PROFILE, ProductionTarget, TargetWorker, TargetWorkerError
from target_provenance import inspect_mapping


def artifact(path="backend/example.txt", text="initial\n", owner=Owner.COMPILER, prior=None):
    content = Document.of({"encoding": "UTF-8", "text": text})
    digest = fingerprint(content, "artifact-content")
    origins = (Subject("test", "ENTITY", 1),)
    prov = Provenance(origins, Stage.GENERATE, "compiler/0.1.0", "pipeline/0.1.0", ("bound-input",))
    return Artifact(path, "TEST", content, digest, owner, prov, origins,
                    "CREATE" if prior is None else "NO_OP" if prior.digest == digest else "UPDATE",
                    None if prior is None else prior.digest, "COMPARE_AND_SWAP", ("source-integrity",))


class ArtifactStoreTests(unittest.TestCase):
    def test_staging_failure_keeps_old_tree_intact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "application"
            store = FilesystemArtifactStore(root)
            store.apply(ArtifactPlan((artifact(),), ()))
            prior = store.inventory()[0]
            before_metadata = (root / store.META).read_bytes()
            original = Path.write_bytes
            def fail_second(path, data):
                if path.name == "second.txt":
                    raise OSError("injected staging failure")
                return original(path, data)
            with patch.object(Path, "write_bytes", fail_second), self.assertRaises(OSError):
                store.apply(ArtifactPlan((artifact(text="new\n", prior=prior), artifact("second.txt")), ()))
            self.assertEqual("initial\n", (root / "backend/example.txt").read_text())
            self.assertFalse((root / "second.txt").exists())
            self.assertEqual(before_metadata, (root / store.META).read_bytes())

    def test_explicit_build_caches_are_discarded_without_following_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "application"
            store = FilesystemArtifactStore(root, ephemeral_build_scopes=("frontend/node_modules",))
            store.apply(ArtifactPlan((artifact(),), ()))
            cache = root / "frontend/node_modules"
            cache.mkdir(parents=True)
            (cache / "outside").symlink_to("/etc")
            store.apply(ArtifactPlan((artifact("new.txt"),), ()))
            self.assertFalse(cache.exists())
            with self.assertRaises(StoreConflict):
                store.apply(ArtifactPlan((artifact("frontend/node_modules/injected"),), ()))

    def test_atomic_cas_and_manual_edit_rejection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "application"
            store = FilesystemArtifactStore(root)
            first = artifact()
            store.apply(ArtifactPlan((first,), ()))
            prior = store.inventory()[0]
            store.apply(ArtifactPlan((artifact(text="updated\n", prior=prior),), ()))
            self.assertEqual("updated\n", (root / first.path).read_text())
            with self.assertRaises(CompilerFault):
                store.apply(ArtifactPlan((artifact(text="stale\n", prior=prior),), ()))
            (root / first.path).write_text("manual\n")
            with self.assertRaises(StoreConflict):
                store.inventory()

    def test_whole_plan_failure_publishes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "application"
            store = FilesystemArtifactStore(root)
            for bad in ["../escape", "/absolute", "a/../b", "a//b", "a\\b", "a:b"]:
                with self.subTest(path=bad), self.assertRaises(CompilerFault):
                    store.apply(ArtifactPlan((artifact(), artifact(bad)), ()))
                self.assertFalse(root.exists())
            for rows in [(artifact("a"), artifact("a/b")), (artifact(), artifact())]:
                with self.assertRaises(CompilerFault): store.apply(ArtifactPlan(rows, ()))
                self.assertFalse(root.exists())

    def test_symlinks_unknown_files_and_prefix_collisions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "application"
            outside = Path(temporary) / "outside"
            outside.mkdir()
            root.symlink_to(outside)
            with self.assertRaises(StoreConflict): FilesystemArtifactStore(root)
            root.unlink(); root.mkdir()
            (root / "escape").symlink_to(outside)
            store = FilesystemArtifactStore(root)
            with self.assertRaises(StoreConflict): store.apply(ArtifactPlan((artifact(),), ()))
            (root / "escape").unlink()
            (root / "unknown").write_text("unowned")
            with self.assertRaises(StoreConflict): store.inventory()

    def test_framework_upgrades_require_explicit_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = FilesystemArtifactStore(Path(temporary) / "application")
            first = artifact(owner=Owner.FRAMEWORK)
            store.apply(ArtifactPlan((first,), ()))
            update = artifact(text="upgrade\n", owner=Owner.FRAMEWORK, prior=store.inventory()[0])
            with self.assertRaises(StoreConflict): store.apply(ArtifactPlan((update,), ()))
            store.apply(ArtifactPlan((update,), ()), framework_upgrades=(first.path,))

    def test_ai_requires_bound_provenance_and_host_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = FilesystemArtifactStore(Path(temporary) / "application")
            candidate = artifact(owner=Owner.AI)
            plan = ArtifactPlan((candidate,), ())
            with self.assertRaises(StoreConflict): store.apply(plan)
            with self.assertRaises(StoreConflict): store.apply(plan, ai_approvals={candidate.path: candidate.content_digest})
            approval = ApprovedAICandidate(candidate.content_digest, Document.of({
                "provider": "test-only", "model": "test-model", "inputDigest": "sha256:input", "outputDigest": candidate.content_digest,
                "approvalPolicy": "explicit-candidate-review/1", "approvalEvidence": "host-fixture-approval"}))
            store.apply(plan, ai_approvals={candidate.path: approval})

    def test_human_extension_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "application"
            store = FilesystemArtifactStore(root)
            path = "frontend/src/extensions/custom.ts"
            store.apply(ArtifactPlan((artifact(path),), ()))
            store.adopt_human(path)
            (root / path).write_text("human edited\n")
            prior = store.inventory()[0]
            with self.assertRaises(CompilerFault): store.apply(ArtifactPlan((artifact(path, owner=Owner.HUMAN, prior=prior),), ()))
            store.apply(ArtifactPlan((artifact("other.txt"),), ()))
            self.assertEqual("human edited\n", (root / path).read_text())


class WorkerTests(unittest.TestCase):
    def test_multi_artifact_pipeline_preserves_host_authority(self):
        from compiler_contracts import Success, Failure
        from compiler_core import compile_pipeline
        from compiler_fixtures import small_model
        from compiler_reference import FixtureApproval, fixture_context
        source, context = fixture_context(small_model())
        target = ProductionTarget()
        decisions = tuple(replace(d, choice=Document.of({"choice": PROFILE["decisions"][d.role]})) for d in context.request.decisions)
        request = replace(context.request, target=target.identity, generator=target.generator,
                          required_capabilities=target.capabilities, decisions=decisions,
                          decision_digests=tuple(sorted(fingerprint(d, "decision") for d in decisions)))
        snapshot = context.snapshots.read_exact(request.application, request.snapshot_digest)
        authority = FixtureApproval((snapshot,), decisions, request.approval_evidence)
        context = replace(context, request=request, approval=authority, target=target)
        result = compile_pipeline(source, context).result
        self.assertIsInstance(result, Success, getattr(result, "diagnostics", ()))
        plan = result.output
        self.assertGreater(len(plan.artifacts), len(small_model()["nodes"]))
        self.assertTrue(all(o.status == "OUTSTANDING" for o in plan.obligations))
        with tempfile.TemporaryDirectory() as temporary:
            store = FilesystemArtifactStore(Path(temporary) / "application")
            store.apply(plan)
            self.assertTrue((store.root / "backend/pom.xml").exists())
            extension = "frontend/src/extensions/identity.ts"
            store.adopt_human(extension)
            (store.root / extension).write_text("// human-owned OIDC integration\n")
            regeneration = compile_pipeline(source, replace(context, inventory=store.inventory())).result
            self.assertIsInstance(regeneration, Success, getattr(regeneration, "diagnostics", ()))
            self.assertNotIn(extension, {a.path for a in regeneration.output.artifacts})
            store.apply(regeneration.output)
            self.assertEqual("// human-owned OIDC integration\n", (store.root / extension).read_text())
            sidecars = json.loads((store.root / "acp/provenance.json").read_text())["artifacts"]
            mapping = next(m for m in sidecars if m["artifact"] == "backend/pom.xml")
            self.assertEqual("CURRENT", inspect_mapping(store.root, mapping)["status"])
            self.assertEqual("STALE_SEMANTICS", inspect_mapping(store.root, mapping, semantic_revisions={})["status"])
            (store.root / mapping["artifact"]).write_text("manual formatting\n")
            inspected = inspect_mapping(store.root, mapping)
            self.assertEqual("STALE_ARTIFACT", inspected["status"])
            self.assertEqual([], inspected["locations"])
        authority.revoked = True
        denied = compile_pipeline(source, context).result
        self.assertIsInstance(denied, Failure)
        self.assertFalse(hasattr(denied, "output"))

    def test_handshake_manifest_and_unknown_versions(self):
        worker = TargetWorker()
        self.assertEqual(PROFILE["protocol"], worker.call("handshake", {})["protocol"])
        manifest = worker.call("manifest", {})
        self.assertEqual(PROFILE["profile"], manifest["profile"])
        self.assertEqual("UNSUPPORTED", manifest["capabilities"]["File/0.2.0"]["status"])
        worker.protocol = "acp-target-worker/999"
        with self.assertRaisesRegex(TargetWorkerError, "PROTOCOL"): worker.call("handshake", {})

    def test_project_model_requires_negotiated_project_capability(self):
        from compiler_contracts import Failure
        from compiler_core import compile_pipeline
        from compiler_fixtures import small_model
        from compiler_reference import SyntheticTarget, fixture_context
        class ForgedTarget(SyntheticTarget):
            def lower(self, realization, request):
                return replace(super().lower(realization, request), target_model=Document.of({"forged": True}))
        source, context = fixture_context(small_model())
        result = compile_pipeline(source, replace(context, target=ForgedTarget())).result
        self.assertIsInstance(result, Failure)
        self.assertEqual("ACP-COMPILER-CAPABILITY", result.diagnostics[0].code)

    def test_capability_and_decision_fail_closed(self):
        worker = TargetWorker()
        for required, decisions in [(["Money/999"], PROFILE["decisions"]), ([], {}), (["File/0.2.0"], PROFILE["decisions"])]:
            with self.assertRaises(TargetWorkerError): worker.call("negotiate", {"nodes": [], "required": required, "decisions": decisions})

    def test_complete_domains_explicitly_block_pending_capabilities(self):
        worker = TargetWorker()
        for domain in ("payment", "case-management"):
            nodes = json.loads((ROOT.parents[1] / "test-corpus/canonical" / (domain + ".json")).read_text())["content"]["nodes"]
            with self.assertRaisesRegex(TargetWorkerError, "UNSUPPORTED:Job/0.2.0"):
                worker.call("lower", {"nodes": nodes, "required": [], "decisions": PROFILE["decisions"]})

    def test_repeat_workers_cwd_locale_and_environment(self):
        worker = TargetWorker()
        expected = worker.call("manifest", {})
        with tempfile.TemporaryDirectory() as temporary:
            original = os.environ.get("ACP_IRRELEVANT_TEST")
            try:
                os.environ["ACP_IRRELEVANT_TEST"] = "different"
                for _ in range(3): self.assertEqual(expected, worker.call("manifest", {}, cwd=temporary))
            finally:
                if original is None: os.environ.pop("ACP_IRRELEVANT_TEST", None)
                else: os.environ["ACP_IRRELEVANT_TEST"] = original

    def test_kernel_sandbox_denies_files_and_network(self):
        source = f'''import sys, os, socket, ctypes
sys.path.insert(0, {str(ROOT / 'worker')!r})
from main import sandbox
sandbox()
for operation in [lambda: os.open('/etc/hostname', os.O_RDONLY), lambda: socket.socket(), lambda: os.getrandom(8)]:
 try: operation()
 except PermissionError: pass
 else: raise RuntimeError('sandbox escape')
print('confined')
'''
        result = subprocess.run([sys.executable, "-I", "-B", "-c", source], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("confined\n", result.stdout)


if __name__ == "__main__":
    unittest.main()
