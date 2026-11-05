"""Bounded H4 reproduction using exact retained H3 production classes and fresh owned PG."""
import argparse,hashlib,json,os,shutil,subprocess,uuid
from pathlib import Path
from datetime import datetime,timezone,timedelta
from engineering.capacity import workload
from engineering.create_reliability.fixture import adapter_source
from engineering.reliability import database
from engineering.demo import reference as demo
from engineering.reference_application import lifecycle as life
from engineering.reference_application.evolution import api
from engineering.source_intelligence.model import require,sha
from engineering.dependency_resolution.inputs import file_hash



def classpath_inventory(paths,m2,reference):
    require(reference['schema']=='acp-maven-inputs/1','H4_LOCK_SCOPE');m2=Path(m2).absolute();result={}
    for value in paths.split(':'):
        path=Path(value).absolute();require(path.is_relative_to(m2),'H4_CLASSPATH_ESCAPE')
        name=path.relative_to(m2).as_posix();require(name in reference['artifacts'] and name.endswith('.jar'),'H4_UNREGISTERED_CLASSPATH')
        row=reference['artifacts'][name];require(file_hash(path)==row['sha256'] and path.stat().st_size==row['size'],'H4_DEPENDENCY_SUBSTITUTION');result[name]=row['sha256']
    require(result,'H4_EMPTY_CLASSPATH');return result


def verify_retained(retained,expected_digest):
    retained=Path(retained);raw=(retained/'result.json').read_bytes()
    require(sha(raw)==expected_digest,'H4_RETAINED_RESULT_CHANGED');result=json.loads(raw)
    consumed_raw=(retained/'build/consumed-build.json').read_bytes()
    require(sha(consumed_raw)==result['files']['build/consumed-build.json'],'H4_CONSUMED_BUILD_CHANGED')
    consumed=json.loads(consumed_raw)
    require(result['generator']['generator']=='acp-h1-job-preview-generator/1+sha256:f982b13e43e0efd070ea1b0773da5aedcdbf2486363c6e902f27c36ba00bcb02','H4_WRONG_RETAINED_GENERATOR')
    require(result['sealed05']=='ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb' and result['scope']=='QUALIFICATION_ONLY' and result['cleanup']=='VERIFIED','H4_RETAINED_SCOPE')
    for kind,key in [('classes','backendMainClasses'),('test-classes','backendTestClasses')]:
        require(life.tree(retained/'outputs/backend/target'/kind)==consumed[key],'H4_RETAINED_CLASS_SUBSTITUTION')
    return consumed


def execute(workspace,retained,age=0,pool=None,*,expected_digest):
    w=Path(workspace).absolute();retained=Path(retained).absolute();require(not w.exists(),'H4_COLLISION');w.mkdir(mode=0o700)
    consumed=verify_retained(retained,expected_digest)
    root=w/'application';shutil.copytree(retained/'application',root)
    shutil.copytree(retained/'outputs/backend/target',root/'backend/target')
    require(life.tree(root/'backend/target/classes')==consumed['backendMainClasses'],'H4_PRODUCTION_CLASS_SUBSTITUTION')
    adapter=root/'backend/src/test/java/acp/browser/BrowserServer.java';adapter.parent.mkdir(parents=True,exist_ok=True);adapter.write_text(adapter_source())
    classpath=(root/'backend/target/browser-classpath').read_text().strip()
    runtime_inputs=classpath_inventory(classpath,retained.parent/(retained.name+'-inputs')/'m2',json.loads((life.ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json').read_bytes()))
    cp=str(root/'backend/target/classes')+':'+classpath
    with (w/'observer-compile.log').open('wb') as log:subprocess.run(['javac','-cp',cp,'-d',str(root/'backend/target/test-classes'),str(adapter)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
    require(life.tree(root/'backend/target/classes')==consumed['backendMainClasses'],'H4_OBSERVER_CHANGED_PRODUCTION')
    active=[];inventory=[];lab=None;old={k:os.environ.get(k) for k in ('ACP_DEMO_AUTH_EVENT','ACP_H2_SESSION_NAMESPACE')}
    os.environ['ACP_DEMO_AUTH_EVENT']=(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat().replace('+00:00','Z');os.environ['ACP_H2_SESSION_NAMESPACE']='h4-'+uuid.uuid4().hex+'-'
    identity={'scope':'NEW_DISPOSABLE_H4_DIAGNOSTIC_ONLY','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'retainedResultSHA256':expected_digest,'executorSHA256':{p.name:sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')},'productionClasses':consumed['backendMainClasses'],'testClasses':life.tree(root/'backend/target/test-classes'),'runtimeDependencies':runtime_inputs,'javac':subprocess.check_output(['javac','-version'],stderr=subprocess.STDOUT,text=True).strip(),'adapterSHA256':sha(adapter.read_bytes()),'authEventAgeSeconds':age,'historical500':'UNRESOLVED_UNLESS_CAUSALLY_ESTABLISHED'}
    life.save(w/'identity.json',identity)
    try:
        with database.owned_database(active,inventory) as container,demo.bind_owned_backend(active):
            try:
                lab=workload.Lab(root,w/'runtime',container);server=lab.start(pool=pool);life.save(w/'sessions.json',lab.prepare(server));before=lab.state();life.save(w/'before.json',before);history=life.history(container);life.save(w/'history.json',history)
                # Prove observer execution and unchanged native invalid-input rejection.
                if pool is not None:
                    from engineering.create_reliability.probes import create_pool
                    life.save(w/'pool-observation.json',create_pool(lab,server,pool))
                else:
                    levels=[]
                    for clients in (4,8,16):
                        for phase in ('warmup','measured'):
                            r=workload.run_level(lab,server,clients,phase);levels.append(r);life.save(w/(phase+'-'+str(clients)+'.json'),r)
                        life.save(w/('correctness-'+str(clients)+'.json'),workload.correctness(lab,server,before,levels,clients));require(life.history(container)==history,'H4_MIGRATION_CHANGED')
                require(life.history(container)==history,'H4_MIGRATION_CHANGED')
                code,_=api(server,lab.create['path'],{'idempotencyKey':'h4-invalid'});require(code==400,'H4_OBSERVER_RESPONSE_CHANGED')
                life.save(w/'result.json',{'result':'OBSERVED_PASS','historical500':'UNRESOLVED','scope':'QUALIFICATION_ONLY'})
            finally:
                with (w/'postgres.log').open('xb') as log:subprocess.run(['docker','logs',container],stdout=log,stderr=subprocess.STDOUT,timeout=10,check=True)
                if lab:lab.close()
    except Exception as error:
        life.save(w/'failure.json',{'type':type(error).__name__,'message':str(error),'result':'FAIL'});raise
    finally:
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
        life.save(w/'resources.json',inventory)
    require('H4_EXCEPTION:org.springframework.web.server.ResponseStatusException:' in (w/'runtime/demo-backend-1011.log').read_text(),'H4_OBSERVER_NOT_EXECUTED')
    require(all(x['cleanup']=='OWN_CONTAINER_AND_VOLUME_REMOVED' for x in inventory),'H4_CLEANUP')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--retained',required=True);p.add_argument('--auth-age',type=int,default=0);p.add_argument('--pool',type=int,choices=(2,4));p.add_argument('--retained-result-sha256',required=True);a=p.parse_args();execute(a.workspace,a.retained,a.auth_age,a.pool,expected_digest=a.retained_result_sha256)
