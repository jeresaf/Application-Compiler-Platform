"""Independently check H11.1 evidence and retain explicit coverage gaps."""
import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

from jsonschema import Draft7Validator
from referencing import Registry, Resource

from engineering.supply_chain.qualify import DIST, MAVEN, ROOT, maven_component, save
from engineering.supply_chain.reconcile import require, sha, version_status

PRODUCER = 'b480983979511efffce95d10d42da9724ec4f0b0'
ARCHIVE = 'ef90224b2199ee1edf2d286c8e37e06d4ff4f0188314ad0db8413cd89a990658'
SCHEMAS = {
    'bom-1.6': '1ebcb88a2c845ecb6ff7bee7aeabdff9422cb0347f3d6875b241bd444b7e098f',
    'jsf-0.82': '2faf5eb3651f2ae5f46091a131770d8d847bbd121139d19c85fc7051bfa58c46',
    'spdx': '33863a360fc4d348e183d89c1ca7aa0877f481e7eb55be2d4102a30386188a10',
}
FILES = {'manifest.json', 'reconciliation.json', 'triage.json', 'maven-graphs.json',
         'payment.cdx.json', 'case-management.cdx.json', 'compiler-build.cdx.json'}


def read_archive(raw):
    require(sha(raw) == ARCHIVE, 'RECONCILIATION_ARCHIVE')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        require(len(archive.namelist()) == len(FILES) and set(archive.namelist()) == FILES
                and archive.testzip() is None, 'ARCHIVE_INVENTORY')
        members = {name: archive.read(name) for name in FILES}
    manifest = json.loads(members.pop('manifest.json'))
    require(manifest['sourceCommit'] == manifest['buildSource'] == PRODUCER, 'EVIDENCE_SOURCE')
    require({n: sha(b) for n, b in members.items()} == manifest['files'], 'EVIDENCE_MEMBER_HASH')
    return {name: json.loads(value) for name, value in members.items()}


def schema_validator(directory):
    schemas = {}
    for name, pin in SCHEMAS.items():
        raw = (directory / (name + '.schema.json')).read_bytes()
        require(sha(raw) == pin, 'CYCLONEDX_SCHEMA_DIGEST')
        schemas[name] = json.loads(raw)
    root = schemas['bom-1.6']
    Draft7Validator.check_schema(root)
    registry = Registry().with_resources(
        (f'http://cyclonedx.org/schema/{name}.schema.json', Resource.from_contents(schema))
        for name, schema in schemas.items()
    )
    return Draft7Validator(root, registry=registry)


def component_key(row):
    return (row['name'], row['version'], row['sha256'])


def validate_bom(bom, expected, validator):
    validator.validate(bom)
    refs = [r['bom-ref'] for r in bom['components']]
    require(len(refs) == len(set(refs)), 'DUPLICATE_BOM_REFERENCE')
    require(bom['specVersion'] == '1.6' and bom['compositions'] == [
        {'aggregate': 'incomplete', 'assemblies': refs}], 'BOM_COMPLETENESS')
    actual = [(r['name'], r['version'], r['hashes'][0]['content']) for r in bom['components']]
    require(sorted(actual) == sorted(expected), 'BOM_COMPONENT_RECONCILIATION')


def packaged_maven_edges(graph, packaged, bom):
    """Project only Maven graph edges with exact, unambiguous packaged endpoints."""
    refs = {}
    by_component = {}
    for component in bom['components']:
        key = (component['name'], component['version'], component['hashes'][0]['content'])
        by_component.setdefault(key, []).append(component['bom-ref'])
    for row in packaged:
        identity = row.get('identity')
        if identity is None:
            continue
        require(row['sha256'] == identity['sha256'], 'PACKAGED_ENDPOINT_DIGEST')
        matches = by_component.get(component_key(identity), [])
        if len(matches) != 1:
            continue
        for origin in row['origins']:
            if origin.startswith('maven:'):
                refs.setdefault(origin.removeprefix('maven:'), set()).add(matches[0])

    def endpoint(node):
        if node.get('type') != 'jar':
            return None
        group, name, version = (node[field] for field in ('groupId', 'artifactId', 'version'))
        classifier = node.get('classifier', '')
        suffix = '-' + classifier if classifier else ''
        path = f"{group.replace('.', '/')}/{name}/{version}/{name}-{version}{suffix}.jar"
        candidates = refs.get(path, set())
        return next(iter(candidates)) if len(candidates) == 1 else None

    edges = {}
    unmapped = 0
    pending = [graph]
    while pending:
        parent = pending.pop()
        start = endpoint(parent)
        for child in parent.get('children', []):
            end = endpoint(child)
            if start is not None and end is not None and start != end:
                edges.setdefault(start, set()).add(end)
            else:
                unmapped += 1
            pending.append(child)
    return [{'ref': source, 'dependsOn': sorted(targets)} for source, targets in sorted(edges.items())], unmapped


def verify_projected_edges(bom, expected, validator):
    validator.validate(bom)
    require(bom.get('dependencies') == expected, 'PACKAGED_EDGE_RECONCILIATION')


def native_tools(toolchains):
    result = {}
    roots = toolchains['inventories']
    for name, path in toolchains['executables'].items():
        if name in ('python', 'node'):
            pin = roots[name]
        else:
            key = 'jdk-bin' if name in ('java', 'javac') else ('maven' if name == 'mvn' else name)
            record = roots[key]
            relative = Path(path).relative_to(record['root']).as_posix()
            pin = record['files'].get(relative, {})
        require(re.fullmatch(r'[0-9a-f]{64}', pin.get('sha256', '')) is not None, 'UNKNOWN_TOOL_BYTES')
        version = toolchains['versions']['maven' if name == 'mvn' else name]
        result[name] = {'executable': path, 'versionObservation': version, 'sha256': pin['sha256'],
                        'scope': 'V3_CLEAN_BUILD', 'publisherProvenance': 'UNVERIFIED',
                        'dynamicLoading': 'NOT_OBSERVED'}
    return result


def qualify(archive, schemas, output):
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require(os.environ.get('GITHUB_SHA', commit) == commit, 'CURRENT_SOURCE')
    data = read_archive(archive.read_bytes())
    validator = schema_validator(schemas)
    reconciliation = data['reconciliation.json']
    require(reconciliation['buildSource'] == reconciliation['sourceCommit'] == PRODUCER, 'BUILD_SOURCE')
    maven = json.loads((ROOT / MAVEN).read_bytes())
    require(data['maven-graphs.json'] == {k: maven[k] for k in ('plugins', 'graphs')}, 'MAVEN_GRAPH')
    output.mkdir(parents=True, exist_ok=False)
    distributions = json.loads((ROOT / DIST).read_bytes())
    tools = native_tools(reconciliation['toolchains'])
    tools['mvn']['approvedDistribution'] = {k: distributions[k] for k in ('version', 'url', 'sha256', 'sha512')}
    save(output / 'native-tools.json', {'sourceCommit': PRODUCER, 'tools': tools,
         'runtimeFileInventory': reconciliation['toolchains']['inventories'],
         'runtimeFileInventoryMeaning': 'RECORDED_INSTALLATION_FILES_NOT_OBSERVED_DYNAMIC_LOADS',
         'unresolved': ['system loader and shared libraries', 'native frontend bundler binaries',
                        'native analyzer execution outside this build']})
    licenses = []
    frontend = {}
    graph_coverage = {}
    require(set(reconciliation['applications']) == {'payment', 'case-management'}, 'APPLICATIONS')
    for domain, app in sorted(reconciliation['applications'].items()):
        expected = [component_key(row['identity']) for row in app['components'] if row['identity']]
        bom = data[f'{domain}.cdx.json']
        validate_bom(bom, expected, validator)
        properties = {r['name']: r['value'] for r in bom['metadata']['properties']}
        require(properties == {'acp:buildSource': PRODUCER, 'acp:packageSHA256': app['packageSHA256']},
                'BOM_PACKAGE_BINDING')
        frontend[domain] = {'files': app['frontendFiles'], 'declaredInputs': app['frontendLock'],
            'sourceMaps': [p for p in app['frontendFiles'] if p.endswith('.map')],
            'attribution': 'UNRESOLVED_INCLUSION'}
        licenses.extend({'application': domain, 'identity': row['identity'], 'nestedSHA256': row['sha256'],
                        'members': row['licenseMembers'], 'ownerReview': 'LEGAL_REVIEW_REQUIRED',
                        'status': 'NOTICE_OR_LICENSE_MEMBER_HASHED' if row['licenseMembers']
                        else 'LICENSE_IDENTITY_UNCERTAIN'} for row in app['components'])
        edges, unmapped = packaged_maven_edges(maven['graphs'][domain], app['components'], bom)
        bom['dependencies'] = edges
        verify_projected_edges(bom, edges, validator)
        graph_coverage[domain] = {'projectedEdges': sum(len(row['dependsOn']) for row in edges),
                                  'unmappedGraphOccurrences': unmapped}
        save(output / f'{domain}.cdx.json', bom)
    build = [component_key(maven_component(path, pin)) for path, pin in maven['artifacts'].items()]
    build.extend((name, row['version'], row['sha256']) for name, row in reconciliation['compilerInputs'].items())
    validate_bom(data['compiler-build.cdx.json'], build, validator)
    save(output / 'compiler-build.cdx.json', data['compiler-build.cdx.json'])
    triage = data['triage.json']
    require([r['finding'] for r in triage] == list(range(1, 39)), 'TRIAGE_COVERAGE')
    for row in triage:
        original = row['original']
        component = original['component']
        require(row['versionDisposition'] == version_status(component, original['advisory'])
                and row['riskDisposition'] == 'OWNER_DECISION_REQUIRED', 'TRIAGE_DISPOSITION')
        row['exposureDisposition'] = {
            'npm': 'FRONTEND_ATTRIBUTION_UNRESOLVED',
            'Maven': 'SHADING_AND_BUILD_EXPOSURE_REVIEW_REQUIRED',
            'PyPI': 'COMPILER_EXPOSURE_REQUIRES_REVIEW',
        }.get(component['ecosystem'], 'EXPOSURE_NOT_ESTABLISHED')
        if row['packagedApplications']:
            row['exposureDisposition'] = 'CONFIRMED_RUNTIME_COMPONENT_INCLUSION'
    save(output / 'triage.json', triage)
    save(output / 'frontend.json', frontend)
    save(output / 'licenses.json', licenses)
    save(output / 'assessment.json', {'sourceCommit': commit, 'buildSource': PRODUCER,
        'sourceArchiveSHA256': ARCHIVE, 'schemaSHA256': SCHEMAS, 'schemaValidation': 'PASS',
        'relationshipCoverage': 'INCOMPLETE', 'packagedMavenGraphProjection': graph_coverage,
        'shadedCoverage': 'UNRESOLVED',
        'trustAndLegalAcceptance': 'PENDING', 'SEC-02': 'BLOCKED', 'SEC-01': 'BLOCKED'})
    save(output / 'manifest.json', {'sourceCommit': commit, 'buildSource': PRODUCER,
                                  'files': {p.name: sha(p.read_bytes()) for p in sorted(output.iterdir())}})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('archive', 'schemas', 'output'):
        parser.add_argument('--' + option, type=Path, required=True)
    args = parser.parse_args()
    qualify(args.archive, args.schemas, args.output)
