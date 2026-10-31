"""Read-only projections of existing ACP ports. Host inputs are never client paths."""
import json,sys,os,stat,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.source_intelligence.model import encode,sha,digest,read,current,impact,require
from engineering.verification.integration import load_model,validate_result
from deterministic_approval import APPROVED
from deterministic_fixtures import DEST
from canonical_json import load as canonical_load,digest as canonical_digest
from canonical_ir import validate_snapshot
from changes import graph,reverse,closure

TOOLS=('project.summary','project.context','spec.query','spec.validate','compiler.plan','source.symbol','source.references','source.impact','compiler.verify')
RESTRICTIONS=('READ_ONLY','NO_CHANGE_AUTHORIZATION','QUALIFICATION_ONLY','PHASE6_RELEASE_CLOSURE_BLOCKED','OPERATIONAL_SECURITY_NOT_ESTABLISHED','PRODUCTION_NOT_AUTHORIZED')

def input_bytes(path):
 p=Path(path).absolute()
 require(not any(x.is_symlink() for x in (p,*p.parents)), 'HOST_INPUT_SYMLINK')
 before=p.stat()
 require(stat.S_ISREG(before.st_mode) and before.st_size<=12*1024*1024,'HOST_INPUT_BOUND')
 with os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW),'rb') as f:
  opened=os.fstat(f.fileno());raw=f.read(12*1024*1024+1);after=os.fstat(f.fileno())
 stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
 require(stamp(before)==stamp(opened)==stamp(after)==stamp(p.stat()) and len(raw)<=12*1024*1024,'HOST_INPUT_CHANGED')
 return raw

class Application:
 def __init__(self,cfg):
  require(set(cfg)=={'root','baseline','model','verification','plan'},'HOST_APPLICATION_FIELDS')
  self.root=Path(cfg['root']);self.cfg=cfg
  def load(key):
   item=cfg[key];require(set(item)=={'path','sha256'},'HOST_INPUT_FIELDS')
   path=Path(item['path']);raw=input_bytes(path);require(sha(raw)==item['sha256'],'HOST_INPUT_DIGEST');return json.loads(raw)
  self.baseline=load('baseline');self.model=load('model');self.verification=validate_result(load('verification'));self.plan=load('plan')
  # The explicit host preparation already used Session's native approval,
  # compiler and plan checks. Inspect the exact original approved snapshot;
  # never recompile or reconstruct authority during an MCP request.
  self.b=self.baseline
  require(self.b['domain'] in APPROVED,'UNKNOWN_APPLICATION')
  self.snapshot=canonical_load(DEST/(self.b['domain']+'-canonical-candidate.json'))
  require(self.snapshot['contentDigest']==APPROVED[self.b['domain']]['contentDigest']==self.b['canonicalDigest'] and canonical_digest(self.snapshot['content'],'canonical')==self.b['canonicalDigest'],'APPROVED_CANONICAL_IDENTITY')
  self.nodes={n['id']:n for n in self.snapshot['content']['nodes']}
  self.revisions={i:n['revision'] for i,n in self.nodes.items()}
  load_model(cfg['model']['path'],cfg['model']['sha256'])
  require(self.model['bindingDigest']==cfg['baseline']['sha256'],'MODEL_BASELINE')
  require(self.plan['schema']=='acp-mcp-plan/1' and self.plan['artifactPlanDigest']==self.b['artifactPlanDigest'],'PLAN_BINDING')
  expected=self.plan['inputs'];actual=self.verification['inputs']
  require(all(actual.get(k)==v for k,v in expected.items()),'VERIFICATION_INPUT_BINDING')
  require(expected['baselineSHA256']==cfg['baseline']['sha256'] and expected['sourceModelFileSHA256']==cfg['model']['sha256'] and expected['canonicalDigest']==self.snapshot['contentDigest'] and expected['artifactPlanDigest']==self.b['artifactPlanDigest'],'APPROVED_INPUT_BINDING')
  self.symbols={s['id']:s for s in self.model['symbols']};self.edges=graph(self.snapshot)
  self.fresh()
 def fresh(self):
  for key in ('baseline','model','verification','plan'):
   item=self.cfg[key];p=Path(item['path']);require(sha(input_bytes(p))==item['sha256'],'STALE_HOST_INPUT')
  current(self.model,self.root)
 def symbol(self,s):
  return {k:s[k] for k in ('id','language','kind','name','confidence','location','sourceHash','ownership')}
 def row(self,r):
  return {k:r[k] for k in ('id','kind','result','origins')}|{'reasons':[x.split(':',1)[0] for x in r['reasons']]}
 def envelope(self,operation):
  v=self.verification
  return {'schema':'acp-mcp-response/1','operation':operation,'application':self.b['domain'],'canonicalDigest':self.snapshot['contentDigest'],'artifactPlanDigest':self.b['artifactPlanDigest'],'targetIRDigest':self.plan['inputs']['targetIRDigest'],'compilationAuditDigest':self.plan['inputs']['compilationAuditDigest'],'compiler':self.b['compiler'],'generator':self.b['generator'],'target':self.plan['targetIdentity'],'sourceModelDigest':self.model['digest'],'verificationDigest':v['digest'],'verificationSummary':v['summary'],'attention':[self.row(r) for r in v['results'] if r['result']=='FAIL'],'unresolvedRetrieval':{'tool':'compiler.verify','statuses':['FAIL','BLOCKED','NOT_RUN']},'evidenceTiming':'RETAINED_HISTORICAL_RESULT_NOT_FRESH_EXECUTION','executionIdentity':{k:v['inputs'].get('executionEvidence',{}).get(k) for k in ('sourceCommit','run','evaluatedAt')},'completeness':self.model['completeness'],'restrictions':list(RESTRICTIONS)}
 def semantic(self,ids):
  require(all(i in self.nodes for i in ids),'UNKNOWN_SEMANTIC_ID');return ids
 def selected(self,q):
  ids=self.semantic(q['ids'])
  if q['task']:
   words=set(re.findall(r'[a-z0-9]+',q['task'].lower()));ids=sorted(set(ids)|{i for i,n in self.nodes.items() if words&set(re.findall(r'[a-z0-9]+',(i+' '+n['kind']+' '+' '.join(str(n['data'].get(k,'')) for k in ('name','title','description','statement','scenario'))).lower()))})
   require(ids,'UNRESOLVED_TASK_USE_SEMANTIC_IDS')
  return set(ids)
 def context_rows(self,ids):
  chosen=closure(closure(ids,reverse(self.edges)),self.edges);rows=[]
  for i in sorted(chosen):
   rows.append({'kind':'SEMANTIC_OBJECT','value':self.nodes[i]})
   rows.extend({'kind':'SOURCE_MAPPING','value':m} for m in self.model['semanticMappings'] if m['semantic']['id']==i)
   rows.extend({'kind':'VERIFICATION_RESULT','value':self.row(r)} for r in self.verification['results'] if any(o['id']==i for o in r['origins']))
  return chosen,rows
 def call(self,operation,q):
  self.fresh();out=self.envelope(operation);ids=self.selected(q);symbol=q['symbol']
  if symbol:require(symbol in self.symbols,'UNKNOWN_SYMBOL_ID')
  if operation=='project.summary':
   rows=[{'project':self.snapshot['content']['applicationId'],'compiler':self.b['compiler'],'generator':self.b['generator'],'target':self.plan['targetIdentity'],'semanticObjects':len(self.nodes),'sourceSymbols':len(self.symbols),'supportedTools':list(TOOLS)}]
  elif operation=='spec.validate':
   validate_snapshot(self.snapshot);rows=[{'result':'PASS','check':'canonical_ir.validate_snapshot','authority':'EXISTING_APPROVAL_UNCHANGED'}]
  elif operation=='compiler.plan':
   rows=[a for a in self.plan['artifacts'] if not ids or any(o['id'] in ids for o in a['origins'])]
  elif operation=='spec.query':rows=[n for i,n in sorted(self.nodes.items()) if (not ids or i in ids) and (not q['kind'] or n['kind']==q['kind'])]
  elif operation=='project.context':
   require(ids,'SEMANTIC_SELECTOR_REQUIRED');chosen,rows=self.context_rows(ids)
   out['selection']={'seeds':sorted(ids),'policy':'existing changes.graph reverse impact then forward dependency closure','objects':len(chosen)}
  elif operation=='source.symbol':
   mapped={m['symbol'] for m in self.model['semanticMappings'] if m['semantic']['id'] in ids}
   rows=[self.symbol(s) for i,s in sorted(self.symbols.items()) if (not symbol or i==symbol) and (not ids or i in mapped)]
  elif operation=='source.references':
   require(symbol,'SYMBOL_REQUIRED');rows=[e for e in self.model['references']+self.model['typeRelations'] if symbol in (e['from'],e['to'])]
  elif operation=='source.impact':
   require(bool(symbol)!=bool(ids) and len(ids)<=1,'EXACT_IMPACT_SELECTOR_REQUIRED')
   result=impact(self.model,self.root,symbol=symbol or None,semantic=next(iter(ids)) if ids else None)
   rows=[{'relationship':e} for e in result['provenDependencies']]+[{'definition':self.symbol(s)} for s in result['affectedDefinitions']]+[{'possibleImpact':e} for e in result['possibleImpacts']]
   out['impact']={k:result[k] for k in ('seeds','authority','limitation')}
  elif operation=='compiler.verify':
   rows=[self.row(r) for r in self.verification['results'] if (not ids or any(o['id'] in ids for o in r['origins'])) and (not q['status'] or r['result']==q['status'])]
  else:raise ValueError('UNSUPPORTED_OPERATION')
  # Cursor is a deterministic continuation bound to operation, query and all inputs.
  context=digest([operation,{k:v for k,v in q.items() if k!='cursor'},{k:self.cfg[k]['sha256'] for k in ('baseline','model','verification','plan')}])
  offset=0
  if q['cursor']:
   parts=q['cursor'].split(':');require(len(parts)==2 and parts[0]==context and parts[1].isdigit(),'INVALID_CONTINUATION');offset=int(parts[1]);require(0<=offset<len(rows),'INVALID_CONTINUATION')
  out.update(items=[],total=len(rows),next=None,complete=not rows)
  for index in range(offset,min(len(rows),offset+q['limit'])):
   candidate={**out,'items':out['items']+[rows[index]],'next':f'{context}:{index+1}' if index+1<len(rows) else None,'complete':index+1==len(rows)}
   if len(encode(candidate))>q['budget']:break
   out=candidate
  require(out['items'] or not rows,'BUDGET_TOO_SMALL_FOR_REQUIRED_CONTEXT')
  if offset+len(out['items'])<len(rows):out['next']=f"{context}:{offset+len(out['items'])}"
  require(len(encode(out))<=q['budget'],'BUDGET_TOO_SMALL_FOR_REQUIRED_CONTEXT');self.fresh();return out

class Service:
 def __init__(self,path):
  p=Path(path);raw=read(p.parent,p.name);cfg=json.loads(raw)
  require(set(cfg)=={'schema','applications'} and cfg['schema']=='acp-mcp-host/1' and set(cfg['applications'])=={'payment','case-management'},'HOST_CONFIGURATION')
  self.config=cfg['applications'];self.apps={}
 def application(self,name):
  require(name in self.config,'UNKNOWN_APPLICATION')
  if name not in self.apps:
   app=Application(self.config[name]);require(app.b['domain']==name,'APPLICATION_BINDING');self.apps[name]=app
  return self.apps[name]
 def call(self,operation,q):return self.application(q['application']).call(operation,q)
