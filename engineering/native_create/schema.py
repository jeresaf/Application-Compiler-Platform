"""Versioned additive schemas; frozen root 0.3/0.4 contracts are read-only."""
import copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CONTRACTS=Path(__file__).resolve().parent/'contracts'
FEATURE='acp.native-create/1'
KINDS={'CreateOperation','CreatePermission','CreateForm'}
def obj(properties):return {'type':'object','additionalProperties':False,'required':list(properties),'properties':properties}
def const(value):return {'const':value}
def ref():return {'$ref':'#/$defs/ref'}
def enum(*values):return {'enum':list(values)}
def schemas():
 a=json.loads((ROOT/'contracts/authoring-0.4.schema.json').read_bytes());c=json.loads((ROOT/'contracts/canonical-0.3.schema.json').read_bytes())
 binding={'oneOf':[obj({'kind':const(k)}) for k in ('GENERATED_UUID','AUTHENTICATED_TENANT','AUTHENTICATED_SUBJECT','ABSENT')]+[obj({'kind':const('INPUT'),'name':{'type':'string','pattern':'^[a-zA-Z][a-zA-Z0-9_]{0,63}$'},'type':{'$ref':'#/$defs/semanticType'},'member':{'anyOf':[ref(),{'type':'null'}]},'minimumLength':{'type':'integer','minimum':1,'maximum':2000},'maximumLength':{'type':'integer','minimum':1,'maximum':2000}})]}
 defs={'CreateOperation':obj({'resource':ref(),'identity':ref(),'tenant':ref(),'principal':ref(),'permission':ref(),'initialState':ref(),'bindings':{'type':'object','minProperties':1,'additionalProperties':binding},'idempotency':obj({'scope':const('ACTOR_TENANT_OPERATION_KEY'),'windowSeconds':{'type':'integer','minimum':1,'maximum':3600},'replay':const('SAME_INPUT_ONLY'),'concurrency':const('ONE_COMMITTED_CREATION')}),'rate':obj({'algorithm':const('TOKEN_BUCKET_CONTINUOUS_RATIONAL'),'partition':const('ACTOR_TENANT'),'requests':{'type':'integer','minimum':1,'maximum':1000},'windowSeconds':{'type':'integer','minimum':1,'maximum':3600},'burst':{'type':'integer','minimum':1,'maximum':1000}}),'audit':const('REQUIRED'),'events':{'type':'array','maxItems':0},'outcomes':{'type':'array','uniqueItems':True,'items':enum('INVALID_INPUT','UNAUTHORIZED','IDENTITY_CONFLICT','IDEMPOTENCY_CONFLICT','IN_PROGRESS','RATE_DENIED','INTERNAL'),'minItems':7,'maxItems':7}}),
 'CreatePermission':obj({'operation':ref(),'actor':ref(),'role':ref(),'scope':ref(),'effect':const('ALLOW'),'tenantRule':const('AUTHENTICATED_TENANT'),'principalRule':const('AUTHENTICATED_SUBJECT')}),
 'CreateForm':obj({'operation':ref(),'screen':ref(),'permission':ref(),'controls':{'type':'array','items':{'type':'string'},'minItems':1,'uniqueItems':True},'states':const(['IDLE','SUBMITTING','SUCCESS','FAILURE']),'existingResourceSelection':const(False)})}
 for s in (a,c):
  s['$defs'].update(copy.deepcopy(defs));node=s['$defs']['node'];node['properties']['kind']['enum']+=sorted(KINDS)
  for k in sorted(KINDS):node['allOf'].append({'if':{'properties':{'kind':const(k)}},'then':{'properties':{'data':{'$ref':'#/$defs/'+k}}}})
 a['$id']='https://acp.invalid/authoring-0.5';a['properties']['modelVersion']=const('0.5.0')
 c['$id']='https://acp.invalid/canonical-0.4';content=c['$defs']['content']['properties'];content['schemaVersion']=const('0.4.0');content['semanticModelVersion']=const('0.5.0');content['requiredFeatures']=const([FEATURE])
 return a,c
if __name__=='__main__':
 for name,s in zip(('authoring-0.5.schema.json','canonical-0.4.schema.json'),schemas()):(CONTRACTS/name).write_text(json.dumps(s,sort_keys=True,separators=(',',':'))+'\n')
