"""Explicit background-job registration; original kernel stage code remains intact."""
from dataclasses import replace
from engineering.jobs import semantics
from engineering.jobs.schema import FEATURES,KINDS
from engineering.native_create.schema import KINDS as CREATE_KINDS
from engineering.reporting.schema import KINDS as REPORT_KINDS
from engineering.documents.schema import KINDS as DOCUMENT_KINDS
from engineering.compiler_extensions.dispatch import Registration,kernel
from compiler_reference import StructuredFrontendV04,FixtureApproval,MemorySnapshots,MemoryCache,ReferenceControl
from compiler_contracts import Source,Document,Subject,Decision,CompilationRequest,fingerprint,COMPILER,PIPELINE
from compiler_ports import CompilationContext
import compiler_core
FRONTEND='acp-structured-reference/0.7.0'
COMPILER_ID=COMPILER+'+jobs.1';PIPELINE_ID=PIPELINE+'+jobs.1'
categories={k:set(v) for k,v in compiler_core.CATEGORIES.items()}
categories['authorization']|=set(KINDS)|set(CREATE_KINDS)|set(REPORT_KINDS)|set(DOCUMENT_KINDS)
categories['audit']|={'CreateOperation','AuditHistory'}|set(KINDS)
categories['tests']|=set(KINDS)|set(CREATE_KINDS)|set(REPORT_KINDS)|set(DOCUMENT_KINDS)
categories['reliability']|={'CreateOperation','ReportDefinition'}|set(KINDS)
categories['privacy']|=set(KINDS)
REGISTRATION=Registration(FRONTEND,'0.8.0',FEATURES,COMPILER_ID,PIPELINE_ID,semantics,frozenset(KINDS|CREATE_KINDS|REPORT_KINDS|DOCUMENT_KINDS),tuple((k,frozenset(v)) for k,v in sorted(categories.items())))
class Frontend(StructuredFrontendV04):identity=FRONTEND

def fixture_context(model,target,inventory=()):
 snapshot=Document.of(semantics.normalize_candidate(model));source=Source(Document.of(model));c=snapshot.read()['content']
 root=next(n for n in c['nodes'] if n['kind']=='Decision');origin=(Subject(c['applicationId'],root['id'],root['revision']),)
 decisions=tuple(Decision('job-preview-'+role,role,origin,Document.of({'choice':target.profile['decisions'][role],'status':'TEST_ONLY'})) for role in ('architecture','design'))
 evidence=Document.of({'scope':'UNAPPROVED_JOB_PREVIEW','features':list(FEATURES)})
 r=CompilationRequest(c['applicationId'],snapshot.read()['contentDigest'],fingerprint(source,'source'),evidence,decisions,tuple(sorted(fingerprint(d,'decision') for d in decisions)))
 r=replace(r,frontend=FRONTEND,features=FEATURES,compiler=COMPILER_ID,pipeline=PIPELINE_ID,target=target.identity,generator=target.generator,required_capabilities=tuple(sorted((*r.required_capabilities,'semantic.execution-dataflow/0.3','target.project-artifacts/1',*FEATURES))))
 return source,CompilationContext(r,MemorySnapshots((snapshot,)),Frontend(),FixtureApproval((snapshot,),decisions,evidence),target,MemoryCache(),ReferenceControl(),tuple(inventory))
def compile_pipeline(source,context,*,repeat=False):return kernel(REGISTRATION)['compile_pipeline'](source,context,repeat=repeat)
