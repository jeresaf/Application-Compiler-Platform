"""Identical native core fault fixtures; explicit failures contain no output.

This remains a representative stage slice, not a production compiler port.
Timeout/crash are real OS process faults supervised outside the worker.
"""
import copy,hashlib,json,os,selectors,signal,subprocess,time
from pathlib import Path
from run import AREA,ROOT,canonical_bytes
LIMIT=1048576
PROTOCOL='acp-core-fault/1'

def commands():
    cp=(AREA/'xtext/target/classpath.txt').read_text().strip()
    return {'java':['java','-XX:-UsePerfData','-Xmx768m','-cp',f'{AREA}/core-runtime/out:{cp}','FaultCore'],'typescript':['node',str(AREA/'core-runtime/fault.ts')],'rust':[str(AREA/'core-runtime/target/release/fault-core')]}
def build():
    cp=(AREA/'xtext/target/classpath.txt').read_text().strip();out=AREA/'core-runtime/out';out.mkdir(exist_ok=True)
    subprocess.run(['javac','-cp',cp,'-d',str(out),str(AREA/'core-runtime/Canonical.java'),str(AREA/'core-runtime/FaultCore.java')],check=True)
    cargo=AREA/'.cache/cargo/bin/cargo';local=cargo.exists()
    env={**os.environ,**({'RUSTUP_HOME':str(AREA/'.cache/rustup'),'CARGO_HOME':str(AREA/'.cache/cargo')} if local else {})}
    subprocess.run(([str(cargo)] if local else ['cargo','+1.90.0'])+['build','--locked','--release','--manifest-path',str(AREA/'core-runtime/Cargo.toml')],env=env,check=True)
def fixtures():
    content='{"modelVersion":"0.2.0"}'
    base={'id':'success','protocol':PROTOCOL,'semanticVersion':'0.2.0','canonicalInput':content,'digest':'sha256:'+hashlib.sha256(b'ACP\0acp-jcs-safe-v1\0canonical\0'+content.encode()).hexdigest(),'dependencies':{'ROOT':['A','B'],'A':['B'],'B':['ROOT']},'budget':3,'cancelled':False,'portVersion':'graph/1','downstream':{'protocol':'graph/1','status':'SUCCESS'}}
    result=[('success',canonical_bytes(base),None)]
    for name,update,code in [('version',{'protocol':'other/1'},'VERSION'),('semantic',{'semanticVersion':'99'},'SEMANTIC_VERSION'),('port',{'portVersion':'other'},'PORT_VERSION'),('digest',{'digest':'sha256:bad'},'DIGEST'),('dependency',{'dependencies':{'ROOT':['MISSING']}},'DEPENDENCY'),('cancel',{'cancelled':True},'CANCELLED'),('budget',{'budget':2},'RESOURCE'),('downstream',{'downstream':{'status':'SUCCESS','output':'unsafe'}},'DOWNSTREAM'),('canonical',{'canonicalInput':' { }'},'CANONICAL'),('multi-fault-order',{'protocol':'other','semanticVersion':'99','cancelled':True},'VERSION'),('bad-shape',{'budget':'2'},'MALFORMED'),('broken-content',{'canonicalInput':'{'},'CANONICAL'),('downstream-null',{'downstream':None},'DOWNSTREAM')]:
        r=copy.deepcopy(base);r.update(update,id=name);result.append((name,canonical_bytes(r),code))
    result += [('malformed',b'{"id":', 'MALFORMED'),('duplicate-key',b'{"id":"first","id":"second"}','MALFORMED'),('oversize',b' '* (LIMIT+1),'INPUT_SIZE')]
    return result

def supervised(command,raw,*,stop=False,kill=False,timeout=5):
    """Bounded subprocess group; crash/timeout never yield compilable output."""
    p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:
        if stop:os.killpg(p.pid,signal.SIGSTOP)
        if kill:os.killpg(p.pid,signal.SIGKILL)
        try:out,err=p.communicate(raw,timeout=timeout)
        except subprocess.TimeoutExpired:return {'status':'FAILURE','diagnostics':[{'code':'TIMEOUT'}]}
        if p.returncode:return {'status':'FAILURE','diagnostics':[{'code':'CRASH'}]}
        if len(out)>LIMIT:return {'status':'FAILURE','diagnostics':[{'code':'RESPONSE_SIZE'}]}
        try:return json.loads(out)
        except (ValueError,UnicodeError):return {'status':'FAILURE','diagnostics':[{'code':'MALFORMED_RESPONSE'}]}
    finally:
        try:os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        p.wait();p.stdin.close();p.stdout.close();p.stderr.close()

def run():
    cases=fixtures();raw=b''.join(r+b'\n' for _,r,_ in cases);evidence={'scope':'Representative immutable graph-stage fault slice; external supervisor owns timeout/crash. No production compiler runtime selected.','protocol':PROTOCOL,'fixtures':[{'name':n,'inputBytes':len(r),'expectedCode':c} for n,r,c in cases],'runtimes':{}}
    expected=None
    for candidate,cmd in commands().items():
        start=time.perf_counter();p=subprocess.run(cmd,input=raw,capture_output=True,timeout=90);assert p.returncode==0,(candidate,p.stderr.decode())
        actual=[json.loads(line) for line in p.stdout.splitlines()];assert len(actual)==len(cases),(candidate,len(actual))
        for (name,_,code),response in zip(cases,actual):
            if code is None:assert response['status']=='SUCCESS' and 'output' in response
            else:assert response['status']=='FAILURE' and set(response)=={'protocol','id','status','diagnostics'} and response['diagnostics'][0]['code']==code,(candidate,name,response)
        if expected is None:expected=actual
        else:assert expected==actual,candidate
        runtime={'faultFixtures':actual,'batchElapsedMs':(time.perf_counter()-start)*1000,'requestBytes':len(raw),'responseBytes':len(p.stdout),'persistentRequests':len(cases)}
        for mode in ('timeout','crash'):
            response=supervised(cmd,cases[0][1]+b'\n',stop=mode=='timeout',kill=mode=='crash',timeout=.15)
            assert response['status']=='FAILURE' and 'output' not in response and response['diagnostics'][0]['code']==mode.upper(),response
            retry=supervised(cmd,cases[0][1]+b'\n');assert retry==actual[0],(candidate,retry)
            runtime[mode]={'failure':response,'retryEquivalent':True}
        evidence['runtimes'][candidate]=runtime
    target=AREA/'results/phase5c';target.mkdir(exist_ok=True);(target/'core-faults.json').write_text(json.dumps(evidence,indent=2)+'\n');print('Phase 5C Java/TypeScript/Rust fault parity PASS; Failure output absent')
    return evidence
if __name__=='__main__':build();run()
