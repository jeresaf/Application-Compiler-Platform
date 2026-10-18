"""Resolve once; qualify #18 and #32 using only content-locked offline inputs.

No sealed-generator changes, database operation, release/admission or deployment.
The acquisition lock records observed bytes, not publisher or human approval.
"""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import platform
import tarfile
from types import SimpleNamespace
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.dependency_resolution.inputs import (require,encode,digest,file_hash,inventory,verify_tree,load_lock,npm_lock,maven_closure,wheel_inputs,compare_packages,installed_npm,seed_maven,plugin_selection,verify_maven_resolution,embedded_jars,packaged_dependencies,tool_inventory)

DEPENDENCY='org.apache.maven.plugins:maven-dependency-plugin:3.10.0:'
JAR='org.apache.maven.plugins:maven-jar-plugin:3.5.1:jar'
BOOT='org.springframework.boot:spring-boot-maven-plugin:4.1.1:repackage'
SETTINGS=b'<settings xmlns="http://maven.apache.org/SETTINGS/1.2.0"><mirrors><mirror><id>central</id><mirrorOf>*</mirrorOf><url>https://repo.maven.apache.org/maven2</url></mirror></mirrors></settings>\n'


def execute(args,cwd,home,tools,log):
    home=Path(home);home.mkdir(parents=True,exist_ok=True)
    env={'PATH':os.pathsep.join([str(Path(tools[n]).parent) for n in ('node','mvn','java')]+['/usr/bin','/bin']),
         'JAVA_HOME':str(Path(tools['java']).parents[1]),'MAVEN_USER_HOME':str(home/'.m2'),'HOME':str(home),'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC',
         'SOURCE_DATE_EPOCH':'1767225600','PYTHONDONTWRITEBYTECODE':'1','PYTHONPYCACHEPREFIX':str(home/'pycache')}
    with Path(log).open('wb') as stream:
        result=subprocess.run(args,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=1200)
    require(result.returncode==0,'COMMAND_FAILED:'+str(log));return result.returncode


def maven(tools,repo,settings,offline=True):
    return [tools['mvn'],'-B','-ntp',*(['-o'] if offline else []),'-s',str(settings),'-gs',str(settings),'-Dmaven.repo.local='+str(repo)]


def toolchains():
    result={k:str(Path(shutil.which(k)).resolve()) for k in ('java','javac','mvn','node','npm')}
    # Node must execute the exact locked npm CLI, never a mutable PATH shim.
    require(subprocess.check_output([result['node'],'--version'],text=True).strip()=='v24.21.0','NODE_VERSION')
    require(sys.version_info[:2]==(3,14),'PYTHON_VERSION')
    result['python']=str(Path(sys.executable).absolute())
    roots={'jdk-bin':Path(result['java']).parent,'jdk-lib':Path(result['java']).parents[1]/'lib',
           'maven':Path(result['mvn']).parents[1],'npm':Path(result['npm']).parents[1]}
    files={}
    for label,root in roots.items():files[label]={'root':str(root),'files':tool_inventory(root)}
    files['node']={'path':result['node'],'sha256':file_hash(result['node'])}
    files['python']={'path':str(Path(sys.executable).resolve()),'sha256':file_hash(Path(sys.executable).resolve())}
    versions={n:subprocess.check_output(cmd,stderr=subprocess.STDOUT,text=True).strip() for n,cmd in {
        'java':[result['java'],'-version'],'javac':[result['javac'],'-version'],'maven':[result['mvn'],'-version'],
        'node':[result['node'],'--version'],'npm':[result['node'],result['npm'],'--version'],'python':[sys.executable,'--version']}.items()}
    require(versions['javac'].split()[1].split('.')[0]=='21','JAVA_VERSION')
    stdlib=Path(sysconfig.get_path('stdlib'))
    files['python-runtime']={'runtimeFiles':{str(p):{'target':str(p.resolve()),'sha256':file_hash(p.resolve())} for p in sorted(stdlib.rglob('*')) if p.suffix in ('.py','.so') and 'site-packages' not in p.parts and 'dist-packages' not in p.parts and '__pycache__' not in p.parts}}
    return {'executables':result,'inventories':files,'versions':versions}


def verify_tools(locked):
    for item in locked['inventories'].values():
        if 'runtimeFiles' in item:
            for logical,row in item['runtimeFiles'].items():require(str(Path(logical).resolve())==row['target'] and file_hash(Path(row['target']))==row['sha256'],'PYTHON_RUNTIME_SUBSTITUTION')
        elif 'root' in item:require(tool_inventory(Path(item['root']))==item['files'],'TOOLCHAIN_INPUT_SUBSTITUTION')
        else:require(file_hash(Path(item['path']))==item['sha256'],'TOOLCHAIN_SUBSTITUTION')


def materialize(domain,root):
    from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
    from compiler_contracts import Document,fingerprint
    from canonical_json import load
    from filesystem_artifacts import FilesystemArtifactStore
    snapshot=Document.of(load(ROOT/f'test-corpus/deterministic-v04/{domain}-canonical-candidate.json'))
    candidate=SuccessorCandidate();request=SimpleNamespace(compiler='compiler/dependency-qualification',pipeline='pipeline/dependency-qualification',snapshot_digest=snapshot.read()['contentDigest'],features=(),generator=candidate.generator)
    plan=candidate.plan(snapshot,request);FilesystemArtifactStore(root).apply(plan);candidate.verify_materialized(root,plan,snapshot,request)
    return {'artifactPlanDigest':fingerprint(plan),'candidate':candidate.descriptor(),'snapshot':snapshot.read()['contentDigest'],'source':inventory(root)}


def npm(tools,cache,settings,offline=True):
    return [tools['node'],tools['npm'],'--userconfig='+str(settings),'--globalconfig='+str(settings)+'.global','--cache='+str(cache),*(['--offline'] if offline else [])]


def prepare(workspace,maven_seed,npm_seed,wheels,online=False):
    workspace=Path(workspace).absolute();workspace.mkdir(mode=0o700,exist_ok=False)
    frozen=workspace/'frozen';frozen.mkdir();repo=frozen/'m2';cache=frozen/'npm';wheel=frozen/'wheels'
    reference=json.loads((ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json').read_bytes())
    seed_maven(maven_seed,repo,reference,online);shutil.copytree(npm_seed,cache)
    # Ignore only mutable npm logs; cache content and index are both frozen.
    for p in cache.glob('_logs/*'):p.unlink()
    wheel.mkdir()
    requirements=ROOT/'engineering/dependency_resolution/compiler-requirements.txt'
    compiler=wheel_inputs(wheels,requirements)
    for row in compiler.values():shutil.copyfile(Path(wheels)/row['wheel'],wheel/row['wheel'])
    tools=toolchains();require(tools['versions']['maven'].splitlines()[0].split()[2]==reference['mavenVersion'],'MAVEN_VERSION');settings=workspace/'settings.xml';settings.write_bytes(SETTINGS);npmsettings=workspace/'npmrc';npmsettings.write_bytes(b'');Path(str(npmsettings)+'.global').write_bytes(b'')
    graphs={};apps={}
    for domain in ('payment','case-management'):
        root=workspace/('resolve-'+domain);apps[domain]=materialize(domain,root)
        home=workspace/('resolve-home-'+domain)
        for goal in ('go-offline','tree'):
            args=maven(tools['executables'],repo,settings)+[DEPENDENCY+goal]
            if goal=='tree':args+=['-DoutputType=json','-DoutputFile='+str(workspace/(domain+'-graph.json'))]
            execute(args,root/'backend',home,tools['executables'],workspace/(domain+'-'+goal+'.log'))
        graphs[domain]=json.loads((workspace/(domain+'-graph.json')).read_bytes())
        npm_lock((root/'frontend/package-lock.json').read_bytes())
        execute(npm(tools['executables'],cache,npmsettings,not online)+['ci','--ignore-scripts','--no-audit','--no-fund'],root/'frontend',home,tools['executables'],workspace/(domain+'-npm-acquire.log'))
        # Only the newly constructed resolution workspace is removed.
        shutil.rmtree(root/'frontend/node_modules')
    maven_files=inventory(repo)
    embedded=embedded_jars(repo,maven_files);require(embedded==reference['embeddedArtifacts'],'EMBEDDED_PLUGIN_RESOLUTION_DRIFT')
    for domain in graphs:verify_maven_resolution(domain,graphs[domain],plugin_selection((workspace/(domain+'-go-offline.log')).read_text()),maven_files,reference)
    lock={'schema':'acp-dependency-qualification/1','scope':'UNSEALED_CANDIDATE_QUALIFICATION_ONLY',
          'host':{'system':platform.system(),'machine':platform.machine()},'toolchains':tools,'compiler':compiler,'compilerRequirementsSHA256':file_hash(requirements),'mavenReferenceSHA256':file_hash(ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json'),
          'embeddedArtifacts':embedded,'mavenFiles':maven_files,'npmFiles':inventory(cache),'wheelFiles':inventory(wheel),
          'applications':{d:{'inputs':apps[d],'maven':maven_closure(graphs[d],repo,maven_files),'graph':graphs[d],
                             'npm':npm_lock((workspace/('resolve-'+d)/'frontend/package-lock.json').read_bytes())} for d in apps}}
    # Freeze an exact source export, including the qualification code being
    # tested, without Git metadata or any materialized application/build cache.
    source=frozen/'source';source.mkdir()
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    for name in sorted(set(names)-{''}):
        original=ROOT/name;require(not original.is_symlink() and original.is_file(),'SOURCE_EXPORT_INPUT')
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
    lock['sourceFiles']=inventory(source)
    raw=encode(lock);(workspace/'dependency-lock.json').write_bytes(raw)
    (workspace/'dependency-lock.sha256').write_text(digest(raw)+'\n')
    return digest(raw)


def package(root):
    """Hash exact JAR and frontend bytes; never normalize a differing build."""
    jar=root/'backend/target/application-0.1.0.jar';require(jar.is_file(),'MISSING_BUILT_PACKAGE')
    files={'backend/application.jar':jar.read_bytes()}
    for directory in ('frontend/dist','database','acp','contracts'):
        for p in (root/directory).rglob('*'):
            require(not p.is_symlink(),'PACKAGE_SYMLINK')
            if p.is_file():files[p.relative_to(root).as_posix()]=p.read_bytes()
    require('frontend/dist/index.html' in files,'MISSING_FRONTEND_PACKAGE')
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w',format=tarfile.USTAR_FORMAT) as tar:
        for name,raw in sorted(files.items()):
            member=tarfile.TarInfo(name);member.size=len(raw);member.mtime=1767225600;member.mode=0o644;tar.addfile(member,io.BytesIO(raw))
    return archive.getvalue(),{name:digest(raw) for name,raw in sorted(files.items())}


def worker(workspace,expected,run_id):
    workspace=Path(workspace);lock=load_lock(workspace/'dependency-lock.json',expected);frozen=workspace/'frozen'
    require(inventory(ROOT)==lock['sourceFiles'],'EXPORTED_SOURCE_SUBSTITUTION')
    verify_tools(lock['toolchains']);require(file_hash(ROOT/'engineering/dependency_resolution/compiler-requirements.txt')==lock['compilerRequirementsSHA256'],'COMPILER_REQUIREMENTS_CHANGED')
    require(file_hash(ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json')==lock['mavenReferenceSHA256'],'MAVEN_REFERENCE_CHANGED')
    require(wheel_inputs(frozen/'wheels',ROOT/'engineering/dependency_resolution/compiler-requirements.txt')==lock['compiler'],'COMPILER_RESOLUTION_DRIFT')
    for directory,key in (('m2','mavenFiles'),('npm','npmFiles'),('wheels','wheelFiles')):verify_tree(frozen/directory,lock[key])
    run=workspace/('clean-'+run_id);run.mkdir(mode=0o700,exist_ok=False);repo=run/'m2';cache=run/'npm';home=run/'home'
    shutil.copytree(frozen/'m2',repo);shutil.copytree(frozen/'npm',cache)
    settings=run/'settings.xml';settings.write_bytes(SETTINGS);npmsettings=run/'npmrc';npmsettings.write_bytes(b'');Path(str(npmsettings)+'.global').write_bytes(b'')
    tools=lock['toolchains']['executables'];results={}
    for domain,reference in lock['applications'].items():
        root=run/domain;actual=materialize(domain,root);require(actual==reference['inputs'],'GENERATED_SOURCE_DRIFT')
        graph=run/(domain+'-graph.json')
        execute(maven(tools,repo,settings)+[DEPENDENCY+'tree','-DoutputType=json','-DoutputFile='+str(graph)],root/'backend',home,tools,run/(domain+'-tree.log'))
        require(json.loads(graph.read_bytes())==reference['graph'],'DEPENDENCY_GRAPH_DRIFT')
        require(npm_lock((root/'frontend/package-lock.json').read_bytes())==reference['npm'],'NPM_RESOLUTION_DRIFT')
        # Explicit package goals avoid a misleading test-skip flag. Existing
        # application test/runtime CI jobs remain separate and mandatory.
        execute(maven(tools,repo,settings)+['clean','test-compile',JAR,BOOT],root/'backend',home,tools,run/(domain+'-backend.log'))
        execute(npm(tools,cache,npmsettings)+['ci','--ignore-scripts','--no-audit','--no-fund'],root/'frontend',home,tools,run/(domain+'-npm.log'))
        npm_before=installed_npm(root/'frontend',reference['npm'])
        for goal in ('typecheck','build'):execute(npm(tools,cache,npmsettings)+['run',goal],root/'frontend',home,tools,run/(domain+'-'+goal+'.log'))
        require(installed_npm(root/'frontend',reference['npm'])==npm_before,'EXTRACTED_NPM_DEPENDENCY_CHANGED')
        raw,contents=package(root);(run/(domain+'.tar')).write_bytes(raw)
        # Exact origin edges cover runtime JARs injected by build plugins too.
        dependencies=packaged_dependencies(root/'backend/target/application-0.1.0.jar',lock['mavenFiles'],lock['embeddedArtifacts'])
        results[domain]={'artifactPlanDigest':actual['artifactPlanDigest'],'packageSHA256':digest(raw),'files':contents,'source':reference['inputs']['source'],'runtimeDependencies':dependencies}
        for p,row in reference['inputs']['source'].items():require(file_hash(root/p)==row['sha256'],'BUILD_CHANGED_SOURCE')
        # Retain exact packages/logs; discard only new, disposable output/cache.
        shutil.rmtree(root/'frontend/node_modules');shutil.rmtree(root/'backend/target');shutil.rmtree(root/'frontend/dist')
        require(inventory(root)==reference['inputs']['source'],'OWNERSHIP_OR_SOURCE_DRIFT')
    # Maven may update bookkeeping, but may never add/change a resolution input.
    before={p:r for p,r in lock['mavenFiles'].items() if p.endswith(('.jar','.pom','.xml','.module'))}
    after={p:r for p,r in inventory(repo).items() if p.endswith(('.jar','.pom','.xml','.module'))};require(before==after,'MAVEN_BUILD_INPUT_DRIFT')
    require(inventory(cache/'_cacache/content-v2')==inventory(frozen/'npm/_cacache/content-v2'),'NPM_BUILD_INPUT_DRIFT')
    verify_tools(lock['toolchains']);verify_tree(frozen/'source',lock['sourceFiles'])
    (run/'results.json').write_bytes(encode(results));shutil.rmtree(repo);shutil.rmtree(cache)
    return results


def qualify(workspace,expected):
    workspace=Path(workspace);lock=load_lock(workspace/'dependency-lock.json',expected);source=workspace/'frozen/source'
    script=source/'engineering/dependency_resolution/qualify.py';python=lock['toolchains']['executables']['python'];results=[]
    # Distinct processes, generated trees, source exports and empty user homes.
    for label in ('one','two'):
        export=workspace/('source-'+label);shutil.copytree(source,export);verify_tree(export,lock['sourceFiles'])
        command=[python,'-I','-B','-X','pycache_prefix='+str(workspace/('compiler-pycache-'+label)),str(export/'engineering/dependency_resolution/qualify.py'),'worker','--workspace',str(workspace),'--expected',expected,'--run-id',label]
        execute(command,export,workspace/('compiler-home-'+label),lock['toolchains']['executables'],workspace/('clean-'+label+'.log'))
        results.append(json.loads((workspace/('clean-'+label)/'results.json').read_bytes()))
    comparison=compare_packages(*results);comparison['dependencyLockSHA256']=expected
    comparison['criteria']={'18':'QUALIFICATION_ONLY_OFFLINE_CLOSURE_VERIFIED','32':'QUALIFICATION_ONLY_TWO_CLEAN_PACKAGES_MATCH'}
    comparison['release']='PHASE6_RELEASE_CLOSURE_BLOCKED';(workspace/'qualification.json').write_bytes(encode(comparison));return comparison


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=['prepare','worker','qualify']);parser.add_argument('--workspace',required=True);parser.add_argument('--expected');parser.add_argument('--run-id');parser.add_argument('--maven-seed');parser.add_argument('--npm-seed');parser.add_argument('--wheels');parser.add_argument('--online-acquire',action='store_true');args=parser.parse_args()
    if args.mode=='prepare':print(prepare(args.workspace,args.maven_seed,args.npm_seed,args.wheels,args.online_acquire))
    elif args.mode=='worker':worker(args.workspace,args.expected,args.run_id)
    else:print(json.dumps(qualify(args.workspace,args.expected),sort_keys=True))
