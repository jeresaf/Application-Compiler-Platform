"""Build evidence-bound coverage; documentation or a test name alone never earns PASS."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
B='test_gateway_integration.IntegrationTests.'
S='test_security_remediation.SecurityRemediationTests.'
P='test_preservation.PreservationTests.test_all_unauthorized_tracked_inputs_remain_exactly_unchanged'
HAPPY=B+'test_native_genesis_transition_signed_receipt_audit_retry_export_restore'
CRASH=B+'test_crash_at_every_native_and_external_boundary_then_reconcile'
SIGNATURE=B+'test_signature_and_closed_envelope_security_matrix'
ROWS=[]


def add(section,control,source,negative,positive=HAPPY,limitation='Laboratory evidence only; no operational authority or deployment.'):
    ROWS.append({'id':f'A{section:02d}-{sum(r["authorizationSection"]==section for r in ROWS)+1:02d}',
        'authorizationSection':section,'control':control,'source':source,
        'positiveTests':[positive] if positive else [],'negativeTests':[negative] if negative else [],
        'knownLimitation':limitation})


def controls():
    if ROWS:return ROWS
    sec='engineering/route_a_gateway/security.py#'
    gate='engineering/route_a_gateway/gateway.py#'
    store='engineering/route_a_gateway/storage.py#'
    ev='engineering/route_a_gateway/evidence.py#'
    arc='engineering/route_a_gateway/archive.py#'
    fresh='engineering/route_a_gateway/freshness.py#'
    add(1,'Exact documentary instruction/request identity; no fabricated operational approval',
        'verification/route_a/test_preservation.py#PreservationTests',None,P,
        'Read-only Git blob measurement; no negative mutation is performed on historical records. Documentary approval is not an authenticated operational proof.')
    add(2,'Working external library uses native bootstrap/propose/review/approve/apply/audit/export/restore',gate+'Gateway',CRASH)
    add(3,'approval/2 and exact native request/verdict shape',sec+'Authority._verify',SIGNATURE)
    for field in ('operationId','repositoryId','applicationId','authorityConfigurationDigest','planDigest',
                  'candidateDigest','requiredScopes','expectedHead','authorPrincipal','reviewerPrincipal',
                  'verificationPolicyVersion','issuedAt/notBefore/expiresAt','nonce','identityEvidenceDigest','grantEvidenceDigest'):
        add(3,'Exact approval subject/identity binding: '+field,sec+'Authority._verify',SIGNATURE)
    add(3,'Real REVIEW_REQUIRED and APPROVED event linkage, no ChangeSet-ID-only identity',gate+'_bind_approval',
        B+'test_changed_review_event_new_proposal_cannot_inherit_approval')
    add(4,'Authorized source paths; native/sealed/historical/frozen inputs and workflow unchanged',
        'verification/route_a/test_preservation.py#PreservationTests',None,P,
        'Git-clean-filtered committed bytes, accounting for pre-existing CRLF; separate sealed-release check measures bundle identity.')
    for control,impl,negative in [
        ('Repository-specific identity',sec+'Host.identity',B+'test_duplicate_genesis_and_cross_repository_replay'),
        ('Immutable invocation context and host-owned trust',sec+'Context',B+'test_immutable_host_and_context_copies'),
        ('Authenticated callers and grants',sec+'Host.authenticate',B+'test_authentication_and_independent_reviewer_grants'),
        ('Independent reviewer policy',sec+'Authority._verify',B+'test_self_approval_even_with_both_grants_and_valid_signature_is_rejected'),
        ('Exact event binding across approval/application',gate+'_bind_approval',B+'test_changed_approved_event_and_proof_rejected'),
        ('Trusted current native/witness head',gate+'_published_head',B+'test_stale_head_and_changed_read_set_fail_before_new_append'),
        ('Controlled fenced native access',store+'Fence',S+'test_concurrent_independent_approval_and_apply_are_fenced'),
        ('Historical authentication',arc+'HistoricalAuthority',S+'test_missing_historical_configuration_key_and_grant_versions_fail_closed'),
        ('Independent retry/read authorization',gate+'retrieve',S+'test_receipt_read_requires_independent_grant_even_for_original_author'),
        ('Quarantined export/restore',arc+'restore',B+'test_restore_corruption_wrong_identity_missing_authority_receipts_truncation')]:add(5,control,impl,negative)
    for control,negative in [
        ('Maintained-library Ed25519 verification, exact canonical signed bytes',SIGNATURE),
        ('Tampered/malformed signature, wrong key/algorithm rejection',SIGNATURE),
        ('Wrong repository/application and altered candidate/plan/scopes rejection',SIGNATURE),
        ('Expired/future proof rejection',B+'test_expiry_between_approve_and_apply'),
        ('Disposable principals, issuer/audience, keys and NON_AUTHORITATIVE_TEST_ONLY classification',B+'test_original_application_and_nonlaboratory_configuration_rejected')]:
        add(6,control,sec+'Host.signed',negative)
    add(6,'Operational algorithm/issuer/root/custody configurability',sec+'Host',None,None,
        'INCOMPLETE: laboratory-only Host enables Ed25519; production provider selection, custody and online configuration/key rotation are not established or authorized.')
    for control,negative in [
        ('PROPOSE has authenticated author, exact base/ChangeSet, no reviewer proof or nonce consumption',B+'test_propose_and_review_have_no_proof_or_approval_reservation'),
        ('REVIEW is author-only against exact PROPOSED event, still proof-free',B+'test_changed_review_event_new_proposal_cannot_inherit_approval'),
        ('APPROVE requires independent proof, exact REVIEW_REQUIRED event, durable reservation',B+'test_authentication_and_independent_reviewer_grants'),
        ('APPLY pins actual approved event, unchanged proof, current authorization and head',B+'test_changed_approved_event_and_proof_rejected'),
        ('GENESIS uses exact plan/author/proof/retry without fabricated ordinary proposal version',B+'test_genesis_has_no_proposal_binding_and_rejects_fabricated_version'),
        ('Changed proposal/rebase requires fresh review and approval',B+'test_changed_review_event_new_proposal_cannot_inherit_approval'),
        ('Cross-repository approval cannot be reused',B+'test_duplicate_genesis_and_cross_repository_replay')]:add(7,control,gate+'Gateway',negative)
    for state in ('RESERVED','JOURNAL_COMMITTED','RECEIPT_STORED','WITNESSED','PUBLISHED'):
        add(8,'Durable closed-state progression through '+state,store+'Ledger.transition',CRASH)
    add(8,'No unauthorized epoch/reservation write before authentication and proof verification',gate+'Gateway',
        S+'test_rejected_authority_cannot_allocate_operation_epochs_or_reservations')
    for control,negative in [
        ('REJECTED/EXPIRED preserve consumed identities and require proven native absence',B+'test_retired_nonce_is_retained_and_expiry_cannot_hide_commit'),
        ('RECOVERY_REQUIRED inspects actual durable effects',B+'test_missing_native_commit_after_stable_commit_remains_recovery_required'),
        ('QUARANTINED has no automatic release',B+'test_authenticated_witness_conflict_quarantines_unpublished_commit'),
        ('Unique operation/approval IDs and nonces, immutable subjects/bindings',B+'test_replayed_nonce_and_approval_id_rejected_after_publication'),
        ('CAS versions, valid epochs, evidence, no skipping or illegal edges',B+'test_durable_ledger_cas_nonce_and_illegal_transitions'),
        ('No cross-store atomicity; commit and ledger can diverge and must reconcile',CRASH)]:add(8,control,store+'Ledger',negative)
    for control,negative in [
        ('Independent processes cannot write concurrently through gateway',S+'test_concurrent_independent_approval_and_apply_are_fenced'),
        ('Lost ownership and SIGTERM release of kernel lock',S+'test_sigterm_lock_holder_releases_kernel_lock'),
        ('Interrupted native commit / commit before ledger / response after ledger',CRASH),
        ('Persisted receipt before response loss',CRASH),
        ('Witness outage after commit prevents publication',B+'test_unpublished_receipt_never_retrieved'),
        ('Conflicting witness observation quarantines operation',B+'test_witness_conflict_during_recovery_also_quarantines'),
        ('Uncertain effect remains in recovery; no substitute journal or receipt',S+'test_stale_native_backup_cannot_recover_a_known_commit')]:add(9,control,gate+'recover',negative)
    add(9,'Privileged same-UID/root and cross-host confinement',store+'Fence',None,None,
        'BLOCKED: no operational confinement/cross-host deployment is authorized. Replaced inode is detected at boundaries; a privileged writer can bypass cooperative fencing.')
    add(10,'Versioned signed receipt binds repository/application/operation/sequence/heads/candidate/plan/proof/configuration/actual commit/service identity',
        ev+'verify_receipt',S+'test_correctly_signed_stale_witness_and_cross_repository_receipt_rejected')
    add(10,'Signed service claim alone cannot authorize semantic acceptance',ev+'verify_witness_submission',
        B+'test_signed_service_claim_without_authentic_human_approval_is_rejected_by_witness')
    add(10,'Unseen backdated commit cannot bypass current service-key authority',ev+'verify_witness_submission',
        S+'test_unwitnessed_backdated_commit_cannot_bypass_current_service_key_revocation')
    for control,negative in [
        ('Configurable independent signed witness, challenge freshness and exact receipt digest',B+'test_receipt_corruption_and_witness_fork_stale_outage'),
        ('Exact head continuity and monotonic independently retained checkpoints',S+'test_authenticated_witness_rollback_after_reader_restart_rejected'),
        ('Freshly signed fork/rollback and stale signed response rejected',S+'test_correctly_signed_stale_witness_and_cross_repository_receipt_rejected'),
        ('Outage and eventual recovery, no publication before witnessing',B+'test_unpublished_receipt_never_retrieved')]:add(11,control,ev+'WitnessClient',negative)
    for control,negative in [
        ('authenticate / verify / verify_historical preserve native verdict shape',SIGNATURE),
        ('Original bytes, proof-time identity/scopes/key/grants/configuration version',S+'test_missing_historical_configuration_key_and_grant_versions_fail_closed'),
        ('Current revocation chronology distinguishes later revocation from compromise',S+'test_later_revocation_preserves_prior_history_but_compromise_invalidates_it'),
        ('Invalid historical reviewer grants rejected',S+'test_invalid_historical_reviewer_grant_is_not_structural_admission'),
        ('Exact independently derived predecessor and actual committed operation',S+'test_independent_predecessor_digest_rejects_changed_historical_chain'),
        ('Duplicate historical approval IDs/nonces rejected',S+'test_duplicate_historical_approval_identity_rejected'),
        ('Structural success does not imply authenticated history admission',S+'test_invalid_historical_reviewer_grant_is_not_structural_admission')]:add(12,control,arc+'HistoricalAuthority',negative)
    for control,negative in [
        ('Separate authenticated RECEIPT_READ, original caller and current grants',S+'test_receipt_read_requires_independent_grant_even_for_original_author'),
        ('Exact repository/application/operation/event/plan/proof/retry receipt bindings',B+'test_retry_read_rejects_all_binding_changes_and_no_native_apply_shortcut'),
        ('Expired/revoked caller or unavailable authority fails read',S+'test_fresh_authority_loopback_positive_and_provider_outage_no_cache'),
        ('Unpublished receipt unavailable',B+'test_unpublished_receipt_never_retrieved'),
        ('Native retry is not a read gateway; RECOVER cannot return receipt bytes',B+'test_recovery_grant_cannot_bypass_independent_receipt_read')]:add(13,control,gate+'retrieve',negative)
    for control,negative in [
        ('Journal/snapshots/plans/proofs/configuration/ledger/receipts/checkpoints/source/file hashes included and authenticated',B+'test_export_service_attestation_protects_metadata_and_exporter_identity'),
        ('Restore begins and remains quarantined; authenticated historical audit required',B+'test_native_genesis_transition_signed_receipt_audit_retry_export_restore'),
        ('Corrupted/missing receipts/trust/truncated/wrong-repository archives rejected',B+'test_restore_corruption_wrong_identity_missing_authority_receipts_truncation'),
        ('Stale backup and conflicting external checkpoint rejected',B+'test_stale_backup_after_real_second_commit_is_rejected'),
        ('Retired identities cannot be erased at unchanged journal head',B+'test_restore_cannot_erase_retired_nonce_at_unchanged_journal_head')]:add(14,control,arc+'restore',negative)
    add(14,'Portable multi-version authority-policy history and large-history backup',arc+'export',None,None,
        'INCOMPLETE: one immutable registered configuration is exported. Fresh dynamic revocation evidence is independently retained and must be fetched again; online multi-version rotation and streaming backups are unsupported.')
    add(15,'Only artificial applications/repositories, disposable keys, synthetic sessions, temporary files and loopback providers',
        sec+'Host',B+'test_original_application_and_nonlaboratory_configuration_rejected')
    add(15,'Original PAYMENT/CASE histories cannot be initialized; SQL/data-binding/deployment scopes isolated',
        gate+'downstream',B+'test_history_scopes_never_authorize_sql_or_deployment')
    # Every mandatory negative family in authorization section 16 is explicitly indexed.
    for control,negative in [
        ('Wrong repository/application/author/reviewer, self-approval and absent reviewer grant',B+'test_authentication_and_independent_reviewer_grants'),
        ('Expired/future proof, revoked grant/key, unknown key/signature/envelope tamper',SIGNATURE),
        ('Modified candidate/plan/scopes and changed proposal version',B+'test_changed_review_event_new_proposal_cannot_inherit_approval'),
        ('Replayed nonce and duplicate genesis',S+'test_nonce_replay_after_restart_is_rejected_with_authentic_signature'),
        ('Stale head and changed read set',B+'test_stale_head_and_changed_read_set_fail_before_new_append'),
        ('Concurrent writers, lost ownership and actual process crashes',CRASH),
        ('Duplicate retry and unauthorized receipt read',B+'test_retry_read_rejects_all_binding_changes_and_no_native_apply_shortcut'),
        ('Corrupted receipt, witness outage/fork/staleness',B+'test_receipt_corruption_and_witness_fork_stale_outage'),
        ('Truncated history/stale backup/missing authority/quarantine bypass',B+'test_restore_corruption_wrong_identity_missing_authority_receipts_truncation'),
        ('Unauthorized SQL or deployment attempt',B+'test_history_scopes_never_authorize_sql_or_deployment'),
        ('New reviewer/key/grant revocations and post-compromise history',S+'test_later_revocation_preserves_prior_history_but_compromise_invalidates_it'),
        ('Authority outage/stale cache/conflicting versions/expired configuration',S+'test_observed_expiry_cannot_be_hidden_by_replaying_older_signed_status'),
        ('Writer termination/replacement/stale epoch/tampered external ledger',S+'test_tampered_external_ledger_is_rejected_before_native_apply'),
        ('Interrupted publication and lost recovery response',S+'test_interrupted_publication_and_lost_recovery_response_do_not_duplicate')]:add(16,control,gate+'Gateway',negative)
    for letter,control,negative in [
        ('A','Genuine authenticated test cryptography',SIGNATURE),('B','Repository cannot be substituted',B+'test_duplicate_genesis_and_cross_repository_replay'),
        ('C','Independent reviewer',B+'test_self_approval_even_with_both_grants_and_valid_signature_is_rejected'),
        ('D','Exact native event binding',B+'test_changed_approved_event_and_proof_rejected'),
        ('E','Durable ledger',B+'test_durable_ledger_cas_nonce_and_illegal_transitions'),('F','Crash/recovery',CRASH),
        ('G','Participating writer fencing',S+'test_concurrent_independent_approval_and_apply_are_fenced'),
        ('H','Signed receipt integrity',S+'test_correctly_signed_stale_witness_and_cross_repository_receipt_rejected'),
        ('I','Independent witness controls publication',B+'test_unpublished_receipt_never_retrieved'),
        ('J','Authenticated historical tamper rejection',S+'test_invalid_historical_reviewer_grant_is_not_structural_admission'),
        ('K','Authorized retry',S+'test_receipt_read_requires_independent_grant_even_for_original_author'),
        ('L','Quarantined export/restore',B+'test_restore_corruption_wrong_identity_missing_authority_receipts_truncation'),
        ('O','Test authority cannot qualify original reference histories',B+'test_original_application_and_nonlaboratory_configuration_rejected')]:add(17,letter+': '+control,gate+'Gateway',negative)
    for letter,control in [('M','Native Canonical/generator contracts unchanged'),('P','Sealed 0.5.0 unchanged')]:
        add(17,letter+': '+control,'verification/route_a/test_preservation.py#PreservationTests',None,P)
    add(17,'N: complete existing compiler/regression suite', 'verification/route_a/test_preservation.py#PreservationTests',None,None,
        'INCOMPLETE: one existing opt-in disposable PostgreSQL test is explicitly skipped, never silently counted as passed; complete measured suite results are retained separately.')
    add(18,'Ubuntu 24.04 / CPython 3.14.7 / Node 24.21.0 and all original gates retained',
        'verification/route_a/test_preservation.py#PreservationTests',None,P)
    add(18,'Exact-source hosted jobs and performed closure with real blockers, no overall PASS on exit 2',
        'verification/route_a/security_coverage.py#build',None,None,
        'Evidence-only control: final hosted observation required; closure remains a distinct release gate.')
    add(19,'Required source/test/provider/ledger/crypto/witness/recovery/review/dependency/hash deliverables',
        'verification/route_a/security_coverage.py#build',None,None,
        'Artifact/hash inspection and independent review required; documents are not executable security evidence.')
    add(20,'Stop for independent review; no operational authority/history/genesis/transition/data binding/SQL/deployment',
        gate+'downstream',B+'test_history_scopes_never_authorize_sql_or_deployment')
    for control,negative in [
        ('Current signed provider challenge and no cached fallback',S+'test_fresh_authority_loopback_positive_and_provider_outage_no_cache'),
        ('New reviewer revocation',S+'test_new_reviewer_revocation_blocks_existing_approval_apply'),
        ('New signing-key revocation',S+'test_new_signing_key_revocation_blocks_existing_approval'),
        ('Expired configuration and durable negative floor',S+'test_observed_expiry_cannot_be_hidden_by_replaying_older_signed_status'),
        ('Conflicting version persists quarantine',S+'test_conflicting_signed_version_quarantines_observer_across_restart'),
        ('Conflicting configuration cannot be hidden by older status',S+'test_conflicting_configuration_cannot_be_hidden_by_older_status'),
        ('Rollback and revocation erasure after restart rejected',S+'test_durable_authority_rollback_and_revocation_erasure_rejected_after_restart'),
        ('Stale signed authority/challenge replay rejected',S+'test_stale_signed_authority_and_replayed_challenge_rejected'),
        ('Provider outage after real commit prevents publication',S+'test_provider_outage_after_native_commit_blocks_publication_then_recovers')]:
        add(16,'Remediation: '+control,fresh+'FreshnessClient',negative,S+'test_fresh_authority_loopback_positive_and_provider_outage_no_cache')
    add(11,'First witnessing requires live reviewer authority; exact already-witnessed retry uses historical verification',
        ev+'verify_witness_submission',S+'test_unwitnessed_backdated_commit_cannot_bypass_current_reviewer_revocation',
        S+'test_exact_witnessed_retry_after_later_revocation_preserves_historical_acceptance')
    for identity in ('approval_id','nonce'):
        add(11,'Independent witness consumes unique '+identity,'verification/route_a/lab_provider.py#Lab',
            S+'test_independent_witness_rejects_duplicate_'+identity+'_despite_valid_native_proof')
    return ROWS


def test_evidence(ref,log):
    module,cls,method=ref.split('.')
    tree=ast.parse((ROOT/'verification/route_a'/f'{module}.py').read_text())
    assert any(isinstance(c,ast.ClassDef) and c.name==cls and any(isinstance(n,ast.FunctionDef) and n.name==method for n in c.body) for c in tree.body),ref
    match=re.search(re.escape(method+' ('+ref+')')+r' \.\.\. ok(?:\n|$)',log)
    return {'test':ref,'result':'PASS' if match else 'NOT_VERIFIED','matchedLine':match.group().strip() if match else None}


def build(local_log,output,hosted_log=None,observation=None,compiler_log=None):
    local=Path(local_log).read_text()
    assert re.search(r'\nOK\s*$',local),'successful complete Route A log required'
    hosted=Path(hosted_log).read_text() if hosted_log else ''
    obs=json.loads(Path(observation).read_text()) if observation else None
    if obs:
        assert re.search(r'\nOK\s*$',hosted),'successful hosted Route A log required'
        assert obs['ordinaryEngineeringJobs']=='PASS'
        assert all(obs['jobs'][n]=='success' for n in ('contracts','phase5-experiments','phase5c-hard-gates','phase6-target'))
    rows=[]
    for definition in controls():
        row=dict(definition)
        filename,symbol=row['source'].split('#')
        tree=ast.parse((ROOT/filename).read_text())
        assert any(isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==symbol.split('.')[-1] for n in ast.walk(tree)),row['source']
        row['positiveEvidence']=[test_evidence(t,local) for t in row.pop('positiveTests')]
        row['negativeEvidence']=[test_evidence(t,local) for t in row.pop('negativeTests')]
        assert all(e['result']=='PASS' for e in row['positiveEvidence']+row['negativeEvidence']),row['id']
        if not row['negativeEvidence']:
            row['negativeEvidenceNotApplicable']='Read-only integrity measurement; no mutation of historical inputs.' if row['positiveEvidence'] else 'No executable negative mapped; review remains incomplete.'
        refs=[e['test'] for e in row['positiveEvidence']+row['negativeEvidence']]
        row['hostedEvidence']={'status':'PENDING_EXACT_REMEDIATION_SOURCE' if not obs else 'VERIFIED',
            'sourceCommit':obs['sourceCommit'] if obs else None,'runId':obs['runId'] if obs else None,
            'tests':[test_evidence(t,hosted) for t in dict.fromkeys(refs)] if obs else []}
        row['status']='INCOMPLETE'
        if row['knownLimitation'].startswith('BLOCKED:'):row['status']='BLOCKED'
        elif not row['knownLimitation'].startswith('INCOMPLETE:') and row['positiveEvidence'] and obs:
            evidence=row['positiveEvidence']+row['negativeEvidence']+row['hostedEvidence']['tests']
            if all(e['result']=='PASS' for e in evidence):row['status']='PASS'
        if row['authorizationSection']==18 and row['control'].startswith('Exact-source hosted') and obs:
            assert obs['closure']['auditExecution']['status']=='PERFORMED'
            row['status']='PASS'
            row['measuredMetadataEvidence']={'jobs':obs['jobs'],'closure':obs['closure']}
        rows.append(row)
    assert {r['authorizationSection'] for r in rows}==set(range(1,21))
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    def sha(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()
    source_files=sorted({r['source'].split('#')[0] for r in rows} | {str(p.relative_to(ROOT)) for p in (ROOT/'engineering/route_a_gateway').glob('*.py')}
                        | {str(p.relative_to(ROOT)) for p in (ROOT/'verification/route_a').glob('*.py')})
    if obs:
        for name in source_files:
            assert subprocess.check_output(['git','show',obs['sourceCommit']+':'+name],cwd=ROOT)==(ROOT/name).read_bytes(),name
    result={'format':'acp-route-a-security-coverage/1','classification':'NON_AUTHORITATIVE_TEST_ONLY',
        'authorizationRequestDigest':'sha256:44805966e05af1db2c4faa3b786361737495025b0eb9e30bfbafe35c701c2eab',
        'localLogDigest':sha(Path(local_log).read_bytes()),'hostedLogDigest':sha(Path(hosted_log).read_bytes()) if hosted_log else None,
        'sourceHashes':{n:sha((ROOT/n).read_bytes()) for n in source_files},
        'status':'STOP_FOR_INDEPENDENT_SECURITY_REVIEW','fullOperationalSecurity':'NOT_ESTABLISHED',
        'fullImplementationGate':'REVIEW_REQUIRED','counts':{s:sum(r['status']==s for r in rows) for s in ('PASS','BLOCKED','INCOMPLETE')},
        'controls':rows,'phase6':'IN_PROGRESS','phase7':'NOT_STARTED'}
    if compiler_log:
        compiler=Path(compiler_log).read_text()
        assert re.search(r'\nOK \(skipped=1\)\s*$',compiler),'actual full compiler result required'
        count,seconds=re.search(r'Ran (\d+) tests in ([\d.]+)s',compiler).groups()
        result['compilerEvidence']={'tests':int(count),'seconds':float(seconds),'skipped':1,
            'skipLines':[line for line in compiler.splitlines() if ' ... skipped ' in line],
            'logDigest':sha(Path(compiler_log).read_bytes()),'status':'OK_WITH_ONE_EXISTING_OPT_IN_SKIP'}
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(result['counts'],len(rows),'controls across all 20 authorization sections')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--local-log',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--hosted-log');parser.add_argument('--observation')
    parser.add_argument('--compiler-log')
    args=parser.parse_args();build(args.local_log,args.output,args.hosted_log,args.observation,args.compiler_log)
