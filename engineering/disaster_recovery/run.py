"""Source-bound logical recovery qualification over the unchanged H6 generator."""
import argparse,json,os,platform,shutil,subprocess,sys
from pathlib import Path
from engineering.operations import application,fixture
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
PUBLIC=('candidate.json','artifact-plan.json','generator.json','verification.json','resources.json','h7-tests.log','h6-regressions.log','build/consumed-build.json','runtime/observations.json','runtime/backup-manifest.json','inspection/baseline.json','inspection/source-model.json')
def inventory():return {p.relative_to(life.ROOT).as_posix():sha(p.read_bytes()) for p in sorted(PACKAGE.rglob('*.py'))}
def public_paths(root):
    root=Path(root).resolve();paths=[]
    for name in PUBLIC:
        p=root/name;require(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root),'H7_PUBLIC_EVIDENCE_MISSING_OR_ESCAPE');paths.append(p)
    return paths

def qualify(workspace,*,maven_seed=None,npm_seed=None,offline=False):
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if os.environ.get('GITHUB_ACTIONS')=='true':require(platform.python_version()=='3.14.7' and 'VERSION_ID="24.04"' in Path('/etc/os-release').read_text() and os.environ.get('GITHUB_SHA')==commit,'H7_WRONG_EXECUTION_CONTEXT')
    w=Path(workspace).absolute();require(not w.exists(),'H7_COLLISION');w.mkdir(mode=0o700);root=w/'application';pins=inventory()
    with (w/'h7-tests.log').open('wb') as output:subprocess.run([sys.executable,'-B','-c',"import unittest;suite=unittest.defaultTestLoader.discover('verification/disaster_recovery');assert suite.countTestCases()==20;result=unittest.TextTestRunner(verbosity=2).run(suite);assert result.wasSuccessful() and result.testsRun==20 and not result.skipped"],stdout=output,stderr=subprocess.STDOUT,check=True,timeout=120)
    print('H7 generate unchanged H6 application and verify native provenance',flush=True)
    candidate,snapshot,request,plan=application.materialize(root);store=FilesystemArtifactStore(root);store.adopt_human(life.HUMAN);human=(root/life.HUMAN).read_bytes();plan=candidate.plan(snapshot,request,store.inventory());store.apply(plan);candidate.verify_materialized(root,plan,snapshot,request);expected=life.tree(root)
    preview=Preview(candidate,snapshot,request,plan,candidate.audit,root);life.save(w/'candidate.json',snapshot.read());life.save(w/'artifact-plan.json',wire(plan));life.save(w/'generator.json',candidate.descriptor())
    with demo.dependencies(w,maven_seed,npm_seed,offline) as deps,observed_offline_maven(),safe_maven_logs():
        print('H7 pinned build and existing Source Intelligence',flush=True);demo.command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],root/'frontend',w/'npm.log');session=analyze(preview,w/'inspection',deps/'m2',root/'frontend/node_modules');logs=w/'build';logs.mkdir();demo.build(root,logs)
        adapter=root/'backend/src/test/java/acp/browser/BrowserServer.java';adapter.parent.mkdir(parents=True,exist_ok=True);adapter.write_text(fixture.adapter_source());demo.command(['mvn','-B','-ntp','test-compile','dependency:build-classpath','-Dmdep.outputFile=target/browser-classpath'],root/'backend',logs/'fixture-compile.log')
        life.save(logs/'consumed-build.json',{'backendMainClasses':life.tree(root/'backend/target/classes'),'backendTestClasses':life.tree(root/'backend/target/test-classes'),'externalFixtureSHA256':sha(adapter.read_bytes())});realms=verify_realms((logs/'production-backend.log').read_text(),deps/'m2')
        env={**os.environ,'ACP_H6_TEST_CLASSPATH':(root/'backend/target/browser-classpath').read_text().strip(),'ACP_H6_PLAN':str(w/'artifact-plan.json')}
        with (w/'h6-regressions.log').open('wb') as output:
            for path,count in [('verification/operations',20),('verification/operations_faults',9)]:subprocess.run([sys.executable,'-B','-c',"import sys,unittest;suite=unittest.defaultTestLoader.discover(sys.argv[1]);assert suite.countTestCases()==int(sys.argv[2]);result=unittest.TextTestRunner(verbosity=2).run(suite);assert result.wasSuccessful() and result.testsRun==int(sys.argv[2]) and not result.skipped",path,str(count)],stdout=output,stderr=subprocess.STDOUT,env=env,check=True,timeout=180)
        from engineering.disaster_recovery.scenarios import exercise,REQUIRED
        issuers=[];resources=[]
        try:
            print('H7 real snapshot backup, independent restores and fresh signed authentication',flush=True);results=exercise(root,w/'runtime',resources,issuers)
        finally:
            for issuer in issuers:issuer.close()
            life.save(w/'resources.json',resources)
        require(resources and all(r['cleanup']=='OWN_CONTAINER_AND_VOLUME_REMOVED' for r in resources),'H7_DATABASE_LEAK');require(all(not Path(i.temp.name).exists() and not i.thread.is_alive() for i in issuers),'H7_ISSUER_LEAK')
        require(inventory()==pins,'H7_EXECUTOR_CHANGED');life.detach_outputs(root,expected,w/'outputs');candidate.verify_materialized(root,plan,snapshot,request);require((root/life.HUMAN).read_bytes()==human,'H7_HUMAN_CHANGED')
        verification=session.evaluate();life.save(w/'verification.json',verification)
        record={'schema':'acp-h7-logical-recovery/1','scope':'QUALIFICATION_ONLY','sourceCommit':commit,'sourceSHA256':pins,'generator':candidate.descriptor(),'canonicalDigest':snapshot.read()['contentDigest'],'artifactPlanDigest':fingerprint(plan),'sourceModelDigest':session.model['digest'],'configurationProfile':'acp-operational-lab/1','backupProfile':'PG_DUMP_CUSTOM_EXPORTED_SNAPSHOT; OWNED_NEW_TARGET_ONLY','results':results,'requiredExperiments':sorted(REQUIRED),'resources':resources,'cleanup':'VERIFIED','focusedTests':{'tests':20,'failures':0,'skipped':0},'h1PluginRealms':realms,'sealed05':life.bundle_digest(),'operationalSecurity':'NOT_ESTABLISHED','productionRecovery':'NOT_APPROVED','G19':'NOT_SATISFIED','releaseClosure':'BLOCKED','phase12':'NOT_STARTED','environment':{'python':platform.python_version(),'osRelease':Path('/etc/os-release').read_text(),'java':subprocess.check_output(['java','-version'],stderr=subprocess.STDOUT,text=True).strip(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'run':os.environ.get('GITHUB_RUN_ID')}}
        selected=public_paths(w);record['files']={p.relative_to(w).as_posix():sha(p.read_bytes()) for p in selected}
        from cryptography.hazmat.primitives import serialization
        secrets_to_deny=[]
        for issuer in issuers:
            secrets_to_deny += [s.encode() for s in issuer.tokens]+[issuer.control.encode(),issuer.tls_private]+[key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()) for key in issuer.keys.values()]
        public=w.parent/(w.name+'-public');require(not public.exists(),'H7_EXPORT_COLLISION');public.mkdir(mode=0o700)
        for p in selected:
            out=public/p.relative_to(w);out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
        record['secretScan']=scan(public,secrets_to_deny);life.save(w/'result.json',record);shutil.copy2(w/'result.json',public/'result.json');scan(public,secrets_to_deny)
        require(not any(p.suffix in ('.dump','.sql') for p in public.rglob('*')),'H7_RAW_BACKUP_EXPORT');print('H7 LOGICAL RECOVERY ENGINEERING VERIFIED; PITR NOT_RUN; G19 NOT APPROVED',flush=True);return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--maven-seed');p.add_argument('--npm-seed');p.add_argument('--offline',action='store_true');a=p.parse_args();qualify(a.workspace,maven_seed=a.maven_seed,npm_seed=a.npm_seed,offline=a.offline)
