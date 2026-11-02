"""Native CREATE validation/canonicalization, exact version and no acceptance authority."""
import copy,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from jsonschema import Draft202012Validator
from canonical_json import canonical_bytes,digest,PROFILE
from canonical_ir import CanonicalError,AdmittedSnapshot,normalize_candidate as normalize_legacy,validate_snapshot as validate_legacy
from engineering.native_create.schema import FEATURE,KINDS,CONTRACTS

def check(ok,code):
 if not ok:raise CanonicalError('CREATE-'+code,code)

def authoring(snapshot):
 c=snapshot['content'];return {'modelVersion':'0.5.0','applicationId':c['applicationId'],'snapshotId':'NATIVE-CREATE-PREVIEW','nodes':copy.deepcopy(c['nodes']),'issues':copy.deepcopy(c['issues']),'approvals':[]}
def legacy_source(source):
 nodes=[n for n in source['nodes'] if n['kind'] not in KINDS]
 # Internal compile-eligibility witnesses, NEVER persisted proofs or human grants.
 return {**source,'modelVersion':'0.4.0','nodes':nodes,'approvals':[{'subject':{'id':n['id'],'revision':n['revision']},'reviewer':'structural-only','evidence':'not-authority'} for n in nodes]}
def validate_source(source):
 schema=json.loads((CONTRACTS/'authoring-0.5.schema.json').read_bytes());check(Draft202012Validator(schema).is_valid(source),'SHAPE_OR_VERSION')
 normalize_legacy(legacy_source(source));nodes={n['id']:n for n in source['nodes']};check(len(nodes)==len(source['nodes']),'DUPLICATE_ID')
 def get(r,kind):
  check(type(r) is dict and r.get('id') in nodes,'REFERENCE');n=nodes[r['id']];check(n['revision']==r['revision'] and n['kind']==kind,'REFERENCE_KIND_REVISION');return n
 def r(n):return {'id':n['id'],'revision':n['revision']}
 for n in nodes.values():
  if n['kind'] not in KINDS:continue
  check(n['lifecycle']=='APPROVED','ACTIVE_CANDIDATE');d=n['data']
  for b in n['basis']:check(b['id'] in nodes and nodes[b['id']]['revision']==b['revision'],'BASIS')
  if n['kind']=='CreateOperation':
   entity=get(d['resource'],'Entity');ed=entity['data'];check(ed['tenancy']=='SCOPED','SCOPED_ENTITY_ONLY')
   check(ed['identity']==[d['identity']] and ed['tenantField']==d['tenant'],'IDENTITY_TENANT')
   fields={f['id']:f for f in nodes.values() if f['kind']=='Field' and f['data']['owner']==r(entity)};check(set(fields)==set(d['bindings']),'FIELD_COVERAGE')
   names=set()
   for id,b in d['bindings'].items():
    f=fields[id]['data'];kind=b['kind']
    if kind=='ABSENT':check(f['optional'],'REQUIRED_FIELD_ABSENT')
    elif kind=='INPUT':
     check(b['name'] not in names and b['name']!='idempotencyKey','INPUT_NAME');names.add(b['name']);check(b['minimumLength']<=b['maximumLength'],'INPUT_LENGTH')
     t=f['type']
     if b['member'] is not None:
      member=get(b['member'],'Field');check(t['kind']=='Value' and member['data']['owner']==t['definition'],'VALUE_BINDING');t=member['data']['type']
      check([x['id'] for x in nodes.values() if x['kind']=='Field' and x['data']['owner']==member['data']['owner']]==[member['id']],'VALUE_MEMBERS')
     check(b['type']==t and t['kind'] in {'String','Identifier'},'INPUT_TYPE')
    else:
     check(kind in {'GENERATED_UUID','AUTHENTICATED_TENANT','AUTHENTICATED_SUBJECT'},'BINDING')
     if kind=='GENERATED_UUID':check(id==d['identity']['id'] and f['type']=={'kind':'Identifier','entity':r(entity)},'GENERATED_IDENTITY_ONLY')
   check(d['bindings'][d['identity']['id']]['kind'] in {'GENERATED_UUID','INPUT'},'IDENTITY_BINDING')
   check(d['bindings'][d['tenant']['id']]['kind']=='AUTHENTICATED_TENANT','TENANT_SPOOFING')
   check(d['bindings'][d['principal']['id']]['kind']=='AUTHENTICATED_SUBJECT','ASSIGNMENT_SPOOFING')
   check([id for id,b in d['bindings'].items() if b['kind']=='AUTHENTICATED_TENANT']==[d['tenant']['id']],'TENANT_BINDING_COUNT')
   check([id for id,b in d['bindings'].items() if b['kind']=='AUTHENTICATED_SUBJECT']==[d['principal']['id']],'PRINCIPAL_BINDING_COUNT')
   state=get(d['initialState'],'State');check(any(m['kind']=='StateMachine' and m['data']['resource']==r(entity) and m['data']['initial']==r(state) for m in nodes.values()),'INITIAL_STATE')
   permission=get(d['permission'],'CreatePermission');check(permission['data']['operation']==r(n),'PERMISSION_ACTION')
  elif n['kind']=='CreatePermission':
   op=get(d['operation'],'CreateOperation');actor=get(d['actor'],'Actor');get(d['role'],'Role');scope=get(d['scope'],'Scope')
   check(op['data']['permission']==r(n) and scope['data']['resourceTenant']==op['data']['tenant'],'PERMISSION_SCOPE')
   principal=get(op['data']['principal'],'Field');check(principal['data']['type']=={'kind':'Identifier','entity':actor['data']['subject']},'PRINCIPAL_ACTOR')
   check(get(scope['data']['actorTenant'],'Field')['data']['owner']==actor['data']['subject'],'ACTOR_TENANT_SCOPE')
  else:
   op=get(d['operation'],'CreateOperation');get(d['screen'],'Screen');check(d['permission']==op['data']['permission'],'FORM_PERMISSION')
   check(set(d['controls'])=={b['name'] for b in op['data']['bindings'].values() if b['kind']=='INPUT'},'FORM_INPUTS')
 return source

def normalize_candidate(source):
 validate_source(source);base=normalize_legacy(legacy_source(source));nodes=base['content']['nodes']
 for n in source['nodes']:
  if n['kind'] in KINDS:
   n=copy.deepcopy(n);n['basis']=sorted(n['basis'],key=canonical_bytes);n['origins']=sorted(n['origins'],key=canonical_bytes)
   if n['kind']=='CreateOperation':n['data']['outcomes']=sorted(n['data']['outcomes'])
   nodes.append(n)
 content={**base['content'],'schemaVersion':'0.4.0','semanticModelVersion':'0.5.0','requiredFeatures':[FEATURE],'nodes':sorted(nodes,key=lambda n:n['id'])}
 return {'content':content,'contentDigest':digest(content,'canonical')}
def validate_snapshot(snapshot):
 schema=json.loads((CONTRACTS/'canonical-0.4.schema.json').read_bytes());check(Draft202012Validator(schema).is_valid(snapshot),'CANONICAL_SHAPE_VERSION_FEATURE')
 check(normalize_candidate(authoring(snapshot))==snapshot,'CANONICAL_NORMAL_FORM_DIGEST');return snapshot

def admit(snapshot,authority=None):
 validate_snapshot(snapshot);body=canonical_bytes(snapshot['content']);q={'applicationId':snapshot['content']['applicationId'],'contentDigest':snapshot['contentDigest'],'contentBytes':body}
 try:allowed=authority is not None and authority(q) is True
 except Exception:allowed=False
 check(allowed,'AUTHORITY');return AdmittedSnapshot(body,snapshot['contentDigest'])

def legacy_snapshot(snapshot):
 validate_snapshot(snapshot);return normalize_legacy(legacy_source(authoring(snapshot)))

def diagnostics(source,mode='compile'):
 try:validate_source(source);return []
 except (CanonicalError,KeyError,TypeError,ValueError) as e:return [{'subject':source.get('nodes',[{}])[0].get('id','UNKNOWN'),'code':getattr(e,'code','CREATE_SHAPE'),'message':str(e)}]
