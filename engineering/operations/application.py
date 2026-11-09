"""H6 uses the existing native compiler and ownership publisher."""
from engineering.identity.application import IdentityApplication
from engineering.operations.target import OperationalTarget
from engineering.jobs.compiler import fixture_context
from engineering.jobs.reference import proposal
from filesystem_artifacts import FilesystemArtifactStore
class OperationalApplication(IdentityApplication):
    def __init__(self):
        self.native=OperationalTarget();self.source,self.context=fixture_context(proposal(),self.native);self.generator,self.bundle=self.native.generator,self.native.bundle;self.targets,self.audit=self.native.targets,None

def materialize(root):
    c=OperationalApplication();r=c.context.request;s=c.context.snapshots.read_exact(r.application,r.snapshot_digest);p=c.plan(s,r);FilesystemArtifactStore(root).apply(p);c.verify_materialized(root,p,s,r);return c,s,r,p
