"""Ordinary compiler/ArtifactPlan publication of the proposed reporting application."""
from engineering.reporting.compiler import fixture_context,compile_pipeline
from engineering.reporting.reference import proposal
from engineering.reporting.target import ReportingTarget
from engineering.native_create.application import NativeApplication as Base
from compiler_contracts import Success
from filesystem_artifacts import FilesystemArtifactStore
from pathlib import Path
from dataclasses import replace
class ReportingApplication(Base):
 def __init__(self):
  self.native=ReportingTarget();self.source,self.context=fixture_context(proposal(),self.native);self.generator=self.native.generator;self.bundle=self.native.bundle;self.targets=self.native.targets;self.audit=None
 def plan(self,snapshot,request,inventory=()):
  if request!=self.context.request or snapshot!=self.context.snapshots.read_exact(request.application,request.snapshot_digest):raise ValueError('REPORT_REQUEST')
  result=compile_pipeline(self.source,replace(self.context,inventory=tuple(inventory)))
  if not isinstance(result.result,Success):raise ValueError('REPORT_COMPILER:'+','.join(str(d.stage)+':'+d.code for d in result.result.diagnostics))
  self.audit=result.audit;return result.result.output

def materialize(root):
 c=ReportingApplication();r=c.context.request;s=c.context.snapshots.read_exact(r.application,r.snapshot_digest);p=c.plan(s,r);FilesystemArtifactStore(Path(root)).apply(p);c.verify_materialized(root,p,s,r);return c,s,r,p
