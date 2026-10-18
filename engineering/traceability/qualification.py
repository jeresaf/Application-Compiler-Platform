"""Integrated successor ownership/provenance checks. Always QUALIFICATION_ONLY.

Uses native CAS and exact immutable generator plans. Human handoffs are explicit
host observations, not generated provenance, approvals or release evidence.
"""
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tooling')]
from compiler_contracts import ArtifactPlan, Document, Owner, fingerprint, wire
from compiler_core import CompilerFault, _ownership
from filesystem_artifacts import FilesystemArtifactStore, ApprovedAICandidate, StoreConflict, source_bytes
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
from canonical_json import load


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, code):
    if not condition:
        raise ValueError(code)


def inputs(domain, compiler='compiler/runtime-test', pipeline='pipeline/runtime-test'):
    require(domain in ('payment', 'case-management'), 'APPLICATION')
    candidate = SuccessorCandidate()
    snapshot = Document.of(load(ROOT / f'test-corpus/deterministic-v04/{domain}-canonical-candidate.json'))
    request = SimpleNamespace(compiler=compiler, pipeline=pipeline, snapshot_digest=snapshot.read()['contentDigest'],
                              features=(), generator=candidate.generator)
    return candidate, snapshot, request, candidate.plan(snapshot, request)


def tree(root):
    return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


def approval(artifact):
    # Non-authoritative test host policy result. Never enrolled as human authority.
    return ApprovedAICandidate(artifact.content_digest, Document.of({
        'provider': 'LAB_ONLY', 'model': 'synthetic', 'inputDigest': fingerprint(artifact.provenance),
        'outputDigest': artifact.content_digest, 'approvalPolicy': 'ISOLATED_TEST_ONLY',
        'approvalEvidence': 'SYNTHETIC_NOT_HUMAN_APPROVAL'}))


def ownership_matrix(root, seed):
    """Actual store operations; every refused transaction must publish nothing."""
    root = Path(root)
    store = FilesystemArtifactStore(root)
    path = 'frontend/src/extensions/qualification.ts'
    results = []
    rejections = []
    def artifact(owner, text, prior=None):
        content = Document.of({'encoding': 'UTF-8', 'text': text})
        digest = fingerprint(content, 'artifact-content')
        return replace(seed, path=path, owner=owner, content=content, content_digest=digest,
                       intent='CREATE' if prior is None else ('NO_OP' if prior.digest == digest else 'UPDATE'),
                       expected_digest=None if prior is None else prior.digest)
    def reject(row, approvals=None, upgrades=()):
        before = tree(root)
        try:
            store.apply(ArtifactPlan((row,), ()), ai_approvals=approvals, framework_upgrades=upgrades)
        except (CompilerFault, StoreConflict):
            require(tree(root) == before, 'REJECTION_PUBLISHED')
            rejections.append({'owner': str(row.owner), 'intent': row.intent, 'published': False})
            return
        raise ValueError('UNAUTHORIZED_WRITE_ACCEPTED')
    # Separate roots retain full owner transition matrix, including framework.
    for source in Owner:
        current = artifact(Owner.COMPILER if source == Owner.HUMAN else source, '// original\n')
        store.apply(ArtifactPlan((current,), ()), ai_approvals={path: approval(current)} if source == Owner.AI else None)
        if source == Owner.HUMAN:
            store.adopt_human(path)
        prior = store.inventory()[0]
        for destination in Owner:
            row = artifact(destination, '// replacement\n', prior)
            if source != destination or source == Owner.HUMAN:
                reject(row, {path: approval(row)}, (path,))
                results.append([str(source), str(destination), 'REJECTED_UNCHANGED'])
            else:
                if source == Owner.AI:
                    reject(row)
                    reject(row, {path: approval(replace(row, content_digest='sha256:' + '0'*64))})
                if source == Owner.FRAMEWORK:
                    reject(row)
                reject(replace(row, expected_digest='sha256:' + '0'*64), {path: approval(row)}, (path,))
                store.apply(ArtifactPlan((row,), ()), ai_approvals={path: approval(row)}, framework_upgrades=(path,))
                require((root/path).read_bytes() == source_bytes(row.content), 'AUTHORIZED_BYTES')
                require(row.mappings == seed.mappings and row.provenance == seed.provenance, 'REVISION_LOST')
                reject(row, {path: approval(row)}, (path,))  # stale post-publication CAS
                prior = store.inventory()[0]
                results.append([str(source), str(destination), 'AUTHORIZED_EXACT_CAS'])
        if source == Owner.HUMAN:
            noop = artifact(source, '// original\n', prior)
            store.apply(ArtifactPlan((noop,), ()))
            (root/path).write_bytes(b'// independently authored HUMAN bytes\n')
            require(store.inventory()[0].owner == Owner.HUMAN, 'HUMAN_OWNER')
            reject(artifact(Owner.COMPILER, '// takeover\n', store.inventory()[0]))
        # Each row uses its own newly constructed disposable store.
        root = root.parent / (root.name + '-next')
        store = FilesystemArtifactStore(root)
    return {'scope': 'QUALIFICATION_ONLY', 'transitions': results, 'rejections': rejections, 'semanticMappings': wire(seed.mappings)}


def live_ownership(root, initial):
    """Exercise the complete application's publication boundary, then restore it."""
    root=Path(root);store=FilesystemArtifactStore(root)
    baseline=tree(root);inventory={a.path:a for a in store.inventory()}
    source=next(a for a in initial.artifacts if a.path=='backend/src/main/java/acp/Application.java')
    human=next(a for a in initial.artifacts if a.path=='frontend/src/extensions/identity.ts')
    require(inventory[human.path].owner==Owner.HUMAN,'LIVE_HUMAN_HANDOFF')
    denied=0
    def reject(artifact):
        nonlocal denied
        before=tree(root)
        try:store.apply(ArtifactPlan((artifact,),()))
        except (CompilerFault,StoreConflict):
            require(tree(root)==before,'LIVE_REJECTION_PUBLISHED');denied+=1;return
        raise ValueError('LIVE_UNAUTHORIZED_WRITE')
    for destination in (Owner.HUMAN,Owner.AI,Owner.FRAMEWORK):
        reject(replace(source,owner=destination,intent='NO_OP',expected_digest=inventory[source.path].digest))
    reject(replace(source,intent='NO_OP',expected_digest='sha256:'+'0'*64))
    for destination in Owner:
        content=Document.of({'encoding':'UTF-8','text':'// attempted HUMAN takeover\n'})
        reject(replace(human,owner=destination,content=content,content_digest=fingerprint(content,'artifact-content'),
                       intent='UPDATE',expected_digest=inventory[human.path].digest))
    reject(replace(source,path='frontend/src/extensions/unapproved-ai.ts',owner=Owner.AI,intent='CREATE',expected_digest=None))
    content=Document.of({'encoding':'UTF-8','text':source.content.read()['text']+'\n// qualification CAS round trip\n'})
    update=replace(source,content=content,content_digest=fingerprint(content,'artifact-content'),intent='UPDATE',expected_digest=inventory[source.path].digest)
    store.apply(ArtifactPlan((update,),()))
    require((root/source.path).read_bytes()==source_bytes(content),'LIVE_COMPILER_REPLACEMENT')
    require((root/human.path).read_bytes()==source_bytes(human.content),'LIVE_HUMAN_CHANGED')
    store.apply(ArtifactPlan((replace(source,intent='UPDATE',expected_digest=update.content_digest),),()))
    require(tree(root)==baseline,'LIVE_RESTORE_BYTES')
    return {'scope':'QUALIFICATION_ONLY','rejectedWithoutPublication':denied,'compilerCASPublications':2,
            'restoredExactSource':True,'humanOwner':str(next(a.owner for a in store.inventory() if a.path==human.path))}


def manifest(root, candidate, snapshot, request, initial, *, human_paths=()):
    """Resolve HUMAN mappings from the original trusted plan, never caller JSON."""
    root = Path(root)
    inventory = FilesystemArtifactStore(root).inventory()
    active = _ownership(candidate.plan(snapshot, request, inventory=inventory), inventory)
    candidate.verify_materialized(root, active, snapshot, request)
    require(set(a.path for a in inventory) == set(a.path for a in initial.artifacts), 'SOURCE_INVENTORY')
    owners = {a.path: a for a in inventory}
    active_artifacts = {a.path: a for a in active.artifacts}
    rows = []
    for original in initial.artifacts:
        artifact = active_artifacts.get(original.path, original)
        human = artifact.path in human_paths
        require(owners[artifact.path].owner == (Owner.HUMAN if human else artifact.owner), 'OWNERSHIP_BINDING')
        data = (root/artifact.path).read_bytes()
        if not human:
            require(data == source_bytes(artifact.content), 'SOURCE_BYTES')
        rows.append({'artifact': artifact.path, 'artifactSHA256': sha(data),
                     'owner': str(owners[artifact.path].owner), 'origins': wire(artifact.mappings),
                     'inputs': list(artifact.provenance.inputs), 'inputDigest': fingerprint(artifact.provenance, 'artifact-inputs'), 'generatedContentDigest': artifact.content_digest,
                     'handoff': 'EXPLICIT_HOST_HUMAN_ADOPTION' if human else 'GENERATED',
                     'originalArtifactSHA256': sha(source_bytes(artifact.content))})
    covered = {(o['id'], o['revision']) for row in rows for o in row['origins']}
    required = {(n['id'], n['revision']) for n in snapshot.read()['content']['nodes']}
    require(required <= covered, 'OBJECT_COVERAGE')
    return {'scope': 'QUALIFICATION_ONLY', 'generator': candidate.generator, 'snapshot': request.snapshot_digest,
            'plan': fingerprint(initial, 'artifact-plan'), 'artifacts': rows}


def verify_manifest(value, expected):
    # Expected is reconstructed by host from exact plan, live inventory and bytes.
    require(value == expected, 'PROVENANCE_BINDING')


# Each step encloses concrete runtime assertions, not merely a PASS label.
STEPS = {
 'query': ("expect((await query).postDataJSON()).toEqual({'QUERY-TEXT':''});", ['QUERY-TASKS']),
 'workflow': ("expect(f.events).toBe(events);expect(f.rows[0]).toEqual({text:'browser note 🦋',version:events,state:FINAL_STATE});expect(f.idempotency).toBe(events);", ['UC-TASK']),
 'screen': ("expect(order).toEqual(ui.screen.data.content.map(r=>r.id));", ['SCREEN-TASK']),
 'form': ("await expect(page.getByText('Enter a task note.',{exact:true}).first()).toBeVisible();", ['FORM-TASK']),
 'control': ("await expect(page.getByLabel('Resource identity')).toHaveValue('fixture-resource');", ['CONTROL-TASK-RESOURCE']),
 'action': ("await expect(page.getByRole('dialog')).toBeVisible();await axe(page,'confirmation');", ['ACTION-TASK']),
 'boundary': ("expect(denied.status()).toBe(403);", ['BOUNDARY-TASK']),
}


def instrument(source):
    require("test.step('ACP:" not in source, 'ALREADY_INSTRUMENTED')
    # FINAL_STATE has already been rendered by the original fixture.
    for key, (needle, _) in STEPS.items():
        if key == 'workflow':
            for state in ('STATE-POSTED', 'STATE-ARCHIVED'):
                actual = needle.replace('FINAL_STATE', json.dumps(state))
                if actual in source:
                    needle = actual
                    break
        require(source.count(needle) == 1, 'ASSERTION_SOURCE_CHANGED:' + key)
        source = source.replace(needle, "await test.step('ACP:" + key + "',async()=>{" + needle + '});', 1)
    return source


def runtime_links(report, provenance, test_source, result_bytes):
    require(json.loads(result_bytes) == report, 'RUNTIME_RESULT_BYTES')
    rows = {r['artifact']: r for r in provenance['artifacts']}
    links = []
    def walk(suites):
        for suite in suites:
            yield from suite.get('specs', [])
            yield from walk(suite.get('suites', []))
    for spec in walk(report.get('suites', [])):
        boundary = spec['title'] == 'permissions, forged calls, wrong tenant and identity change clear protected state'
        if not boundary and spec['title'] != 'production typed query, semantic order, keyboard journey, exact database effect and axe':
            continue
        require(spec.get('ok') is True, 'RUNTIME_SPEC_FAILED')
        for test in spec['tests']:
            require(test['status'] == 'expected' and test['expectedStatus'] == 'passed' and len(test['results']) == 1, 'RUNTIME_RETRY_OR_SKIP')
            result = test['results'][0]
            require(result['status'] == 'passed' and not result.get('errors'), 'RUNTIME_FAILURE')
            steps = result.get('steps', [])
            for key, (_, identities) in STEPS.items():
                if (key == 'boundary') != boundary:continue
                found = [s for s in steps if s['title'] == 'ACP:' + key]
                require(len(found) == (2 if boundary else 1) and not any(f.get('error') for f in found), 'MISSING_RUNTIME_ASSERTION:' + key)
                require("test.step('ACP:" + key + "'" in test_source, 'TEST_SOURCE_BINDING')
                for identity in identities:
                    matches = [r for r in rows.values() if any(o['id'] == identity for o in r['origins'])]
                    require(matches, 'MISSING_RUNTIME_MAPPING:' + identity)
                    links.append({'object': identity, 'project': test['projectName'], 'assertion': 'ACP:' + key,
                                  'steps': found, 'artifacts': matches,
                                  'kind': {'query':'Query','workflow':'UseCase','screen':'Screen','form':'Form','control':'InputControl','action':'Action','boundary':'PermissionBoundary'}[key],
                                  'testSourceSHA256': sha(test_source.encode()), 'resultSHA256': sha(result_bytes)})
    require(len(links) == 14 and {l['project'] for l in links} == {'COMPACT', 'EXPANDED'}, 'RUNTIME_ASSERTION_COVERAGE')
    return links
