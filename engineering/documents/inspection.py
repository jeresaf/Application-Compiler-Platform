"""Explicit host-constructed reporting preview; original admission stays strict."""
import json,types
from pathlib import Path
from engineering.documents import semantics
from engineering.source_intelligence import analysis
from engineering.source_intelligence.model import encode,sha,digest,require,current
from engineering.generator_candidates.spring_vue_postgres_0_6.provenance import read_provenance
from engineering.verification import integration
from compiler_contracts import fingerprint,wire
from filesystem_artifacts import FilesystemArtifactStore

SCHEMA='acp-document-preview-baseline/1'
NAMESPACE='case-management-document-preview'


class Preview:
    """Exact immutable host observations, not client-provided acceptance authority."""
    def __init__(self,candidate,snapshot,request,plan,audit,root):
        semantics.validate_snapshot(snapshot.read())
        require(audit.status=='COMPLETE' and audit.input_canonical_digest==snapshot.read()['contentDigest'] and audit.artifact_plan_digest==fingerprint(plan),'PREVIEW_COMPILATION_BINDING')
        require(request.snapshot_digest==snapshot.read()['contentDigest'],'PREVIEW_SNAPSHOT')
        candidate.verify_materialized(root,plan,snapshot,request)
        self.candidate,self.snapshot,self.request,self.plan,self.audit=candidate,snapshot,request,plan,audit
        self.target=candidate.targets[(request.snapshot_digest,request.compiler,request.pipeline)]
        self.root=Path(root).absolute()
        self.revisions={n['id']:n['revision'] for n in snapshot.read()['content']['nodes']}
        mappings={m['artifact']:m for m in read_provenance(self.root/'acp/provenance.json')['artifacts']}
        files={a.path:{'sha256':sha((self.root/a.path).read_bytes()),'owner':str(a.owner),
                      'contentDigest':a.digest,'origins':mappings.get(a.path,{}).get('origins',[]),
                      'historicalConfidence':mappings.get(a.path,{}).get('locationConfidence','ABSENT')}
               for a in FilesystemArtifactStore(self.root).inventory()}
        self.document=encode({'schema':SCHEMA,'scope':'UNAPPROVED_DOCUMENT_PREVIEW',
            'namespace':NAMESPACE,'domain':'case-management',
            'canonicalDigest':snapshot.read()['contentDigest'],'generator':candidate.generator,
            'compiler':request.compiler,'pipeline':request.pipeline,'artifactPlanDigest':fingerprint(plan),
            'provenanceSHA256':sha((self.root/'acp/provenance.json').read_bytes()),
            'compilerExecutions':[wire(audit)],'files':files})
        self.pin=sha(self.document)
    def binding(self,path,pin):
        require(pin==self.pin and Path(path).read_bytes()==self.document,'PREVIEW_EXACT_HOST_BINDING')
        return json.loads(self.document),dict(self.revisions)
    def analyze(self,baseline,*,maven_repo,node_modules,scratch):
        # Reuse the native analyzer algorithm with one private version-scoped
        # binding port. The default approved snapshot lookup is never changed.
        namespace={**vars(analysis),'binding':self.binding}
        analyze=types.FunctionType(analysis.analyze.__code__,namespace,'analyze',analysis.analyze.__defaults__)
        analyze.__kwdefaults__=analysis.analyze.__kwdefaults__
        return analyze(self.root,baseline,self.pin,maven_repo=maven_repo,node_modules=node_modules,scratch=scratch)
    def session(self,baseline,model_path):
        return PreviewSession(self,baseline,model_path)


class PreviewSession(integration.Session):
    def __init__(self,preview,baseline,model_path):
        self.preview=preview;self.root=preview.root;self.baseline=Path(baseline);self.baseline_pin=preview.pin
        self.b,self.revisions=preview.binding(baseline,preview.pin)
        self.model_path=Path(model_path);self.model_pin=sha(self.model_path.read_bytes())
        self.model=integration.load_model(model_path,self.model_pin)
        self.candidate,self.snapshot,self.request,self.plan,self.target=(preview.candidate,preview.snapshot,preview.request,preview.plan,preview.target)
        require(self.model['bindingDigest']==preview.pin and all(self.model['identity'][k]==self.b[k] for k in ('domain','canonicalDigest','generator','compiler','pipeline','artifactPlanDigest')),'PREVIEW_SOURCE_MODEL_IDENTITY')
        self.inputs={'domain':self.b['domain'],'previewNamespace':NAMESPACE,'canonicalDigest':self.b['canonicalDigest'],
            'compiler':self.b['compiler'],'pipeline':self.b['pipeline'],'generator':self.b['generator'],
            'generatorBundle':self.candidate.bundle,'artifactPlanDigest':fingerprint(self.plan),
            'compilationAuditDigest':digest(wire(preview.audit)),'targetIRDigest':fingerprint(self.target),
            'baselineSHA256':preview.pin,'sourceModelDigest':self.model['digest'],
            'sourceModelFileSHA256':self.model_pin,'executorSHA256':sha(Path(integration.__file__).read_bytes()),
            'previewExecutorSHA256':sha(Path(__file__).read_bytes())}
        self.input_digests=tuple('sha256:'+digest({k:self.inputs[k]}) for k in sorted(self.inputs))
        self.obligations={o.id:o for o in self.plan.obligations}
    def check_fresh(self):
        self.preview.binding(self.baseline,self.baseline_pin)
        require(sha(Path(__file__).read_bytes())==self.inputs['previewExecutorSHA256'],'STALE_PREVIEW_EXECUTOR')
        self.candidate._verify()
        return super().check_fresh()
