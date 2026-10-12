"""Publish measured reference-only review packages; no approval or execution port."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from retained_inventory import ROOT,PINS,RECORDS,SOURCE,digest,verify,population_digest,writer_inventory,json_bytes,sha
EVIDENCE=ROOT/'targets/spring-vue-postgres/evidence/retained-data-inventory/2026-10-12'
DEST=ROOT/'proposals/phase6-measured-data-binding-review'

def negative_checks(frozen,writers):
 results={};owner=frozen['body']['ownerTable'];row=frozen['body']['tables'][owner][0]
 mapping=frozen['body']['fieldColumnMap'];domain=frozen['body']['domain']
 tenant=mapping['FLD-PAYMENT-TENANT' if domain=='payment' else 'CASE-TENANT']
 field=mapping['FLD-TASK-SUMMARY']
 def mutation(name,change,changed_writers=None,stale=False):
  observed=copy.deepcopy(frozen);change(observed['body'])
  if not stale:observed['body']['populationDigest']=population_digest(observed['body'])
  observed['inventoryDigest']=digest(observed['body'])
  try:verify(frozen,observed,changed_writers if changed_writers is not None else writers)
  except ValueError as error:results[name]={'result':'REJECTED','reason':str(error)}
  else:raise AssertionError('FAIL_OPEN:'+name)
 mutation('missing-row',lambda b:b['tables'][owner].pop())
 mutation('extra-row',lambda b:b['tables'][owner].append(copy.deepcopy(row)))
 mutation('changed-tenant',lambda b:b['tables'][owner][0].update({tenant:b'unknown-tenant'.hex()}))
 mutation('modified-stored-bytes',lambda b:b['tables'][owner][0].update({field:'00'}))
 mutation('unexpected-new-writer',lambda b:None,{**writers,'sources':writers['sources']+[{'path':'unexpected-import.py','digest':'sha256:unexpected'}]})
 mutation('database-mismatch',lambda b:b['database'].update(database='wrong-database'))
 mutation('schema-mismatch',lambda b:b['database'].update(schema='wrong-schema'))
 mutation('stale-population-digest',lambda b:b.update(populationDigest='sha256:stale'),stale=True)
 mutation('wrong-application',lambda b:b.update(applicationId='WRONG-APPLICATION'))
 return results

def main():
 DEST.mkdir(parents=True,exist_ok=True)
 writers=json.loads((EVIDENCE/'writers.json').read_bytes())
 if writers!=writer_inventory():raise ValueError('STALE_SOURCE_WRITER_INVENTORY')
 manifest={'sourceCommit':SOURCE,'status':'MEASURED_NOT_APPROVED','domains':{}}
 validation={'sourceCommit':SOURCE,'scope':'Measured frozen populations; adversarial payloads are rehashed to prove comparison to independent frozen baseline, not merely checksum rejection','domains':{}}
 for domain,pin in PINS.items():
  frozen=json.loads((EVIDENCE/(domain+'.json')).read_bytes());again=json.loads((EVIDENCE/(domain+'-recapture.json')).read_bytes())
  positive=verify(frozen,again,writers);negative=negative_checks(frozen,writers)
  b=frozen['body']
  old=json.loads((ROOT/'proposals/phase6-independent-data-binding-review'/(domain+'.json')).read_bytes())
  value=old['value'];assert value.encode().hex()=='65cc8100f09fa68b27';assert len(value.encode())==9
  population={'scope':'RETAINED_SYNTHETIC_REFERENCE_ROWS_ONLY','classification':b['classification'],
   'databaseIdentity':b['database'],'predecessor':b['predecessor'],'oldSnapshotDigest':b['canonicalDigest'],
   'tenantAllowlist':b['tenantIdentifiers'],'resources':b['population'],'ownerRowCount':len(b['population']),
   'allTableCounts':b['rowCounts'],'inventoryDigest':frozen['inventoryDigest'],'inventoryFileDigest':sha((EVIDENCE/(domain+'.json')).read_bytes()),
   'populationDigest':b['populationDigest'],'writerInventoryDigest':b['writerInventoryDigest'],
   'selection':'Every row of '+pin['owner']+' in this exact frozen synthetic reference database; no production rows',
   'populationApproved':False,'measuredNotApproved':True,'everySelectedRowWouldReceiveSameValue':True}
  package={**old,'source':{'branch':'codex/phase6-production-remediation','commit':SOURCE},
   'status':'REVIEW_REQUIRED','bindingPopulationStatus':'MEASURED_NOT_APPROVED','population':population,
   'semanticDecisionDigest':sha((RECORDS/(domain+'.json')).read_bytes()),
   'authenticatedContentProof':'PENDING_HUMAN_SIGNING','historyAvailability':'AUTHENTIC_HISTORY_UNAVAILABLE',
   'acceptedMigrationPlan':'NOT_APPROVED','sqlExecution':'NOT_AUTHORIZED',
   'writerFindings':writers['domainWriters'],'writerInventoryDigest':digest(writers),
   'proposedBindingValidation':{'result':'VALID_FOR_REVIEW_ONLY','utf8Hex':value.encode().hex(),'byteLength':9,'measuredRows':len(b['population']),'tenants':b['tenantIdentifiers'],'fieldCurrentlyAbsent':True,'writesPerformed':False,'newRecordDefault':False,'productionApplicability':False},
   'validationEvidence':positive,'negativeChecks':negative,
   'populationReviewBoundary':'A new test database is not authentic historical acceptance. Authentic history, signed content proof, independent binding approval, exact plan/SQL/recovery approval and deployment authority remain outstanding.',
   'recoveryObligations':[
    'Retain sealed predecessor artifacts, inventory and reproducible authorized fixture seed evidence before any future evolution.',
    'Fence all existing seed/clone/import/provisioning writers; recheck database/schema identities, full rows/runtime state and source writer manifest against frozen digest.',
    'Any missing/extra row, tenant/byte drift, writer change or identity mismatch invalidates this population; recapture and obtain a fresh independent decision, never silently retarget approval.',
    'Before COMMIT prove transactional rollback; separately committed stages require explicit stage-aware repair, no assumed global rollback.',
    'For ambiguous COMMIT inspect actual schema/data and genuine execution receipts before retry. After COMMIT require approved forward repair or tested backup/restore plus reconciliation of subsequent effects.',
    'No proposed note value is a new-record default. Required-model readers/writers cannot activate over unverified transitional NULLs.',
   ],'remainingHumanDecisions':[
    'Human signing of the existing exact semantic-content requests through a trusted authority; no signature has been created.',
    'Independent application-specific approval or rejection of the exact proposed scalar, frozen population and inventory/writer digests in this package.',
    'Supply/identify a genuinely accepted append-only history repository, trusted authority configuration and authorized authenticated read mechanism; verify head, snapshots, continuity and receipt provenance.',
    'Only after authentic history and valid content/binding authority: review the exact rebased plan, SQL, writer rollout, failure/recovery and execution scope.',
    'Migration execution and deployment require separate explicit authorization; neither is authorized here.',
   ]}
  path=DEST/(domain+'.json');path.write_bytes(json_bytes(package))
  text=f"# {domain.upper()} — measured independent binding review\n\nREVIEW_REQUIRED. Population MEASURED, NOT APPROVED.\n\nApplication `{pin['applicationId']}`; owner `{pin['owner']}`; proposed field `EVOLVE-REFERENCE-NOTE`.\n\nSemantic decision `{package['semanticDecisionDigest']}`. Candidate `{pin['candidateDigest']}`. Proposed binding `{package['bindingDigest']}`; exact scalar UTF-8 hex `65cc8100f09fa68b27` (9 bytes). Synthetic reference-only; never a production value or new-record default.\n\nDatabase `{b['database']['database']}`, schema `{b['database']['schema']}`, PostgreSQL 18.6. Sealed predecessor target 0.4.0, bundle `{b['predecessor']['bundleDigest']}`.\n\nOwner rows: **{len(b['population'])}**, tenants: `{', '.join(b['tenantIdentifiers'])}`. All old field bytes, identities and runtime rows are in the exact inventory. No proposed field exists.\n\nInventory `{frozen['inventoryDigest']}`. Population `{b['populationDigest']}`. Writer inventory `{digest(writers)}`.\n\nAuthenticated proof PENDING_HUMAN_SIGNING; AUTHENTIC_HISTORY_UNAVAILABLE. The database was newly constructed from sealed artifacts and is not evidence of historical journal acceptance.\n\nExisting fixture seed and clone writers omit the proposed field and become incompatible with the final required schema. Existing Commands update resources and do not create them. External import/provisioning remains unknown; no production rollout can rely on this bounded source inventory.\n\nRead-only recapture PASS; all nine measured-population negative cases REJECTED. No expand/backfill/verify/switch/contract SQL ran. The only schema operations were sealed predecessor V1–V3 bootstrap in empty test databases.\n\nRecovery obligations:\n\n"+'\n'.join('- '+x for x in package['recoveryObligations'])+'\n\nExact remaining human decisions:\n\n'+'\n'.join('- '+x for x in package['remainingHumanDecisions'])+f'\n\n[Machine package]({domain}.json). Phase 6 IN_PROGRESS; Phase 7 NOT_STARTED.\n'
  md=DEST/(domain+'.md');md.write_text(text)
  manifest['domains'][domain]={'applicationId':pin['applicationId'],'packageDigest':sha(path.read_bytes()),'notesDigest':sha(md.read_bytes()),'inventoryDigest':frozen['inventoryDigest'],'populationDigest':b['populationDigest'],'bindingDigest':package['bindingDigest']}
  validation['domains'][domain]={'positiveRecapture':positive,'negativeTests':negative,'bindingValidation':package['proposedBindingValidation']}
 (DEST/'manifest.json').write_bytes(json_bytes(manifest));(EVIDENCE/'validation.json').write_bytes(json_bytes(validation))
 print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
