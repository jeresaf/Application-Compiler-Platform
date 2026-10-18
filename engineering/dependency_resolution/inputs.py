"""Content-locked dependency inputs; candidate qualification, never release approval."""
import base64
import csv
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import stat
import zipfile


def require(condition, reason):
    if not condition:raise ValueError(reason)


def encode(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    path=Path(path);before=path.lstat()
    require(stat.S_ISREG(before.st_mode) and not path.is_symlink(),'NONREGULAR_INPUT')
    def stable(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    h=hashlib.sha256()
    with path.open('rb') as f:
        require(stable(os.fstat(f.fileno()))==stable(before),'REPLACED_INPUT')
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        require(stable(os.fstat(f.fileno()))==stable(before)==stable(path.lstat()),'INPUT_CHANGED')
    return h.hexdigest()


def inventory(root):
    root=Path(root);require(root.is_dir() and not root.is_symlink(),'INPUT_DIRECTORY')
    before=root.stat();files={}
    for p in sorted(root.rglob('*')):
        require(not p.is_symlink(),'SYMLINK_INPUT')
        if p.is_dir():continue
        require(len(files)<30000,'INPUT_FILE_LIMIT')
        files[p.relative_to(root).as_posix()]={'sha256':file_hash(p),'size':p.stat().st_size}
    after=root.stat();require((before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns),'INPUT_DIRECTORY_CHANGED')
    require(files,'EMPTY_INPUT')
    return files


def verify_tree(root,expected):
    require(type(expected) is dict and expected,'EMPTY_LOCK')
    require(inventory(root)==expected,'DEPENDENCY_SUBSTITUTION_OR_RESOLUTION_DRIFT')


def load_lock(path,expected_digest):
    raw=Path(path).read_bytes();require(digest(raw)==expected_digest,'LOCK_SUBSTITUTION')
    def pairs(items):
        d={}
        for k,v in items:require(k not in d,'DUPLICATE_LOCK_KEY');d[k]=v
        return d
    value=json.loads(raw,object_pairs_hook=pairs)
    require(encode(value)==raw and value['schema']=='acp-dependency-qualification/1' and value['scope']=='UNSEALED_CANDIDATE_QUALIFICATION_ONLY','LOCK_SCOPE_OR_ENCODING')
    return value


def exact_version(value):
    require(type(value) is str and re.fullmatch(r'[0-9][A-Za-z0-9._+\-]*',value) and not any(x in value.upper() for x in ('SNAPSHOT','LATEST','RELEASE')),'MUTABLE_DEPENDENCY_VERSION')
    return value


def npm_lock(raw):
    lock=json.loads(raw);require(lock.get('lockfileVersion')==3 and lock.get('packages'),'NPM_LOCK_VERSION')
    rows={}
    for name,p in lock['packages'].items():
        if not name:continue
        require(name.startswith('node_modules/') and '..' not in Path(name).parts and not p.get('link'),'NPM_EXTERNAL_OR_LINK_DEPENDENCY')
        exact_version(p.get('version'))
        url=p.get('resolved','');require(url.startswith('https://registry.npmjs.org/') and '?' not in url and '#' not in url,'NPM_MUTABLE_OR_EXTERNAL_RESOLUTION')
        integrity=p.get('integrity','');require(type(integrity) is str and integrity.startswith('sha512-'),'NPM_CONTENT_HASH_REQUIRED')
        try:decoded=base64.b64decode(integrity[7:],validate=True)
        except ValueError:raise ValueError('NPM_CONTENT_HASH_REQUIRED')
        require(len(decoded)==64,'NPM_CONTENT_HASH_REQUIRED')
        rows[name]={'version':p['version'],'resolved':url,'integrity':integrity,'optional':p.get('optional',False)}
    require(rows,'EMPTY_NPM_CLOSURE');return rows


def maven_closure(graph,repo,files):
    """Resolved graph plus every cached plugin/POM/JAR, a conservative superset.

    Completeness is demonstrated by subsequent clean offline compilation and
    packaging, not inferred from filenames or from dependency:tree alone.
    """
    nodes=[]
    def visit(n):
        version=exact_version(n['version']);group=n['groupId'];name=n['artifactId'];kind=n.get('type','jar');classifier=n.get('classifier','')
        for field in (group,name,kind,classifier):require(type(field) is str and '/' not in field and '\\' not in field and '..' not in field,'MAVEN_COORDINATE')
        base=group.replace('.','/')+'/'+name+'/'+version+'/'+name+'-'+version
        if group!='acp.generated':
            extension='jar' if kind in ('jar','test-jar','bundle','maven-plugin') else kind
            artifact=base+('-'+classifier if classifier else '')+'.'+extension
            require(artifact in files and base+'.pom' in files,'INCOMPLETE_MAVEN_CLOSURE')
            nodes.append({'group':group,'artifact':name,'version':version,'scope':n.get('scope','compile'),'path':artifact,'sha256':files[artifact]['sha256']})
        for child in n.get('children',[]):visit(child)
    visit(graph)
    artifacts={}
    for name,row in files.items():
        if name.endswith(('.jar','.pom')):
            parts=Path(name).parts;require(len(parts)>=4,'MAVEN_LAYOUT');exact_version(parts[-2]);require(parts[-1].startswith(parts[-3]+'-'+parts[-2]),'MAVEN_ARTIFACT_IDENTITY');artifacts[name]=row
    require(nodes and artifacts,'EMPTY_MAVEN_CLOSURE');return {'resolvedGraph':nodes,'allRuntimeAndBuildArtifacts':artifacts,'inventorySemantics':'CONSERVATIVE_SUPERSET_VERIFIED_BY_OFFLINE_BUILD'}


def wheel_inputs(directory,requirements,installed=True):
    expected={}
    for line in Path(requirements).read_text().splitlines():
        if not line or line.startswith('#'):continue
        m=re.fullmatch(r'([a-zA-Z0-9-]+)==([^ ]+) --hash=sha256:([0-9a-f]{64})',line);require(m is not None,'UNPINNED_COMPILER_REQUIREMENT')
        name,version,h=m.groups();exact_version(version);expected[name.replace('_','-').lower()]=(version,h)
    found={}
    for path in Path(directory).glob('*.whl'):
        with zipfile.ZipFile(path) as z:
            metadata=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')];require(len(metadata)==1,'WHEEL_METADATA')
            text=z.read(metadata[0]).decode();name=re.search(r'^Name: (.+)$',text,re.M)[1].lower().replace('_','-');version=re.search(r'^Version: (.+)$',text,re.M)[1]
            if name not in expected:continue
            require(name not in found and (version,file_hash(path))==expected[name],'COMPILER_WHEEL_SUBSTITUTION')
            if installed:
                distribution=importlib.metadata.distribution(name);require(distribution.version==version,'COMPILER_VERSION')
                package_dirs=set();members=set()
                for member in z.namelist():
                    if member.endswith('/') or '.dist-info/' in member:continue
                    require('.data/' not in member and '..' not in Path(member).parts,'WHEEL_LAYOUT')
                    target=Path(distribution.locate_file(member));require(target.read_bytes()==z.read(member),'INSTALLED_COMPILER_SUBSTITUTION')
                    members.add(member);package_dirs.add(member.split('/')[0])
                base=Path(distribution.locate_file(''))
                for directory_name in package_dirs:
                    folder=base/directory_name
                    if not folder.is_dir():continue
                    actual={p.relative_to(base).as_posix() for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
                    require(actual<=members,'EXTRA_COMPILER_SOURCE')
            found[name]={'version':version,'wheel':path.name,'sha256':expected[name][1]}
    require(set(found)==set(expected),'MISSING_COMPILER_WHEEL');return found


def compare_packages(first,second):
    require(set(first)==set(second)=={'payment','case-management'},'INDEPENDENT_APPLICATION_COVERAGE')
    for name in first:
        require(first[name]==second[name],'INDEPENDENT_CLEAN_BUILD_MISMATCH:'+name)
    return {'status':'QUALIFICATION_ONLY','applications':first,'claim':'Two independent materializations and offline caches; no release approval'}


def installed_npm(front,locked):
    """Verify actual versions and freeze extracted code, including .bin targets."""
    front=Path(front);root=front/'node_modules';require(root.is_dir() and not root.is_symlink(),'MISSING_NODE_MODULES')
    for relative,row in locked.items():
        package=front/relative/'package.json'
        if not package.exists():
            require(row['optional'] is True,'MISSING_REQUIRED_NPM_PACKAGE');continue
        require(not package.is_symlink(),'NPM_PACKAGE_SYMLINK')
        value=json.loads(package.read_bytes())
        require(value['version']==row['version'] and value['name']==relative.rsplit('node_modules/',1)[-1],'INSTALLED_NPM_VERSION_OR_IDENTITY')
    result={}
    for p in sorted(root.rglob('*')):
        relative=p.relative_to(root).as_posix()
        if p.is_symlink():
            target=p.resolve();require(target.is_relative_to(root.resolve()) and target.is_file(),'NPM_BIN_ESCAPE')
            result[relative]={'link':os.readlink(p),'targetSHA256':file_hash(target)}
        elif p.is_file():result[relative]={'sha256':file_hash(p)}
    require(result,'EMPTY_NPM_INSTALL');return result


def seed_maven(seed,target,reference,online=False):
    """Hash BEFORE copying or executing; never bless fresh resolver output.

    Only pre-registered immutable artifacts can be acquired from Maven Central.
    No arbitrary seed JAR, extension or settings file enters the build cache.
    """
    from concurrent.futures import ThreadPoolExecutor
    import shutil
    import urllib.request
    require(reference['schema']=='acp-maven-inputs/1' and reference['scope']=='UNSEALED_CANDIDATE_QUALIFICATION_ONLY','MAVEN_REFERENCE_SCOPE')
    target=Path(target);target.mkdir(exist_ok=False)
    def acquire(item):
        relative,row=item;require(not Path(relative).is_absolute() and '..' not in Path(relative).parts and relative.endswith(('.jar','.pom')),'MAVEN_REFERENCE_PATH')
        source=Path(seed)/relative;destination=target/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        if source.exists():
            require(file_hash(source)==row['sha256'] and source.stat().st_size==row['size'],'PINNED_MAVEN_SUBSTITUTION')
            shutil.copyfile(source,destination)
        else:
            require(online,'MISSING_PINNED_MAVEN_ARTIFACT:'+relative)
            url='https://repo.maven.apache.org/maven2/'+relative
            with urllib.request.urlopen(url,timeout=60) as response:
                require(response.geturl()==url,'MAVEN_REDIRECT')
                data=response.read(row['size']+1)
            require(len(data)==row['size'] and digest(data)==row['sha256'],'DOWNLOADED_MAVEN_SUBSTITUTION')
            destination.write_bytes(data)
        require(file_hash(destination)==row['sha256'],'MAVEN_COPY_SUBSTITUTION')
    with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(acquire,reference['artifacts'].items()))
    verify_tree(target,reference['artifacts'])


def plugin_selection(log):
    return sorted(l.removeprefix('[INFO] ').strip() for l in log.splitlines() if l.startswith('[INFO] Resolved plugin') or l.startswith('[INFO]       '))


def verify_maven_resolution(domain,graph,plugins,files,reference):
    artifacts={n:r for n,r in files.items() if n.endswith(('.jar','.pom'))}
    require(artifacts==reference['artifacts'],'PINNED_MAVEN_INVENTORY_DRIFT')
    require(graph==reference['graphs'][domain],'PINNED_MAVEN_GRAPH_DRIFT')
    require(plugins==reference['plugins'][domain],'PINNED_PLUGIN_RESOLUTION_DRIFT')


def embedded_jars(repo,files):
    """Explicit hashed origin edges for binaries supplied inside build plugins."""
    found={}
    for relative,row in files.items():
        if not relative.endswith('.jar'):continue
        container=Path(repo)/relative;require(file_hash(container)==row['sha256'],'EMBEDDED_CONTAINER_SUBSTITUTION')
        with zipfile.ZipFile(container) as z:
            for entry in z.infolist():
                if not entry.filename.endswith('.jar'):continue
                require(entry.file_size<=64*1024*1024 and '..' not in Path(entry.filename).parts,'EMBEDDED_JAR_LIMIT')
                raw=z.read(entry)
                found[relative+'!/'+entry.filename]={'container':relative,'containerSHA256':row['sha256'],'entry':entry.filename,'sha256':digest(raw),'size':len(raw)}
    return found


def packaged_dependencies(path,maven_files,embedded):
    origins={}
    for name,row in maven_files.items():
        if name.endswith('.jar'):origins.setdefault(row['sha256'],[]).append('maven:'+name)
    for name,row in embedded.items():origins.setdefault(row['sha256'],[]).append('embedded:'+name)
    result={}
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not(name.startswith('BOOT-INF/lib/') and name.endswith('.jar')):continue
            h=digest(z.read(name));require(h in origins,'UNLOCKED_PACKAGED_DEPENDENCY:'+name)
            result[name]={'sha256':h,'lockedOrigins':sorted(origins[h])}
    require(result,'NO_RUNTIME_DEPENDENCIES');return result


def tool_inventory(root):
    """Installed host tools may have declared OS-managed links.

    Record the logical link, exact resolved target and bytes. This function is
    never used for dependency caches, wheels, application or compiler source.
    """
    root=Path(root);require(root.is_dir() and not root.is_symlink(),'TOOLCHAIN_ROOT')
    found={}
    def stamp(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_mtime_ns,s.st_ctime_ns)
    def visit(directory,prefix,ancestors):
        identity=directory.stat();key=(identity.st_dev,identity.st_ino)
        require(key not in ancestors and len(ancestors)<64,'TOOLCHAIN_LINK_CYCLE')
        ancestors=ancestors|{key}
        for p in sorted(directory.iterdir()):
            require(len(found)<30000,'TOOLCHAIN_FILE_LIMIT');name=prefix+p.name
            before=p.lstat()
            if p.is_symlink():
                try:target=p.resolve(strict=True)
                except (OSError,RuntimeError):raise ValueError('TOOLCHAIN_LINK_TARGET')
                link=os.readlink(p)
                if target.is_dir():
                    found[name]={'link':link,'directoryTarget':str(target)};visit(target,name+'/',ancestors)
                else:
                    require(target.is_file(),'TOOLCHAIN_NONREGULAR_LINK')
                    found[name]={'link':link,'target':str(target),'sha256':file_hash(target),'size':target.stat().st_size}
                require(stamp(before)==stamp(p.lstat()) and os.readlink(p)==link,'TOOLCHAIN_LINK_CHANGED')
            elif p.is_dir():visit(p,name+'/',ancestors)
            else:found[name]={'sha256':file_hash(p),'size':p.stat().st_size}
        require(stamp(identity)==stamp(directory.stat()),'TOOLCHAIN_DIRECTORY_CHANGED')
    visit(root,'',set());require(found,'EMPTY_TOOLCHAIN');return found
