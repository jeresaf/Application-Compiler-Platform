"""Ordinary compiler/ArtifactPlan publication of the proposed background-job application."""
from engineering.jobs.compiler import fixture_context,compile_pipeline
from engineering.jobs.reference import proposal
from engineering.jobs.target import JobTarget
from engineering.native_create.application import NativeApplication as Base
from compiler_contracts import Success
from filesystem_artifacts import FilesystemArtifactStore
from pathlib import Path
from dataclasses import replace
class JobApplication(Base):
 def __init__(self):
  self.native=JobTarget();self.source,self.context=fixture_context(proposal(),self.native);self.generator=self.native.generator;self.bundle=self.native.bundle;self.targets=self.native.targets;self.audit=None
 def plan(self,snapshot,request,inventory=()):
  if request!=self.context.request or snapshot!=self.context.snapshots.read_exact(request.application,request.snapshot_digest):raise ValueError('JOB_REQUEST')
  result=compile_pipeline(self.source,replace(self.context,inventory=tuple(inventory)))
  if not isinstance(result.result,Success):raise ValueError('JOB_COMPILER:'+','.join(str(d.stage)+':'+d.code for d in result.result.diagnostics))
  self.audit=result.audit;return result.result.output

def materialize(root):
 c=JobApplication();r=c.context.request;s=c.context.snapshots.read_exact(r.application,r.snapshot_digest);p=c.plan(s,r);FilesystemArtifactStore(Path(root)).apply(p);c.verify_materialized(root,p,s,r);return c,s,r,p
