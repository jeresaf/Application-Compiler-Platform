"""H9 transport-only successor. Historical runtime and fault maps stay immutable."""
from dataclasses import replace
from pathlib import Path
import json,hashlib
from compiler_contracts import Document
from engineering.operations.target import OperationalTarget,source_digest as parent_digest
from engineering.source_intelligence.model import sha,encode,require
PACKAGE=Path(__file__).parent
PROFILE='acp-h9-http-target/1';GENERATOR='acp-h9-http-generator/1'
PARENT='9bdc1adcbc50789421bd58a8f0909741031f20cd68bb66f0a6e1a205586dbfc1'
def source_digest():return sha(encode({'parent':parent_digest(),'files':{n:sha((PACKAGE/n).read_bytes()) for n in ('target.py','application.py','compatibility.json')}}))
class HttpTarget(OperationalTarget):
    identity=PROFILE
    def __init__(self):
        super().__init__();self.h6_bundle=self.bundle;require(self.h6_bundle==PARENT,'H9_PARENT_IDENTITY');self.bundle=source_digest();self.generator=GENERATOR+'+sha256:'+self.bundle;self._profile=Document.of({**self.base.profile,'profile':PROFILE,'generator':GENERATOR})
    def _verify(self):
        self.base._verify();require(self.h6_bundle==parent_digest()==PARENT and self.bundle==source_digest(),'H9_SOURCE_CHANGED');require(self.profile=={**self.base.profile,'profile':PROFILE,'generator':GENERATOR},'H9_PROFILE_CHANGED')
    def lower(self,realization,request):
        target=super().lower(realization,request);model=target.target_model.read();model.update(profile=PROFILE,generator=GENERATOR);target=replace(target,target=PROFILE,target_model=Document.of(model));self.targets[(request.snapshot_digest,request.compiler,request.pipeline)]=target;return target
    def _call(self,operation,payload):
        rows=super()._call(operation,payload)
        if operation!='plan':return rows
        by={r['path']:r for r in rows};row=by['backend/src/main/java/acp/api/Errors.java'];marker='var mapped=FailureMapping.map(error);';require(row['text'].count(marker)==1,'H9_HANDLER_DRIFT')
        contract=json.loads((PACKAGE/'compatibility.json').read_bytes());require(contract['exactException']=='org.springframework.web.servlet.resource.NoResourceFoundException' and contract['response']=={'status':404,'code':'RESOURCE_NOT_FOUND','category':'HTTP','retryable':False},'H9_HTTP_CONTRACT')
        row['text']=row['text'].replace(marker,'if(error.getClass()==org.springframework.web.servlet.resource.NoResourceFoundException.class) return ResponseEntity.status(404).body(new ErrorResponse("RESOURCE_NOT_FOUND","HTTP",false));\n        '+marker,1)
        upgrade=json.loads(by['acp/target-upgrade.json']['text']);upgrade.update(schema='acp-h9-http-preview-upgrade/1',candidateGenerator=GENERATOR);by['acp/target-upgrade.json']['text']=json.dumps(upgrade,sort_keys=True)+'\n'
        doc=json.loads(by['acp/provenance.json']['text']);doc['build']['generator']=GENERATOR
        for entry in doc['artifacts']:
            item=by[entry['artifact']];entry.update(generator=GENERATOR,artifactDigest='sha256:'+sha(item['text'].encode()),targetObjects=['target_'+hashlib.sha256(i.encode()).hexdigest()[:24] for i in item['origins']])
        by['acp/provenance.json']['text']=json.dumps(doc,sort_keys=True,separators=(',',':'))+'\n';self._verify();return rows
    def descriptor(self):
        self._verify();return {'profile':PROFILE,'generator':self.generator,'parentSourceDigest':self.h6_bundle,'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED','operationalApproval':'NOT_APPROVED'}
