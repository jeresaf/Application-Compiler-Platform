"""Lifecycle orchestration of existing source, verification and MCP adapters."""
import asyncio,copy,json,sys
from pathlib import Path
from engineering.source_intelligence import analysis
from engineering.source_intelligence.model import encode,sha,require,impact,compare,current
from engineering.verification.integration import Session,wire
from engineering.mcp_adapter.service import Service
from compiler_contracts import Owner
from filesystem_artifacts import FilesystemArtifactStore

HUMAN='frontend/src/extensions/identity.ts'

def extension_baseline(original,root,output):
 """New observation of authorized HUMAN bytes; never rewrite the original baseline."""
 b=json.loads(Path(original).read_bytes());rows={x.path:x for x in FilesystemArtifactStore(root).inventory()}
 require(set(rows)==set(b['files']),'SOURCE_INVENTORY_CHANGED')
 for name,old in b['files'].items():
  raw=(Path(root)/name).read_bytes();item=rows[name]
  require(str(item.owner)==old['owner'],'OWNERSHIP_CHANGED')
  if sha(raw)!=old['sha256']:
   require(item.owner==Owner.HUMAN and name==HUMAN,'MANAGED_BASELINE_REPLACEMENT')
   old.update(sha256=sha(raw),contentDigest=item.digest)
 require(not Path(output).exists(),'BASELINE_COLLISION');Path(output).write_bytes(encode(b));return sha(Path(output).read_bytes())

def inspect(root,baseline,output,*,maven_repo,node_modules):
 output=Path(output);output.mkdir(mode=0o700,exist_ok=False);pin=sha(Path(baseline).read_bytes())
 model=analysis.analyze(root,baseline,pin,maven_repo=Path(maven_repo),node_modules=Path(node_modules),scratch=output)
 model_path=output/'source-model.json';model_path.write_bytes(encode(model))
 session=Session(root,baseline,pin,model_path,sha(model_path.read_bytes()))
 result=session.evaluate();require(all(r['result']=='PASS' for r in result['results'] if r['kind']=='ARTIFACT_VERIFICATION'),'ARTIFACT_VERIFICATION_FAILED')
 (output/'verification-result.json').write_bytes(encode(result))
 selected=impact(model,root,semantic='UC-TASK');(output/'impact.json').write_bytes(encode(selected))
 plan={'schema':'acp-mcp-plan/1','inputs':session.inputs,'artifactPlanDigest':session.b['artifactPlanDigest'],'targetIdentity':session.target.target,'artifacts':[{'path':a.path,'sha256':session.b['files'][a.path]['sha256'],'ownership':str(a.owner),'origins':wire(a.mappings),'verification':list(a.verification)} for a in session.plan.artifacts]}
 (output/'plan.json').write_bytes(encode(plan))
 return session,model,result

async def mcp_inspect(foundation,session,folder):
 from mcp import Client
 from mcp.client.stdio import StdioServerParameters
 folder=Path(folder);config=copy.deepcopy(json.loads(Path(foundation).read_bytes()));cfg=config['applications']['case-management']
 cfg.update(root=str(session.root),**{key:{'path':str(p.absolute()),'sha256':sha(p.read_bytes())} for key,p in [('baseline',session.baseline),('model',folder/'source-model.json'),('verification',folder/'verification-result.json'),('plan',folder/'plan.json')]})
 path=folder/'mcp-host.json';path.write_bytes(encode(config));records=[]
 parameters=StdioServerParameters(command=sys.executable,args=['-B','-m','engineering.mcp_adapter.server','--host-config',str(path)],cwd=str(Path(__file__).resolve().parents[2]))
 async with Client(parameters,read_timeout_seconds=45) as client:
  listing=await client.list_tools();require(len(listing.tools)==9,'MCP_TOOL_DISCOVERY')
  symbol=session.model['semanticMappings'][0]['symbol']
  queries=[('project.summary',{}),('spec.query',{'ids':['UC-TASK']}),('project.context',{'ids':['UC-TASK']}),('source.symbol',{'symbol':symbol}),('source.references',{'symbol':symbol}),('source.impact',{'symbol':symbol}),('compiler.plan',{'ids':['UC-TASK']}),('compiler.verify',{}),('compiler.verify',{'status':'BLOCKED'})]
  for name,args in queries:
   r=await client.call_tool(name,{'application':'case-management',**args});require(not r.is_error,'MCP_LIFECYCLE_INSPECTION')
   records.append({'view':'CURRENT_SOURCE','tool':name,'arguments':args,'serializedResultBytes':len(r.model_dump_json(by_alias=True).encode()),'result':r.structured_content})
 # Retain known security FAILs through the real MCP boundary as historical
 # observations; current offline verification must never hide or clear them.
 historical=StdioServerParameters(command=sys.executable,args=['-B','-m','engineering.mcp_adapter.server','--host-config',str(Path(foundation).absolute())],cwd=str(Path(__file__).resolve().parents[2]))
 async with Client(historical,read_timeout_seconds=45) as client:
  await client.list_tools();r=await client.call_tool('compiler.verify',{'application':'case-management','status':'FAIL'})
  require(not r.is_error and r.structured_content['payload']['verificationSummary']['FAIL']>0,'HISTORICAL_FINDINGS_NOT_PRESERVED')
  records.append({'view':'RETAINED_HISTORICAL_SECURITY_NOT_RESCANNED','tool':'compiler.verify','arguments':{'status':'FAIL'},'serializedResultBytes':len(r.model_dump_json(by_alias=True).encode()),'result':r.structured_content})
 (folder/'mcp-results.json').write_bytes(encode(records));return {'tools':len(listing.tools),'calls':len(records),'bytes':sum(r['serializedResultBytes'] for r in records),'authority':'READ_ONLY_NO_APPROVAL'}
