"""Dated advisory details and dispositions for both old and current matches."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[2]

def run(source):
    report=json.loads((source/'phase6-final-closure.json').read_text())
    old=json.loads((ROOT/'targets/spring-vue-postgres/evidence/phase6-final-security.json').read_text())
    previous={v['id']:v for v in old['advisories']}
    current={v['id'] for p in report.get('packages',{}).values()
        for result in p['security'].get('osv',{}).get('response',{}).get('results',[])
        for v in result.get('vulns',[])}
    records={}
    for key in sorted(set(previous)|current):
        with urllib.request.urlopen('https://api.osv.dev/v1/vulns/'+key,timeout=30) as response:records[key]=json.load(response)
    inventories={};complete=True
    for domain,package in report.get('packages',{}).items():
        path=source/package['sbom']['path']
        if 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()!=package['sbom']['sha256']:raise ValueError('SECURITY_SBOM_BINDING')
        components=json.loads(path.read_text())['components']
        inventories[domain]=[{'group':c.get('group'),'name':c['name'],'version':c['version'],'purl':c.get('purl')} for c in components if 'jackson' in c.get('group','')]
        complete &= package['security'].get('osv',{}).get('status')=='COMPLETED'
    complete &= set(inventories)=={'payment','case-management'}
    dispositions=[]
    for key,prior in previous.items():
        affected={a['package']['name'] for a in records[key]['affected'] if a['package'].get('ecosystem')=='Maven'}
        observed={d:[c for c in cs if str(c['group'])+':'+c['name'] in affected] for d,cs in inventories.items()}
        observed_all=bool(observed) and all(observed.values())
        dispositions.append({'id':key,'previousSeverity':prior['severity'],
            'disposition':'REMEDIATED_IN_PACKAGED_RUNTIME' if complete and observed_all and key not in current else 'BLOCKED_REVIEW_REQUIRED',
            'basis':'Actual packaged inventory bound to SBOM and fresh OSV queries; prior advisory retained, no suppression. This is runtime scope only.',
            'currentVersions':observed,'matchedInCurrentAssessment':key in current,'advisoryModified':records[key].get('modified')})
    result={'retrievedAt':datetime.now(timezone.utc).isoformat(),'bundleDigest':report.get('baseline',{}).get('bundleDigest'),
        'advisories':records,'previousFindingDispositions':dispositions,'currentMatchedAdvisories':sorted(current),
        'scope':'Packaged runtime matches and all seven historical findings; compiler/build-plugin security remains separate and incomplete.'}
    (source/'osv-advisory-details.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Retained advisory records:',len(records),'previous dispositions:',len(dispositions))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);args=p.parse_args();run(args.source.resolve())
