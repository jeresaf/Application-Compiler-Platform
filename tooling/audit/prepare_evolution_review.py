"""Prepare unapproved reference proposals; never issue authority or execute migration."""
import copy
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deterministic_approval import approved_snapshot
from change_fixtures import evolution_change
from changes import prepare, index
from compiler_contracts import fingerprint
from target_worker import bundle_digest

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / 'proposals/phase6-evolution-review'
SEAL = 'ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb'

def write(name, value):
    p = DEST / name
    p.write_text(json.dumps(value, ensure_ascii=True, indent=2) + '\n')
    return 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    assert bundle_digest() == SEAL
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = {'status':'REVIEW_REQUIRED_NOT_APPROVED', 'reviewedSource':'80e19a6282c481c616f370e2876d3099eead0a2e',
                'sealedBundleDigest':SEAL, 'authorityIssued':False, 'migrationExecuted':False, 'domains':{}}
    for domain in ('payment','case-management'):
        before = approved_snapshot(domain)
        anchor = {'sequence':0, 'digest':before['contentDigest'], 'journalDigest':'sha256:'+'0'*64}
        proposal = evolution_change(before, anchor, 'required-field')
        proposal['changeVersion'] = '0.3.0'
        proposal['canonicalVersion'] = '0.3.0'
        proposal['id'] = 'CHANGE-REVIEW-' + domain
        proposal['author'] = 'assistant:proposal'
        proposal['intent'] = 'UNAPPROVED synthetic reference-only required field; HUMAN REVIEW REQUIRED'
        node = proposal['operations'][0]['node']
        node['id'] = 'EVOLVE-REFERENCE-NOTE'
        node['name'] = 'Synthetic reference evolution note'
        owner = index(before)['ENT-PAYMENT' if domain == 'payment' else 'CASE']
        node['data']['owner'] = {'id':owner['id'], 'revision':owner['revision']}
        node['origins'] = [{'source':'proposal:phase6-evolution-review','locator':domain+'/'+node['id'],
                            'actor':'assistant:proposal','actorType':'AI'}]
        plan = prepare(before, proposal)
        bindings = {'requiredFieldBackfills':{node['id']:"e\u0301\u0000🦋'"}}
        files = {}
        for label, value in [('change',proposal),('plan',plan),('canonical-candidate',plan['candidate']),('data-bindings',bindings)]:
            files[label] = write(domain+'-'+label+'.json',value)
        manifest['domains'][domain] = {'baseDigest':before['contentDigest'],
            'candidateDigest':plan['candidate']['contentDigest'], 'previewPlanDigest':plan['planDigest'],
            'bindingDigest':fingerprint(bindings,'migration-bindings'), 'bindingUTF8Hex':'65cc8100f09fa68b27',
            'owner':node['data']['owner'], 'files':files,
            'anchorStatus':'SYNTHETIC_PREVIEW_ANCHOR_NOT_ACCEPTED_HISTORY',
            'candidateLifecycleMeaning':'APPROVED is the structural active-candidate encoding; no human approval is asserted',
            'decisionsRequired':['SEMANTIC_CANDIDATE_AND_CHANGESET','INDEPENDENT_DATA_BINDING',
                'REAL_ACCEPTED_HISTORY_REBASE_AND_PLAN','EXACT_SQL_AND_DEPLOYMENT_APPROVAL'],
            'approvals':[]}
    write('manifest.json',manifest)
    assert bundle_digest() == SEAL
    print(json.dumps(manifest,indent=2))

if __name__ == '__main__':
    main()
