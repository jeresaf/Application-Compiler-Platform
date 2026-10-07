"""Transitive evidence inventory; declared licenses are not legal clearance."""
import hashlib,json,os,tomllib,xml.etree.ElementTree as ET
from pathlib import Path
from run import AREA
NS={'m':'http://maven.apache.org/POM/4.0.0'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pom_licenses(path,seen=()):
    if path in seen or not path.exists():return [],['missing/inherited POM '+path.name]
    root=ET.parse(path).getroot();licenses=[{'name':e.findtext('m:name',namespaces=NS),'url':e.findtext('m:url',namespaces=NS)} for e in root.findall('m:licenses/m:license',NS)]
    if licenses:return licenses,[]
    parent=root.find('m:parent',NS)
    if parent is None:return [],['No declared/inherited license located']
    values=[parent.findtext('m:'+k,namespaces=NS) for k in ('groupId','artifactId','version')]
    if not all(values) or any('${' in v for v in values):return [],['Unresolved parent coordinates']
    group,artifact,version=values
    return pom_licenses(AREA/'.cache/m2'/group.replace('.','/')/artifact/version/f'{artifact}-{version}.pom',(*seen,path))
def main():
    npm=json.loads((AREA/'langium/package-lock.json').read_text());node=[]
    for path,v in npm['packages'].items():
        if not path:continue
        package=AREA/'langium'/path/'package.json';metadata=json.loads(package.read_text()) if package.exists() else {}
        node.append({'package':path.removeprefix('node_modules/'),'version':v.get('version'),'source':v.get('resolved'),'integrity':v.get('integrity'),'license':v.get('license') or metadata.get('license'),'developmentOnly':v.get('dev',False),'redistribution':'Retain package license/notice and inspect bundled dependencies; lock metadata is not clearance.'})
    jvm=[]
    for jar in (AREA/'xtext/target/classpath.txt').read_text().strip().split(':'):
        path=Path(jar);relative=str(path.relative_to(AREA/'.cache/m2'));licenses,unknown=pom_licenses(path.with_suffix('.pom'))
        jvm.append({'artifact':relative,'source':'https://repo.maven.apache.org/maven2/'+relative,'sha256':digest(path),'licenses':licenses,'unresolved':unknown,'redistribution':'Review artifact notices, EPL source obligations and applicable linking/Classpath exceptions; do not infer from top-level Xtext license.'})
    lock=tomllib.loads((AREA/'core-runtime/Cargo.lock').read_text());rust=[]
    for p in lock['package']:
        if 'source' not in p:continue
        candidates=list((AREA/'.cache/cargo/registry/src').glob(f'*/{p["name"]}-{p["version"]}/Cargo.toml'))
        if not candidates:
            candidates=list((Path(os.environ.get('CARGO_HOME',str(Path.home()/'.cargo')))/'registry/src').glob(f'*/{p["name"]}-{p["version"]}/Cargo.toml'))
        metadata=tomllib.loads(candidates[0].read_text())['package'] if candidates else {}
        rust.append({'package':p['name'],'version':p['version'],'source':p['source'],'sha256':p.get('checksum'),'license':metadata.get('license'),'repository':metadata.get('repository'),'unresolved':[] if metadata.get('license') else ['crate license metadata not restored']})
    license_unknown=[x['artifact'] for x in jvm if x['unresolved']]
    result={'npm':node,'jvm':jvm,'rust':rust,'generatedCode':{'antlr':'ANTLR BSD-3-Clause tool/runtime; generated code is user output but runtime notices remain relevant. Release review still required.','langium':'MIT generated infrastructure and runtime; preserve applicable notices.','xtext':'EPL-2.0 tool/runtime and mixed transitive licenses; output/runtime redistribution review needed. Patched ANTLR3 generator artifact source/build provenance remains unresolved.'},'unresolvedJvmLicenses':license_unknown,'productionClearance':'UNKNOWN: declared/inherited metadata inventory does not establish complete legal and redistribution clearance.','reproduction':{'npmLockSha256':digest(AREA/'langium/package-lock.json'),'cargoLockSha256':digest(AREA/'core-runtime/Cargo.lock'),'maven':'Resolved artifact digest manifest captured; cached offline resolution and clean Ubuntu network restore are separate evidence. No independently rebuildable patched generator/source provenance proof.'},'treeSitterWasm':'REJECTED_FOR_PRODUCTION; exact binary digest and reason in source.json'}
    (AREA/'results/phase5b/inventory.json').write_text(json.dumps(result,indent=2)+'\n')
    print(f'Inventoried {len(node)} npm, {len(jvm)} JVM, {len(rust)} Rust packages; unresolved JVM license metadata: {len(license_unknown)}')
if __name__=='__main__':main()
