"""Linux engineering adapter: confined, locked, atomic complete-tree publication.

Semantic contracts remain platform neutral. Linux renameat2 is an implementation
choice for exchanging an existing directory without a partially published tree.
"""
import ctypes
from dataclasses import dataclass
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import uuid

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
        parent = self._open_directory(self.root.parent, create=True)
        os.close(parent)

    @staticmethod
    def _open_directory(path, *, create=False):
        """Walk absolute components without following any ancestor symlink."""
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for name in Path(path).parts[1:]:
                if create:
                    try:
                        os.mkdir(name, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                try:
                    child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                except OSError:
                    raise StoreConflict("DIRECTORY_BINDING") from None
                os.close(fd)
                fd = child
            return fd
        except BaseException:
            os.close(fd)
            raise

    @staticmethod
    def _identity(fd):
        value = os.fstat(fd)
        return value.st_dev, value.st_ino

    @contextmanager
    def _parent(self, *, locked=False):
        parent = self._open_directory(self.root.parent)
        lock_fd = None
        try:
            if locked:
                lock_fd = os.open("." + self.root.name + ".acp-lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
                if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
                    raise StoreConflict("LOCK_TYPE")
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield parent
        finally:
            if lock_fd is not None:
                os.close(lock_fd)
            os.close(parent)

    def _namespace(self, parent):
        current = self._open_directory(self.root.parent)
        try:
            if self._identity(current) != self._identity(parent):
                raise StoreConflict("DIRECTORY_BINDING")
        finally:
            os.close(current)

    @staticmethod
    def _read_file(directory, name):
        try:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except OSError:
            raise StoreConflict("FILE_BINDING") from None
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_size > 16000000:
                raise StoreConflict("FILE_TYPE_OR_LIMIT")
            data = bytearray()
            while True:
                block = os.read(fd, min(65536, 16000001 - len(data)))
                if not block:
                    break
                data.extend(block)
                if len(data) > 16000000:
                    raise StoreConflict("FILE_LIMIT")
            after = os.fstat(fd)
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise StoreConflict("FILE_CHANGED")
            return bytes(data), stat.S_IMODE(before.st_mode)
        finally:
            os.close(fd)

    def _scan(self, parent, name=None):
        name = name or self.root.name
        try:
            root = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        except FileNotFoundError:
            return ({}, {}, {}, None, None)
        except OSError:
            raise StoreConflict("ROOT_BINDING") from None
        try:
            identity = self._identity(root)
            try:
                meta, _ = self._read_file(root, self.META)
            except StoreConflict:
                if self.META in os.listdir(root):
                    raise
                meta = None
            try:
                records = json.loads(meta) if meta is not None else {}
            except (ValueError, TypeError):
                raise StoreConflict("METADATA") from None
            if type(records) is not dict:
                raise StoreConflict("METADATA")
            files, modes = {}, {}

            def walk(directory, prefix=""):
                for entry in sorted(os.listdir(directory)):
                    relative = prefix + entry
                    safe_path(relative)
                    observed = os.stat(entry, dir_fd=directory, follow_symlinks=False)
                    if stat.S_ISLNK(observed.st_mode):
                        raise StoreConflict("SYMLINK")
                    if stat.S_ISDIR(observed.st_mode):
                        if relative in self.build_scopes:
                            continue
                        child = os.open(entry, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                        try:
                            if self._identity(child) != (observed.st_dev, observed.st_ino):
                                raise StoreConflict("DIRECTORY_CHANGED")
                            walk(child, relative + "/")
                        finally:
                            os.close(child)
                        continue
                    if relative == self.META:
                        continue
                    record = records.get(relative)
                    if type(record) is not dict or set(record) != {"owner", "bytes", "digest"} or record["owner"] not in set(Owner):
                        raise StoreConflict("UNKNOWN_OWNERSHIP")
                    data, mode = self._read_file(directory, entry)
                    try:
                        digest = fingerprint(Document.of({"encoding": "UTF-8", "text": data.decode("utf-8")}), "artifact-content")
                    except (ValueError, UnicodeError):
                        raise StoreConflict("SOURCE_ENCODING") from None
                    if record["owner"] == Owner.HUMAN:
                        records[relative] = dict(record, bytes=byte_digest(data), digest=digest)
                    elif byte_digest(data) != record["bytes"] or digest != record["digest"]:
                        raise StoreConflict("MANUAL_EDIT")
                    files[relative], modes[relative] = data, mode
            walk(root)
            if set(files) != set(records):
                raise StoreConflict("MISSING_ARTIFACT")
            return records, files, modes, identity, meta
        finally:
            os.close(root)

    def _records(self):
        with self._parent() as parent:
            return self._scan(parent)[0]

    def inventory(self):
        return tuple(ExistingArtifact(path, r["digest"], Owner(r["owner"]))
                     for path, r in sorted(self._records().items()))

    def _write_file(self, root, relative, data, mode=0o644):
        parts = relative.split("/")
        directory = os.dup(root)
        try:
            for part in parts[:-1]:
                try:
                    os.mkdir(part, 0o700, dir_fd=directory)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=directory)
            try:
                offset = 0
                while offset < len(data):
                    offset += os.write(fd, data[offset:offset + 65536])
                os.fchmod(fd, mode)
                os.fsync(fd)
            finally:
                os.close(fd)
            os.fsync(directory)
        finally:
            os.close(directory)

    def _checkpoint(self, phase):
        """Trusted test seam for crashes/races; no generated semantic effects."""

    def _publish(self, parent, snapshot, records, files, modes):
        stage_name = "." + self.root.name + ".acp-stage-" + uuid.uuid4().hex
        os.mkdir(stage_name, 0o700, dir_fd=parent)
        stage = os.open(stage_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            for relative, data in sorted(files.items()):
                self._write_file(stage, relative, data, modes.get(relative, 0o644))
            metadata = (json.dumps(records, sort_keys=True, separators=(",", ":")) + "\n").encode()
            self._write_file(stage, self.META, metadata, 0o600)
            os.fsync(stage)
            self._checkpoint("STAGED")
            self._namespace(parent)
            if snapshot != self._scan(parent):
                raise StoreConflict("CAS_CHANGED")
            staged = self._scan(parent, stage_name)
            if staged[:3] != (records, files, {key: modes.get(key, 0o644) for key in files}) or staged[3] != self._identity(stage):
                raise StoreConflict("STAGE_CHANGED")
            if snapshot[3] is not None:
                libc = ctypes.CDLL(None, use_errno=True)
                if libc.renameat2(parent, os.fsencode(stage_name), parent, os.fsencode(self.root.name), 2):
                    raise OSError(ctypes.get_errno(), "atomic directory exchange failed")
            else:
                # NOREPLACE prevents an unexpected root from being overwritten.
                libc = ctypes.CDLL(None, use_errno=True)
                if libc.renameat2(parent, os.fsencode(stage_name), parent, os.fsencode(self.root.name), 1):
                    raise StoreConflict("ROOT_CHANGED")
            os.fsync(parent)
        finally:
            os.close(stage)
            # The directory descriptor pins the parent if its pathname moved.
            # rmtree's fd-based implementation refuses symlink traversal.
            try:
                shutil.rmtree(stage_name, dir_fd=parent)
            except FileNotFoundError:
                pass

    def apply(self, plan, *, framework_upgrades=(), ai_approvals=None):
        with self._parent(locked=True) as parent:
            snapshot = self._scan(parent)
            records, files, modes = snapshot[:3]
            inventory = tuple(ExistingArtifact(p, r["digest"], Owner(r["owner"])) for p, r in sorted(records.items()))
            validate_plan(plan, inventory, plan.obligations)
            updated_records, updated_files = dict(records), dict(files)
            for artifact in plan.artifacts:
                if any(artifact.path == scope or artifact.path.startswith(scope + "/") for scope in self.build_scopes):
                    raise StoreConflict("BUILD_SCOPE_WRITE")
                if artifact.path == self.META:
                    raise StoreConflict("RESERVED_PATH")
                data = source_bytes(artifact.content)
                if artifact.owner == Owner.FRAMEWORK and artifact.intent == "UPDATE" and artifact.path not in framework_upgrades:
                    raise StoreConflict("FRAMEWORK_UPGRADE_REQUIRED")
                if artifact.owner == Owner.AI:
                    approval = (ai_approvals or {}).get(artifact.path)
                    if type(approval) is not ApprovedAICandidate or not approval.validate(artifact.content_digest):
                        raise StoreConflict("AI_APPROVAL_REQUIRED")
                if artifact.intent != "NO_OP":
                    updated_files[artifact.path] = data
                    updated_records[artifact.path] = {"digest": artifact.content_digest, "bytes": byte_digest(data), "owner": str(artifact.owner)}
            self._publish(parent, snapshot, updated_records, updated_files, modes)

    def adopt_human(self, relative):
        """Explicit atomic handoff of an existing extension; source is unchanged."""
        safe_path(relative)
        if not relative.startswith(("backend/src/main/java/acp/extensions/", "frontend/src/extensions/")):
            raise StoreConflict("EXTENSION_ONLY")
        with self._parent(locked=True) as parent:
            snapshot = self._scan(parent)
            records, files, modes = snapshot[:3]
            if relative not in records:
                raise StoreConflict("UNKNOWN_ARTIFACT")
            updated = {key: dict(value) for key, value in records.items()}
            updated[relative]["owner"] = str(Owner.HUMAN)
            self._publish(parent, snapshot, updated, files, modes)
