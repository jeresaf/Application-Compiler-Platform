"""Generate, build and qualify the additive H5 cryptographic identity profile."""
import argparse,json,os,platform,shutil,subprocess,tempfile
from contextlib import contextmanager
from pathlib import Path
from engineering.identity import application,fixture
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

def inventory():return {str(p.relative_to(life.ROOT)):sha(p.read_bytes()) for p in sorted(PACKAGE.rglob('*')) if p.is_file() and p.suffix in ('.py','.java')}


def scan(root,secrets):
    count=0
    for p in Path(root).rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ('node_modules','__pycache__')):continue
        raw=p.read_bytes();require(not any(value and value in raw for value in secrets),'H5_CREDENTIAL_EXPORT_BLOCKED');count+=1
    return {'filesScanned':count,'credentialMatches':0,'signingKeysExported':False,'bearerTokensExported':False}


@contextmanager
def safe_maven_logs():
    """Retain plugin-realm diagnostics without Maven's environment dump.

    Raw command output stays in an owned private temporary directory, never in
    the evidence tree. Redacted output survives command failure; exit status is
    unchanged. The independent actual-credential scan still fails closed.
    """
    original=demo.command
    def command(args,cwd,log):
        if args[0]!='mvn':return original(args,cwd,log)
        with tempfile.TemporaryDirectory(prefix='acp-h5-maven-private-') as directory:
            private=Path(directory)/'raw.log'
            try:return original(args,cwd,private)
            finally:
                if private.exists():
                    with private.open('rb') as source,Path(log).open('wb') as target:
                        for line in source:
                            target.write(b'[DEBUG] Environment property redacted\n' if b'[DEBUG] env.' in line else line)
    demo.command=command
    try:yield
    finally:demo.command=original


def qualify(workspace,*,maven_seed=None,npm_seed=None,offline=False):
    if os.environ.get('GITHUB_ACTIONS')=='true':require(platform.python_version()=='3.14.7' and 'VERSION_ID="24.04"' in Path('/etc/os-release').read_text(),'H5_WRONG_RUNNER')
    w=Path(workspace).absolute();require(not w.exists(),'H5_COLLISION');w.mkdir(mode=0o700);root=w/'application'
    print('H5 generation',flush=True);candidate,snapshot,request,plan=application.materialize(root)
    store=FilesystemArtifactStore(root);store.adopt_human(life.HUMAN);human=(root/life.HUMAN).read_bytes();plan=candidate.plan(snapshot,request,store.inventory());store.apply(plan);candidate.verify_materialized(root,plan,snapshot,request);expected=life.tree(root)
    preview=Preview(candidate,snapshot,request,plan,candidate.audit,root);life.save(w/'candidate.json',snapshot.read());life.save(w/'artifact-plan.json',wire(plan));life.save(w/'generator.json',candidate.descriptor())
    with demo.dependencies(w,maven_seed,npm_seed,offline) as deps,observed_offline_maven(),safe_maven_logs():
        print('H5 source analysis and builds',flush=True);demo.command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],root/'frontend',w/'npm.log');session=analyze(preview,w/'inspection',deps/'m2',root/'frontend/node_modules')
        logs=w/'build';logs.mkdir();demo.build(root,logs);adapter=root/'backend/src/test/java/acp/browser/BrowserServer.java';adapter.parent.mkdir(parents=True,exist_ok=True);adapter.write_text(fixture.adapter_source())
        demo.command(['mvn','-B','-ntp','test-compile','dependency:build-classpath','-Dmdep.outputFile=target/browser-classpath'],root/'backend',logs/'adapter-compile.log')
        life.save(logs/'consumed-build.json',{'backendMainClasses':life.tree(root/'backend/target/classes'),'backendTestClasses':life.tree(root/'backend/target/test-classes'),'adapterSHA256':sha(adapter.read_bytes())})
        realms=verify_realms((logs/'production-backend.log').read_text(),deps/'m2')
        # Runtime source is snapshotted before loading/executing the test executor.
        pins=inventory();from engineering.identity.scenarios import exercise
        from engineering.identity.issuer import Issuer
        issuer=Issuer();active=[];resources=[]
        try:
            require(not Path(issuer.temp.name).is_relative_to(w),'H5_PRIVATE_CUSTODY_SCOPE')
            with database.owned_database(active,resources) as container,demo.bind_owned_backend(active):
                print('H5 real signed-token qualification',flush=True)
                result=exercise(root,w/'runtime',container,issuer)
                life.save(w/'database-state.json',demo.database_state(container,'acp_browser_case_management'));life.save(w/'migration-history.json',life.history(container))
        finally:
            issuer.close();life.save(w/'resources.json',resources)
        require(resources and all(r['cleanup']=='OWN_CONTAINER_AND_VOLUME_REMOVED' for r in resources),'H5_RESOURCE_LEAK');require(not Path(issuer.temp.name).exists() and not issuer.thread.is_alive(),'H5_ISSUER_LEAK')
        life.detach_outputs(root,expected,w/'outputs');candidate.verify_materialized(root,plan,snapshot,request);require((root/life.HUMAN).read_bytes()==human,'H5_HUMAN_CHANGED');require(inventory()==pins,'H5_EXECUTOR_CHANGED')
        secrets=[t.encode() for t in issuer.tokens]+[issuer.control.encode(),issuer.tls_private]
        from cryptography.hazmat.primitives import serialization
        secrets += [k.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()) for k in issuer.keys.values()]
        exposure=scan(w,secrets)
        record={'schema':'acp-h5-identity-execution/1','scope':'QUALIFICATION_ONLY','authenticationProfile':'CRYPTOGRAPHIC_JWT_VALIDATION_TEST','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'sourceSHA256':pins,'generator':candidate.descriptor(),'canonicalDigest':snapshot.read()['contentDigest'],'artifactPlanDigest':fingerprint(plan),'sourceModelDigest':session.model['digest'],'h1PluginRealms':realms,'results':result,'resources':resources,'cleanup':'VERIFIED','secretScan':exposure,'sealed05':life.bundle_digest(),'historicalCreate500':'UNRESOLVED_NOT_CLAIMED_FIXED','operationalSecurity':'NOT_ESTABLISHED','releaseClosure':'BLOCKED','phase12':'NOT_STARTED','environment':{'python':platform.python_version(),'system':platform.system(),'osRelease':Path('/etc/os-release').read_text(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'java':subprocess.check_output(['java','-version'],stderr=subprocess.STDOUT,text=True).strip(),'run':os.environ.get('GITHUB_RUN_ID')}}
        verification=session.evaluate();life.save(w/'verification.json',verification)
        record['files']={str(p.relative_to(w)):sha(p.read_bytes()) for p in sorted((w/'runtime').rglob('*')) if p.is_file()};record['verificationSHA256']=sha((w/'verification.json').read_bytes());life.save(w/'result.json',record)
        public=w.parent/(w.name+'-public');require(not public.exists(),'H5_EXPORT_COLLISION');public.mkdir(mode=0o700)
        for p in w.rglob('*'):
            rel=p.relative_to(w)
            if p.is_file() and not any(x in rel.parts for x in ('node_modules','target','__pycache__')):
                dest=public/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
        scan(public,secrets);print('H5 QUALIFICATION_ONLY completed',flush=True);return record


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--maven-seed');p.add_argument('--npm-seed');p.add_argument('--offline',action='store_true');a=p.parse_args();qualify(a.workspace,maven_seed=a.maven_seed,npm_seed=a.npm_seed,offline=a.offline)
