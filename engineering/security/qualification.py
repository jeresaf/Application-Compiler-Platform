"""Bounded OS enforcement, package and current advisory checks. No release authority."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.dependency_resolution.inputs import require, file_hash, npm_lock


def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(path,value):path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')


def sandbox_source():
    path=ROOT/'targets/spring-vue-postgres/worker/main.py'
    raw=path.read_bytes();tree=ast.parse(raw)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sandbox')
    return ast.get_source_segment(raw.decode(),node),sha(raw)


def confinement(output):
    """Execute the exact sealed sandbox in fresh bounded disposable child processes.

    No hostile workload executes before sandbox installation. Direct syscalls
    avoid libc/vDSO caches. This tests the released worker, not the explicitly
    in-process, trusted SuccessorCandidate API.
    """
    require(platform.machine()=='x86_64' and platform.system()=='Linux','UNQUALIFIED_SANDBOX_ABI')
    function,binding=sandbox_source()
    prefix='import ctypes,errno,resource,os,sys,json\n'+function+'\n'
    # libseccomp resolves the host ABI before confinement. Safe denied syscalls
    # only: never attempt host writes, identity changes, mounts or clock changes.
    probes={
      'filesystemRead':('openat',[-100,ctypes_string('/etc/passwd'),0]),
      'filesystemWrite':('openat',[-100,ctypes_string(str(output/'must-not-exist')),65,384]),
      'networkSocket':('socket',[2,1,0]),
      'networkConnect':('connect',[-1,0,0]),
      'processFork':('fork',[]), 'processClone':('clone',[17,0,0,0,0]),
      'subprocessExec':('execve',[ctypes_string('/does-not-exist'),0,0]),
      'identityUid':('getuid',[]),'identityEuid':('geteuid',[]),
      'identityGid':('getgid',[]),'identityEgid':('getegid',[]),
      'clockRead':('clock_gettime',[0,0]),'wallClock':('gettimeofday',[0,0]),
      'entropy':('getrandom',[0,0,0]),'kernelIdentity':('uname',[0]),
      'ptrace':('ptrace',[0,0,0,0]),'ioUring':('io_uring_setup',[0,0]),
    }
    rows=[]
    for name,(syscall,args) in probes.items():
        code=prefix+"lib=ctypes.CDLL(None,use_errno=True);lib.syscall.restype=ctypes.c_long\ns=ctypes.CDLL('libseccomp.so.2');s.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p]\nn=s.seccomp_syscall_resolve_name("+repr(syscall.encode())+")\nassert n>=0\nsandbox()\nctypes.set_errno(0)\nr=lib.syscall(n"+''.join(','+str(a) for a in args)+")\ne=ctypes.get_errno()\nprint(json.dumps({'return':r,'errno':e}))\nassert r==-1 and e==errno.EPERM\n"
        result=subprocess.run([sys.executable,'-I','-B','-c',code],env={'LC_ALL':'C'},cwd=output,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
        require(result.returncode==0,'SANDBOX_NOT_ENFORCED:'+name+':'+result.stderr)
        rows.append({'test':name,'syscall':syscall,'exit':result.returncode,'observation':json.loads(result.stdout)})
    memory=prefix+"sandbox()\nassert resource.getrlimit(resource.RLIMIT_AS)==(536870912,536870912)\ntry: bytearray(600*1024*1024)\nexcept MemoryError: print('ADDRESS_SPACE_LIMIT_ENFORCED')\nelse: raise AssertionError('UNBOUNDED_MEMORY')\n"
    p=subprocess.run([sys.executable,'-I','-B','-c',memory],capture_output=True,text=True,timeout=30,env={'LC_ALL':'C'},cwd=output)
    require(p.returncode==0 and p.stdout.strip()=='ADDRESS_SPACE_LIMIT_ENFORCED','MEMORY_NOT_ENFORCED')
    rows.append({'test':'memoryExhaustion','exit':p.returncode,'observation':p.stdout.strip()})
    cpu=prefix+"sandbox()\nassert resource.getrlimit(resource.RLIMIT_CPU)==(20,20)\nwhile True: pass\n"
    p=subprocess.run([sys.executable,'-I','-B','-c',cpu],capture_output=True,timeout=30,start_new_session=True,env={'LC_ALL':'C'},cwd=output)
    require(p.returncode==-signal.SIGKILL,'CPU_NOT_ENFORCED')
    rows.append({'test':'cpuExhaustion','exit':p.returncode,'cpuHardSeconds':20})
    from target_worker import TargetWorker
    environment=TargetWorker(command=(sys.executable,'-I','-B','-c',"import os,json; print(json.dumps({'ok':True,'result':dict(os.environ)}))")).call('manifest',{})
    require(set(environment)<= {'LC_ALL','LC_CTYPE','PYTHONHASHSEED'} and environment.get('PYTHONHASHSEED')=='0','WORKER_CREDENTIAL_ENVIRONMENT_LEAK')
    rows.append({'test':'credentialEnvironmentIsolation','environment':environment})
    require(not (output/'must-not-exist').exists(),'FILESYSTEM_WRITE_ESCAPED')
    return {'scope':'SEALED_WORKER_SANDBOX_COMPONENT_QUALIFICATION_ONLY','sourceSHA256':binding,'abi':platform.machine(),'observations':rows,'limitations':['SuccessorCandidate is a trusted in-process API, not a hostile-plugin execution boundary.','The worker installs a syscall denylist after trusted preload; this is not an exhaustive syscall allowlist or namespace isolation.','vDSO clock reads may bypass seccomp; direct clock syscalls are denied.','Inherited standard input/output are protocol channels, not confidential channels. No credential-bearing handles may be supplied.']}


def ctypes_string(value):return 'ctypes.c_char_p('+repr(os.fsencode(value))+')'


def resolve_backend_components(components, locked):
    """Recover absent Maven metadata only from exact content-locked origins.

    Never infer group/version from a display filename. Ambiguous or embedded-only
    identities remain unknown and block a clean assessment.
    """
    for component in components:
        if component.get('purl'):continue
        identities=set()
        for row in locked.values():
            if row['sha256']!=component['hashes'][0]['content']:continue
            for origin in row['lockedOrigins']:
                if origin.startswith('maven:'):
                    parts=Path(origin[len('maven:'):]).parts
                    identities.add(('.'.join(parts[:-3]),parts[-3],parts[-2]))
        if len(identities)==1:
            group,name,version=next(iter(identities));purl=f'pkg:maven/{group}/{name}@{version}'
            component.update(group=group,name=name,version=version,purl=purl,**{'bom-ref':purl,'identitySource':'EXACT_SHA256_LOCKED_MAVEN_ORIGIN'})
    return components


def package_inventory(root):
    """Verify actual packaged JAR/assets, exact dependencies and test exclusion."""
    root=Path(root);jar=root/'backend/target/application-0.1.0.jar'
    from engineering.dependency_resolution.inputs import packaged_dependencies
    sys.path.insert(0,str(ROOT/'tooling/audit'))
    from tooling.audit.package_audit import backend_components,inspect_jar,FORBIDDEN
    # audit import is delayed: package_audit historically imports top-level phase6.
    raw=jar.read_bytes();hits=inspect_jar(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        require(z.testzip() is None,'CORRUPT_PACKAGE')
        names=z.namelist();require(len(names)==len(set(names)),'DUPLICATE_JAR_MEMBER')
        for n in ('BOOT-INF/classes/acp/Application.class','BOOT-INF/classes/acp/infrastructure/RuntimeConfigurationContract.class','BOOT-INF/classes/acp-runtime-configuration-contract.json','BOOT-INF/classes/acp-tzdb-2026d.json'):require(n in names,'INCOMPLETE_PACKAGE:'+n)
        for p in (root/'database').glob('*.sql'):
            require(z.read('BOOT-INF/classes/db/migration/'+p.name)==p.read_bytes(),'MIGRATION_PACKAGE_SUBSTITUTION')
    assets=list((root/'frontend/dist').rglob('*'));require((root/'frontend/dist/index.html').is_file() and any(p.suffix=='.js' for p in assets),'INCOMPLETE_FRONTEND')
    for p in assets:
        require(not p.is_symlink(),'PACKAGE_SYMLINK')
        if p.is_file():hits.extend(str(p.relative_to(root))+':'+v.decode() for v in FORBIDDEN if v in p.read_bytes())
    require(not hits,'TEST_AUTHORITY_IN_PACKAGE:'+str(hits))
    reference=json.loads((ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json').read_bytes())
    locked=packaged_dependencies(jar,reference['artifacts'],reference['embeddedArtifacts'])
    components=resolve_backend_components(backend_components(jar),locked)
    unknown=[c['bom-ref'] for c in components if not c.get('purl')]
    return {'jarSHA256':sha(raw),'files':{str(p.relative_to(root)):file_hash(p) for p in [jar,*assets] if p.is_file()},'backend':components,'lockedDependencies':locked,'unknownComponents':unknown,'testCredentialScan':'NO_KNOWN_TEST_MARKERS','limitation':'Marker exclusion is not a secret-custody or operational identity-provider acceptance proof.'}


def component_queries(root,package):
    lock=npm_lock((root/'frontend/package-lock.json').read_bytes())
    raw=json.loads((root/'frontend/package-lock.json').read_bytes())
    rows=[{'ecosystem':'Maven','name':c['group']+':'+c['name'],'version':c['version'],'source':'PACKAGED_BACKEND','sha256':c['hashes'][0]['content']} for c in package['backend'] if c.get('purl')]
    for name,p in raw['packages'].items():
        if name and not p.get('dev'):
            rows.append({'ecosystem':'npm','name':name.rsplit('node_modules/',1)[-1],'version':p['version'],'source':'PRODUCTION_NPM','integrity':lock[name]['integrity']})
    for line in (ROOT/'tooling/requirements.txt').read_text().splitlines():
        if line and not line.startswith('#'):
            name,version=line.split('==');rows.append({'ecosystem':'PyPI','name':name,'version':version,'source':'COMPILER_LOCK'})
    reference=json.loads((ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json').read_bytes())
    for path,binding in reference['artifacts'].items():
        if not path.endswith('.jar'):continue
        parts=Path(path).parts;rows.append({'ecosystem':'Maven','name':'.'.join(parts[:-3])+':'+parts[-3],'version':parts[-2],'source':'MAVEN_BUILD_AND_TRANSITIVE_LOCK','sha256':binding['sha256']})
    return rows


def https_json(url,payload=None):
    require(url.startswith('https://api.osv.dev/'),'UNTRUSTED_SCANNER_ENDPOINT')
    request=urllib.request.Request(url,data=None if payload is None else json.dumps(payload).encode(),headers={'Content-Type':'application/json','User-Agent':'ACP-candidate-security-qualification'},method='GET' if payload is None else 'POST')
    with urllib.request.urlopen(request,timeout=120) as response:
        require(response.geturl().startswith('https://api.osv.dev/'),'SCANNER_REDIRECT')
        raw=response.read(16_000_001);require(len(raw)<=16_000_000,'SCANNER_RESPONSE_LIMIT')
    return json.loads(raw)


def assess_response(rows,response,fetch):
    require(type(response) is dict and type(response.get('results')) is list and len(rows)==len(response['results']),'INCOMPLETE_SCANNER_RESPONSE')
    findings=[]
    for component,result in zip(rows,response['results']):
        require(type(result) is dict and set(result)<= {'vulns'},'INVALID_SCANNER_RESULT')
        for item in result.get('vulns',[]):
            require(type(item.get('id')) is str and item['id'] and '/' not in item['id'],'INVALID_ADVISORY_ID')
            advisory=fetch(item['id']);require(advisory.get('id')==item['id'],'ADVISORY_IDENTITY')
            severity=advisory.get('severity',[])
            matching=[a for a in advisory.get('affected',[]) if a.get('package',{}).get('name')==component['name'] and a.get('package',{}).get('ecosystem')==component['ecosystem']]
            findings.append({'affectedIdentityStatus':'MATCHED' if matching else 'UNRESOLVED_REQUIRES_TRIAGE','component':component,'advisory':advisory,'severity':severity,'severityLabel':advisory.get('database_specific',{}).get('severity','UNSPECIFIED'),'proposedFixedVersions':sorted({e['fixed'] for a in matching for r in a.get('ranges',[]) for e in r.get('events',[]) if 'fixed' in e}),'severityStatus':'SCORED_REQUIRES_TRIAGE' if severity else 'UNSCORED_BLOCKING','disposition':'REVIEW_REQUIRED'})
    return findings


def scan(root,package,output):
    rows=component_queries(root,package);save(output/'scanner-components.json',rows)
    result={'scope':'QUALIFICATION_ONLY','scannedAt':datetime.now(timezone.utc).isoformat(),'transport':'HTTPS_SYSTEM_TRUST_VERIFICATION','service':'https://api.osv.dev','databaseTimestamp':'NOT_EXPOSED','componentCount':len(rows),'coverage':sorted({r['source'] for r in rows}),'unknown':package['unknownComponents'],'unresolvedEmbeddedBuildArtifacts':list(json.loads((ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json').read_bytes())['embeddedArtifacts']),'findings':[],'status':'BLOCKED'}
    try:
        advisories={}
        # Bound batch size and retain exact request/response plus full advisories.
        for start in range(0,len(rows),100):
            part=rows[start:start+100];request={'queries':[{'package':{'ecosystem':r['ecosystem'],'name':r['name']},'version':r['version']} for r in part]}
            save(output/f'osv-request-{start}.json',request);response=https_json('https://api.osv.dev/v1/querybatch',request);save(output/f'osv-response-{start}.json',response)
            def fetch(identity):
                if identity not in advisories:
                    advisories[identity]=https_json('https://api.osv.dev/v1/vulns/'+urllib.parse.quote(identity,safe=''));save(output/(identity+'.json'),advisories[identity])
                return advisories[identity]
            result['findings'].extend(assess_response(part,response,fetch))
        result['osvStatus']='COMPLETED'
    except Exception as error:result['osvStatus']='UNAVAILABLE_OR_INVALID';result['error']=type(error).__name__+':'+str(error)
    p=subprocess.run(['npm','audit','--omit=dev','--json'],cwd=root/'frontend',capture_output=True,text=True,timeout=180)
    (output/'npm-audit.json').write_text(p.stdout);(output/'npm-audit.stderr').write_text(p.stderr)
    try:
        npm=json.loads(p.stdout);require(p.returncode in (0,1) and 'error' not in npm and 'vulnerabilities' in npm and 'metadata' in npm,'NPM_SCANNER_UNAVAILABLE')
        result['npm']={'exit':p.returncode,'status':'COMPLETED','vulnerabilities':npm['metadata']['vulnerabilities']}
    except (ValueError,KeyError):result['npm']={'exit':p.returncode,'status':'UNAVAILABLE_OR_INVALID'}
    # A zero result is bounded coverage only, not operational or legal approval.
    if result['osvStatus']=='COMPLETED' and result['npm']['status']=='COMPLETED' and not result['findings'] and not result['unknown'] and not result['unresolvedEmbeddedBuildArtifacts'] and result['npm']['exit']==0:result['status']='NO_KNOWN_FINDINGS_IN_SCANNED_IDENTITIES'
    save(output/'assessment.json',result);return result


READINESS_TEST=r'''package acp.domain;
import acp.infrastructure.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class PackageReadinessTest extends RuntimeConfigurationContractTest {
 @Test void missingIssuerRejected(){assertThrows(RuntimeException.class,()->RuntimeConfigurationContract.validate(production().withProperty("spring.security.oauth2.resourceserver.jwt.issuer-uri","${MISSING_ISSUER}"),new TargetModel(),true));}
 @Test void insecureProductionIssuerRejected(){assertThrows(RuntimeException.class,()->RuntimeConfigurationContract.validate(production().withProperty("spring.security.oauth2.resourceserver.jwt.issuer-uri","http://localhost:1234"),new TargetModel(),true));}
 @Test void unsupportedDeploymentRejected(){assertThrows(RuntimeException.class,()->RuntimeConfigurationContract.validate(production().withProperty("acp.runtime.deployment-profile","unrestricted"),new TargetModel(),true));}
 @Test void missingTransportRejected(){assertThrows(RuntimeException.class,()->RuntimeConfigurationContract.validate(production(),new TargetModel(),false));}
 @Test void missingPrincipalRejectedBeforeDatabaseAccess(){
  var jdbc=new org.springframework.jdbc.core.JdbcTemplate(); // No DataSource: any attempted database access fails.
  var factory=new org.springframework.beans.factory.support.StaticListableBeanFactory();
  var principals=factory.getBeanProvider(JobRuntime.PrincipalPort.class);
  var transports=factory.getBeanProvider(DeliveryRuntime.Transport.class);
  var error=assertThrows(IllegalStateException.class,()->new RuntimeBootstrap(jdbc,null,new TargetModel(),null,production(),principals,transports));
  assertEquals("JOB_PRINCIPAL_ADAPTER_REQUIRED",error.getMessage());assertNull(jdbc.getDataSource());
 }
 @Test void invalidConfigurationCannotStartPolling(){
  assertThrows(RuntimeException.class,()->RuntimeConfigurationContract.validate(production().withProperty("acp.runtime.mode","test"),new TargetModel(),true));
  assertFalse(Thread.getAllStackTraces().keySet().stream().anyMatch(t->t.isAlive()&&t.getName().equals("acp-runtime-poll")));
 }
}
'''


def qualify(workspace, *, offline=False, scans=True):
    from engineering.traceability.qualification import inputs
    from filesystem_artifacts import FilesystemArtifactStore
    from target_worker import bundle_digest
    import xml.etree.ElementTree as ET
    workspace=Path(workspace).resolve();workspace.mkdir(mode=0o700,exist_ok=False)
    sys.path.insert(0,str(ROOT/'tooling/audit'))
    tracked=['engineering/security/qualification.py','verification/security/test_security.py','engineering/dependency_resolution/maven-artifacts.lock.json','engineering/dependency_resolution/compiler-requirements.txt','tooling/requirements.txt']
    bindings={p:file_hash(ROOT/p) for p in tracked}
    result={'scope':'QUALIFICATION_ONLY','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'sourceHashes':bindings,'sealedParent':bundle_digest(),'applications':{},'confinement':confinement(workspace),'operationalSecurity':'NOT_ESTABLISHED','releaseClosure':'BLOCKED'}
    for domain in ('payment','case-management'):
        candidate,snapshot,request,plan=inputs(domain);root=workspace/domain
        FilesystemArtifactStore(root).apply(plan);candidate.verify_materialized(root,plan,snapshot,request)
        originals={p.relative_to(root).as_posix():file_hash(p) for p in root.rglob('*') if p.is_file()}
        test=root/'backend/src/test/java/acp/domain/PackageReadinessTest.java';test.write_text(READINESS_TEST)
        mvn=['mvn','-B','-ntp']+(['-o'] if offline else [])
        with (workspace/(domain+'-backend.log')).open('wb') as log:
            subprocess.run(mvn+['package','-Dtest=RuntimeConfigurationContractTest,PackageReadinessTest'],cwd=root/'backend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
        reports=list((root/'backend/target/surefire-reports').glob('TEST-*.xml'));counts={'tests':0,'failures':0,'errors':0,'skipped':0}
        for p in reports:
            r=ET.parse(p).getroot()
            for k in counts:counts[k]+=int(r.get(k,'0'))
        # The subclass also inherits the two original contract tests.
        require(counts=={'tests':10,'failures':0,'errors':0,'skipped':0},'PACKAGE_READINESS_TEST_INVENTORY:'+str(counts))
        with (workspace/(domain+'-frontend.log')).open('wb') as log:
            subprocess.run(['npm','ci','--ignore-scripts','--no-audit','--no-fund']+(['--offline'] if offline else []),cwd=root/'frontend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
            subprocess.run(['npm','run','build'],cwd=root/'frontend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        package=package_inventory(root);save(workspace/(domain+'-package.json'),package)
        require(all(file_hash(root/p)==d for p,d in originals.items()),'GENERATED_SOURCE_CHANGED')
        assessment=workspace/(domain+'-scan');assessment.mkdir()
        security=scan(root,package,assessment) if scans else {'status':'NOT_EXECUTED','reason':'Explicit offline run; current authenticated hosted scan still required.'}
        result['applications'][domain]={'candidate':candidate.descriptor(),'canonical':snapshot.read()['contentDigest'],'tests':counts,'package':package,'security':security,'externalTestSHA256':sha(READINESS_TEST.encode()),'sourcePreserved':True}
    require(bindings=={p:file_hash(ROOT/p) for p in bindings},'QUALIFICATION_SOURCE_CHANGED')
    result['artifacts']={str(p.relative_to(workspace)):file_hash(p) for p in workspace.rglob('*') if p.is_file() and not any(v in p.parts for v in ('node_modules','target')) and not p.is_symlink()}
    result['resultSHA256']=sha(json.dumps(result,sort_keys=True,separators=(',',':')).encode());save(workspace/'security-results.json',result)
    print(json.dumps({'scope':result['scope'],'sourceCommit':result['sourceCommit'],'applications':{d:{'tests':v['tests'],'security':v['security']['status']} for d,v in result['applications'].items()},'releaseClosure':'BLOCKED'}),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--offline',action='store_true');p.add_argument('--no-scans',action='store_true');a=p.parse_args();qualify(a.workspace,offline=a.offline,scans=not a.no_scans)
