"""Proposed document semantics. Validation never grants human approval."""
import copy,json
from engineering.reporting import semantics as parent
from engineering.documents.schema import CONTRACTS,FEATURES,KINDS
from jsonschema import Draft202012Validator
from canonical_json import canonical_bytes,digest
from canonical_ir import CanonicalError,AdmittedSnapshot

def check(ok,code):
 if not ok:raise CanonicalError('DOCUMENT-'+code,code)
def authoring(snapshot):
 c=snapshot['content'];return {'modelVersion':'0.7.0','applicationId':c['applicationId'],'snapshotId':'DOCUMENT-PREVIEW','nodes':copy.deepcopy(c['nodes']),'issues':copy.deepcopy(c['issues']),'approvals':[]}
def reporting_source(source):return {**copy.deepcopy(source),'modelVersion':'0.6.0','nodes':[copy.deepcopy(n) for n in source['nodes'] if n['kind'] not in KINDS]}
def validate_source(source):
 check(Draft202012Validator(json.loads((CONTRACTS/'authoring-0.7.schema.json').read_bytes())).is_valid(source),'SHAPE')
 parent.validate_source(reporting_source(source));nodes={n['id']:n for n in source['nodes']};check(len(nodes)==len(source['nodes']),'DUPLICATE')
 def ref(n):return {'id':n['id'],'revision':n['revision']}
 def get(r,k):
  check(r['id'] in nodes,'REFERENCE');n=nodes[r['id']];check(n['kind']==k and n['revision']==r['revision'],'REFERENCE_REVISION');return n
 for n in nodes.values():
  if n['kind'] not in KINDS:continue
  check(n['lifecycle']=='APPROVED','STRUCTURAL_ELIGIBILITY')
  for r in n['basis']:check(r['id'] in nodes and nodes[r['id']]['revision']==r['revision'],'BASIS')
  d=n['data']
  if n['kind']=='DocumentDefinition':
   e=get(d['resource'],'Entity');check(e['data']['tenancy']=='SCOPED' and len(e['data']['identity'])==1,'RESOURCE')
   for key,access in [('uploadPermission','UPLOAD'),('readPermission','READ')]:
    p=get(d[key],'DocumentPermission');check(p['data']['document']==ref(n) and p['data']['access']==access,'PERMISSION')
  elif n['kind']=='DocumentPermission':
   doc=get(d['document'],'DocumentDefinition');e=get(doc['data']['resource'],'Entity');actor=get(d['actor'],'Actor');get(d['role'],'Role');scope=get(d['scope'],'Scope');field=get(d['principalField'],'Field')
   check(scope['data']['actor']==ref(actor) and scope['data']['resource']==ref(e) and scope['data']['resourceTenant']==e['data']['tenantField'],'SCOPE')
   check(field['data']['owner']==ref(e) and field['data']['type']=={'kind':'Identifier','entity':actor['data']['subject']},'OWNER')
   check(doc['data']['uploadPermission' if d['access']=='UPLOAD' else 'readPermission']==ref(n),'BINDING')
  else:
   doc=get(d['document'],'DocumentDefinition');get(d['screen'],'Screen');check(all(d[k]==doc['data'][k] for k in ('uploadPermission','readPermission')),'VIEW')
 return source
def normalize_candidate(source):
 validate_source(source);base=parent.normalize_candidate(reporting_source(source));nodes=base['content']['nodes']
 for n in source['nodes']:
  if n['kind'] in KINDS:
   n=copy.deepcopy(n);n['basis']=sorted(n['basis'],key=canonical_bytes);n['origins']=sorted(n['origins'],key=canonical_bytes);nodes.append(n)
 c={**base['content'],'schemaVersion':'0.6.0','semanticModelVersion':'0.7.0','requiredFeatures':list(FEATURES),'nodes':sorted(nodes,key=lambda n:n['id'])};return {'content':c,'contentDigest':digest(c,'canonical')}
def validate_snapshot(snapshot):
 check(Draft202012Validator(json.loads((CONTRACTS/'canonical-0.6.schema.json').read_bytes())).is_valid(snapshot),'CANONICAL_SHAPE');check(normalize_candidate(authoring(snapshot))==snapshot,'NORMAL_FORM');return snapshot
def reporting_snapshot(snapshot):validate_snapshot(snapshot);return parent.normalize_candidate(reporting_source(authoring(snapshot)))
def admit(snapshot,authority=None):
 validate_snapshot(snapshot);body=canonical_bytes(snapshot['content'])
 try:allowed=authority is not None and authority({'applicationId':snapshot['content']['applicationId'],'contentDigest':snapshot['contentDigest'],'contentBytes':body}) is True
 except Exception:allowed=False
 check(allowed,'AUTHORITY');return AdmittedSnapshot(body,snapshot['contentDigest'])
def diagnostics(source,mode='compile'):
 try:validate_source(source);return []
 except (CanonicalError,KeyError,TypeError,ValueError) as e:return [{'subject':'DOCUMENT-PREVIEW','code':getattr(e,'code','DOCUMENT_SHAPE'),'message':str(e)}]
