"""Host-supervised Phase 6 target adapter. No semantic-history write capability."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from compiler_contracts import Artifact, ArtifactPlan, Document, Owner, Provenance, Stage, fingerprint
from compiler_reference import SyntheticTarget

ROOT = Path(__file__).resolve().parents[1] / "targets/spring-vue-postgres"
PROFILE = json.loads((ROOT / "profile.json").read_text())


class TargetWorkerError(ValueError):
    pass


def bundle_digest():
    files = [ROOT / "profile.json", *sorted((ROOT / "worker").glob("*.py")), *sorted((ROOT / "templates").rglob("*"))]
    digest = hashlib.sha256()
    for path in files:
        if path.is_file():
            digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


class TargetWorker:
    protocol = PROFILE["protocol"]

    def call(self, operation, payload, *, cwd=None):
        envelope = {"protocol": self.protocol, "operation": operation, "payload": payload}
        raw = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode()
        if len(raw) > 4000000:
            raise TargetWorkerError("RESOURCE_INPUT")
        try:
            result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "worker/main.py")],
                input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd or "/",
                env={"LC_ALL": "C", "PYTHONHASHSEED": "0"}, timeout=30, check=False)
        except (subprocess.TimeoutExpired, OSError):
            raise TargetWorkerError("WORKER_UNAVAILABLE") from None
        if result.returncode or len(result.stdout) > 16000000 or result.stderr:
            raise TargetWorkerError("WORKER_FAILED")
        try:
            response = json.loads(result.stdout)
            if response["ok"] is not True:
                raise TargetWorkerError(response["error"])
            if set(response) != {"ok", "result"}:
                raise ValueError()
            return response["result"]
        except (KeyError, TypeError, json.JSONDecodeError, ValueError) as error:
            if isinstance(error, TargetWorkerError):
                raise
            raise TargetWorkerError("WORKER_PROTOCOL") from None


class ProductionTarget(SyntheticTarget):
    """Reference host adapter; worker cannot approve snapshots or decisions."""
    identity = PROFILE["profile"]
    capabilities = ("target.project-artifacts/1", "target.semantic-coverage/1")

    def __init__(self):
        self.worker = TargetWorker()
        self.generator = PROFILE["generator"] + "+sha256:" + bundle_digest()

    def lower(self, realization, request):
        choices = {d.role: d.choice.read().get("choice") for d in (*realization.architecture, *realization.design)}
        payload = {"nodes": sorted((o.semantic.read() for o in realization.objects), key=lambda n: n["id"]),
                   "required": [], "decisions": choices}
        # Host approved decisions are checked by compiler_core before this port.
        model = self.worker.call("lower", payload)
        expected = payload["nodes"]
        if model.get("nodes") != expected or model.get("profile") != self.identity or model.get("version") != "0.1.0":
            raise TargetWorkerError("LOWER_PROVENANCE")
        neutral = super().lower(realization, request)
        return replace(neutral, target_model=Document.of(model))

    def plan(self, target, request, *, inventory=()):
        model = target.target_model.read()
        rows = self.worker.call("plan", {"model": model, "inventory": [
            {"path": item.path, "digest": item.digest, "owner": str(item.owner)} for item in inventory]})
        self.worker.call("validate-plan", {"artifacts": rows})
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
