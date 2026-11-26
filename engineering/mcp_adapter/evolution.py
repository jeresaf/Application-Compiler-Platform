"""Read-only semantic evolution through the native planning and target ports."""

from types import SimpleNamespace

from canonical_json import canonical_bytes
from changes import ChangeError, prepare
from compiler_contracts import Document, fingerprint, wire
from engineering.source_intelligence.model import impact, require


def preview(app, query):
    from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate

    if query['preset'] == 'case-r6-r7':
        return r8_preview(app, query['change'])
    change = query['change']
    require(type(change) is dict and len(canonical_bytes(change)) <= 32768,
            'CHANGE_PREVIEW_BOUND')
    require(type(change.get('operations')) is list and 0 < len(change['operations']) <= 8, 'CHANGE_PREVIEW_OPERATIONS')
    try:
        plan = prepare(app.snapshot, change)
    except ChangeError as error:
        raise ValueError(error.code.replace('-', '_')) from None

    candidate = SuccessorCandidate()
    old = Document.of(app.snapshot)
    new = Document.of(plan['candidate'])
    request = SimpleNamespace(compiler=app.b['compiler'], pipeline=app.b['pipeline'],
                              generator=candidate.generator, snapshot_digest=app.snapshot['contentDigest'],
                              features=tuple(app.snapshot['content']['requiredFeatures']))
    previous = candidate.plan(old, request)
    target = candidate.lower(new, compiler=request.compiler, pipeline=request.pipeline)
    proposed = candidate.plan(new, replace_request(request, new))
    prior = {a.path: a for a in previous.artifacts}
    current = {a.path: a for a in proposed.artifacts}
    rows = []
    for entry in plan['diff']:
        before, after = entry['before'], entry['after']
        rows.append({'kind': 'SEMANTIC_DIFF', 'id': entry['id'], 'operation': entry['operation'],
                     'fields': entry['fields'], 'beforeRevision': before['revision'] if before else None,
                     'afterRevision': after['revision'] if after else None})
    for semantic_id in sorted(plan['impact']['semanticIds']):
        if semantic_id not in app.nodes:
            continue
        if not any(m['semantic']['id'] == semantic_id for m in app.model['semanticMappings']):
            rows.append({'kind': 'SOURCE_IMPACT', 'id': semantic_id, 'confidence': 'UNKNOWN'})
            continue
        evidence = impact(app.model, app.root, semantic=semantic_id)
        rows.append({'kind': 'SOURCE_IMPACT', 'id': semantic_id,
                     'definitions': len(evidence['affectedDefinitions']),
                     'provenRelationships': len(evidence['provenDependencies']),
                     'possibleRelationships': len(evidence['possibleImpacts']),
                     'dynamicRelationships': 'UNKNOWN'})
    for path in sorted(prior.keys() | current.keys()):
        a, b = prior.get(path), current.get(path)
        if a and b and a.content_digest == b.content_digest:
            continue
        rows.append({'kind': 'ARTIFACT_IMPACT', 'path': path,
                     'before': a.content_digest if a else None,
                     'after': b.content_digest if b else None,
                     'owner': str(b.owner if b else a.owner),
                     'origins': [s.id for s in (b or a).mappings]})
    affected = set(plan['impact']['semanticIds'])
    for obligation in app.verification['results']:
        if any(origin['id'] in affected for origin in obligation['origins']):
            rows.append({'kind': 'VERIFICATION_OBLIGATION', 'id': obligation['id'],
                         'origins': obligation['origins'], 'result': 'NOT_RUN'})
    for obligation in proposed.obligations:
        rows.append({'kind': 'PROPOSED_OBLIGATION', 'value': wire(obligation)})
    migration = change['migration']
    summary = {'candidateDigest': plan['candidate']['contentDigest'],
               'changePlanDigest': plan['planDigest'], 'proposedTargetIRDigest': fingerprint(target),
               'proposedArtifactPlanDigest': fingerprint(proposed), 'generator': candidate.generator,
               'requiredScopes': plan['requiredScopes'], 'compatibility': plan['compatibility'],
               'migration': {'mode': migration['mode'], 'approval': 'NOT_AUTHORIZED',
                             'dataEffect': plan['dataEffect']},
               'publication': 'NOT_AUTHORIZED',
               'verification': 'PROPOSED_ARTIFACT_TESTS_NOT_RUN',
               'ownership': 'HOST_CAS_REQUIRED'}
    return summary, rows


def replace_request(request, snapshot):
    return SimpleNamespace(**(vars(request) | {'snapshot_digest': snapshot.read()['contentDigest'],
                                               'features': tuple(snapshot.read()['content']['requiredFeatures'])}))

R8_ARCHIVE_SHA256 = 'e3cd31674bd7f1fe605fb9b498fd98abf3c65c7763cb8f017304c73cfecf19ea'


def prepare_r8(archive):
    """Re-run the migration preview over exact compiler plans from the hosted R8 execution."""
    import hashlib
    import json
    import zipfile

    from engineering.application_evolution.plan import preview as native_preview

    with open(archive, 'rb') as stream:
        require(hashlib.file_digest(stream, 'sha256').hexdigest() == R8_ARCHIVE_SHA256,
                'CHANGE_PREVIEW_R8_ARCHIVE')
        stream.seek(0)
        with zipfile.ZipFile(stream) as source:
            def read(name):
                return json.loads(source.read('acp-r8/' + name + '.json'))

            retained = read('evolution-plan')
            observation_bytes = source.read('acp-r8/result.json')
            observation = json.loads(observation_bytes)
            source_impact = read('source-impact')
            before, after = read('r6-candidate'), read('r7-candidate')
            prior, proposed = read('r6-plan'), read('r7-plan')
    result = native_preview(before, after, prior, proposed, retained['before'], retained['after'])
    require(result == retained, 'CHANGE_PREVIEW_R8_PLAN_MISMATCH')
    migration = observation['migration']
    require(observation['planDigest'] == result['planDigest']
            and migration['preexistingRowsExact'] is True
            and migration['after'][:-1] == migration['before']
            and migration['after'][-1]['version'] == '5'
            and [migration['sqlSHA256']] == list(result['migration']['additions'].values()),
            'CHANGE_PREVIEW_R8_OBSERVATION')
    rows = [{'kind': 'SEMANTIC_DIFF', 'id': row['id'], 'operation': row['operation'],
             'fields': row['fields']} for row in result['change']['operations']]
    owners = {item['path']: item['owner'] for item in proposed['artifacts']}
    rows += [{'kind': 'ARTIFACT_IMPACT', **row, 'owner': owners[row['path']]}
             for row in result['artifactImpact']]
    for identity, key in [('DOC-ATTACHMENTS', 'oldDocumentImpact'), ('JOB-INTEGRITY', 'newJobImpact')]:
        impact_result = source_impact[key]
        rows.append({'kind': 'RETAINED_SOURCE_IMPACT', 'id': identity,
                     'modelDigest': impact_result['modelDigest'],
                     'definitions': len(impact_result['affectedDefinitions']),
                     'provenRelationships': len(impact_result['provenDependencies']),
                     'dynamicRelationships': 'UNKNOWN'})
    rows += [{'kind': 'PROPOSED_OBLIGATION', 'value': row} for row in proposed['obligations']]
    return {'preview': {'baseDigest': result['change']['base'], 'candidateDigest': result['change']['candidate'],
                        'changePlanDigest': result['planDigest'], 'proposedArtifactPlanDigest': result['after']['artifactPlan'],
                        'migration': result['migration'], 'compatibility': result['change']['compatibility'],
                        'requiredScopes': result['change']['requiredScopes'], 'publication': 'NOT_AUTHORIZED',
                        'ownership': 'HOST_CAS_REQUIRED', 'sourceImpact': 'RETAINED_R8_MODELS_CROSS_BASELINE_UNKNOWN',
                        'observation': {'run': 45667269534, 'archiveSHA256': R8_ARCHIVE_SHA256,
                                        'resultSHA256': hashlib.sha256(observation_bytes).hexdigest(), 'scope': 'QUALIFICATION_ONLY',
                                        'migrationVersion': '5', 'humanSHA256': observation['humanSHA256'],
                                        'sourceCommit': observation['sourceCommit']}},
            'rows': rows}


def r8_preview(app, selector):
    require(app.b['domain'] == 'case-management' and type(selector) is dict and set(selector) == {'baseDigest'},
            'CHANGE_PREVIEW_SCOPE')
    require(app.evolution is not None, 'CHANGE_PREVIEW_R8_INPUT_UNAVAILABLE')
    result = app.evolution
    require(selector['baseDigest'] == result['preview']['baseDigest'], 'CHANGE_PREVIEW_STALE_BASE')
    return result['preview'], result['rows']
