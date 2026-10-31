"""Explicit host preparation. Compilation is never an MCP tool operation."""
import argparse,json,shutil,zipfile
from pathlib import Path
from engineering.verification.inputs import reference_inputs,DOMAINS
from engineering.verification.integration import Session,encode,sha,validate_result,wire
from engineering.source_intelligence.analysis import prepare
from engineering.mcp_adapter.service import Service
PHASE8_SHA256='d2d26338105b5e6df7b4484c24fda7213452d998f50a610bfe7745c6404d67c8'

def host(workspace,phase7,phase8,reuse=None):
 w=Path(workspace).absolute();w.mkdir(mode=0o700,exist_ok=False)
 reference_inputs(phase7,w/'reference');raw=Path(phase8).read_bytes()
 if sha(raw)!=PHASE8_SHA256:raise ValueError('PHASE8_ARCHIVE_DIGEST')
 config={'schema':'acp-mcp-host/1','applications':{}}
 with zipfile.ZipFile(phase8) as z:
  if z.testzip() is not None:raise ValueError('PHASE8_ARCHIVE_CORRUPT')
  q=json.loads(z.read('acp-verification/qualification.json'))
  if q['tests']!=30 or any(q[k] for k in ('failures','errors','skips')):raise ValueError('PHASE8_QUALIFICATION')
  for domain in DOMAINS:
   location=w/domain
   if reuse:
    location.mkdir();shutil.copytree(Path(reuse)/domain/domain,location/domain)
   else:prepare(location,domain)
   ref=w/'reference'/domain;model=ref/'source-model.json';baseline=ref/'source-baseline.json'
   session=Session(location/domain,baseline,sha(baseline.read_bytes()),model,sha(model.read_bytes()))
   session.check_fresh()
   report=z.read(f'acp-verification/{domain}/execution-verification-result.json');v=validate_result(json.loads(report))
   if sha(report)!=q['applications'][domain]['fileSHA256']:raise ValueError('PHASE8_RESULT_DIGEST')
   result=location/'verification.json';result.write_bytes(report)
   plan=location/'plan.json';plan.write_bytes(encode({'schema':'acp-mcp-plan/1','inputs':session.inputs,'artifactPlanDigest':session.b['artifactPlanDigest'],'targetIdentity':session.target.target,'artifacts':[{'path':a.path,'sha256':session.b['files'][a.path]['sha256'],'ownership':str(a.owner),'origins':wire(a.mappings),'verification':list(a.verification)} for a in session.plan.artifacts]}))
   config['applications'][domain]={'root':str(location/domain),**{k:{'path':str(p),'sha256':sha(p.read_bytes())} for k,p in [('baseline',baseline),('model',model),('verification',result),('plan',plan)]}}
 path=w/'host.json';path.write_bytes(encode(config));service=Service(path)
 for domain in DOMAINS:service.application(domain)
 return path

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True);p.add_argument('--phase7-archive',required=True);p.add_argument('--phase8-archive',required=True);p.add_argument('--reuse-applications');a=p.parse_args()
 print(host(a.workspace,a.phase7_archive,a.phase8_archive,a.reuse_applications))
if __name__=='__main__':main()
