"""Bounded offline qualification; exit 0 means offline success, never release approval."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

BASELINE = '2b03d2d35b517f5a073bf83a3cb7a4e6126118cf'
PATCH = '9706ba0c436f57560b0e8ace897cee7f1f258c2d40870e8bf1c9c2da70b791c8'
PYTHON = '3.14.7'
SELECTORS = ('test_core_wave1', 'test_canonical03_migrations.Canonical03MigrationTests',
             'test_target_migrations.MigrationPlannerTests', 'test_core_wave2',
             'test_core_wave3', 'test_phase6_qualification')
EXPECTED_TESTS = 32
PHYSICAL_METHODS = ('test_real_postgresql_storage_presence_required_and_rollback',
                    'test_missing_persisted_column_rejects_before_expand',
                    'test_wrong_text_storage_rejects_without_catalog_change',
                    'test_cross_version_retained_bytes_and_rollback_both_domains')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_files(root):
    root = Path(root)
    if root.is_symlink():
        raise ValueError('SOURCE_SYMLINK')
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError('SOURCE_SYMLINK')
        if path.is_file():
            files[path.relative_to(root).as_posix()] = sha(path)
    return files


def source_digest(root):
    return hashlib.sha256(json.dumps(source_files(root), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def validate_candidate(root, patch, manifest_path, *, expected_manifest, expected_candidate, baseline=BASELINE):
    # Expected hashes must come from the reviewing operator, not the manifest.
    if baseline != BASELINE or sha(patch) != PATCH or sha(manifest_path) != expected_manifest:
        raise ValueError('BASELINE_PATCH_OR_MANIFEST_MISMATCH')
    manifest = json.loads(Path(manifest_path).read_text())
    if (manifest['baselineCommit'] != BASELINE or manifest['wave3PatchSHA256'] != PATCH
        or manifest['python'] != PYTHON or tuple(manifest['offlineSelectors']) != SELECTORS
        or manifest['expectedTests'] != EXPECTED_TESTS or tuple(manifest['physicalMethods']) != PHYSICAL_METHODS
        or manifest['physicalEnabled'] is not False):
        raise ValueError('MANIFEST_POLICY_MISMATCH')
    expected = dict(manifest['baselineFileHashes'])
    if len(expected) != 895 or len(manifest['wave3Files']) != 6:
        raise ValueError('BASELINE_INVENTORY_MISMATCH')
    expected.update(manifest['wave3Files'])
    corrections=manifest.get('postIntegrationCorrections',{})
    if not set(corrections)<={'tooling/tests/test_canonical03_migrations.py','tooling/tests/test_core_wave2.py'}:
        raise ValueError('UNAUTHORIZED_LINEAGE_CORRECTION')
    expected.update(corrections)
    additions = manifest['additionFileHashes']
    if set(additions) & set(expected):
        raise ValueError('ADDITION_REPLACES_BASELINE')
    expected.update(additions)
    relative = Path(manifest_path).resolve().relative_to(Path(root).resolve()).as_posix()
    expected[relative] = expected_manifest
    if source_files(root) != expected or source_digest(root) != expected_candidate:
        raise ValueError('CANDIDATE_IDENTITY_MISMATCH')
    return manifest


def scrub_environment(environment, temporary):
    # An allowlist also removes unknown JDBC/credential aliases and PYTHONPATH.
    clean = {k: v for k, v in environment.items() if k in {'PATH', 'LANG', 'LC_ALL', 'TZ'}}
    clean.update(PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(temporary))
    return clean


def runtime_status(version, implementation='CPython'):
    if implementation != 'CPython' or not re.fullmatch(r'3\.14\.[0-9]+', version):
        raise ValueError('UNSUPPORTED_PYTHON_RUNTIME')
    return 'PINNED' if version == PYTHON else 'LOCAL_VERSION_NOT_PINNED'


def test_outcome(returncode, output):
    matches = re.findall(r'^Ran ([0-9]+) tests? in ', output, re.MULTILINE)
    count = int(matches[-1]) if matches else 0
    skipped = re.search(r'skipped=([0-9]+)', output)
    skips = int(skipped.group(1)) if skipped else 0
    errors = re.search(r'errors=([0-9]+)', output)
    failures = re.search(r'failures=([0-9]+)', output)
    passed = (returncode == 0 and count == EXPECTED_TESTS and skips == 0
              and re.search(r'^OK$', output, re.MULTILINE) is not None
              and errors is None and failures is None)
    return {'status': 'PASS' if passed else 'FAIL', 'tests': count, 'skips': skips,
            'errors': int(errors.group(1)) if errors else 0,
            'failures': int(failures.group(1)) if failures else 0, 'exitCode': returncode}


def qualification_matrix(offline=None, python='NOT_RUN'):
    def item(status, level, blocker):
        return {'status': status, 'proofLevel': level, 'blockingCondition': blocker,
                'unrunReason': blocker if status in {'NOT_RUN', 'UNPROVEN', 'BLOCKED'} else None}
    return {'overall': 'NOT_QUALIFIED', 'matrix': {
        'OFFLINE_FOCUSED': item((offline or {}).get('status', 'NOT_RUN'), 'EXECUTED_OFFLINE_ONLY' if offline else 'NONE', 'Complete selected suite required'),
        'PINNED_PYTHON': item(python, 'OBSERVED_RUNTIME', 'CPython 3.14.7 parity remains required'),
        'PHYSICAL_POSTGRESQL': item('NOT_RUN', 'PLAN_ONLY', 'Separate disposable-cluster authorization and verified PostgreSQL 18.6 required'),
        'GENERATED_APP_INTEGRATION': item('NOT_RUN', 'PLAN_ONLY', 'Separate bounded generated-app build/runtime authorization required'),
        'ACCEPTED_DEPLOYED_HISTORY': item('UNPROVEN', 'REFERENCE_SEMANTICS_ONLY', 'ACCEPTED_DEPLOYED_UPGRADE_NOT_PROVEN'),
        'OWNERSHIP': item('OFFLINE_BOUNDARY_VERIFIED' if offline and offline['status']=='PASS' else 'NOT_RUN', 'FILE_LEVEL_TESTS_ONLY', 'Deployment-wide ownership not proven'),
        'PROVENANCE': item('OFFLINE_BOUNDARY_VERIFIED' if offline and offline['status']=='PASS' else 'NOT_RUN', 'REAL_PURE_PLANNER_INTERFACE', 'Runtime/accepted deployment provenance not proven'),
        'SOURCE_TRUST': item('SOURCE_TRUST_PENDING', 'UNCHANGED_DECISION', 'Independent source trust pending'),
        'SECURITY_GATES': item('BLOCKED', 'UNCHANGED_DECISION', 'Gates 1/2/3 and T09 reservations preserved'),
        'RELEASE_GATES': item('BLOCKED', 'UNCHANGED_CRITERIA', '39 criteria / 21 historical blockers unchanged'),
        'RELEASE': item('BLOCKED', 'UNSEALED_CANDIDATE', 'NO_GO; Phase6 IN_PROGRESS; Phase7 NOT_STARTED; operational security NOT_ESTABLISHED')}}


def run_offline(root, interpreter, scratch, *, verified_patch=None, process=subprocess.run):
    root=Path(root);scratch=Path(scratch)
    if scratch.is_symlink() or scratch.resolve().is_relative_to(root.resolve()):
        raise ValueError('SCRATCH_MUST_BE_OUTSIDE_SOURCE')
    scratch.mkdir(mode=0o700,parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='qualification-',dir=scratch) as temp:
        env=scrub_environment(os.environ,temp)
        if verified_patch is not None:env['ACP_QUALIFICATION_VERIFIED_PATCH']=str(Path(verified_patch).resolve())
        probe=[str(interpreter),'-B','-I','-c','import json,platform;print(json.dumps([platform.python_version(),platform.python_implementation()]))']
        observed=process(probe,cwd=root,text=True,capture_output=True,env=env,timeout=15,check=True)
        version,implementation=json.loads(observed.stdout)
        parity=runtime_status(version,implementation)
        command=[str(interpreter),'-B','-m','unittest',*SELECTORS,'-v']
        try:
            result=process(command,cwd=root/'tooling/tests',text=True,capture_output=True,env=env,timeout=1500)
            stdout,stderr=result.stdout,result.stderr;code=result.returncode
        except subprocess.TimeoutExpired as error:
            def decoded(value):return value.decode(errors='replace') if isinstance(value,bytes) else value or ''
            stdout,stderr=decoded(error.stdout),decoded(error.stderr);code=124
        outcome=test_outcome(code,stdout+stderr)
        report=qualification_matrix(outcome,parity)
        report.update(mode='OFFLINE',candidateSourceDigest=source_digest(root),baselineCommit=BASELINE,
            wave3PatchSHA256=PATCH,candidateState='UNSEALED_CANDIDATE',runtime={'version':version,'implementation':implementation,'expected':PYTHON},
            runtimeProbe={'argv':probe,'exitCode':observed.returncode,'stdout':observed.stdout,'stderr':observed.stderr},
            run={'argv':command,'cwd':str(root/'tooling/tests'),'timeoutSeconds':1500,'environment':env,
                 'exitCode':code,'counts':outcome,'stdout':stdout,'stderr':stderr},
            physicalMethods={name:'NOT_RUN' for name in PHYSICAL_METHODS},ci='STAGED_NOT_EXECUTED')
        return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True);mode.add_argument('--offline',action='store_true');mode.add_argument('--plan-physical',action='store_true')
    for name in ('source','patch','manifest','manifest-sha256','candidate-sha256','scratch','output'):parser.add_argument('--'+name,required=True)
    parser.add_argument('--baseline',default=BASELINE);parser.add_argument('--python',default=sys.executable)
    args=parser.parse_args(argv)
    output=Path(args.output)
    if output.resolve().is_relative_to(Path(args.source).resolve()):raise ValueError('OUTPUT_MUST_BE_OUTSIDE_SOURCE')
    validate_candidate(args.source,args.patch,args.manifest,expected_manifest=args.manifest_sha256,expected_candidate=args.candidate_sha256,baseline=args.baseline)
    if args.offline:
        report=run_offline(args.source,args.python,args.scratch,verified_patch=args.patch)
    else:
        from phase6_postgresql import physical_plan
        report=qualification_matrix();report.update(mode='PLAN_PHYSICAL',candidateSourceDigest=args.candidate_sha256,baselineCommit=BASELINE,
            wave3PatchSHA256=PATCH,physicalPlan=physical_plan(Path('/tmp')/('acp-phase6-wave2-q-'+args.candidate_sha256[:12])),ci='STAGED_NOT_EXECUTED')
    manifest=validate_candidate(args.source,args.patch,args.manifest,expected_manifest=args.manifest_sha256,expected_candidate=args.candidate_sha256,baseline=args.baseline)
    report['manifestSHA256']=args.manifest_sha256
    report['baselineFileInventoryDigest']=hashlib.sha256(json.dumps(manifest['baselineFileHashes'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return 0 if not args.offline or report['run']['counts']['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
