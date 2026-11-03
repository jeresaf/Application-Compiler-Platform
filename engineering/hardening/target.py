"""H1 unsealed successor: explicit plugin dependency overrides, no release promotion."""
import json
from dataclasses import replace
from pathlib import Path

from compiler_contracts import Document
from engineering.jobs.target import JobTarget, source_digest as parent_digest
from engineering.source_intelligence.model import encode, require, sha

PACKAGE = Path(__file__).parent
PROFILE = 'acp-h1-job-preview-target/1'
GENERATOR = 'acp-h1-job-preview-generator/1'
# Commons IO 2.11.0 enters several plugin realms through maven-shared-utils.
# Project dependencyManagement does not govern those realms.
PLUGIN_VERSIONS = {
    'maven-clean-plugin': '3.5.0',
    'maven-compiler-plugin': '3.15.0',
    'maven-deploy-plugin': '3.1.4',
    'maven-install-plugin': '3.1.4',
    'maven-jar-plugin': '3.5.1',
    'maven-resources-plugin': '3.5.0',
    'maven-site-plugin': '3.22.0',
    'maven-surefire-plugin': '3.5.6',
    'maven-dependency-plugin': '3.10.0',
    'spring-boot-maven-plugin': '4.1.1',
}


def source_digest():
    return sha(encode({'parent': parent_digest(), 'files': {
        name: sha((PACKAGE/name).read_bytes()) for name in ('target.py', 'application.py')}}))


def harden_pom(text):
    require(text.count('<build><plugins>') == 1 and '<pluginManagement>' not in text,
            'H1_PARENT_POM_DRIFT')
    dependency = ('<dependencies><dependency><groupId>commons-io</groupId>'
                  '<artifactId>commons-io</artifactId><version>2.22.0</version>'
                  '</dependency></dependencies>')
    plugins = ''.join('<plugin><groupId>'+('org.springframework.boot' if name ==
                      'spring-boot-maven-plugin' else 'org.apache.maven.plugins')+'</groupId>'
                      '<artifactId>'+name+'</artifactId><version>'+version+'</version>'
                      +dependency+'</plugin>' for name, version in sorted(PLUGIN_VERSIONS.items()))
    return text.replace('<build><plugins>', '<build><pluginManagement><plugins>'+plugins+
                        '</plugins></pluginManagement><plugins>', 1)


class HardeningTarget(JobTarget):
    identity = PROFILE

    def __init__(self):
        # Parent initialization performs no dynamic verification.
        super().__init__()
        self.parent_bundle = self.bundle
        self.bundle = source_digest()
        self.generator = GENERATOR+'+sha256:'+self.bundle
        self._profile = Document.of({**self.base.profile, 'profile': PROFILE, 'generator': GENERATOR})

    def _verify(self):
        self.base._verify()
        require(self.parent_bundle == parent_digest() and self.bundle == source_digest(),
                'H1_SOURCE_CHANGED')
        require(self.profile == {**self.base.profile, 'profile': PROFILE, 'generator': GENERATOR},
                'H1_PROFILE_CHANGED')

    def lower(self, realization, request):
        target = super().lower(realization, request)
        model = target.target_model.read()
        model.update(profile=PROFILE, generator=GENERATOR)
        target = replace(target, target=PROFILE, target_model=Document.of(model))
        self.targets[(request.snapshot_digest, request.compiler, request.pipeline)] = target
        return target

    def _call(self, operation, payload):
        rows = super()._call(operation, payload)
        if operation != 'plan':
            return rows
        by = {r['path']: r for r in rows}
        by['backend/pom.xml']['text'] = harden_pom(by['backend/pom.xml']['text'])
        side = by['acp/provenance.json']
        doc = json.loads(side['text'])
        doc['build']['generator'] = GENERATOR
        for artifact in doc['artifacts']:
            artifact.update(generator=GENERATOR,
                            artifactDigest='sha256:'+sha(by[artifact['artifact']]['text'].encode()))
        side['text'] = json.dumps(doc, sort_keys=True, separators=(',', ':'))+'\n'
        self._verify()
        return rows

    def descriptor(self):
        self._verify()
        return {'profile': PROFILE, 'generator': self.generator, 'scope': 'QUALIFICATION_ONLY',
                'semanticApproval': 'NOT_APPROVED', 'parentSourceDigest': self.parent_bundle}
