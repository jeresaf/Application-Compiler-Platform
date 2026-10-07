"""Ownership continuity + a second target-native semantic analyzer."""
import hashlib,json,os,re,subprocess,tempfile
from pathlib import Path
from run import AREA

def markers(text):return re.findall(r'^// acp-owner: (GENERATED|HUMAN) id=([A-Z][A-Z0-9-]+)$',text,re.MULTILINE)
def main():
    cp=(AREA/'xtext/target/classpath.txt').read_text().strip();out=AREA/'core-runtime/out';out.mkdir(exist_ok=True)
    subprocess.run(['javac','-cp',cp,'-d',str(out),str(AREA/'source-analysis/NativeSource.java')],check=True)
    files=['GeneratedPayment.java','HumanExtension.java']
    cmd=['java','-XX:-UsePerfData','-cp',f'{out}:{cp}','NativeSource']
    old=json.loads(subprocess.check_output([*cmd,*[str(AREA/'source-analysis'/f) for f in files]],text=True))
    with tempfile.TemporaryDirectory(prefix='acp-native-rename-') as tmp:
        for file in files:
            text=(AREA/'source-analysis'/file).read_text();renamed=re.sub(r'\bsettle\b','settleRenamed',text)
            assert markers(text)==markers(renamed)
            (Path(tmp)/file).write_text(renamed)
        new=json.loads(subprocess.check_output([*cmd,*[str(Path(tmp)/f) for f in files]],text=True))
    assert [c['status'] for c in old['calls']]==[c['status'] for c in new['calls']]
    assert any(c['status']=='KNOWN' and 'settle' in c['name'] for c in old['calls'])
    assert any(c['status']=='UNRESOLVED' for c in old['calls'])
    ts=json.loads(subprocess.check_output(['node',str(AREA/'langium/source-probe5b.mjs')],text=True))
    with tempfile.TemporaryDirectory(prefix='acp-ts-rename-') as tmp:
        for file in ['generated.ts','extension.ts']:
            text=(AREA/'source-analysis'/file).read_text();renamed=re.sub(r'\bsettle\b','settleRenamed',text)
            assert markers(text)==markers(renamed)
            (Path(tmp)/file).write_text(renamed)
        ts_after=json.loads(subprocess.check_output(['node',str(AREA/'langium/source-probe5b.mjs')],text=True,env={**os.environ,'ACP_SOURCE_AREA':tmp}))
    assert [v['status'] for v in ts['evidence']]==[v['status'] for v in ts_after['evidence']]
    ts['afterRename']=ts_after
    ts['ownershipAndNativeBindingContinuity']=True
    ownership={f:markers((AREA/'source-analysis'/f).read_text()) for f in files+['generated.ts','extension.ts']}
    assert all(ownership.values())
    wasm=AREA/'langium/node_modules/tree-sitter-wasms/out/tree-sitter-typescript.wasm'
    evidence={'java':{'before':old,'afterRename':new,'ownershipContinuity':True,'nativeBindingStatusContinuity':True,'limitations':'Java has static imports rather than TypeScript-style import aliases; aliases demonstrated by native TS.'},'typescript':ts,'ownership':ownership,'treeSitterWasm':{'decision':'REJECTED_FOR_PRODUCTION','sha256':hashlib.sha256(wasm.read_bytes()).hexdigest(),'reason':'Exact grammar source revision and reproducible source-to-wasm build not established. Experimental syntax results remain UNKNOWN for semantic resolution.','fallback':'Build a reviewed grammar from pinned upstream source; use target-native semantic analyzer for bindings.'}}
    (AREA/'results/phase5b/source.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('Native Java/TypeScript source and ownership continuity PASS; third-party wasm rejected for production')
if __name__=='__main__':main()
