"""Retain audited observations and a conservative reporting-policy review.

Does not rerun or relabel runtime evidence. Execution and reporting commits
are recorded separately. Large binary/raw evidence stays outside Git.
"""
import argparse
import copy
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

from phase6 import ROOT,TARGET,BUNDLE,bundle_digest,digest,write
from criteria import assess


def publish(source):
    raw=json.loads((source/'phase6-final-closure.json').read_text())
    if raw.get('executionError') or raw['sealedBundleAfterAudit']!='sha256:'+BUNDLE or bundle_digest()!=BUNDLE:
        raise RuntimeError('COMPLETE_UNCHANGED_AUDIT_REQUIRED')
    evidence=TARGET/'evidence';artifacts=ROOT/'.audit-artifacts/phase6-final-closure';artifacts.mkdir(parents=True,exist_ok=True)
    records={}
    for path in sorted(source.glob('*')):
        if path.suffix in ('.json','.log') or path.name.endswith('-production-1.tar'):
            records[path.name]=path.read_bytes()
    for path in sorted((source/'admission').rglob('browser-results.json')):
        records[path.relative_to(source).as_posix()]=path.read_bytes()
    supplemental=source/'admission/supplemental-http'
    for path in sorted(supplemental.rglob('*')):
        if path.is_file():records[path.relative_to(source).as_posix()]=path.read_bytes()
    for path in sorted((source/'admission').glob('*.log')):
        records[path.relative_to(source).as_posix()]=path.read_bytes()
    archive_bytes=io.BytesIO()
    with gzip.GzipFile(fileobj=archive_bytes,mode='wb',mtime=0) as zipped:
        with tarfile.open(fileobj=zipped,mode='w',format=tarfile.PAX_FORMAT) as archive:
            for name,data in sorted(records.items()):
                info=tarfile.TarInfo(name);info.size=len(data);info.mtime=0;info.mode=0o644
                archive.addfile(info,io.BytesIO(data))
    archive_path=artifacts/'raw-audit-evidence.tar.gz';archive_path.write_bytes(archive_bytes.getvalue())
    report=copy.deepcopy(raw)
    totals={}
    for domain in raw['packages']:
        matches=re.findall(r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)',(source/'admission'/(domain+'-backend.log')).read_text())
        count,failures,errors,skipped=map(int,matches[-1])
        if failures or errors or skipped:raise RuntimeError('BACKEND_RESULTS_NOT_GREEN')
        totals[domain]=count
    supplemental=json.loads((source/'admission/supplemental-http/http-outcomes-report.json').read_text())
    if supplemental['result']!='PASS':raise RuntimeError('HTTP_RESULTS_NOT_GREEN')
    report['validationCounts']={'backend':totals,'mainBrowser':{d:v['browser']['stats'] for d,v in raw['admission']['domains'].items()},
        'supplementalBrowser':{d:v['stats'] for d,v in supplemental['domains'].items()},'faultHistoryTests':38}
    report['rawEvidence']={'path':archive_path.relative_to(ROOT).as_posix(),'sha256':digest(archive_path.read_bytes()),
        'originalReportDigest':digest((source/'phase6-final-closure.json').read_bytes()),
        'fileDigests':{n:digest(b) for n,b in records.items()},'scope':'AUDIT_EVIDENCE_NOT_A_DEPLOYMENT_PACKAGE'}
    report['reportingReview']={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'at':datetime.now(timezone.utc).isoformat(),'actorType':'AI','humanAcceptance':'NOT_GRANTED',
        'reason':'Criterion 32 tightened: same-checkout repeat packages do not prove independent clean package builds. Runtime observations unchanged.',
        'policyDigest':digest((ROOT/'tooling/audit/criteria.py').read_bytes())}
    report['criteria']=assess(report);report['blockers']=[c for c in report['criteria'] if c['status']=='BLOCKED']
    report['recommendation']='PHASE6_CLOSURE_BLOCKED'
    traces={}
    for domain,p in report['provenance'].items():
        rows=p.pop('traceability')
        traces[domain]={'canonicalDigest':report['baseline']['canonicalDigests'][domain],
            'hostPlanEvidence':{'archiveEntry':domain+'-artifact-plan.json','sha256':digest(records[domain+'-artifact-plan.json'])},
            'representatives':[{k:v for k,v in row.items() if k!='artifacts'}|{'artifacts':[{'path':a['path'],'sha256':a['sha256']} for a in row['artifacts']]} for row in rows]}
        p['traceabilityEvidence']='phase6-final-traceability.json'
        p['hostPlanEvidence']=traces[domain]['hostPlanEvidence']
    trace_binding=write(evidence/'phase6-final-traceability.json',traces)
    details=json.loads((source/'osv-advisory-details.json').read_text())
    review={'retrievedAt':details['retrievedAt'],'method':'Versioned PURL OSV batch query, followed by individual advisory details; no reachability waiver.',
        'apiContract':'https://google.github.io/osv.dev/post-v1-querybatch/','advisories':[]}
    for key,value in details['advisories'].items():
        review['advisories'].append({'id':key,'url':'https://osv.dev/vulnerability/'+key,
            'severity':value.get('database_specific',{}).get('severity','UNKNOWN'),
            'published':value.get('published'),'modified':value.get('modified'),'cvss':value.get('severity',[]),
            'affected':value['affected'],'disposition':'RELEASE_BLOCKER' if value.get('database_specific',{}).get('severity') in ('HIGH','CRITICAL') else 'TRIAGE_REQUIRED'})
    review['distinctAdvisories']=len(review['advisories'])
    review['high']=sum(a['severity']=='HIGH' for a in review['advisories']);review['moderate']=sum(a['severity']=='MODERATE' for a in review['advisories'])
    report['securityReview']=write(evidence/'phase6-final-security.json',review)
    report['traceabilityReport']=trace_binding
    for domain,package in report['packages'].items():
        destination=artifacts/(domain+'-production.tar');shutil.copyfile(source/(domain+'-production-1.tar'),destination)
        package['localArtifact']=destination.relative_to(ROOT).as_posix()
        if digest(destination.read_bytes())!=package['packageDigest']:raise RuntimeError('PACKAGE_DIGEST')
        for key in ('sbom','dependencies'):
            name=package[key]['path'];destination=evidence/('phase6-final-'+name)
            shutil.copyfile(source/name,destination)
            if digest(destination.read_bytes())!=package[key]['sha256']:raise RuntimeError('EVIDENCE_DIGEST')
            package[key]['path']=destination.name
    for domain,value in report['admission']['domains'].items():
        browser=value['browser'];path='admission/'+domain+'/frontend/browser-results.json'
        value['browser']={'stats':browser['stats'],'rawEvidence':{'archiveEntry':path,'sha256':digest(records[path])}}
    report_path=evidence/'phase6-final-closure.json';write(report_path,report)
    md=ROOT/'docs/phase6-final-closure-audit.md'
    prefix=md.read_text().split('## Audit execution result')[0]
    text='''## Audit execution result

**PHASE6_CLOSURE_BLOCKED — audit performed.** No human closure approval is implied. Phase 6 remains IN_PROGRESS; Phase 7 remains NOT_STARTED. No push was performed.

'''
    text+=f"The final runtime audit executed from `{report['baseline']['auditExecutionCommit']}`. Reporting-policy review is separately bound to `{report['reportingReview']['commit']}`; it tightens criterion 32 without changing observed runtime evidence. The later evidence commit records results and is not represented as the browser source commit. The audit exited **2 intentionally**, with no execution error.\n\n"
    text+='Both unchanged approved applications negotiated with **zero capability blockers** and passed full admission. Fresh local results: **145 backend tests, 24 main browser journeys, 16 supplemental HTTP/browser journeys and 38 worker/materializer/ownership/history/approval tests passed**. Automated axe evidence remains distinct from outstanding manual review.\n\n'
    text+='Each application package reproduced byte-for-byte in two builds and passed the test-code exclusion gate. These builds shared a checkout/cache; independent clean package reproduction remains **BLOCKED**, not inferred from these results. The distribution contains a configuration inventory, not a complete enforced production configuration schema.\n\n'
    text+='| Application | Package SHA-256 | Bytes | SBOM |\n| --- | --- | ---: | --- |\n'
    for d,p in report['packages'].items():text+=f"| {d} | `{p['packageDigest'].split(':')[1]}` | {p['bytes']} | [CycloneDX](../targets/spring-vue-postgres/evidence/{p['sbom']['path']}) |\n"
    text+='\nPackage files and the raw evidence archive are retained locally under `.audit-artifacts/phase6-final-closure/` and ignored by Git. Their digests and archive-entry hashes are bound in the [machine report](../targets/spring-vue-postgres/evidence/phase6-final-closure.json). `/tmp` logs remain ephemeral. The dedicated CI job will retain packages and raw evidence when explicitly pushed and run; no fresh hosted audit is claimed.\n\n'
    text+='### Security and license disposition\n\n'
    text+=f"Production npm audit returned zero findings. OSV returned **14 package/advisory matches per application**, representing **{review['distinctAdvisories']} distinct advisories: {review['high']} HIGH and {review['moderate']} MODERATE** across Jackson 2.21.5/3.1.5 core/databind. The versioned PURL query follows the [OSV batch API](https://google.github.io/osv.dev/post-v1-querybatch/). [Core HIGH advisory](https://osv.dev/vulnerability/GHSA-7hhh-6rmp-j9qf) and [databind HIGH advisory](https://osv.dev/vulnerability/GHSA-cxp5-3px4-pw24) affect the packaged versions. Dated advisory records, affected ranges, severities and CVSS data are in the [security evidence](../targets/spring-vue-postgres/evidence/phase6-final-security.json). No reachability waiver or dependency upgrade was applied.\n\n"
    text+='Each application inventory contains 188 backend/frontend components, including development tooling distinguished from runtime dependencies; 54 components lack a captured license declaration. Unknown declarations do not prove incompatibility, but complete notices/redistribution review is unresolved. Maven build-plugin/transitive locking and generation-tool vulnerability coverage are incomplete. No legal approval or universal security guarantee is claimed.\n\n'
    text+='### Required corrective tranche\n\n'
    text+='1. Create a deliberate successor for actual production defects: Canonical 0.3 migration/backfill storage, affected Jackson dependencies, and startup configuration/transport admission. Do not mutate sealed 0.4.0 or change approved business semantics.\n2. Prove the complete applicable accepted-history deployment chain, including explicit authorization/backfills, migrations, post-transition backend/frontend behavior, ownership and provenance; independent legacy upgrade tests are insufficient.\n3. Complete the non-test OIDC integration fixture, exact provenance/runtime trace reconciliation, ownership-transition matrix, migration failure and real-process restart matrices, remaining sandbox exhaustion/syscall probes, independent clean packaging, dependency/license/security review, bounded scaling/performance measurements and fresh pinned Ubuntu closure-audit execution.\n\n'
    text+='### All requested dispositions\n\n| Requirement | Area | Disposition | Evidence or exact gap |\n| ---: | --- | --- | --- |\n'
    for c in report['criteria']:text+=f"| {c['requirement']} | {c['area']} | {c['status']} | {c['detail'].replace('|','/')} |\n"
    text+='\nThe machine report binds the immutable baseline, exact Canonical/release/bundle/UI/migration/package/SBOM digests, dated security evidence, browser observations, fault/history results and every generated outstanding deployment requirement. Family-level [traceability](../targets/spring-vue-postgres/evidence/phase6-final-traceability.json) is retained without pretending suite-level links are per-object runtime proof. Stop here for human review of this blocked audit and authorization of the corrective tranche.\n'
    md.write_text(prefix+text)
    print('Retained PHASE6_CLOSURE_BLOCKED;',len(report['blockers']),'blocked criteria')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args();publish(a.source.resolve())
