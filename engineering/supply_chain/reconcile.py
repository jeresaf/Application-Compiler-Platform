"""Reconcile V3 package bytes with existing qualification and H11 OSV evidence."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import zipfile

from engineering.dependency_resolution.inputs import packaged_dependencies
from engineering.supply_chain.qualify import ROOT, MAVEN, maven_component, save, sbom
from engineering.security.qualification import EMBEDDED_CONTAINER, embedded_component_inventory

SCAN_MANIFEST = 'ffee8709c2e3a52a5eae9b3b69ad3cd6cfc5bfe59d384aeb54d6aca45ab8552c'
SCAN_SOURCE = '00b1227471679dd0fabd647df269c1e885042f90'
HISTORICAL_BUILD = 'a5393724f352d117899afa6f75381dff02d7f5f3'
HISTORICAL_LOCK = '3dd6c5f504f4dba8f36d3ee10605421a29554dcb6ba7ad106413214acfaffa17'
DOMAINS = {'payment', 'case-management'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def historical_scan(root):
    raw = (root / 'manifest.json').read_bytes()
    require(sha(raw) == SCAN_MANIFEST, 'SCAN_MANIFEST')
    manifest = json.loads(raw)
    require(manifest['sourceCommit'] == SCAN_SOURCE, 'SCAN_SOURCE')
    for name, pin in manifest['files'].items():
        require(Path(name).name == name and sha((root / name).read_bytes()) == pin, 'SCAN_MEMBER')
    findings = json.loads((root / 'assessment.json').read_bytes())['scanner']['findings']
    require(len(findings) == 38, 'FINDING_COUNT')
    return findings


def package_members(path, expected):
    raw = path.read_bytes()
    require(sha(raw) == expected['packageSHA256'], 'PACKAGE_DIGEST')
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        require(len(set(names)) == len(names) and set(names) == set(expected['files']),
                'PACKAGE_MEMBER_INVENTORY')
        require(all(m.isfile() for m in members), 'PACKAGE_MEMBER_TYPE')
        result = {m.name: tar.extractfile(m).read() for m in members}
    require({n: sha(b) for n, b in result.items()} == expected['files'], 'PACKAGE_MEMBER_DIGEST')
    return result


def backend(raw, lock, expected):
    require(raw[:4] == b'PK\x03\x04', 'BACKEND_JAR')
    with zipfile.ZipFile(io.BytesIO(raw)) as jar:
        require(len(jar.namelist()) == len(set(jar.namelist())) and jar.testzip() is None,
                'BACKEND_JAR_INTEGRITY')
        licenses = {}
        for name in jar.namelist():
            if not name.startswith('BOOT-INF/lib/') or not name.endswith('.jar'):
                continue
            with zipfile.ZipFile(io.BytesIO(jar.read(name))) as nested:
                licenses[name] = [
                    {'path': member, 'sha256': sha(nested.read(member))}
                    for member in nested.namelist()
                    if re.search(r'(?:^|/)(LICENSE|NOTICE|COPYING)(?:[._-][^/]*)?$', member, re.I)
                    and not member.endswith('/')
                ]
        actual = packaged_dependencies(io.BytesIO(raw), lock['artifacts'], lock['embeddedArtifacts'])
    require(actual == expected, 'NESTED_COMPONENT_INVENTORY')
    embedded, unresolved = embedded_component_inventory(lock['embeddedArtifacts'])
    by_origin = {EMBEDDED_CONTAINER + '!/' + row['entry']: row for row in embedded}
    rows = []
    for name, observed in actual.items():
        identities = {}
        for origin in observed['lockedOrigins']:
            kind, source = origin.split(':', 1)
            if kind == 'maven':
                row = maven_component(source, observed)
            elif source in by_origin:
                row = by_origin[source]
            else:
                continue
            identities[(row['ecosystem'], row['name'], row['version'])] = row
        identity = next(iter(identities.values())) if len(identities) == 1 else None
        rows.append({'path': name, 'sha256': observed['sha256'], 'origins': observed['lockedOrigins'],
                     'identity': identity, 'status': 'CONFIRMED_PACKAGED' if identity else 'UNKNOWN_IDENTITY',
                     'licenseMembers': licenses[name], 'legalReview': 'LEGAL_REVIEW_REQUIRED'})
    return rows, unresolved


def version_status(component, advisory):
    """Support exact affected lists and stable numeric npm SemVer only."""
    matched = [entry for entry in advisory.get('affected', [])
               if entry.get('package', {}).get('name') == component['name']
               and entry.get('package', {}).get('ecosystem') == component['ecosystem']]
    version = component['version']
    if any(version in entry.get('versions', []) for entry in matched):
        return 'CONFIRMED_AFFECTED_VERSION'
    if not matched:
        return 'ADVISORY_DATA_INCOMPLETE'
    if component['ecosystem'] != 'npm':
        return 'VERSION_COMPARISON_UNSUPPORTED'
    def numeric(value):
        if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value):
            raise ValueError('UNSUPPORTED_SEMVER')
        return tuple(map(int, value.split('.')))
    try:
        candidate = numeric(version)
        ranges = [r for entry in matched for r in entry.get('ranges', [])]
        if not ranges:
            return 'ADVISORY_DATA_INCOMPLETE'
        unsupported = False
        for row in ranges:
            events = row.get('events', [])
            if (row.get('type') != 'SEMVER' or len(events) not in (1, 2)
                    or set(events[0]) != {'introduced'}
                    or len(events) == 2 and set(events[1]) != {'fixed'}):
                unsupported = True
                continue
            start = (0, 0, 0) if events[0]['introduced'] == '0' else numeric(events[0]['introduced'])
            end = numeric(events[1]['fixed']) if len(events) == 2 else None
            if end is not None and end <= start:
                unsupported = True
                continue
            if candidate >= start and (end is None or candidate < end):
                return 'CONFIRMED_AFFECTED_VERSION'
        return 'VERSION_COMPARISON_UNSUPPORTED' if unsupported else 'VERSION_OUTSIDE_AFFECTED_RANGE'
    except (ValueError, TypeError):
        return 'VERSION_COMPARISON_UNSUPPORTED'


def reconcile(workspace, scan, output, build_source):
    findings = historical_scan(scan)
    lock = json.loads((ROOT / MAVEN).read_bytes())
    run = json.loads((workspace / 'qualification.json').read_bytes())
    first = (workspace / 'clean-one/results.json').read_bytes()
    require(first == (workspace / 'clean-two/results.json').read_bytes(), 'INDEPENDENT_BUILD_MISMATCH')
    expected = json.loads(first)
    require(expected == run['applications'] and set(expected) == DOMAINS, 'APPLICATION_COVERAGE')
    pinned = (workspace / 'dependency-lock.json').read_bytes()
    require(sha(pinned) == run['dependencyLockSHA256'], 'DEPENDENCY_LOCK_DIGEST')
    current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    require((build_source == HISTORICAL_BUILD and sha(pinned) == HISTORICAL_LOCK)
            or (build_source == current == os.environ.get('GITHUB_SHA')
                and not subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
            'BUILD_SOURCE')
    evidence = json.loads(pinned)
    require(evidence['mavenReferenceSHA256'] == sha((ROOT / MAVEN).read_bytes()), 'MAVEN_LOCK_MISMATCH')
    output.mkdir(parents=True, exist_ok=False)
    applications = {}
    for domain, report in sorted(expected.items()):
        members = package_members(workspace / f'clean-one/{domain}.tar', report)
        rows, unknown = backend(members['backend/application.jar'], lock, report['runtimeDependencies'])
        provenance = json.loads(members['acp/provenance.json'])
        applications[domain] = {'packageSHA256': report['packageSHA256'], 'components': rows,
            'generator': evidence['applications'][domain]['inputs']['candidate'],
            'provenanceSHA256': sha(members['acp/provenance.json']),
            'frontendFiles': {p: sha(b) for p,b in members.items() if p.startswith('frontend/dist/')},
            'frontendLock': evidence['applications'][domain]['npm'],
            'frontendAttribution': 'UNRESOLVED_INCLUSION', 'unresolvedEmbeddedOrigins': unknown}
        require(type(provenance) is dict, 'PACKAGE_PROVENANCE')
        bom = sbom([r['identity'] for r in rows if r['identity']], domain)
        bom['metadata'] = {'properties': [{'name': 'acp:packageSHA256', 'value': report['packageSHA256']},
                                         {'name': 'acp:buildSource', 'value': build_source}]}
        save(output / f'{domain}.cdx.json', bom)
    triage = []
    for index, finding in enumerate(findings, 1):
        c = finding['component']
        present = [domain for domain, app in applications.items() if any(
            r['identity'] and all(r['identity'][k] == c[k] for k in ('ecosystem', 'name', 'version'))
            for r in app['components'])]
        if present:
            exposure = 'CONFIRMED_PACKAGED'
        elif c['ecosystem'] == 'Maven':
            exposure = 'BUILD_TIME_EXPOSURE_REQUIRES_REVIEW'
        elif c['ecosystem'] == 'PyPI':
            exposure = 'COMPILER_EXPOSURE_REQUIRES_REVIEW'
        else:
            exposure = 'PACKAGED_APPLICABILITY_UNRESOLVED'
        triage.append({'finding': index, 'versionDisposition': version_status(c, finding['advisory']),
                       'packagedApplications': present,
                       'exposure': exposure,
                       'proposedAction': 'Review upstream fixed versions, executable exposure and compatibility before any lock change',
                       'riskDisposition': 'OWNER_DECISION_REQUIRED', 'original': finding})
    save(output / 'reconciliation.json', {'sourceCommit': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'buildSource': build_source,
        'scanSource': SCAN_SOURCE, 'applications': applications, 'SEC-02': 'BLOCKED',
        'toolchains': evidence['toolchains'], 'compilerInputs': evidence['compiler'],
        'nativeProvenance': 'INCOMPLETE', 'independentResultsSHA256': sha(first)})
    from engineering.supply_chain.qualify import maven_component
    build_rows = [maven_component(path, row) for path, row in sorted(lock['artifacts'].items())]
    build_rows += [{'ecosystem': 'PyPI', 'name': name, 'version': row['version'],
                    'sha256': row['sha256']} for name, row in evidence['compiler'].items()]
    save(output / 'compiler-build.cdx.json', sbom(build_rows, 'compiler-build'))
    save(output / 'maven-graphs.json', {k: lock[k] for k in ('graphs', 'plugins')})
    save(output / 'triage.json', triage)
    save(output / 'manifest.json', {'sourceCommit': current, 'buildSource': build_source, 'files': {p.name: sha(p.read_bytes()) for p in sorted(output.iterdir())}})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('workspace', 'scan', 'output'):
        parser.add_argument('--' + option, required=True, type=Path)
    parser.add_argument('--build-source', required=True)
    args = parser.parse_args()
    reconcile(args.workspace, args.scan, args.output, args.build_source)
