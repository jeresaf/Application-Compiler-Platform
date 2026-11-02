"""Service-authorized background operation; historical interactive Job is unchanged."""
import copy,json
from pathlib import Path
from engineering.documents.schema import schemas as parent_schemas,FEATURES as PARENT
from engineering.native_create.schema import obj,ref,const,enum
CONTRACTS=Path(__file__).parent/'contracts';FEATURE='acp.background-jobs/1';FEATURES=tuple(sorted((*PARENT,FEATURE)));KINDS=frozenset({'IntegrityJob','WorkerGrant','JobReadPermission','JobView'})
def schemas():
 a,c=parent_schemas();defs={
 'IntegrityJob':obj({'document':ref(),'operation':const('VERIFY_DOCUMENT_SHA256'),'schedule':ref(),'retry':ref(),'worker':ref(),'readPermission':ref(),'timeoutSeconds':{'type':'integer','minimum':1,'maximum':10},'leaseSeconds':{'type':'integer','minimum':2,'maximum':30},'maximumDocuments':{'type':'integer','minimum':1,'maximum':20},'missedOccurrences':const('SKIP'),'catchUp':const(None),'effectIdentity':const('JOB_TENANT_OCCURRENCE_DOCUMENT'),'execution':const('AT_LEAST_ONCE_FENCED_COMMIT'),'manualTrigger':const('FORBIDDEN'),'failureDisposition':const('INTEGRITY_TERMINAL_TRANSIENT_BOUNDED_RETRY'),'contentMutation':const('FORBIDDEN')}),
 'WorkerGrant':obj({'job':ref(),'identity':{'type':'string','pattern':'^service:[a-z][a-z0-9-]{0,63}$'},'tenants':{'type':'array','minItems':1,'maxItems':8,'uniqueItems':True,'items':{'type':'string','pattern':'^[a-z][a-z0-9-]{0,63}$'}},'scope':const('ALL_DOCUMENTS_OF_RESOURCE_IN_TENANT'),'privileges':const(['READ_CONTENT','WRITE_INTEGRITY_RESULT','APPEND_JOB_AUDIT']),'binding':const('EXPLICIT_HOST_SERVICE_CONTEXT_NO_USER_JWT')}),
 'JobReadPermission':obj({'job':ref(),'actor':ref(),'role':ref(),'scope':ref(),'principalField':ref(),'effect':const('ALLOW'),'resourceRule':const('AUTHENTICATED_OWNER')}),
 'JobView':obj({'job':ref(),'screen':ref(),'permission':ref(),'presentation':const('READ_ONLY_JOB_RESULTS'),'states':const(['PENDING','RUNNING','RETRY','COMPLETED','FAILED'])})}
 for s in (a,c):
  s['$defs'].update(copy.deepcopy(defs));n=s['$defs']['node'];n['properties']['kind']['enum']+=sorted(KINDS)
  for k in sorted(KINDS):n['allOf'].append({'if':{'properties':{'kind':const(k)}},'then':{'properties':{'data':{'$ref':'#/$defs/'+k}}}})
 a['$id']='https://acp.invalid/authoring-0.8';a['properties']['modelVersion']=const('0.8.0');c['$id']='https://acp.invalid/canonical-0.7';c['$defs']['content']['properties'].update(schemaVersion=const('0.7.0'),semanticModelVersion=const('0.8.0'),requiredFeatures=const(list(FEATURES)));return a,c
if __name__=='__main__':
 for name,s in zip(('authoring-0.8.schema.json','canonical-0.7.schema.json'),schemas()):(CONTRACTS/name).write_text(json.dumps(s,sort_keys=True,separators=(',',':'))+'\n')
