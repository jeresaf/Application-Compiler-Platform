"""H11 inventory and OSV observation for pinned inputs, with explicit coverage gaps."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import quote

from engineering.dependency_resolution.inputs import file_hash, npm_lock
from engineering.dependency_resolution.qualify import materialize
from engineering.security.qualification import (
    assess_response, embedded_component_inventory, https_json, save,
)

ROOT = Path(__file__).resolve().parents[2]
MAVEN = 'engineering/dependency_resolution/maven-artifacts.lock.json'
PYTHON = 'engineering/dependency_resolution/compiler-requirements.txt'
DIST = 'engineering/dependency_resolution/maven-distribution.json'


def maven_component(path, binding):
    parts = Path(path).parts
    if len(parts) < 4:
        raise ValueError('MAVEN_COORDINATE')
    group, name, version = '.'.join(parts[:-3]), parts[-3], parts[-2]
    prefix = f'{name}-{version}'
    if not (parts[-1] in (prefix + '.jar', prefix + '.pom')
            or parts[-1].startswith(prefix + '-') and parts[-1].endswith('.jar')):
        raise ValueError('MAVEN_ARTIFACT_IDENTITY')
    return {'ecosystem': 'Maven', 'name': group + ':' + name, 'version': version,
            'origin': path, 'sha256': binding['sha256'], 'lock': MAVEN,
            'scope': 'BUILD_OR_RUNTIME', 'relationship': 'SEE_LOCKED_GRAPHS'}


def inventory():
    lock = json.loads((ROOT / MAVEN).read_bytes())
    components = [maven_component(path, row) for path, row in sorted(lock['artifacts'].items())]
    embedded, unknown = embedded_component_inventory(lock['embeddedArtifacts'])
    components.extend(row | {'lock': MAVEN, 'scope': 'EMBEDDED'} for row in embedded)
    for line in (ROOT / PYTHON).read_text().splitlines():
        if not line or line.startswith('#'):
            continue
        pin, artifact_hash = line.split(' --hash=sha256:')
        name, version = pin.split('==')
        components.append({'ecosystem': 'PyPI', 'name': name, 'version': version,
                           'sha256': artifact_hash, 'lock': PYTHON, 'scope': 'COMPILER'})
    with tempfile.TemporaryDirectory(prefix='acp-h11-source-') as directory:
        for app in ('payment', 'case-management'):
            target = Path(directory) / app
            materialize(app, target)
            raw = (target / 'frontend/package-lock.json').read_bytes()
            entries = json.loads(raw)['packages']
            for path, row in npm_lock(raw).items():
                components.append({'ecosystem': 'npm', 'name': path.rsplit('node_modules/', 1)[-1],
                                   'version': row['version'], 'integrity': row['integrity'],
                                   'origin': row['resolved'], 'path': path, 'application': app,
                                   'lockSHA256': file_hash(target / 'frontend/package-lock.json'),
                                   'scope': 'BUILD' if entries[path].get('dev') else 'RUNTIME'})
    return components, unknown, lock


def scan(components, output, *, request=https_json):
    identities = sorted({(r['ecosystem'], r['name'], r['version']) for r in components})
    rows = [dict(ecosystem=e, name=n, version=v) for e, n, v in identities]
    findings = []
    advisories = {}

    def fetch(identity):
        if identity not in advisories:
            value = request('https://api.osv.dev/v1/vulns/' + quote(identity, safe=''))
            advisories[identity] = value
            save(output / f'advisory-{len(advisories)}.json', value)
        return advisories[identity]

    for start in range(0, len(rows), 100):
        batch = rows[start:start + 100]
        query = {'queries': [{'package': {'ecosystem': r['ecosystem'], 'name': r['name']},
                              'version': r['version']} for r in batch]}
        save(output / f'request-{start}.json', {'time': datetime.now(timezone.utc).isoformat(), 'body': query})
        try:
            response = request('https://api.osv.dev/v1/querybatch', query)
            save(output / f'response-{start}.json', response)
            findings.extend(assess_response(batch, response, fetch))
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            return {'status': 'SCANNER_UNAVAILABLE', 'failedBatchOffset': start,
                    'errorClass': type(error).__name__, 'httpStatus': getattr(error, 'code', None),
                    'findings': findings, 'requestedIdentities': len(rows)}
    return {'status': 'REQUIRES_TRIAGE' if findings else 'NO_MATCHES_IN_QUERIED_SCOPE',
            'findings': findings, 'requestedIdentities': len(rows)}


def sbom(components, scope):
    """CycloneDX inventory view. Completeness is deliberately marked incomplete."""
    entries = []
    for index, row in enumerate(components):
        component = {'type': 'library', 'bom-ref': f'{scope}:{index}',
                     'name': row['name'], 'version': row['version'],
                     'properties': [{'name': 'acp:ecosystem', 'value': row['ecosystem']}]}
        if 'sha256' in row:
            component['hashes'] = [{'alg': 'SHA-256', 'content': row['sha256']}]
        if 'integrity' in row:
            component['properties'].append({'name': 'acp:npm-integrity', 'value': row['integrity']})
        entries.append(component)
    return {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1,
            'components': entries,
            'compositions': [{'aggregate': 'incomplete', 'assemblies': [e['bom-ref'] for e in entries]}]}


def qualify(output):
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if (os.environ.get('GITHUB_SHA', commit) != commit
            or subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)):
        raise ValueError('SOURCE_BINDING')
    output.mkdir(parents=True, exist_ok=False)
    components, embedded_unknown, lock = inventory()
    save(output / 'inventory.json', {'components': components, 'sourceCommit': commit,
                                    'nativeTools': 'UNKNOWN_ACTUAL_CONSUMPTION',
                                    'distribution': json.loads((ROOT / DIST).read_bytes())})
    save(output / 'maven-graphs.json', {key: lock[key] for key in ('graphs', 'plugins') if key in lock})
    for scope, included in (
        ('compiler', [r for r in components if r['scope'] == 'COMPILER']),
        ('application-inputs', [r for r in components if r['scope'] != 'COMPILER']),
    ):
        save(output / (scope + '.cdx.json'), sbom(included, scope))
    save(output / 'license-register.json', {'status': 'BLOCKED_BY_EXTERNAL_EVIDENCE',
        'components': [row | {'licenseStatus': 'UNKNOWN_UNVERIFIED', 'legalReview': 'PENDING'}
                       for row in components]})
    save(output / 'assessment.json', {'sourceCommit': commit, 'SEC-01': 'BLOCKED', 'SEC-02': 'BLOCKED',
        'scanEndpoint': 'https://api.osv.dev/v1/querybatch', 'transport': 'HTTPS_SYSTEM_TRUST',
        'scanner': scan(components, output), 'unknownEmbedded': embedded_unknown,
        'sbomStatus': 'INCOMPLETE_ACTUAL_PACKAGE_AND_TOOLCHAIN_RECONCILIATION',
        'cleanup': 'TEMPORARY_GENERATED_SOURCE_REMOVED',
        'inputSHA256': {name: file_hash(ROOT / name) for name in (MAVEN, PYTHON, DIST)}})
    save(output / 'manifest.json', {'sourceCommit': commit,
        'files': {p.name: file_hash(p) for p in sorted(output.iterdir())}})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    qualify(parser.parse_args().output)
