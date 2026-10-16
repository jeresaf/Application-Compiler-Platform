"""Offline Wave 1 tests. History/data authority and artifact trace are test only."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
from canonical_json import load
from change_fixtures import evolution_change
from changes import prepare
from compiler_contracts import Artifact, ArtifactPlan, Document, Owner, Provenance, Stage, Subject, fingerprint
from compiler_core import CompilerFault
from filesystem_artifacts import FilesystemArtifactStore, StoreConflict, byte_digest
from target_migrations import MigrationBlocked, identifier, plan_upgrade
from target_provenance import inspect_mapping
from target_release import verify_production_upgrade
from test_canonical03_migrations import fixture
from test_target_migrations import FixtureAcceptedHistory


def cross_version(value="e\u0301\x00🦋'", *, domain="payment"):
    before = load(Path(__file__).resolve().parents[2] / f"test-corpus/execution-v03/{domain}-canonical.json")
    # Canonical 0.3 requires the explicit deterministic semantic revisions,
    # not just a schemaVersion relabel. Clone the historical proposal as inert
    # fixture data and add a TEST-ONLY field/backfill; no real approval is issued.
    proposal = load(Path(__file__).resolve().parents[2] / f"test-corpus/deterministic-v04/{domain}-change.json")
    addition = evolution_change(before, proposal["base"], "required-field")
    proposal["id"] = "TEST-CORE-W1-UPGRADE"
    proposal["intent"] = "TEST ONLY canonical 0.2 to 0.3 storage witness"
    proposal["operations"].extend(addition["operations"])
    proposal["migration"] = addition["migration"]
    plan = Document.of(prepare(before, proposal))
    bindings = Document.of({"requiredFieldBackfills": {"EVOLUTION-required-field": value}})
    return Document.of(before), Document.of(plan.read()["candidate"]), plan, bindings, FixtureAcceptedHistory(plan, bindings)


def migration_artifact(args, text=None, prior=None, owner=Owner.COMPILER, path="backend/migration.sql"):
    migration = plan_upgrade(*args).read()
    field = next(n for n in args[1].read()["content"]["nodes"] if n["id"] == "EVOLUTION-required-field")
    origin = Subject(args[1].read()["content"]["applicationId"], field["id"], field["revision"])
    content = Document.of({"encoding": "UTF-8", "text": migration["sql"] if text is None else text})
    digest = fingerprint(content, "artifact-content")
    provenance = Provenance((origin,), Stage.GENERATE, "compiler/0.1.0", "pipeline/0.1.0",
        (migration["previousSnapshot"], migration["nextSnapshot"], migration["phase3PlanDigest"], migration["bindingsDigest"]))
    return Artifact(path, "TEST_MIGRATION_TRACE", content, digest, owner, provenance, (origin,),
        "CREATE" if prior is None else "NO_OP" if digest == prior.digest else "UPDATE",
        None if prior is None else prior.digest, "COMPARE_AND_SWAP",
        ("test_binary_property_to_migration_artifact_trace",))


class CoreWave1Tests(unittest.TestCase):
    def test_existing_storage_must_be_present_and_bytea_before_expand(self):
        args = fixture()
        sql = plan_upgrade(*args).read()["sql"]
        guard = sql.splitlines()[0]
        # EXISTS(udt_name <> bytea) wrongly succeeds when a column is missing.
        self.assertIn("IF NOT EXISTS (SELECT 1 FROM information_schema.columns", guard)
        self.assertIn("udt_name='bytea'", guard)
        self.assertIn("ACP_INCOMPATIBLE_STORAGE_REPRESENTATION", guard)
        self.assertLess(sql.index("ACP_INCOMPATIBLE_STORAGE_REPRESENTATION"), sql.index("ADD COLUMN"))
        self.assertNotIn("::bytea", sql)  # No inferred conversion of legacy text.
        nodes = {n["id"]: n for n in args[0].read()["content"]["nodes"]}
        persistent = [n for n in nodes.values() if n["kind"] == "Field"
            and n["data"]["type"]["kind"] == "String"
            and nodes[n["data"]["owner"]["id"]]["kind"] == "Entity"]
        self.assertEqual(len(persistent), sql.count("information_schema.columns"))
        for node in nodes.values():
            if node["kind"] == "Field" and nodes[node["data"]["owner"]["id"]]["kind"] == "ValueObject":
                self.assertNotIn(identifier(node["data"]["owner"]["id"], "e"), sql)

    def test_canonical02_to03_preserves_exact_binary_backfill(self):
        for value in ("e\u0301\x00🦋'", "", "'\\n"):
            with self.subTest(value=value):
                args = cross_version(value)
                result = plan_upgrade(*args).read()
                self.assertEqual("0.2.0", args[0].read()["content"]["schemaVersion"])
                self.assertEqual("0.3.0", args[1].read()["content"]["schemaVersion"])
                column = identifier("EVOLUTION-required-field", "f")
                self.assertIn(column + " bytea;", result["sql"])
                self.assertNotIn(column + " text", result["sql"])
                self.assertIn("decode('" + value.encode("utf-8").hex() + "','hex')", result["sql"])
                self.assertIn("SET NOT NULL", result["sql"])
                self.assertNotIn("DEFAULT", result["sql"])
                self.assertEqual(["EXPAND", "BACKFILL", "VERIFY", "SWITCH"], result["changes"][0]["phases"])

    def test_binary_backfill_wrong_type_and_missing_authority_rejected(self):
        with self.assertRaisesRegex(MigrationBlocked, "BACKFILL_TYPE"):
            plan_upgrade(*fixture(value=False))
        args = list(cross_version()); args[-1].revoked = True
        with self.assertRaisesRegex(MigrationBlocked, "UNACCEPTED_HISTORY"):
            plan_upgrade(*args)
        args = list(cross_version()); args[3] = Document.of({"requiredFieldBackfills": {}})
        with self.assertRaisesRegex(MigrationBlocked, "UNAPPROVED_DATA_BINDINGS"):
            plan_upgrade(*args)

    def test_boolean_and_presence_storage_contract_is_preserved(self):
        sql = plan_upgrade(*fixture(value=True, typ={"kind": "Boolean"})).read()["sql"]
        self.assertIn(identifier("EVOLUTION-required-field", "f") + " boolean;", sql)
        self.assertIn("=TRUE WHERE", sql)
        sql = plan_upgrade(*fixture(optional=True, nullable=True)).read()["sql"]
        self.assertIn("boolean NOT NULL DEFAULT false", sql)
        self.assertIn("ADD CHECK", sql)
        self.assertNotIn("SET NOT NULL", sql)

    def test_generator_upgrade_preserves_human_file_and_rejects_ai_candidate(self):
        args = cross_version()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "application"
            store = FilesystemArtifactStore(root)
            first = migration_artifact(args, text="-- predecessor migration\n")
            manual = migration_artifact(args, text="manual extension\n", path="frontend/src/extensions/manual.txt")
            store.apply(ArtifactPlan((first, manual), ()))
            store.adopt_human(manual.path)
            (root / manual.path).write_text("human-maintained extension\n")
            inventory = {a.path: a for a in store.inventory()}
            updated = migration_artifact(args, prior=inventory[first.path])
            keep = migration_artifact(args, text=(root / manual.path).read_text(),
                prior=inventory[manual.path], owner=Owner.HUMAN, path=manual.path)
            store.apply(ArtifactPlan((updated, keep), ()))
            self.assertEqual(updated.content.read()["text"], (root / first.path).read_text())
            self.assertEqual("human-maintained extension\n", (root / manual.path).read_text())
            inventory = {a.path: a for a in store.inventory()}
            forbidden = migration_artifact(args, text="overwrite\n", prior=inventory[manual.path],
                owner=Owner.HUMAN, path=manual.path)
            with self.assertRaises(CompilerFault):
                store.apply(ArtifactPlan((forbidden,), ()))
            ai = migration_artifact(args, owner=Owner.AI, path="backend/ai.sql")
            with self.assertRaisesRegex(StoreConflict, "AI_APPROVAL_REQUIRED"):
                store.apply(ArtifactPlan((ai,), ()))
            self.assertFalse((root / ai.path).exists())
            self.assertEqual("human-maintained extension\n", (root / manual.path).read_text())

    def test_binary_property_to_migration_artifact_trace(self):
        args = cross_version(); item = migration_artifact(args)
        field = next(n for n in args[1].read()["content"]["nodes"] if n["id"] == "EVOLUTION-required-field")
        nodes = {n["id"]: n for n in args[1].read()["content"]["nodes"]}
        self.assertTrue(any(nodes[r["id"]]["kind"] == "Requirement" for r in field["basis"]))
        self.assertEqual((field["id"], field["revision"]), (item.mappings[0].id, item.mappings[0].revision))
        self.assertEqual(item.mappings, item.provenance.origins)
        self.assertIn(args[2].read()["planDigest"], item.provenance.inputs)
        self.assertIn(identifier(field["id"], "f") + " bytea;", item.content.read()["text"])
        self.assertEqual((self._testMethodName,), item.verification)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "application"
            FilesystemArtifactStore(root).apply(ArtifactPlan((item,), ()))
            mapping = {"artifact": item.path, "artifactDigest": byte_digest((root / item.path).read_bytes()),
                "origins": [{"id": field["id"], "revision": field["revision"]}],
                "locations": [{"line": next(i for i, s in enumerate(item.content.read()["text"].splitlines(), 1)
                    if identifier(field["id"], "f") + " bytea;" in s)}], "locationConfidence": "EXACT_TEST_FIXTURE"}
            self.assertEqual("CURRENT", inspect_mapping(root, mapping, semantic_revisions={field["id"]: field["revision"]})["status"])
            self.assertEqual("STALE_SEMANTICS", inspect_mapping(root, mapping, semantic_revisions={field["id"]: field["revision"]+1})["status"])
            (root / item.path).write_text("tampered\n")
            self.assertEqual("STALE_ARTIFACT", inspect_mapping(root, mapping)["status"])

    def test_policy_c_still_rejects_production01(self):
        for old in ("0.2.0", "0.3.0", "0.4.0"):
            self.assertEqual("C", verify_production_upgrade("acp-spring-vue-postgres/" + old,
                "acp-spring-vue-postgres/0.5.0")["policy"])
        with self.assertRaisesRegex(ValueError, "PRODUCTION_UPGRADE_OUTSIDE_WINDOW"):
            verify_production_upgrade("acp-spring-vue-postgres/0.1.0", "acp-spring-vue-postgres/0.5.0")


if __name__ == "__main__":
    unittest.main()
