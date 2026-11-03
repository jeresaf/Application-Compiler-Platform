"""H3 bounded application capacity, using the existing H1 generator and H2 lab."""
import argparse,json,os,platform,shutil,subprocess,uuid
from pathlib import Path
from datetime import datetime,timezone
from engineering.reference_application import lifecycle as life
from engineering.application_evolution.run import analyze,build
from engineering.hardening import application
from engineering.hardening.run import observed_offline_maven
from engineering.hardening.assessment import verify_realms
from engineering.jobs.inspection import Preview
from engineering.demo import reference as demo
from engineering.reliability import database
from engineering.capacity import fixture,workload,scenarios
from engineering.source_intelligence.model import sha,require
from compiler_contracts import fingerprint,wire
from filesystem_artifacts import FilesystemArtifactStore

ROOT=life.ROOT
PACKAGE=Path(__file__).parent


def source_inventory():
    return {p.relative_to(ROOT).as_posix():sha(p.read_bytes()) for p in sorted(PACKAGE.iterdir()) if p.is_file() and p.suffix in ('.py','.json')}


def qualify(workspace,*,maven_seed=None,npm_seed=None,offline=False):
    if os.environ.get('GITHUB_ACTIONS')=='true':
        release=Path('/etc/os-release').read_text()
        require(platform.python_version()=='3.14.7' and platform.system()=='Linux' and 'ID=ubuntu\n' in release and 'VERSION_ID="24.04"' in release,'H3_WRONG_RUNNER')
        require(os.environ.get('GITHUB_SHA')==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'H3_WRONG_SOURCE')
    w=Path(workspace).absolute();require(not w.exists(),'H3_WORKSPACE_COLLISION');w.mkdir(mode=0o700)
    life.save(w/'execution-owner.json',{'scope':'NEW_DISPOSABLE_H3_TEST','repository':str(ROOT),'evidenceCustody':'SEPARATE_DESTINATION_APPROVAL_REQUIRED; RETAIN_BEFORE_REMOVAL'})
    sources=source_inventory();root=w/'application';candidate,snapshot,request,plan=application.materialize(root)
    store=FilesystemArtifactStore(root);store.adopt_human(life.HUMAN);human=(root/life.HUMAN).read_bytes();plan=candidate.plan(snapshot,request,store.inventory());store.apply(plan);candidate.verify_materialized(root,plan,snapshot,request);expected=life.tree(root);preview=Preview(candidate,snapshot,request,plan,candidate.audit,root)
    life.save(w/'candidate.json',snapshot.read());life.save(w/'artifact-plan.json',wire(plan))
    active=[];inventory=[];lab=None;auth_before=os.environ.get('ACP_H2_SESSION_NAMESPACE')
    with demo.dependencies(w,maven_seed,npm_seed,offline) as deps,observed_offline_maven():
        demo.command(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],root/'frontend',w/'npm.log')
        session=analyze(preview,w/'inspection',deps/'m2',root/'frontend/node_modules')
        build(root,w/'build',fixture.adapter_source)
        consumed=json.loads((w/'build/consumed-build.json').read_bytes())
        require(life.tree(root/'backend/target/classes')==consumed['backendMainClasses'] and life.tree(root/'backend/target/test-classes')==consumed['backendTestClasses'],'H3_WRONG_CONSUMED_BUILD')
        realms=verify_realms((w/'build/production-backend.log').read_text(),deps/'m2')
        try:
            os.environ['ACP_H2_SESSION_NAMESPACE']='h3-'+uuid.uuid4().hex+'-'
            with database.owned_database(active,inventory) as container,demo.bind_owned_backend(active):
                try:
                    life.save(w/'execution-resources.json',inventory);lab=workload.Lab(root,w/'runtime',container);server=lab.start()
                    initialized=lab.prepare(server);before=lab.state();life.save(w/'runtime/before-workloads.json',before);history=life.history(container);life.save(w/'runtime/initial-history.json',history)
                    levels=[];warmups=[];invariants=[];all_levels=[]
                    for clients in workload.PROFILE['clients']:
                        warm=workload.run_level(lab,server,clients,'warmup');warmups.append(warm);all_levels.append(warm);life.save(w/f'runtime/warmup-{clients}.json',warm)
                        measured=workload.run_level(lab,server,clients,'measured');levels.append(measured);all_levels.append(measured);life.save(w/f'runtime/normal-{clients}.json',measured)
                        invariants.append(workload.correctness(lab,server,before,all_levels,clients));require(life.history(container)==history,'H3_WORKLOAD_MIGRATION_CHANGED')
                    life.save(w/'runtime/query-plans.json',scenarios.query_plans(lab))
                    life.save(w/'runtime/workload-identities.json',{'created':lab.created,'reported':lab.reported,'uploads':[{'tenant':k[0],'resource':k[1],'key':k[2],'metadata':v} for k,v in lab.uploads.items()]})
                    cases=[];server,workers=scenarios.workers(lab,server);cases.append(workers)
                    cases.append(scenarios.admitted_create(lab,server));cases.append(scenarios.invalid_inputs(lab,server))
                    server,pressure=scenarios.pool_pressure(lab,server);cases.append(pressure)
                    cases.append(scenarios.client_timeout(lab,server))
                    for kill in (False,True):server,recovery=scenarios.interrupted_uploads(lab,server,kill=kill);cases.append(recovery)
                    cases.append(scenarios.scope_limit(lab,server));lab.close();life.save(w/'runtime/scenarios.json',cases)
                    require(life.history(container)==history,'H3_RECOVERY_MIGRATION_CHANGED');life.freeze(container,w/'database')
                except Exception:
                    # Retain the real server's diagnostics before the owned DB
                    # context removes it. This never changes failure policy.
                    try:
                        with (w/'postgres-failure.log').open('xb') as log:
                            subprocess.run(['docker','logs',container],stdout=log,stderr=subprocess.STDOUT,timeout=10,check=False)
                    except Exception as capture:
                        life.save(w/'failure-capture.json',{'error':type(capture).__name__})
                    raise
        finally:
            if lab:lab.close()
            if auth_before is None:os.environ.pop('ACP_H2_SESSION_NAMESPACE',None)
            else:os.environ['ACP_H2_SESSION_NAMESPACE']=auth_before
            life.save(w/'execution-resources.json',inventory)
        require(inventory and all(r['cleanup']=='OWN_CONTAINER_AND_VOLUME_REMOVED' for r in inventory),'H3_UNVERIFIED_CLEANUP')
        life.detach_outputs(root,expected,w/'outputs');candidate.verify_materialized(root,plan,snapshot,request);require((root/life.HUMAN).read_bytes()==human,'H3_HUMAN_SOURCE_CHANGED')
        require(source_inventory()==sources,'H3_SOURCE_CHANGED_DURING_RUN')
        from engineering.capacity.verification import Execution,validate
        evidence=[w/'execution-resources.json',w/'runtime/initial-history.json',w/'runtime/before-workloads.json',w/'runtime/workload-identities.json',w/'runtime/scenarios.json',w/'runtime/observations.json',w/'database/database-state.json',w/'database/database-identity.json',w/'database/migration-history.json',w/'runtime/query-plans.json',w/'build/consumed-build.json']
        evidence.extend(w/'runtime'/f'{kind}-{n}.json' for n in workload.PROFILE['clients'] for kind in ('normal','warmup','after-level'))
        record={'schema':'acp-h3-execution/1','scope':'QUALIFICATION_ONLY','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'sourceSHA256':sources,
                'generator':candidate.descriptor(),'canonicalDigest':snapshot.read()['contentDigest'],'artifactPlanDigest':fingerprint(plan),'sourceModelDigest':session.model['digest'],
                'workload':workload.PROFILE,'workloadSHA256':sha((PACKAGE/'profile.json').read_bytes()),'database':lab.identity,'sessions':initialized,
                'environment':{'python':platform.python_version(),'system':platform.system(),'osRelease':Path('/etc/os-release').read_text(),'kernel':platform.release(),'cpuCount':os.cpu_count(),'loadAverage':list(os.getloadavg()),'meminfo':Path('/proc/meminfo').read_text(),'cpuinfo':Path('/proc/cpuinfo').read_text(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'java':subprocess.check_output(['java','-version'],stderr=subprocess.STDOUT,text=True).strip(),'maven':subprocess.check_output(['mvn','--version'],text=True).strip(),'hosted':os.environ.get('GITHUB_ACTIONS')=='true','run':os.environ.get('GITHUB_RUN_ID'),'attempt':os.environ.get('GITHUB_RUN_ATTEMPT')},
                'runtimeConfiguration':{'authentication':'EXTERNAL_TRUSTED_JWT_COMPONENT; NOT_ISSUER_QUALIFICATION','heapMiB':512,'directMemoryMiB':128,'activeProcessorCountHint':2,'workersPerJVM':2,'applicationPool':workload.PROFILE['applicationPoolConnections'],'pressurePool':2,'clientTimeoutSeconds':10,'serverMCPTimeoutUnchanged':30},
                'levels':levels,'warmups':warmups,'invariants':invariants,'scenarios':cases,'h2Fencing':lab.rows,'resources':inventory,'h1PluginRealms':realms,
                'files':{p.relative_to(w).as_posix():sha(p.read_bytes()) for p in evidence},'cleanup':'VERIFIED','ownership':'NATIVE_PLAN_VERIFIED; HUMAN_BYTES_UNCHANGED','sealed05':life.bundle_digest(),
                'runtimeCorrections':'H3_PROFILE_POOL_34_AFTER_RETAINED_DEFAULT_10_STARVATION; ORIGINAL_H1_GENERATOR_UNCHANGED','capacityDisposition':'ENGINEERING_CAPACITY_OBSERVED','productionCapacity':'NOT_APPROVED','G22':'NOT_SATISFIED','semanticApproval':'NOT_APPROVED','releaseClosure':'BLOCKED','operationalSecurity':'NOT_ESTABLISHED',
                'limits':['20_ELIGIBLE_DOCUMENTS_PER_TENANT_FOR_SCHEDULING','2_EXECUTING_LOOPS_PER_JVM','NO_APPROVED_PENDING_OCCURRENCE_BOUND','GENERIC_500_ON_POOL_EXHAUSTION','CLIENT_TIMEOUT_DOES_NOT_CANCEL_COMMITTED_EFFECTS','NO_PRODUCTION_SLO_OR_CAPACITY_APPROVAL']}
        validate(record);life.save(w/'capacity-execution.json',record);verified=session.evaluate(execution=Execution(w/'capacity-execution.json'));require(all(r['result']=='PASS' for r in verified['results'] if r['kind']=='ARTIFACT_VERIFICATION'),'H3_ARTIFACT_VERIFICATION_FAILED');life.save(w/'verification.json',verified);life.save(w/'result.json',record)
        return record


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--workspace',required=True,type=Path);parser.add_argument('--maven-seed',type=Path);parser.add_argument('--npm-seed',type=Path);parser.add_argument('--offline',action='store_true');args=parser.parse_args()
    try:qualify(args.workspace,maven_seed=args.maven_seed,npm_seed=args.npm_seed,offline=args.offline)
    except Exception as error:
        if args.workspace.exists():life.save(args.workspace/'failure.json',{'result':'FAIL','scope':'QUALIFICATION_ONLY','error':type(error).__name__+':'+str(error),'releaseClosure':'BLOCKED'})
        raise


if __name__=='__main__':main()
