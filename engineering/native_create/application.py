"""Existing compiler and ArtifactPlan publication for the explicit CREATE preview."""
from pathlib import Path
from dataclasses import replace
from engineering.native_create.compiler import fixture_context,compile_pipeline
from engineering.native_create.reference import proposal
from engineering.native_create.target import NativeTarget
from engineering.reference_application import lifecycle as life
from engineering.reference_application.intake import TEMPLATES
from engineering.source_intelligence.model import require
from compiler_contracts import Success,Document
from filesystem_artifacts import FilesystemArtifactStore

class NativeApplication:
    def __init__(self):
        self.native=NativeTarget();self.source,self.context=fixture_context(proposal(),self.native)
        self.generator=self.native.generator;self.bundle=self.native.bundle
        self.targets=self.native.targets;self.audit=None
    def plan(self,snapshot,request,inventory=()):
        require(request==self.context.request and snapshot==self.context.snapshots.read_exact(request.application,request.snapshot_digest),'CREATE_APPLICATION_REQUEST')
        result=compile_pipeline(self.source,replace(self.context,inventory=tuple(inventory)))
        require(isinstance(result.result,Success),'CREATE_COMPILATION_FAILED:'+','.join(d.code for d in result.result.diagnostics) if not isinstance(result.result,Success) else '')
        self.audit=result.audit
        return result.result.output
    def lower(self,snapshot,request):
        require(request==self.context.request and snapshot==self.context.snapshots.read_exact(request.application,request.snapshot_digest),'CREATE_APPLICATION_REQUEST')
        return self.targets[(request.snapshot_digest,request.compiler,request.pipeline)]
    def verify_materialized(self,*args):return self.native.verify_materialized(*args)
    def descriptor(self):return self.native.descriptor()
    def _verify(self):return self.native._verify()

def materialize(workspace):
    c=NativeApplication();r=c.context.request;s=c.context.snapshots.read_exact(r.application,r.snapshot_digest)
    p=c.plan(s,r);root=Path(workspace);FilesystemArtifactStore(root).apply(p)
    c.verify_materialized(root,p,s,r)
    return c,s,r,p
