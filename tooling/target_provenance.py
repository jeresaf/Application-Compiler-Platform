"""Digest-bound generated artifact maps; no general source intelligence."""
from pathlib import Path

from compiler_core import safe_path
from filesystem_artifacts import byte_digest


def inspect_mapping(root, mapping, *, semantic_revisions=None):
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
            if not origins or len({o['id'] for o in origins})!=len(origins) or any(type(o['revision']) is not int or o['revision']<1 for o in origins):raise ValueError('PROVENANCE_ORIGINS')
            mapping['origins']=origins
    elif value['version']!='0.2.0':raise ValueError('PROVENANCE_VERSION')
    return value
