"""Reuse the closed H6 failure export and add bounded redacted H9 correlations."""
import argparse,json,re
from pathlib import Path
from engineering.operations.diagnostics import collect
from engineering.http_reliability.scenarios import observations
FIELDS={'correlation','subjectSHA256','tenantSHA256','startedNanos','finishedNanos','status','activeBefore','activeAfter','awaitingBefore','awaitingAfter','acquisitionMetricPresent','acquisitionCountDelta','acquisitionAggregateNanosDelta'}
def export(workspace,output):
    facts=collect(workspace,output);facts['parentFormat']=facts['schema'];facts['schema']='acp-h9-http-failure/1';facts['h9Exceptions']=[];facts['h9Requests']=[];facts['h9HTTP']=[];facts['h9ParseErrors']=0
    root=Path(workspace)
    for folder in (root/'baseline/runtime/signed/runtime',root/'successor/runtime/signed/runtime'):
        try:data=observations(folder)
        except (ValueError,TypeError,KeyError):facts['h9ParseErrors']+=1;continue
        for row in data['exceptions'][:512]:
            if re.fullmatch(r'(java|javax|org|acp)\.[A-Za-z0-9_.$]{1,180}',row['exceptionClass']) and (row['sqlState'] is None or re.fullmatch('[A-Z0-9]{5}',row['sqlState'])):facts['h9Exceptions'].append(row)
        for row in data['requests'][:512]:
            if set(row)!=FIELDS:continue
            if not re.fullmatch('[0-9a-f-]{36}',str(row['correlation'])) or any(not re.fullmatch('(?:[0-9a-f]{64}|NONE)',str(row[k])) for k in ('subjectSHA256','tenantSHA256')):continue
            if any(type(row[k]) is not int or row[k]<0 for k in FIELDS-{'correlation','subjectSHA256','tenantSHA256','acquisitionMetricPresent','acquisitionAggregateNanosDelta'}):continue
            if type(row['acquisitionMetricPresent']) is not bool or type(row['acquisitionAggregateNanosDelta']) not in (int,float) or not 0<=row['acquisitionAggregateNanosDelta']<1e18:continue
            facts['h9Requests'].append(row)
    for file in root.glob('*/runtime/http-results.json'):
        for row in json.loads(file.read_bytes())[:64]:
            response=row.get('response',{});status=response.get('status');correlation=response.get('correlation');digest=response.get('responseSHA256')
            if type(status) is int and 100<=status<=599 and re.fullmatch('[0-9a-f-]{36}',str(correlation)) and re.fullmatch('[0-9a-f]{64}',str(digest)):facts['h9HTTP'].append({'status':status,'correlation':correlation,'responseSHA256':digest})
    (Path(output)/'failure.json').write_text(json.dumps(facts,sort_keys=True,indent=2)+'\n');return facts
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--output',required=True);a=p.parse_args();export(a.workspace,a.output)
