"""Versioned reporting meaning and validation; structural validity is not acceptance."""
import copy,json
from engineering.native_create import semantics as parent
from engineering.reporting.schema import CONTRACTS,FEATURES,KINDS
from jsonschema import Draft202012Validator
from canonical_json import canonical_bytes,digest
from canonical_ir import CanonicalError,AdmittedSnapshot

def check(ok,code):
 if not ok:raise CanonicalError('REPORT-'+code,code)
def authoring(snapshot):
 c=snapshot['content'];return {'modelVersion':'0.6.0','applicationId':c['applicationId'],'snapshotId':'REPORT-PREVIEW','nodes':copy.deepcopy(c['nodes']),'issues':copy.deepcopy(c['issues']),'approvals':[]}
def create_source(source):return {**copy.deepcopy(source),'modelVersion':'0.5.0','nodes':[copy.deepcopy(n) for n in source['nodes'] if n['kind'] not in KINDS]}
def validate_source(source):
 shape=json.loads((CONTRACTS/'authoring-0.6.schema.json').read_bytes());check(Draft202012Validator(shape).is_valid(source),'SHAPE_VERSION')
 parent.validate_source(create_source(source));nodes={n['id']:n for n in source['nodes']};check(len(nodes)==len(source['nodes']),'DUPLICATE_ID')
 def get(r,kind):
  check(type(r) is dict and r['id'] in nodes,'REFERENCE');n=nodes[r['id']];check(n['kind']==kind and n['revision']==r['revision'],'REFERENCE_KIND_REVISION');return n
 def ref(n):return {'id':n['id'],'revision':n['revision']}
 for n in nodes.values():
  if n['kind'] not in KINDS:continue
  check(n['lifecycle']=='APPROVED','STRUCTURAL_ELIGIBILITY')
  for b in n['basis']:check(b['id'] in nodes and nodes[b['id']]['revision']==b['revision'],'BASIS')
  d=n['data']
  if n['kind']=='ReportDefinition':
   entity=get(d['resource'],'Entity');check(entity['data']['tenancy']=='SCOPED' and len(entity['data']['identity'])==1,'RESOURCE_SCOPE')
   selected=set()
   for f in d['fields']:
    field=get(f['field'],'Field');fd=field['data'];check(fd['owner']==ref(entity) and field['id'] not in selected,'FIELD_OWNER_DUPLICATE');selected.add(field['id'])
    check(fd['classification'] in {'PUBLIC','INTERNAL'},'SENSITIVE_PROJECTION')
    t=fd['type']
    if f['member'] is not None:
     member=get(f['member'],'Field');check(t['kind']=='Value' and member['data']['owner']==t['definition'],'VALUE_MEMBER')
     check(member['data']['classification'] in {'PUBLIC','INTERNAL'},'SENSITIVE_MEMBER');t=member['data']['type']
     check(len([x for x in nodes.values() if x['kind']=='Field' and x['data']['owner']==member['data']['owner']])==1,'VALUE_MEMBERS')
    check(t['kind'] in {'String','Identifier'},'PROJECTION_TYPE')
   names=set()
   for f in d['filters']:
    check(f['name'] not in names and f['name'] not in {'tenant','subject','resourceId','sql'},'FILTER_NAME');names.add(f['name'])
    if f['type']=='STATE':check(f['field'] is None and f['operation']=='EQ','STATE_FILTER')
    else:
     field=get(f['field'],'Field');check(field['id'] in selected and field['data']['type']=={'kind':'String'} and f['operation'] in {'EQ','CONTAINS'},'FILTER_FIELD_TYPE')
   check(len({o['field'] for o in d['orderBy']})==len(d['orderBy']) and all(o['field'] in selected|{'STATE','IDENTITY'} for o in d['orderBy']),'SORT')
   check(d['pagination']['defaultSize']<=d['pagination']['maximumSize'],'PAGINATION')
   check(get(d['permission'],'ReportPermission')['data']['report']==ref(n),'PERMISSION')
   check(get(d['auditHistory'],'AuditHistory')['data']['report']==ref(n),'HISTORY')
  elif n['kind']=='ReportPermission':
   report=get(d['report'],'ReportDefinition');entity=get(report['data']['resource'],'Entity');actor=get(d['actor'],'Actor');get(d['role'],'Role');scope=get(d['scope'],'Scope');field=get(d['principalField'],'Field')
   check(scope['data']['actor']==ref(actor) and scope['data']['resource']==ref(entity) and scope['data']['resourceTenant']==entity['data']['tenantField'],'AUTHORIZATION_SCOPE')
   check(field['data']['owner']==ref(entity) and field['data']['type']=={'kind':'Identifier','entity':actor['data']['subject']},'OWNER_BINDING')
   if d['access']=='REPORT':check(report['data']['permission']==ref(n),'REPORT_PERMISSION')
   else:check(get(report['data']['auditHistory'],'AuditHistory')['data']['permission']==ref(n),'AUDIT_PERMISSION')
  elif n['kind']=='AuditHistory':
   report=get(d['report'],'ReportDefinition');permission=get(d['permission'],'ReportPermission');check(permission['data']['access']=='AUDIT' and permission['data']['report']==ref(report),'AUDIT_GRANT')
   for r in d['operations']:
    check(r['id'] in nodes and nodes[r['id']]['revision']==r['revision'],'AUDIT_OPERATION')
    op=nodes[r['id']]
    check(op['kind'] in {'CreateOperation','Command'},'AUDIT_OPERATION_KIND')
    if op['kind']=='CreateOperation':resource=op['data']['resource']
    else:
     resources={json.dumps(p['data']['resource'],sort_keys=True) for p in nodes.values() if p['kind']=='Permission' and p['data']['action']==r}
     check(resources=={json.dumps(report['data']['resource'],sort_keys=True)},'AUDIT_RESOURCE');resource=report['data']['resource']
    check(resource==report['data']['resource'],'AUDIT_RESOURCE')
  else:
   report=get(d['report'],'ReportDefinition');get(d['screen'],'Screen');check(d['permission']==report['data']['permission'],'VIEW_PERMISSION')
   check(d['columns']==[f['field'] for f in report['data']['fields']] and d['filters']==[f['name'] for f in report['data']['filters']],'VIEW_OUTPUT')
 return source

def normalize_candidate(source):
 validate_source(source);base=parent.normalize_candidate(create_source(source));nodes=base['content']['nodes']
 for n in source['nodes']:
  if n['kind'] in KINDS:
   n=copy.deepcopy(n);n['basis']=sorted(n['basis'],key=canonical_bytes);n['origins']=sorted(n['origins'],key=canonical_bytes)
   if n['kind']=='AuditHistory':n['data']['operations']=sorted(n['data']['operations'],key=canonical_bytes)
   nodes.append(n)
 content={**base['content'],'schemaVersion':'0.5.0','semanticModelVersion':'0.6.0','requiredFeatures':list(FEATURES),'nodes':sorted(nodes,key=lambda n:n['id'])}
 return {'content':content,'contentDigest':digest(content,'canonical')}
def validate_snapshot(snapshot):
 check(Draft202012Validator(json.loads((CONTRACTS/'canonical-0.5.schema.json').read_bytes())).is_valid(snapshot),'CANONICAL_SHAPE')
 check(normalize_candidate(authoring(snapshot))==snapshot,'CANONICAL_NORMAL_FORM');return snapshot
def admit(snapshot,authority=None):
 validate_snapshot(snapshot);body=canonical_bytes(snapshot['content']);q={'applicationId':snapshot['content']['applicationId'],'contentDigest':snapshot['contentDigest'],'contentBytes':body}
 try:allowed=authority is not None and authority(q) is True
 except Exception:allowed=False
 check(allowed,'AUTHORITY');return AdmittedSnapshot(body,snapshot['contentDigest'])
def create_snapshot(snapshot):
 validate_snapshot(snapshot);return parent.normalize_candidate(create_source(authoring(snapshot)))
def diagnostics(source,mode='compile'):
 try:validate_source(source);return []
 except (CanonicalError,KeyError,TypeError,ValueError) as e:return [{'subject':next(iter(source.get('nodes',[{'id':'UNKNOWN'}])))['id'],'code':getattr(e,'code','REPORT_SHAPE'),'message':str(e)}]
