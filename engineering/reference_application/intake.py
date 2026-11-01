"""Existing target extension for a closed, synthetic CREATE execution contract.

Canonical 0.3 cannot represent creation. This adapter never admits that contract
as Canonical semantics, nor changes the immutable 0.6.0 candidate or 0.5.0 seal.
"""
from dataclasses import replace
import hashlib,json,sys
from pathlib import Path
from engineering.reference_application import lifecycle as life
from engineering.demo.pipeline import request as make_request
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
from engineering.generator_candidates.spring_vue_postgres_0_6 import dependencies,rate_clock,provenance
from engineering.source_intelligence.model import sha,encode,require
from compiler_contracts import Document,COMPILER,PIPELINE
from compiler_core import _ownership
from changes import prepare
from deterministic_approval import approved_snapshot
from target_worker import ProductionTarget
from filesystem_artifacts import FilesystemArtifactStore

ROOT=life.ROOT;PROPOSAL=ROOT/'proposals/phase10-r3-intake';TEMPLATES=Path(__file__).parent/'intake_templates'
PROFILE='acp-intake-synthetic-target/1';GENERATOR='acp-intake-synthetic-generator/1'

def proposal():
 review=json.loads((PROPOSAL/'review.json').read_bytes())
 for name,pin in review['files'].items():require(sha((PROPOSAL/name).read_bytes())==pin,'INTAKE_PROPOSAL_SUBSTITUTED')
 change=json.loads((PROPOSAL/'change.json').read_bytes());p=prepare(approved_snapshot('case-management'),change)
 require(p==json.loads((PROPOSAL/'plan.json').read_bytes()) and p['candidate']==json.loads((PROPOSAL/'candidate.json').read_bytes()),'INTAKE_NATIVE_PLAN')
 require(p['candidate']['contentDigest']==review['candidateDigest'],'INTAKE_CANDIDATE_DIGEST')
 return Document.of(p['candidate']),json.loads((PROPOSAL/'synthetic-contract.json').read_bytes()),p

def lower_contract(snapshot,contract,target):
 expected={'schema','scope','requirement','acceptance','entity','operation','path','role','identity','tenant','assignee','initialState','inputs','optionalAbsent','idempotencySeconds','rate','routing','authority'}
 require(type(contract) is dict and set(contract)==expected and contract['schema']=='acp-intake-synthetic/1' and contract['scope']=='SYNTHETIC_PREVIEW_ONLY' and contract['authority']=='NOT_APPROVED','INTAKE_CLOSED_CONTRACT')
 require(contract['routing']=='AUTHENTICATED_SELF' and contract['path']=='/api/intake-preview' and contract['operation']=='PREVIEW-CREATE-CASE','INTAKE_UNSUPPORTED_OPERATION')
 require(type(contract['idempotencySeconds']) is int and 1<=contract['idempotencySeconds']<=3600 and contract['rate']=={'requests':30,'windowSeconds':60,'burst':10},'INTAKE_POLICY_BOUNDS')
 nodes={n['id']:n for n in snapshot.read()['content']['nodes']};tables={t['origin']['id']:t for t in target.target_model.read()['tables']}
 require(nodes[contract['requirement']]['kind']=='Requirement' and nodes[contract['acceptance']]['kind']=='AcceptanceCriterion','INTAKE_PROPOSAL_ORIGINS')
 entity=nodes[contract['entity']];require(entity['kind']=='Entity' and entity['data']['tenancy']=='SCOPED','INTAKE_SCOPED_ENTITY')
 ref=lambda id:{'id':id,'revision':nodes[id]['revision']}
 require(entity['data']['identity']==[ref(contract['identity'])] and entity['data']['tenantField']==ref(contract['tenant']),'INTAKE_IDENTITY_BINDING')
 require(any(n['kind']=='StateMachine' and n['data']['resource']==ref(entity['id']) and n['data']['initial']==ref(contract['initialState']) for n in nodes.values()),'INTAKE_INITIAL_STATE')
 require(nodes[contract['role']]['kind']=='Role','INTAKE_ROLE')
 table=tables[entity['id']];columns={c['origin']['id']:c for c in table['columns']}
 fields=[contract[k] for k in ('identity','tenant','assignee')];ordered=[]
 for name,b in contract['inputs'].items():
  require(type(name) is str and name.isidentifier() and name!='idempotencyKey' and set(b)=={'field','member','maxLength'} and type(b['maxLength']) is int and 1<=b['maxLength']<=2000,'INTAKE_INPUT_BINDING')
  node=nodes[b['field']];require(node['kind']=='Field' and node['data']['owner']==ref(entity['id']) and not node['data']['optional'],'INTAKE_FIELD_OWNER')
  typ=node['data']['type']
  if b['member'] is None:require(typ=={'kind':'String'},'INTAKE_UNSUPPORTED_TYPE')
  else:
   require(typ['kind']=='Value' and nodes[b['member']]['data']['owner']==typ['definition'] and nodes[b['member']]['data']['type']=={'kind':'String'},'INTAKE_VALUE_MEMBER')
   require([n['id'] for n in nodes.values() if n['kind']=='Field' and n['data']['owner']==typ['definition']]==[b['member']],'INTAKE_VALUE_MEMBERS')
  require(columns[b['field']]['sqlType']=='bytea','INTAKE_STORAGE');fields.append(b['field']);ordered.append({'name':name,**b})
 require(len(fields)==len(set(fields)),'INTAKE_DUPLICATE_FIELD')
 require(set(columns)==set(fields)|set(contract['optionalAbsent']),'INTAKE_FIELD_COVERAGE')
 for id in contract['optionalAbsent']:require(nodes[id]['data']['optional'],'INTAKE_REQUIRED_FIELD_OMITTED')
 assignee=nodes[contract['assignee']]['data']['type'];require(assignee['kind']=='Identifier','INTAKE_ASSIGNEE_TYPE')
 principal=tables[assignee['entity']['id']];pd=principal['semantic'];require(pd['tenancy']=='SCOPED' and len(pd['identity'])==1,'INTAKE_PRINCIPAL_SCOPE')
 ident=lambda id:'f_'+hashlib.sha256(id.encode()).hexdigest()[:24]
 names=[columns[id]['name'] for id in fields]
 require(all(columns[id]['sqlType']=='bytea' for id in fields),'INTAKE_STORAGE')
 result={**contract,'writtenFields':fields+[b['member'] for b in contract['inputs'].values() if b['member'] is not None],'orderedInputs':ordered,'insertSQL':f"INSERT INTO {table['name']}({','.join(names)},acp_state) VALUES({','.join(['?']*len(names))},'{contract['initialState']}')",'principalSQL':f"SELECT count(*) FROM {principal['name']} WHERE {ident(pd['identity'][0]['id'])}=? AND {ident(pd['tenantField']['id'])}=?"}
 return result

def source_digest():
 paths=[Path(__file__),*sorted(TEMPLATES.iterdir()),*sorted(PROPOSAL.glob('*.json'))]
 return sha(encode({str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths}))

class IntakeCandidate:
 """Reuse pure target lowering/templates, host ArtifactPlan adaptation and CAS."""
 def __init__(self):
  self.base=SuccessorCandidate();self.bundle=source_digest();self.generator=GENERATOR+'+sha256:'+self.bundle
  self.profile={**self.base.profile,'profile':PROFILE,'generator':GENERATOR}
 def _verify(self):self.base._verify();require(source_digest()==self.bundle,'INTAKE_SOURCE_CHANGED')
 def descriptor(self):return {'profile':PROFILE,'generator':self.generator,'scope':'SYNTHETIC_PREVIEW_ONLY','parent':self.base.descriptor(),'admission':'NOT_AUTHORIZED'}
 def lower(self,snapshot,request):
  self._verify();expected,contract,_=proposal();require(snapshot==expected and request.generator==self.generator and request.snapshot_digest==snapshot.read()['contentDigest'],'INTAKE_EXACT_PREVIEW_BINDING')
  target=self.base.lower(snapshot,compiler=request.compiler,pipeline=request.pipeline);lowered=lower_contract(snapshot,contract,target)
  return replace(target,target=PROFILE,target_model=Document.of({**target.target_model.read(),'profile':PROFILE,'intakePreview':lowered}))
 def _call(self,operation,payload):
  self._verify()
  if operation=='validate-plan':return self.base._generation.validate_plan(payload['artifacts'])
  require(operation=='plan' and payload['build']['bundleDigest']=='sha256:'+self.bundle,'INTAKE_OPERATION')
  worker=ROOT/'targets/spring-vue-postgres';templates={p.relative_to(worker/'templates').as_posix():p.read_text() for p in (worker/'templates').rglob('*') if p.is_file()}
  templates=dependencies.apply(rate_clock.apply(templates));contract=payload['model']['intakePreview']
  # Preserve the successor's ordered server-clock admission. Public token(...,
  # instant) is for explicit semantic instants, not pre-lock wall-clock sampling.
  core='backend/src/main/java/acp/infrastructure/InvocationCore.java';text=templates[core]
  require(text.count('private byte[] rateKey(')==1 and text.count('private boolean debit(')==1,'INTAKE_RATE_ANCESTRY')
  bridge="""
    public boolean syntheticToken(String policy,int revision,String tenant,String actor,int requests,int seconds,int burst) {
        byte[] key=rateKey(policy,revision,tenant,actor);
        return isolated.execute(status -> {
            lockRates(List.of(key));
            BigInteger instant=time.now();if(instant.signum()<0)throw new Outcome("SEMANTIC_TIME");
            return debit(key,requests,seconds,burst,instant);
        });
    }
"""
  position=text.rfind('}');templates[core]=text[:position]+bridge+text[position:]

  templates['backend/src/main/java/acp/api/IntakeController.java']=(TEMPLATES/'IntakeController.java').read_text().replace('${INTAKE_PATH}',contract['path'])
  templates['backend/src/main/resources/acp-intake-preview.json']=json.dumps(contract,sort_keys=True)
  templates['frontend/src/IntakeForm.vue']=(TEMPLATES/'IntakeForm.vue').read_text().replace('${CONTRACT}',json.dumps(contract,sort_keys=True))
  app=templates['frontend/src/App.vue'];require(app.count('<script setup lang="ts">')==1 and app.count('<template>')==1,'INTAKE_UI_TEMPLATE_DRIFT')
  app=app.replace('<script setup lang="ts">','<script setup lang="ts">\nimport IntakeForm from "./IntakeForm.vue";',1)
  head,tail=app.rsplit('</template>',1);templates['frontend/src/App.vue']=head+'<IntakeForm /></template>'+tail
  rows=self.base._generation.plan(payload['model'],templates,self.profile,payload['inventory'],build=payload['build'])
  creation={'backend/src/main/java/acp/infrastructure/InvocationCore.java','frontend/src/IntakeForm.vue','frontend/src/App.vue','backend/src/main/java/acp/api/IntakeController.java','backend/src/main/resources/acp-intake-preview.json'}
  whole={'contracts/target-ir.json','backend/src/main/resources/acp-model.json','frontend/src/model.ts','acp/provenance.json'}
  new_ids={contract['requirement'],contract['acceptance']}
  for row in rows:
   if row['path'] in creation:row['origins']=sorted(set(row['origins'])|new_ids)
   elif row['path'] not in whole:row['origins']=[id for id in row['origins'] if id not in new_ids]
   require(row['origins'],'INTAKE_ARTIFACT_WITHOUT_ORIGIN')
  # Precise applicable subsets: unchanged shared code is not falsely attributed
  # to new intake requirements. Full TargetIR remains in every input digest.
  sidecar=next(a for a in rows if a['path']=='acp/provenance.json');doc=json.loads(sidecar['text']);by_path={a['path']:a for a in rows}
  for mapping in doc['artifacts']:mapping['targetObjects']=['target_'+hashlib.sha256(id.encode()).hexdigest()[:24] for id in by_path[mapping['artifact']]['origins']]
  sidecar['text']=json.dumps(doc,sort_keys=True,separators=(',',':'))+'\n'
  self._verify();return rows
 def plan(self,snapshot,request,inventory=()):return _ownership(ProductionTarget.plan(self,self.lower(snapshot,request),request,inventory=inventory),inventory)
 def verify_materialized(self,root,plan,snapshot,request):return provenance.verify_plan_provenance(root,plan,provenance.read_provenance(Path(root)/'acp/provenance.json'),target=self.lower(snapshot,request),request=request)

def materialize(workspace):
 snapshot,contract,proposal_plan=proposal();c=IntakeCandidate();r=make_request(c,snapshot);p=c.plan(snapshot,r);root=Path(workspace);store=FilesystemArtifactStore(root);store.apply(p);c.verify_materialized(root,p,snapshot,r);return c,snapshot,r,p
