"""Prepare unapproved review packages. Never issue authority or execute migration."""
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
REVIEWED = 'e15bd1058f69194c87f71599250cf4474b93514c'
REQ = 'REQ-EVOLVE-REFERENCE-NOTE'
FIELD = 'EVOLVE-REFERENCE-NOTE'
SCENARIOS = {
    'AC-EVOLVE-RETAINED': 'PROPOSED synthetic reference-only: retained rows receive only the independently approved exact backfill bytes; never use this binding as a production tenant or future-write default.',
    'AC-EVOLVE-NEW-WRITE': 'PROPOSED: each new reference record must explicitly supply EVOLVE-REFERENCE-NOTE as a non-null String. Absent, null or non-String values are rejected; empty String is permitted. Preserve exact Unicode scalar sequence as UTF-8, without normalization or an inferred default. Target 0.5.0 exposes no resource-create Command or UseCase; direct fixture provisioning must supply this field explicitly.',
    'AC-EVOLVE-UPDATE': 'PROPOSED: existing task Commands continue to update existing records using their exact approved inputs and preserve EVOLVE-REFERENCE-NOTE. Missing resource identity remains RESOURCE_NOT_FOUND; no upsert or create is introduced.',
    'AC-EVOLVE-ROLLOUT': 'PROPOSED: old insert writers that omit the field are incompatible with final NOT NULL/no-default schema. Expand nullable, backfill retained rows, verify, switch or fence all insert writers, then contract. Keep REVIEW_REQUIRED until actual old-writer/new-schema and recovery evidence exists.'}


def write(name, value):
    p = DEST / name
    p.write_text(json.dumps(value, ensure_ascii=True, indent=2) + '\n')
    return 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()


def reference(n):
    return {'id': n['id'], 'revision': n['revision']}


def main():
    assert bundle_digest() == SEAL
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = {'status':'REVIEW_REQUIRED_NOT_APPROVED', 'reviewedSource':REVIEWED,
                'planningCheckpoint':'ACCEPTED_ENGINEERING_APPROACH_ONLY',
                'sealedBundleDigest':SEAL, 'authorityIssued':False, 'migrationExecuted':False, 'domains':{}}
    for domain in ('payment','case-management'):
        before = approved_snapshot(domain)
        nodes = index(before)
        anchor = {'sequence':0, 'digest':before['contentDigest'], 'journalDigest':'sha256:'+'0'*64}
        proposal = evolution_change(before, anchor, 'required-field')
        proposal.update(changeVersion='0.3.0', canonicalVersion='0.3.0', id='CHANGE-REVIEW-'+domain,
                        author='assistant:proposal', intent='UNAPPROVED synthetic reference requirement and required field; HUMAN REVIEW REQUIRED')
        owner = nodes['ENT-PAYMENT' if domain == 'payment' else 'CASE']
        origin = {'source':'proposal:phase6-evolution-review','locator':domain,'actor':'assistant:proposal','actorType':'AI'}
        common = {'revision':1,'lifecycle':'APPROVED','steward':'assistant:proposal','origins':[origin]}
        requirement = {**copy.deepcopy(common),'id':REQ,'kind':'Requirement','name':'PROPOSED synthetic reference note requirement',
            'basis':[], 'data':{'statement':'PROPOSED, UNAPPROVED, SYNTHETIC REFERENCE ONLY: '+owner['id']+
            ' records retain a required exact String reference note. New records must explicitly supply it; retained-row backfill requires independent approval and is never a future-write default. No create operation or UI is added. Existing approved update behavior preserves it. Rollout remains REVIEW_REQUIRED.',
            'priority':'MUST','acceptance':[{'id':id,'revision':1} for id in SCENARIOS]}}
        criteria = [{**copy.deepcopy(common),'id':id,'kind':'AcceptanceCriterion','name':'PROPOSED '+id,
            'basis':[reference(requirement)],'data':{'requirement':reference(requirement),'scenario':scenario}}
            for id,scenario in SCENARIOS.items()]
        field = proposal['operations'][0]['node']
        field.update(id=FIELD, name='PROPOSED synthetic reference evolution note',
                     steward='assistant:proposal', origins=[origin], basis=[reference(requirement)])
        field['data']['owner'] = reference(owner)
        proposal['operations'] = [{'op':'ADD','node':n} for n in [requirement,*criteria,field]]
        proposal['migration'].update(compatibility='BREAKING',
            steps=['EXPAND nullable column without a default','BACKFILL only retained reference rows from independently approved binding',
                   'VERIFY exact bytes and every writer inventory','SWITCH or fence every insert writer before required enforcement',
                   'CONTRACT NOT NULL only after approved compatibility and recovery checks'],
            preconditions=['REVIEW_REQUIRED: no backward compatibility proof exists',
                           'Require actual accepted history and separately approved binding, SQL and deployment',
                           'Final schema rejects old INSERT writers omitting the field; no default is inferred'],
            verification=['Verify retained row bytes, explicit new insert values and rejection of omitted/null values',
                          'Verify existing update inputs, missing-resource rejection, UI behavior and recovery'],
            recovery='Fence incompatible writers; reconcile transaction outcome; reviewed forward repair or verified restore. No automatic production rollback.')
        plan = prepare(before, proposal)
        bindings = {'requiredFieldBackfills':{FIELD:"e\u0301\u0000🦋'"}}
        commands = [n for n in before['content']['nodes'] if n['kind']=='Command' and n['data']['resource']['id']==owner['id']]
        source_paths = ['targets/spring-vue-postgres/worker/execution_codegen.py',
            'targets/spring-vue-postgres/worker/generation.py',
            'targets/spring-vue-postgres/templates/backend/src/main/java/acp/infrastructure/ExecutionStore.java',
            'tooling/phase6_reference_tests.py','tooling/invocation_reference_tests.py']
        package = {'status':'REVIEW_REQUIRED_NOT_APPROVED','domain':domain,'applicationId':before['content']['applicationId'],'approvals':[],
            'oldMeaning':nodes['REQ-PAYMENT' if domain=='payment' else 'REQ-CASE']['data']['statement'],
            'proposedMeaning':requirement['data']['statement'], 'requirement':requirement,'acceptanceCriteria':criteria,
            'field':field,'oldSnapshotDigest':before['contentDigest'],'candidateDigest':plan['candidate']['contentDigest'],
            'previewPlanDigest':plan['planDigest'],'compatibility':'REVIEW_REQUIRED',
            'changeSchemaCompatibility':'BREAKING (conservative final-schema classification; rollout REVIEW_REQUIRED)',
            'operations':{'supportedResourceCreators':[],
                'reason':'Every approved Command locks an existing tenant-scoped resource and issues UPDATE; missing row throws RESOURCE_NOT_FOUND. UseCases/UI invoke those same Commands. Runtime bookkeeping INSERTs do not create domain resources.',
                'commands':[{'id':n['id'],'revision':n['revision'],'input':n['data']['input'],
                    'requiredInputFields':[reference(f) for f in before['content']['nodes'] if f['kind']=='Field' and f['data']['owner']['id']==n['data']['input']['id'] and not f['data']['optional']],
                    'writeFields':n['data']['writeFields'],'assignments':n['data']['assignments'],
                    'createsResource':False,'noteAssignmentAdded':False} for n in commands],
                'useCase':nodes['UC-TASK'],'steps':[n for n in before['content']['nodes'] if n['kind']=='ExecutionStep'],
                'ui':[nodes[id] for id in ('FORM-TASK','CONTROL-TASK-RESOURCE','CONTROL-TEXT','ACTION-TASK')],
                'newRecordProvisioning':'Only out-of-band fixture/admin insertion is available, not an admitted application create API. Such writers must supply all existing required owner fields plus the new field and obey existing FK/invariant constraints.',
                'requiredProvisioningFields':[reference(f) for f in before['content']['nodes'] if f['kind']=='Field' and f['data']['owner']['id']==owner['id'] and not f['data']['optional']]+[reference(field)],
                'incompatibleKnownWriters':['tooling/phase6_reference_tests.py: seed_sql/source seed INSERT',
                    'tooling/invocation_reference_tests.py: source clone INSERT with explicit old-column list',
                    'other integration seed/import writers that use explicit old-column lists: must inventory and switch or fence'],
                'externalWriterInventory':'NOT_PROVIDED; no blanket compatibility claim'},
            'newWrite':{'required':True,'nullable':False,'type':'String','emptyStringAllowed':True,
                'absence':'REJECT','null':'REJECT','nonString':'REJECT','default':None,
                'encoding':'exact UTF-8 bytes; no Unicode normalization; NUL is a scalar witness',
                'existingUpdates':'preserve supplied stored note; no new assignment or create/upsert',
                'currentCreateAPI':'UNSUPPORTED; proposal adds none',
                'databaseEnforcement':'bytea NOT NULL enforces non-null presence only; raw SQL does not prove String type or valid UTF-8. Explicit provisioning must validate these proposed constraints; no provisioning implementation is approved'},
            'backfill':{'scope':'SYNTHETIC_REFERENCE_RETAINED_ROWS_ONLY','binding':bindings,
                'digest':fingerprint(bindings,'migration-bindings'),'utf8Hex':'65cc8100f09fa68b27',
                'independentApproval':'REQUIRED_NOT_GRANTED','productionTenantDefault':False,'futureWriteDefault':False},
            'unsupportedTargetBehavior':['No application resource-create operation is exposed by these approved fixtures',
                'Staged expand/switch/contract deployment orchestration is not implemented by the sealed single migration planner',
                'Actual old-writer/new-schema runtime compatibility and revised full admission are unproved',
                'No approved new-record provisioning validator exists; bytea alone cannot enforce String/UTF-8 validity',
                'Existing hard-coded seed and clone writers omit the required field',
                'No real accepted journal anchor, approved binding, exact SQL or deployment receipt is supplied'],
            'risks':['Final required schema breaks old inserts; nullable expansion alone does not enforce final semantics',
                'Do not deploy required-model readers against a nullable expanded schema containing nulls',
                'Public classification is a synthetic proposal; do not store production personal data on that assumption',
                'A future create Command/input/UI or staged migration support needs separate exact semantic/target approval'],
            'sourceEvidence':{path:'sha256:'+hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in source_paths},
            'runtimeEvidence':'NOT_EXECUTED; static source audit only',
            'authorityBoundary':'Synthetic preview anchor is not accepted history; candidate lifecycle is structural, not human approval'}
        files = {}
        for label,value in [('change',proposal),('plan',plan),('canonical-candidate',plan['candidate']),('data-bindings',bindings)]:
            files[label] = write(domain+'-'+label+'.json',value)
        package['changeSetFileDigest'] = files['change']
        package['candidateFileDigest'] = files['canonical-candidate']
        files['human-review'] = write(domain+'-human-review.json',package)
        notes = [f"# {domain.upper()} — separate human review package", "",
            "Status: REVIEW_REQUIRED, UNAPPROVED. Engineering planning approach accepted only.",
            "Phase 6 IN PROGRESS; Phase 7 NOT STARTED.", "",
            "## Old and proposed meaning", "", package['oldMeaning'], "", requirement['data']['statement'], "",
            f"New requirement: `{REQ}` revision 1. New field: `{FIELD}` revision 1 on `{owner['id']}`.",
            "The field basis is the new synthetic requirement alone. Existing business requirements do not authorize it.",
            "All added origins are AI proposals. Active-candidate lifecycle markers do not represent human approval.", "",
            "## Exact review bindings", "",
            f"Old snapshot: `{before['contentDigest']}`", "",
            f"Proposed candidate: `{plan['candidate']['contentDigest']}`", "",
            f"ChangeSet file SHA-256: `{files['change']}`", "",
            f"Preview plan: `{plan['planDigest']}` (synthetic anchor; not executable authority).", "",
            f"Independent backfill binding: `{package['backfill']['digest']}`; UTF-8 hex `65cc8100f09fa68b27`.",
            "Reference retained rows only; no production tenant or future-write default.", "",
            "## Proposed acceptance criteria", ""]
        notes += [f"- `{id}`: {scenario}" for id,scenario in SCENARIOS.items()]
        notes += ["", "## Commands, UseCases and UI", "",
            "Supported resource-create operations: **none**. Existing Commands lock existing records and UPDATE them.",
            "Missing records fail RESOURCE_NOT_FOUND. Runtime outbox/job/audit inserts are not resource creators.", ""]
        notes += [f"- `{n['id']}`: `{n['data']['input']['id']}` requires `OPERATION-TEXT`; resource identity, expected version, authentication/authorization and existing invocation/idempotency rules still apply. Writes `FLD-TASK-SUMMARY`, not the proposed field." for n in commands]
        notes += ["", "`UC-TASK` requires `INPUT-TASK-RESOURCE` and `INPUT-TASK-TEXT`; the exact command sequence is " + " → ".join(n["data"]["operation"]["id"] for n in package["operations"]["steps"]) + ".",
            "`FORM-TASK`/`CONTROL-TASK-RESOURCE`/`CONTROL-TEXT`/`ACTION-TASK` remain existing-record task controls. No create form or note input is proposed. Dependency revision closure is not a new business effect.", "",
            "## New records and required constraints", "",
            "Out-of-band reference provisioning must explicitly supply all existing required fields and the new String, satisfying existing identities, tenant/FK/invariant constraints. It is not a supported create API.", "",
            "Required provisioning fields: " + ', '.join('`'+r['id']+'`' for r in package['operations']['requiredProvisioningFields']) + '.', "",
            "The note is required, non-null, non-Nullable String; absent/null/non-String rejected. Empty String permitted; no length/nonblank constraint is invented. Preserve exact UTF-8 scalar bytes, without normalization or any default. New writes must not copy the retained-row backfill implicitly.", "",
            "PostgreSQL bytea NOT NULL enforces non-null presence, not String or valid UTF-8. Explicit provisioning must validate those proposed rules; no such writer implementation is approved.", "",
            "Existing update Commands preserve stored notes. Their inputs/assignments do not create a new note or resource. Known seed and clone INSERT writers omit this column and become incompatible after NOT NULL enforcement. All external import/provisioning writers remain to be inventoried.", "",
            "## Compatibility and rollout", "",
            "**REVIEW_REQUIRED.** The ChangeSet conservatively declares BREAKING, replacing BACKWARD: old inserts omitting the final NOT NULL/no-default column fail. No runtime compatibility proof is claimed. UNKNOWN cannot produce a prepared plan in the existing fail-closed planner; it has not been bypassed or changed.", "",
            "1. Expand nullable with no default while compatible old readers/writers run.",
            "2. Backfill only independently approved retained rows; capture byte/tenant inventories.",
            "3. Verify exact bytes and inventory every new-record writer and recovery boundary.",
            "4. Switch reference provisioning to explicit values, fence old insert writers, re-scan rows under writer fencing. Do not activate required-model readers while any nulls remain.",
            "5. Contract NOT NULL only after approved writer/reader compatibility, counts and recovery proof. Resume existing updates and full-admission checks on retained data.", "",
            "The sealed migration planner emits one migration, not staged traffic orchestration. This rollout needs separately approved exact SQL/deployment support; no implementation or application is performed.", "",
            "## Risks and decisions", ""]
        notes += ['- '+r for r in package['risks']+package['unsupportedTargetBehavior']]
        notes += ["", "Review the exact semantic requirement/candidate/ChangeSet, independently review backfill bindings, and decide the writer/compatibility policy separately for this application. Real accepted-history rebasing and exact SQL/deployment decisions remain pending their actual inputs. No approvals are issued by this package.", "",
            f"[Complete machine package]({domain}-human-review.json) includes source-file hashes, exact operation bindings and acceptance criteria.", ""]
        notes_path = DEST / (domain+'-human-review.md')
        notes_path.write_text('\n'.join(notes))
        files['human-review-notes'] = 'sha256:' + hashlib.sha256(notes_path.read_bytes()).hexdigest()
        manifest['domains'][domain] = {'baseDigest':before['contentDigest'],
            'candidateDigest':plan['candidate']['contentDigest'],'previewPlanDigest':plan['planDigest'],
            'bindingDigest':fingerprint(bindings,'migration-bindings'),'bindingUTF8Hex':'65cc8100f09fa68b27',
            'requirement':REQ,'acceptanceCriteria':list(SCENARIOS),'owner':reference(owner),'applicationId':before['content']['applicationId'],'files':files,
            'compatibility':'REVIEW_REQUIRED','changeSchemaCompatibility':'BREAKING',
            'anchorStatus':'SYNTHETIC_PREVIEW_ANCHOR_NOT_ACCEPTED_HISTORY',
            'candidateLifecycleMeaning':'APPROVED is structural active-candidate encoding; no human approval asserted',
            'decisionsRequired':['SEMANTIC_REQUIREMENT_CANDIDATE_AND_CHANGESET','INDEPENDENT_REFERENCE_DATA_BINDING',
                'NEW_RECORD_WRITER_AND_COMPATIBILITY_POLICY','REAL_ACCEPTED_HISTORY_REBASE_AND_PLAN',
                'EXACT_SQL_AND_DEPLOYMENT_APPROVAL'],'approvals':[]}
    write('manifest.json',manifest)
    assert bundle_digest() == SEAL
    print(json.dumps(manifest,indent=2))

if __name__ == '__main__':
    main()
