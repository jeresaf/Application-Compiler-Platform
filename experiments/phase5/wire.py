"""Identical representative core fixtures across four independently implemented runtimes."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from run import AREA,ROOT,canonical_bytes

PROTOCOL="acp-core-wire/1"
def reference(r):
    # Freeze authority-facing input through exact bytes; no shared mutable state.
    r=json.loads(canonical_bytes(r));visited=[];pending=['ROOT'];code=''
    if r['protocol']!=PROTOCOL:code='VERSION'
    elif r['portVersion']!='graph/1':code='PORT'
    elif canonical_bytes(json.loads(r['canonicalInput'])).decode()!=r['canonicalInput']:code='CANONICAL'
    while not code and pending:
        node=pending.pop(0)
        if r['cancelled']:code='CANCELLED';break
        if node in visited:continue
        if len(visited)>=r['budget']:code='RESOURCE';break
        visited.append(node);pending+=r['dependencies'].get(node,[])
    return {'protocol':PROTOCOL,'id':r['id'],'status':'FAILURE' if code else 'SUCCESS',
            'diagnostics':[{'code':code,'subject':'ROOT','primary':'graph.acp#L1C1','related':[],
                            'remediation':'Repair the declared request or retry with valid authority and budgets.'}] if code else [],
            'digest':'sha256:'+hashlib.sha256(b'ACP\0acp-jcs-safe-v1\0canonical\0'+canonical_bytes(json.loads(r['canonicalInput']))).hexdigest(),
            'provenance':r['provenance'],'obligations':r['obligations'],'visited':visited,'work':len(visited)}

def fixtures():
    manifest=json.loads((ROOT/'test-corpus/canonical/manifest.json').read_text())
    snapshot=json.loads((ROOT/'test-corpus/canonical'/manifest['examples'][0]['file']).read_text())
    base={'protocol':PROTOCOL,'id':'success','canonicalInput':canonical_bytes(snapshot['content']).decode(),
          'provenance':[{'id':'ENT-PAYMENT','revision':1,'producer':'experiment/1'}],
          'obligations':[{'id':'OB-TEST','status':'OUTSTANDING','origin':'ENT-PAYMENT@1'}],
          'dependencies':{'ROOT':['A','B'],'A':['B'],'B':['ROOT']},'budget':3,'cancelled':False,'portVersion':'graph/1'}
    result=[base]
    for name,update in [('resource',{'budget':2}),('cancelled',{'cancelled':True}),('version',{'protocol':'acp-core-wire/2'}),('port',{'portVersion':'graph/2'}),('noncanonical',{'canonicalInput':json.dumps(snapshot['content'])})]:
        r=copy.deepcopy(base);r.update(update,id=name);result.append(r)
    return result

def main():
    cp=(AREA/'xtext/target/classpath.txt').read_text().strip();out=AREA/'core-runtime/out';out.mkdir(exist_ok=True)
    subprocess.run(['javac','-cp',cp,'-d',str(out),str(AREA/'core-runtime/Canonical.java'),str(AREA/'core-runtime/WireCore.java')],check=True)
    cargo=AREA/'.cache/cargo/bin/cargo'
    args=[str(cargo),'build','--locked','--offline','--release','--manifest-path',str(AREA/'core-runtime/Cargo.toml')] if cargo.exists() else ['cargo','+1.90.0','build','--locked','--release','--manifest-path',str(AREA/'core-runtime/Cargo.toml')]
    env={**os.environ,**({'RUSTUP_HOME':str(AREA/'.cache/rustup'),'CARGO_HOME':str(AREA/'.cache/cargo')} if cargo.exists() else {})}
    subprocess.run(args,check=True,env=env)
    requests=fixtures();raw=b''.join(canonical_bytes(r)+b'\n' for r in requests);expected=[reference(r) for r in requests]
    commands={'java':['java','-XX:-UsePerfData','-cp',f'{out}:{cp}','WireCore'], 'typescript':['node',str(AREA/'core-runtime/wire.ts')], 'rust':[str(AREA/'core-runtime/target/release/wire-core')]}
    evidence={'protocol':PROTOCOL,'fixtures':len(requests),'requestBytes':len(raw),'runtimes':{},'scope':'Representative graph-stage contract slice; not the complete Phase 4 compiler or production wire. Authority remains external. Cycles visit each identity once.'}
    for candidate,command in commands.items():
        def run():
            start=time.perf_counter();p=subprocess.run(command,input=raw,capture_output=True,timeout=90,env={**os.environ,'ACP_WIRE_METRICS':'1'})
            assert p.returncode==0,(candidate,p.stderr.decode())
            actual=[json.loads(line) for line in p.stdout.splitlines()];assert actual==expected,candidate
            return {'elapsedMs':(time.perf_counter()-start)*1000,'outputBytes':len(p.stdout),'semanticEquality':True,'metrics':[json.loads(line) for line in p.stderr.splitlines()]}
        cold=run()
        with ThreadPoolExecutor(max_workers=2) as workers:concurrent=list(workers.map(lambda _:run(),range(2)))
        evidence['runtimes'][candidate]={'cold':cold,'concurrentIndependentProcesses':concurrent}
    target=AREA/'results/phase5b';target.mkdir(exist_ok=True)
    (target/'wire.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('Four-runtime representative wire equivalence PASS; TypeScript independent processes executed')

if __name__=='__main__':main()
