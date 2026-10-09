"""Closed Canonical 0.3 task-interface lowering; not a new semantic authority."""
from model import CapabilityError, identifier, encoded
UI_KINDS=set('Screen Form InputControl Table Filter Search Wizard WizardStep Action ViewState PermissionBoundary'.split())
BROWSER={'version':'1.0.0','engine':'chromium','playwright':'1.63.0','axe':'4.13.0','viewports':{'COMPACT':{'width':390,'height':844},'EXPANDED':{'width':1280,'height':900}},'manualAccessibility':'OUTSTANDING','otherBrowsers':'OUTSTANDING'}

def validate(nodes):
    by={n['id']:n for n in nodes}
    def fail(reason):raise CapabilityError('TASK_UI:'+reason)
    def check(condition,reason):
        if not condition:fail(reason)
    def resolve(ref,kind):
        n=by.get(ref.get('id')) if isinstance(ref,dict) else None
        check(n is not None and n['revision']==ref.get('revision') and n['kind']==kind,'REFERENCE_'+kind)
        return n
    def one(kind):
        values=[n for n in nodes if n['kind']==kind];check(len(values)==1,'COUNT_'+kind);return values[0]
    def ref(n):return {'id':n['id'],'revision':n['revision']}
    def owned(field,owner):check(field['data']['owner']==ref(owner),'FIELD_OWNER')
    screen=one('Screen');sd=screen['data'];task=resolve(sd['task'],'UseCase');inp=resolve(task['data']['input'],'ValueObject');out=resolve(task['data']['output'],'ValueObject')
    search=one('Search');table=one('Table');wizard=one('Wizard');step=one('WizardStep');form=one('Form');action=one('Action');filter=one('Filter');boundary=one('PermissionBoundary');responsive=one('ResponsivePolicy');a11y=one('AccessibilityRequirement')
    check(sd['content']==[ref(search),ref(table),ref(wizard)],'CONTENT_ORDER')
    check(sd['actions']==[ref(action)] and form['data']['submit']==ref(action),'ACTION_OWNER')
    check(form['data']['useCase']==ref(task) and action['data']['useCase']==ref(task),'USE_CASE')
    check(action['data']['confirmation']=='REQUIRED','CONFIRMATION')
    check(wizard['data']['screen']==ref(screen) and wizard['data']['steps']==[ref(step)],'WIZARD')
    check(step['data']['wizard']==ref(wizard) and step['data']['form']==ref(form) and step['data']['requiresPrevious'] is False,'WIZARD_STEP')
    query=resolve(search['data']['query'],'Query');qd=query['data'];check(table['data']['query']==ref(query) and filter['data']['query']==ref(query),'QUERY_OWNER')
    check(qd['result']=={'kind':'Value','definition':ref(out)},'QUERY_RESULT')
    check(search['data']['filters']==[ref(filter)],'FILTER_COUNT')
    fd=filter['data'];qinp=resolve(qd['input'],'ValueObject');qfield=resolve(fd['inputField'],'Field');owned(qfield,qinp)
    check(fd['operator']=='CONTAINS' and fd['inputType']=={'kind':'String'} and qfield['data']['type']=={'kind':'String'} and not qfield['data']['optional'],'FILTER_TYPE')
    check([n['id'] for n in nodes if n['kind']=='Field' and n['data']['owner']==ref(qinp)]==[qfield['id']],'QUERY_INPUT')
    projected=resolve(fd['field'],'Field');owned(projected,out)
    projection={p['field']['id']:p for p in qd['projection']}
    check(projected['id'] in projection and qd['predicate']=={'tag':'textContains','value':projection[projected['id']]['value'],'pattern':{'tag':'input','scope':'OPERATION','field':ref(qfield)}},'FILTER_PREDICATE')
    columns=[resolve(r,'Field') for r in table['data']['columns']]
    check(len(columns)==1 and ref(columns[0])==ref(projected),'TABLE_COLUMNS')
    check(all(n['id'] in projection and n['data']['type']=={'kind':'String'} and not n['data']['optional'] for n in columns),'TABLE_PROJECTION')
    steps=[resolve(r,'ExecutionStep') for r in task['data']['steps']]
    resources=[s['data']['resource'] for s in steps]
    check(bool(resources) and all(r==resources[0] for r in resources),'RESOURCE_BINDING')
    r=resources[0];check(r['tag']=='input' and r['scope']=='USE_CASE','RESOURCE_BINDING')
    resource=resolve(r['field'],'Field');owned(resource,inp)
    check(resource['data']['type']=={'kind':'Identifier','entity':qd['resource']},'SELECTED_RESOURCE_BINDING')
    controls=[resolve(r,'InputControl') for r in form['data']['controls']]
    check(len(controls)==2 and set(n['id'] for n in controls)==set(n['id'] for n in nodes if n['kind']=='InputControl'),'CONTROL_COUNT')
    fields=[]
    for control in controls:
        d=control['data'];f=resolve(d['field'],'Field');owned(f,inp);fields.append(f)
        check(d['form']==ref(form) and d['required'] is True and not f['data']['optional'],'CONTROL_OWNER_REQUIRED')
        check((d['purpose']=='TEXT' and f['data']['type']['kind'] in {'String','Identifier'}) or (d['purpose']=='MULTILINE' and f['data']['type']=={'kind':'String'}),'CONTROL_PURPOSE_TYPE')
    check(set(n['id'] for n in fields)==set(n['id'] for n in nodes if n['kind']=='Field' and n['data']['owner']==ref(inp)),'FORM_FIELDS')
    check(fields[0]['id']==resource['id'] and controls[0]['data']['purpose']=='TEXT' and controls[1]['data']['purpose']=='MULTILINE','CONTROL_BINDING')
    actor=one('AuthenticationModel')['data']['actor'];resolve(actor,'Actor')
    permissions=[n for n in nodes if n['kind']=='Permission' and n['data']['action']['id'] in [s['data']['operation']['id'] for s in steps]]
    check(action['data']['permissions']==[ref(n) for n in sorted(permissions,key=lambda n:n['id'])],'ACTION_PERMISSIONS')
    check(sd['boundary']==ref(boundary) and boundary['data']['actor']==actor,'BOUNDARY_ACTOR')
    query_permissions=[n for n in nodes if n['kind']=='Permission' and n['data']['action']==ref(query)]
    check(boundary['data']['permissions']==[ref(n) for n in sorted(permissions+query_permissions,key=lambda n:n['id'])],'BOUNDARY_PERMISSIONS')
    states=[resolve(r,'ViewState') for r in sd['states']]
    check(len(states)==4 and {n['data']['state'] for n in states}=={'EMPTY','LOADING','ERROR','SUCCESS'} and len([n for n in nodes if n['kind']=='ViewState'])==4,'VIEW_STATES')
    for n in states:check(n['data']['screen']==ref(screen),'VIEW_SCREEN')
    error=next(n for n in states if n['data']['state']=='ERROR')
    check(error['data'].get('recovery')==ref(action) and boundary['data']['denied']==ref(error),'ERROR_RECOVERY')
    check(sd['responsive']==ref(responsive) and responsive['data']['screen']==ref(screen) and set(responsive['data']['modes'])=={'COMPACT','EXPANDED'} and responsive['data']['preserveActions'] is True and responsive['data']['preserveReadingOrder'] is True,'RESPONSIVE')
    check(sd['accessibility']==ref(a11y) and a11y['data']['method']=='AUTOMATED_AND_MANUAL' and set(a11y['data']['checks'])=={'ERROR_ANNOUNCEMENT','FOCUS','KEYBOARD','LABELS'} and all(ref(n) in a11y['data']['subjects'] for n in [screen,form,action,*controls]),'ACCESSIBILITY')
    result={'version':'1.0.0','screen':screen,'task':task,'search':search,'filter':filter,'query':query,'table':table,'columns':columns,'wizard':wizard,'step':step,'form':form,'controls':controls,'fields':fields,'action':action,'boundary':boundary,'states':{n['data']['state']:n for n in states},'responsive':responsive,'accessibility':a11y,'resourceInputField':resource['id'],'queryInputField':qfield['id'],'textInputField':fields[1]['id'],'outputField':projected['id'],'queryPath':'/api/'+identifier(query['id'],'op'),'actionPath':'/api/'+identifier(task['id'],'op'),'page':{'offset':0,'limit':min(50,qd['maximumResults'])},'selectionBinding':{'source':'QueryCompletion.resourceId','target':ref(resource),'expectedVersionSource':'QueryCompletion.version'},'browserProfile':BROWSER}
    return result

def contracts(ui):
    import json
    q=lambda v:json.dumps(v,ensure_ascii=False)
    resource,text,output,query=(ui[k] for k in ('resourceInputField','textInputField','outputField','queryInputField'))
    return """import { call } from './api';
export type QueryInput = { %s: string };
export type TaskInput = { %s: string; %s: string };
export type TaskOutput = { %s: string };
export type TaskCompletion = { output: TaskOutput; resourceId: string; version: number; state: string | null };
export type ActionRequest = { expectedVersion: number; idempotencyKey: string; input: TaskInput };
export const resourceInputField = %s;
export function queryInput(text: string): QueryInput { return { %s: text }; }
export function taskInput(values: Partial<TaskInput>, resourceId: string): TaskInput {
 const text=values[%s]; if(text===undefined || text==='') throw new Error('INVALID_TASK_INPUT');
 return { %s: resourceId, %s: text };
}
export function queryTasks(text: string): Promise<TaskCompletion[]> {
 return call<TaskCompletion[]>(%s,queryInput(text));
}
export function submitTask(values: Partial<TaskInput>,resourceId: string,expectedVersion: number,idempotencyKey: string): Promise<TaskCompletion> {
 const body:ActionRequest={expectedVersion,idempotencyKey,input:taskInput(values,resourceId)};
 return call<TaskCompletion>(%s,body);
}
"""%(q(query),q(resource),q(text),q(output),q(resource),q(query),q(text),q(resource),q(text),q(ui['queryPath']+'?offset=0&limit='+str(ui['page']['limit'])),q(ui['actionPath']))
