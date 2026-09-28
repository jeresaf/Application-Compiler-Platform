import concurrent.futures
from contextlib import closing
import copy
import json
import os
from pathlib import Path
import random
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_fixtures import synthetic_approved
from canonical_json import canonical_bytes, load
from canonical_ir import validate_snapshot
from change_contract import build_schema
from change_fixtures import change, revise, migration, evolution_change, STEPS, vectors
from changes import ChangeError, SCHEMA, SHAPES, fingerprint, genesis, index, prepare, request
from history_repository import HistoryRepository
from reference_authority import ReferenceAuthority
from reference_models import models
from validate import ROOT


def authority(application="APP-HISTORY"):
    scopes = [application + ":" + s for s in ("SEMANTIC", "SECURITY", "MIGRATION", "IRREVERSIBLE", "LOCKED_DECISION")]
    return ReferenceAuthority(b"synthetic-test-key-not-production" * 2,
        {"author-session": "author", "reviewer-session": "reviewer", "limited-session": "limited"},
        {"author": scopes, "reviewer": scopes, "limited": [application + ":SEMANTIC"]})


def small_source():
    nodes = [{"id": id, "revision": 1, "kind": "Fact", "name": id, "lifecycle": "APPROVED", "steward": "fixture",
        "origins": [{"source": "fixture", "locator": id, "actor": "fixture", "actorType": "HUMAN"}], "basis": [],
        "data": {"statement": "Synthetic " + id, "evidence": "fixture-only"}} for id in ("FACT-A", "FACT-B")]
    return synthetic_approved({"modelVersion": "0.2.0", "applicationId": "APP-HISTORY", "snapshotId": "SOURCE-1",
                               "nodes": nodes, "approvals": [], "issues": []})


class ChangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "history.sqlite"
        self.repo = HistoryRepository(self.path)
        self.auth = authority()
        self.now = 1000
        self.initial = genesis(small_source(), "author")
        self.repo.bootstrap(self.initial, self.auth.issue("reviewer-session", request(self.initial), self.now),
                            self.auth, self.now, "author-session")

    def assert_error(self, code, fn, *args, **kwargs):
        with self.assertRaises(ChangeError) as caught:
            fn(*args, **kwargs)
        self.assertEqual("ACP-CHANGE-" + code, caught.exception.code)

    def propose(self, id="CHANGE-1", target="FACT-A", name="Renamed", **kwargs):
        return self.repo.propose(change(id, self.repo.head(), [revise(self.repo.snapshot(), target, name=name)], **kwargs),
                                 self.auth, "author-session")

    def approve(self, plan, repo=None, auth=None, ttl=300):
        repo, auth = repo or self.repo, auth or self.auth
        id = plan["change"]["id"]
        repo.review(id, auth, "author-session")
        proof = auth.issue("reviewer-session", request(plan), self.now, ttl)
        repo.approve(id, proof, auth, self.now)
        return proof

    def test_schema_and_atomic_rename_history_lookup(self):
        SHAPES.check_schema(SCHEMA)
        self.assertEqual(build_schema(), SCHEMA)
        before = self.repo.snapshot()
        plan = self.propose()
        self.assertEqual(before, self.repo.snapshot())
        self.assertEqual("PROPOSED", self.repo.proposal("CHANGE-1")["state"])
        self.approve(plan)
        head = self.repo.apply("CHANGE-1", "retry-1", self.auth, self.now)
        self.assertEqual(1, head["sequence"])
        self.assertEqual("FACT-A", self.repo.revision("FACT-A", 2)["id"])
        self.assertEqual("Renamed", self.repo.revision("FACT-A", 2)["name"])
        self.assertEqual("FACT-A", self.repo.revision("FACT-A", 1)["name"])
        self.assertEqual(before, self.repo.snapshot(0))
        self.assertEqual(self.repo.snapshot(), self.repo.snapshot(digest_value=head["digest"]))
        self.assertEqual(2, self.repo.audit(head)["entries"])
        self.assertIn("CHANGE-1", self.repo.provenance("FACT-A", 2)["changes"])
        reopened = HistoryRepository(self.path)
        self.assertEqual(head, reopened.head())

    def test_stale_base_and_stale_read_set(self):
        a, b = self.propose("CHANGE-A"), self.propose("CHANGE-B", "FACT-B")
        self.approve(a)
        self.approve(b)
        self.repo.apply("CHANGE-A", "retry-a", self.auth, self.now)
        self.assert_error("STALE_BASE", self.repo.apply, "CHANGE-B", "retry-b", self.auth, self.now)
        c = self.propose("CHANGE-C", "FACT-B", "Third")
        self.approve(c)
        rebased = self.repo.rebase("CHANGE-B", "CHANGE-B-REBASE", self.auth, "author-session")
        self.approve(rebased)
        self.repo.apply("CHANGE-B-REBASE", "retry-br", self.auth, self.now)
        self.assert_error("READSET", self.repo.apply, "CHANGE-C", "retry-c", self.auth, self.now)

    def test_declared_stale_reads_and_exact_base_binding(self):
        c = change("CHANGE-BAD", self.repo.head(), [revise(self.repo.snapshot(), "FACT-A", name="Changed")])
        c["reads"] = [{"id": "FACT-B", "revision": 9}]
        self.assert_error("READSET", self.repo.propose, c, self.auth, "author-session")
        c["reads"] = []
        c["base"]["journalDigest"] = "sha256:" + "0" * 64
        self.assert_error("BASE", self.repo.propose, c, self.auth, "author-session")

    def test_independent_rebase_requires_new_approval(self):
        a, b = self.propose("CHANGE-A"), self.propose("CHANGE-B", "FACT-B")
        old_proof = self.approve(b)
        self.approve(a)
        self.repo.apply("CHANGE-A", "retry-a", self.auth, self.now)
        rebased = self.repo.rebase("CHANGE-B", "CHANGE-B2", self.auth, "author-session")
        self.assertNotEqual(b["planDigest"], rebased["planDigest"])
        self.repo.review("CHANGE-B2", self.auth, "author-session")
        self.assert_error("AUTHORITY", self.repo.approve, "CHANGE-B2", old_proof, self.auth, self.now)
        proof = self.auth.issue("reviewer-session", request(rebased), self.now)
        self.repo.approve("CHANGE-B2", proof, self.auth, self.now)
        self.repo.apply("CHANGE-B2", "retry-b", self.auth, self.now)
        self.assertEqual(2, self.repo.head()["sequence"])

    def test_conflicting_rebase_is_a_persisted_merge_proposal(self):
        a, b = self.propose("CHANGE-A"), self.propose("CHANGE-B", name="Conflicting")
        self.approve(a)
        self.repo.apply("CHANGE-A", "retry-a", self.auth, self.now)
        merge = self.repo.rebase("CHANGE-B", "IGNORED", self.auth, "author-session")
        self.assertEqual("MERGE_REQUIRED", merge["kind"])
        self.assertIn("FACT-A", merge["conflicts"])
        self.assertFalse(merge["automaticApply"])
        self.assertEqual("MERGE_REQUIRED", self.repo.proposal("CHANGE-B")["state"])
        self.assertEqual(1, self.repo.head()["sequence"])
        resolution = change("CHANGE-MERGED", self.repo.head(), [revise(self.repo.snapshot(), "FACT-A", name="Reviewed resolution")])
        resolution["parents"] = merge["parents"]
        resolved = self.repo.propose(resolution, self.auth, "author-session")
        self.approve(resolved)
        self.repo.apply("CHANGE-MERGED", "retry-merge", self.auth, self.now)
        self.assert_error("LIFECYCLE", self.repo.rebase, "CHANGE-MERGED", "INVALID", self.auth, "author-session")
        self.assertEqual(3, self.repo.audit()["entries"])

    def test_concurrent_connections_never_last_write_win(self):
        plans = [self.propose("CHANGE-A"), self.propose("CHANGE-B", "FACT-B")]
        for p in plans:
            self.approve(p)
        barrier = threading.Barrier(2)
        def worker(id):
            repo = HistoryRepository(self.path)
            barrier.wait(timeout=20)
            try:
                return repo.apply(id, "retry-" + id, self.auth, self.now)
            except ChangeError as e:
                return e.code
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(worker, ["CHANGE-A", "CHANGE-B"]))
        self.assertEqual(1, sum(isinstance(r, dict) for r in results), results)
        self.assertIn("ACP-CHANGE-STALE_BASE", results)
        self.assertEqual(2, self.repo.audit()["entries"])

    def test_idempotent_retry_and_key_conflict(self):
        plan = self.propose()
        self.approve(plan)
        first = self.repo.apply("CHANGE-1", "retry-1", self.auth, self.now)
        self.assertEqual(first, self.repo.apply("CHANGE-1", "retry-1", self.auth, self.now + 99999))
        another = self.propose("CHANGE-2", "FACT-B")
        self.approve(another)
        self.assert_error("IDEMPOTENCY", self.repo.apply, "CHANGE-2", "retry-1", self.auth, self.now)
        self.assertEqual(2, self.repo.audit()["entries"])

    def test_real_process_crash_before_and_after_commit(self):
        plan = self.propose()
        self.approve(plan)
        code = """
import os,sys
sys.path.insert(0,sys.argv[3]);sys.path.insert(0,sys.argv[4])
from history_repository import HistoryRepository
from test_changes import authority
def crash(stage):
    if stage==sys.argv[2]: os._exit(72)
HistoryRepository(sys.argv[1]).apply('CHANGE-1','crash-retry',authority(),1000,crash)
"""
        for stage, expected in (("after_snapshot", 0), ("before_commit", 0), ("after_commit", 1)):
            with self.subTest(stage=stage):
                result = subprocess.run([sys.executable, "-c", code, str(self.path), stage,
                    str(ROOT / "tooling"), str(ROOT / "tooling/tests")], capture_output=True, text=True, timeout=45)
                self.assertEqual(72, result.returncode, result.stderr)
                reopened = HistoryRepository(self.path)
                self.assertEqual(expected, reopened.head()["sequence"])
                reopened.audit()
        self.assertEqual(1, self.repo.apply("CHANGE-1", "crash-retry", self.auth, self.now)["sequence"])

    def test_one_byte_edit_impact_and_migration_invalidate_approval(self):
        original = self.propose()
        proof = self.approve(original)
        edited = copy.deepcopy(original["change"])
        edited["operations"][0]["node"]["name"] += "!"
        new_plan = self.repo.propose(edited, self.auth, "author-session")
        self.assertNotEqual(original["candidate"]["contentDigest"], new_plan["candidate"]["contentDigest"])
        self.assert_error("LIFECYCLE", self.repo.apply, "CHANGE-1", "retry", self.auth, self.now)
        self.repo.review("CHANGE-1", self.auth, "author-session")
        self.assert_error("AUTHORITY", self.repo.approve, "CHANGE-1", proof, self.auth, self.now)
        for modify in (lambda c: c["reads"].append({"id": "FACT-B", "revision": 1}),
                       lambda c: c.update(migration=migration())):
            edited = copy.deepcopy(original["change"])
            modify(edited)
            candidate = self.repo.propose(edited, self.auth, "author-session")
            self.assertEqual(original["candidate"], candidate["candidate"])
            self.assertNotEqual(original["planDigest"], candidate["planDigest"])
            self.assert_error("AUTHORITY", self.auth.verify, proof, request(candidate), self.now)
        forged = copy.deepcopy(original)
        forged["impact"]["semanticIds"] = []
        forged["planDigest"] = fingerprint({k: v for k, v in forged.items() if k != "planDigest"}, "plan")
        self.assert_error("AUTHORITY", self.auth.verify, proof, request(forged), self.now)

    def test_authentication_scope_expiry_revocation_and_separation(self):
        plan = self.propose()
        self.assert_error("AUTHORITY", self.auth.issue, "author-session", request(plan), self.now)
        self.assert_error("AUTHORITY", self.auth.issue, "invalid-session", request(plan), self.now)
        spoof = {**plan["change"], "author": "reviewer"}
        self.assert_error("AUTHORITY", self.repo.propose, spoof, self.auth, "author-session")
        proof = self.approve(plan, ttl=1)
        self.assert_error("AUTHORITY", self.repo.apply, "CHANGE-1", "retry", self.auth, self.now + 1)
        self.auth.revoke(proof)
        self.assert_error("AUTHORITY", self.repo.apply, "CHANGE-1", "retry", self.auth, self.now)
        altered = copy.deepcopy(proof)
        altered["body"]["expiresAt"] += 500
        self.assert_error("AUTHORITY", self.auth.verify, altered, request(plan), self.now)
        scoped = {**request(plan), "requiredScopes": ["SEMANTIC", "SECURITY"]}
        self.assert_error("AUTHORITY", self.auth.issue, "limited-session", scoped, self.now)
        self.assert_error("AUTHORITY", self.auth.verify, proof, {**request(plan), "applicationId": "OTHER-APP"}, self.now)

    def test_same_revision_mutation_and_revision_skip_rejected(self):
        for revision in (1, 3):
            op = revise(self.repo.snapshot(), "FACT-A", name="Different")
            op["node"]["revision"] = revision
            c = change("CHANGE-BAD", self.repo.head(), [op])
            self.assert_error("REVISION", self.repo.propose, c, self.auth, "author-session")
        op = revise(self.repo.snapshot(), "FACT-A")
        self.assert_error("OPERATION", self.repo.propose, change("CHANGE-NOOP", self.repo.head(), [op]), self.auth, "author-session")

    def test_deprecation_supersession_retirement_and_id_reuse(self):
        c = change("CHANGE-DEP", self.repo.head(), [{"op": "DEPRECATE", "id": "FACT-A", "expectedRevision": 1}])
        p = self.repo.propose(c, self.auth, "author-session")
        self.approve(p)
        self.repo.apply("CHANGE-DEP", "dep", self.auth, self.now)
        self.assertEqual("DEPRECATED", self.repo.revision("FACT-A", 2)["lifecycle"])
        c = change("CHANGE-SUP", self.repo.head(), [{"op": "SUPERSEDE", "id": "FACT-A", "expectedRevision": 2,
                                                    "replacement": {"id": "FACT-B", "revision": 1}}])
        p = self.repo.propose(c, self.auth, "author-session")
        self.approve(p)
        self.repo.apply("CHANGE-SUP", "sup", self.auth, self.now)
        self.assertNotIn("FACT-A", index(self.repo.snapshot()))
        self.assertEqual("SUPERSEDED", self.repo.revision("FACT-A", 3)["lifecycle"])
        retired = copy.deepcopy(index(self.initial["candidate"])["FACT-A"])
        c = change("CHANGE-REUSE", self.repo.head(), [{"op": "ADD", "node": retired}])
        self.assert_error("IDENTITY", self.repo.propose, c, self.auth, "author-session")
        self.assertEqual(3, self.repo.audit()["entries"])

    def test_supersession_cannot_cycle_or_retarget_wrong_kind(self):
        ops = [{"op": "SUPERSEDE", "id": "FACT-A", "expectedRevision": 1, "replacement": {"id": "FACT-A", "revision": 1}}]
        self.assert_error("SUPERSESSION", self.repo.propose, change("CHANGE-BAD", self.repo.head(), ops), self.auth, "author-session")
        ops[0]["replacement"]["id"] = "FACT-B"
        ops.append({"op": "SUPERSEDE", "id": "FACT-B", "expectedRevision": 1, "replacement": {"id": "FACT-A", "revision": 1}})
        self.assert_error("SUPERSESSION", self.repo.propose, change("CHANGE-BAD", self.repo.head(), ops), self.auth, "author-session")

    def test_rollback_is_forward_history_and_irreversible_requires_repair(self):
        plan = self.propose(migration_plan=migration(True))
        self.approve(plan)
        self.repo.apply("CHANGE-1", "first", self.auth, self.now)
        template = change("CHANGE-ROLLBACK", self.repo.head(), [])
        c = self.repo.rollback_change(0, template)
        self.assert_error("ROLLBACK", self.repo.propose, c, self.auth, "author-session")
        c["migration"] = migration(True)
        rollback = self.repo.propose(c, self.auth, "author-session")
        self.assertEqual("CRITICAL", rollback["risk"])
        self.assertIn("IRREVERSIBLE", rollback["requiredScopes"])
        self.approve(rollback)
        self.repo.apply("CHANGE-ROLLBACK", "restore", self.auth, self.now)
        self.assertEqual("FACT-A", self.repo.revision("FACT-A", 3)["name"])
        self.assertNotEqual(self.repo.snapshot(0)["contentDigest"], self.repo.snapshot()["contentDigest"])
        self.assertEqual(3, self.repo.audit()["entries"])

    def test_failed_and_stale_evidence_never_mutates_accepted_history(self):
        head = self.repo.head()
        for result in ("PASS", "FAIL"):
            self.repo.observe({"id": "EVIDENCE-" + result, "snapshotDigest": head["digest"],
                "subjects": [{"id": "FACT-A", "revision": 1}], "result": result, "artifactDigest": "sha256:" + "a" * 64})
        self.assertEqual(head, self.repo.head())
        self.assertEqual("FAIL", self.repo.evidence("EVIDENCE-FAIL")["state"])
        plan = self.propose()
        self.approve(plan)
        self.repo.apply("CHANGE-1", "next", self.auth, self.now)
        self.assertEqual("STALE", self.repo.evidence("EVIDENCE-PASS")["state"])

    def test_source_receipts_and_portable_restore(self):
        source_digest = self.initial["sources"][0]["receipt"]["sourceDigest"]
        self.assertEqual(small_source(), self.repo.source(source_digest)["source"])
        plan = self.propose()
        self.approve(plan)
        self.repo.apply("CHANGE-1", "next", self.auth, self.now)
        exported, anchor = self.repo.export_records(), self.repo.head()
        replacement = HistoryRepository(Path(self.temp.name) / "replacement.sqlite")
        replacement.restore(exported, anchor)
        self.assertEqual(exported, replacement.export_records())
        self.assertEqual(self.repo.revision("FACT-A", 1), replacement.revision("FACT-A", 1))
        tampered = copy.deepcopy(exported)
        tampered["journal"][0][3]["committedAt"] += 1
        rejected = HistoryRepository(Path(self.temp.name) / "rejected.sqlite")
        self.assert_error("HISTORY", rejected.restore, tampered, anchor)
        self.assert_error("NOT_FOUND", rejected.head)

    def test_append_only_enforcement_tamper_detection_and_anchor(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM journal")
        anchor = self.repo.head()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DROP TRIGGER deny_journal_UPDATE")
            entry = self.repo.history()[0]
            entry["committedAt"] += 1
            db.execute("UPDATE journal SET body=?", (canonical_bytes(entry),))
        self.assert_error("HISTORY", self.repo.audit)
        with closing(sqlite3.connect(self.path)) as db, db:
            new_digest = fingerprint(entry, "journal")
            db.execute("UPDATE journal SET digest=?", (new_digest,))
            db.execute("DROP TRIGGER deny_records_UPDATE")
            receipt = json.loads(db.execute("SELECT body FROM records WHERE kind='retry' AND key='GENESIS'").fetchone()[0])
            receipt["result"]["journalDigest"] = new_digest
            db.execute("UPDATE records SET body=? WHERE kind='retry' AND key='GENESIS'", (canonical_bytes(receipt),))
            # Even a coherently recomputed unkeyed chain cannot match an external anchor.
        self.repo.audit()
        self.assert_error("HISTORY", self.repo.audit, anchor)

    def test_unavailable_authority_malformed_evidence_and_unknown_parent(self):
        p = self.propose()
        proof = self.approve(p)
        class Offline:
            def verify(self, *args):
                raise RuntimeError("private service failure")
        self.assert_error("AUTHORITY", self.repo.apply, "CHANGE-1", "retry", Offline(), self.now)
        self.assertEqual(0, self.repo.head()["sequence"])
        self.assert_error("EVIDENCE", self.repo.observe, {"id": "INVALID"})
        c = copy.deepcopy(p["change"])
        c["parents"] = ["sha256:" + "0" * 64]
        self.assert_error("PROVENANCE", self.repo.propose, c, self.auth, "author-session")
        self.repo.apply("CHANGE-1", "retry", self.auth, self.now)
        self.auth.revoke(proof)
        self.repo.audit(self.repo.head(), authority=self.auth)

    def test_journal_snapshot_inconsistency_is_detected(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DROP TRIGGER deny_records_UPDATE")
            snapshot = self.repo.snapshot()
            snapshot["content"]["nodes"][0]["name"] = "tampered"
            db.execute("UPDATE records SET body=? WHERE kind='snapshot' AND key='0'", (canonical_bytes(snapshot),))
        self.assert_error("HISTORY", self.repo.audit)

    def test_requirement_decision_concept_provenance_and_locked_scope(self):
        source = small_source()
        template = copy.deepcopy(source["nodes"][0])
        r = lambda id: {"id": id, "revision": 1}
        source["nodes"] += [
            {**template, "id": "REQ-HISTORY", "kind": "Requirement", "data": {
                "statement": "Preserve history", "priority": "MUST", "acceptance": [r("AC-HISTORY")]}},
            {**template, "id": "AC-HISTORY", "kind": "AcceptanceCriterion", "basis": [r("REQ-HISTORY")],
             "data": {"requirement": r("REQ-HISTORY"), "scenario": "History remains explainable"}},
            {**template, "id": "DEC-HISTORY", "kind": "Decision", "basis": [r("REQ-HISTORY")], "data": {
                "statement": "Use explicit lineage", "strength": "LOCKED", "rationale": "Traceability", "alternatives": ["Implicit lineage"]}},
        ]
        source["nodes"][0]["basis"] = [r("DEC-HISTORY")]
        source = synthetic_approved(source)
        repo = HistoryRepository(Path(self.temp.name) / "provenance.sqlite")
        initial = genesis(source, "author")
        repo.bootstrap(initial, self.auth.issue("reviewer-session", request(initial), self.now), self.auth, self.now, "author-session")
        lineage = repo.provenance("FACT-A", 1)
        self.assertEqual({"REQ-HISTORY", "DEC-HISTORY"}, {n["id"] for n in lineage["justification"]})
        p = repo.propose(change("CHANGE-LOCKED", repo.head(), [revise(repo.snapshot(), "DEC-HISTORY", name="New decision label")]),
                         self.auth, "author-session")
        self.assertIn("LOCKED_DECISION", p["requiredScopes"])
        self.assertGreater(len(p["writeSet"]), 1)
        self.assert_error("AUTHORITY", self.auth.issue, "limited-session", request(p), self.now)

    def test_missing_migration_and_bad_source_receipt_are_rejected(self):
        p = self.propose()
        c = copy.deepcopy(p["change"])
        c["sources"] = copy.deepcopy(self.initial["sources"])
        c["sources"][0]["receipt"]["sourceDigest"] = "sha256:" + "0" * 64
        self.assert_error("SOURCE", self.repo.propose, c, self.auth, "author-session")
        c = copy.deepcopy(p["change"])
        c["migration"] = migration()
        c["migration"]["verification"] = []
        self.assert_error("MIGRATION", self.repo.propose, c, self.auth, "author-session")
        c["migration"] = migration()
        c["migration"]["compatibility"] = "UNKNOWN"
        self.assert_error("MIGRATION", self.repo.propose, c, self.auth, "author-session")

    def test_dependency_cascade_and_both_reference_domain_evolutions(self):
        expected = load(ROOT / "test-corpus/change/evolution.json")
        self.assertEqual(expected, vectors())
        for domain in expected["domains"]:
            with self.subTest(domain=domain["base"]):
                model = synthetic_approved(models()[domain["base"]])
                auth = authority(model["applicationId"])
                repo = HistoryRepository(Path(self.temp.name) / (domain["base"] + ".sqlite"))
                initial = genesis(model, "author")
                repo.bootstrap(initial, auth.issue("reviewer-session", request(initial), self.now), auth, self.now, "author-session")
                for step, vector in zip(STEPS, domain["steps"][1:]):
                    prior = repo.snapshot()
                    plan = repo.propose(evolution_change(prior, repo.head(), step), auth, "author-session")
                    self.assertEqual(vector["contentDigest"], plan["candidate"]["contentDigest"])
                    self.assertEqual(vector["writeSet"], plan["writeSet"])
                    self.approve(plan, repo, auth)
                    repo.apply(plan["change"]["id"], "retry-" + step, auth, self.now)
                    after = repo.snapshot()
                    validate_snapshot(after)
                    previous_nodes, current_nodes = index(prior), index(after)
                    for id in set(previous_nodes) & set(current_nodes):
                        a, b = previous_nodes[id], current_nodes[id]
                        self.assertEqual(a["revision"] + (a != b), b["revision"])
                self.assertEqual(6, repo.audit(repo.head())["entries"])
                requirement = next(n for n in model["nodes"] if n["kind"] == "Requirement")
                self.assertEqual(requirement, repo.revision(requirement["id"], 1))

    def test_concurrent_security_changes_require_merge_and_scoped_review(self):
        model = synthetic_approved(models()["case-management.json"])
        auth = authority(model["applicationId"])
        repo = HistoryRepository(Path(self.temp.name) / "security.sqlite")
        first = genesis(model, "author")
        repo.bootstrap(first, auth.issue("reviewer-session", request(first), self.now), auth, self.now, "author-session")
        policies = [n for n in repo.snapshot()["content"]["nodes"] if n["kind"] == "Policy"][:2]
        plans = []
        for count, policy in enumerate(policies):
            op = revise(repo.snapshot(), policy["id"], data={**policy["data"], "effect": "DENY"})
            plan = repo.propose(change("CHANGE-POLICY-" + str(count), repo.head(), [op]), auth, "author-session")
            self.assertIn("SECURITY", plan["requiredScopes"])
            self.assert_error("AUTHORITY", auth.issue, "limited-session", request(plan), self.now)
            self.approve(plan, repo, auth)
            plans.append(plan)
        repo.apply(plans[0]["change"]["id"], "policy-first", auth, self.now)
        merge = repo.rebase(plans[1]["change"]["id"], "POLICY-REBASE", auth, "author-session")
        self.assertEqual("MERGE_REQUIRED", merge["kind"])

    def test_property_independent_operation_order_and_reference_stability(self):
        base = self.repo.snapshot()
        operations = [revise(base, "FACT-A", name="Alpha"), revise(base, "FACT-B", name="Beta")]
        expected = prepare(base, change("CHANGE-PROPERTY", self.repo.head(), operations))["candidate"]
        rng = random.Random(30928)
        for _ in range(12):
            shuffled = copy.deepcopy(operations)
            rng.shuffle(shuffled)
            for op in shuffled:
                op["node"] = {k: op["node"][k] for k in reversed(op["node"])}
            actual = prepare(base, change("CHANGE-PROPERTY", self.repo.head(), shuffled))
            self.assertEqual(expected, actual["candidate"])
            self.assertEqual(["FACT-A", "FACT-B"], actual["writeSet"])


if __name__ == "__main__":
    unittest.main()
