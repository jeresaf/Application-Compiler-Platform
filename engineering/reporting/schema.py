"""Closed reporting extension; no change to prior schema meanings."""
import copy,json
from pathlib import Path
from engineering.native_create.schema import schemas as create_schemas,obj,ref,const,enum,FEATURE as CREATE
CONTRACTS=Path(__file__).parent/'contracts'
FEATURE='acp.reporting/1'
FEATURES=tuple(sorted((CREATE,FEATURE)))
KINDS=frozenset({'ReportDefinition','ReportPermission','ReportView','AuditHistory'})
def schemas():
 a,c=create_schemas()
 defs={
 'ReportDefinition':obj({'resource':ref(),'fields':{'type':'array','minItems':1,'maxItems':12,'uniqueItems':True,'items':obj({'field':ref(),'member':{'anyOf':[ref(),{'type':'null'}]}})},'filters':{'type':'array','minItems':1,'maxItems':8,'items':obj({'name':{'type':'string','pattern':'^[a-z][a-zA-Z0-9]{0,31}$'},'field':{'anyOf':[ref(),{'type':'null'}]},'type':enum('STRING','STATE'),'operation':enum('EQ','CONTAINS')})},'orderBy':{'type':'array','minItems':1,'maxItems':4,'items':obj({'field':{'type':'string'},'direction':enum('ASC','DESC')})},'pagination':obj({'defaultSize':{'type':'integer','minimum':1,'maximum':50},'maximumSize':{'type':'integer','minimum':1,'maximum':50},'maximumPage':{'type':'integer','minimum':0,'maximum':10000}}),'groupBy':const('WORKFLOW_STATE'),'aggregations':const(['COUNT']),'permission':ref(),'auditHistory':ref(),'output':const('PROJECTED_FIELDS_IDENTITY_VERSION_STATE'),'mutation':const('FORBIDDEN'),'export':const('NOT_GRANTED')}),
 'ReportPermission':obj({'report':ref(),'access':enum('REPORT','AUDIT'),'actor':ref(),'role':ref(),'scope':ref(),'principalField':ref(),'effect':const('ALLOW'),'tenantRule':const('AUTHENTICATED_TENANT'),'resourceRule':const('AUTHENTICATED_OWNER'),'fieldLevels':const(['PUBLIC','INTERNAL'])}),
 'AuditHistory':obj({'report':ref(),'permission':ref(),'operations':{'type':'array','minItems':1,'maxItems':20,'uniqueItems':True,'items':ref()},'projection':const(['operation','occurredAt']),'visibility':const('AUTHORIZED_RESOURCE_SCOPE'),'orderBy':const('OCCURRED_AT_ASC_ID_ASC')}),
 'ReportView':obj({'report':ref(),'permission':ref(),'screen':ref(),'presentation':const('TABLE_STATE_COUNTS_AUDIT'),'columns':{'type':'array','minItems':1,'uniqueItems':True,'items':ref()},'filters':{'type':'array','uniqueItems':True,'items':{'type':'string'}},'states':const(['LOADING','READY','EMPTY','ERROR'])})}
 for s in (a,c):
  s['$defs'].update(copy.deepcopy(defs));node=s['$defs']['node'];node['properties']['kind']['enum']+=sorted(KINDS)
  for k in sorted(KINDS):node['allOf'].append({'if':{'properties':{'kind':const(k)}},'then':{'properties':{'data':{'$ref':'#/$defs/'+k}}}})
 a['$id']='https://acp.invalid/authoring-0.6';a['properties']['modelVersion']=const('0.6.0')
 c['$id']='https://acp.invalid/canonical-0.5';p=c['$defs']['content']['properties'];p.update(schemaVersion=const('0.5.0'),semanticModelVersion=const('0.6.0'),requiredFeatures=const(list(FEATURES)))
 return a,c
if __name__=='__main__':
 for name,s in zip(('authoring-0.6.schema.json','canonical-0.5.schema.json'),schemas()):(CONTRACTS/name).write_text(json.dumps(s,sort_keys=True,separators=(',',':'))+'\n')
