"""Bounded native persistence/in-process measurements and scheduling permutations."""
import copy,hashlib,json,os,selectors,subprocess,sys,tempfile,time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from run import AREA,ROOT,canonical_bytes
from native_frontend import client,native_command
from test_phase5c import model,request
from canonical_ir import normalize_candidate
from generate import encode
from fault5c import commands,fixtures

def rss(pid):
    for line in Path(f'/proc/{pid}/status').read_text().splitlines():
        if line.startswith('VmRSS:'):return int(line.split()[1])*1024
    return None

def split_comparison(candidate):
    split={}
    for core,command in commands().items():
        samples=[]
        with client(candidate) as worker:
            template=request(candidate,model(),'split-template')
            process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
            try:
                for i in range(6):
                    native_request={**template,'id':f'split-{i}'}
                    start=time.perf_counter();native=worker.call(native_request,timeout=90);frontms=(time.perf_counter()-start)*1000
                    semantic=normalize_candidate(native['payload']['documents'][0]['output']['model']);message=json.loads(fixtures()[0][1]);message['id']=f'split-{i}';message['canonicalInput']=canonical_bytes(semantic['content']).decode();message['digest']=semantic['contentDigest']
                    start=time.perf_counter();raw=canonical_bytes(message)+b'\n';encodedus=(time.perf_counter()-start)*1e6
                    start=time.perf_counter();process.stdin.write(raw);process.stdin.flush()
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdout,selectors.EVENT_READ);assert selector.select(90),'Core response timeout'
                    response=json.loads(process.stdout.readline());corems=(time.perf_counter()-start)*1000
                    assert response['status']=='SUCCESS' and response['output']['digest']==semantic['contentDigest']
                    samples.append({'frontendMs':frontms,'coreRequestMs':corems,'encodeMicroseconds':encodedus,'requestBytes':len(raw),'responseBytes':len(canonical_bytes(response)),'coreRssBytes':rss(process.pid),'frontendRssBytes':rss(worker.process.pid)})
            finally:process.kill();process.wait();process.stdin.close();process.stdout.close()
        split[core]={'frontendMsIncludesFixtureConstruction':False,'coldAndFiveWarm':samples,'scope':'Actual frontend output normalized by existing host then passed as canonical content/digest to independent representative graph core. This is not a complete candidate implementation of the eight Phase 4 stages.'}
    return split

def run():
    target=AREA/'results/phase5c';target.mkdir(exist_ok=True)
    evidence={'scope':'Linux engineering measurements; 3 cold starts, 5 warm requests per start. Two native workers maximum. Same-process probes call actual native parse functions; Python host cannot embed JVM/Node directly. No synthetic cross-runtime embedding.','candidates':{},'phase6':'NOT_STARTED'}
    for candidate in ('antlr','langium','xtext'):
        runs=[]
        for cold in range(3):
            req=request(candidate,model(),f'{cold}-cold')
            start=time.perf_counter()
            with client(candidate) as worker:
                response=worker.call(req,timeout=90)
                coldms=(time.perf_counter()-start)*1000;warm=[]
                expected=response['payload']['documents']
                for i in range(5):
                    req['id']=f'{cold}-warm-{i}';serialized=time.perf_counter();raw=canonical_bytes(req);encodeus=(time.perf_counter()-serialized)*1e6
                    start=time.perf_counter();r=worker.call(req,timeout=90);elapsed=(time.perf_counter()-start)*1000
                    assert expected==r['payload']['documents']
                    warm.append({'elapsedMs':elapsed,'nativeMicroseconds':r['payload']['metrics']['nativeRequestMicroseconds'],'requestBytes':len(raw),'responseBytes':len(canonical_bytes(r)),'hostEncodeMicroseconds':encodeus,'rssBytes':rss(worker.process.pid),'nativeHeapBytes':r['payload']['metrics']['heapUsedBytes']})
                runs.append({'coldStartupAndFirstRequestMs':coldms,'warm':warm,'nativeRequestsSamePid':6})
        with tempfile.TemporaryDirectory(prefix='acp5c-') as folder:
            path=Path(folder)/'domain.acp';path.write_text(encode(model()))
            cmd=native_command(candidate)
            if candidate=='langium':cmd += ['--embedded',str(path)]
            else:cmd[-1:]=['--embedded',candidate,str(path)]
            start=time.perf_counter();p=subprocess.run(cmd,capture_output=True,timeout=90);assert p.returncode==0,(candidate,p.stderr.decode());embedded={'processStartupPlusSixDirectCallsMs':(time.perf_counter()-start)*1000,**json.loads(p.stdout)}
            permutations=[]
            for seed in ('1','7351'):
                env={**os.environ,'TMPDIR':folder,'LANG':'C.UTF-8','LC_ALL':'C' if seed=='1' else 'C.UTF-8','PYTHONHASHSEED':seed,'ACP_UNUSED_ENV':seed}
                with client(candidate,cwd=folder,environment=env) as worker:
                    for domain in ('payment','case-management'):
                        r=worker.call(request(candidate,model(domain),domain),timeout=90);actual=r['payload']['documents'][0]['output']['model'];assert normalize_candidate(actual)['contentDigest']==normalize_candidate(model(domain))['contentDigest'];permutations.append({'seed':seed,'domain':domain,'digest':normalize_candidate(actual)['contentDigest']})
            before=model('case-management');after=copy.deepcopy(before)
            # Ordered application composition is semantic; preserve declaration IDs.
            candidates=[n for n in after['nodes'] if isinstance(n.get('data',{}).get('steps'),list) and len(n['data']['steps'])>1]
            if candidates: candidates[0]['data']['steps'].reverse()
            else:
                # Interface action order is also an ordered semantic collection.
                candidates=[n for n in after['nodes'] if isinstance(n.get('data',{}).get('actions'),list) and len(n['data']['actions'])>1];assert candidates; candidates[0]['data']['actions'].reverse()
            with client(candidate) as worker:
                outputs=[worker.call(request(candidate,m,str(i)))['payload']['documents'][0]['output']['model'] for i,m in enumerate((before,after,before))]
            digests=[normalize_candidate(m)['contentDigest'] for m in outputs];assert digests[0]==digests[2] and digests[0]!=digests[1]
        cp=(AREA/'xtext/target/classpath.txt').read_text().strip().split(':')
        footprint={'resolvedJvmJarBytes':sum(Path(p).stat().st_size for p in cp if candidate=='xtext' or '/com/google/code/gson/gson/' in p),'antlrGeneratorJarBytes':(AREA/'tools/antlr-4.13.2-complete.jar').stat().st_size} if candidate!='langium' else {'nodeModulesBytes':sum(p.stat().st_size for p in (AREA/'langium/node_modules').rglob('*') if p.is_file())}
        split=split_comparison(candidate)
        evidence['candidates'][candidate]={'splitRuntime':split,'persistent':runs,'nativeSameProcess':embedded,'environmentPermutations':permutations,'orderedChangeDigests':digests,'footprint':footprint,'operations':'Disposable exact-version worker; parent owns approval, request identities, bounded framing, timeout and process-group cancellation. Per-worker FIFO; concurrency uses independent workers, never shared parser objects.'}
    (target/'integration.json').write_text(json.dumps(evidence,indent=2)+'\n');print('Native persistent/direct comparison and warm/environment/order permutations PASS')
    return evidence
if __name__=='__main__':
    if '--split-only' in sys.argv:
        target=AREA/'results/phase5c/integration.json';data=json.loads(target.read_text())
        for candidate in data['candidates']:data['candidates'][candidate]['splitRuntime']=split_comparison(candidate)
        target.write_text(json.dumps(data,indent=2)+'\n');print('Added actual frontend-to-core split measurements without repeating cold/native measurements')
    else:run()
