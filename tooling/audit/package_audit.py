"""Deterministic distribution evidence; mutable security evidence is separate."""
from datetime import datetime,timezone
import importlib.metadata
import io
import json
from pathlib import Path
import tarfile
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

from phase6 import command,digest,write,ROOT

FORBIDDEN = (b'BrowserServer',b'browser-authorized',b'/__test/',b'ephemeral-test-only',
             b'browser-test-only',b'BrowserJwtDecoder',b'UIUpgradeSeedTest')


def backend_components(jar):
    components=[]
    with zipfile.ZipFile(jar) as archive:
        for name in sorted(archive.namelist()):
            if not name.startswith('BOOT-INF/lib/') or not name.endswith('.jar'):continue
            data=archive.read(name);properties=None;licenses=[]
            with zipfile.ZipFile(io.BytesIO(data)) as library:
                for entry in library.namelist():
                    if entry.startswith('META-INF/maven/') and entry.endswith('/pom.properties'):
                        properties=dict(line.split('=',1) for line in library.read(entry).decode().splitlines() if '=' in line and not line.startswith('#'))
                    if entry.startswith('META-INF/maven/') and entry.endswith('/pom.xml'):
                        try:
                            pom=ET.fromstring(library.read(entry));licenses += [n.text for n in pom.findall('.//{*}licenses/{*}license/{*}name') if n.text]
                        except ET.ParseError:pass
            if properties:
                group,name_,version=(properties[k] for k in ('groupId','artifactId','version'))
                purl=f'pkg:maven/{group}/{name_}@{version}'
            else:
                name_,version=name.rsplit('/',1)[-1][:-4].rsplit('-',1);group='UNKNOWN';purl=None
            components.append({'type':'library','group':group,'name':name_,'version':version,
                **({'purl':purl} if purl else {}),'hashes':[{'alg':'SHA-256','content':digest(data).split(':')[1]}],
                'licenses':[{'license':{'name':n}} for n in sorted(set(licenses))],
                'scope':'required','bom-ref':purl or name,'properties':[{'name':'acp:source','value':'packaged-backend'}]})
    return components


def frontend_components(front):
    lock=json.loads((front/'package-lock.json').read_text());rows=[]
    for path,value in sorted(lock['packages'].items()):
        if not path or 'version' not in value:continue
        name=path.rsplit('node_modules/',1)[-1];version=value['version']
        purl='pkg:npm/'+name.replace('@','%40')+'@'+version
        rows.append({'type':'library','name':name,'version':version,'purl':purl,'bom-ref':purl,
            'scope':'excluded' if value.get('dev') else 'required',
            'licenses':[{'license':{'name':value['license']}}] if isinstance(value.get('license'),str) else [],
            'properties':[{'name':'acp:source','value':'frontend-lock'},
                          {'name':'acp:lock-integrity','value':value.get('integrity','MISSING')} ]})
    return rows


def inspect_jar(data):
    hits=[]
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in archive.namelist():
            if name.startswith('BOOT-INF/classes/'):
                content=archive.read(name)
                for word in FORBIDDEN:
                    if word in name.encode() or word in content:hits.append(name+':'+word.decode())
    return hits


def package_bytes(project, config):
    files={}
    jar=project/'backend/target/application-0.1.0.jar'
    files['backend/application.jar']=jar.read_bytes()
    for directory in ('database','acp','contracts'):
        for p in sorted((project/directory).rglob('*')):
            if p.is_file():files[p.relative_to(project).as_posix()]=p.read_bytes()
    for p in sorted((project/'frontend/dist').rglob('*')):
        if p.is_file():files['frontend/'+p.relative_to(project/'frontend/dist').as_posix()]=p.read_bytes()
    files['runtime-configuration.json']=json.dumps(config,sort_keys=True,separators=(',',':')).encode()
    # No node_modules, source, tests, credentials or test identities are packaged.
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode='w',format=tarfile.USTAR_FORMAT) as tar:
        for path,data in sorted(files.items()):
            info=tarfile.TarInfo(path);info.size=len(data);info.mtime=1767225600
            info.uid=info.gid=0;info.uname=info.gname='';info.mode=0o644
            tar.addfile(info,io.BytesIO(data))
    hits=inspect_jar(files['backend/application.jar'])
    for path,data in files.items():
        if path.startswith('frontend/'):
            hits += [path+':'+word.decode() for word in FORBIDDEN if word in data]
    return raw.getvalue(),files,hits


def scan(components, front, output, domain):
    evidence={'scanAt':datetime.now(timezone.utc).isoformat(),'databaseTimestamp':'NOT_EXPOSED_BY_SERVICES',
        'severityPolicy':'High/Critical findings block release; unscored findings and unavailable coverage also block. No automatic suppressions.',
        'deterministicArtifactInput':False}
    evidence['npm']=command(['npm','audit','--omit=dev','--json'],front,output/(domain+'-npm-audit.json'),300,accepted=(0,1))
    queries=[{'package':{'purl':c['purl']}} for c in components if c.get('purl') and c['scope']=='required']
    try:
        request=urllib.request.Request('https://api.osv.dev/v1/querybatch',data=json.dumps({'queries':queries}).encode(),
            headers={'Content-Type':'application/json','User-Agent':'ACP-phase6-closure-audit'},method='POST')
        with urllib.request.urlopen(request,timeout=120) as response:results=json.load(response)
        evidence['osv']={'queries':queries,'response':results,'status':'COMPLETED',
            'findingCount':sum(len(r.get('vulns',[])) for r in results['results']),
            'disposition':'Any returned advisory requires severity/affected-version triage; not automatically accepted.'}
    except Exception as error:
        evidence['osv']={'status':'UNAVAILABLE','error':type(error).__name__,'coverage':'NOT_PROVEN'}
    write(output/(domain+'-security-assessment.json'),evidence)
    return evidence


def packages(output, generated):
    reports={}
    config=json.loads((generated/'payment/backend/src/main/resources/acp-runtime-configuration-contract.json').read_text())
    for domain in ('payment','case-management'):
        project=generated/domain;front=project/'frontend';backend=project/'backend'
        dependency_graph=command(['mvn','-B','-ntp','dependency:tree','-DoutputType=json','-DoutputFile=target/resolved-dependencies.json'],backend,output/(domain+'-maven-dependency-graph.log'),900)
        graph=backend/'target/resolved-dependencies.json'
        (output/(domain+'-maven-dependency-graph.json')).write_bytes(graph.read_bytes())
        identity=(front/'src/extensions/identity.ts').read_bytes()
        if b'browser-authorized' in identity:raise RuntimeError('TEST_IDENTITY_IN_SOURCE')
        builds=[];packages_=[];contents=None;hits=None
        for attempt in (1,2):
            builds.append(command(['mvn','-B','-ntp','package','-DskipTests'],backend,output/(domain+f'-package-backend-{attempt}.log'),900))
            builds.append(command(['npm','run','build'],front,output/(domain+f'-package-frontend-{attempt}.log'),300))
            package,contents,hits=package_bytes(project,config);packages_.append(package)
            (output/(domain+f'-production-{attempt}.tar')).write_bytes(package)
        components=backend_components(backend/'target/application-0.1.0.jar')+frontend_components(front)
        sbom={'bomFormat':'CycloneDX','specVersion':'1.6','version':1,
              'metadata':{'component':{'type':'application','name':'ACP '+domain,'version':json.loads((project/'acp/profile.json').read_text())['profile']}},
              'components':[{k:v for k,v in c.items() if k!='licenses' or v} for c in components]}
        sbom_binding=write(output/(domain+'-sbom.cdx.json'),sbom)
        python=[{'name':d.metadata['Name'],'version':d.version} for d in importlib.metadata.distributions()]
        dependencies={'components':components,'pythonGenerationEnvironment':sorted(python,key=lambda d:d['name']),
            'tzdb':json.loads((project/'acp/provenance.json').read_text())['build']['tzdb'],
            'workerPythonDependencies':'same pinned tooling/requirements.txt; imports bound by sealed bundle',
            'buildPluginsAndTransitiveLock':'INCOMPLETE','legalApproval':'NOT_CLAIMED',
            'unknownLicenses':[c['bom-ref'] for c in components if not c['licenses']],
            'noticesCompleteness':'OUTSTANDING'}
        dependency_binding=write(output/(domain+'-dependencies-licenses.json'),dependencies)
        security=scan(components,front,output,domain)
        reports[domain]={'packageDigest':digest(packages_[0]),'repeatPackageDigest':digest(packages_[1]),
            'reproducibility':'PASS' if packages_[0]==packages_[1] else 'FAIL',
            'testExclusion':'PASS' if not hits else 'FAIL','forbiddenHits':hits,'bytes':len(packages_[0]),
            'files':{p:digest(b) for p,b in contents.items()},'sbom':sbom_binding,'dependencies':dependency_binding,
            'security':security,'builds':builds,'configuration':config,
            'productionIdentityDigest':digest(identity),'deploymentReadiness':'BLOCKED_PENDING_ADAPTERS_AND_CONFIGURATION'}
        write(output/'package-report.json',reports)
    return reports
