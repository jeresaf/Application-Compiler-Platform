"""H6 operational adapter over the immutable H5 compiler/target."""
import hashlib,json
from dataclasses import replace
from pathlib import Path
from compiler_contracts import Document
from engineering.identity.target import IdentityTarget,source_digest as parent_digest
from engineering.source_intelligence.model import encode,sha,require
PACKAGE=Path(__file__).parent
PROFILE='acp-h6-operational-target/1';GENERATOR='acp-h6-operational-generator/1'
def source_digest():return sha(encode({'parent':parent_digest(),'files':{str(p.relative_to(PACKAGE)):sha(p.read_bytes()) for p in sorted(PACKAGE.rglob('*')) if p.is_file() and (p.suffix=='.java' or p.name in ('target.py','application.py'))}}))
def change(row,before,after):
    require(row['text'].count(before)==1,'H6_PARENT_MARKER_DRIFT');row['text']=row['text'].replace(before,after,1)
class OperationalTarget(IdentityTarget):
    identity=PROFILE
    def __init__(self):
        super().__init__();self.h5_bundle=self.bundle;require(self.h5_bundle=='c2f712a0411b1b75aec39ea47c43d28c4ea484a68496b5b4d695588c927e9615','H6_PARENT_IDENTITY');self.bundle=source_digest();self.generator=GENERATOR+'+sha256:'+self.bundle;self._profile=Document.of({**self.base.profile,'profile':PROFILE,'generator':GENERATOR})
    def _verify(self):
        self.base._verify();require(self.h5_bundle==parent_digest() and self.bundle==source_digest(),'H6_SOURCE_CHANGED');require(self.profile=={**self.base.profile,'profile':PROFILE,'generator':GENERATOR},'H6_PROFILE_CHANGED')
    def lower(self,realization,request):
        target=super().lower(realization,request);model=target.target_model.read();model.update(profile=PROFILE,generator=GENERATOR);target=replace(target,target=PROFILE,target_model=Document.of(model));self.targets[(request.snapshot_digest,request.compiler,request.pipeline)]=target;return target
    def _call(self,operation,payload):
        rows=super()._call(operation,payload)
        if operation!='plan':return rows
        by={r['path']:r for r in rows};nodes=payload['model']['nodes'];decisions=sorted(n['id'] for n in nodes if n['kind']=='Decision');origins=sorted(n['id'] for n in nodes if n['kind'] in {'Decision','AuthenticationModel','DataClassification','SessionPolicy','ObservabilityRequirement','IntegrityJob','Job','WorkerGrant'})
        require(decisions and origins,'H6_CONTROL_ORIGINS_REQUIRED')
        # These are declaration/pointer artifacts, not implementations of every
        # semantic object. The full runtime model retains all object mappings;
        # each artifact still binds the exact complete Target IR input digest.
        pointer=json.loads(by['contracts/target-ir.json']['text']);require(pointer['schema']=='acp-runtime-target-projection/1' and len(by['frontend/src/model.ts']['text'])<256,'H6_PROJECTION_POINTER_DRIFT')
        for path in ('contracts/target-ir.json','frontend/src/model.ts'):by[path]['origins']=decisions
        for name in ('OperationalConfiguration.java','OperationalRuntime.java'):
            path='backend/src/main/java/acp/operations/'+name;require(path not in by,'H6_PATH_COLLISION');row={'path':path,'text':(PACKAGE/'templates'/name).read_text(),'role':'OPERATIONAL_CONTROL','owner':'COMPILER_OWNED','origins':origins,'verification':['target-source-integrity']};rows.append(row);by[path]=row
        path='backend/src/main/resources/META-INF/spring.factories';require(path not in by,'H6_FACTORY_COLLISION');rows.append({'path':path,'text':'org.springframework.boot.EnvironmentPostProcessor=acp.operations.OperationalConfiguration\n','role':'OPERATIONAL_CONFIGURATION','owner':'COMPILER_OWNED','origins':origins,'verification':['target-source-integrity']});by[path]=rows[-1]
        properties=by['backend/src/main/resources/application.properties'];change(properties,'management.endpoints.web.exposure.include=health,info,metrics','management.endpoints.web.exposure.include=health,info')
        properties['text']+='\nmanagement.endpoint.health.group.readiness.include=readinessState,acpOperational\nmanagement.endpoint.health.group.liveness.include=livenessState\nmanagement.endpoint.health.group.dependencies.include=acpDatabase\nmanagement.endpoint.health.group.identity.include=acpIdentity\nmanagement.endpoint.health.group.worker.include=acpWorker\nmanagement.observations.enable.http.server.requests=false\nmanagement.metrics.enable.http.server.requests=false\nserver.shutdown=graceful\nspring.lifecycle.timeout-per-shutdown-phase=5s\nlogging.level.root=INFO\n'
        observable=by['backend/src/main/java/acp/security/Observability.java'];where=observable['text'].rfind('}')
        observable['text']=observable['text'][:where]+'''public void operational(String event,String correlation,String outcome,String origin){
if(!java.util.Set.of("STARTUP","MIGRATION","HTTP","AUTHENTICATION","AUTHORIZATION","DATABASE","TRANSACTION","IDEMPOTENCY","DOCUMENT","WORKFLOW","WORKER","READINESS","RECOVERY","SHUTDOWN").contains(event)||!java.util.Set.of("SUCCEEDED","DENIED","FAILED","COMMITTED","ROLLED_BACK","INDETERMINATE","REPLAYED","UP","DOWN","STARTED","STOPPED").contains(outcome)||!correlation.matches("[0-9a-f-]{36}")||!origin.matches("[A-Za-z0-9:_-]{1,128}")||!event.matches("[A-Z_]{1,24}")||!outcome.matches("[A-Z_]{1,24}"))throw new IllegalArgumentException("OPERATIONAL_METADATA");
int revision=origin.equals("OPERATIONAL_PROFILE")?0:privacy.model().node(origin).path("revision").asInt();metadata(Surface.LOG,Map.of());
try{org.slf4j.LoggerFactory.getLogger(Observability.class).info("ACP_OPERATIONAL {}",new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(Map.of("contract","acp-h6-operations/1","classificationContract",CONTRACT_VERSION,"event",event,"correlation",correlation,"outcome",outcome,"origin",origin,"originRevision",revision)));}catch(com.fasterxml.jackson.core.JsonProcessingException invalid){throw new IllegalArgumentException("OPERATIONAL_METADATA");}
}
'''+observable['text'][where:]
        security=by['backend/src/main/java/acp/security/SecurityConfiguration.java'];change(security,'return decoder.decode(token);','Jwt verified=decoder.decode(token);acp.operations.OperationalRuntime.record("AUTHENTICATION","SUCCEEDED");return verified;');change(security,'}catch(Exception error){throw new BadJwtException','}catch(Exception error){acp.operations.OperationalRuntime.record("AUTHENTICATION","DENIED");throw new BadJwtException')
        worker=by['backend/src/main/java/acp/api/IntegrityWorker.java'];change(worker,' private void safe(Runnable r){try{r.run();}', ' private volatile long operationalPulse=System.nanoTime();\n public boolean operationalRunning(){return enabled&&!loops.isShutdown();}\n public long operationalPulseAgeSeconds(){return java.util.concurrent.TimeUnit.NANOSECONDS.toSeconds(System.nanoTime()-operationalPulse);}\n public Set<String> operationalTenants(){return authority.tenants();}\n private void safe(Runnable r){operationalPulse=System.nanoTime();try{r.run();}')
        change(worker,' private void terminal(Map<String,Object> row,String status,String actual){',' private void terminal(Map<String,Object> row,String status,String actual){acp.operations.OperationalRuntime.observeWorkerResult(status.equals("VALID"));')
        document=by['backend/src/main/java/acp/api/DocumentController.java'];change(document,'private void audit(Jwt jwt,String resource,String operation,String id,String hash){','private void audit(Jwt jwt,String resource,String operation,String id,String hash){acp.operations.OperationalRuntime.observeTransaction();')
        change(worker,'public void execute(Claim q){authorize(q.tenant());','public void execute(Claim q){authorize(q.tenant());acp.operations.OperationalRuntime.beginWorker();')
        change(worker,'finally{executor.shutdownNow();}}','finally{executor.shutdownNow();acp.operations.OperationalRuntime.endWorker();}}')
        invocation=by['backend/src/main/java/acp/infrastructure/InvocationCore.java'];change(invocation,'recordJobAttempt(jobAttempt,"COMMITTED",null);return completed;','acp.operations.OperationalRuntime.record("TRANSACTION","COMMITTED");if(claims.stream().anyMatch(claim->claim.owner()!=null)){acp.operations.OperationalRuntime.record("IDEMPOTENCY","COMMITTED");acp.operations.OperationalRuntime.record("WORKFLOW","SUCCEEDED");}recordJobAttempt(jobAttempt,"COMMITTED",null);return completed;')
        change(invocation,'recordJobAttempt(jobAttempt,rollback[0]?"ROLLED_BACK":"INDETERMINATE",error instanceof SemanticFailure f?f:null);','acp.operations.OperationalRuntime.record("TRANSACTION",rollback[0]?"ROLLED_BACK":"INDETERMINATE");recordJobAttempt(jobAttempt,rollback[0]?"ROLLED_BACK":"INDETERMINATE",error instanceof SemanticFailure f?f:null);')
        change(invocation,'try {return new Claim(call,identity,null,mapper.readTree(ExecutionStore.text((byte[])row.get("result"))));}','try {acp.operations.OperationalRuntime.record("IDEMPOTENCY","REPLAYED");return new Claim(call,identity,null,mapper.readTree(ExecutionStore.text((byte[])row.get("result"))));}')
        upgrade=json.loads(by['acp/target-upgrade.json']['text']);upgrade.update(schema='acp-h6-operational-preview-upgrade/1',candidateGenerator=GENERATOR);by['acp/target-upgrade.json']['text']=json.dumps(upgrade,sort_keys=True)+'\n'
        doc=json.loads(by['acp/provenance.json']['text']);doc['build']['generator']=GENERATOR;known={r['artifact'] for r in doc['artifacts']}
        for row in rows:
            if row['path'] not in known and row['path']!='acp/provenance.json':doc['artifacts'].append({'artifact':row['path'],'generator':GENERATOR,'targetRole':row['role'],'ownership':row['owner'],'originSet':'canonical-model','locations':[],'locationConfidence':'ARTIFACT_ONLY'})
        for entry in doc['artifacts']:
            row=by[entry['artifact']];entry.update(generator=GENERATOR,artifactDigest='sha256:'+sha(row['text'].encode()),targetObjects=['target_'+hashlib.sha256(i.encode()).hexdigest()[:24] for i in row['origins']])
        by['acp/provenance.json']['text']=json.dumps(doc,sort_keys=True,separators=(',',':'))+'\n';self._verify();return rows
    def descriptor(self):
        self._verify();return {'profile':PROFILE,'generator':self.generator,'parentSourceDigest':self.h5_bundle,'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED','operationalApproval':'NOT_APPROVED'}
