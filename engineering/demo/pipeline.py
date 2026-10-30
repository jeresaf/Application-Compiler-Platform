"""Trusted internal-demo adapter for the existing compiler and successor target.

No new generator, authority service or hostile-plugin isolation boundary.
"""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from compiler_contracts import Document,Success,wire,COMPILER,PIPELINE
from compiler_core import compile_pipeline
from check_task_interface import ui_context
from deterministic_approval import approved_snapshot,APPROVED
from target_worker import ProductionTarget,TargetWorkerError
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
from engineering.generator_candidates.spring_vue_postgres_0_6 import provenance

class CandidatePort(ProductionTarget):
    """Use the existing target-port adaptation and pure candidate implementation."""
    def __init__(self,candidate):
        self.candidate=candidate;self.identity=candidate.profile['profile']
        self.bundle=candidate.bundle;self.generator=candidate.generator
        self.last_admission=None;self.last_target=None
    def _call(self,operation,payload):
        self.candidate._verify()
        if operation=='lower':
            try:
                self.candidate._model.negotiate(payload['nodes'],payload['required'],payload['decisions'],self.candidate.profile,payload.get('canonicalVersion','0.1.0'))
                result=self.candidate._model.lower(payload['nodes'],self.candidate.profile,payload.get('canonicalVersion','0.1.0'))
            except self.candidate._model.CapabilityError as error:raise TargetWorkerError(str(error)) from None
        else:result=self.candidate._call(operation,payload)
        self.candidate._verify();return result
    def lower(self,realization,request):
        self.last_target=super().lower(realization,request);return self.last_target

class PipelineCandidate(SuccessorCandidate):
    """Keep the trusted candidate API, but execute all eight real compiler stages."""
    def __init__(self):
        super().__init__();self.executions=[];self.targets={}
    def plan(self,snapshot,request,*,inventory=()):
        domain=next((d for d,binding in APPROVED.items() if binding['contentDigest']==snapshot.read().get('contentDigest')),None)
        if domain is None or request.snapshot_digest!=snapshot.read()['contentDigest'] or request.generator!=self.generator or approved_snapshot(domain)!=snapshot.read():
            raise ValueError('DEMO_REQUIRES_EXACT_APPROVED_REFERENCE')
        if tuple(request.features)!=tuple(snapshot.read()['content']['requiredFeatures']):raise ValueError('DEMO_FEATURE_IDENTITY')
        source,context=ui_context(domain);port=CandidatePort(self)
        compiled_request=replace(context.request,compiler=request.compiler,pipeline=request.pipeline,target=port.identity,generator=port.generator)
        context=replace(context,target=port,request=compiled_request,inventory=tuple(inventory))
        compilation=compile_pipeline(source,context)
        if not isinstance(compilation.result,Success):raise ValueError('DEMO_COMPILATION_FAILED:'+str(compilation.result.diagnostics))
        key=(request.snapshot_digest,request.compiler,request.pipeline)
        self.targets[key]=port.last_target
        self.executions.append({'domain':domain,'canonicalDigest':request.snapshot_digest,'admission':port.last_admission,'audit':wire(compilation.audit),'artifactPlanDigest':compilation.result.output_digest,'scope':'QUALIFICATION_ONLY'})
        return compilation.result.output
    def verify_materialized(self,root,plan,snapshot,request,*,required_origins=()):
        self._verify();key=(request.snapshot_digest,request.compiler,request.pipeline)
        if key not in self.targets or request.generator!=self.generator or request.snapshot_digest!=snapshot.read()['contentDigest']:
            raise ValueError('DEMO_MATERIALIZATION_BINDING')
        document=provenance.read_provenance(Path(root)/'acp/provenance.json')
        return provenance.verify_plan_provenance(root,plan,document,target=self.targets[key],request=request,required_origins=required_origins)

def request(candidate,snapshot):
    return SimpleNamespace(compiler=COMPILER,pipeline=PIPELINE,snapshot_digest=snapshot.read()['contentDigest'],features=tuple(snapshot.read()['content']['requiredFeatures']),generator=candidate.generator)

def inputs(domain,compiler=COMPILER,pipeline=PIPELINE):
    snapshot=Document.of(approved_snapshot(domain));candidate=PipelineCandidate()
    request=SimpleNamespace(compiler=compiler,pipeline=pipeline,snapshot_digest=snapshot.read()['contentDigest'],features=tuple(snapshot.read()['content']['requiredFeatures']),generator=candidate.generator)
    return candidate,snapshot,request,candidate.plan(snapshot,request)
