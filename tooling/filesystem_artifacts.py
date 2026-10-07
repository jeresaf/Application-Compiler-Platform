"""Linux engineering adapter: confined, locked, atomic complete-tree publication.

Semantic contracts remain platform neutral. Linux renameat2 is an implementation
choice for exchanging an existing directory without a partially published tree.
"""
import ctypes
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

from compiler_contracts import Document, ExistingArtifact, Owner, fingerprint
from compiler_core import safe_path, validate_plan


class StoreConflict(ValueError):
    pass


@dataclass(frozen=True)
class ApprovedAICandidate:
    """Host policy result, not a worker-supplied approval flag."""
    content_digest: str
    provenance: Document

    def validate(self, digest):
        value = self.provenance.read()
        return (self.content_digest == digest and set(value) == {"provider", "model", "inputDigest", "outputDigest", "approvalPolicy", "approvalEvidence"}
                and all(type(v) is str and v for v in value.values()) and value["outputDigest"] == digest)


def source_bytes(document):
    value = document.read()
    if set(value) != {"encoding", "text"} or value["encoding"] != "UTF-8" or type(value["text"]) is not str:
        raise StoreConflict("SOURCE_ENCODING")
    if "\r" in value["text"] or "\x00" in value["text"]:
        raise StoreConflict("SOURCE_ENCODING")
    return value["text"].encode("utf-8")


def byte_digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


class FilesystemArtifactStore:
    META = ".acp-store.json"
    ALLOWED_BUILD_SCOPES = frozenset({"backend/target", "frontend/node_modules", "frontend/dist"})

    def __init__(self, root, *, ephemeral_build_scopes=()):
        self.root = Path(os.path.abspath(root))
        self.build_scopes = frozenset(ephemeral_build_scopes)
        if not self.build_scopes <= self.ALLOWED_BUILD_SCOPES:
            raise StoreConflict("BUILD_SCOPE")
        # Reject symlinks in every existing ancestor, including the store root.
        for p in (self.root, *self.root.parents):
            if p.is_symlink():
                raise StoreConflict("SYMLINK")
        self.root.parent.mkdir(parents=True, exist_ok=True)

    def _records(self):
        if not self.root.exists():
            return {}
        if not self.root.is_dir():
            raise StoreConflict("ROOT_TYPE")
        metadata = self.root / self.META
        if metadata.is_symlink():
            raise StoreConflict("SYMLINK")
        records = json.loads(metadata.read_text()) if metadata.exists() else {}
        observed = set()
        for base, dirs, files in os.walk(self.root, followlinks=False):
            for name in tuple(dirs):
                path = Path(base) / name
                if path.relative_to(self.root).as_posix() in self.build_scopes:
                    if path.is_symlink():
                        raise StoreConflict("SYMLINK")
                    dirs.remove(name)
            for name in (*dirs, *files):
                path = Path(base) / name
                if path.is_symlink():
                    raise StoreConflict("SYMLINK")
                if not (path.is_dir() or stat.S_ISREG(path.stat().st_mode)):
                    raise StoreConflict("FILE_TYPE")
            for name in files:
                path = Path(base) / name
                relative = path.relative_to(self.root).as_posix()
                if relative == self.META:
                    continue
                safe_path(relative)
                record = records.get(relative)
                if record is None or record.get("owner") not in set(Owner):
                    raise StoreConflict("UNKNOWN_OWNERSHIP")
                data = path.read_bytes()
                # Human edits are retained and their current digest enters CAS.
                if record["owner"] == Owner.HUMAN:
                    record = dict(record, bytes=byte_digest(data), digest=fingerprint(
                        Document.of({"encoding": "UTF-8", "text": data.decode("utf-8")}), "artifact-content"))
                    records[relative] = record
                elif byte_digest(data) != record["bytes"]:
                    raise StoreConflict("MANUAL_EDIT")
                observed.add(relative)
        if observed != set(records):
            raise StoreConflict("MISSING_ARTIFACT")
        return records

    def inventory(self):
        return tuple(ExistingArtifact(path, r["digest"], Owner(r["owner"]))
                     for path, r in sorted(self._records().items()))

    def apply(self, plan, *, framework_upgrades=(), ai_approvals=None):
        lock = self.root.parent / ("." + self.root.name + ".acp-lock")
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            records = self._records()
            inventory = tuple(ExistingArtifact(p, r["digest"], Owner(r["owner"])) for p, r in sorted(records.items()))
            validate_plan(plan, inventory, plan.obligations)
            for artifact in plan.artifacts:
                if any(artifact.path == scope or artifact.path.startswith(scope + "/") for scope in self.build_scopes):
                    raise StoreConflict("BUILD_SCOPE_WRITE")
                if artifact.path == self.META:
                    raise StoreConflict("RESERVED_PATH")
                source_bytes(artifact.content)
                if artifact.owner == Owner.FRAMEWORK and artifact.intent == "UPDATE" and artifact.path not in framework_upgrades:
                    raise StoreConflict("FRAMEWORK_UPGRADE_REQUIRED")
                if artifact.owner == Owner.AI:
                    approval = (ai_approvals or {}).get(artifact.path)
                    if type(approval) is not ApprovedAICandidate or not approval.validate(artifact.content_digest):
                        raise StoreConflict("AI_APPROVAL_REQUIRED")
            stage = Path(tempfile.mkdtemp(prefix="." + self.root.name + ".acp-stage-", dir=self.root.parent))
            try:
                if self.root.exists():
                    def ignored(base, names):
                        return [name for name in names if (Path(base) / name).relative_to(self.root).as_posix() in self.build_scopes]
                    shutil.copytree(self.root, stage, dirs_exist_ok=True, symlinks=False, ignore=ignored)
                updated = dict(records)
                for artifact in plan.artifacts:
                    if artifact.intent == "NO_OP":
                        continue
                    destination = stage / artifact.path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    data = source_bytes(artifact.content)
                    destination.write_bytes(data)
                    updated[artifact.path] = {"digest": artifact.content_digest, "bytes": byte_digest(data), "owner": str(artifact.owner)}
                (stage / self.META).write_text(json.dumps(updated, sort_keys=True, separators=(",", ":")) + "\n")
                # Recheck original bytes after staging. No writes precede publication.
                if records != self._records():
                    raise StoreConflict("CAS_CHANGED")
                for path in stage.rglob("*"):
                    if path.is_file():
                        with path.open("rb") as handle:
                            os.fsync(handle.fileno())
                if self.root.exists():
                    libc = ctypes.CDLL(None, use_errno=True)
                    if libc.renameat2(-100, os.fsencode(stage), -100, os.fsencode(self.root), 2):
                        raise OSError(ctypes.get_errno(), "atomic directory exchange failed")
                else:
                    os.rename(stage, self.root)
                parent_fd = os.open(self.root.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)

    def adopt_human(self, relative):
        """Explicit handoff of an existing extension; never creates or edits source."""
        safe_path(relative)
        if not relative.startswith(("backend/src/main/java/acp/extensions/", "frontend/src/extensions/")):
            raise StoreConflict("EXTENSION_ONLY")
        lock = self.root.parent / ("." + self.root.name + ".acp-lock")
        fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            records = self._records()
            if relative not in records:
                raise StoreConflict("UNKNOWN_ARTIFACT")
            records[relative]["owner"] = str(Owner.HUMAN)
            temporary = self.root / (self.META + ".pending")
            temporary.write_text(json.dumps(records, sort_keys=True, separators=(",", ":")) + "\n")
            os.replace(temporary, self.root / self.META)
