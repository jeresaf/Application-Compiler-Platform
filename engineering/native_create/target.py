"""Native CREATE target adapter over the existing deterministic execution backend.

The legacy renderer is a versioned backend ABI, not a Canonical admission path.
Its temporary render view is never exported as the specification identity.
"""
import hashlib,json
from dataclasses import replace
from pathlib import Path
from engineering.native_create import semantics
from engineering.native_create.schema import FEATURE,KINDS,CONTRACTS
from engineering.reference_application.intake import IntakeCandidate
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
from engineering.generator_candidates.spring_vue_postgres_0_6 import provenance
from engineering.source_intelligence.model import require,sha,encode
from compiler_contracts import Document
from compiler_reference import SyntheticTarget
from compiler_core import _ownership
from target_worker import ProductionTarget

ROOT=Path(__file__).resolve().parents[2]
PROFILE='acp-native-create-preview-target/1'
GENERATOR='acp-native-create-preview-generator/1'


def source_digest():
    paths=[*sorted(Path(__file__).parent.glob('*.py')),
           *sorted(CONTRACTS.glob('*.json')),
           ROOT/'engineering/reference_application/intake.py',
           *sorted((ROOT/'engineering/reference_application/intake_templates').glob('*'))]
    return sha(encode({str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in paths if p.is_file()}))


def lower_create(snapshot,model):
    semantics.validate_snapshot(snapshot)
    nodes={n['id']:n for n in snapshot['content']['nodes']}
    operations=[n for n in nodes.values() if n['kind']=='CreateOperation']
    require(len(operations)==1,'CREATE_TARGET_SINGLE_OPERATION')
    op=operations[0];d=op['data'];permission=nodes[d['permission']['id']]
    forms=[n for n in nodes.values() if n['kind']=='CreateForm' and n['data']['operation']['id']==op['id']]
    require(len(forms)==1,'CREATE_TARGET_SINGLE_FORM')
    table=next(t for t in model['tables'] if t['origin']['id']==d['resource']['id'])
    by_column={c['origin']['id']:c for c in table['columns']}
    principal_field=nodes[d['principal']['id']]['data']['type']
    require(principal_field['kind']=='Identifier','CREATE_PRINCIPAL_TYPE')
    principal=next(t for t in model['tables'] if t['origin']['id']==principal_field['entity']['id'])
    pd=principal['semantic'];require(len(pd['identity'])==1 and pd['tenancy']=='SCOPED','CREATE_PRINCIPAL_STORAGE')
    fields=[d[k]['id'] for k in ('identity','tenant','principal')];inputs={};ordered=[]
    for identity,b in d['bindings'].items():
        require(by_column[identity]['sqlType']=='bytea','CREATE_STORAGE')
        if b['kind']=='INPUT':
            require(not nodes[identity]['data']['optional'],'CREATE_OPTIONAL_INPUT_UNSUPPORTED')
            inputs[b['name']]={'field':identity,'member':b['member']['id'] if b['member'] else None,
                               'minLength':b['minimumLength'],'maxLength':b['maximumLength']}
            if identity!=d['identity']['id']:
                fields.append(identity);ordered.append({'name':b['name'],**inputs[b['name']]})
    # Every persisted field has an explicit native semantic binding.
    columns=[by_column[i]['name'] for i in fields]
    sqlid=lambda i:'f_'+hashlib.sha256(i.encode()).hexdigest()[:24]
    req=next(n['id'] for n in nodes.values() if n['kind']=='Requirement' and {'id':n['id'],'revision':n['revision']} in op['basis'])
    ac=next(n['id'] for n in nodes.values() if n['kind']=='AcceptanceCriterion' and {'id':n['id'],'revision':n['revision']} in op['basis'])
    return {'schema':'acp-native-create-target/1','scope':'SYNTHETIC_PREVIEW_ONLY',
        'requirement':req,'acceptance':ac,'operation':op['id'],'revision':op['revision'],
        'resource':d['resource'],'resourceLabel':nodes[d['resource']['id']]['name'].replace('_',' ').title(),'controls':forms[0]['data']['controls'],'permission':permission['id'],'form':forms[0]['id'],
        'actor':permission['data']['actor'],'authorizationScope':permission['data']['scope'],
        'role':permission['data']['role']['id'],'identityBinding':d['bindings'][d['identity']['id']],
        'path':'/api/create_'+hashlib.sha256(op['id'].encode()).hexdigest()[:24],
        'initialState':d['initialState']['id'],'inputs':inputs,'orderedInputs':ordered,
        'writtenFields':fields+[v['member'] for v in ordered if v['member']],
        'idempotencySeconds':d['idempotency']['windowSeconds'],
        'rate':{k:d['rate'][k] for k in ('requests','windowSeconds','burst')},
        'insertSQL':f"INSERT INTO {table['name']}({','.join(columns)},acp_state) VALUES({','.join('?' for _ in fields)},'{d['initialState']['id']}')",
        'principalSQL':f"SELECT count(*) FROM {principal['name']} WHERE {sqlid(pd['identity'][0]['id'])}=? AND {sqlid(pd['tenantField']['id'])}=?"}


class NativeTarget(IntakeCandidate):
    identity=PROFILE
    capabilities=(*SyntheticTarget.capabilities,'target.project-artifacts/1',FEATURE)
    def __init__(self):
        self.base=SuccessorCandidate();self.bundle=source_digest()
        self.generator=GENERATOR+'+sha256:'+self.bundle
        self._profile=Document.of({**self.base.profile,'profile':PROFILE,'generator':GENERATOR})
        self.targets={}
    @property
    def profile(self):return self._profile.read()
    def _verify(self):
        self.base._verify();require(source_digest()==self.bundle,'CREATE_SOURCE_CHANGED')
        require(self.profile=={**self.base.profile,'profile':PROFILE,'generator':GENERATOR},'CREATE_PROFILE_CHANGED')
    def lower(self,realization,request):
        self._verify()
        choices={d.role:d.choice.read().get('choice') for d in (*realization.architecture,*realization.design)}
        require(choices==self.profile['decisions'],'CREATE_ARCHITECTURE_DESIGN_BINDING')
        snapshot=realization.projections.snapshot.read()
        require(request.features==(FEATURE,) and request.snapshot_digest==snapshot['contentDigest'],'CREATE_TARGET_VERSION')
        # Explicit compatibility backend for the unchanged deterministic subgraph.
        legacy=semantics.legacy_snapshot(snapshot)
        old=self.base.lower(Document.of(legacy),compiler=request.compiler,pipeline=request.pipeline)
        model=old.target_model.read();nodes=snapshot['content']['nodes']
        model.update(profile=PROFILE,generator=GENERATOR,canonicalVersion='0.4.0',
            semanticModelVersion='0.5.0',requiredCapabilities=[FEATURE,'semantic.execution-dataflow/0.3'],nodes=nodes,
            objects=[{'id':'target_'+hashlib.sha256(n['id'].encode()).hexdigest()[:24],
                      'role':n['kind'],'origin':{'id':n['id'],'revision':n['revision']}} for n in nodes])
        model['intakePreview']=lower_create(snapshot,model)
        create=model['intakePreview']
        model['api'].append({'origin':{'id':create['operation'],'revision':create['revision']},'path':create['path'],'method':'POST','role':'CreateOperation','permissions':[create['permission']],'semantic':next(n['data'] for n in nodes if n['id']==create['operation']),'errors':[202,400,401,403,409,429,500],'concurrency':'ONE_COMMITTED_CREATION','pagination':{'maximum':1}})
        neutral=SyntheticTarget.lower(self,realization,request)
        result=replace(neutral,target_model=Document.of(model))
        self.targets[(request.snapshot_digest,request.compiler,request.pipeline)]=result
        return result
    def _call(self,operation,payload):
        if operation!='plan':return super()._call(operation,payload)
        model=payload['model'];require(model['canonicalVersion']=='0.4.0','CREATE_RENDER_VERSION')
        view={**model,'canonicalVersion':'0.3.0'}
        rows=super()._call(operation,{**payload,'model':view})
        contract=model['intakePreview'];by_path={r['path']:r for r in rows}
        controller=by_path['backend/src/main/java/acp/api/IntakeController.java']
        text=controller['text']
        text=text.replace('public final class IntakeController {','public final class IntakeController {\n public static final String OPERATION_ID='+json.dumps(contract['operation'])+';')
        text=text.replace('&&n.path("data").path("role").path("id").asText().equals(contract.path("role").asText())',
          '&&n.path("data").path("role").path("id").asText().equals(contract.path("role").asText())&&n.path("data").path("actor").equals(contract.path("actor"))&&n.path("data").path("scope").equals(contract.path("authorizationScope"))')
        text=text.replace('SyntheticIntake','NativeCreate')
        text=text.replace('new InvocationCore.Call(operation,1,operation+"-IDEMPOTENCY",1,','new InvocationCore.Call(operation,'+str(contract['revision'])+',operation+"-IDEMPOTENCY",'+str(contract['revision'])+',')
        text=text.replace('syntheticToken(operation+"-RATE",1,','syntheticToken(operation+"-RATE",'+str(contract['revision'])+',')
        text=text.replace('String operation=contract.path("operation").asText();','String operation=OPERATION_ID;')
        text=text.replace('length<1||','length<f.getValue().path("minLength").asInt()||')
        identity=contract['identityBinding']
        if identity['kind']=='INPUT':
            text=text.replace('String id=UUID.randomUUID().toString();','String id=(String)values.get('+json.dumps(identity['name'])+');')
        # SQL uniqueness is an identity conflict, not an idempotency success.
        text=text.replace('jdbc.update(contract.path("insertSQL").asText(),parameters.toArray());',
            'try{jdbc.update(contract.path("insertSQL").asText(),parameters.toArray());}catch(org.springframework.dao.DuplicateKeyException e){throw new ResponseStatusException(HttpStatus.CONFLICT,"IDENTITY_CONFLICT");}')
        controller['text']=text
        form=by_path['frontend/src/IntakeForm.vue']
        form['text']=form['text'].replace('n>=1&&','n>=field.minLength&&')
        form['text']=form['text'].replace('v-for="(field,name) in contract.inputs"','v-for="name in contract.controls"')
        form['text']=form['text'].replace("message.value='Case created'","message.value=contract.resourceLabel+' created'")
        form['text']=form['text'].replace('Synthetic case intake','Native creation preview').replace('Create case — synthetic preview','Create {{contract.resourceLabel.toLowerCase()}} — native preview').replace('>Create case</button>','>Create {{contract.resourceLabel.toLowerCase()}}</button>')
        form['text']=form['text'].replace('const contract='+json.dumps(contract,sort_keys=True)+';', 'import {createContract as contract} from \"./create-contract\";')
        rows.append({'path':'frontend/src/create-contract.ts','role':'NATIVE_CREATE_CONTRACT','verification':['target-source-integrity'],'owner':'COMPILER_OWNED','origins':sorted({contract['operation'],contract['permission'],contract['form']}),'text':'export const operationId = '+json.dumps(contract['operation'])+' as const;\nexport const createContract = {...'+json.dumps(contract,sort_keys=True)+', operation: operationId} as const;\n'})
        by_path={r['path']:r for r in rows}
        # Export the actual native model and explicit rendering ABI identity.
        full=json.dumps(model,sort_keys=True,separators=(',',':'))+'\n'
        by_path['backend/src/main/resources/acp-model.json']['text']=full
        # Avoid a second full model copy: exact path+hash reference is the new ABI.
        by_path['contracts/target-ir.json']['text']=json.dumps({'schema':'acp-native-target-reference/1',
            'path':'backend/src/main/resources/acp-model.json','sha256':sha(full.encode()),
            'canonicalVersion':'0.4.0','renderBackend':'deterministic-execution/0.3'},sort_keys=True)+'\n'
        for row in rows:
            if row['path']=='acp/target-upgrade.json':
                row['text']=json.dumps({'schema':'acp-native-create-preview-upgrade/1','scope':'QUALIFICATION_ONLY','from':None,'to':{'canonicalVersion':'0.4.0','generator':GENERATOR},'migration':'NOT_AUTHORIZED','existingDatabaseUpgrade':'UNSUPPORTED'},sort_keys=True)+'\n'
            if row['path'].endswith('build.json'):
                doc=json.loads(row['text']);doc.update(canonicalVersion='0.4.0',semanticModelVersion='0.5.0',features=[FEATURE]);row['text']=json.dumps(doc,sort_keys=True)+'\n'
        native_ids={n['id'] for n in model['nodes'] if n['kind'] in KINDS}
        for row in rows:
            if row['path'] in {'backend/src/main/java/acp/api/IntakeController.java','frontend/src/IntakeForm.vue','frontend/src/App.vue','backend/src/main/resources/acp-intake-preview.json'}:
                row['origins']=sorted(set(row['origins'])|native_ids)
        side=by_path['acp/provenance.json'];doc=json.loads(side['text'])
        doc['build'].update(canonicalVersion='0.4.0',semanticModelVersion='0.5.0',features=[FEATURE],renderBackend='deterministic-execution/0.3')
        new=by_path['frontend/src/create-contract.ts']
        doc['artifacts'].append({'artifact':new['path'],'artifactDigest':'sha256:'+sha(new['text'].encode()),'generator':GENERATOR,'targetRole':new['role'],'ownership':new['owner'],'originSet':'canonical-model','targetObjects':[],'locations':[],'locationConfidence':'ARTIFACT_ONLY'})
        for entry in doc['artifacts']:
            entry['artifactDigest']='sha256:'+sha(by_path[entry['artifact']]['text'].encode())
            entry['targetObjects']=['target_'+hashlib.sha256(i.encode()).hexdigest()[:24] for i in by_path[entry['artifact']]['origins']]
        side['text']=json.dumps(doc,sort_keys=True,separators=(',',':'))+'\n'
        self._verify();return rows
    def plan(self,target,request,inventory=()):
        return _ownership(ProductionTarget.plan(self,target,request,inventory=inventory),inventory)
    def descriptor(self):
        return {'profile':PROFILE,'generator':self.generator,'scope':'QUALIFICATION_ONLY',
                'semanticApproval':'NOT_APPROVED','renderBackend':'deterministic-execution/0.3'}

    def verify_materialized(self,root,plan,snapshot,request):
        self._verify()
        semantics.validate_snapshot(snapshot.read())
        require(snapshot.read()['contentDigest']==request.snapshot_digest,'CREATE_VERIFY_IDENTITY')
        target=self.targets[(request.snapshot_digest,request.compiler,request.pipeline)]
        return provenance.verify_plan_provenance(root,plan,
            provenance.read_provenance(Path(root)/'acp/provenance.json'),target=target,request=request)
