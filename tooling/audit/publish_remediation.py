"""Publish a new remediation evidence identity without modifying the first audit.

Runtime observations are retained verbatim. A separately identified evaluation
checks their artifacts with the execution commit frozen at coordinator startup.
"""
import argparse
import copy
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

from phase6 import ROOT, TARGET, BUNDLE, bundle_digest, digest, write
from criteria import assess, current_binding


def publish(source):
    original=source/'phase6-final-closure.json'
    raw=json.loads(original.read_text())
    if raw.get('executionError') or raw['auditExecution']['status']!='PERFORMED':
        raise ValueError('COMPLETE_AUDIT_REQUIRED')
    if raw['sealedBundleAfterAudit']!='sha256:'+BUNDLE or bundle_digest()!=BUNDLE:
        raise ValueError('UNCHANGED_SEALED_BUNDLE_REQUIRED')
    evidence=TARGET/'evidence'
    durable=ROOT/'.audit-artifacts/phase6-remediation-0.5.0'
    durable.mkdir(parents=True,exist_ok=False)
    files=set()
    for record in raw['criterionEvidence'].values():
        files.update(item['path'] for item in record['artifacts'])
    files.update(p.relative_to(source).as_posix() for p in source.iterdir()
                 if p.is_file() and (p.suffix in ('.json','.log') or p.name.endswith('-production-1.tar')))
    for directory in ('oidc','release-upgrade','attempts'):
        files.update(p.relative_to(source).as_posix() for p in (source/directory).rglob('*')
                     if p.is_file() and p.suffix in ('.json','.log','.xml'))
    files.update(p.relative_to(source).as_posix() for p in (source/'admission').rglob('browser-results.json'))
    files.update(p.relative_to(source).as_posix() for p in (source/'admission').glob('*.log'))
    files.update(p.relative_to(source).as_posix() for p in (source/'admission/supplemental-http').rglob('*')
                 if p.is_file() and p.suffix in ('.json','.log','.xml'))
    records={}
    for name in sorted(files):
        relative=Path(name);path=source/relative
        if relative.is_absolute() or '..' in relative.parts or path.is_symlink() or not path.is_file():
            raise ValueError('UNTRUSTED_RAW_ARTIFACT:'+name)
        records[name]=path.read_bytes()
        destination=durable/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(records[name])
    buffer=io.BytesIO()
    with gzip.GzipFile(fileobj=buffer,mode='wb',mtime=0) as zipped:
        with tarfile.open(fileobj=zipped,mode='w',format=tarfile.PAX_FORMAT) as archive:
            for name,data in sorted(records.items()):
                member=tarfile.TarInfo(name);member.size=len(data);member.mtime=0;member.mode=0o644
                archive.addfile(member,io.BytesIO(data))
    archive=durable/'raw-audit-evidence.tar.gz';archive.write_bytes(buffer.getvalue())
    report=copy.deepcopy(raw)
    binding=current_binding()
    binding['evaluationCommit']=binding['executionCommit']
    binding['executionCommit']=raw['baseline']['auditExecutionCommit']
    report['producerAuditIdentity']=raw['auditIdentity']
    report['auditIdentity']='phase6-remediation-evaluation/'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    report['evidenceRoot']=str(durable)
    manifest=durable/'audit-producer-manifest.json'
    write(manifest,{**binding,'commands':raw['commands']})
    for record in report['criterionEvidence'].values():
        record.update(binding,evaluatedAt=datetime.now(timezone.utc).isoformat())
        for artifact in record['artifacts']:
            if artifact['path']=='audit-producer-manifest.json':artifact['sha256']=digest(manifest.read_bytes())
    report['reportingReview']={**binding,'at':datetime.now(timezone.utc).isoformat(),
        'actorType':'AI','humanAcceptance':'NOT_GRANTED',
        'reason':'Independent artifact re-evaluation; runtime execution commit is frozen to baseline startup. Original report and producer manifest retained verbatim in raw archive.',
        'policyDigest':digest((ROOT/'tooling/audit/criteria.py').read_bytes())}
    # Preserve partial, genuine runtime security coverage as partial evidence.
    # The existing verifier must reject it for complete closure coverage.
    partial={'scanAt':min(p['security']['scanAt'] for p in raw['packages'].values()),
        'bundleDigest':binding['bundleDigest'],'coverage':['packaged-backend','npm-production'],
        'findings':[{'domain':d,'advisory':v} for d,p in raw['packages'].items()
                    for result in p['security'].get('osv',{}).get('response',{}).get('results',[])
                    for v in result.get('vulns',[])],
        'unknownComponents':[{'domain':d,'component':c['bom-ref']} for d in raw['packages']
                    for c in json.loads((source/(d+'-sbom.cdx.json')).read_text())['components']
                    if c.get('scope')=='required' and not c.get('purl')],
        'packages':[{'file':d+'-production-1.tar','sha256':p['packageDigest']} for d,p in raw['packages'].items()],
        'sourceAssessments':{d:p['security'] for d,p in raw['packages'].items()},
        'remainingCoverage':['compiler','build-plugins']}
    scan=durable/'security-assessment.json';write(scan,partial)
    report['criterionEvidence']['21']={'criterion':21,**binding,
        'evaluatedAt':datetime.now(timezone.utc).isoformat(),
        'artifacts':[{'path':'security-assessment.json','sha256':digest(scan.read_bytes())},
                     *[{'path':v['file'],'sha256':v['sha256']} for v in partial['packages']]]}
    report['criteria']=assess(report,root=durable,binding=binding)
    report['blockers']=[row for row in report['criteria'] if row['status']=='BLOCKED']
    report['recommendation']='PHASE6_CLOSURE_BLOCKED' if report['blockers'] else 'PHASE6_CLOSURE_RECOMMENDED'
    report['rawEvidence']={'path':archive.relative_to(ROOT).as_posix(),'sha256':digest(archive.read_bytes()),
        'originalReportDigest':digest(original.read_bytes()),
        'fileDigests':{name:digest(data) for name,data in records.items()},
        'scope':'LOCAL_IGNORED_RAW_AUDIT_EVIDENCE_NOT_A_DEPLOYMENT_PACKAGE'}
    security=json.loads((source/'osv-advisory-details.json').read_text())
    report['securityReview']=write(evidence/'phase6-remediation-security.json',security)
    for domain,package in report['packages'].items():
        package['localArtifact']=(durable/(domain+'-production-1.tar')).relative_to(ROOT).as_posix()
        for key in ('sbom','dependencies'):
            name=package[key]['path'];destination=evidence/('phase6-remediation-'+name)
            shutil.copyfile(source/name,destination)
            if digest(destination.read_bytes())!=package[key]['sha256']:raise ValueError('EVIDENCE_DIGEST')
            package[key]['path']=destination.name
        graph=domain+'-maven-dependency-graph.json'
        package['resolvedDependencyGraph']=write(evidence/('phase6-remediation-'+graph),json.loads((source/graph).read_text()))
    # Full plans and assertion reports remain hash-addressed in the raw archive;
    # the committed report retains summary provenance and exact source identity.
    for domain,value in report['provenance'].items():
        value.pop('traceability',None)
        value['traceabilityEvidence']={'archiveEntry':'traceability-and-provenance.json',
            'sha256':digest(records['traceability-and-provenance.json'])}
    for domain,value in report['admission']['domains'].items():
        # Integration producers reuse the generated frontend directory. The
        # admission report embeds the original browser result and is immutable
        # under admission reuse; a later browser-results.json is a different run.
        path='admission/task-interface-report.json'
        value['browser']={'stats':value['browser']['stats'],
            'rawEvidence':{'archiveEntry':path,'sha256':digest(records[path])}}
    admission=copy.deepcopy(report['admission'])
    admission.update(evidenceIdentity='phase6-remediation-0.5.0-admission',
        originalExecutionCommit=report['reusedAdmission']['originalExecutionCommit'],
        reusedByAuditExecutionCommit=report['baseline']['auditExecutionCommit'],
        rawReportDigest=digest(records['admission/task-interface-report.json']),
        admissionContractVersion='5.0.0',phase6='IN_PROGRESS',phase7='NOT_STARTED')
    report['successorAdmissionEvidence']=write(evidence/'phase6-remediation-admission.json',admission)
    report['additionalValidation']={name:{'archiveEntry':name,'sha256':digest(records[name])}
        for name in ('python-regression.log','local-validation.json','hosted-validation.json') if name in records}
    write(evidence/'phase6-remediation-closure.json',report)
    print(report['recommendation'],len(report['blockers']),'blocked criteria; raw evidence:',durable)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    publish(parser.parse_args().source.resolve())
