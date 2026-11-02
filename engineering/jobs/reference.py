"""Proposed service authority and document-integrity operation, not accepted intent."""
from engineering.documents.reference import proposal as parent

def proposal():
 s=parent();s['modelVersion']='0.8.0';nodes={n['id']:n for n in s['nodes']}
 def ref(i):return {'id':i,'revision':nodes[i]['revision'] if i in nodes else 1}
 def add(i,k,d,basis=('REQ-R7-INTEGRITY',)):
  s['nodes'].append({'id':i,'revision':1,'kind':k,'name':'PROPOSED '+i,'lifecycle':'APPROVED','steward':'assistant:proposal','origins':[{'source':'proposal:phase10-r7-jobs','locator':i,'actor':'assistant:proposal','actorType':'AI'}],'basis':[ref(b) for b in basis],'data':d})
 add('REQ-R7-INTEGRITY','Requirement',{'statement':'PROPOSED durable scheduled document SHA256 verification with explicit tenant-bound service authority, fenced at-least-once attempts, deduplicated committed results and bounded recovery; never repair/delete content or fabricate interactive JWTs.','priority':'MUST','acceptance':[ref('AC-R7-INTEGRITY')]},())
 add('AC-R7-INTEGRITY','AcceptanceCriterion',{'requirement':ref('REQ-R7-INTEGRITY'),'scenario':'Actual generated workers verify stored bytes independently of HTTP; prove concurrent claims, bounded retries, lease expiry, stale token rejection, timeout, rollback, missing/corrupt input, tenant isolation and restart persistence. Read-only results require an explicit owner/role grant.'})
 add('SCHEDULE-INTEGRITY','Schedule',{'mode':'INTERVAL','intervalSeconds':3600,'anchorInstant':'2026-11-01T00:00:00Z'})
 add('FAIL-JOB-TIMEOUT','Failure',{'code':'EXECUTION_TIMEOUT','category':'TRANSIENT','retryable':True})
 add('RETRY-INTEGRITY','RetryPolicy',{'failures':[ref('FAIL-TRANSIENT'),ref('FAIL-JOB-TIMEOUT')],'maxAttempts':3,'initialSeconds':1,'maxDelaySeconds':2,'multiplier':2,'delayBasis':'AFTER_FAILURE_COMPLETION','jitter':'NONE','attemptCounting':'INCLUDING_INITIAL'})
 add('JOB-INTEGRITY','IntegrityJob',{'document':ref('DOC-ATTACHMENTS'),'operation':'VERIFY_DOCUMENT_SHA256','schedule':ref('SCHEDULE-INTEGRITY'),'retry':ref('RETRY-INTEGRITY'),'worker':ref('WORKER-INTEGRITY'),'readPermission':ref('PERM-JOB-READ'),'timeoutSeconds':2,'leaseSeconds':4,'maximumDocuments':20,'missedOccurrences':'SKIP','catchUp':None,'effectIdentity':'JOB_TENANT_OCCURRENCE_DOCUMENT','execution':'AT_LEAST_ONCE_FENCED_COMMIT','manualTrigger':'FORBIDDEN','failureDisposition':'INTEGRITY_TERMINAL_TRANSIENT_BOUNDED_RETRY','contentMutation':'FORBIDDEN'})
 add('WORKER-INTEGRITY','WorkerGrant',{'job':ref('JOB-INTEGRITY'),'identity':'service:reference-integrity','tenants':['tenant-one','tenant-two'],'scope':'ALL_DOCUMENTS_OF_RESOURCE_IN_TENANT','privileges':['READ_CONTENT','WRITE_INTEGRITY_RESULT','APPEND_JOB_AUDIT'],'binding':'EXPLICIT_HOST_SERVICE_CONTEXT_NO_USER_JWT'})
 add('PERM-JOB-READ','JobReadPermission',{'job':ref('JOB-INTEGRITY'),'actor':ref('ACT-REVIEWER'),'role':ref('ROLE-REVIEWER'),'scope':ref('SCOPE-CASE'),'principalField':ref('CASE-ASSIGNEE'),'effect':'ALLOW','resourceRule':'AUTHENTICATED_OWNER'})
 add('VIEW-JOBS','JobView',{'job':ref('JOB-INTEGRITY'),'screen':ref(next(n['id'] for n in s['nodes'] if n['kind']=='Screen')),'permission':ref('PERM-JOB-READ'),'presentation':'READ_ONLY_JOB_RESULTS','states':['PENDING','RUNNING','RETRY','COMPLETED','FAILED']})
 return s
