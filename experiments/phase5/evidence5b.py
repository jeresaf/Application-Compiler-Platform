"""Measured Phase 5B evidence; never turn missing native behavior into a pass."""
import copy,hashlib,json,os,random,sys,tempfile,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from run import AREA,ROOT,command,invoke,canonical_bytes
from generate import encode
from frontend import TextFrontend
from frontend_worker import Client,PROTOCOL,encode as wire_encode
from compiler_contracts import Source,Document
from canonical_fixtures import synthetic_approved
from canonical_ir import normalize_candidate
from diagnostics import project
sys.path.insert(0,str(ROOT/'tooling/tests'))
from test_contracts import apply_edits
from validate import validate

RESULTS=AREA/'results/phase5b'
def save(name,value):RESULTS.mkdir(exist_ok=True);(RESULTS/name).write_text(json.dumps(value,indent=2)+'\n')
def location(span,text,path='domain.acp'):
    if 'range' in span:line,column=span['range']['start']['line']+1,span['range']['start']['character']+1
    elif 'offset' in span:
        prefix=text[:span['offset']];line,column=prefix.count('\n')+1,len(prefix.rsplit('\n',1)[-1])+1
    else:line,column=span['line'],span['column']+1
    return f'{path}#L{line}C{column}'
def parse(candidate,text,**kwargs):
    with tempfile.TemporaryDirectory(prefix='acp-evidence-') as tmp:
        file=Path(tmp)/'domain.acp';file.write_text(text)
        return invoke(command(candidate,file),**kwargs)
def diagnostics():
    cases=json.loads((ROOT/'test-corpus/semantic/cases.json').read_text())
    names={'duplicate-id','missing-reference','stale-reference','currency-mismatch','boolean-money-literal','nonfinite-money-text','terminal-outgoing','ambiguous-transition','conflict-blocks-compilation'}
    models={}
    for case in cases:
        if case['name'] in names:
            model=json.loads((ROOT/'test-corpus/semantic'/case['base']).read_text());apply_edits(model,case['edits']);models[case['name']]=(model,case['mode'])
    payment=json.loads((ROOT/'test-corpus/phase1/payment.json').read_text())
    for name,identity,key,value in [('conflicting-permission','POL-TENANT','permission',{'id':'PERM-QUERY-TASKS','revision':1}),('conflicting-scope','SCOPE-ENT-PAYMENT','resource',{'id':'ENT-MEMBER','revision':1})]:
        model=copy.deepcopy(payment);next(n for n in model['nodes'] if n['id']==identity)['data'][key]=value;models[name]=(model,'compile')
    evidence={};expected={}
    for candidate in ('antlr','langium','xtext'):
        evidence[candidate]={}
        for name,(model,mode) in models.items():
            model=synthetic_approved(model)
            text=encode(model);result=parse(candidate,text);assert result['status']=='PASS',(candidate,name,result)
            output=result['output'];assert output['model']==model,(candidate,name)
            locations={}
            for span in output['spans']:locations.setdefault(span['id'],[]).append(location(span,text))
            projected=project(output['model'],locations,mode);assert projected and projected==project(output['model'],locations,mode)
            assert all(set(d)=={'code','subject','primary','related','remediation'} for d in projected)
            expected.setdefault(name,projected);assert expected[name]==projected,(candidate,name)
            evidence[candidate][name]={'status':'PASS','diagnostics':projected,'elapsedMs':result['elapsedMs']}
        for name,text in [('incomplete',encode(payment)[:-3]),('malformed','application ???')]:
            result=parse(candidate,text);assert result['output']['errors'] and 'model' not in result['output']
            evidence[candidate][name]={'status':'PASS','compilable':False,'diagnostics':[{'code':'SYNTAX','subject':'','primary':'domain.acp#L1C1','related':[],'remediation':'Complete or repair the source before compiling.'}],'scope':'Safe rejection; exact recovery token spans remain candidate-specific.'}
        save('diagnostics.json',evidence)
    return evidence

def determinism():
    original=json.loads((ROOT/'test-corpus/phase1/case-management.json').read_text());expected=normalize_candidate(synthetic_approved(original))['contentDigest'];evidence={}
    for candidate in ('antlr','langium','xtext'):
        variants=[]
        for i in range(2):
            model=copy.deepcopy(original);random.Random(7351+i).shuffle(model['nodes'])
            with tempfile.TemporaryDirectory(prefix='acp-environment-') as tmp:
                result=parse(candidate,encode(model),working_directory=tmp,LC_ALL='C' if i else 'C.UTF-8',TMPDIR=tmp,PYTHONHASHSEED=str(i),ACP_IRRELEVANT='noise-'+str(i))
                actual=normalize_candidate(synthetic_approved(result['output']['model']))['contentDigest'];assert actual==expected
                variants.append({'cwd':'independent temporary directory','seed':i,'locale':'C' if i else 'C.UTF-8','digest':actual,'elapsedMs':result['elapsedMs']})
        # Requests overlap; heavy native parser invocations are serialized per the
        # preregistered one-heavy-worker limit. Langium requests execute concurrently.
        def task(i):
            with Client(candidate) as client:
                identity=TextFrontend(candidate).identity
                r={'protocol':PROTOCOL,'frontend':identity,'id':str(i),'source':{'version':'acp-text/1','frontend':identity,'documents':[{'path':'domain.acp','text':encode(original)}]}}
                response=client.call(r);return normalize_candidate(synthetic_approved(response['payload']['representation']))['contentDigest']
        if candidate=='langium':
            with ThreadPoolExecutor(max_workers=2) as pool:concurrent=list(pool.map(task,range(2)))
        else:concurrent=[task(0),task(1)]
        assert concurrent==[expected,expected]
        changed=copy.deepcopy(original);next(n for n in changed['nodes'] if n['kind']=='UseCase')['data']['steps'].reverse()
        result=parse(candidate,encode(changed));different=normalize_candidate(synthetic_approved(result['output']['model']))['contentDigest'];assert different!=expected
        evidence[candidate]={'variants':variants,'workerRestartAndRepeatedRequests':concurrent,'concurrentNativeRequests':'PASS' if candidate=='langium' else 'NOT_RUN: preregistered heavy-worker concurrency limit is one','orderedSemanticChangeDigest':different,'orderedMeaningChangesOutput':True}
        save('determinism.json',evidence)
    return evidence

def integration():
    model=json.loads((ROOT/'test-corpus/phase1/payment.json').read_text());evidence={}
    for candidate in ('antlr','langium','xtext'):
        frontend=TextFrontend(candidate);source={'version':'acp-text/1','frontend':frontend.identity,'documents':[{'path':'payment.acp','text':encode(model)}]}
        request={'protocol':PROTOCOL,'frontend':frontend.identity,'id':'0','source':source}
        start=time.perf_counter();encoded=wire_encode(request);encode_ms=(time.perf_counter()-start)*1000
        direct=parse(candidate,encode(model));assert direct['status']=='PASS'
        start=time.perf_counter();client=Client(candidate);spawn_ms=(time.perf_counter()-start)*1000
        with client:
            calls=[]
            for i in range(3):
                request['id']=str(i);start=time.perf_counter();response=client.call(request);elapsed=(time.perf_counter()-start)*1000
                start=time.perf_counter();raw=wire_encode(response);decode=json.loads(raw);codec_ms=(time.perf_counter()-start)*1000
                assert decode['payload']['representation']==model
                calls.append({'elapsedMs':elapsed,'responseBytes':len(raw),'encodeDecodeMs':codec_ms})
        evidence[candidate]={'sameProcess':'NOT_RUN: Python host cannot load JVM/Node frameworks in-process without a new embedding adapter. Native repeated-parse timings remain separate.','nativeCli':{k:direct[k] for k in ('elapsedMs','peakRssBytes','status')},'supervisorSpawnMs':spawn_ms,'requestBytes':len(encoded),'requestEncodeMs':encode_ms,'persistentSupervisorCalls':calls,'nativeParserPersistence':False,'failureIsolation':'Process group termination and restart exercised by test_worker5b.py','scope':'Warm framing process, cold native parser per request; do not interpret as warm native worker.'}
        save('integration.json',evidence)
    return evidence

if __name__=='__main__':
    for action in sys.argv[1:] or ['diagnostics','determinism','integration']:
        globals()[action]();print(action+' PASS',flush=True)
