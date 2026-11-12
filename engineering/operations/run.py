"""Real H6 qualification through the existing compiler, publisher and H5 executor."""
import argparse,json,os,platform,shutil,subprocess
from pathlib import Path
from engineering.operations import application,fixture
from engineering.identity.run import scan,safe_maven_logs,inventory as h5_inventory
from engineering.hardening.run import observed_offline_maven
from engineering.hardening.assessment import verify_realms
from engineering.reference_application import lifecycle as life
from engineering.application_evolution.run import analyze
from engineering.demo import reference as demo
from engineering.jobs.inspection import Preview
from engineering.reliability import database
from engineering.source_intelligence.model import sha,require
from compiler_contracts import fingerprint,wire
from filesystem_artifacts import FilesystemArtifactStore
PACKAGE=Path(__file__).parent

PUBLIC_EVIDENCE=('candidate.json','artifact-plan.json','generator.json','verification.json','resources.json','h6-unit-tests.log','h6-fault-tests.log','build/consumed-build.json','runtime/experiments.json','runtime/mixed-workload.json','runtime/structured-events.json','runtime/identity/security-results.json','inspection/baseline.json','inspection/source-model.json')
def public_evidence_paths(workspace):
    root=Path(workspace).resolve();result=[]
    for name in PUBLIC_EVIDENCE:
        p=root/name;require(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root),'H6_PUBLIC_EVIDENCE_MISSING_OR_ESCAPE');result.append(p)
    return result

def inventory():return {str(p.relative_to(life.ROOT)):sha(p.read_bytes()) for p in sorted(PACKAGE.rglob('*')) if p.is_file() and p.suffix in ('.py','.java')}

def qualify(workspace,*,maven_seed=None,npm_seed=None,offline=False):
    commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    if os.environ.get('GITHUB_ACTIONS')=='true':require(platform.python_version()=='3.14.7' and 'VERSION_ID="24.04"' in Path('/etc/os-release').read_text() and os.environ.get('GITHUB_SHA')==commit,'H6_WRONG_EXECUTION_CONTEXT')
    w=Path(workspace).absolute();require(not w.exists(),'H6_COLLISION');w.mkdir(mode=0o700);root=w/'application';print('H6 native generation and publication',flush=True)
    candidate,snapshot,request,plan=application.materialize(root);store=FilesystemArtifactStore(root);store.adopt_human(life.HUMAN);human=(root/life.HUMAN).read_bytes();plan=candidate.plan(snapshot,request,store.inventory());store.apply(plan);candidate.verify_materialized(root,plan,snapshot,request);expected=life.tree(root)
    preview=Preview(candidate,snapshot,request,plan,candidate.audit,root);life.save(w/'candidate.json',snapshot.read());life.save(w/'artifact-plan.json',wire(plan));life.save(w/'generator.json',candidate.descriptor())
    with demo.dependencies(w,maven_seed,npm_seed,offline) as deps,observed_offline_maven(),safe_maven_logs():
        print('H6 source analysis and pinned builds',flush=True);demo.command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],root/'frontend',w/'npm.log');session=analyze(preview,w/'inspection',deps/'m2',root/'frontend/node_modules');logs=w/'build';logs.mkdir();demo.build(root,logs)
        adapter=root/'backend/src/test/java/acp/browser/BrowserServer.java';adapter.parent.mkdir(parents=True,exist_ok=True);adapter.write_text(fixture.adapter_source());demo.command(['mvn','-B','-ntp','test-compile','dependency:build-classpath','-Dmdep.outputFile=target/browser-classpath'],root/'backend',logs/'fixture-compile.log')
        life.save(logs/'consumed-build.json',{'backendMainClasses':life.tree(root/'backend/target/classes'),'backendTestClasses':life.tree(root/'backend/target/test-classes'),'externalFixtureSHA256':sha(adapter.read_bytes())});realms=verify_realms((logs/'production-backend.log').read_text(),deps/'m2')
        env={**os.environ,'ACP_H6_TEST_CLASSPATH':(root/'backend/target/browser-classpath').read_text().strip(),'ACP_H6_PLAN':str(w/'artifact-plan.json')}
        with (w/'h6-unit-tests.log').open('wb') as output:subprocess.run([__import__('sys').executable,'-B','-c',"import unittest;suite=unittest.defaultTestLoader.discover('verification/operations');assert suite.countTestCases()==20;result=unittest.TextTestRunner(verbosity=2).run(suite);assert result.wasSuccessful() and result.testsRun==20 and not result.skipped"],stdout=output,stderr=subprocess.STDOUT,env=env,check=True,timeout=180)
        with (w/'h6-fault-tests.log').open('wb') as output:subprocess.run([__import__('sys').executable,'-B','-c',"import unittest;suite=unittest.defaultTestLoader.discover('verification/operations_faults');assert suite.countTestCases()==9;result=unittest.TextTestRunner(verbosity=2).run(suite);assert result.wasSuccessful() and result.testsRun==9 and not result.skipped"],stdout=output,stderr=subprocess.STDOUT,env=env,check=True,timeout=180)
        pins=inventory();parent_pins=h5_inventory();from engineering.identity.issuer import Issuer
        from engineering.operations.scenarios import exercise
        issuer=Issuer();active=[];resources=[]
        try:
            with database.owned_database(active,resources) as container,demo.bind_owned_backend(active):
                print('H6 actual signed-token operational failure and recovery qualification',flush=True);results=exercise(root,w/'runtime',container,issuer)
        finally:issuer.close();life.save(w/'resources.json',resources)
        require(resources and all(r['cleanup']=='OWN_CONTAINER_AND_VOLUME_REMOVED' for r in resources),'H6_DATABASE_LEAK');require(not Path(issuer.temp.name).exists() and not issuer.thread.is_alive(),'H6_ISSUER_LEAK')
        life.detach_outputs(root,expected,w/'outputs');candidate.verify_materialized(root,plan,snapshot,request);require((root/life.HUMAN).read_bytes()==human,'H6_HUMAN_CHANGED');require(inventory()==pins and h5_inventory()==parent_pins,'H6_EXECUTOR_CHANGED')
        from cryptography.hazmat.primitives import serialization
        secrets=[s.encode() for s in issuer.tokens]+[issuer.control.encode(),issuer.tls_private]+[key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()) for key in issuer.keys.values()]
        exposure=scan(w,secrets);verification=session.evaluate();life.save(w/'verification.json',verification)
        record={'schema':'acp-h6-operational-execution/1','scope':'QUALIFICATION_ONLY','engineeringObservability':'VERIFIED','focusedTests':{'configurationAndTarget':20,'faultRegressions':9,'failures':0,'skipped':0},'productionOperations':'NOT_APPROVED','sourceCommit':commit,'sourceSHA256':pins,'h5SourceSHA256':parent_pins,'generator':candidate.descriptor(),'canonicalDigest':snapshot.read()['contentDigest'],'artifactPlanDigest':fingerprint(plan),'sourceModelDigest':session.model['digest'],'configurationProfile':'acp-operational-lab/1','h1PluginRealms':realms,'results':results,'resources':resources,'cleanup':'VERIFIED','secretScan':exposure,'sealed05':life.bundle_digest(),'historicalCreate500':'UNRESOLVED_NOT_CLAIMED_FIXED','operationalSecurity':'NOT_ESTABLISHED','releaseClosure':'BLOCKED','phase12':'NOT_STARTED','productionGateClaims':'NONE; G16_G17_G18_G19_REQUIRE_INDEPENDENT_ACCEPTANCE','environment':{'python':platform.python_version(),'osRelease':Path('/etc/os-release').read_text(),'java':subprocess.check_output(['java','-version'],stderr=subprocess.STDOUT,text=True).strip(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'run':os.environ.get('GITHUB_RUN_ID')}}
        selected=public_evidence_paths(w)
        record['files']={str(p.relative_to(w)):sha(p.read_bytes()) for p in selected}
        record['privateEvidenceSHA256']={str(p.relative_to(w)):sha(p.read_bytes()) for p in sorted((w/'runtime').rglob('*')) if p.is_file() and p not in selected}
        record['verificationSHA256']=sha((w/'verification.json').read_bytes());life.save(w/'result.json',record)
        public=w.parent/(w.name+'-public');require(not public.exists(),'H6_EXPORT_COLLISION');public.mkdir(mode=0o700)
        for p in [*selected,w/'result.json']:
            rel=p.relative_to(w);out=public/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
        scan(public,secrets);print('H6 ENGINEERING OBSERVABILITY VERIFIED; PRODUCTION OPERATIONS NOT APPROVED',flush=True);return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--maven-seed');p.add_argument('--npm-seed');p.add_argument('--offline',action='store_true');a=p.parse_args();qualify(a.workspace,maven_seed=a.maven_seed,npm_seed=a.npm_seed,offline=a.offline)
