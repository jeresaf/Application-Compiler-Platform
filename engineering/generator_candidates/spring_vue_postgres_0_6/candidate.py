"""Pure engineering candidate; no worker launch, approval, build or deployment."""
import hashlib
import importlib
import json
from pathlib import Path
import sys

from . import migrations, provenance, rate_clock

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[2]
WORKER = ROOT / 'targets/spring-vue-postgres/worker'
PROFILE_ID = 'acp-spring-vue-postgres/0.6.0'
GENERATOR_ID = 'acp-spring-vue-generator/0.6.0'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source_digest():
    files = {}
    for path in sorted(PACKAGE.iterdir()):
        if path.suffix not in {'.py', '.json'}:
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError('CANDIDATE_SOURCE_PATH')
        files[path.name] = digest(path.read_bytes())
    return digest(json.dumps(files, sort_keys=True, separators=(',', ':')).encode())


class SuccessorCandidate:
    """Explicit offline API, separate from the released ProductionTarget port.

    Reuses the released pure model/templates and ArtifactPlan adaptation with a
    new identity. No confinement, authority, runtime or release admission claim.
    """
    def __init__(self):
        from compiler_contracts import Document
        self._profile = Document.of(json.loads((PACKAGE / 'profile.json').read_text()))
        if self.profile['profile'] != PROFILE_ID or self.profile['generator'] != GENERATOR_ID:
            raise ValueError('CANDIDATE_IDENTITY')
        self._ancestry = Document.of(json.loads((PACKAGE / 'ancestry.json').read_text()))
        if self._ancestry.read()['status'] != 'UNSEALED_CANDIDATE':
            raise ValueError('CANDIDATE_STATE')
        self.bundle = source_digest()  # Observed source fingerprint, NOT a release seal.
        self.generator = GENERATOR_ID + '+sha256:' + self.bundle
        self._verify()
        # Only independently sealed parent code supplies the pure backend.
        sys.path.insert(0, str(WORKER))
        self._model = importlib.import_module('model')
        self._generation = importlib.import_module('generation')
        for module in (self._model, self._generation):
            if Path(module.__file__).resolve().parent != WORKER.resolve():
                raise ValueError('CANDIDATE_BACKEND_SOURCE')

    @property
    def profile(self):
        return self._profile.read()

    def _verify(self):
        from target_worker import bundle_digest, PROFILE
        from target_release import verify_release
        ancestry = self._ancestry.read()
        if source_digest() != self.bundle:
            raise ValueError('CANDIDATE_SOURCE_CHANGED')
        registry = ROOT / 'targets/spring-vue-postgres/release-contract.json'
        if digest(registry.read_bytes()) != ancestry['releaseContractSHA256']:
            raise ValueError('PARENT_RELEASE_CONTRACT_CHANGED')
        parent = bundle_digest()
        verify_release(PROFILE, parent)
        if parent != ancestry['parentBundleDigest'] or PROFILE['profile'] != ancestry['parentProfile']:
            raise ValueError('PARENT_RELEASE_CHANGED')
        expected = {**PROFILE, 'profile': PROFILE_ID, 'generator': GENERATOR_ID}
        if self.profile != expected:
            raise ValueError('CANDIDATE_PROFILE_CONTRACT')
        for name, binding in ancestry['corrections'].items():
            if digest((PACKAGE / name).read_bytes()) != binding['sha256']:
                raise ValueError('V3_CORRECTION_CHANGED')

    def descriptor(self):
        self._verify()
        return {'profile': PROFILE_ID, 'generator': self.generator,
                'status': 'UNSEALED_CANDIDATE', 'sourceDigest': self.bundle,
                'sourceCommit': self._ancestry.read()['sourceCommit'],
                'parentBundleDigest': self._ancestry.read()['parentBundleDigest'],
                'productionAdmission': 'NOT_AUTHORIZED', 'runtime': 'NOT_PROVEN'}

    def lower(self, snapshot, *, compiler, pipeline):
        from canonical_ir import validate_snapshot
        from compiler_contracts import Derived, Document, Provenance, Stage, Subject, TargetIR
        self._verify()
        value = snapshot.read()
        validate_snapshot(value)
        nodes, version = value['content']['nodes'], value['content']['schemaVersion']
        required = ['semantic.execution-dataflow/0.3'] if version in {'0.2.0', '0.3.0'} else []
        if version == '0.3.0':
            required.append('acp.deterministic-execution.0.4')
        self._model.negotiate(nodes, required, self.profile['decisions'], self.profile, version)
        model = self._model.lower(nodes, self.profile, version)
        objects = tuple(Derived(node['id'], 'LOWER', Document.of(node), Provenance(
            (Subject(value['content']['applicationId'], node['id'], node['revision']),),
            Stage.LOWER, compiler, pipeline, (value['contentDigest'],))) for node in nodes)
        self._verify()
        return TargetIR(PROFILE_ID, objects, (), (), target_model=Document.of(model))

    def _call(self, operation, payload):
        self._verify()
        if operation == 'plan':
            if payload['build']['bundleDigest'] != 'sha256:' + self.bundle:
                raise ValueError('CANDIDATE_BUILD_IDENTITY')
            templates = {p.relative_to(WORKER.parent / 'templates').as_posix(): p.read_text()
                         for p in (WORKER.parent / 'templates').rglob('*') if p.is_file()}
            templates = rate_clock.apply(templates)
            result = self._generation.plan(payload['model'], templates, self.profile,
                                           payload['inventory'], build=payload['build'])
            self._generation.validate_plan(result)
        elif operation == 'validate-plan':
            result = self._generation.validate_plan(payload['artifacts'])
        else:
            raise ValueError('CANDIDATE_OPERATION')
        self._verify()
        return result

    def plan(self, snapshot, request, *, inventory=()):
        from target_worker import ProductionTarget
        if request.generator != self.generator or request.snapshot_digest != snapshot.read()['contentDigest']:
            raise ValueError('CANDIDATE_REQUEST_IDENTITY')
        target = self.lower(snapshot, compiler=request.compiler, pipeline=request.pipeline)
        # Shared host ArtifactPlan adaptation; no ProductionTarget construction,
        # release bypass, worker launch or production registration.
        return ProductionTarget.plan(self, target, request, inventory=inventory)

    def plan_upgrade(self, previous, current, accepted_plan, bindings, history):
        self._verify()
        result = migrations.plan_upgrade(previous, current, accepted_plan, bindings, history)
        self._verify()
        return result

    def verify_materialized(self, root, plan, snapshot, request, *, required_origins=()):
        if request.generator != self.generator or request.snapshot_digest != snapshot.read()['contentDigest']:
            raise ValueError('CANDIDATE_REQUEST_IDENTITY')
        target = self.lower(snapshot, compiler=request.compiler, pipeline=request.pipeline)
        document = provenance.read_provenance(Path(root) / 'acp/provenance.json')
        return provenance.verify_plan_provenance(root, plan, document, target=target,
                                                request=request, required_origins=required_origins)
