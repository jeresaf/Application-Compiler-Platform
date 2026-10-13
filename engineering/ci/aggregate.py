"""CI-only exact-source aggregation. No release criteria or authority are issued here."""
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

JOBS = ('contracts', 'phase5-experiments', 'phase5c-hard-gates', 'phase6-target', 'phase6-closure-audit')
ARTIFACTS = ('route-a-engineering-test-evidence', 'phase5c-ubuntu-evidence',
             'phase5b-ubuntu-evidence', 'phase6-target-ubuntu-evidence',
             'phase6-remediation-0.5.0-closure-audit')
ARTIFACT_OWNERS = dict(zip(ARTIFACTS, ('contracts', 'phase5-experiments', 'phase5-experiments', 'phase6-target', 'phase6-closure-audit')))
REQUIRED_FILES = {
    ARTIFACTS[0]: ('tests.log',),
    ARTIFACTS[1]: ('validation.json', 'native-tests.json', 'maintenance.json'),
    ARTIFACTS[2]: ('validation.json', 'inventory.json', 'evolution.json'),
    ARTIFACTS[3]: ('task-interface-report.json', 'ui-upgrade-report.json', 'component-report.json', 'invocation-report.json', 'delivery-job-report.json', 'privacy-lifecycle-report.json', 'target-upgrade-report.json'),
    ARTIFACTS[4]: ('phase6-final-closure.json', 'remediation-regressions.log'),
}
OUT = Path('.ci-evidence')


def write(name, value):
    OUT.mkdir(exist_ok=True)
    (OUT/name).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def evaluate(source, run, attempt, jobs, bindings, artifacts, closure):
    """All inputs must already have passed transport/ZIP verification."""
    errors = []
    for name in JOBS:
        found = [j for j in jobs if j['name'] == name]
        if len(found) != 1 or found[0].get('conclusion') != 'success':
            errors.append('JOB_NOT_SUCCESS:'+name)
        expected = {'source': source, 'run': str(run), 'attempt': str(attempt), 'job': name}
        if bindings.get(name) != expected:
            errors.append('SOURCE_BINDING:'+name)
    for name in ARTIFACTS:
        a = artifacts.get(name)
        if not a or a.get('source') != source or a.get('valid') is not True:
            errors.append('ARTIFACT_INVALID:'+name)
    if (closure.get('baseline', {}).get('auditExecutionCommit') != source
            or closure.get('auditExecution', {}).get('status') != 'PERFORMED'
            or closure.get('recommendation') != 'PHASE6_CLOSURE_RECOMMENDED'
            or closure.get('blockers') != []
            or {c.get('requirement') for c in closure.get('criteria', [])} != set(range(1, 40))
            or len(closure.get('criteria', [])) != 39
            or any(c.get('status') != 'PASS' or c.get('evaluationProvenance', {}).get('executionCommit') != source
                   or c.get('evaluationProvenance', {}).get('evaluationCommit') != source
                   for c in closure.get('criteria', []))):
        errors.append('RELEASE_CLOSURE_NOT_SATISFIED')
    engineering = (all(len([j for j in jobs if j['name'] == n and j.get('conclusion') == 'success']) == 1
                       and bindings.get(n) == {'source': source, 'run': str(run), 'attempt': str(attempt), 'job': n}
                       for n in JOBS[:-1])
                   and all(artifacts.get(n, {}).get('valid') is True and artifacts[n].get('source') == source
                           for n in ARTIFACTS[:-1]))
    return {'releasePassed': not errors, 'engineering': 'ENGINEERING_VALIDATION_PASSED' if engineering else 'ENGINEERING_VALIDATION_NOT_PASSED',
            'closure': closure.get('recommendation', 'CLOSURE_EVIDENCE_UNAVAILABLE'),
            'release': 'PHASE6_RELEASE_CLOSURE_BLOCKED' if closure.get('recommendation') == 'PHASE6_CLOSURE_BLOCKED' else ('RELEASE_VALIDATION_PASSED' if not errors else 'RELEASE_VALIDATION_FAILED'),
            'errors': errors}


def api(path):
    req = urllib.request.Request('https://api.github.com/repos/'+os.environ['GITHUB_REPOSITORY']+path,
                                 headers={'Authorization': 'Bearer '+os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def pages(path, key):
    result = []
    for page in range(1, 101):
        data = api(path+'?'+'per_page=100&page='+str(page))[key]
        result.extend(data)
        if len(data) < 100:
            return result
    raise ValueError('PAGINATION_LIMIT')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def archive(artifact):
    # Never forward the GitHub token to the signed object-storage URL.
    req = urllib.request.Request(artifact['archive_download_url'], headers={'Authorization': 'Bearer '+os.environ['GH_TOKEN']})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=120) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code != 302:
            raise
        with urllib.request.urlopen(e.headers['Location'], timeout=180) as r:
            data = r.read()
    digest = 'sha256:'+hashlib.sha256(data).hexdigest()
    if artifact.get('digest') != digest:
        raise ValueError('ARCHIVE_DIGEST_MISMATCH:'+artifact['name'])
    z = zipfile.ZipFile(io.BytesIO(data))
    if not z.namelist() or len(set(z.namelist())) != len(z.namelist()) or z.testzip() is not None:
        raise ValueError('INVALID_ARCHIVE:'+artifact['name'])
    return z


def hosted():
    source, run, attempt = (os.environ[n] for n in ('GITHUB_SHA', 'GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT'))
    base = '/actions/runs/'+run
    metadata = api(base)
    if str(metadata['run_attempt']) != attempt:
        raise ValueError('RUN_ATTEMPT_MISMATCH')
    if metadata['head_sha'] != source:
        # Pull-request runs identify their head in the API but execute the
        # event-bound merge commit. Every job still captures the exact checkout.
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        pr = event.get('pull_request', {})
        if (os.environ.get('GITHUB_EVENT_NAME') != 'pull_request'
                or pr.get('head', {}).get('sha') != metadata['head_sha']
                or pr.get('merge_commit_sha') != source):
            raise ValueError('RUN_SOURCE_MISMATCH')
    jobs = pages(base+'/attempts/'+attempt+'/jobs', 'jobs')
    artifacts = pages(base+'/artifacts', 'artifacts')
    write('jobs.json', jobs)
    write('artifacts.json', artifacts)
    timings = []
    for job in jobs:
        duration = lambda start, end: (datetime.fromisoformat(end.replace('Z', '+00:00'))-datetime.fromisoformat(start.replace('Z', '+00:00'))).total_seconds() if start and end else None
        timings.append({'job': job['name'], 'startedAt': job.get('started_at'), 'completedAt': job.get('completed_at'),
                        'seconds': duration(job.get('started_at'), job.get('completed_at')),
                        'steps': [{'name': step['name'], 'seconds': duration(step.get('started_at'), step.get('completed_at'))} for step in job.get('steps', [])]})
    write('timings.json', {'source': source, 'jobs': timings, 'limitation': 'Final aggregate duration and workflow end are measured from the completed run API after this job finishes.'})
    needs = json.loads(os.environ['EXPECTED_NEEDS'])
    if set(needs) != set(JOBS):
        raise ValueError('NEEDS_SET_MISMATCH')
    bindings, validated, inventories, closure = {}, {}, {}, {}
    for name in (*ARTIFACTS, *('ci-source-'+j for j in JOBS)):
        found = [a for a in artifacts if a['name'] == name and not a['expired']]
        if len(found) != 1:
            continue
        a = found[0]
        if a['workflow_run']['head_sha'] != metadata['head_sha'] or str(a['workflow_run']['id']) != run:
            continue
        owner = name.removeprefix('ci-source-') if name.startswith('ci-source-') else ARTIFACT_OWNERS[name]
        producers = [j for j in jobs if j['name'] == owner]
        if (len(producers) != 1 or not producers[0].get('started_at') or not producers[0].get('completed_at')
                or not producers[0]['started_at'] <= a['created_at'] <= producers[0]['completed_at']):
            continue
        z = archive(a)
        if name.startswith('ci-source-'):
            job = name.removeprefix('ci-source-')
            if z.namelist() != [job+'.json']:
                raise ValueError('BINDING_ARCHIVE_SHAPE')
            bindings[job] = json.loads(z.read(job+'.json'))
        else:
            basenames = {p.split('/')[-1] for p in z.namelist()}
            if not set(REQUIRED_FILES[name]) <= basenames:
                raise ValueError('REQUIRED_ARTIFACT_FILES_MISSING:'+name)
            for entry in z.namelist():
                if entry.split('/')[-1] in REQUIRED_FILES[name] and entry.endswith('.json'):
                    if not isinstance(json.loads(z.read(entry)), dict):
                        raise ValueError('ARTIFACT_REPORT_NOT_OBJECT:'+entry)
            validated[name] = {'source': source, 'valid': True, 'id': a['id'], 'digest': a['digest']}
            counts, junit = [], []
            for entry in z.namelist():
                if entry.endswith('.xml') and 'surefire-reports' in entry:
                    root = ET.fromstring(z.read(entry))
                    if root.tag == 'testsuite':
                        junit.append({'path': entry, **{key: int(root.get(key, '0')) for key in ('tests', 'failures', 'errors', 'skipped')}})
                if entry.endswith('.log'):
                    text = z.read(entry).decode('utf-8', errors='replace')
                    for count in re.findall(r'Ran (\d+) tests? in ', text):
                        counts.append({'path': entry, 'unittestRunCount': int(count)})
            inventories[name] = {'files': len(z.namelist()), 'unittestSummaries': counts, 'junitSuites': junit}
            if name == ARTIFACTS[-1]:
                reports = [p for p in z.namelist() if p.split('/')[-1] == 'phase6-final-closure.json']
                if len(reports) != 1:
                    raise ValueError('CLOSURE_REPORT_MISSING_OR_DUPLICATED')
                closure = json.loads(z.read(reports[0]))
                write('closure-summary.json', {k: closure.get(k) for k in ('baseline','auditExecution','recommendation','blockers')})
    result = evaluate(source, run, attempt, jobs, bindings, validated, closure)
    for name in JOBS:
        actual = next((j.get('conclusion') for j in jobs if j['name'] == name), None)
        if needs[name]['result'] != actual:
            result['errors'].append('NEEDS_API_DISAGREEMENT:'+name)
            result['releasePassed'] = False
            result['release'] = 'RELEASE_VALIDATION_FAILED'
    result.update(source=source, run=run, attempt=attempt, artifacts=validated, inventories=inventories)
    write('aggregate.json', result)
    print(json.dumps(result, indent=2))
    return 0 if result['releasePassed'] else 1


def main():
    if sys.argv[1:] == ['capture']:
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        if source != os.environ['GITHUB_SHA']:
            raise ValueError('CHECKOUT_SOURCE_MISMATCH')
        job = os.environ['GITHUB_JOB']
        write(job+'.json', {'source': source, 'run': os.environ['GITHUB_RUN_ID'], 'attempt': os.environ['GITHUB_RUN_ATTEMPT'], 'job': job})
        return 0
    if sys.argv[1:] == ['hosted']:
        try:
            return hosted()
        except Exception as e:
            write('aggregate-exception.json', {'error': type(e).__name__, 'detail': str(e), 'releasePassed': False})
            raise
    raise SystemExit('usage: aggregate.py capture|hosted')


if __name__ == '__main__':
    sys.exit(main())
