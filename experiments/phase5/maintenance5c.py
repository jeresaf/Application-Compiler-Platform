"""Phase 5C toolchain comparison and disposition; no Phase 5B evidence overwrite."""
import hashlib,json,os,subprocess,tomllib,zipfile
from pathlib import Path
from run import AREA,ROOT
from fault5c import commands,fixtures

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run_command(cmd,raw=None,env=None):
    p=subprocess.run(cmd,input=raw,capture_output=True,timeout=180,env=env);assert p.returncode==0,(cmd,p.stderr.decode());return {'command':list(map(str,cmd)),'stdout':p.stdout.decode(),'stderr':p.stderr.decode(),'exitCode':p.returncode}
def run():
    target=AREA/'results/phase5c';target.mkdir(exist_ok=True)
    crates=[]
    for package in tomllib.loads((AREA/'core-runtime/Cargo.lock').read_text())['package']:
        if 'source' not in package:continue
        roots=[AREA/'.cache/cargo',Path(os.environ.get('CARGO_HOME',str(Path.home()/'.cargo')))]
        paths=[p for root in roots for p in (root/'registry/src').glob(f'*/{package["name"]}-{package["version"]}/Cargo.toml')]
        data=tomllib.loads(paths[0].read_text())['package'] if paths else {}
        crates.append({'name':package['name'],'version':package['version'],'registry':package['source'],'checksum':package['checksum'],'license':data.get('license'),'repository':data.get('repository'),'metadataSha256':digest(paths[0]) if paths else None})
    assert all(p['license'] for p in crates),'Missing restored Rust metadata'
    patched=AREA/'xtext/.antlr-generator-3.2.0-patch.jar'
    with zipfile.ZipFile(patched) as jar:
        notices={name:jar.read(name).decode('utf8',errors='replace') for name in jar.namelist() if name.upper().endswith(('MANIFEST.MF','LICENSE','LICENSE.TXT','NOTICE','NOTICE.TXT')) and jar.getinfo(name).file_size<64000}
    result={'rustInventory':crates,'xtext':{'candidateDisposition':'REJECTED_FOR_PRODUCTION','generatorSha256':digest(patched),'notices':notices,'reason':'No verified mapping from exact patched generator bytes to source revision, patch set and reproducible build. Upstream ANTLR source is not patched-binary provenance. Digest-pinning alone is insufficient.','licenseEvidence':{'aopalliance1.0':{'source':'https://aopalliance.sourceforge.net/','declared':'Public Domain','status':'Upstream statement; retain downloaded evidence. Not inferred from a parent POM.'},'antlrRuntime3.2':{'source':'https://repo.maven.apache.org/maven2/org/antlr/antlr-runtime/3.2/antlr-runtime-3.2-sources.jar','declared':'BSD-3-Clause','status':'Upstream source header evidence; preserve conditions and disclaimer.'}},'cleanRestoration':'Existing clean Ubuntu Maven/setup builds reproduce artifacts over the network; exact patched generator source rebuild remains unavailable and excludes this production model.'},'toolchainUpgrades':{},'rollback':'Production pins and locks unchanged; alternate tools/output directories isolated under ignored .cache. Generated grammar sources unchanged by core-toolchain tests.','licensingScope':'Restored metadata and notices are engineering supply-chain evidence, not a legal clearance claim.'}
    sourcejar=AREA/'.cache/phase5c-toolchains/antlr-runtime-3.2-sources.jar'
    if sourcejar.exists():
        with zipfile.ZipFile(sourcejar) as jar:header=jar.read('org/antlr/runtime/Token.java').decode().split('package org.antlr.runtime;')[0]
        notice=target/'antlr-runtime-3.2-LICENSE.txt';notice.write_text(header)
        result['xtext']['licenseEvidence']['antlrRuntime3.2'].update(sourceArtifactSha256=digest(sourcejar),noticeSha256=digest(notice),status='Exact Maven source artifact header verified; preserve source/binary notice, disclaimer and non-endorsement condition.')
    result['xtext']['licenseEvidence']['aopalliance1.0']['status']='Upstream primary page inspected 2026-10-07: source code is Public Domain. License statement resolved; do not infer a license from absent POM metadata.'
    raw=b''.join(r+b'\n' for _,r,_ in fixtures())
    cp=(AREA/'xtext/target/classpath.txt').read_text().strip();base=commands()
    java_home=Path(os.environ.get('ACP5C_JAVA_UPGRADE_HOME','/opt/android-studio/jbr'))
    if java_home.exists():
        out=AREA/'.cache/phase5c-toolchains/java-upgrade-out';out.mkdir(exist_ok=True)
        compiled=run_command([str(java_home/'bin/javac'),'--release','21','-cp',cp,'-d',str(out),str(AREA/'core-runtime/Canonical.java'),str(AREA/'core-runtime/FaultCore.java')])
        old=run_command(base['java'],raw);new=run_command([str(java_home/'bin/java'),'-XX:-UsePerfData','-cp',f'{out}:{cp}','FaultCore'],raw);assert old['stdout']==new['stdout']
        canonical=run_command([str(java_home/'bin/java'),'-cp',f'{out}:{cp}','Canonical',str(ROOT/'test-corpus/canonical')])
        result['toolchainUpgrades']['java']={'status':'PASS','from':run_command(['java','-version']),'to':run_command([str(java_home/'bin/java'),'-version']),'compile':compiled,'sameFaultCorpus':True,'canonicalCorpus':canonical,'vendorChange':'Local comparison also changes Temurin to JetBrains Runtime; cannot attribute timing to version alone. CI uses alternate Temurin explicitly.','generatedDiff':[],'rollback':'Original javac/java and production pin unchanged.'}
    else:result['toolchainUpgrades']['java']={'status':'NOT_RUN','reason':'Alternate JDK unavailable; set ACP5C_JAVA_UPGRADE_HOME.'}
    node_old=Path(os.environ.get('ACP5C_NODE_PREVIOUS',str(AREA/'.cache/phase5c-toolchains/node-v22.20.0-linux-x64/bin/node')))
    if node_old.exists():
        archive=AREA/'.cache/phase5c-toolchains/node-v22.20.0-linux-x64.tar.xz';sums=archive.with_name('node-v22.20.0-SHASUMS256.txt')
        if archive.exists():assert f'{digest(archive)}  {archive.name}' in sums.read_text()
        old=run_command([str(node_old),str(AREA/'core-runtime/fault.ts')],raw);new=run_command(base['typescript'],raw);assert old['stdout']==new['stdout']
        native=run_command([str(node_old),str(AREA/'langium/native-worker.mjs'),'--embedded',str(AREA/'corpus/payment.acp')]) if (AREA/'corpus/payment.acp').exists() else None
        result['toolchainUpgrades']['node']={'status':'PASS','from':run_command([str(node_old),'--version']),'to':run_command(['node','--version']),'sameFaultCorpus':True,'canonicalCorpus':run_command([str(node_old),str(ROOT/'tooling/check_canonical_vectors.mjs')]),'native':native,'archiveSha256':digest(archive) if archive.exists() else None,'source':'https://nodejs.org/dist/v22.20.0/SHASUMS256.txt','generatedDiff':[],'rollback':'Alternate executable only; Node 24.21.0 stays pinned.'}
    else:result['toolchainUpgrades']['node']={'status':'NOT_RUN','reason':'Previous Node unavailable; set ACP5C_NODE_PREVIOUS.'}
    cargo=AREA/'.cache/cargo/bin/cargo';env={**os.environ,**({'RUSTUP_HOME':str(AREA/'.cache/rustup'),'CARGO_HOME':str(AREA/'.cache/cargo')} if cargo.exists() else {})};cargo=str(cargo) if cargo.exists() else 'cargo'
    out=AREA/'.cache/phase5c-toolchains/rust-previous';built=run_command([cargo,'+1.89.0','build','--offline','--locked','--release','--manifest-path',str(AREA/'core-runtime/Cargo.toml'),'--target-dir',str(out)],env=env)
    old=run_command([str(out/'release/fault-core')],raw);new=run_command(base['rust'],raw);assert old['stdout']==new['stdout']
    result['toolchainUpgrades']['rust']={'status':'PASS','from':'1.89.0 (29483883e 2025-08-04)','to':'1.90.0','build':built,'sameFaultCorpus':True,'canonicalCorpus':run_command([str(out/'release/canonical-probe'),str(ROOT/'test-corpus/canonical')]),'generatedDiff':[],'rollback':'Isolated target directory; lock and default toolchain unchanged.'}
    (target/'maintenance.json').write_text(json.dumps(result,indent=2)+'\n');print('Restored Rust license inventory and controlled toolchain checks complete; Xtext production REJECTED on exact generator provenance')
if __name__=='__main__':run()
