"""Closed, metadata-only failure export. Raw logs, HTTP bodies and SQL stay private."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path

def collect(workspace,output):
    root=Path(workspace);out=Path(output)
    if out.exists():raise ValueError('DIAGNOSTIC_EXPORT_COLLISION')
    facts={'schema':'acp-operational-failure/1','result':'FAIL','scope':'QUALIFICATION_ONLY','releaseClosure':'BLOCKED','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'files':{},'exceptions':[],'sqlFailures':[],'http':[],'cleanup':[],'observations':[],'events':[]}
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.is_symlink() or any(x in p.relative_to(root).parts for x in ('node_modules','target','m2','npm','browsers','application','outputs')):continue
        raw=p.read_bytes();name=p.relative_to(root).as_posix()
        if not re.fullmatch(r'[A-Za-z0-9_./-]{1,240}',name):continue
        facts['files'][name]=hashlib.sha256(raw).hexdigest()
        if p.name.startswith('demo-backend-'):
            for kind,state in re.findall(r'H4_EXCEPTION:([A-Za-z0-9_.$]+):([A-Z0-9]{5})?',raw.decode(errors='replace')):
                if re.fullmatch(r'(?:java|javax|org|acp)\.[A-Za-z0-9_.$]{1,180}',kind):facts['exceptions'].append({'file':name,'class':kind,'sqlState':state or None})
        if p.name.startswith('demo-backend-'):
            for line in raw.decode(errors='replace').splitlines():
                try:
                    message=json.loads(line).get('message','')
                    if not message.startswith('ACP_OPERATIONAL '):continue
                    e=json.loads(message[len('ACP_OPERATIONAL '):])
                    if set(e)=={'contract','classificationContract','event','correlation','outcome','origin','originRevision'} and e['contract']=='acp-h6-operations/1' and e['classificationContract']=='1.0.0' and e['event'] in {'STARTUP','MIGRATION','HTTP','AUTHENTICATION','AUTHORIZATION','DATABASE','TRANSACTION','IDEMPOTENCY','DOCUMENT','WORKFLOW','WORKER','READINESS','RECOVERY','SHUTDOWN'} and e['outcome'] in {'SUCCEEDED','DENIED','FAILED','COMMITTED','ROLLED_BACK','INDETERMINATE','REPLAYED','UP','DOWN','STARTED','STOPPED'} and re.fullmatch('[0-9a-f-]{36}',e['correlation']) and re.fullmatch('[A-Za-z0-9:_-]{1,128}',e['origin']) and type(e['originRevision']) is int:
                        if len(facts['events'])<2000:facts['events'].append(e)
                except (ValueError,TypeError,AttributeError):continue
        if p.name=='failure-observations.json':
            row=json.loads(raw);allowed={'errorClass','pid','postgresPaused','healthHTTP','pressureWaiters','captureErrorClass'}
            if set(row)<=allowed and re.fullmatch('[A-Za-z]{1,80}',row.get('errorClass','')) and re.fullmatch('[A-Za-z]{0,80}',row.get('captureErrorClass','')) and type(row.get('postgresPaused')) is bool and (row.get('pid') is None or type(row.get('pid')) is int) and (row.get('pressureWaiters') is None or type(row.get('pressureWaiters')) is int) and all(k in ('liveness','readiness','worker') and (v is None or type(v) is int and 100<=v<=599) for k,v in row.get('healthHTTP',{}).items()):facts['observations'].append(row)
        if p.name=='postgres-failure.log':
            for stamp,kind in re.findall(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+ UTC) \[\d+\] ERROR:  (duplicate key value violates unique constraint|deadlock detected|canceling statement due to statement timeout)',raw.decode(errors='replace')):
                facts['sqlFailures'].append({'time':stamp,'kind':kind})
        if p.name=='worker-admin-observations.json':
            for row in json.loads(raw):
                if set(row)=={'action','status','responseSHA256','occurrence'} and re.fullmatch('[A-Z_]{1,32}',row['action']) and isinstance(row['status'],int) and re.fullmatch('[0-9a-f]{64}',row['responseSHA256']) and (row['occurrence'] is None or isinstance(row['occurrence'],int)):facts['http'].append(row)
        if p.name in ('resources.json','execution-resources.json'):
            for row in json.loads(raw):
                if row.get('cleanup') in ('PENDING','OWN_CONTAINER_AND_VOLUME_REMOVED'):facts['cleanup'].append({'cleanup':row['cleanup'],'identitySHA256':hashlib.sha256(str(row.get('container','')).encode()).hexdigest()})
    out.mkdir(mode=0o700);(out/'failure.json').write_text(json.dumps(facts,sort_keys=True,indent=2)+'\n');return facts

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--output',required=True);a=p.parse_args();collect(a.workspace,a.output)
