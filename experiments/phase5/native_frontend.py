"""Phase 4 port using a true persistent native parser and immutable token sidecar."""
from pathlib import Path
from run import AREA
from frontend import TextFrontend
from frontend_worker import Client,PROTOCOL
from compiler_contracts import Document,Ingested,SemanticAST
from compiler_ports import FrontendDiagnosticsFailure
from modules import resolve,ModuleError
from source_tokens import details_for,syntax_diagnostics,module_diagnostic

def native_command(candidate):
    if candidate=='langium':return ['node','--max-old-space-size=768',str(AREA/'langium/native-worker.mjs')]
    cp=(AREA/'xtext/target/classpath.txt').read_text().strip()
    if candidate=='antlr':
        gson=next(p for p in cp.split(':') if '/com/google/code/gson/gson/' in p)
        return ['java','-XX:-UsePerfData','-Xmx768m','-cp',f'{AREA}/core-runtime/out:{AREA}/antlr/generated:{gson}:{AREA}/tools/antlr-4.13.2-complete.jar','NativeWorker',candidate]
    return ['java','-XX:-UsePerfData','-Xmx768m','-cp',f'{AREA}/core-runtime/out:{AREA}/antlr/generated:{AREA}/xtext/out:{AREA}/xtext/generated/org.acp.experiment/src-gen:{cp}:{AREA}/tools/antlr-4.13.2-complete.jar','NativeWorker',candidate]

class NativeFrontend(TextFrontend):
    def __init__(self,candidate,client):
        super().__init__(candidate);self.client=client;self.sequence=0
    def ingest(self,source):
        raw=source.document.read();self.sequence+=1
        documents=raw['documents']
        for d in documents:
            path=d['path']
            if not path or Path(path).is_absolute() or '..' in Path(path).parts or '\\' in path or ':' in path:raise ValueError('Path')
        response=self.client.call({'protocol':PROTOCOL,'frontend':self.identity,'id':f'native-{self.sequence}','source':raw})
        payload=response['payload'];parsed=[];syntax=[]
        if set(payload)!={'documents','metrics'} or len(payload['documents'])!=len(documents):raise ValueError('Response')
        for document,entry in zip(documents,payload['documents']):
            if entry['path']!=document['path']:raise ValueError('Stale document')
            output=entry['output']
            if output.get('errors'):syntax.extend(syntax_diagnostics(self.candidate,document,output['errors']))
            else:parsed.append((entry['path'],output))
        if syntax:raise FrontendDiagnosticsFailure(tuple(syntax))
        details=details_for(documents,parsed)
        try:model,_=resolve(parsed)
        except ModuleError as error:raise FrontendDiagnosticsFailure(module_diagnostic(error,documents,parsed,details)) from None
        for node in model['nodes']:
            for ref in details['references'].get(node['id'],[]):
                value=node
                for key in ref['path'].lstrip('/').split('/'):
                    key=key.replace('~1','/').replace('~0','~');value=value[int(key)] if isinstance(value,list) else value[key]
                ref['id'],ref['revision']=value['id'],value['revision']
        return Ingested(Document.of(model),Document.of(details['declarations']),self.identity,Document.of(details))
    def elaborate(self,parsed):
        if parsed.dialect!=self.identity:raise ValueError('Version')
        return SemanticAST(parsed.representation,parsed.source_map,source_details=parsed.source_details)


def client(candidate,**kwargs):return Client(candidate,command=native_command(candidate),**kwargs)
