"""Version-scoped document generation on the existing reporting target."""
import hashlib,json
from pathlib import Path
from dataclasses import replace
from engineering.documents import semantics
from engineering.documents.schema import FEATURES,KINDS
from engineering.reporting.target import ReportingTarget,source_digest as reporting_digest
from engineering.reporting.schema import FEATURES as REPORT_FEATURES
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
from engineering.source_intelligence.model import sha,encode,require
from compiler_contracts import Document
from compiler_reference import SyntheticTarget
PACKAGE=Path(__file__).parent;ROOT=PACKAGE.parents[1];PROFILE='acp-document-preview-target/1';GENERATOR='acp-document-preview-generator/1'
def source_digest():return sha(encode({'reporting':reporting_digest(),'files':{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(PACKAGE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.json','.java','.vue','.ts'}}}))
def lower_documents(snapshot,model):
 nodes={n['id']:n for n in snapshot['content']['nodes']};docs=[n for n in nodes.values() if n['kind']=='DocumentDefinition'];require(len(docs)==1,'DOCUMENT_SINGLE_DEFINITION');doc=docs[0];d=doc['data'];e=nodes[d['resource']['id']];table=next(t for t in model['tables'] if t['origin']['id']==e['id']);cols={c['origin']['id']:c['name'] for c in table['columns']};upload=nodes[d['uploadPermission']['id']]['data'];read=nodes[d['readPermission']['id']]['data'];require(all(upload[k]==read[k] for k in ('actor','scope','principalField')),'DOCUMENT_GRANT_SCOPE');views=[n for n in nodes.values() if n['kind']=='DocumentView' and n['data']['document']=={'id':doc['id'],'revision':doc['revision']}];require(len(views)==1,'DOCUMENT_SINGLE_VIEW')
 ident=cols[e['data']['identity'][0]['id']];tenant=cols[e['data']['tenantField']['id']];owner=cols[upload['principalField']['id']];symbol=hashlib.sha256(doc['id'].encode()).hexdigest()[:24]
 return {'schema':'acp-document-target/1','scope':'UNAPPROVED_DOCUMENT_PREVIEW','id':doc['id'],'path':'/api/document_'+symbol,'table':'d_'+symbol,'resourceTable':table['name'],'resourceIdentity':ident,'resourceTenant':tenant,'resourceOwner':owner,'resourceEntity':e['id'],'uploadPermission':upload,'readPermission':read,'uploadOperation':d['uploadPermission']['id'],'downloadOperation':d['readPermission']['id'],'maximumBytes':d['maximumBytes'],'mediaTypes':d['mediaTypes'],'view':views[0]['id']}
def migration(c):
 return f'''CREATE TABLE {c['table']} (
 id uuid PRIMARY KEY,tenant bytea NOT NULL,resource bytea NOT NULL,principal bytea NOT NULL,
 filename varchar(120) NOT NULL,media_type text NOT NULL CHECK(media_type='text/plain'),
 content bytea NOT NULL,sha256 char(64) NOT NULL CHECK(sha256 ~ '^[0-9a-f]{{64}}$'),
 size integer NOT NULL CHECK(size>0 AND size<={c['maximumBytes']} AND octet_length(content)=size),
 idempotency_key varchar(80) NOT NULL,request_hash char(64) NOT NULL,created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(tenant,resource,idempotency_key),
 FOREIGN KEY(tenant,resource) REFERENCES {c['resourceTable']}({c['resourceTenant']},{c['resourceIdentity']}) ON DELETE RESTRICT
);
CREATE INDEX ix_{c['table']} ON {c['table']}(tenant,resource,created_at,id);
CREATE TABLE {c['table']}_audit (audit_id bigint PRIMARY KEY REFERENCES acp_audit(id),document uuid NOT NULL REFERENCES {c['table']}(id),sha256 char(64) NOT NULL);
'''
class DocumentTarget(ReportingTarget):
 identity=PROFILE;capabilities=tuple(sorted(set(ReportingTarget.capabilities)|set(FEATURES)))
 def __init__(self):
  self.base=SuccessorCandidate();require(self.base.bundle=='600a552287cc1121be7578c31ba2a379332c9b0d55c60a79b2a5d054c92271aa','DOCUMENT_PARENT');self.bundle=source_digest();self.generator=GENERATOR+'+sha256:'+self.bundle;self._profile=Document.of({**self.base.profile,'profile':PROFILE,'generator':GENERATOR});self.targets={}
 def _verify(self):self.base._verify();require(self.bundle==source_digest(),'DOCUMENT_SOURCE_CHANGED');require(self.profile=={**self.base.profile,'profile':PROFILE,'generator':GENERATOR},'DOCUMENT_PROFILE')
 def lower(self,realization,request):
  self._verify();snapshot=realization.projections.snapshot.read();semantics.validate_snapshot(snapshot);require(request.features==FEATURES and request.snapshot_digest==snapshot['contentDigest'],'DOCUMENT_VERSION');compat=Document.of(semantics.reporting_snapshot(snapshot));view=replace(realization,projections=replace(realization.projections,snapshot=compat));r=replace(request,features=REPORT_FEATURES,snapshot_digest=compat.read()['contentDigest']);base=ReportingTarget.lower(self,view,r);model=base.target_model.read();nodes=snapshot['content']['nodes'];model.update(profile=PROFILE,generator=GENERATOR,canonicalVersion='0.6.0',semanticModelVersion='0.7.0',requiredCapabilities=list(FEATURES),nodes=nodes,objects=[{'id':'target_'+hashlib.sha256(n['id'].encode()).hexdigest()[:24],'role':n['kind'],'origin':{'id':n['id'],'revision':n['revision']}} for n in nodes]);model['documents']=lower_documents(snapshot,model)
  d=model['documents'];model['api'].extend({'origin':{'id':d['id'],'revision':1},'path':d['path']+'/'+op,'method':'POST','role':'DocumentDefinition','permissions':[d['uploadOperation'] if op=='upload' else d['downloadOperation']],'semantic':{'transactionalBinary':True},'errors':[400,401,403,404,409,413,415,500],'concurrency':'RESOURCE_FENCED','pagination':{'maximum':20}} for op in ('upload','list','metadata','download'))
  neutral=SyntheticTarget.lower(self,realization,request);target=replace(neutral,target_model=Document.of(model));self.targets[(request.snapshot_digest,request.compiler,request.pipeline)]=target;return target
 def _call(self,operation,payload):
  if operation!='plan':return self.base._call(operation,payload)
  model=payload['model'];require(model['canonicalVersion']=='0.6.0','DOCUMENT_RENDER_VERSION');legacy={**model,'canonicalVersion':'0.5.0','nodes':[n for n in model['nodes'] if n['kind'] not in KINDS and n['id'] not in {'REQ-R6-DOCUMENTS','AC-R6-DOCUMENTS'}],'objects':[o for o in model['objects'] if o['role'] not in KINDS and o['origin']['id'] not in {'REQ-R6-DOCUMENTS','AC-R6-DOCUMENTS'}],'api':[a for a in model['api'] if a['role']!='DocumentDefinition']};rows=ReportingTarget._call(self,operation,{**payload,'model':legacy});c=model['documents'];ids=sorted(n['id'] for n in model['nodes'] if n['kind'] in KINDS or n['id'] in {'REQ-R6-DOCUMENTS','AC-R6-DOCUMENTS'})
  def add(path,text,role):rows.append({'path':path,'text':text,'role':role,'owner':'COMPILER_OWNED','origins':ids,'verification':['target-source-integrity']})
  add('backend/src/main/java/acp/api/DocumentController.java',(PACKAGE/'templates/DocumentController.java').read_text().replace('${DOCUMENT_ID}',json.dumps(c['id'])).replace('${DOCUMENT_PATH}',c['path']),'DOCUMENT_API')
  add('backend/src/main/resources/acp-documents.json',json.dumps(c,sort_keys=True)+'\n','DOCUMENT_CONTRACT');add('backend/src/main/resources/db/migration/V4__documents.sql',migration(c),'DOCUMENT_STORAGE')
  add('frontend/src/document-contract.ts','export const documentId='+json.dumps(c['id'])+' as const;\nexport const documentContract={...'+json.dumps({k:c[k] for k in ('id','path','maximumBytes','mediaTypes')},sort_keys=True)+',id:documentId} as const;\n','DOCUMENT_CLIENT_CONTRACT');add('frontend/src/DocumentPanel.vue',(PACKAGE/'templates/DocumentPanel.vue').read_text(),'DOCUMENT_UI')
  by={r['path']:r for r in rows};app=by['frontend/src/App.vue'];app['text']=app['text'].replace('<script setup lang="ts">','<script setup lang="ts">\nimport DocumentPanel from "./DocumentPanel.vue";',1);a,b=app['text'].rsplit('</template>',1);app['text']=a+'<DocumentPanel v-if="allowed" :key="JSON.stringify([snapshot.tenant,snapshot.subject])" /></template>'+b;app['origins']=sorted(set(app['origins'])|set(ids))
  props=by['backend/src/main/resources/application.properties'];props['text']+='\nspring.servlet.multipart.max-file-size=1MB\nspring.servlet.multipart.max-request-size=2MB\n';props['origins']=sorted(set(props['origins'])|set(ids))
  full=json.dumps(model,sort_keys=True,separators=(',',':'))+'\n';by['backend/src/main/resources/acp-model.json']['text']=full;by['backend/src/main/resources/acp-model.json']['origins']=sorted(set(by['backend/src/main/resources/acp-model.json']['origins'])|set(ids));by['contracts/target-ir.json']['text']=json.dumps({'schema':'acp-native-target-reference/1','path':'backend/src/main/resources/acp-model.json','sha256':sha(full.encode()),'canonicalVersion':'0.6.0','renderBackend':'deterministic-execution/0.3'},sort_keys=True)+'\n'
  by['acp/target-upgrade.json']['text']=json.dumps({'scope':'QUALIFICATION_ONLY','schema':'acp-document-preview-upgrade/1','existingDatabaseUpgrade':'UNSUPPORTED','migration':'NOT_AUTHORIZED'},sort_keys=True)+'\n';side=by['acp/provenance.json'];doc=json.loads(side['text']);doc['originSets']['canonical-model']=[{'id':n['id'],'revision':n['revision']} for n in model['nodes']];doc['build'].update(canonicalVersion='0.6.0',semanticModelVersion='0.7.0',features=list(FEATURES),generator=GENERATOR);known={m['artifact'] for m in doc['artifacts']}
  for r in rows:
   if r['path'] not in known and r is not side:doc['artifacts'].append({'artifact':r['path'],'generator':GENERATOR,'targetRole':r['role'],'ownership':r['owner'],'originSet':'canonical-model','locations':[],'locationConfidence':'ARTIFACT_ONLY'})
  # Whitespace-only encoding; preserve text-block indentation and HUMAN code.
  for row in rows:
   if row['path'].endswith('.java') and row['owner']!='HUMAN_OWNED' and '"""' not in row['text']:row['text']='\n'.join(line.lstrip() for line in row['text'].splitlines() if line.strip())+'\n'
  for m in doc['artifacts']:
   row=by[m['artifact']];m.update(generator=GENERATOR,artifactDigest='sha256:'+sha(row['text'].encode()),targetObjects=['target_'+hashlib.sha256(i.encode()).hexdigest()[:24] for i in row['origins']])
  side['text']=json.dumps(doc,sort_keys=True,separators=(',',':'))+'\n';self._verify();return rows
 def verify_materialized(self,root,plan,snapshot,request):
  from engineering.generator_candidates.spring_vue_postgres_0_6 import provenance
  self._verify();semantics.validate_snapshot(snapshot.read());require(snapshot.read()['contentDigest']==request.snapshot_digest,'DOCUMENT_VERIFY_IDENTITY');return provenance.verify_plan_provenance(root,plan,provenance.read_provenance(Path(root)/'acp/provenance.json'),target=self.targets[(request.snapshot_digest,request.compiler,request.pipeline)],request=request)
 def descriptor(self):return {'profile':PROFILE,'generator':self.generator,'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED'}
