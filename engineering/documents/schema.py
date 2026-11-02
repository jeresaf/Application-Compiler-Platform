"""Closed document policy; binary transport/storage is not implied by Evidence."""
import copy,json
from pathlib import Path
from engineering.reporting.schema import schemas as parent_schemas,FEATURES as PARENT
from engineering.native_create.schema import obj,ref,const,enum
CONTRACTS=Path(__file__).parent/'contracts';FEATURE='acp.documents/1';FEATURES=tuple(sorted((*PARENT,FEATURE)))
KINDS=frozenset({'DocumentDefinition','DocumentPermission','DocumentView'})
def schemas():
 a,c=parent_schemas()
 definitions={
 'DocumentDefinition':obj({'resource':ref(),'identity':const('SERVER_UUID'),'tenantRule':const('AUTHENTICATED_TENANT'),'metadata':const(['filename','mediaType','size','sha256','createdAt']),'classification':const('INTERNAL'),'contentIdentity':const('SHA256_EXACT_BYTES'),'mediaTypes':const(['text/plain']),'contentValidation':const('STRICT_UTF8_TEXT_NO_NUL'),'maximumBytes':{'type':'integer','minimum':1,'maximum':65536},'storage':const('TRANSACTIONAL_BINARY'),'association':const('EXACT_AUTHORIZED_RESOURCE'),'uploadPermission':ref(),'readPermission':ref(),'audit':const('UPLOAD_AND_DOWNLOAD'),'idempotency':const('RESOURCE_SCOPED_EXACT_REQUEST'),'retrieval':const('ATTACHMENT_NO_SNIFF_NO_STORE'),'filenamePolicy':const('SAFE_BASENAME_TXT'),'resourceIdentityPolicy':const('ASCII_TOKEN_128'),'sharing':const('FORBIDDEN')}),
 'DocumentPermission':obj({'document':ref(),'access':enum('UPLOAD','READ'),'actor':ref(),'role':ref(),'scope':ref(),'principalField':ref(),'effect':const('ALLOW'),'resourceRule':const('AUTHENTICATED_OWNER')}),
 'DocumentView':obj({'document':ref(),'screen':ref(),'uploadPermission':ref(),'readPermission':ref(),'presentation':const('RESOURCE_ATTACHMENTS'),'states':const(['LOADING','EMPTY','READY','UPLOADING','ERROR'])})}
 for s in (a,c):
  s['$defs'].update(copy.deepcopy(definitions));n=s['$defs']['node'];n['properties']['kind']['enum']+=sorted(KINDS)
  for k in sorted(KINDS):n['allOf'].append({'if':{'properties':{'kind':const(k)}},'then':{'properties':{'data':{'$ref':'#/$defs/'+k}}}})
 a['$id']='https://acp.invalid/authoring-0.7';a['properties']['modelVersion']=const('0.7.0');c['$id']='https://acp.invalid/canonical-0.6';c['$defs']['content']['properties'].update(schemaVersion=const('0.6.0'),semanticModelVersion=const('0.7.0'),requiredFeatures=const(list(FEATURES)))
 return a,c
if __name__=='__main__':
 for name,s in zip(('authoring-0.7.schema.json','canonical-0.6.schema.json'),schemas()):(CONTRACTS/name).write_text(json.dumps(s,sort_keys=True,separators=(',',':'))+'\n')
