"""Separate read-only MCP namespace for an explicitly unapproved native preview."""
import argparse,json,types
from pathlib import Path
from typing import Literal
from engineering.reporting import semantics
from engineering.reporting.inspection import NAMESPACE,SCHEMA
from engineering.mcp_adapter import service,server
from engineering.source_intelligence.model import require,sha,current
from engineering.verification.integration import load_model,validate_result
from changes import graph

class PreviewApplication(service.Application):
    def __init__(self,cfg):
        require(set(cfg)=={'root','baseline','model','verification','plan','snapshot'},'PREVIEW_HOST_FIELDS')
        self.root=Path(cfg['root']);self.cfg=cfg
        def load(key):
            row=cfg[key];require(set(row)=={'path','sha256'},'PREVIEW_INPUT_FIELDS')
            raw=service.input_bytes(row['path']);require(sha(raw)==row['sha256'],'PREVIEW_INPUT_HASH')
            return json.loads(raw)
        self.baseline=load('baseline');self.b=self.baseline
        require(self.b['schema']==SCHEMA and self.b['namespace']==NAMESPACE and self.b['scope']=='UNAPPROVED_REPORT_PREVIEW','PREVIEW_SCOPE')
        self.snapshot=load('snapshot');semantics.validate_snapshot(self.snapshot)
        require(self.snapshot['contentDigest']==self.b['canonicalDigest'],'PREVIEW_CANONICAL_IDENTITY')
        self.nodes={n['id']:n for n in self.snapshot['content']['nodes']}
        self.revisions={i:n['revision'] for i,n in self.nodes.items()}
        self.model=load_model(cfg['model']['path'],cfg['model']['sha256'])
        self.verification=validate_result(load('verification'));self.plan=load('plan')
        require(self.model['bindingDigest']==cfg['baseline']['sha256'] and all(self.model['identity'][k]==self.b[k] for k in ('domain','canonicalDigest','generator','compiler','pipeline','artifactPlanDigest')),'PREVIEW_MODEL_IDENTITY')
        require(self.plan['schema']=='acp-mcp-plan/1' and self.plan['artifactPlanDigest']==self.b['artifactPlanDigest'],'PREVIEW_PLAN')
        expected=self.plan['inputs'];actual=self.verification['inputs']
        require(all(actual.get(k)==v for k,v in expected.items()) and expected['previewNamespace']==NAMESPACE and expected['baselineSHA256']==cfg['baseline']['sha256'] and expected['sourceModelFileSHA256']==cfg['model']['sha256'] and expected['canonicalDigest']==self.b['canonicalDigest'],'PREVIEW_EXECUTION_BINDING')
        self.symbols={s['id']:s for s in self.model['symbols']};self.edges=graph(self.snapshot)
        self.fresh()
    def fresh(self):
        for key in ('baseline','model','verification','plan','snapshot'):
            require(sha(service.input_bytes(self.cfg[key]['path']))==self.cfg[key]['sha256'],'STALE_PREVIEW_HOST_INPUT')
        current(self.model,self.root)
    def envelope(self,operation):
        value=super().envelope(operation)
        value.update(application=NAMESPACE,semanticApproval='NOT_APPROVED',scope='UNAPPROVED_REPORT_PREVIEW')
        value['restrictions'].append('NO_APPROVED_APPLICATION_ALIAS')
        return value
    def call(self,operation,q):
        require(q['application']==NAMESPACE,'PREVIEW_NAMESPACE_REQUIRED')
        fn=types.FunctionType(service.Application.call.__code__,{**vars(service),'validate_snapshot':semantics.validate_snapshot},'call')
        result=fn(self,operation,q)
        if operation=='spec.validate':
            for row in result['items']:
                row.update(authority='NO_SEMANTIC_APPROVAL',check='engineering.reporting.semantics.validate_snapshot')
        return result

class PreviewService:
    def __init__(self,path):
        cfg=json.loads(service.input_bytes(path))
        require(set(cfg)=={'schema','namespace','application'} and cfg['schema']=='acp-report-mcp-host/1' and cfg['namespace']==NAMESPACE,'PREVIEW_HOST_SCHEMA')
        self.app=PreviewApplication(cfg['application'])
    def call(self,operation,q):return self.app.call(operation,q)

class PreviewQuery(server.Query):
    application:Literal['case-management-report-preview']

def create(svc):
    def factory(*args,**kwargs):
        kwargs['instructions']='Unapproved synthetic reporting preview only. No semantic, release or operational authority.'
        return server.Server(*args,**kwargs)
    fn=types.FunctionType(server.create.__code__,{**vars(server),'Query':PreviewQuery,'Server':factory},'create')
    return fn(svc)

async def serve(config):
    svc=PreviewService(config);transport=create(svc)
    async with server.stdio_server(stdin=server.BoundedInput()) as (incoming,outgoing):
        await transport.run(incoming,outgoing,transport.create_initialization_options())

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host-config',required=True);a=p.parse_args()
    server.anyio.run(serve,a.host_config)
if __name__=='__main__':main()
