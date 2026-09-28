"""Reproduce reference-storage size/recovery observations using synthetic domains."""
import json
from pathlib import Path
import platform
import sqlite3
import tempfile

from canonical_fixtures import synthetic_approved
from canonical_json import canonical_bytes
from change_fixtures import STEPS, evolution_change
from changes import genesis, request
from history_repository import HistoryRepository
from reference_authority import ReferenceAuthority
from reference_models import models


def run():
    results = []
    for name, model in models().items():
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.sqlite"
            repo = HistoryRepository(path)
            app = model["applicationId"]
            auth = ReferenceAuthority(b"synthetic-experiment-key-not-production" * 2,
                {"synthetic-author-session": "author", "synthetic-review-session": "reviewer"},
                {"reviewer": [app + ":" + scope for scope in ("SEMANTIC", "SECURITY", "MIGRATION", "IRREVERSIBLE", "LOCKED_DECISION")]})
            initial = genesis(synthetic_approved(model), "author")
            repo.bootstrap(initial, auth.issue("synthetic-review-session", request(initial), 1000), auth, 1000, "synthetic-author-session")
            initial_bytes = path.stat().st_size
            for step in STEPS:
                p = repo.propose(evolution_change(repo.snapshot(), repo.head(), step), auth, "synthetic-author-session")
                id = p["change"]["id"]
                repo.review(id, auth, "synthetic-author-session")
                repo.approve(id, auth.issue("synthetic-review-session", request(p), 1000), auth, 1000)
                repo.apply(id, "retry-" + step, auth, 1000)
            anchor = repo.head()
            audited = HistoryRepository(path).audit(anchor, authority=auth)
            exported = repo.export_records()
            results.append({"domain": name, "entries": audited["entries"], "initialDatabaseBytes": initial_bytes,
                "finalDatabaseBytes": path.stat().st_size,
                "snapshotPayloadBytes": sum(len(canonical_bytes(b)) for kind, _, b in exported["records"] if kind == "snapshot"),
                "journalPayloadBytes": sum(len(canonical_bytes(row[-1])) for row in exported["journal"]),
                "proposalPayloadBytes": sum(len(canonical_bytes(row[-1])) for row in exported["proposals"]),
                "reopenAndAnchoredAudit": "PASS", "finalContentDigest": anchor["digest"]})
    return {"experiment": "synthetic-six-snapshot-storage-v1", "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version, "platform": platform.system(), "results": results}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
