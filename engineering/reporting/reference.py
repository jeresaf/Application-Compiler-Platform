"""Proposed reporting authority; no accepted history is altered."""
import copy
from engineering.native_create.reference import proposal as create_proposal

def proposal():
 s=create_proposal();s['modelVersion']='0.6.0';nodes={n['id']:n for n in s['nodes']}
 def ref(i):return {'id':i,'revision':nodes[i]['revision'] if i in nodes else 1}
 def node(i,kind,data,basis=('REQ-R5-REPORT',)):
  n={'id':i,'revision':1,'kind':kind,'name':'PROPOSED '+i,'lifecycle':'APPROVED','steward':'assistant:proposal','origins':[{'source':'proposal:phase10-r5-reporting','locator':i,'actor':'assistant:proposal','actorType':'AI'}],'basis':[ref(b) for b in basis],'data':data};s['nodes'].append(n);nodes[i]=n
 node('REQ-R5-REPORT','Requirement',{'statement':'PROPOSED authorized owner-scoped, tenant-bound case reporting, explicit safe projection/filter/sort/pagination/state counts and operation-only audit history. Read-only, no export or new production authority.','priority':'MUST','acceptance':[ref('AC-R5-REPORT')]},())
 node('AC-R5-REPORT','AcceptanceCriterion',{'requirement':ref('REQ-R5-REPORT'),'scenario':'Real generated queries/UI show only authenticated tenant and owner cases; support typed filters, stable pages, state counts and authorized operation/time history; reject malformed, unauthorized, cross-tenant and sensitive-field requests. Regeneration, refresh and restart preserve rows and audits.'})
 node('ASSIGN-R5-TENANT-TWO','RoleAssignment',{'role':ref('ROLE-REVIEWER'),'actor':ref('ACT-REVIEWER'),'scope':ref('SCOPE-CASE'),'principal':'fixture:reporter-two'})
 node('REPORT-CASES','ReportDefinition',{'resource':ref('CASE'),'fields':[{'field':ref('FLD-CASE-TITLE'),'member':ref('FLD-TITLE')},{'field':ref('FLD-TASK-SUMMARY'),'member':None}],'filters':[{'name':'summary','field':ref('FLD-TASK-SUMMARY'),'type':'STRING','operation':'CONTAINS'},{'name':'state','field':None,'type':'STATE','operation':'EQ'}],'orderBy':[{'field':'IDENTITY','direction':'ASC'}],'pagination':{'defaultSize':2,'maximumSize':20,'maximumPage':1000},'groupBy':'WORKFLOW_STATE','aggregations':['COUNT'],'permission':ref('PERM-REPORT'),'auditHistory':ref('HISTORY-CASES'),'output':'PROJECTED_FIELDS_IDENTITY_VERSION_STATE','mutation':'FORBIDDEN','export':'NOT_GRANTED'},('REQ-R5-REPORT','AC-R5-REPORT'))
 for i,access in [('PERM-REPORT','REPORT'),('PERM-HISTORY','AUDIT')]:
  node(i,'ReportPermission',{'report':ref('REPORT-CASES'),'access':access,'actor':ref('ACT-REVIEWER'),'role':ref('ROLE-REVIEWER'),'scope':ref('SCOPE-CASE'),'principalField':ref('CASE-ASSIGNEE'),'effect':'ALLOW','tenantRule':'AUTHENTICATED_TENANT','resourceRule':'AUTHENTICATED_OWNER','fieldLevels':['PUBLIC','INTERNAL']})
 node('HISTORY-CASES','AuditHistory',{'report':ref('REPORT-CASES'),'permission':ref('PERM-HISTORY'),'operations':[ref(i) for i in ['CREATE-CASE','CMD-REVIEW','CMD-APPROVE','CMD-ARCHIVE']],'projection':['operation','occurredAt'],'visibility':'AUTHORIZED_RESOURCE_SCOPE','orderBy':'OCCURRED_AT_ASC_ID_ASC'})
 node('VIEW-REPORT','ReportView',{'report':ref('REPORT-CASES'),'permission':ref('PERM-REPORT'),'screen':ref(next(n['id'] for n in s['nodes'] if n['kind']=='Screen')),'presentation':'TABLE_STATE_COUNTS_AUDIT','columns':[ref('FLD-CASE-TITLE'),ref('FLD-TASK-SUMMARY')],'filters':['summary','state'],'states':['LOADING','READY','EMPTY','ERROR']})
 return copy.deepcopy(s)
