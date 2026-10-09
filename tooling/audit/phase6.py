"""Evidence-driven closure audit. Outside the sealed generator bundle.

Exit 2 means a performed but BLOCKED closure audit; never converts that to green.
The ordinary admission entrypoint still runs with builds and no blocker waiver.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'tooling'), str(ROOT/'tooling/tests')]
from target_worker import PROFILE, bundle_digest, TargetWorker
from deterministic_approval import approved_snapshot, header
from compiler_contracts import Success, wire
from compiler_core import compile_pipeline
from check_task_interface import ui_context
from target_provenance import read_provenance

BASELINE = 'db5d03dcc0763a62b3150d9b485581b163e89435'
BUNDLE = '61c4647cfbe38cdbd97d03305685b3903f3ff24cfdb20d7c5b4502b478a0e06a'
TARGET = ROOT/'targets/spring-vue-postgres'


def digest(data):
    return 'sha256:'+hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')
    return {'path': path.name, 'sha256': digest(path.read_bytes())}


def command(args, cwd, log, timeout=3600, accepted=(0,)):
    start = time.monotonic()
    with log.open('wb') as stream:
        result = subprocess.run(args, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    record = {'command': args, 'exitCode': result.returncode, 'seconds': round(time.monotonic()-start, 3),
              'log': log.name, 'logDigest': digest(log.read_bytes())}
    if result.returncode not in accepted:
        raise RuntimeError('AUDIT_COMMAND_FAILED:'+log.name)
    return record


def baseline():
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():
        raise RuntimeError('CLEAN_AUDIT_CHECKOUT_REQUIRED')
    if bundle_digest()!=BUNDLE:
        raise RuntimeError('SEALED_BUNDLE_MISMATCH_STOP')
    subprocess.run(['git','merge-base','--is-ancestor',BASELINE,'HEAD'],cwd=ROOT,check=True)
    protected = ['contracts','test-corpus','targets/spring-vue-postgres/release-contract.json',
                 'targets/spring-vue-postgres/admission-contract-v5.json',
                 'docs/adr/0016-deterministic-query-lifecycle-and-rate-semantics.md']
    if subprocess.check_output(['git','diff',BASELINE,'HEAD','--',*protected],cwd=ROOT):
        raise RuntimeError('APPROVED_BASELINE_CHANGED')
    return {'mergedMainCommit':BASELINE,'auditExecutionCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'target':PROFILE['profile'],'generator':PROFILE['generator'],'bundleDigest':'sha256:'+BUNDLE,
            'targetIR':'0.2.0','admissionContract':json.loads((TARGET/'admission-contract-v5.json').read_text()),
            'approval':header(),'canonicalDigests':{d:approved_snapshot(d)['contentDigest'] for d in ('payment','case-management')},
            'environment':{'python':sys.version,'node':subprocess.check_output(['node','--version'],text=True).strip(),
                           'java':subprocess.run(['java','-version'],capture_output=True,text=True).stderr.splitlines()[0],
                           'platform':sys.platform,'hosted':os.environ.get('CI')=='true'},
            'protectedFiles':{p:digest((ROOT/p).read_bytes()) for p in protected if (ROOT/p).is_file()}}


def provenance_and_trace(output, generated):
    result = {}
    for domain in ('payment','case-management'):
        src,ctx=ui_context(domain)
        first=compile_pipeline(src,ctx); src2,ctx2=ui_context(domain);second=compile_pipeline(src2,ctx2)
        if not isinstance(first.result,Success) or not isinstance(second.result,Success):raise RuntimeError('AUDIT_COMPILATION_FAILED')
        if first.result.output_digest!=second.result.output_digest:raise RuntimeError('AUDIT_NONDETERMINISM')
        artifacts=first.result.output.artifacts
        nodes=approved_snapshot(domain)['content']['nodes'];byid={n['id']:n for n in nodes}
        inventory=[];traces=[]
        for a in artifacts:
            if not a.mappings or not a.provenance.origins:raise RuntimeError('EMPTY_HOST_ORIGINS:'+a.path)
            for origin in a.provenance.origins:
                if byid[origin.id]['revision']!=origin.revision:raise RuntimeError('STALE_HOST_REVISION')
            inventory.append(wire(a))
        # Persist exact host plan, including per-artifact mappings; sidecar sets
        # conservatively cover the model and are not the host authority.
        write(output/(domain+'-artifact-plan.json'),{'outputDigest':first.result.output_digest,'artifacts':inventory})
        for kind in ('Entity','Field','Permission','Policy','Command','Query','UseCase','Failure','RatePolicy',
                     'IdempotencyPolicy','DeliveryPolicy','Schedule','Job','DataClassification','DataLifecycle',
                     'Retention','DeletionPolicy','LegalHold','Screen','Form','InputControl','Action','PermissionBoundary'):
            n=next((n for n in nodes if n['kind']==kind),None)
            if n is None:raise RuntimeError('TRACE_FAMILY_MISSING:'+kind)
            mappings=[{'path':a.path,'sha256':digest(a.content.read()['text'].encode()),'hostMappings':wire(a.mappings)}
                      for a in artifacts if any(o.id==n['id'] for o in a.provenance.origins)]
            traces.append({'kind':kind,'id':n['id'],'revision':n['revision'],'basis':n['basis'],'origins':n['origins'],
                           'canonicalNodeDigest':digest(json.dumps(n,sort_keys=True).encode()),'artifacts':mappings,
                           'runtimeEvidence':'admission/'+domain+'-backend.log and browser-results.json',
                           'runtimeLinkQuality':'SUITE_LEVEL; per-object assertion trace NOT PROVEN'})
        app=generated/domain
        sidecar=read_provenance(app/'acp/provenance.json')
        obligations=json.loads((app/'acp/deployment-requirements.json').read_text())
        classified=[]
        for row in obligations['requirements']+obligations.get('taskInterfaceObligations',[]):
            requirement=row['requirement']
            category='MANUAL_REVIEW_REQUIRED' if requirement=='MANUAL_ACCESSIBILITY_REVIEW' else 'REQUIRED_BEFORE_PRODUCTION_DEPLOYMENT'
            classified.append(dict(row,classification=category,disposition='OUTSTANDING'))
        result[domain]={'planDigest':first.result.output_digest,'artifactCount':len(artifacts),'determinism':'PASS',
                        'targetIRDigest':digest((app/'contracts/target-ir.json').read_bytes()),
                        'taskUIModelDigest':digest((app/'acp/task-ui-model.json').read_bytes()),
                        'migrationDigests':{p.name:digest(p.read_bytes()) for p in sorted((app/'database').glob('*.sql'))},
                        'sidecarContract':sidecar['version'],'build':sidecar['build'],'obligations':classified,'traceability':traces}
    write(output/'traceability-and-provenance.json',result)
    return result


def historical_provenance(output):
    # Policy C: historical 0.1 evidence remains immutable, but its sidecar is
    # outside the production reader's supported upgrade window. No monkeypatch.
    records=[]
    for value,expected in [({'version':'0.1.0','artifacts':[]},'REJECT'),
                           ({'version':'0.1.0','artifacts':[{'origins':'malformed'}]},'REJECT'),
                           ({'version':'0.2.0','artifacts':[]},'ACCEPT'),
                           ({'version':'0.3.0','originSets':{},'artifacts':[{'originSet':'missing'}]},'REJECT')]:
        path=output/'provenance-input.json';write(path,value)
        try: read_provenance(path);actual='ACCEPT'
        except (ValueError,KeyError,TypeError):actual='REJECT'
        if actual!=expected:raise RuntimeError('HISTORICAL_PROVENANCE_POLICY')
        records.append({'input':value,'result':actual})
    return {'policy':'C','productionWindow':'0.2/0.3 sidecars only; target 0.1 is outside supported production upgrade window',
            'forensicAdapter':'retained historical tests only; not production compatibility','cases':records,
            'additionalRequirement':'Complete malformed 0.2/0.3 schema validation remains a release-review gap'}


def evolution_inventory(output):
    # Execute current negotiation for each historical snapshot version; retain
    # exact failure rather than treating semantic-history tests as deployment.
    from canonical_json import load
    from execution_fixtures import evolution,DEST
    rows=[]
    for domain in ('payment','case-management'):
        old,_=evolution(domain)
        for snapshot in (old,load(DEST/(domain+'-canonical.json')),approved_snapshot(domain)):
            try:
                response=TargetWorker().call('negotiate',{'nodes':snapshot['content']['nodes'],'canonicalVersion':snapshot['content']['schemaVersion'],
                   'required':[],'decisions':PROFILE['decisions']})
                status='ACCEPTED'
            except ValueError as error:status=str(error);response=None
            rows.append({'domain':domain,'snapshotDigest':snapshot['contentDigest'],'canonicalVersion':snapshot['content']['schemaVersion'],
                         'negotiation':status,'response':response,'deployedEvolution':'NOT_PROVEN'})
    # Synthetic review witness to inspect storage planning; not new human
    # approval and never deployed as an accepted business change.
    from change_fixtures import evolution_change
    from changes import prepare
    from compiler_contracts import Document
    from target_migrations import plan_upgrade
    from tooling.tests.test_target_migrations import FixtureAcceptedHistory
    probes=[]
    for domain in ('payment','case-management'):
        snapshot=approved_snapshot(domain)
        proposal=evolution_change(snapshot,{'sequence':0,'digest':snapshot['contentDigest'],'journalDigest':'sha256:'+'0'*64},'required-field')
        proposal.update(changeVersion='0.3.0',canonicalVersion='0.3.0')
        plan=Document.of(prepare(snapshot,proposal));bindings=Document.of({'requiredFieldBackfills':{'EVOLUTION-required-field':'audit-only backfill'}})
        migration=plan_upgrade(Document.of(snapshot),Document.of(plan.read()['candidate']),plan,bindings,FixtureAcceptedHistory(plan,bindings)).read()
        probes.append({'domain':domain,'authority':'SYNTHETIC_TEST_WITNESS_ONLY','oldSnapshot':snapshot['contentDigest'],
            'newSnapshot':plan.read()['candidate']['contentDigest'],'migration':migration,
            'productionStorageForString':'bytea','observedNewColumnType':'text' if ' text;' in migration['sql'] else 'OTHER',
            'finding':'INCOMPATIBLE_STORAGE_PLANNING_FOR_CANONICAL_0.3'})
    history=json.loads((ROOT/'test-corpus/change/evolution.json').read_text())
    return {'historicalRecordedSteps':history,'productionNegotiationProbes':rows,'requiredFieldPlanningProbes':probes,
            'result':'BLOCKED','reason':'No complete accepted-history deployment chain with authorized backfills, migration execution, regenerated UI and post-transition behavior. Semantic history is not deployed evolution.',
            'plannerFinding':"target_migrations.py selects bytea storage only for schemaVersion == 0.2.0; Canonical 0.3 falls through to text storage. Production fix would change the sealed bundle: STOP; deliberate successor corrective tranche required."}


def run(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    report={'schemaVersion':'1.0.0','auditPerformedAt':datetime.now(timezone.utc).isoformat(),
            'phase6':'IN_PROGRESS','phase7':'NOT_STARTED','recommendation':'PHASE6_CLOSURE_BLOCKED','commands':[]}
    report['baseline']=baseline();write(output/'baseline.json',report['baseline'])
    def execute(arguments,name,timeout=3600):
        r=command([sys.executable,*arguments],ROOT,output/(name+'.log'),timeout)
        report['commands'].append(r);write(output/'progress.json',report)
    try:
        execute(['tooling/audit/admission.py','--output',str(output/'admission'),'--run-builds','--full-admission'],'full-admission',3600)
        execute(['tooling/tests/task_ui_http_outcomes.py','--root',str(output/'admission')],'supplemental-browser',1800)
        execute(['-m','unittest','tooling.tests.test_target_worker_faults','tooling.tests.test_materializer_faults',
                 'tooling.tests.test_phase6_foundations','tooling.tests.test_target_migrations',
                 'tooling.tests.test_execution_v03_evolution','tooling.tests.test_deterministic_approval','-v'],'faults-ownership-history',1800)
        report['admission']=json.loads((output/'admission/task-interface-report.json').read_text())
        report['provenance']=provenance_and_trace(output,output/'admission')
        report['historicalProvenance']=historical_provenance(output)
        report['evolution']=evolution_inventory(output)
        from package_audit import packages
        report['packages']=packages(output,output/'admission')
    except Exception as error:
        report['executionError']=type(error).__name__+':'+str(error)
    finally:
        report['sealedBundleAfterAudit']='sha256:'+bundle_digest()
        if bundle_digest()!=BUNDLE:raise RuntimeError('SEALED_BUNDLE_CHANGED_STOP')
        from criteria import assess
        report['criteria']=assess(report)
        report['blockers']=[r for r in report['criteria'] if r['status']=='BLOCKED']
        report['recommendation']='PHASE6_CLOSURE_BLOCKED' if report['blockers'] else 'PHASE6_CLOSURE_RECOMMENDED'
        write(output/'phase6-final-closure.json',report)
        print(report['recommendation'],flush=True)
    return 2 if report['blockers'] else 0


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    raise SystemExit(run(p.parse_args()))
