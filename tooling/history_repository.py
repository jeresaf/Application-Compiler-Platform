"""SQLite reference repository behind Phase 3 ports; single application per store."""
from contextlib import contextmanager, nullcontext
import copy
import json
import sqlite3

from canonical_ir import validate_snapshot, admit
from canonical_json import canonical_bytes, loads
from changes import (ChangeError, SHAPES, EVIDENCE_SHAPES, check_sources, fingerprint, genesis, index, prepare, request,
                     rebase_conflicts, rewrite, seal, stale_reads, evidence_state)

TABLES = ("journal", "records", "proposal_events")


def revision_key(id, revision):
    return json.dumps([id, revision], separators=(",", ":"))


class HistoryRepository:
    def __init__(self, path):
        self.path = str(path)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS journal (
                    sequence INTEGER PRIMARY KEY, change_id TEXT NOT NULL UNIQUE,
                    digest TEXT NOT NULL UNIQUE, body BLOB NOT NULL);
                CREATE TABLE IF NOT EXISTS records (
                    kind TEXT NOT NULL, key TEXT NOT NULL, body BLOB NOT NULL, PRIMARY KEY(kind,key));
                CREATE TABLE IF NOT EXISTS proposal_events (
                    serial INTEGER PRIMARY KEY, change_id TEXT NOT NULL, state TEXT NOT NULL,
                    plan_digest TEXT NOT NULL, body BLOB NOT NULL);
            """)
            for table in TABLES:
                for action in ("UPDATE", "DELETE"):
                    db.execute(f"CREATE TRIGGER IF NOT EXISTS deny_{table}_{action} BEFORE {action} ON {table} "
                               "BEGIN SELECT RAISE(ABORT, 'append-only reference repository'); END")
            row = db.execute("SELECT body FROM records WHERE kind='format' AND key='version'").fetchone()
            if row is None:
                self._put(db, "format", "version", {"repositoryFormat": "acp-history-sqlite-ref-1"})
            elif loads(row[0]) != {"repositoryFormat": "acp-history-sqlite-ref-1"}:
                raise ChangeError("STORAGE", "Unsupported repository format.")

    @contextmanager
    def connection(self, write=False):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("PRAGMA synchronous=FULL")
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except sqlite3.Error:
            if db.in_transaction:
                db.rollback()
            raise ChangeError("STORAGE", "Reference storage operation failed; transaction was not partially accepted.") from None
        except BaseException:
            if db.in_transaction:
                db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _put(db, kind, key, body):
        db.execute("INSERT INTO records VALUES (?,?,?)", (kind, str(key), canonical_bytes(body)))

    @staticmethod
    def _get(db, kind, key):
        row = db.execute("SELECT body FROM records WHERE kind=? AND key=?", (kind, str(key))).fetchone()
        if row is None:
            raise ChangeError("NOT_FOUND", "Requested historical record does not exist.")
        return loads(row[0])

    @staticmethod
    def _head(db):
        row = db.execute("SELECT sequence,digest,body FROM journal ORDER BY sequence DESC LIMIT 1").fetchone()
        if row is None:
            raise ChangeError("NOT_FOUND", "Repository has no accepted snapshot.")
        body = loads(row[2])
        if fingerprint(body, "journal") != row[1]:
            raise ChangeError("HISTORY", "Journal head digest mismatch.")
        return {"sequence": row[0], "digest": body["plan"]["candidate"]["contentDigest"], "journalDigest": row[1]}

    def head(self):
        with self.connection() as db:
            return self._head(db)

    def snapshot(self, sequence=None, digest_value=None):
        with self.connection() as db:
            if digest_value is not None:
                sequence = self._get(db, "snapshot-digest", digest_value)["sequence"]
            if sequence is None:
                sequence = self._head(db)["sequence"]
            result = self._get(db, "snapshot", sequence)
            validate_snapshot(result)
            return result

    def revision(self, id, revision):
        with self.connection() as db:
            return self._get(db, "revision", revision_key(id, revision))["node"]

    def _event(self, db, id, state, plan_digest, body):
        db.execute("INSERT INTO proposal_events(change_id,state,plan_digest,body) VALUES (?,?,?,?)",
                   (id, state, plan_digest, canonical_bytes(body)))

    def _proposal(self, db, id):
        row = db.execute("SELECT state,plan_digest,body FROM proposal_events WHERE change_id=? ORDER BY serial DESC LIMIT 1", (id,)).fetchone()
        if row is None:
            raise ChangeError("NOT_FOUND", "Proposal does not exist.")
        return {"state": row[0], "planDigest": row[1], **loads(row[2])}

    def proposal(self, id):
        with self.connection() as db:
            return self._proposal(db, id)

    def _base(self, db, token):
        snapshot = self._get(db, "snapshot", token["sequence"])
        row = db.execute("SELECT digest FROM journal WHERE sequence=?", (token["sequence"],)).fetchone()
        if row is None or row[0] != token["journalDigest"] or snapshot["contentDigest"] != token["digest"]:
            raise ChangeError("BASE", "Base sequence, snapshot and journal binding disagree.")
        return snapshot

    @staticmethod
    def _authorize(authority, proof, plan, now):
        expected = request(plan)
        try:
            verdict = authority.verify(proof, expected, now)
            if (set(verdict) != {"principal", "proofDigest", "request"} or not isinstance(verdict["principal"], str)
                    or not verdict["principal"].strip() or verdict["principal"] == plan["author"]
                    or verdict["request"] != expected or verdict["proofDigest"] != fingerprint(proof, "proof")):
                raise ValueError()
            return verdict
        except Exception:
            raise ChangeError("AUTHORITY", "Trusted authority is unavailable or did not return a valid exact-content approval.") from None

    def propose(self, change, authority, session):
        from changes import valid_change_shape
        try:
            canonical_bytes(change)
            if not valid_change_shape(change) or change["id"] == "GENESIS":
                raise ValueError()
        except (ValueError, RecursionError):
            raise ChangeError("SHAPE", "ChangeSet violates its bounded input contract.") from None
        if authority.authenticate(session) != change.get("author"):
            raise ChangeError("AUTHORITY", "Authenticated proposer must match the ChangeSet author.")
        with self.connection(write=True) as db:
            base = self._base(db, change["base"])
            plan = prepare(base, change)
            for parent in change["parents"]:
                if not db.execute("SELECT 1 FROM proposal_events WHERE plan_digest=? UNION SELECT 1 FROM journal WHERE digest=?", (parent, parent)).fetchone():
                    raise ChangeError("PROVENANCE", "Parent proposal or journal digest is not present in history.")
            for op in change["operations"]:
                if op["op"] == "ADD" and db.execute("SELECT 1 FROM records WHERE kind='identity' AND key=?", (op["node"]["id"],)).fetchone():
                    raise ChangeError("IDENTITY", "Semantic IDs are permanently reserved, including retired IDs.")
            existing = db.execute("SELECT 1 FROM proposal_events WHERE change_id=?", (change["id"],)).fetchone()
            if existing:
                previous = self._proposal(db, change["id"])
                if previous["state"] in {"APPLIED", "REJECTED"} or previous["plan"]["author"] != change["author"]:
                    raise ChangeError("LIFECYCLE", "Terminal or differently authored ChangeSet cannot be edited.")
            if change["rollbackOf"] is not None:
                target = change["rollbackOf"]
                if target >= change["base"]["sequence"]:
                    raise ChangeError("ROLLBACK", "Rollback must identify an earlier accepted snapshot.")
                self._get(db, "snapshot", target)
                for row in db.execute("SELECT body FROM journal WHERE sequence>?", (target,)):
                    prior = loads(row[0])["plan"].get("change")
                    if prior and prior["migration"]["irreversible"] and not change["migration"]["irreversible"]:
                        raise ChangeError("ROLLBACK", "Irreversible history requires an explicit forward-repair migration and scope.")
            self._event(db, change["id"], "PROPOSED", plan["planDigest"], {"plan": plan})
            return plan

    def review(self, id, authority, session):
        with self.connection(write=True) as db:
            p = self._proposal(db, id)
            if p["state"] != "PROPOSED" or authority.authenticate(session) != p["plan"]["author"]:
                raise ChangeError("LIFECYCLE", "Only the authenticated author can submit a proposal for review.")
            self._event(db, id, "REVIEW_REQUIRED", p["planDigest"], {"plan": p["plan"]})

    def reject(self, id, authority, session):
        with self.connection(write=True) as db:
            p = self._proposal(db, id)
            if p["state"] in {"APPLIED", "REJECTED"} or authority.authenticate(session) != p["plan"]["author"]:
                raise ChangeError("LIFECYCLE", "Applied history cannot be rejected or deleted.")
            self._event(db, id, "REJECTED", p["planDigest"], {"plan": p["plan"]})

    def approve(self, id, proof, authority, now):
        with self.connection(write=True) as db:
            p = self._proposal(db, id)
            if p["state"] != "REVIEW_REQUIRED":
                raise ChangeError("LIFECYCLE", "Proposal must be awaiting review.")
            verdict = self._authorize(authority, proof, p["plan"], now)
            self._event(db, id, "APPROVED", p["planDigest"], {"plan": p["plan"], "proof": proof, "verdict": verdict})

    def _append(self, db, plan, proof, verdict, retry_key, now, crash):
        row = db.execute("SELECT sequence,digest FROM journal ORDER BY sequence DESC LIMIT 1").fetchone()
        seq, prev = (0, None) if row is None else (row[0] + 1, row[1])
        snapshot = plan["candidate"]
        for n in snapshot["content"]["nodes"] + plan.get("tombstones", []):
            id, rev = n["id"], n["revision"]
            existing = db.execute("SELECT body FROM records WHERE kind='revision' AND key=?", (revision_key(id, rev),)).fetchone()
            if existing:
                if loads(existing[0])["node"] != n:
                    raise ChangeError("REVISION", "Accepted semantic ID/revision cannot acquire different meaning.")
            else:
                identity = db.execute("SELECT body FROM records WHERE kind='identity' AND key=?", (id,)).fetchone()
                if identity is None:
                    if rev != 1:
                        raise ChangeError("REVISION", "New identities start at revision one.")
                    self._put(db, "identity", id, {"id": id, "kind": n["kind"], "firstSequence": seq})
                elif loads(identity[0])["kind"] != n["kind"]:
                    raise ChangeError("IDENTITY", "Kind cannot change for an existing ID.")
                self._put(db, "revision", revision_key(id, rev), {"node": n, "firstSequence": seq})
        for tombstone in plan.get("tombstones", []):
            self._put(db, "retired", tombstone["id"], {"sequence": seq, "node": tombstone})
        self._put(db, "snapshot", seq, snapshot)
        self._put(db, "snapshot-digest", snapshot["contentDigest"], {"sequence": seq})
        if crash:
            crash("after_snapshot")
        change_id = "GENESIS" if plan["change"] is None else plan["change"]["id"]
        body = {"entryVersion": "0.1.0", "sequence": seq, "previousDigest": prev,
                "plan": plan, "approval": {"proof": proof, "verdict": verdict}, "committedAt": now, "retryKey": retry_key}
        journal_digest = fingerprint(body, "journal")
        db.execute("INSERT INTO journal VALUES (?,?,?,?)", (seq, change_id, journal_digest, canonical_bytes(body)))
        result = {"sequence": seq, "digest": snapshot["contentDigest"], "journalDigest": journal_digest}
        self._put(db, "retry", retry_key, {"planDigest": plan["planDigest"], "changeId": change_id, "result": result})
        if plan["change"] is not None:
            self._event(db, change_id, "APPLIED", plan["planDigest"], {"plan": plan, "result": result})
        if crash:
            crash("before_commit")
        return result

    def bootstrap(self, plan, proof, authority, now, session, crash=None):
        with self.connection(write=True) as db:
            if db.execute("SELECT 1 FROM journal").fetchone():
                raise ChangeError("LIFECYCLE", "Repository is already initialized.")
            if authority.authenticate(session) != plan["author"] or plan != genesis(plan["sources"][0]["source"], plan["author"]):
                raise ChangeError("PLAN", "Initialization plan or authenticated author does not match.")
            verdict = self._authorize(authority, proof, plan, now)
            admit(plan["candidate"], lambda r: r["contentDigest"] == request(plan)["contentDigest"])
            result = self._append(db, plan, proof, verdict, "GENESIS", now, crash)
        if crash:
            crash("after_commit")
        return result

    def apply(self, id, retry_key, authority, now, crash=None):
        if not isinstance(retry_key, str) or not retry_key.strip() or len(retry_key) > 128:
            raise ChangeError("IDEMPOTENCY", "A bounded nonblank retry key is required.")
        with self.connection(write=True) as db:
            p = self._proposal(db, id)
            row = db.execute("SELECT body FROM records WHERE kind='retry' AND key=?", (retry_key,)).fetchone()
            if row:
                receipt = loads(row[0])
                if receipt["planDigest"] != p["planDigest"] or receipt["changeId"] != id:
                    raise ChangeError("IDEMPOTENCY", "Retry key is bound to a different immutable change.")
                return receipt["result"]
            if p["state"] != "APPROVED":
                raise ChangeError("LIFECYCLE", "Only an approved current proposal can be applied.")
            plan = p["plan"]
            base = self._base(db, plan["change"]["base"])
            if plan != prepare(base, plan["change"]):
                raise ChangeError("PLAN", "Candidate, impact or migration differs from deterministic analysis.")
            head = self._head(db)
            if stale_reads(plan, self._get(db, "snapshot", head["sequence"])):
                raise ChangeError("READSET", "Read-set or absent-ID reservation became stale.")
            if head != plan["change"]["base"]:
                raise ChangeError("STALE_BASE", "Head advanced; explicit rebase or merge review is required.")
            verdict = self._authorize(authority, p["proof"], plan, now)
            # Reuse the exact Phase 2 admission boundary after full change approval.
            admit(plan["candidate"], lambda r: r["contentDigest"] == request(plan)["contentDigest"])
            result = self._append(db, plan, p["proof"], verdict, retry_key, now, crash)
        if crash:
            crash("after_commit")
        return result

    def rebase(self, id, new_id, authority, session):
        # Read lifecycle and head under the same writer reservation as the merge
        # event, so a concurrent apply/reject cannot make that event illegal.
        with self.connection(write=True) as db:
            p = self._proposal(db, id)
            if p["state"] in {"APPLIED", "REJECTED"}:
                raise ChangeError("LIFECYCLE", "Terminal proposals cannot be rebased.")
            plan = p["plan"]
            if authority.authenticate(session) != plan["author"]:
                raise ChangeError("AUTHORITY", "Only the authenticated author can rebase.")
            head = self._head(db)
            current = self._get(db, "snapshot", head["sequence"])
            conflicts = rebase_conflicts(plan, self._base(db, plan["change"]["base"]), current)
            if conflicts:
                merge = {"plan": plan, "merge": {"kind": "MERGE_REQUIRED", "parents": [plan["planDigest"], head["journalDigest"]],
                         "base": plan["change"]["base"], "head": head, "conflicts": conflicts, "automaticApply": False}}
                self._event(db, id, "MERGE_REQUIRED", plan["planDigest"], merge)
                return merge["merge"]
            change = {**copy.deepcopy(plan["change"]), "id": new_id, "base": head, "parents": [plan["planDigest"]]}
        # This is an isolated proposal only; apply rechecks any later head change.
        return self.propose(change, authority, session)

    def rollback_change(self, target_sequence, template):
        head = self.head()
        current, prior = self.snapshot(head["sequence"]), self.snapshot(target_sequence)
        old, desired = index(current), index(prior)
        if set(old) != set(desired):
            raise ChangeError("ROLLBACK", "Membership rollback requires an explicit forward repair; retired IDs cannot be resurrected.")
        mapping = {id: (desired[id]["revision"], old[id]["revision"]) for id in old}
        operations = []
        for id, historical in desired.items():
            restored = rewrite(historical, mapping, {})
            restored["revision"] = old[id]["revision"]
            restored["lifecycle"] = old[id]["lifecycle"]
            if restored != old[id]:
                restored["revision"] += 1
                operations.append({"op": "REVISE", "id": id, "expectedRevision": old[id]["revision"], "node": restored})
        return {**copy.deepcopy(template), "base": head, "operations": operations, "rollbackOf": target_sequence}

    def observe(self, evidence):
        canonical_bytes(evidence)
        if not EVIDENCE_SHAPES.is_valid(evidence):
            raise ChangeError("EVIDENCE", "Invalid bounded evidence observation.")
        snapshot = self.snapshot(digest_value=evidence["snapshotDigest"])
        if evidence_state(evidence, snapshot) == "STALE":
            raise ChangeError("EVIDENCE", "Evidence subjects do not bind the historical snapshot.")
        with self.connection(write=True) as db:
            self._put(db, "evidence", evidence["id"], {"observation": evidence, "digest": fingerprint(evidence, "record")})

    def evidence(self, id):
        with self.connection() as db:
            value = self._get(db, "evidence", id)
            if fingerprint(value["observation"], "record") != value["digest"]:
                raise ChangeError("HISTORY", "Evidence integrity mismatch.")
            return {**value, "state": evidence_state(value["observation"], self.snapshot())}

    def history(self):
        with self.connection() as db:
            return [loads(row[0]) for row in db.execute("SELECT body FROM journal ORDER BY sequence")]

    def provenance(self, id, revision):
        node = self.revision(id, revision)
        ancestors, pending = {}, list(node["basis"])
        while pending:
            r = pending.pop()
            key = revision_key(r["id"], r["revision"])
            if key not in ancestors:
                ancestor = self.revision(r["id"], r["revision"])
                ancestors[key] = ancestor
                pending.extend(ancestor["basis"])
        events = [e for e in self.history() if any(n["id"] == id and n["revision"] == revision
                  for n in e["plan"]["candidate"]["content"]["nodes"] + e["plan"].get("tombstones", []))]
        return {"node": node, "basis": [self.revision(r["id"], r["revision"]) for r in node["basis"]],
                "justification": [ancestors[k] for k in sorted(ancestors)],
                "changes": [e["plan"]["change"]["id"] if e["plan"]["change"] else "GENESIS" for e in events],
                "snapshots": [e["plan"]["candidate"]["contentDigest"] for e in events]}

    def source(self, source_digest):
        for entry in self.history():
            p = entry["plan"]
            for pair in p.get("sources", []) + (p["change"]["sources"] if p["change"] else []):
                if pair["receipt"]["sourceDigest"] == source_digest:
                    check_sources([pair])
                    return pair
        raise ChangeError("NOT_FOUND", "Source receipt is not retained in history.")

    def audit(self, anchor=None, authority=None, _db=None):
        """Recompute the hash chain, candidate plans and all accepted-state indexes."""
        with (self.connection() if _db is None else nullcontext(_db)) as db:
            if not db.in_transaction:
                db.execute("BEGIN")
            rows = list(db.execute("SELECT sequence,change_id,digest,body FROM journal ORDER BY sequence"))
            expected = {("format", "version"): {"repositoryFormat": "acp-history-sqlite-ref-1"}}
            previous = None
            prior_snapshot = None
            for offset, (seq, id, hash_value, raw) in enumerate(rows):
                entry = loads(raw)
                if seq != offset or entry["sequence"] != seq or entry["previousDigest"] != previous or fingerprint(entry, "journal") != hash_value:
                    raise ChangeError("HISTORY", "Journal sequence or hash chain is inconsistent.")
                plan = entry["plan"]
                if seq == 0:
                    regenerated = genesis(plan["sources"][0]["source"], plan["author"])
                else:
                    if plan["change"]["base"] != {"sequence": seq - 1, "digest": prior_snapshot["contentDigest"], "journalDigest": previous}:
                        raise ChangeError("HISTORY", "Journal entry did not commit against its exact predecessor.")
                    regenerated = prepare(prior_snapshot, plan["change"])
                if plan != regenerated or id != ("GENESIS" if plan["change"] is None else plan["change"]["id"]):
                    raise ChangeError("HISTORY", "Accepted plan does not reproduce its semantic analysis.")
                snapshot = plan["candidate"]
                validate_snapshot(snapshot)
                if entry["approval"]["verdict"]["request"] != request(plan) or entry["approval"]["verdict"]["proofDigest"] != fingerprint(entry["approval"]["proof"], "proof"):
                    raise ChangeError("HISTORY", "Approval receipt does not bind accepted content and analysis.")
                if authority is not None and authority.verify_historical(entry["approval"]["proof"], request(plan), entry["committedAt"]) != entry["approval"]["verdict"]:
                    raise ChangeError("HISTORY", "Historical authority receipt does not verify.")
                expected[("snapshot", str(seq))] = snapshot
                expected[("snapshot-digest", snapshot["contentDigest"])] = {"sequence": seq}
                for n in snapshot["content"]["nodes"] + plan.get("tombstones", []):
                    k = ("revision", revision_key(n["id"], n["revision"]))
                    if k in expected and expected[k]["node"] != n:
                        raise ChangeError("HISTORY", "Same accepted ID/revision has different meaning.")
                    if ("retired", n["id"]) in expected:
                        raise ChangeError("HISTORY", "A retired semantic ID reappeared.")
                    expected.setdefault(k, {"node": n, "firstSequence": seq})
                    expected.setdefault(("identity", n["id"]), {"id": n["id"], "kind": n["kind"], "firstSequence": seq})
                for n in plan.get("tombstones", []):
                    expected[("retired", n["id"])] = {"sequence": seq, "node": n}
                result = {"sequence": seq, "digest": snapshot["contentDigest"], "journalDigest": hash_value}
                expected[("retry", entry["retryKey"])] = {"planDigest": plan["planDigest"], "changeId": id, "result": result}
                previous, prior_snapshot = hash_value, snapshot
            actual = {(kind, key): loads(raw) for kind, key, raw in db.execute("SELECT kind,key,body FROM records WHERE kind!='evidence'")}
            if actual != expected:
                raise ChangeError("HISTORY", "Journal, snapshot, revision, reservation or retry indexes disagree.")
            if anchor is not None:
                if anchor["sequence"] >= len(rows) or rows[anchor["sequence"]][2] != anchor["journalDigest"]:
                    raise ChangeError("HISTORY", "History does not match the external trusted anchor.")
            for raw, in db.execute("SELECT body FROM records WHERE kind='evidence'"):
                e = loads(raw)
                if fingerprint(e["observation"], "record") != e["digest"]:
                    raise ChangeError("HISTORY", "Evidence observation was altered.")
            states, applied = {}, set()
            accepted = {id: loads(raw) for _, id, _, raw in rows if id != "GENESIS"}
            allowed = {"PROPOSED": {None, "PROPOSED", "REVIEW_REQUIRED", "APPROVED", "MERGE_REQUIRED"},
                       "REVIEW_REQUIRED": {"PROPOSED"}, "APPROVED": {"REVIEW_REQUIRED"},
                       "APPLIED": {"APPROVED"}, "REJECTED": {"PROPOSED", "REVIEW_REQUIRED", "APPROVED", "MERGE_REQUIRED"},
                       "MERGE_REQUIRED": {"PROPOSED", "REVIEW_REQUIRED", "APPROVED", "MERGE_REQUIRED"}}
            for id, state, plan_digest, raw in db.execute("SELECT change_id,state,plan_digest,body FROM proposal_events ORDER BY serial"):
                event = loads(raw)
                p = event["plan"]
                if (state not in allowed or states.get(id) not in allowed[state] or p["change"]["id"] != id
                        or p["planDigest"] != plan_digest or seal({k: v for k, v in p.items() if k != "planDigest"}) != p):
                    raise ChangeError("HISTORY", "Proposal lifecycle or immutable plan binding is inconsistent.")
                if state == "APPROVED":
                    if event["verdict"]["request"] != request(p) or event["verdict"]["proofDigest"] != fingerprint(event["proof"], "proof"):
                        raise ChangeError("HISTORY", "Proposal approval is not bound to its exact plan.")
                if state == "APPLIED":
                    if id not in accepted or accepted[id]["plan"] != p or event["result"] != expected[("retry", accepted[id]["retryKey"])]["result"]:
                        raise ChangeError("HISTORY", "Applied proposal and journal outcome disagree.")
                    applied.add(id)
                states[id] = state
            if applied != set(accepted):
                raise ChangeError("HISTORY", "Accepted changes and applied lifecycle events disagree.")
            return {"entries": len(rows), "head": previous, "anchored": anchor is not None}

    def export_records(self):
        """Portable records, one bounded JSON value each; no SQLite pages escape."""
        with self.connection() as db:
            db.execute("BEGIN")
            return {"format": "acp-history-export-1",
                "journal": [[s, id, d, loads(b)] for s, id, d, b in db.execute("SELECT * FROM journal ORDER BY sequence")],
                "records": [[k, id, loads(b)] for k, id, b in db.execute("SELECT * FROM records ORDER BY kind,key")],
                "proposals": [[s, id, state, d, loads(b)] for s, id, state, d, b in db.execute("SELECT * FROM proposal_events ORDER BY serial")]}

    def restore(self, exported, anchor):
        if exported["format"] != "acp-history-export-1" or not isinstance(anchor, dict) or not {"sequence", "journalDigest"} <= set(anchor):
            raise ChangeError("STORAGE", "Unsupported portable export version.")
        with self.connection(write=True) as db:
            if db.execute("SELECT 1 FROM journal").fetchone() or db.execute("SELECT 1 FROM proposal_events").fetchone():
                raise ChangeError("STORAGE", "Restore requires an empty repository.")
            for seq, id, d, body in exported["journal"]:
                db.execute("INSERT INTO journal VALUES (?,?,?,?)", (seq, id, d, canonical_bytes(body)))
            for kind, key, body in exported["records"]:
                if kind != "format":
                    self._put(db, kind, key, body)
            for seq, id, state, d, body in exported["proposals"]:
                db.execute("INSERT INTO proposal_events VALUES (?,?,?,?,?)", (seq, id, state, d, canonical_bytes(body)))
            self.audit(anchor, _db=db)
