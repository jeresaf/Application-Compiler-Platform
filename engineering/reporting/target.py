"""Reporting target over existing CREATE and deterministic execution generation."""
import hashlib,json
from pathlib import Path
from dataclasses import replace
from engineering.reporting import semantics
from engineering.reporting.schema import FEATURES,KINDS
from engineering.native_create import semantics as create_semantics
from engineering.native_create.target import NativeTarget,lower_create,source_digest as create_digest
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
from engineering.source_intelligence.model import sha,encode,require
from compiler_contracts import Document
from compiler_reference import SyntheticTarget
from compiler_core import _ownership
from target_worker import ProductionTarget
PACKAGE=Path(__file__).parent;ROOT=PACKAGE.parents[1]
PROFILE='acp-reporting-preview-target/1';GENERATOR='acp-reporting-preview-generator/1'
def source_digest():
 paths=[p for p in sorted(PACKAGE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.json','.java','.vue','.ts'}]
 paths+=[ROOT/'engineering/compiler_extensions/dispatch.py']
 return sha(encode({'files':{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths},'createSource':create_digest(),'parent06':'600a552287cc1121be7578c31ba2a379332c9b0d55c60a79b2a5d054c92271aa'}))
def lower_report(snapshot,model):
 semantics.validate_snapshot(snapshot);nodes={n['id']:n for n in snapshot['content']['nodes']};reports=[n for n in nodes.values() if n['kind']=='ReportDefinition'];require(len(reports)==1,'REPORT_SINGLE_DEFINITION')
 report=reports[0];d=report['data'];entity=nodes[d['resource']['id']];table=next(t for t in model['tables'] if t['origin']['id']==entity['id']);columns={c['origin']['id']:c['name'] for c in table['columns']}
 permission=nodes[d['permission']['id']]['data'];history=nodes[d['auditHistory']['id']]['data'];audit_permission=nodes[history['permission']['id']]['data']
 require(permission['principalField']==audit_permission['principalField'] and permission['actor']==audit_permission['actor'] and permission['scope']==audit_permission['scope'],'REPORT_AUDIT_SCOPE')
 ident=entity['data']['identity'][0]['id'];tenant=entity['data']['tenantField']['id'];principal=permission['principalField']['id'];fields=[];sorts={'IDENTITY':columns[ident],'STATE':'acp_state COLLATE "C"'}
 for f in d['fields']:
  node=nodes[f['field']['id']];require(not node['data']['optional'],'REPORT_OPTIONAL_PROJECTION_UNSUPPORTED')
  member=f['member']['id'] if f['member'] else None
  expression='convert_from('+columns[node['id']]+",'UTF8')"
  if member:expression="("+expression+"::jsonb ->> '"+member.replace("'","''")+"')"
  sorts[node['id']]=expression+' COLLATE "C"'
  fields.append({'id':node['id'],'label':node['name'].removeprefix('FLD-').replace('-',' ').title(),'column':columns[node['id']],'member':member})
 filters={}
 for f in d['filters']:
  expression='acp_state' if f['type']=='STATE' else 'convert_from('+columns[f['field']['id']]+",'UTF8')"
  filters[f['name']]={**f,'sql':expression+'=?' if f['operation']=='EQ' else 'position(? in '+expression+')>0'}
 owner=nodes[principal]['data']['type']['entity']['id'];pt=next(t for t in model['tables'] if t['origin']['id']==owner);pd=pt['semantic'];require(pd['tenancy']=='SCOPED' and len(pd['identity'])==1,'REPORT_PRINCIPAL')
 sqlid=lambda id:'f_'+hashlib.sha256(id.encode()).hexdigest()[:24]
 where=columns[tenant]+'=? AND '+columns[principal]+'=?'
 where+=' AND NOT EXISTS (SELECT 1 FROM acp_lifecycle_anchor la WHERE la.entity=\''+entity['id'].replace("'","''")+'\' AND la.tenant='+table['name']+'.'+columns[tenant]+' AND la.resource='+table['name']+'.'+columns[ident]+" AND la.status IN ('COMPLETED','INDETERMINATE'))"
 states=sorted([{'id':n['id'],'label':n['name']} for n in nodes.values() if n['kind']=='State' and any(m['kind']=='StateMachine' and m['data']['resource']==d['resource'] and n['data']['machine']=={'id':m['id'],'revision':m['revision']} for m in nodes.values())],key=lambda x:x['id'])
 views=[n for n in nodes.values() if n['kind']=='ReportView' and n['data']['report']=={'id':report['id'],'revision':report['revision']}];require(len(views)==1,'REPORT_SINGLE_VIEW')
 ops=[r['id'] for r in history['operations']]
 return {'schema':'acp-report-target/1','scope':'UNAPPROVED_REPORT_PREVIEW','id':report['id'],'path':'/api/report_'+hashlib.sha256(report['id'].encode()).hexdigest()[:24],'view':views[0]['id'],'historyId':d['auditHistory']['id'],'reportPermissionId':d['permission']['id'],'auditPermissionId':history['permission']['id'],'table':table['name'],'identityColumn':columns[ident],'fields':fields,'filters':filters,'sorts':sorts,'defaultOrderSQL':','.join(sorts[o['field']]+' '+o['direction'] for o in d['orderBy'])+','+columns[ident]+' ASC','pagination':d['pagination'],'states':states,'permission':permission,'auditPermission':audit_permission,'auditOperations':ops,'auditWhereSQL':'tenant=? AND resource=? AND operation IN ('+','.join('?' for _ in ops)+')','whereSQL':where,'selectSQL':','.join(dict.fromkeys([columns[ident],'acp_version','acp_state',*[f['column'] for f in fields]])),'principalSQL':f"SELECT count(*) FROM {pt['name']} WHERE {sqlid(pd['identity'][0]['id'])}=? AND {sqlid(pd['tenantField']['id'])}=?"}

class ReportingTarget(NativeTarget):
 identity=PROFILE;capabilities=tuple(sorted(set(NativeTarget.capabilities)|set(FEATURES)))
 def __init__(self):
  self.base=SuccessorCandidate();require(self.base.bundle=='600a552287cc1121be7578c31ba2a379332c9b0d55c60a79b2a5d054c92271aa','REPORT_PARENT_SOURCE')
  self.bundle=source_digest();self.generator=GENERATOR+'+sha256:'+self.bundle;self._profile=Document.of({**self.base.profile,'profile':PROFILE,'generator':GENERATOR});self.targets={}
 def _verify(self):
  self.base._verify();require(source_digest()==self.bundle,'REPORT_SOURCE_CHANGED');require(self.profile=={**self.base.profile,'profile':PROFILE,'generator':GENERATOR},'REPORT_PROFILE')
 def lower(self,realization,request):
  self._verify();require({d.role:d.choice.read()['choice'] for d in (*realization.architecture,*realization.design)}==self.profile['decisions'],'REPORT_DECISIONS')
  snapshot=realization.projections.snapshot.read();require(request.features==FEATURES and request.snapshot_digest==snapshot['contentDigest'],'REPORT_VERSION')
  create=semantics.create_snapshot(snapshot);legacy=create_semantics.legacy_snapshot(create)
  model=self.base.lower(Document.of(legacy),compiler=request.compiler,pipeline=request.pipeline).target_model.read();nodes=snapshot['content']['nodes']
  model.update(profile=PROFILE,generator=GENERATOR,canonicalVersion='0.5.0',semanticModelVersion='0.6.0',requiredCapabilities=list(FEATURES),nodes=nodes,objects=[{'id':'target_'+hashlib.sha256(n['id'].encode()).hexdigest()[:24],'role':n['kind'],'origin':{'id':n['id'],'revision':n['revision']}} for n in nodes])
  model['intakePreview']=lower_create(create,model);model['reporting']=lower_report(snapshot,model)
  create=model['intakePreview'];report=model['reporting']
  model['api'].extend([{'origin':{'id':create['operation'],'revision':create['revision']},'path':create['path'],'method':'POST','role':'CreateOperation','permissions':[create['permission']],'semantic':next(n['data'] for n in nodes if n['id']==create['operation']),'errors':[202,400,401,403,409,429,500],'concurrency':'ONE_COMMITTED_CREATION','pagination':{'maximum':1}},*({'origin':{'id':identity,'revision':1},'path':path,'method':'POST','role':'ReportDefinition','permissions':[permission],'semantic':{'readOnly':True},'errors':[400,401,403,404,500],'concurrency':'READ_ONLY','pagination':{'maximum':report['pagination']['maximumSize']}} for identity,path,permission in [(report['id'],report['path'],report['reportPermissionId']),(report['historyId'],report['path']+'/history',report['auditPermissionId'])])])
  neutral=SyntheticTarget.lower(self,realization,request);target=replace(neutral,target_model=Document.of(model));self.targets[(request.snapshot_digest,request.compiler,request.pipeline)]=target;return target
 def _call(self,operation,payload):
  if operation!='plan':return self.base._call(operation,payload)
  model=payload['model'];require(model['canonicalVersion']=='0.5.0','REPORT_RENDER_VERSION')
  rows=NativeTarget._call(self,operation,{**payload,'model':{**model,'canonicalVersion':'0.4.0'}});c=model['reporting'];ids=sorted(n['id'] for n in model['nodes'] if n['kind'] in KINDS or n['id'] in {'REQ-R5-REPORT','AC-R5-REPORT'})
  def add(path,text,role):rows.append({'path':path,'text':text,'role':role,'owner':'COMPILER_OWNED','origins':ids,'verification':['target-source-integrity']})
  add('backend/src/main/java/acp/api/ReportingController.java',(PACKAGE/'templates/ReportingController.java').read_text().replace('${REPORT_ID}',json.dumps(c['id'])).replace('${REPORT_PATH}',c['path']),'REPORT_API')
  add('backend/src/main/resources/acp-report.json',json.dumps(c,sort_keys=True)+'\n','REPORT_CONTRACT')
  public={k:c[k] for k in ('id','path','fields','states','pagination')};public['filters']=[{'name':n,'type':f['type']} for n,f in c['filters'].items()]
  add('frontend/src/report-contract.ts','export const reportId='+json.dumps(c['id'])+' as const;\nexport const reportContract={...'+json.dumps(public,sort_keys=True)+',id:reportId} as const;\n','REPORT_CLIENT_CONTRACT')
  add('frontend/src/ReportPanel.vue',(PACKAGE/'templates/ReportPanel.vue').read_text(),'REPORT_UI')
  by={r['path']:r for r in rows};app=by['frontend/src/App.vue'];app['text']=app['text'].replace('<script setup lang="ts">','<script setup lang="ts">\nimport ReportPanel from "./ReportPanel.vue";',1);a,b=app['text'].rsplit('</template>',1);app['text']=a+'<ReportPanel v-if="allowed" :key="JSON.stringify([snapshot.tenant,snapshot.subject])" /></template>'+b;app['origins']=sorted(set(app['origins'])|set(ids))
  full=json.dumps(model,sort_keys=True,separators=(',',':'))+'\n';by['backend/src/main/resources/acp-model.json']['text']=full
  by['contracts/target-ir.json']['text']=json.dumps({'schema':'acp-native-target-reference/1','path':'backend/src/main/resources/acp-model.json','sha256':sha(full.encode()),'canonicalVersion':'0.5.0','renderBackend':'deterministic-execution/0.3'},sort_keys=True)+'\n'
  by['acp/target-upgrade.json']['text']=json.dumps({'scope':'QUALIFICATION_ONLY','schema':'acp-report-preview-upgrade/1','existingDatabaseUpgrade':'UNSUPPORTED','migration':'NOT_AUTHORIZED'},sort_keys=True)+'\n'
  side=by['acp/provenance.json'];doc=json.loads(side['text']);doc['build'].update(canonicalVersion='0.5.0',semanticModelVersion='0.6.0',features=list(FEATURES),generator=GENERATOR)
  known={x['artifact'] for x in doc['artifacts']}
  for r in rows:
   if r['path'] not in known and r is not side:doc['artifacts'].append({'artifact':r['path'],'generator':GENERATOR,'targetRole':r['role'],'ownership':r['owner'],'originSet':'canonical-model','locations':[],'locationConfidence':'ARTIFACT_ONLY'})
  for m in doc['artifacts']:
   r=by[m['artifact']];m.update(generator=GENERATOR,artifactDigest='sha256:'+sha(r['text'].encode()),targetObjects=['target_'+hashlib.sha256(i.encode()).hexdigest()[:24] for i in r['origins']])
  side['text']=json.dumps(doc,sort_keys=True,separators=(',',':'))+'\n';self._verify();return rows
 def verify_materialized(self,root,plan,snapshot,request):
  from engineering.generator_candidates.spring_vue_postgres_0_6 import provenance
  self._verify();semantics.validate_snapshot(snapshot.read());require(snapshot.read()['contentDigest']==request.snapshot_digest,'REPORT_VERIFY_IDENTITY')
  return provenance.verify_plan_provenance(root,plan,provenance.read_provenance(Path(root)/'acp/provenance.json'),target=self.targets[(request.snapshot_digest,request.compiler,request.pipeline)],request=request)
 def descriptor(self):return {'profile':PROFILE,'generator':self.generator,'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED'}
