"""Canonical 0.3 invocation components, separate from full target admission."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parent))
from deterministic_approval import approved_snapshot,header
from target_worker import ROOT,PROFILE,TargetWorker,TargetWorkerError
from invocation_reference_tests import source,variants,http_source
from delivery_job_reference_tests import source as delivery_source
sys.path.insert(0,str(ROOT/'worker'))
from generation import plan
from model import lower


def run(output,builds):
    output.mkdir(parents=True,exist_ok=False)
    templates={p.relative_to(ROOT/'templates').as_posix():p.read_text() for p in (ROOT/'templates').rglob('*') if p.is_file()}
    report={'mode':'UNNEGOTIATED_DELIVERY_JOB_COMPONENTS_ONLY','phase6':'IN_PROGRESS','phase7':'NOT_STARTED','approval':header(),
        'environment':{'os':platform.platform(),'python':platform.python_version(),'node':subprocess.check_output(['node','--version'],text=True).strip(),
            'java':subprocess.run(['java','-version'],capture_output=True,text=True).stderr.splitlines()[0]},'domains':{}}
    failed=False
    for domain in ('payment','case-management'):
        snapshot=approved_snapshot(domain);nodes=snapshot['content']['nodes']
        try:
            TargetWorker().call('negotiate',{'nodes':nodes,'canonicalVersion':'0.3.0','required':['semantic.execution-dataflow/0.3','acp.deterministic-execution.0.4'],'decisions':PROFILE['decisions']})
            admission='ACCEPTED'
        except TargetWorkerError as e:admission=str(e)
        artifacts=plan(lower(nodes,PROFILE,'0.3.0'),templates,PROFILE,build={'bundleDigest':'sha256:'+__import__('target_worker').bundle_digest(),'canonicalSnapshotDigest':snapshot['contentDigest'],'features':['acp.deterministic-execution.0.4']})
        directory=output/domain
        for a in artifacts:
            p=directory/a['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(a['text'])
        p=directory/'backend/src/test/java/acp/generated/InvocationCoreTest.java';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source(domain))
        p=directory/'backend/src/test/java/acp/generated/InvocationHttpTest.java';p.write_text(http_source(domain))
        p=directory/'backend/src/test/java/acp/generated/DeliveryJobTest.java';p.write_text(delivery_source(domain))
        p=directory/'backend/src/test/resources/invocation-profile-V1.sql';p.parent.mkdir(parents=True,exist_ok=True);p.write_text((ROOT/'historical/invocation-0.1'/(domain+'-V1__initial.sql')).read_text())
        for name,text in variants(domain,nodes).items():
            p=directory/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        evidence={'profile':PROFILE['profile'],'generator':PROFILE['generator'],'generatedProvenance':__import__('json').loads((directory/'acp/provenance.json').read_text())['build'],'canonicalDigest':snapshot['contentDigest'],'fullTargetAdmission':admission,'checks':{}}
        report['domains'][domain]=evidence
        if builds:
            with (output/(domain+'-postgresql.log')).open('wb') as log:
                result=subprocess.run(['mvn','-B','-ntp','test'],cwd=directory/'backend',stdout=log,stderr=subprocess.STDOUT,timeout=600)
            evidence['checks']['generated-postgresql-invocation']='PASS' if result.returncode==0 else 'FAIL'
            suites=[]
            for xml in sorted((directory/'backend/target/surefire-reports').glob('TEST-*.xml')):
                root=ET.parse(xml).getroot()
                suites.append({'suite':root.attrib['name'], 'tests':int(root.attrib['tests']),
                    'failures':int(root.attrib['failures']), 'errors':int(root.attrib['errors']), 'skipped':int(root.attrib['skipped']),
                    'cases':[{'name':c.attrib['name'],'status':'FAIL' if any(c.find(k) is not None for k in ('failure','error','skipped')) else 'PASS'} for c in root.findall('testcase')]})
            evidence['postgresqlVersion']='18.6' if 'PostgreSQL 18.6' in (output/(domain+'-postgresql.log')).read_text() else 'UNVERIFIED'
            evidence['generatedTestSuites']=suites
            if result.returncode or not suites or any(s['failures'] or s['errors'] or s['skipped'] for s in suites):failed=True
            if result.returncode==0:
                for key,command in (
                    ('frontend-lock',['npm','ci','--ignore-scripts','--no-audit','--no-fund']),
                    ('frontend-types',['npm','run','typecheck']),('frontend-tests',['npm','test']),('frontend-build',['npm','run','build'])):
                    with (output/(domain+'-'+key+'.log')).open('wb') as log:
                        check=subprocess.run(command,cwd=directory/'frontend',stdout=log,stderr=subprocess.STDOUT,timeout=600)
                    evidence['checks'][key]='PASS' if check.returncode==0 else 'FAIL'
                    if check.returncode:failed=True;break
        (output/'delivery-job-report.json').write_text(json.dumps(report,indent=2)+'\n')
    report['result']='FAIL' if failed else ('COMPONENTS_PASS_FULL_TARGET_STILL_BLOCKED' if builds else 'GENERATED_ONLY_NO_RUNTIME_CLAIM')
    (output/'delivery-job-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,sort_keys=True));return int(failed)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--run-builds',action='store_true');args=parser.parse_args()
    raise SystemExit(run(args.output,args.run_builds))
