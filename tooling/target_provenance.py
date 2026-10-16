"""Digest-bound generated artifact maps; no general source intelligence."""
from pathlib import Path
import hashlib


def _origins(value):
    if (type(value) is not list or not value or any(type(o) is not dict or set(o) != {"id", "revision"}
        or type(o["id"]) is not str or not o["id"] or type(o["revision"]) is not int or o["revision"] < 1 for o in value)
        or len({o["id"] for o in value}) != len(value)):
        raise ValueError("PROVENANCE_ORIGINS")
    return {(o["id"], o["revision"]) for o in value}


def _target_id(origin):
    return "target_" + hashlib.sha256(origin.encode()).hexdigest()[:24]


from compiler_core import safe_path
from filesystem_artifacts import byte_digest


def inspect_mapping(root, mapping, *, semantic_revisions=None):
    try:
        _origins(mapping['origins'])
        if mapping.get('locationConfidence') not in {'ARTIFACT_ONLY', 'EXACT_TEST_FIXTURE'} or type(mapping.get('locations')) is not list:
            raise ValueError('PROVENANCE_CONFIDENCE')
        if mapping['locationConfidence'] == 'ARTIFACT_ONLY' and mapping['locations']:
            raise ValueError('PROVENANCE_CONFIDENCE')
    except (KeyError, TypeError, ValueError):
        return {'status': 'INVALID_MAPPING', 'locations': []}
    relative = safe_path(mapping["artifact"])
    root = Path(root).absolute()
    path = root / relative
    for ancestor in (path, *path.parents):
        if ancestor.is_symlink():
            return {"status": "UNTRUSTED_PATH", "locations": []}
        if ancestor == root:
            break
    if not path.is_file() or byte_digest(path.read_bytes()) != mapping["artifactDigest"]:
        return {"status": "STALE_ARTIFACT", "locations": []}
    if semantic_revisions is not None and any(semantic_revisions.get(origin["id"]) != origin["revision"] for origin in mapping["origins"]):
        return {"status": "STALE_SEMANTICS", "locations": []}
    return {"status": "CURRENT", "locations": mapping["locations"], "confidence": mapping["locationConfidence"]}


def read_provenance(path):
    """Expand exact versioned origin sets; old 0.2 sidecars remain readable."""
    import json
    value=json.loads(Path(path).read_text())
    if value['version']=='0.3.0':
        sets=value['originSets']
        for mapping in value['artifacts']:
            key=mapping['originSet']
            if key not in sets:raise ValueError('PROVENANCE_ORIGIN_SET')
            origins=sets[key]
            _origins(origins)
            # The shared set is a dictionary, not each artifact's origin list.
            # Current generator output identifies its applicable subset here.
            if 'targetObjects' in mapping:
                targets = mapping['targetObjects']
                index = {_target_id(o['id']): o for o in origins}
                if (type(targets) is not list or not targets or any(type(t) is not str for t in targets)
                    or len(set(targets)) != len(targets) or any(t not in index for t in targets)):
                    raise ValueError('PROVENANCE_TARGET_OBJECTS')
                origins = [index[t] for t in targets]
            # Retain compatibility for older v0.3 records without targetObjects;
            # strict plan verification below still requires exact applicable IDs.
            mapping['origins']=origins
    elif value['version']!='0.2.0':raise ValueError('PROVENANCE_VERSION')
    return value


def verify_plan_provenance(root, plan, document, *, target, request, required_origins=()):
    """Reconcile expanded sidecars with a trusted host plan/TargetIR/request.

    Pure offline integrity checking, NOT authority/admission or runtime proof.
    HUMAN paths omitted by the generator are not blanket-exempted mappings:
    callers must scope required_origins to genuinely generated semantic objects.
    The provenance sidecar itself is the sole non-self-referential artifact.
    """
    from compiler_contracts import Owner, Stage, fingerprint
    from filesystem_artifacts import FilesystemArtifactStore, source_bytes
    artifacts = {a.path: a for a in plan.artifacts}
    if len(artifacts) != len(plan.artifacts):
        raise ValueError('PROVENANCE_DUPLICATE_ARTIFACT')
    inventory = {a.path: a for a in FilesystemArtifactStore(root).inventory()}
    nodes = {o.provenance.origins[0].id: o for o in target.objects}
    revisions = {n['id']: n['revision'] for n in target.target_model.read()['nodes']}
    if document['build']['canonicalSnapshotDigest'] != request.snapshot_digest or document['build']['generator'] != request.generator.split('+sha256:')[0]:
        raise ValueError('PROVENANCE_BUILD')
    mappings = {}
    for mapping in document['artifacts']:
        path = mapping['artifact']
        if path in mappings:
            raise ValueError('PROVENANCE_DUPLICATE_ARTIFACT')
        mappings[path] = mapping
    expected_paths = {p for p,a in artifacts.items() if not (p == 'acp/provenance.json' and a.role == 'PROVENANCE')}
    if set(mappings) != expected_paths:
        raise ValueError('PROVENANCE_ARTIFACT_COVERAGE')
    covered = set()
    for path, artifact in artifacts.items():
        if artifact.content_digest != fingerprint(artifact.content, 'artifact-content') or 'target-source-integrity' not in artifact.verification:
            raise ValueError('PROVENANCE_ARTIFACT')
        if type(artifact.owner) is not Owner or path not in inventory or inventory[path].owner != artifact.owner or inventory[path].digest != artifact.content_digest:
            raise ValueError('PROVENANCE_OWNERSHIP')
        origins = {(o.id,o.revision) for o in artifact.mappings}
        if (not origins or len(origins) != len(artifact.mappings) or artifact.mappings != artifact.provenance.origins
            or any(revisions.get(id) != rev or id not in nodes or nodes[id].provenance.origins != (origin,)
                   for origin in artifact.mappings for id,rev in ((origin.id,origin.revision),))):
            raise ValueError('PROVENANCE_PLAN_ORIGINS')
        expected_inputs = tuple(sorted((*[fingerprint(nodes[o.id]) for o in artifact.mappings],
            fingerprint(target.target_model,'target-model'),fingerprint(request.generator,'generator-manifest'))))
        if artifact.provenance.stage != Stage.GENERATE or artifact.provenance.inputs != expected_inputs or artifact.provenance.compiler != request.compiler or artifact.provenance.pipeline != request.pipeline:
            raise ValueError('PROVENANCE_INPUTS')
        if byte_digest((Path(root)/path).read_bytes()) != byte_digest(source_bytes(artifact.content)):
            raise ValueError('PROVENANCE_BYTES')
        if path not in mappings:
            continue
        mapping = mappings[path]
        if (_origins(mapping['origins']) != origins or mapping.get('ownership') != str(artifact.owner)
            or mapping.get('targetRole') != artifact.role or mapping.get('generator') != document['build']['generator']):
            raise ValueError('PROVENANCE_MAPPING_BINDING')
        if inspect_mapping(root,mapping,semantic_revisions=revisions)['status'] != 'CURRENT':
            raise ValueError('PROVENANCE_MAPPING_INTEGRITY')
        covered.update(origins)
    required = {(o.id,o.revision) for o in required_origins}
    if not required <= covered:
        raise ValueError('PROVENANCE_SEMANTIC_COVERAGE')
    return {'status':'VERIFIED_OFFLINE','artifacts':len(mappings),'origins':len(covered),
            'verification':sorted({v for a in plan.artifacts for v in a.verification}),
            'runtime':'NOT_PROVEN'}
