"""H2: existing R8 evolution plus real H1 application contention in a restored lab."""
import argparse,json,os,shutil,subprocess,types,time,platform,uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from engineering.application_evolution import run as evolution
from engineering.application_evolution import plan as migration
from engineering.hardening.application import HardeningApplication
from engineering.hardening.target import HardeningTarget
from engineering.hardening.run import observed_offline_maven
from engineering.hardening.assessment import verify_realms
from engineering.jobs.inspection import Preview
from engineering.source_intelligence.model import require,sha,encode
from engineering.reference_application import lifecycle as life
from engineering.reference_application.evolution import DisposableSQL,SCHEMA
from engineering.demo import reference as demo
from engineering.reliability import fixture,database,concurrency
from compiler_contracts import fingerprint,wire
from compiler_contracts import Owner
from filesystem_artifacts import FilesystemArtifactStore,StoreConflict

ROOT=life.ROOT

# Exact already-qualified H1 POM, not a general framework-upgrade permission.
H1_POM_SHA256='0c00c13ef546753e606d20e9891b7ecb3b4aa7f3cb464a130b7ca37dc2d63cc3'


class H2ArtifactStore(FilesystemArtifactStore):
    def apply(self,plan):
        updates=[a for a in plan.artifacts if a.owner==Owner.FRAMEWORK and a.intent=='UPDATE']
        if not updates:return super().apply(plan)
        require(len(updates)==1 and updates[0].path=='backend/pom.xml','H2_UNREGISTERED_FRAMEWORK_UPGRADE')
        from engineering.hardening.target import harden_pom
        text=updates[0].content.read()['text']
        require(sha(text.encode())==H1_POM_SHA256 and text==harden_pom((self.root/'backend/pom.xml').read_text()),'H2_FRAMEWORK_CONTENT_BINDING')
        before=life.tree(self.root)
        try:super().apply(plan)
        except StoreConflict as error:
            require(str(error)=='FRAMEWORK_UPGRADE_REQUIRED','H2_WRONG_PUBLICATION_REJECTION')
        else:raise AssertionError('H2_FRAMEWORK_GATE_BYPASSED')
        require(life.tree(self.root)==before,'H2_REJECTED_PUBLICATION_CHANGED_SOURCE')
        # The native publisher still validates ownership, CAS and every artifact.
        return super().apply(plan,framework_upgrades=('backend/pom.xml',))


class RecordingApplication(HardeningApplication):
    def plan(self,*args,**kwargs):
        self.last_plan=super().plan(*args,**kwargs)
        return self.last_plan


def restored_session(*args,**kwargs):
    """A new test authentication event; never refresh a captured session in place."""
    session=evolution.session(*args,**kwargs)
    session.env.update(ACP_DEMO_AUTH_EVENT=datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                       ACP_H2_SESSION_NAMESPACE='h2-restore-'+uuid.uuid4().hex+'-')
    return session


def qualify(workspace,*,maven_seed=None,npm_seed=None,browser_seed=None,offline=False):
    if os.environ.get('GITHUB_ACTIONS')=='true':
        release=Path('/etc/os-release').read_text()
        require(platform.system()=='Linux' and 'ID=ubuntu\n' in release and 'VERSION_ID="24.04"' in release and platform.python_version()=='3.14.7','H2_WRONG_HOSTED_RUNNER')
        require(os.environ.get('GITHUB_SHA')==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'H2_WRONG_HOSTED_SOURCE')
    w=Path(workspace).absolute();require(not w.exists(),'H2_WORKSPACE_COLLISION');w.mkdir(mode=0o700)
    source={p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}
    for name in ('engineering/application_evolution/plan.py','engineering/source_intelligence/model.py'):source[name]=sha((ROOT/name).read_bytes())
    inventory=[];applications=[];migration_faults=[]
    def application():
        value=RecordingApplication();applications.append(value);return value
    @contextmanager
    def owned(active):
        try:
            with database.owned_database(active,inventory) as container:
                life.save(w/'execution-resources.json',inventory)
                yield container
        finally:life.save(w/'execution-resources.json',inventory)
    host=types.SimpleNamespace(**{**vars(demo),'owned_database':owned})
    def preview(*args):return migration.preview(*args,successor=HardeningTarget())
    def preconditions(plan,observed,expected,sql):
        for key,bad in (('source','wrong-source'),('populationDigest','stale-population'),('schema','public')):
            altered={**observed,key:bad}
            try:migration.preconditions(plan,altered,expected,sql)
            except ValueError as error:migration_faults.append({'case':key,'result':'PASS','error':str(error)})
            else:raise AssertionError('H2_INVALID_MIGRATION_PREFLIGHT_ACCEPTED')
        return migration.preconditions(plan,observed,expected,sql)
    def faults(db,container,sql,before,logs):
        result=evolution.faults(db,container,sql,before,logs)
        original=evolution.identity(db);started=db.data('SELECT to_json(pg_postmaster_start_time())');begin=time.monotonic()
        subprocess.run(['docker','restart',container],check=True,capture_output=True,timeout=40);database.ready(container)
        binding=database.renew_connection(container)
        require(evolution.identity(db)==original and demo.database_state(container,SCHEMA)==before,'H2_MIGRATION_RESTART_LOSS')
        require(db.data('SELECT to_json(pg_postmaster_start_time())')!=started,'H2_MIGRATION_DATABASE_NOT_RESTARTED')
        result['databaseRestartBetweenMigrationStages']={'result':'PASS','seconds':time.monotonic()-begin,'identity':original,'populationExact':True,'ownedBinding':binding}
        return result
    function=types.FunctionType(evolution.qualify.__code__,{**vars(evolution),
        'jobs':types.SimpleNamespace(JobApplication=application),'demo':host,'preview':preview,'FilesystemArtifactStore':H2ArtifactStore,
        'adapter7':fixture.adapter_source,'preconditions':preconditions,'faults':faults,
        'offline_maven':observed_offline_maven,
        'restore':types.FunctionType(evolution.restore.__code__,{**vars(evolution),'demo':host,'session':restored_session},'h2_restore')},'h2_evolution')
    function.__kwdefaults__=evolution.qualify.__kwdefaults__
    core=w/'evolution';prior=function(core,maven_seed=maven_seed,npm_seed=npm_seed,browser_seed=browser_seed,offline=offline)
    require(len(applications)==1,'H2_APPLICATION_FACTORY');candidate=applications[0];request=candidate.context.request
    snapshot=candidate.context.snapshots.read_exact(request.application,request.snapshot_digest);plan=candidate.last_plan
    realm=verify_realms((core/'r7-build/production-backend.log').read_text(),core.parent/(core.name+'-inputs')/'m2')

    # A new copy and a new owned DB. No retained H1/R1 population is addressed.
    folder=w/'concurrency';folder.mkdir();root=folder/'application';shutil.copytree(core/'application',root)
    candidate.verify_materialized(root,plan,snapshot,request);expected=life.tree(root)
    preview_host=Preview(candidate,snapshot,request,plan,candidate.audit,root)
    for name in ('backend/target','frontend/node_modules','frontend/dist'):
        shutil.copytree(core/'r7-outputs'/name,root/name,symlinks=True)
    consumed=json.loads((core/'r7-build/consumed-build.json').read_bytes())
    require(life.tree(root/'backend/target/classes')==consumed['backendMainClasses'] and life.tree(root/'backend/target/test-classes')==consumed['backendTestClasses'],'H2_CONSUMED_BINARY_SUBSTITUTION')
    inspect=folder/'inspection';session=evolution.analyze(preview_host,inspect,core.parent/(core.name+'-inputs')/'m2',root/'frontend/node_modules')
    capture=core/'r7-database';pins={n:sha((capture/n).read_bytes()) for n in migration.CAPTURE_FILES};migration.verify_capture(capture,pins)
    active=[];lab=None;auth_before=os.environ.get('ACP_DEMO_AUTH_EVENT');namespace_before=os.environ.get('ACP_H2_SESSION_NAMESPACE')
    try:
        os.environ['ACP_DEMO_AUTH_EVENT']=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        os.environ['ACP_H2_SESSION_NAMESPACE']='h2-'+uuid.uuid4().hex+'-'
        with owned(active) as container,demo.bind_owned_backend(active):
            restored=subprocess.run(['docker','exec','-i',container,'psql','-X','-U','acp_runtime','-d','acp_runtime','-v','ON_ERROR_STOP=1'],input=(capture/'database.sql').read_bytes(),capture_output=True,timeout=60)
            (folder/'restore.stdout').write_bytes(restored.stdout);(folder/'restore.stderr').write_bytes(restored.stderr);require(restored.returncode==0,'H2_RESTORE_FAILED')
            require(demo.database_state(container,SCHEMA)==json.loads((capture/'database-state.json').read_bytes()),'H2_RESTORE_POPULATION_MISMATCH')
            lab=concurrency.Lab(root,folder/'runtime',container)
            running,resources=concurrency.run(lab);concurrency.workers(lab,running,resources[0]);lab.close()
            life.freeze(container,folder/'database')
    finally:
        if lab:lab.close()
        if auth_before is None:os.environ.pop('ACP_DEMO_AUTH_EVENT',None)
        else:os.environ['ACP_DEMO_AUTH_EVENT']=auth_before
        if namespace_before is None:os.environ.pop('ACP_H2_SESSION_NAMESPACE',None)
        else:os.environ['ACP_H2_SESSION_NAMESPACE']=namespace_before
        life.save(w/'execution-resources.json',inventory)
    require(all(i['cleanup']=='OWN_CONTAINER_AND_VOLUME_REMOVED' for i in inventory),'H2_UNVERIFIED_DATABASE_CLEANUP')
    life.detach_outputs(root,expected,folder/'outputs');candidate.verify_materialized(root,plan,snapshot,request)
    require(all(sha((ROOT/p).read_bytes())==h for p,h in source.items()),'H2_SOURCE_CHANGED')
    from engineering.reliability.verification import Execution,SCENARIOS
    require({r['scenario'] for r in lab.rows}==SCENARIOS,'H2_INCOMPLETE_SCENARIOS')
    files=[folder/'runtime/observations.json',w/'execution-resources.json',folder/'database/database-state.json',folder/'database/migration-history.json',
           *[core/name for name in ('result.json','evolution-plan.json','capture-manifest.json','r6-database/migration-history.json','r7-database/migration-history.json','restore/result.json','r6-candidate.json','r7-candidate.json','r7-plan.json')]]
    record={'scope':'QUALIFICATION_ONLY','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'sourceSHA256':source,'generator':candidate.descriptor(),'canonicalDigest':snapshot.read()['contentDigest'],
        'artifactPlanDigest':fingerprint(plan),'sourceModelDigest':session.model['digest'],'database':lab.identity,
        'runtimeConfiguration':{'identity':'TRUSTED_JWT_COMPONENT_ONLY','authEvent':lab.sessions[0].env['ACP_DEMO_AUTH_EVENT'],'workerPrincipal':'service:reference-integrity','tenants':['tenant-one','tenant-two']},
        'environment':{'system':platform.system(),'python':platform.python_version(),'osRelease':Path('/etc/os-release').read_text(),'hosted':os.environ.get('GITHUB_ACTIONS')=='true','runId':os.environ.get('GITHUB_RUN_ID'),'attempt':os.environ.get('GITHUB_RUN_ATTEMPT')},
        'captureSHA256':pins,'migrationPreflightRejections':migration_faults,'evolution':prior,
        'h1PluginRealms':realm,'scenarioResults':lab.rows,'resources':inventory,
        'files':{p.relative_to(w).as_posix():sha(p.read_bytes()) for p in files},'cleanup':'VERIFIED',
        'semanticApproval':'NOT_APPROVED','releaseClosure':'BLOCKED','operationalSecurity':'NOT_ESTABLISHED'}
    life.save(w/'h2-execution.json',record);result=session.evaluate(execution=Execution(w/'h2-execution.json'))
    require(all(r['result']=='PASS' for r in result['results'] if r['kind']=='ARTIFACT_VERIFICATION'),'H2_SOURCE_VERIFICATION_FAILED')
    life.save(w/'verification.json',result);life.save(w/'result.json',record);return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True,type=Path)
    for name in ('maven-seed','npm-seed','browser-seed'):p.add_argument('--'+name,type=Path)
    p.add_argument('--offline',action='store_true');a=p.parse_args()
    try:qualify(a.workspace,maven_seed=a.maven_seed,npm_seed=a.npm_seed,browser_seed=a.browser_seed,offline=a.offline)
    except Exception as error:
        if a.workspace.exists():life.save(a.workspace/'failure.json',{'result':'FAIL','scope':'QUALIFICATION_ONLY','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'error':type(error).__name__+':'+str(error),'releaseClosure':'BLOCKED'})
        raise


if __name__=='__main__':main()
