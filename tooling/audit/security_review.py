"""Retain full dated public advisory details for matches; never suppress findings."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import urllib.request


def run(source):
    report=json.loads((source/'phase6-final-closure.json').read_text())
    ids=sorted({v['id'] for p in report.get('packages',{}).values()
        for result in p['security'].get('osv',{}).get('response',{}).get('results',[])
        for v in result.get('vulns',[])})
    records={}
    for key in ids:
        with urllib.request.urlopen('https://api.osv.dev/v1/vulns/'+key,timeout=30) as response:
            records[key]=json.load(response)
    result={'retrievedAt':datetime.now(timezone.utc).isoformat(),'advisories':records,
        'scope':'Details for existing OSV matches only; absent matches do not establish complete security coverage.'}
    (source/'osv-advisory-details.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Retained advisory records:',len(records))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);args=p.parse_args();run(args.source.resolve())
