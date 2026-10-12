"""Prepare independent, unapproved retained-reference binding decisions. No SQL or authority."""
import json
from pathlib import Path
from semantic_content_decisions import ROOT, PROPOSALS, RECORDS, PINS, SOURCE, sha, json_bytes
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compiler_contracts import fingerprint

DEST=ROOT/'proposals/phase6-independent-data-binding-review'


def main():
    DEST.mkdir(parents=True,exist_ok=True)
    manifest={'status':'REVIEW_REQUIRED','source':SOURCE,'approvalsIssued':False,'domains':{}}
    for domain,pin in PINS.items():
        bindings=json.loads((PROPOSALS/(domain+'-data-bindings.json')).read_bytes())
        value=bindings['requiredFieldBackfills']['EVOLVE-REFERENCE-NOTE']
        binding_digest=fingerprint(bindings,'migration-bindings')
        assert value.encode('utf-8').hex()=='65cc8100f09fa68b27'
        assert binding_digest=='sha256:2a584b4d5ca471d1f1686db24e3b094e1a91f7e69e4d9f4775fcad1607c49481'
        package={'status':'REVIEW_REQUIRED','domain':domain,'applicationId':pin['applicationId'],
            'source':SOURCE,'semanticDecisionDigest':sha((RECORDS/(domain+'.json')).read_bytes()),
            'semanticCandidateDigest':pin['candidateDigest'],'owner':pin['owner'],'field':'EVOLVE-REFERENCE-NOTE',
            'proposedBinding':bindings,'bindingDigest':binding_digest,'value':value,
            'valueJsonEscaped':json.dumps(value,ensure_ascii=True),'utf8Hex':value.encode().hex(),
            'utf8ByteLength':len(value.encode()),'unicodeScalars':['U+0065','U+0301','U+0000','U+1F98B','U+0027'],
            'population':{'scope':'RETAINED_SYNTHETIC_REFERENCE_ROWS_ONLY',
                'databaseIdentity':'PENDING_VERIFIED_REFERENCE_DATABASE_IDENTITY',
                'schemaIdentity':'PENDING_VERIFIED_SCHEMA_IDENTITY',
                'selection':'Every retained row of owner '+pin['owner']+' in this application reference database, only for tenants and resource IDs explicitly enumerated in the independently reviewed frozen inventory. No production rows.',
                'tenantAllowlist':'PENDING_EXACT_REFERENCE_TENANT_INVENTORY',
                'resourceIds':'PENDING_EXACT_RETAINED_ROW_INVENTORY','rowCounts':'PENDING_MEASURED_COUNTS',
                'inventoryDigest':'PENDING_REAL_DATABASE_BYTE_INVENTORY',
                'oldSnapshotDigest':pin['previousDigest'],
                'assumptions':['Database is a disposable synthetic reference deployment, not a production tenant database',
                    'Database, schema, old sealed target and Canonical snapshot identity must be verified',
                    'Inventory contains all owner rows, exact tenant/identity scalar bytes, required old columns and operational state',
                    'No concurrent insert/delete/update may silently change the reviewed population; fence writers and recheck inventory',
                    'Unknown tenant, row, count, schema or byte drift stops migration before writes'],
                'everySelectedRowReceivesSameValue':True,'populationApproved':False},
            'tenantApplicability':'Only exact synthetic tenants enumerated in the future inventory; names such as tenant-one/tenant-two are test examples, not authorization or a production allowlist',
            'valueMeaning':'Synthetic Unicode/NUL byte-preservation witness only, not a business note or production tenant default',
            'unicodeAndNul':'Store exact UTF-8 bytes in bytea; never normalize composed/decomposed accents, strip NUL, trim text or reinterpret as SQL text',
            'presenceRules':{'beforeExpand':'field absent from old schema','afterExpandBeforeBackfill':'SQL NULL is transitional only',
                'final':'explicit non-null String; this proposed value is neither null nor empty',
                'emptyString':'valid distinct semantic String with zero bytes; never substitute this backfill for it',
                'absent':'not equivalent to null or empty; new record omitting required note must fail final enforcement'},
            'notANewRecordDefault':'This mapping is only a one-time retained-row transformation on the reviewed frozen population. No DEFAULT clause, create input, UI value or future tenant policy is authorized. New writers supply explicit independently chosen values.',
            'errorDetection':['Compare pre/post row identities, exact tenant counts and unchanged old column/runtime bytes',
                'Compare encode(new_column, hex) for every selected row to 65cc8100f09fa68b27',
                'Verify no selected row remains null, no unselected row changed and no new/removed row was hidden',
                'Verify empty/null/absent negative cases and decomposed-accent/NUL preservation through typed application reads',
                'Capture exact SQL hash, transaction outcome, row inventory digest and per-object runtime evidence'],
            'recovery':{'transactional':'Before COMMIT, transactional PostgreSQL DDL/backfill/verification can roll back as a unit if actually executed in one transaction; prove original schema and rows survive fault injection',
                'staged':'Separately committed expand/backfill stages are not undone by rollback of a later transaction. Keep exact stage receipts and fence affected writers',
                'ambiguousCommit':'Inspect actual schema, row inventories and transaction/version receipts before retry; no blind replay',
                'afterCommit':'Reviewed forward repair or verified backup/restore with reconciliation of later committed domain/idempotency/outbox/job effects. No automatic production rollback',
                'beforeActivation':'Do not deploy required-model readers over transitional nulls; switch/fence incompatible insert writers before final NOT NULL'},
            'approvalRequirements':['Independent human decision for this application, exact binding digest and exact frozen population',
                'Bind the decision to the real rebased plan digest and approved Canonical candidate; identical binding digest cannot authorize another application or plan',
                'Exact SQL/recovery/lock policy and execution/deployment approvals remain separate',
                'Missing population inputs block execution even if the proposed scalar value is later approved'],
            'approvals':[],'authenticatedProofIssued':False,'journalAccepted':False,
            'migration':'NOT_AUTHORIZED','deployment':'NOT_AUTHORIZED','phase6':'IN_PROGRESS','phase7':'NOT_STARTED'}
        p=DEST/(domain+'.json');p.write_bytes(json_bytes(package))
        notes=[f'# {domain.upper()} — independent retained-data binding review','',
            '**REVIEW_REQUIRED. No data-binding approval is recorded.**','',
            f"Application: `{pin['applicationId']}`. Owner: `{pin['owner']}`. Field: `EVOLVE-REFERENCE-NOTE`.",'',
            f"Semantic content decision: `{package['semanticDecisionDigest']}`. This does not approve this data value.",'',
            f"Proposed value (escaped JSON): `{package['valueJsonEscaped']}`; UTF-8 hex `65cc8100f09fa68b27`, 9 bytes.",'',
            f'Binding digest: `{binding_digest}`.','',
            '## Population and tenant boundary','',package['population']['selection'],'',
            'Database/schema identity, exact tenant and row IDs/counts and inventory digest are PENDING. No population approval can be inferred from fixture names. Every selected retained row would receive the same synthetic scalar; no unselected row may change.','',
            package['tenantApplicability'],'',package['valueMeaning'],'',
            '## Unicode, presence and future writes','',package['unicodeAndNul'],'',
            'Old schema absence, transitional SQL NULL, final required non-null String and explicit empty String are distinct states. Empty String remains valid; this proposed value is nonempty. Raw bytea NOT NULL alone cannot enforce valid String/UTF-8; provisioning/application validation needs its own evidence.','',
            package['notANewRecordDefault'],'', '## Detecting erroneous backfill','']
        notes+=['- '+x for x in package['errorDetection']]
        notes+=['','## Recovery','']+['- '+v for v in package['recovery'].values()]
        notes+=['','## Independent decisions required','']+['- '+x for x in package['approvalRequirements']]
        notes+=['',f'[Exact machine package]({domain}.json). No SQL, journal receipt, migration execution or deployment approval is created.','']
        md=DEST/(domain+'.md');md.write_text('\n'.join(notes))
        manifest['domains'][domain]={'applicationId':pin['applicationId'],'packageDigest':sha(p.read_bytes()),
            'notesDigest':sha(md.read_bytes()),'bindingDigest':binding_digest,'status':'REVIEW_REQUIRED'}
    (DEST/'manifest.json').write_bytes(json_bytes(manifest))
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':
    main()
