"""Conservative closure predicates. Status labels never constitute evidence.

Every record is bound to the running sealed release, immutable approved inputs,
execution commit, dated files and a registered criterion-specific verifier.
Human decisions cannot be created by a test runner.
"""
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0,str(ROOT/'tooling'))


def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()


def current_binding():
    import sys
    sys.path.insert(0,str(ROOT/'tooling'))
    from target_worker import bundle_digest
    from deterministic_approval import approved_snapshot,record
    return {'bundleDigest':'sha256:'+bundle_digest(),
        'canonicalDigests':{d:approved_snapshot(d)['contentDigest'] for d in ('payment','case-management')},
        'approvalDigest':sha(json.dumps(record(),sort_keys=True).encode()),
        'executionCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}


def validate_record(number,record,root,binding,now):
    if type(record) is not dict:raise ValueError('MISSING_EVIDENCE')
    if record.get('criterion')!=number:raise ValueError('UNRELATED_CRITERION')
    for key,value in binding.items():
        if record.get(key)!=value:raise ValueError('STALE_OR_EDITED_'+key)
    when=datetime.fromisoformat(record['evaluatedAt'])
    if when.tzinfo is None or when>now+timedelta(minutes=5) or now-when>timedelta(hours=24):raise ValueError('STALE_EVIDENCE')
    artifacts=record['artifacts']
    if type(artifacts) is not list or not artifacts:raise ValueError('MISSING_ARTIFACT')
    files={}
    for entry in artifacts:
        relative=Path(entry['path']);path=root/relative
        if relative.is_absolute() or '..' in relative.parts or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():raise ValueError('NONEXISTENT_OR_UNTRUSTED_ARTIFACT')
        if sha(path.read_bytes())!=entry['sha256']:raise ValueError('MISMATCHED_ARTIFACT_DIGEST')
        files[relative.as_posix()]=path
    return files


def junit(files,required):
    found=set()
    for path in files.values():
        if path.suffix!='.xml':continue
        suite=ET.parse(path).getroot()
        for case in suite.iter('testcase'):
            if any(case.find(k) is not None for k in ('failure','error','skipped')):raise ValueError('TEST_NOT_GREEN')
            found.add(case.attrib['name'])
    if not set(required)<=found:raise ValueError('INCOMPLETE_CRITERION_TESTS:'+','.join(sorted(set(required)-found)))


def read_named(files,name):
    matches=[p for k,p in files.items() if k.endswith(name)]
    if len(matches)!=1:raise ValueError('EXACT_EVIDENCE_REQUIRED:'+name)
    return json.loads(matches[0].read_text())


def admission(files,binding):
    value=read_named(files,'task-interface-report.json')
    if value['bundleDigest'].removeprefix('sha256:')!=binding['bundleDigest'].removeprefix('sha256:'):raise ValueError('ADMISSION_BUNDLE')
    if set(value['domains'])!={'payment','case-management'}:raise ValueError('INCOMPLETE_ADMISSION')
    for domain,row in value['domains'].items():
        if row['canonicalDigest']!=binding['canonicalDigests'][domain] or row['blockers']:raise ValueError('ADMISSION_CANONICAL_OR_BLOCKERS')
        if set(row['checks'])!={'backend','frontend-lock','frontend-types','frontend-tests','frontend-build','real-browser'}:raise ValueError('INCOMPLETE_PIPELINE')
        stats=row['browser']['stats']
        if stats['unexpected'] or stats['flaky'] or stats['skipped'] or stats['expected']<12:raise ValueError('BROWSER_NOT_GREEN')
    # Status words above are deliberately not read. Actual test artifacts needed.
    junit(files,['exactSemanticFailureEnvelopeUsesVersionedHttpProfile'])


def security(files,binding,now):
    scan=read_named(files,'security-assessment.json')
    date=datetime.fromisoformat(scan['scanAt'])
    if date.tzinfo is None or date>now+timedelta(minutes=5) or now-date>timedelta(hours=24):raise ValueError('STALE_SECURITY_SCAN')
    if scan['bundleDigest']!=binding['bundleDigest']:raise ValueError('SECURITY_BUNDLE')
    if scan['coverage']!=['packaged-backend','npm-production','compiler','build-plugins']:raise ValueError('INCOMPLETE_SECURITY_COVERAGE')
    if scan['findings'] or scan['unknownComponents']:raise ValueError('UNRESOLVED_SECURITY_FINDINGS')
    for package in scan['packages']:
        path=next((p for p in files.values() if p.name==package['file']),None)
        if path is None or sha(path.read_bytes())!=package['sha256']:raise ValueError('MISMATCHED_PACKAGE_DIGEST')


def evolution(files,binding):
    value=read_named(files,'accepted-deployed-evolution.json')
    # A public synthetic authority cannot approve a new business evolution.
    from deterministic_approval import APPROVED,authority,WHEN
    for domain in ('payment','case-management'):
        row=value['domains'][domain]
        if row['snapshotDigest']!=APPROVED[domain]['contentDigest'] or row['planDigest']!=APPROVED[domain]['planDigest']:raise ValueError('UNAPPROVED_SEMANTIC_MIGRATION')
        authority().verify_historical(row['proof'],row['approvalRequest'],WHEN)
        if row['approvalRequest']['contentDigest']!=row['snapshotDigest'] or row['approvalRequest']['planDigest']!=row['planDigest']:raise ValueError('EDITED_APPROVAL_RECORD')
        if row['appliedMigrationDigests']!=row['expectedMigrationDigests'] or not row['appliedMigrationDigests']:raise ValueError('INCOMPLETE_DATABASE_UPGRADE')
    junit(files,['approvedEvolutionPreservesBehaviorAndOwnership'])


def deployment(files,number,accepted_reviews):
    value=read_named(files,'deployment-review.json')
    row=value['criteria'][str(number)]
    # Automated evidence cannot create deployment or human review authority.
    if row.get('authority')!='EXPLICIT_HUMAN_ACCEPTANCE' or row.get('verification')!='REVIEWED_EXTERNAL_OBLIGATION':raise ValueError('UNSATISFIED_DEPLOYMENT_OBLIGATION')
    review=next(p for p in files.values() if p.name=='deployment-review.json')
    if accepted_reviews.get(str(number))!=sha(review.read_bytes()):raise ValueError('HUMAN_REVIEW_AUTHORITY_NOT_REGISTERED')


def validate(number,files,binding,now,accepted_reviews):
    if number in (1,2,6,34):
        value=read_named(files,'baseline.json')
        if value['auditExecutionCommit']!=binding['executionCommit'] or value['bundleDigest']!=binding['bundleDigest']:raise ValueError('BASELINE_BINDING')
        baseline=value['mergedMainCommit']
        if baseline!='7e4e3438179e7a446c5f3737ad1d6d9cb07a96ea':raise ValueError('WRONG_REVIEWED_BASELINE')
        subprocess.run(['git','merge-base','--is-ancestor',baseline,'HEAD'],cwd=ROOT,check=True,capture_output=True)
        from target_release import verify_preserved_releases,verify_production_upgrade
        prior=json.loads(subprocess.check_output(['git','show',baseline+':targets/spring-vue-postgres/release-contract.json'],cwd=ROOT,text=True))
        current=json.loads((ROOT/'targets/spring-vue-postgres/release-contract.json').read_text())
        verify_preserved_releases(prior,current)
        if number==6:
            verify_production_upgrade('acp-spring-vue-postgres/0.4.0','acp-spring-vue-postgres/0.5.0',current)
            try:verify_production_upgrade('acp-spring-vue-postgres/0.1.0','acp-spring-vue-postgres/0.5.0',current)
            except ValueError:pass
            else:raise ValueError('TARGET01_PRODUCTION_UPGRADE_MUST_BE_REJECTED')
        if number in (1,34):
            protected=['contracts','test-corpus','docs/phase6-final-closure-audit.md','targets/spring-vue-postgres/evidence/phase6-final-closure.json']
            if subprocess.check_output(['git','diff',baseline,'HEAD','--',*protected],cwd=ROOT):raise ValueError('HISTORICAL_BYTES_CHANGED')
        return
    if number in (35,36,38,39):
        value=read_named(files,'audit-state.json')
        if value['phase6']!='IN_PROGRESS' or value['phase7']!='NOT_STARTED' or value['closureAuthority']!='EXPLICIT_HUMAN_REVIEW_REQUIRED':raise ValueError('UNAUTHORIZED_PHASE_DISPOSITION')
        if number==36 and value['recommendation']!='PHASE6_CLOSURE_BLOCKED':raise ValueError('PREMATURE_CLOSURE_RECOMMENDATION')
        if number==38:
            workflow=(ROOT/'.github/workflows/acp-contracts.yml').read_text()
            job=workflow.split('  phase6-closure-audit:')[1]
            if 'continue-on-error' in job or 'tooling/audit/phase6.py' not in job or 'if: always()' not in job:raise ValueError('CLOSURE_CI_POLICY')
        return
    if number in (3,7,11):return admission(files,binding)
    if number==5:return evolution(files,binding)
    if number==21:return security(files,binding,now)
    if number in DEPLOYMENT:return deployment(files,number,accepted_reviews)
    spec=SPECS[number]
    if spec['tests']:return junit(files,spec['tests'])
    raise ValueError('INVALID_CRITERION_DEFINITION')


def assess(report,root=None,binding=None,now=None,accepted_reviews=None):
    root=Path(root or report.get('evidenceRoot','/nonexistent'))
    binding=binding or current_binding();now=now or datetime.now(timezone.utc)
    rows=[]
    records=report.get('criterionEvidence',{})
    for number,spec in SPECS.items():
        reason=None
        try:
            record=records.get(str(number))
            files=validate_record(number,record,root,binding,now)
            validate(number,files,binding,now,accepted_reviews or {})
        except (ValueError,KeyError,TypeError,OSError,ET.ParseError,subprocess.CalledProcessError) as error:reason=str(error)
        rows.append({'requirement':number,'area':spec['area'],'status':'BLOCKED' if reason else 'PASS',
            'detail':spec['detail'],'evidenceRequired':spec['evidenceRequired'],
            'validationFunction':'criteria.validate/'+str(number),'passConditions':'All binding, artifact and criterion-specific predicates satisfied',
            'blockedConditions':'Missing, malformed, stale, unrelated or failing evidence; unresolved human authority',
            'deploymentObligationDisposition':'EXPLICIT_HUMAN_REVIEW_REQUIRED' if number in DEPLOYMENT else 'NOT_A_SUBSTITUTE_FOR_AUTOMATED_EVIDENCE',
            'failureReason':reason,'evaluationProvenance':binding})
    if report.get('executionError'):rows.append({'requirement':0,'area':'Audit execution','status':'BLOCKED','detail':report['executionError'],'failureReason':'AUDIT_EXECUTION_EXCEPTION'})
    return rows


DEPLOYMENT={12,13,15,26,27,28}
SPECS={}
SPECS[1]={'area': 'Immutable baseline', 'detail': 'Exact merged baseline and execution commit; clean checkout, protected history and sealed bundle checked.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[2]={'area': 'Release immutability', 'detail': 'Intentional 0.5.0 successor; exact prior release entries retained and verified against the reviewed baseline.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[3]={'area': 'Full actual admission', 'detail': 'Original strict CLI with --full-admission --run-builds; no expected-blocker allowance.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[4]={'area': 'Integrated final entrypoint', 'detail': 'Audit orchestrates full strict admission, supplemental browser, fault/materializer/history, provenance and package checks; exits 2 for unmet closure criteria.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[5]={'area': 'Accepted-history deployed evolution', 'detail': 'Semantic six-step witnesses and independent upgrades do not prove every accepted deployed transition. Canonical 0.3 backfill storage currently falls through to text instead of bytea; no deployed 0.2→0.3 chain or sequential 0.1→0.2→0.3→0.4 proof.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[6]={'area': 'Historical provenance', 'detail': 'Policy C: target 0.1 excluded from supported production upgrade window. Historical test adapter is forensic evidence only; 0.2/0.3 ordinary reader remains production policy.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[7]={'area': 'Scheduler observation', 'detail': 'Exact occurrence-scoped recovery assertions retain non-skipped count. Separate deterministic scheduler observation is fixed immediately after the original occurrence; invocation clock alone observes actual PostgreSQL commit time.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[8]={'area': 'Integrated ownership', 'detail': 'Actual compiler replacement/human identity preservation/unapproved AI rejection plus retained approved AI/framework/CAS/unknown-file tests. Complete integrated cross-owner transition matrix remains incomplete.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[9]={'area': 'Provenance completeness', 'detail': 'Exact ArtifactPlans retained separately from conservative sidecar origin sets. Host per-artifact revisions checked; exhaustive target-object bijection/input-digest reconciliation and HUMAN-owned artifact provenance remain incomplete.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[10]={'area': 'Traceability', 'detail': 'Machine-readable family→basis→ID/revision→host-artifact trace exists; suite-level runtime links do not prove a per-object assertion chain for every representative.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[11]={'area': 'Production browser review', 'detail': '24 production-browser journeys plus 16 exact HTTP outcomes against real Spring/PostgreSQL; report preserves database facts and axe incomplete results.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[12]={'area': 'Manual accessibility', 'detail': 'MANUAL_ACCESSIBILITY_REVIEW=OUTSTANDING; permitted before deployment, not represented as automated evidence. Human acceptance of this disposition is still required.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[13]={'area': 'Browser support', 'detail': 'SUPPORTED_BROWSER_PROFILE=CHROMIUM only; Firefox/WebKit OUTSTANDING, not supported by this audit.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[14]={'area': 'Deployable package', 'detail': 'Deterministic tar audit binds jar/assets/migrations/profile/provenance/deployment requirements/configuration inventory. An enforced exact startup configuration schema and deployable non-test identity/principal/transport integrations are still missing.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[15]={'area': 'Container/package profile', 'detail': 'Chosen audit package is a reproducible JAR+static-assets tar, not OCI. Java 21/Node generation environment bound; no image digest or portable architecture/container guarantee claimed.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[16]={'area': 'Startup configuration', 'detail': 'Versioned production startup configuration validated before background activation; require focused startup tests.', 'tests': ['productionConfigurationFailsBeforeActivation', 'activeDeliveryRequiresTransport'], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': ['productionConfigurationFailsBeforeActivation', 'activeDeliveryRequiresTransport']}}
SPECS[17]={'area': 'Test-only exclusion', 'detail': 'Packages rebuilt using restored production identity; inspect archive entries and decompressed JS/class content for BrowserServer, decoder, tokens, test endpoints and credentials.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[18]={'area': 'Transitive dependency inventory', 'detail': 'Package JAR dependencies, npm lock and Python distributions inventoried. Maven plugin/build graph checksums and full transitive immutable resolution lock not complete; inventory alone is not a lock.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[19]={'area': 'SBOM', 'detail': 'CycloneDX 1.6 JSON from actual packaged backend JARs and frontend lock; generation/build-only tools distinguished in evidence.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[20]={'area': 'License review', 'detail': 'License declarations inventoried; unknowns/redistribution notices and compatibility require resolution and human/legal review. No automatic legal approval.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[21]={'area': 'Current vulnerability assessment', 'detail': 'npm audit and OSV timestamped runtime assessments are independent of deterministic package bytes. Missing/unscored/high/critical findings block closure; exact results in package evidence. Compiler/build-plugin vulnerability coverage is incomplete even if runtime scanners return zero findings.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[22]={'area': 'Worker confinement', 'detail': 'Retained real sandbox/protocol/resource supervision tests rerun. Exhaustive process/identity/clock syscalls plus memory/CPU exhaustion under the production sandbox are not all exercised by existing tests.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[23]={'area': 'Materializer', 'detail': 'Retained traversal/symlink/stale-CAS/concurrent-writer/crash/manual/human/AI/framework fault suites rerun. Power-loss durability and hostile same-user mutation remain Phase 11 concerns.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[24]={'area': 'Deployment migration failure/recovery', 'detail': 'Existing migration planner, Flyway repeat/legacy upgrade tests do not cover complete unavailable-DB/validation/partial-upgrade/incompatible-schema/safe-retry deployment matrix. Destructive rollback NOT CLAIMED.', 'tests': ['failedBackfillRollsBackDdl', 'requiredFieldRejectsNull'], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': ['failedBackfillRollsBackDdl', 'requiredFieldRejectsNull']}}
SPECS[25]={'area': 'Real application restart matrix', 'detail': 'Lost-process idempotency/outbox/Job/lifecycle runtime tests exist. A complete real process restart with all specified committed state simultaneously is not proven.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[26]={'area': 'Deployment obligations', 'detail': 'Every generated OUTSTANDING row retained and classified in domain evidence; none waived. Release blockers are separately enumerated.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[27]={'area': 'Encryption/TLS', 'detail': 'At-rest, backup encryption, TLS termination and key management remain REQUIRED_BEFORE_PRODUCTION_DEPLOYMENT; not runtime guarantees.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[28]={'area': 'Physical destruction', 'detail': 'ANONYMIZE does not establish physical erasure, WAL/replica/backup destruction; retained deployment obligations.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[29]={'area': 'Production OIDC integration', 'detail': 'Required identity()/onIdentityChange()/accessToken()/permissions() contract documented. No accepted non-test provider adapter fixture proving token acquisition/change notification/configuration end-to-end.', 'tests': ['oidcAcquisitionIdentityChangeExpiredAndWrongTenant'], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': ['oidcAcquisitionIdentityChangeExpiredAndWrongTenant']}}
SPECS[30]={'area': 'Performance baseline', 'detail': 'Build durations/package sizes are measured; bounded Query/Action/startup/browser-load/concurrent-rate performance measurements are not complete. No synthetic SLO promised.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[31]={'area': 'Resource scaling', 'detail': 'Approved fixtures within limits pass; no larger valid generated UI fixture/node-limit scaling and provenance-growth curve accepted.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[32]={'area': 'Generation/package determinism', 'detail': 'Independent compiler contexts compare ArtifactPlan digest and repeated package builds compare exact bytes. Package builds share the same checkout/build cache; two independently materialized clean package builds are still required. Runtime random keys excluded.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[33]={'area': 'Fresh hosted reproduction', 'detail': 'Historical run 37910102322: contracts, phase5-experiments, phase5c-hard-gates and phase6-target passed; closure audit performed and deliberately exited 2 PHASE6_CLOSURE_BLOCKED. Fresh successor hosted evidence is required.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[34]={'area': 'Historical contracts', 'detail': 'Protected contract/corpus/release/ADR bytes compared against immutable merged baseline.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[35]={'area': 'Human closure authority', 'detail': 'Audit recommendation does not mark Phase 6 COMPLETE; stop for explicit human review.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[36]={'area': 'Recommendation', 'detail': 'Only PHASE6_CLOSURE_BLOCKED or PHASE6_CLOSURE_RECOMMENDED; blocked report lists remediation criteria.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[37]={'area': 'Bound machine-readable report', 'detail': 'Baseline, exact execution commit, Canonical/bundle/IR/UI/migration/package/SBOM/security/browser/fault/history/obligation evidence bound with digests.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[38]={'area': 'Dedicated closure CI', 'detail': 'Separate dependent job; no continue-on-error. BLOCKED audit exits nonzero rather than faking green.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}
SPECS[39]={'area': 'Phase disposition', 'detail': 'Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED; closure cannot be accepted automatically.', 'tests': [], 'evidenceRequired': {'binding': ['bundleDigest', 'canonicalDigests', 'approvalDigest', 'executionCommit', 'evaluatedAt'], 'artifacts': 'Existing files with verified SHA-256; no self-reported status accepted', 'criterionTests': []}}

_WITNESSES={
1:'exactReviewedBaselineAndProtectedHistory',2:'previousReleasedBundlesRemainImmutable',
4:'closureEntrypointRunsEveryRequiredProducer',6:'productionEvolutionWindowExcludesTarget01',
8:'integratedCrossOwnerTransitions',9:'everyTargetObjectHasExactRevisionAndInputDigest',
10:'representativeObjectRuntimeTraceability',14:'productionDistributionStartsWithDeploymentConfiguration',
17:'productionPackagesExcludeTestAuthority',18:'transitiveResolutionLockIncludesBuildPlugins',
19:'sbomMatchesEveryPackagedDependency',20:'licensesAndRedistributionNoticesAccepted',
22:'productionSandboxDeniesSyscallsAndBoundsCpuMemory',23:'materializerRejectsTraversalStaleCasAndCrash',
25:'restartPreservesAllCommittedRuntimeFamilies',30:'measuredApplicationPerformanceBaseline',
31:'validLargeFixtureScaling',32:'independentCleanPackageBuildsMatch',
33:'freshHostedSuccessorAuditPerformed',34:'historicalContractBytesUnchanged',
35:'humanClosureAuthorityRemainsRequired',36:'recommendationReflectsEveryBlocker',
37:'reportBindsEveryEvidenceArtifact',38:'dedicatedClosureJobDistinguishesBlockedAndException',
39:'phase6InProgressPhase7NotStarted'}
for _number,_name in _WITNESSES.items():
    SPECS[_number]['tests']=[_name]
    SPECS[_number]['evidenceRequired']['criterionTests']=[_name]
