"""Verify review integrity and authority boundaries; no deployment is performed."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_json import load
from canonical_ir import validate_snapshot
from changes import fingerprint as change_hash
from compiler_contracts import Document, fingerprint
from deterministic_approval import approved_snapshot as deterministic_snapshot
from execution_approval import approved_snapshot as execution_snapshot
from target_migrations import MigrationBlocked, plan_upgrade
from target_worker import bundle_digest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'proposals/phase6-evolution-review'

def stable(value):
    if isinstance(value, dict):
        if set(value) == {'id','revision'}:
            return {'id':value['id']}
        return {k:stable(v) for k,v in value.items()}
    return [stable(v) for v in value] if isinstance(value,list) else value

class NoAuthority:
    def read_accepted_plan(self, digest):
        raise PermissionError('No deployed accepted-history receipt supplied')
    def read_approved_bindings(self, *args):
        raise PermissionError('No independent binding approval supplied')

def main():
    manifest = load(BASE/'manifest.json')
    assert not manifest['authorityIssued'] and not manifest['migrationExecuted']
    assert bundle_digest() == manifest['sealedBundleDigest']
    report = {'status':'REVIEW_INTEGRITY_PASS_NOT_DEPLOYMENT_APPROVAL',
              'semanticEvolutionDeployed':'NOT_PROVED','phase6':'IN_PROGRESS','phase7':'NOT_STARTED',
              'sealedBundleDigest':bundle_digest(),'historicalAuthority':{},'proposals':{}}
    for domain, entry in manifest['domains'].items():
        before = deterministic_snapshot(domain)
        old = execution_snapshot(domain)
        report['historicalAuthority'][domain] = {'executionV03':old['contentDigest'],
            'deterministicV04':before['contentDigest'],'verification':'EXISTING_BOUNDED_REFERENCE_APPROVALS_VERIFIED',
            'deploymentHistoryAndIndependentBindings':'NOT_SUPPLIED; no deployed-transition PASS asserted'}
        inventory = load(BASE/'historical-authority-inventory.json')['domains'][domain]
        for transition in inventory:
            for path, expected in transition['files'].items():
                assert 'sha256:'+hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected
        report['historicalAuthority'][domain]['transitions'] = inventory
        plan = load(BASE/(domain+'-plan.json'));proposal = load(BASE/(domain+'-change.json'))
        candidate = load(BASE/(domain+'-canonical-candidate.json'));bindings = load(BASE/(domain+'-data-bindings.json'))
        package = load(BASE/(domain+'-human-review.json'))
        for label, expected in entry['files'].items():
            suffix = '-human-review.md' if label == 'human-review-notes' else '-'+label+'.json'
            assert 'sha256:'+hashlib.sha256((BASE/(domain+suffix)).read_bytes()).hexdigest() == expected
        validate_snapshot(candidate)
        assert plan['change'] == proposal and plan['candidate'] == candidate
        assert change_hash({k:v for k,v in plan.items() if k!='planDigest'},'plan') == entry['previewPlanDigest']
        assert candidate['contentDigest'] == entry['candidateDigest']
        assert fingerprint(Document.of(bindings),'migration-bindings') == entry['bindingDigest']
        assert bindings['requiredFieldBackfills']['EVOLVE-REFERENCE-NOTE'].encode('utf-8').hex() == '65cc8100f09fa68b27'
        assert not package['approvals'] and not entry['approvals']
        assert entry['compatibility'] == 'REVIEW_REQUIRED' and proposal['migration']['compatibility'] == 'BREAKING'
        assert package['operations']['supportedResourceCreators'] == []
        assert package['newWrite']['default'] is None and package['newWrite']['emptyStringAllowed']
        assert package['newWrite']['absence'] == package['newWrite']['null'] == 'REJECT'
        assert not package['backfill']['productionTenantDefault'] and not package['backfill']['futureWriteDefault']
        added = {op['node']['id']:op['node'] for op in proposal['operations']}
        assert len(added) == 6 and all(op['op']=='ADD' for op in proposal['operations'])
        req = added['REQ-EVOLVE-REFERENCE-NOTE']; field = added['EVOLVE-REFERENCE-NOTE']
        assert req['basis'] == [] and field['basis'] == [{'id':req['id'],'revision':1}]
        assert field['data']['optional'] is False and field['data']['type'] == {'kind':'String'}
        assert len(req['data']['acceptance']) == 4
        for ref in req['data']['acceptance']:
            assert added[ref['id']]['data']['requirement'] == {'id':req['id'],'revision':1}
        for node in added.values():
            assert all(o['actorType']=='AI' for o in node['origins'])
        proposed = {n['id']:n for n in candidate['content']['nodes']}
        for node in before['content']['nodes']:
            if node['kind'] in {'Command','UseCase','ExecutionStep','Form','InputControl','Action','Requirement','AcceptanceCriterion'}:
                assert stable(node['data']) == stable(proposed[node['id']]['data']),node['id']
        for path, digest in package['sourceEvidence'].items():
            assert 'sha256:'+hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest
        try:
            plan_upgrade(Document.of(before),Document.of(candidate),Document.of(plan),Document.of(bindings),NoAuthority())
        except MigrationBlocked as error:
            assert str(error) == 'UNACCEPTED_HISTORY'
        else:
            raise AssertionError('Unapproved preview must not lower to executable migration')
        report['proposals'][domain] = {'candidateDigest':entry['candidateDigest'],
            'previewPlanDigest':entry['previewPlanDigest'],'integrity':'PASS',
            'independentSyntheticRequirement':'PASS','existingOperationMeaningPreserved':'PASS',
            'unacceptedMigration':'REJECTED_UNACCEPTED_HISTORY','runtimeCompatibility':'NOT_EXECUTED'}
    print(json.dumps(report,indent=2))

if __name__ == '__main__':
    main()
