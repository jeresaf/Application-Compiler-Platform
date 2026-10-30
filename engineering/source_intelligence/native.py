"""Bounded, disposable native compiler processes. No hostile-code isolation claim."""
import json,os,subprocess,tempfile,sys,resource,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.source_intelligence.model import require,sha,digest
from engineering.dependency_resolution.inputs import file_hash,tool_inventory,maven_closure

def run(args,scratch,name):
    output=scratch/(name+'.json');error=scratch/(name+'.stderr')
    def limits():resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024*1024,16*1024*1024));os.setsid()
    with output.open('wb') as out,error.open('wb') as err:
        env={k:v for k,v in os.environ.items() if k not in ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','NODE_OPTIONS','CLASSPATH')}
        env.update(LANG='C.UTF-8',LC_ALL='C.UTF-8')
        p=subprocess.Popen(args,stdout=out,stderr=err,preexec_fn=limits,env=env)
        try:code=p.wait(timeout=90)
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(p.pid,signal.SIGKILL);p.wait();raise ValueError('NATIVE_TIMEOUT')
    require(code==0,'NATIVE_PROCESS_FAILED:'+error.read_text()[-1500:]);require(output.stat().st_size<=16*1024*1024,'NATIVE_OUTPUT_BOUND')
    value=json.loads(output.read_bytes());require(value['protocol']=='acp-source-native/1','NATIVE_PROTOCOL');return value

def java(root,files,classpath,scratch):
    source=ROOT/'engineering/source_intelligence/NativeSource.java';before=file_hash(source)
    out=scratch/'java-classes';out.mkdir()
    subprocess.run(['javac','-proc:none','-classpath',str(out),'-d',str(out),str(source)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    listing=scratch/'java-files';listing.write_text('\n'.join(files)+'\n')
    cp={str(p):file_hash(p) for p in classpath}
    empty=scratch/'empty-classpath';empty.mkdir()
    result=run(['java','-XX:-UsePerfData','-Xmx768m','-cp',str(out),'NativeSource',str(root),os.pathsep.join(map(str,classpath)) or str(empty),str(listing),str(empty)],scratch,'java')
    require(before==file_hash(source) and cp=={str(p):file_hash(p) for p in classpath},'NATIVE_INPUT_CHANGED')
    result['adapterSHA256']=before
    common=Path(os.path.commonpath([str(Path(p).parent) for p in cp])) if cp else scratch
    result['dependencyDigest']=digest({str(Path(p).relative_to(common)):h for p,h in cp.items()})
    home=Path(shutil.which('java')).resolve().parents[1]
    result['compilerSHA256']=digest({n:file_hash(home/n) for n in ('bin/java','bin/javac','lib/modules','release')})
    return result

def typescript(root,files,node_modules,scratch):
    source=ROOT/'engineering/source_intelligence/typescript.mjs';before=file_hash(source)
    module=node_modules/'typescript/lib/typescript.js';package=json.loads((node_modules/'typescript/package.json').read_text())
    require(package['version']=='6.0.3','UNSUPPORTED_TYPESCRIPT_TOOLCHAIN')
    # Reuse Phase 6's exact installed tree; bind bytes, including followed executable links.
    def inventory():
        value=tool_inventory(node_modules)
        for row in value.values():
            for key in ('target','directoryTarget'):
                if key in row:row[key]=row[key].replace(str(node_modules),'<DEPENDENCIES>')
        return digest(value)
    dependencies=inventory();listing=scratch/'typescript-files.json';listing.write_text(json.dumps(files))
    result=run(['node','--max-old-space-size=768',str(source),str(root),str(module),str(node_modules),str(listing)],scratch,'typescript')
    require(before==file_hash(source) and dependencies==inventory(),'NATIVE_INPUT_CHANGED')
    result['adapterSHA256']=before;result['dependencyDigest']=dependencies;result['compilerSHA256']=digest({'typescript':file_hash(module),'node':file_hash(Path(shutil.which('node')).resolve())});return result

def classpath(repo,domain):
    reference=json.loads((ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json').read_text())
    closure=maven_closure(reference['graphs'][domain],repo,reference['artifacts']);paths=[]
    for row in closure['resolvedGraph']:
        if row['scope'] in ('compile','runtime') and row['path'].endswith('.jar'):
            p=repo/row['path'];require(file_hash(p)==row['sha256'],'CLASSPATH_SUBSTITUTION');paths.append(p)
    return list(dict.fromkeys(paths))
