"""Additive H5 successor over H1. Prior generator identities remain immutable."""
import json
from pathlib import Path
from dataclasses import replace
from compiler_contracts import Document
from engineering.hardening.target import HardeningTarget,source_digest as parent_digest
from engineering.source_intelligence.model import sha,encode,require
PACKAGE=Path(__file__).parent
PROFILE='acp-h5-identity-target/1';GENERATOR='acp-h5-identity-generator/1'

def source_digest():return sha(encode({'parent':parent_digest(),'files':{n:sha((PACKAGE/n).read_bytes()) for n in ('target.py','application.py','templates/SecurityConfiguration.java')}}))

class IdentityTarget(HardeningTarget):
    identity=PROFILE
    def __init__(self):
        super().__init__();self.h1_bundle=self.bundle;self.bundle=source_digest();self.generator=GENERATOR+'+sha256:'+self.bundle;self._profile=Document.of({**self.base.profile,'profile':PROFILE,'generator':GENERATOR})
    def _verify(self):
        self.base._verify();require(self.h1_bundle==parent_digest() and self.bundle==source_digest(),'H5_SOURCE_CHANGED');require(self.profile=={**self.base.profile,'profile':PROFILE,'generator':GENERATOR},'H5_PROFILE_CHANGED')
    def lower(self,realization,request):
        target=super().lower(realization,request);model=target.target_model.read();model.update(profile=PROFILE,generator=GENERATOR);target=replace(target,target=PROFILE,target_model=Document.of(model));self.targets[(request.snapshot_digest,request.compiler,request.pipeline)]=target;return target
    def _call(self,operation,payload):
        # H1's renderer checks its own _verify through this versioned instance.
        rows=super()._call(operation,payload)
        if operation!='plan':return rows
        by={r['path']:r for r in rows};row=by['backend/src/main/java/acp/security/SecurityConfiguration.java'];row['text']=(PACKAGE/'templates/SecurityConfiguration.java').read_text()
        bootstrap=by['backend/src/main/java/acp/infrastructure/RuntimeBootstrap.java']
        marker='handles.put(JobRuntime.principalKey(id,job.path("revision").asInt()),handle);var jwt='
        require(bootstrap['text'].count(marker)==1,'H5_DISABLED_JOB_BINDING_DRIFT')
        bootstrap['text']=bootstrap['text'].replace(marker,'handles.put(JobRuntime.principalKey(id,job.path("revision").asInt()),handle);if("development".equals(env.getProperty("acp.runtime.mode"))&&!env.getProperty("acp.runtime.poll-enabled",Boolean.class,true))continue;var jwt=',1)
        nodes={n['id']:n for n in payload['model']['nodes']};origins=set(row['origins'])
        for n in nodes.values():
            if n['kind']=='Actor':
                entity=nodes[n['data']['subject']['id']];origins|={n['id'],entity['id'],*(x['id'] for x in entity['data']['identity']),entity['data']['tenantField']['id']}
        row['origins']=sorted(origins)
        upgrade=json.loads(by['acp/target-upgrade.json']['text']);upgrade.update(schema='acp-h5-identity-preview-upgrade/1',candidateGenerator=GENERATOR);by['acp/target-upgrade.json']['text']=json.dumps(upgrade,sort_keys=True)+'\n'
        doc=json.loads(by['acp/provenance.json']['text']);doc['build']['generator']=GENERATOR
        import hashlib
        for entry in doc['artifacts']:
            item=by[entry['artifact']];entry.update(generator=GENERATOR,artifactDigest='sha256:'+sha(item['text'].encode()),targetObjects=['target_'+hashlib.sha256(i.encode()).hexdigest()[:24] for i in item['origins']])
        by['acp/provenance.json']['text']=json.dumps(doc,sort_keys=True,separators=(',',':'))+'\n';self._verify();return rows
    def descriptor(self):
        self._verify();return {'profile':PROFILE,'generator':self.generator,'scope':'QUALIFICATION_ONLY','semanticApproval':'NOT_APPROVED','parentSourceDigest':self.h1_bundle}
