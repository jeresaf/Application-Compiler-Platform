"""Pure Phase 3 planning. Neither storage nor approval authority lives here."""
import copy
import hashlib
from typing import Protocol

from jsonschema import Draft202012Validator
from referencing import Registry

from canonical_json import canonical_bytes, digest, load
from canonical_ir import normalize_candidate, validate_snapshot, migrate_authoring, CanonicalError
from validate import ROOT, semantic_walk

SCHEMA = load(ROOT / "contracts/change.schema.json")
SHAPES = Draft202012Validator(SCHEMA, registry=Registry())
EVIDENCE_SHAPES = Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": "#/$defs/observation"}, registry=Registry())
SECURITY = {"Actor", "AuthenticationModel", "Role", "RoleAssignment", "Permission", "Policy", "PolicySet",
            "Scope", "SessionPolicy", "RatePolicy", "DataClassification", "Retention", "DeletionPolicy", "LegalHold", "DataLifecycle"}
WORKFLOW = {"State", "StateMachine", "Transition"}
DATA = {"Field", "Entity", "TypeDefinition", "ValueObject", "Parameter", "Relation", "Aggregate"}


class ChangeError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = "ACP-CHANGE-" + code


class ApprovalAuthority(Protocol):
    def authenticate(self, session: str) -> str:
        """Resolve a host-authenticated session to its principal or raise."""

    def verify(self, proof: dict, request: dict, now: int) -> dict:
        """Return authenticated principal/proof receipt or raise; never trust JSON identity."""


class SnapshotRepository(Protocol):
    def head(self) -> dict: ...
    def snapshot(self, sequence: int | None = None, digest_value: str | None = None) -> dict: ...
    def propose(self, change: dict, authority: ApprovalAuthority, session: str) -> dict: ...
    def apply(self, change_id: str, retry_key: str, authority: ApprovalAuthority, now: int) -> dict: ...
    def audit(self, anchor: dict | None = None) -> dict: ...


def fingerprint(value, domain):
    if domain not in {"plan", "node", "journal", "proof", "record"}:
        raise ValueError("Unknown history digest domain")
    return "sha256:" + hashlib.sha256(("ACP\0change-history-v1\0" + domain + "\0").encode() + canonical_bytes(value)).hexdigest()


def index(snapshot):
    return {n["id"]: n for n in snapshot["content"]["nodes"]}


def references(value):
    return [v for v, _ in semantic_walk(value) if isinstance(v, dict) and set(v) == {"id", "revision"}]


def graph(snapshot):
    return {id: {r["id"] for r in references(n)} for id, n in index(snapshot).items()}


def closure(seeds, edges):
    seen, pending = set(), list(seeds)
    while pending:
        id = pending.pop()
        if id not in seen:
            seen.add(id)
            pending.extend(edges.get(id, set()) - seen)
    return seen


def reverse(edges):
    result = {}
    for source, targets in edges.items():
        for target in targets:
            result.setdefault(target, set()).add(source)
    return result


def rewrite(value, revisions, replacements):
    if isinstance(value, dict):
        if set(value) == {"id", "revision"}:
            id = value["id"]
            if id in revisions:
                prior, current = revisions[id]
                if value["revision"] not in {prior, current}:
                    raise ChangeError("REVISION", "Reference has an unexpected prior revision.")
                if id in replacements:
                    id = replacements[id]
                return {"id": id, "revision": revisions.get(id, (value["revision"], value["revision"]))[1]}
            return copy.deepcopy(value)
        literal = value.get("tag") == "literal" or set(value) == {"type", "value"}
        return {k: copy.deepcopy(v) if literal and k == "value" else rewrite(v, revisions, replacements)
                for k, v in value.items()}
    if isinstance(value, list):
        return [rewrite(v, revisions, replacements) for v in value]
    return value


def normalize_content(content):
    """Structural witnesses only, as in Phase 2; actual admission is separate."""
    authoring = {"modelVersion": "0.2.0", "applicationId": content["applicationId"], "snapshotId": "CHANGE-CANDIDATE",
        "nodes": content["nodes"], "issues": content["issues"], "approvals": [
            {"subject": {"id": n["id"], "revision": n["revision"]}, "reviewer": "structural-only", "evidence": "not-authority"}
            for n in content["nodes"]]}
    try:
        return normalize_candidate(authoring)
    except CanonicalError:
        raise ChangeError("SEMANTIC", "Candidate fails the accepted canonical semantic contract.") from None


def check_sources(sources):
    for item in sources:
        try:
            if set(item) != {"source", "receipt"} or migrate_authoring(item["source"]) != item["receipt"]:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise ChangeError("SOURCE", "Source receipt does not reproduce its declared canonical import.") from None


def seal(body):
    return {**body, "planDigest": fingerprint(body, "plan")}


def request(plan):
    return {"applicationId": plan["candidate"]["content"]["applicationId"], "author": plan["author"],
        "planDigest": plan["planDigest"], "contentDigest": plan["candidate"]["contentDigest"],
        "requiredScopes": plan["requiredScopes"]}


def genesis(source, author):
    receipt = migrate_authoring(source)
    return seal({"planVersion": "0.1.0", "kind": "INITIALIZE", "author": author,
        "candidate": receipt["candidate"], "sources": [{"source": copy.deepcopy(source), "receipt": receipt}],
        "requiredScopes": ["SEMANTIC", "SECURITY"], "change": None})


def semantic_diff(before, after):
    old, new = index(before), index(after)
    result = []
    for id in sorted(set(old) | set(new)):
        a, b = old.get(id), new.get(id)
        if a != b:
            fields = sorted(k for k in set(a or {}) | set(b or {}) if (a or {}).get(k) != (b or {}).get(k))
            result.append({"id": id, "operation": "ADD" if a is None else "RETIRE" if b is None else "REVISE",
                           "before": a, "after": b, "fields": fields})
    return result


def prepare(base, change):
    try:
        canonical_bytes(change)
        valid = SHAPES.is_valid(change)
    except (ValueError, RecursionError):
        valid = False
    if not valid:
        raise ChangeError("SHAPE", "ChangeSet violates the closed versioned input contract.")
    validate_snapshot(base)
    if change["base"]["digest"] != base["contentDigest"]:
        raise ChangeError("BASE", "ChangeSet does not bind the supplied base snapshot.")
    check_sources(change["sources"])
    old = index(base)
    nodes = copy.deepcopy(old)
    direct, replacements = set(), {}
    for op in change["operations"]:
        id = op["node"]["id"] if op["op"] == "ADD" else op["id"]
        if id in direct:
            raise ChangeError("OPERATION", "Only one explicit operation per semantic ID is allowed.")
        direct.add(id)
        if op["op"] == "ADD":
            if id in old or op["node"]["revision"] != 1 or op["node"]["lifecycle"] != "APPROVED":
                raise ChangeError("IDENTITY", "ADD requires a fresh ID, revision one and active candidate.")
            nodes[id] = copy.deepcopy(op["node"])
            continue
        if id not in old or op["expectedRevision"] != old[id]["revision"]:
            raise ChangeError("REVISION", "Expected prior revision is stale or missing.")
        if op["op"] == "REVISE":
            n = op["node"]
            if (n["id"] != id or n["kind"] != old[id]["kind"] or n["revision"] != old[id]["revision"] + 1
                    or n["lifecycle"] != old[id]["lifecycle"]):
                raise ChangeError("REVISION", "REVISE preserves ID, kind and lifecycle and advances exactly one revision.")
            if {k: v for k, v in n.items() if k != "revision"} == {k: v for k, v in old[id].items() if k != "revision"}:
                raise ChangeError("OPERATION", "A revision-only edit is not a semantic operation.")
            nodes[id] = copy.deepcopy(n)
        elif op["op"] == "DEPRECATE":
            if old[id]["lifecycle"] != "APPROVED":
                raise ChangeError("LIFECYCLE", "Only an approved active concept can become deprecated.")
            nodes[id].update(lifecycle="DEPRECATED", revision=old[id]["revision"] + 1)
        else:
            replacements[id] = op["replacement"]["id"]
    for op in change["operations"]:
        if op["op"] != "SUPERSEDE":
            continue
        id, target = op["id"], op["replacement"]["id"]
        if (target == id or target in replacements or target not in nodes or
                nodes[target]["kind"] != old[id]["kind"] or nodes[target]["lifecycle"] != "APPROVED" or
                op["replacement"]["revision"] != nodes[target]["revision"]):
            raise ChangeError("SUPERSESSION", "Supersession requires a different, current, active same-kind replacement.")
        del nodes[id]
    authored_data_changes = {id for id in direct & set(old) if id not in nodes or old[id]["data"] != nodes[id]["data"]}
    lifecycle_changed = any(id in old and id in nodes and old[id]["lifecycle"] != nodes[id]["lifecycle"] for id in direct)
    # Exact references cause explicit, deterministic dependent revision advancement.
    edges = graph(base)
    for id, n in nodes.items():
        edges.setdefault(id, set()).update(r["id"] for r in references(n))
    affected = closure(direct, reverse(edges))
    revisions = {id: (n["revision"], n["revision"] + 1 if id in affected else n["revision"]) for id, n in old.items()}
    revisions.update({id: (0, 1) for id in nodes if id not in old})
    for id, n in nodes.items():
        if id in affected and id in old:
            n["revision"] = revisions[id][1]
    nodes = {id: rewrite(n, revisions, replacements) for id, n in nodes.items()}
    content = {**copy.deepcopy(base["content"]), "nodes": list(nodes.values()),
               "issues": rewrite(base["content"]["issues"], revisions, replacements)}
    candidate = normalize_content(content)
    diff = semantic_diff(base, candidate)
    if not diff:
        raise ChangeError("OPERATION", "ChangeSet has no semantic effect.")
    actual = index(candidate)
    for id in direct & set(old) & set(actual):
        if {k: v for k, v in actual[id].items() if k != "revision"} == {k: v for k, v in old[id].items() if k != "revision"}:
            raise ChangeError("OPERATION", "A revision-only change without changed content is forbidden.")
    write_ids = {d["id"] for d in diff}
    combined = graph(base)
    for id, targets in graph(candidate).items():
        combined.setdefault(id, set()).update(targets)
    impact = sorted(closure(write_ids, reverse(combined)))
    reads = closure(set(impact), combined) & set(old)
    for r in change["reads"]:
        if r["id"] not in old or old[r["id"]]["revision"] != r["revision"]:
            raise ChangeError("READSET", "Declared read has a stale or missing revision.")
        reads.update(closure({r["id"]}, combined) & set(old))
    read_set = [{"id": id, "revision": old[id]["revision"], "digest": fingerprint(old[id], "node")} for id in sorted(reads)]
    read_set += [{"id": id, "revision": 0, "digest": None} for id in sorted(write_ids - set(old))]
    kinds = {nodes[id]["kind"] if id in nodes else old[id]["kind"] for id in direct}
    scopes = {"SEMANTIC"}
    if kinds & SECURITY or any((nodes.get(id) or old[id])["kind"] in {"Field", "Entity"}
                              for id in (authored_data_changes | (direct - set(old)))):
        scopes.add("SECURITY")
    if any(old.get(id, {}).get("kind") == "Decision" and old[id]["data"]["strength"] == "LOCKED" for id in direct):
        scopes.add("LOCKED_DECISION")
    structural = any(old[id]["kind"] in DATA for id in authored_data_changes)
    structural |= any(id not in old and nodes[id]["kind"] == "Field" and not nodes[id]["data"]["optional"] for id in direct)
    migration = change["migration"]
    if migration["compatibility"] == "UNKNOWN":
        raise ChangeError("MIGRATION", "Unknown migration compatibility blocks approval.")
    if structural and migration["mode"] != "REQUIRED":
        raise ChangeError("MIGRATION", "Structural data changes require an explicit migration plan.")
    if migration["mode"] == "REQUIRED":
        scopes.add("MIGRATION")
        if not all(migration[k] for k in ("steps", "preconditions", "verification", "recovery")):
            raise ChangeError("MIGRATION", "Required migration is missing its execution/recovery obligations.")
    elif migration["irreversible"] or migration["steps"] or migration["compatibility"] != "BACKWARD":
        raise ChangeError("MIGRATION", "NONE cannot carry migration steps, breakage or irreversible work.")
    if migration["irreversible"]:
        scopes.add("IRREVERSIBLE")
    meaning_changed = bool(authored_data_changes) or lifecycle_changed
    risk = "CRITICAL" if migration["irreversible"] else "HIGH" if len(scopes) > 1 or replacements else "REVIEW" if meaning_changed or kinds & WORKFLOW else "LOW"
    compatible = "BREAKING" if replacements or migration["compatibility"] == "BREAKING" else "REVIEW_REQUIRED" if meaning_changed or structural or kinds & (SECURITY | WORKFLOW) else "BACKWARD"
    tombstones = [{**copy.deepcopy(old[id]), "revision": old[id]["revision"] + 1, "lifecycle": "SUPERSEDED",
                   "supersededBy": {"id": target, "revision": actual[target]["revision"]}} for id, target in sorted(replacements.items())]
    provenance = [{"concept": {"id": id, "revision": n["revision"]}, "basis": n["basis"],
                   "origins": n["origins"], "changeId": change["id"], "snapshotDigest": candidate["contentDigest"]}
                  for id, n in sorted(actual.items()) if id in write_ids]
    return seal({"planVersion": "0.1.0", "kind": "CHANGE", "author": change["author"], "change": copy.deepcopy(change),
        "candidate": candidate, "readSet": read_set, "writeSet": sorted(write_ids), "diff": diff,
        "impact": {"semanticIds": impact, "external": "NOT_ANALYZED", "method": "exact-reference-closure-v1"},
        "risk": risk, "compatibility": compatible, "requiredScopes": sorted(scopes), "tombstones": tombstones,
        "dataEffect": "DECLARED_IRREVERSIBLE" if migration["irreversible"] else "REQUIRES_DATA_REVIEW" if structural or replacements else "NO_DATA_CHANGE_INFERRED",
        "provenance": provenance, "evidenceStaleness": {"priorSnapshot": base["contentDigest"], "reason": "EXACT_SNAPSHOT_CHANGED"}})


def stale_reads(plan, current):
    now = index(current)
    return sorted(r["id"] for r in plan["readSet"] if
        (r["revision"] == 0 and r["id"] in now) or
        (r["revision"] != 0 and (r["id"] not in now or fingerprint(now[r["id"]], "node") != r["digest"])))


def rebase_conflicts(plan, base, current):
    changed = {d["id"] for d in semantic_diff(base, current)}
    conflicts = set(stale_reads(plan, current))
    # New incoming dependencies are semantic changes, even if the original reads survive.
    conflicts.update(changed & closure(set(plan["writeSet"]), reverse(graph(current))))
    old, new = index(base), index(current)
    planned_kinds = {d["after"]["kind"] if d["after"] else d["before"]["kind"] for d in plan["diff"]}
    concurrent_kinds = {(new.get(id) or old[id])["kind"] for id in changed}
    for fence in (SECURITY, WORKFLOW):
        if planned_kinds & fence and concurrent_kinds & fence:
            conflicts.update(changed)
    return sorted(conflicts)


def evidence_state(evidence, snapshot):
    nodes = index(snapshot)
    if evidence["snapshotDigest"] != snapshot["contentDigest"] or any(
            r["id"] not in nodes or nodes[r["id"]]["revision"] != r["revision"] for r in evidence["subjects"]):
        return "STALE"
    return evidence["result"]
