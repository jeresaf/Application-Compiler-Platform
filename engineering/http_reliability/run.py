"""Native H6/H9 builds, actual signed HTTP execution and bounded CREATE study."""
import argparse,json,os,platform,shutil,subprocess,sys,types
from pathlib import Path
from engineering.http_reliability import application,fixture,scenarios
from engineering.operations import application as parent
from engineering.identity.run import scan,safe_maven_logs
from engineering.hardening.run import observed_offline_maven
from engineering.hardening.assessment import verify_realms
from engineering.reference_application import lifecycle as life
from engineering.application_evolution.run import analyze
from engineering.demo import reference as demo
from engineering.jobs.inspection import Preview
from engineering.source_intelligence.model import sha,require
from compiler_contracts import fingerprint,wire
from filesystem_artifacts import FilesystemArtifactStore
PACKAGE=Path(__file__).parent
PUBLIC=('baseline/generator.json','baseline/artifact-plan.json','baseline/build/consumed-build.json','baseline/runtime-result.json','successor/generator.json','successor/candidate.json','successor/artifact-plan.json','successor/build/consumed-build.json','successor/inspection/baseline.json','successor/inspection/source-model.json','successor/verification.json','successor/runtime-result.json','crypto-result.json','resources.json','focused-tests.log')
def inventory():return {p.relative_to(life.ROOT).as_posix():sha(p.read_bytes()) for p in sorted(PACKAGE.rglob('*')) if p.is_file() and p.suffix in ('.py','.json')}
def export(w,record,issuers):
    from cryptography.hazmat.primitives import serialization
    deny=[]
    for issuer in issuers:deny += [t.encode() for t in issuer.tokens]+[issuer.control.encode(),issuer.tls_private]+[k.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()) for k in issuer.keys.values()]
    public=w.parent/(w.name+'-public');require(not public.exists(),'H9_EXPORT_COLLISION');public.mkdir(mode=0o700);files={}
    for name in PUBLIC:
        p=w/name;require(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(w),'H9_PUBLIC_EVIDENCE');target=public/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);files[name]=sha(p.read_bytes())
    record['files']=files;record['secretScan']=scan(public,deny);life.save(w/'result.json',record);shutil.copy2(w/'result.json',public/'result.json');scan(public,deny);return record

def qualify(workspace,*,maven_seed=None,npm_seed=None,offline=False):
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if os.environ.get('GITHUB_ACTIONS')=='true':require(platform.python_version()=='3.14.7' and 'VERSION_ID="24.04"' in Path('/etc/os-release').read_text() and os.environ.get('GITHUB_SHA')==commit,'H9_WRONG_EXECUTION_CONTEXT')
    w=Path(workspace).absolute();require(not w.exists(),'H9_COLLISION');w.mkdir(mode=0o700);pins=inventory();resources=[];issuers=[];records={};generated={}
    with (w/'focused-tests.log').open('wb') as log:
        subprocess.run([sys.executable,'-B','-c',"import unittest;s=unittest.defaultTestLoader.discover('verification/http_reliability');assert s.countTestCases()==16;r=unittest.TextTestRunner(verbosity=2).run(s);assert r.wasSuccessful() and r.testsRun==16 and not r.skipped"],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    try:
        with demo.dependencies(w,maven_seed,npm_seed,offline) as deps,observed_offline_maven(),safe_maven_logs():
            for label,module in (('baseline',parent),('successor',application)):
                folder=w/label;folder.mkdir();root=folder/'application';print('H9 native materialization/build: '+label,flush=True)
                candidate,snapshot,request,plan=module.materialize(root);store=FilesystemArtifactStore(root);store.adopt_human(life.HUMAN);human=(root/life.HUMAN).read_bytes();plan=candidate.plan(snapshot,request,store.inventory());store.apply(plan);candidate.verify_materialized(root,plan,snapshot,request);expected=life.tree(root)
                life.save(folder/'generator.json',candidate.descriptor());life.save(folder/'candidate.json',snapshot.read());life.save(folder/'artifact-plan.json',wire(plan));preview=Preview(candidate,snapshot,request,plan,candidate.audit,root)
                demo.command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],root/'frontend',folder/'npm.log');verification=analyze(preview,folder/'inspection',deps/'m2',root/'frontend/node_modules')
                logs=folder/'build';logs.mkdir();demo.build(root,logs);adapter=root/'backend/src/test/java/acp/browser/BrowserServer.java';adapter.parent.mkdir(parents=True,exist_ok=True);adapter.write_text(fixture.adapter_source())
                demo.command(['mvn','-B','-ntp','test-compile','dependency:build-classpath','-Dmdep.outputFile=target/browser-classpath'],root/'backend',logs/'fixture-compile.log')
                life.save(logs/'consumed-build.json',{'backendMainClasses':life.tree(root/'backend/target/classes'),'backendTestClasses':life.tree(root/'backend/target/test-classes'),'externalFixtureSHA256':sha(adapter.read_bytes())})
                realm=verify_realms((logs/'production-backend.log').read_text(),deps/'m2')
                print('H9 actual signed HTTP: '+label,flush=True);result=scenarios.exercise(root,folder/'runtime',resources,issuers,successor=label=='successor');life.save(folder/'runtime-result.json',result)
                records[label]={'generator':candidate.descriptor(),'canonicalDigest':snapshot.read()['contentDigest'],'artifactPlanDigest':fingerprint(plan),'sourceModelDigest':verification.model['digest'],'realm':realm,'REL02':result['REL02'],'REL01':result.get('REL01'),'studyOutcome':result.get('studyOutcome'),'httpCases':len(result['http']),'attempts':result.get('submissions',0)}
                if label=='successor':
                    from engineering.identity import scenarios as h5
                    from engineering.identity.issuer import Issuer
                    from engineering.operations.lab import OperationalLab
                    from engineering.disaster_recovery import backup as db
                    issuer=Issuer();issuers.append(issuer)
                    class Bound(OperationalLab):
                        def __init__(self,*args):super().__init__(*args);issuer.tokens.append(self.metrics_key)
                    run=types.FunctionType(h5.exercise.__code__,{**vars(h5),'Lab':Bound},'h5_on_h9')
                    with db.new_database([],resources) as container,demo.bind_owned_backend([container]):
                        issuer.tokens.append(os.environ['ACP_TEST_DATABASE_PASSWORD']);crypto=run(root,w/'crypto',container,issuer)
                    life.save(w/'crypto-result.json',crypto)
                life.detach_outputs(root,expected,folder/'outputs');candidate.verify_materialized(root,plan,snapshot,request);require((root/life.HUMAN).read_bytes()==human,'H9_HUMAN_CHANGED');life.save(folder/'verification.json',verification.evaluate());generated[label]=root
            before=generated['baseline'];after=generated['successor'];require(life.tree(before/'backend/src/main/resources/db/migration')==life.tree(after/'backend/src/main/resources/db/migration'),'H9_MIGRATION_CHANGED')
            require((before/'backend/src/main/resources/acp-failure-mapping.json').read_bytes()==(after/'backend/src/main/resources/acp-failure-mapping.json').read_bytes(),'H9_PARENT_FAILURE_MAPPING_CHANGED')
    finally:
        for issuer in issuers:issuer.close()
        life.save(w/'resources.json',resources)
    require(inventory()==pins,'H9_EXECUTOR_CHANGED');require(resources and all(r['cleanup']=='OWN_CONTAINER_AND_VOLUME_REMOVED' for r in resources),'H9_DATABASE_LEAK');require(all(not Path(i.temp.name).exists() and not i.thread.is_alive() for i in issuers),'H9_ISSUER_LEAK')
    dirty=bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip())
    record={'executionSourceKind':'WORKING_TREE_WITH_HASHED_PRODUCERS' if dirty else 'EXACT_GIT_COMMIT','schema':'acp-h9-http-reliability/1','scope':'QUALIFICATION_ONLY','sourceCommit':commit,'sourceSHA256':pins,'baseline':records['baseline'],'successor':records['successor'],'compatibilitySHA256':sha((PACKAGE/'compatibility.json').read_bytes()),'workloadSHA256':sha((PACKAGE/'workload.json').read_bytes()),'focusedTests':{'tests':16,'failures':0,'skipped':0},'cleanup':'VERIFIED','REL01':'UNRESOLVED_NOT_CAUSALLY_ATTRIBUTED','REL02':'CORRECTED_H9_ONLY','sealed05':life.bundle_digest(),'operationalSecurity':'NOT_ESTABLISHED','releaseClosure':'BLOCKED','phase12':'NOT_STARTED','environment':{'python':platform.python_version(),'osRelease':Path('/etc/os-release').read_text(),'java':subprocess.check_output(['java','-version'],stderr=subprocess.STDOUT,text=True).strip(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'run':os.environ.get('GITHUB_RUN_ID')}}
    return export(w,record,issuers)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--maven-seed');p.add_argument('--npm-seed');p.add_argument('--offline',action='store_true');a=p.parse_args();qualify(a.workspace,maven_seed=a.maven_seed,npm_seed=a.npm_seed,offline=a.offline)
