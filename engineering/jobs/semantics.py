"""Bounded service job semantics; no approval or interactive JWT fabrication."""
import copy,json,datetime
from engineering.documents import semantics as parent
from engineering.jobs.schema import CONTRACTS,FEATURES,KINDS
from jsonschema import Draft202012Validator
from canonical_json import canonical_bytes,digest
from canonical_ir import CanonicalError,AdmittedSnapshot

def check(ok,code):
 if not ok:raise CanonicalError('JOB-'+code,code)
def extension_ids(source):
 ids={n['id'] for n in source['nodes'] if n['kind'] in KINDS}
 for n in source['nodes']:
  if n['kind']=='IntegrityJob':ids.update(n['data'][k]['id'] for k in ('schedule','retry'))
 retries={n['data']['retry']['id'] for n in source['nodes'] if n['kind']=='IntegrityJob'}
 failures={r['id'] for n in source['nodes'] if n['kind']=='RetryPolicy' and n['id'] in retries for r in n['data']['failures']}
 shared={r['id'] for n in source['nodes'] if n['kind']=='RetryPolicy' and n['id'] not in retries for r in n['data']['failures']}
 return ids|(failures-shared)
def authoring(snapshot):
 c=snapshot['content'];return {'modelVersion':'0.8.0','applicationId':c['applicationId'],'snapshotId':'JOB-PREVIEW','nodes':copy.deepcopy(c['nodes']),'issues':copy.deepcopy(c['issues']),'approvals':[]}
def document_source(source):
 ids=extension_ids(source);return {**copy.deepcopy(source),'modelVersion':'0.7.0','nodes':[copy.deepcopy(n) for n in source['nodes'] if n['id'] not in ids]}
def validate_source(source):
 check(Draft202012Validator(json.loads((CONTRACTS/'authoring-0.8.schema.json').read_bytes())).is_valid(source),'SHAPE');parent.validate_source(document_source(source));nodes={n['id']:n for n in source['nodes']};check(len(nodes)==len(source['nodes']),'DUPLICATE')
 def get(r,k):
  check(r['id'] in nodes and nodes[r['id']]['kind']==k and nodes[r['id']]['revision']==r['revision'],'REFERENCE');return nodes[r['id']]
 def ref(n):return {'id':n['id'],'revision':n['revision']}
 for n in source['nodes']:
  if n['kind'] not in KINDS:continue
  check(n['lifecycle']=='APPROVED','STRUCTURAL_ELIGIBILITY')
  for b in n['basis']:check(b['id'] in nodes and nodes[b['id']]['revision']==b['revision'],'BASIS')
  d=n['data']
  if n['kind']=='IntegrityJob':
   get(d['document'],'DocumentDefinition');sd=get(d['schedule'],'Schedule')['data'];rd=get(d['retry'],'RetryPolicy')['data'];check(sd['mode']=='INTERVAL' and 1<=sd['intervalSeconds']<=3600,'SCHEDULE')
   try:anchor=datetime.datetime.fromisoformat(sd['anchorInstant'].replace('Z','+00:00'));check(anchor.utcoffset()==datetime.timedelta(0) and anchor.microsecond==0,'ANCHOR')
   except (ValueError,TypeError):check(False,'ANCHOR')
   check(d['leaseSeconds']>d['timeoutSeconds'],'LEASE_TIMEOUT');check(rd['maxAttempts']<=5 and rd['initialSeconds']<=rd['maxDelaySeconds']<=30 and rd['multiplier']<=2 and rd['jitter']=='NONE' and rd['delayBasis']=='AFTER_FAILURE_COMPLETION' and rd['attemptCounting']=='INCLUDING_INITIAL','RETRY')
   check({get(f,'Failure')['data']['code'] for f in rd['failures']}=={'DEPENDENCY_UNAVAILABLE','EXECUTION_TIMEOUT'},'RETRY_CODES')
   for f in rd['failures']:fd=get(f,'Failure')['data'];check(fd['category']=='TRANSIENT' and fd['retryable'],'RETRY_FAILURE')
   check(get(d['worker'],'WorkerGrant')['data']['job']==ref(n),'WORKER');check(get(d['readPermission'],'JobReadPermission')['data']['job']==ref(n),'READ_PERMISSION')
  elif n['kind']=='WorkerGrant':check(get(d['job'],'IntegrityJob')['data']['worker']==ref(n),'WORKER_BINDING')
  elif n['kind']=='JobReadPermission':
   job=get(d['job'],'IntegrityJob');doc=get(job['data']['document'],'DocumentDefinition');resource=get(doc['data']['resource'],'Entity');actor=get(d['actor'],'Actor');get(d['role'],'Role');scope=get(d['scope'],'Scope');field=get(d['principalField'],'Field');check(scope['data']['actor']==ref(actor) and scope['data']['resource']==ref(resource) and scope['data']['resourceTenant']==resource['data']['tenantField'],'READ_SCOPE');check(field['data']['owner']==ref(resource) and field['data']['type']=={'kind':'Identifier','entity':actor['data']['subject']},'READ_OWNER');check(job['data']['readPermission']==ref(n),'READ_BINDING')
  else:job=get(d['job'],'IntegrityJob');get(d['screen'],'Screen');check(d['permission']==job['data']['readPermission'],'VIEW')
 return source
def normalize_candidate(source):
 validate_source(source);base=parent.normalize_candidate(document_source(source));nodes=base['content']['nodes'];ids=extension_ids(source)
 for n in source['nodes']:
  if n['id'] in ids:n=copy.deepcopy(n);n['basis']=sorted(n['basis'],key=canonical_bytes);n['origins']=sorted(n['origins'],key=canonical_bytes);nodes.append(n)
 c={**base['content'],'schemaVersion':'0.7.0','semanticModelVersion':'0.8.0','requiredFeatures':list(FEATURES),'nodes':sorted(nodes,key=lambda n:n['id'])};return {'content':c,'contentDigest':digest(c,'canonical')}
def validate_snapshot(snapshot):
 check(Draft202012Validator(json.loads((CONTRACTS/'canonical-0.7.schema.json').read_bytes())).is_valid(snapshot),'CANONICAL_SHAPE');check(normalize_candidate(authoring(snapshot))==snapshot,'NORMAL_FORM');return snapshot
def document_snapshot(snapshot):validate_snapshot(snapshot);return parent.normalize_candidate(document_source(authoring(snapshot)))
def admit(snapshot,authority=None):
 validate_snapshot(snapshot);body=canonical_bytes(snapshot['content'])
 try:ok=authority is not None and authority({'applicationId':snapshot['content']['applicationId'],'contentDigest':snapshot['contentDigest'],'contentBytes':body}) is True
 except Exception:ok=False
 check(ok,'AUTHORITY');return AdmittedSnapshot(body,snapshot['contentDigest'])
def diagnostics(source,mode='compile'):
 try:validate_source(source);return []
 except (ValueError,KeyError,TypeError) as e:return [{'subject':'JOB-PREVIEW','code':getattr(e,'code','JOB_SHAPE'),'message':str(e)}]
