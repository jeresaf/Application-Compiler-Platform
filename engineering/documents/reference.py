"""Unapproved R6 synthetic reference; every R0–R5 node is preserved."""
from engineering.reporting.reference import proposal as parent

def proposal():
 s=parent();s['modelVersion']='0.7.0';nodes={n['id']:n for n in s['nodes']}
 def ref(i):return {'id':i,'revision':nodes[i]['revision'] if i in nodes else 1}
 def add(i,k,d,basis=('REQ-R6-DOCUMENTS',)):
  s['nodes'].append({'id':i,'revision':1,'kind':k,'name':'PROPOSED '+i,'lifecycle':'APPROVED','steward':'assistant:proposal','origins':[{'source':'proposal:phase10-r6-documents','locator':i,'actor':'assistant:proposal','actorType':'AI'}],'basis':[ref(b) for b in basis],'data':d})
 add('REQ-R6-DOCUMENTS','Requirement',{'statement':'PROPOSED owner/tenant scoped transactional document upload, metadata and exact-byte download, bounded safe text policy, auditable resource-scoped idempotency and persistence. No public sharing or production acceptance.','priority':'MUST','acceptance':[ref('AC-R6-DOCUMENTS')]},())
 add('AC-R6-DOCUMENTS','AcceptanceCriterion',{'requirement':ref('REQ-R6-DOCUMENTS'),'scenario':'Real generated upload/list/metadata/download preserve exact bytes and SHA256 across restart and regeneration; reject unauthorized, cross-tenant, malformed, oversized, unsupported, corrupted and conflicting requests; concurrent retries create one document and one upload audit; failed audit rolls back metadata and content.'})
 add('DOC-ATTACHMENTS','DocumentDefinition',{'resource':ref('CASE'),'identity':'SERVER_UUID','tenantRule':'AUTHENTICATED_TENANT','metadata':['filename','mediaType','size','sha256','createdAt'],'classification':'INTERNAL','contentIdentity':'SHA256_EXACT_BYTES','mediaTypes':['text/plain'],'contentValidation':'STRICT_UTF8_TEXT_NO_NUL','maximumBytes':65536,'storage':'TRANSACTIONAL_BINARY','association':'EXACT_AUTHORIZED_RESOURCE','uploadPermission':ref('PERM-DOC-UPLOAD'),'readPermission':ref('PERM-DOC-READ'),'audit':'UPLOAD_AND_DOWNLOAD','idempotency':'RESOURCE_SCOPED_EXACT_REQUEST','retrieval':'ATTACHMENT_NO_SNIFF_NO_STORE','filenamePolicy':'SAFE_BASENAME_TXT','resourceIdentityPolicy':'ASCII_TOKEN_128','sharing':'FORBIDDEN'})
 for i,access in [('PERM-DOC-UPLOAD','UPLOAD'),('PERM-DOC-READ','READ')]:add(i,'DocumentPermission',{'document':ref('DOC-ATTACHMENTS'),'access':access,'actor':ref('ACT-REVIEWER'),'role':ref('ROLE-REVIEWER'),'scope':ref('SCOPE-CASE'),'principalField':ref('CASE-ASSIGNEE'),'effect':'ALLOW','resourceRule':'AUTHENTICATED_OWNER'})
 add('VIEW-DOCUMENTS','DocumentView',{'document':ref('DOC-ATTACHMENTS'),'screen':ref(next(n['id'] for n in s['nodes'] if n['kind']=='Screen')),'uploadPermission':ref('PERM-DOC-UPLOAD'),'readPermission':ref('PERM-DOC-READ'),'presentation':'RESOURCE_ATTACHMENTS','states':['LOADING','EMPTY','READY','UPLOADING','ERROR']})
 return s
