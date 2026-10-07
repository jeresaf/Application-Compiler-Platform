"""Target migration planner safety; fixture authority is explicitly test only."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_json import load
from change_fixtures import evolution_change
from changes import prepare, seal
from compiler_contracts import Document, fingerprint
from target_migrations import MigrationBlocked, plan_upgrade
from validate import ROOT


class FixtureAcceptedHistory:
    def __init__(self, plan, bindings):
        self.plan, self.bindings = plan, bindings
        self.revoked = False

    def read_accepted_plan(self, digest):
        if self.revoked or digest != self.plan.read()["planDigest"]:
            raise PermissionError()
        return self.plan

    def read_approved_bindings(self, digest, binding_digest):
        self.read_accepted_plan(digest)
        if binding_digest != fingerprint(self.bindings, "migration-bindings"):
            raise PermissionError()
        return self.bindings


class MigrationPlannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = Document.of(load(ROOT / "test-corpus/canonical/payment.json"))
        snapshot = cls.before.read()
        base = {"sequence": 0, "digest": snapshot["contentDigest"], "journalDigest": "sha256:" + "0" * 64}
        cls.required = Document.of(prepare(snapshot, evolution_change(snapshot, base, "required-field")))
        cls.rename = Document.of(prepare(snapshot, evolution_change(snapshot, base, "stable-id-rename")))

    def test_required_field_consumes_explicit_approved_backfill(self):
        bindings = Document.of({"requiredFieldBackfills": {"EVOLUTION-required-field": "reviewed ' value"}})
        history = FixtureAcceptedHistory(self.required, bindings)
        after = Document.of(self.required.read()["candidate"])
        result = plan_upgrade(self.before, after, self.required, bindings, history).read()
        self.assertEqual(["EXPAND", "BACKFILL", "VERIFY", "SWITCH"], result["changes"][0]["phases"])
        self.assertIn("reviewed '' value", result["sql"])
        self.assertIn("SET NOT NULL", result["sql"])
        self.assertNotIn("DROP", result["sql"])
        self.assertEqual("NOT_CLAIMED", result["productionRollback"])

    def test_missing_backfill_unaccepted_history_and_stale_plan_block(self):
        bindings = Document.of({})
        history = FixtureAcceptedHistory(self.required, bindings)
        after = Document.of(self.required.read()["candidate"])
        with self.assertRaisesRegex(MigrationBlocked, "REQUIRED_BACKFILL_BINDING"):
            plan_upgrade(self.before, after, self.required, bindings, history)
        history.revoked = True
        with self.assertRaisesRegex(MigrationBlocked, "UNACCEPTED_HISTORY"):
            plan_upgrade(self.before, after, self.required, bindings, history)
        with self.assertRaisesRegex(MigrationBlocked, "SNAPSHOT_BINDING"):
            plan_upgrade(self.before, self.before, self.required, bindings, history)

    def test_identity_preserving_display_rename_needs_no_ddl(self):
        bindings = Document.of({})
        result = plan_upgrade(self.before, Document.of(self.rename.read()["candidate"]), self.rename,
                              bindings, FixtureAcceptedHistory(self.rename, bindings)).read()
        self.assertEqual("", result["sql"])
        self.assertNotEqual(result["previousSnapshot"], result["nextSnapshot"])

    def test_tampering_and_destructive_contract_are_not_guessed(self):
        bindings = Document.of({})
        changed = self.rename.read()
        changed["change"]["intent"] = "tampered"
        with self.assertRaisesRegex(MigrationBlocked, "PHASE3_PLAN_DIGEST"):
            plan_upgrade(self.before, Document.of(changed["candidate"]), Document.of(changed), bindings,
                         FixtureAcceptedHistory(Document.of(changed), bindings))
        changed = self.rename.read()
        changed["tombstones"] = [{"id": "destructive-review-required"}]
        changed = seal({k: v for k, v in changed.items() if k != "planDigest"})
        plan = Document.of(changed)
        with self.assertRaisesRegex(MigrationBlocked, "DESTRUCTIVE_CONTRACT_UNSUPPORTED"):
            plan_upgrade(self.before, Document.of(changed["candidate"]), plan, bindings, FixtureAcceptedHistory(plan, bindings))


if __name__ == "__main__":
    unittest.main()
