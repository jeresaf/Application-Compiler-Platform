"""Reuse the R7 compiler, Canonical candidate, ArtifactPlan and ownership publisher."""
from pathlib import Path
from engineering.jobs.application import JobApplication
from engineering.jobs.compiler import fixture_context
from engineering.jobs.reference import proposal
from engineering.hardening.target import HardeningTarget
from filesystem_artifacts import FilesystemArtifactStore


class HardeningApplication(JobApplication):
    def __init__(self):
        self.native = HardeningTarget()
        self.source, self.context = fixture_context(proposal(), self.native)
        self.generator, self.bundle = self.native.generator, self.native.bundle
        self.targets, self.audit = self.native.targets, None


def materialize(root):
    candidate = HardeningApplication()
    request = candidate.context.request
    snapshot = candidate.context.snapshots.read_exact(request.application, request.snapshot_digest)
    plan = candidate.plan(snapshot, request)
    FilesystemArtifactStore(Path(root)).apply(plan)
    candidate.verify_materialized(root, plan, snapshot, request)
    return candidate, snapshot, request, plan
