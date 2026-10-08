"""Host-supervised Phase 6 target adapter. No semantic-history write capability."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import time

from compiler_contracts import Artifact, ArtifactPlan, Document, Owner, Provenance, Stage, fingerprint
from compiler_reference import SyntheticTarget

ROOT = Path(__file__).resolve().parents[1] / "targets/spring-vue-postgres"
PROFILE = json.loads((ROOT / "profile.json").read_text())


class TargetWorkerError(ValueError):
    pass


def bundle_digest():
    files = [ROOT / "profile.json", *sorted((ROOT / "worker").glob("*.py")), *sorted((ROOT / "templates").rglob("*"))]
    # Worker confinement now preloads the closed semantic validator. Bind its
    # transitive local modules/schemas as well as target source/templates.
    repository = ROOT.parents[1]
    files += sorted((repository / 'tooling').glob('*.py'))
    files += sorted((repository / 'contracts').glob('*.schema.json'))
    digest = hashlib.sha256()
    for path in files:
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != ROOT.parent):
            raise TargetWorkerError("BUNDLE_SYMLINK")
        if path.is_file():
            digest.update(path.relative_to(repository).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


class TargetWorker:
    protocol = PROFILE["protocol"]

    def __init__(self, *, command=None, timeout=30, output_limit=16000000):
        # Only a trusted host chooses launch commands and stricter limits.
        self.command = tuple(command or (sys.executable, "-I", "-B", str(ROOT / "worker/main.py")))
        if not 0 < timeout <= 30 or type(output_limit) is not int or not 0 < output_limit <= 16000000:
            raise ValueError("WORKER_LIMITS")
        self.timeout = timeout
        self.output_limit = output_limit

    def _exchange(self, raw, cwd):
        try:
            child = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, cwd=cwd or "/", env={"LC_ALL": "C", "PYTHONHASHSEED": "0"},
                start_new_session=True, close_fds=True)
        except OSError:
            raise TargetWorkerError("WORKER_UNAVAILABLE") from None
        stdout, stderr = bytearray(), bytearray()
        offset = 0
        deadline = time.monotonic() + self.timeout
        selector = selectors.DefaultSelector()
        try:
            for stream, event in ((child.stdin, selectors.EVENT_WRITE), (child.stdout, selectors.EVENT_READ), (child.stderr, selectors.EVENT_READ)):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, event)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TargetWorkerError("WORKER_TIMEOUT")
                for key, _ in selector.select(remaining):
                    stream = key.fileobj
                    if stream is child.stdin:
                        try:
                            offset += os.write(stream.fileno(), raw[offset:offset + 65536])
                        except BrokenPipeError:
                            offset = len(raw)
                        if offset == len(raw):
                            selector.unregister(stream)
                            stream.close()
                    else:
                        data = os.read(stream.fileno(), 65536)
                        if not data:
                            selector.unregister(stream)
                            stream.close()
                            continue
                        sink = stdout if stream is child.stdout else stderr
                        limit = self.output_limit if stream is child.stdout else 8192
                        if len(sink) + len(data) > limit:
                            raise TargetWorkerError("WORKER_OUTPUT_LIMIT")
                        sink.extend(data)
            try:
                code = child.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise TargetWorkerError("WORKER_TIMEOUT") from None
            if code < 0:
                raise TargetWorkerError("WORKER_SIGNAL")
            if code:
                raise TargetWorkerError("WORKER_EXIT")
            if stderr:
                raise TargetWorkerError("WORKER_STDERR")
            return bytes(stdout)
        finally:
            selector.close()
            # Kill the process group even if a faulty worker left descendants.
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            for stream in (child.stdin, child.stdout, child.stderr):
                if not stream.closed:
                    stream.close()

    def call(self, operation, payload, *, cwd=None):
        envelope = {"protocol": self.protocol, "operation": operation, "payload": payload}
        raw = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode()
        if len(raw) > 4000000:
            raise TargetWorkerError("RESOURCE_INPUT")
        result = self._exchange(raw, cwd)
        try:
            def unique_pairs(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError()
                    result[key] = value
                return result
            response = json.loads(result, object_pairs_hook=unique_pairs,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
            pending = [(response, 0)]
            count = 0
            while pending:
                value, depth = pending.pop()
                count += 1
                if depth > 128 or count > 200000:
                    raise ValueError()
                if type(value) is dict:
                    pending.extend((item, depth + 1) for item in value.values())
                elif type(value) is list:
                    pending.extend((item, depth + 1) for item in value)
            if type(response) is not dict or type(response.get("ok")) is not bool:
                raise ValueError()
            if response["ok"] is False:
                if set(response) != {"ok", "error"} or type(response["error"]) is not str or not re.fullmatch(r"[A-Za-z0-9_:;/.-]{1,16384}", response["error"]):
                    raise ValueError()
                raise TargetWorkerError(response["error"])
            if set(response) != {"ok", "result"}:
                raise ValueError()
            return response["result"]
        except (KeyError, TypeError, json.JSONDecodeError, ValueError, RecursionError) as error:
            if isinstance(error, TargetWorkerError):
                raise
            raise TargetWorkerError("WORKER_PROTOCOL") from None


class ProductionTarget(SyntheticTarget):
    """Reference host adapter; worker cannot approve snapshots or decisions."""
    identity = PROFILE["profile"]
    capabilities = ("target.project-artifacts/1", "target.semantic-coverage/1", "semantic.execution-dataflow/0.3")

    def __init__(self):
        self.worker = TargetWorker()
        self.last_admission = None
        self.bundle = bundle_digest()
        if json.loads((ROOT / "profile.json").read_text()) != PROFILE:
            raise TargetWorkerError("BUNDLE_CHANGED")
        self.generator = PROFILE["generator"] + "+sha256:" + self.bundle

    def _call(self, operation, payload):
        if bundle_digest() != self.bundle:
            raise TargetWorkerError("BUNDLE_CHANGED")
        result = self.worker.call(operation, payload)
        if bundle_digest() != self.bundle:
            raise TargetWorkerError("BUNDLE_CHANGED")
        return result

    def lower(self, realization, request):
        choices = {d.role: d.choice.read().get("choice") for d in (*realization.architecture, *realization.design)}
        payload = {"nodes": sorted((o.semantic.read() for o in realization.objects), key=lambda n: n["id"]),
                   "required": [c for c in request.required_capabilities if c == 'semantic.execution-dataflow/0.3'], "decisions": choices}
        if 'acp.deterministic-execution.0.4' in request.features:
            payload.update(canonicalVersion='0.3.0', required=['semantic.execution-dataflow/0.3', 'acp.deterministic-execution.0.4'])
        elif 'acp.execution.0.3' in request.features:
            payload.update(canonicalVersion='0.2.0', required=['semantic.execution-dataflow/0.3'])
        # Host approved decisions are checked by compiler_core before this port.
        self.last_admission = {"operation": "lower", "result": "PENDING"}
        try:
            model = self._call("lower", payload)
            self.last_admission = {"operation": "lower", "result": "ACCEPTED"}
        except TargetWorkerError as error:
            self.last_admission = {"operation": "lower", "result": "BLOCKED", "error": str(error)}
            if any(part.startswith('UNSUPPORTED:') for part in str(error).split(';')):
                from compiler_core import CompilerFault
                raise CompilerFault('CAPABILITY') from None
            raise
        expected = payload["nodes"]
        if model.get("nodes") != expected or model.get("profile") != self.identity or model.get("version") != "0.1.0":
            raise TargetWorkerError("LOWER_PROVENANCE")
        neutral = super().lower(realization, request)
        return replace(neutral, target_model=Document.of(model))

    def plan(self, target, request, *, inventory=()):
        model = target.target_model.read()
        rows = self._call("plan", {"model": model, "inventory": [
            {"path": item.path, "digest": item.digest, "owner": str(item.owner)} for item in inventory]})
        self._call("validate-plan", {"artifacts": rows})
        by_id = {o.provenance.origins[0].id: o for o in target.objects}
        artifacts = []
        for row in rows:
            origins = tuple(sorted(by_id[id].provenance.origins[0] for id in row["origins"]))
            inputs = tuple(sorted((*[fingerprint(by_id[s.id]) for s in origins],
                                   fingerprint(target.target_model, "target-model"),
                                   fingerprint(request.generator, "generator-manifest"))))
            provenance = Provenance(origins, Stage.GENERATE, request.compiler, request.pipeline, inputs)
            content = Document.of({"encoding": "UTF-8", "text": row["text"]})
            artifacts.append(Artifact(row["path"], row["role"], content, fingerprint(content, "artifact-content"),
                Owner(row["owner"]), provenance, origins, "CREATE", None, "COMPARE_AND_SWAP",
                tuple(row["verification"]), tuple(sorted({target.source_map.read()[s.id] for s in origins if s.id in target.source_map.read()}))))
        return ArtifactPlan(tuple(artifacts), target.obligations)
