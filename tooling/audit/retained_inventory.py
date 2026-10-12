"""Read-only, exact-byte reference inventory capture and fail-closed drift verification.

Never approves a population or calls compiler history/migration/execution ports.
All cells are SQL NULL or exact database text/bytea hex, avoiding numeric rounding.
"""
import argparse,copy,hashlib,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tooling'),str(Path(__file__).parent)]
from semantic_content_decisions import PINS,RECORDS,sha,json_bytes
from phase6_reference_tests import symbol
SOURCE='9c29727148dd6f9fd563722bd9c5fbffd9dd5699'
OLD_SOURCE='7e4e3438179e7a446c5f3737ad1d6d9cb07a96ea'
OLD_BUNDLE='61c4647cfbe38cdbd97d03305685b3903f3ff24cfdb20d7c5b4502b478a0e06a'
SCHEMA='acp_retained_inventory'

def digest(body):
 return sha(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode())

def writer_inventory(root=ROOT):
 """Conservative source boundary: pin every Python/Java/SQL source in writer roots.

Added sources fail even if spelling evades SQL detection. Matches are review aids,
not a claim that regex recognizes every dynamically generated insert.
"""
 roots=['tooling','targets/spring-vue-postgres/worker','targets/spring-vue-postgres/templates']
 sources=[];matches=[]
 for relative in roots:
  for path in sorted((root/relative).rglob('*')):
   if path.suffix not in ('.py','.java','.sql') or '__pycache__' in path.parts:continue
   name=path.relative_to(root).as_posix();raw=path.read_bytes()
   sources.append({'path':name,'digest':sha(raw)})
   for number,line in enumerate(raw.decode().splitlines(),1):
    if re.search(r'\bINSERT\s+INTO\b|\bCOPY\s+\w|\bseed_sql\(|\bvoid insert\(',line,re.I):
     category=('HISTORY_NOT_DOMAIN' if name.endswith('history_repository.py') else
       'TEST_PROBE_NOT_DOMAIN' if name.endswith('test_canonical03_migrations.py') else
       'RUNTIME_OR_SCHEMA_BOOTSTRAP' if 'templates/' in name or 'worker/' in name else
       'FIXTURE_PROVISIONING_OR_CALLER')
     matches.append({'path':name,'line':number,'lineDigest':sha(line.encode()),'classification':category})
 return {'scope':roots,'sources':sources,'insertionAndProvisioningSites':matches,
  'externalWriters':'UNAVAILABLE_NOT_ASSERTED_ABSENT; inventory is restricted to repository and isolated reference deployments',
  'domainWriters':[
   {'path':'tooling/phase6_reference_tests.py','operation':'seed_sql and relationship/child fixture inserts','omitsProposedField':True,'newSchemaCompatibility':'INCOMPATIBLE_WHERE_OWNER_ROW_IS_CREATED'},
   {'path':'tooling/invocation_reference_tests.py','operation':'explicit approved-snapshot column clone insert(String id)','omitsProposedField':True,'newSchemaCompatibility':'INCOMPATIBLE'},
   {'path':'tooling/integration/retained_inventory_seed.py','operation':'existing seed_sql and existing clone, multi-tenant harness','omitsProposedField':True,'newSchemaCompatibility':'INCOMPATIBLE'},
  ],
  'supportedCommands':{'payment':['CMD-RECORD'],'case-management':['CMD-REVIEW','CMD-APPROVE','CMD-ARCHIVE']},
  'commandCreationBehavior':'Existing-row locking and UPDATE only; Commands and UC-TASK do not provision new resources',
  'importPaths':'No supported domain import endpoint found in target source; external provisioning is unknown and must be inventoried before rollout',
  'runtimeWriters':'Session, rate, idempotency, outbox, audit, job, delivery and lifecycle rows do not create owner resources; proposed owner field does not apply',
  'futureNewRecords':'Explicit required non-null valid UTF-8 String, empty String allowed; no backfill-derived default; switch/fence every provisioning writer before contract'}

def psql(db,sql):
 result=subprocess.run(['psql','-X','-qAt','-h','127.0.0.1','-p','54349','-U','postgres','-d',db,'-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True,check=True)
 decoder=json.JSONDecoder();remaining=result.stdout.strip();documents=[]
 while remaining:
  document,end=decoder.raw_decode(remaining);documents.append(document);remaining=remaining[end:].lstrip()
 return documents

def qi(text):return '"'+text.replace('"','""')+'"'

def capture(domain,db,projects,writers):
 pin=PINS[domain];project=projects/domain
 provenance=json.loads((project/'acp/provenance.json').read_bytes())
 build=provenance['build']
 if build['bundleDigest']!='sha256:'+OLD_BUNDLE or build['canonicalSnapshotDigest']!=pin['previousDigest'] or build['targetProfile']!='acp-spring-vue-postgres/0.4.0':raise ValueError('WRONG_SEALED_PREDECESSOR')
 # Read exact sealed artifact digests before querying any database.
 for item in provenance['artifacts']:
  if sha((project/item['artifact']).read_bytes())!=item['artifactDigest']:raise ValueError('SEALED_PREDECESSOR_ARTIFACT_DRIFT')
 catalogsql="""SELECT coalesce(json_agg(x ORDER BY table_name,ordinal_position),'[]'::json) FROM (SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default FROM information_schema.columns WHERE table_schema='acp_retained_inventory') x;"""
 columns=psql(db,'BEGIN READ ONLY;'+catalogsql+'COMMIT;')[0]
 if not columns:raise ValueError('MISSING_REFERENCE_SCHEMA')
 tables={}
 for column in columns:tables.setdefault(column['table_name'],[]).append(column)
 meta="""SELECT json_build_object('database',current_database(),'databaseOid',(SELECT oid::text FROM pg_database WHERE datname=current_database()),'schema','acp_retained_inventory','schemaOid',(SELECT oid::text FROM pg_namespace WHERE nspname='acp_retained_inventory'),'systemIdentifier',(SELECT system_identifier::text FROM pg_control_system()),'version',version(),'versionNumber',current_setting('server_version_num'),'encoding',current_setting('server_encoding'),'readOnly',current_setting('transaction_read_only'),'defaultReadOnly',current_setting('default_transaction_read_only'),'captureTimestamp',clock_timestamp()::text,'transactionSnapshot',pg_current_snapshot()::text);"""
 schema_sql="""SELECT json_build_object('constraints',coalesce((SELECT json_agg(x ORDER BY table_name,name) FROM (SELECT c.relname AS table_name,k.conname AS name,pg_get_constraintdef(k.oid,true) AS definition FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='acp_retained_inventory') x),'[]'::json),'sequences',coalesce((SELECT json_agg(x ORDER BY sequencename) FROM (SELECT sequencename,data_type::text,start_value::text,min_value::text,max_value::text,increment_by::text,cycle,cache_size::text,last_value::text FROM pg_sequences WHERE schemaname='acp_retained_inventory') x),'[]'::json),'indexes',coalesce((SELECT json_agg(x ORDER BY tablename,indexname) FROM (SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='acp_retained_inventory') x),'[]'::json));"""
 queries=['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;',meta,catalogsql,schema_sql]
 for name,cols in sorted(tables.items()):
  cells=[]
  for col in cols:
   ident=qi(col['column_name']);expr=f"encode({ident},'hex')" if col['udt_name']=='bytea' else ident+'::text'
   cells.extend(["'"+col['column_name'].replace("'","''")+"'",expr])
  obj='jsonb_build_object('+','.join(cells)+')'
  queries.append("SELECT json_build_object('table','"+name+"','rows',coalesce(jsonb_agg(row ORDER BY row::text),'[]'::jsonb)) FROM (SELECT "+obj+' AS row FROM '+qi(SCHEMA)+'.'+qi(name)+') t;')
 queries.append('COMMIT;')
 result=psql(db,'\n'.join(queries));metadata,capturedcols,schema_definition,*rows=result
 if columns!=capturedcols:raise ValueError('CONCURRENT_SCHEMA_DRIFT')
 if metadata['versionNumber']!='180006' or metadata['readOnly']!='on' or metadata['defaultReadOnly']!='on':raise ValueError('DATABASE_VERSION_OR_FENCE')
 root=pin['owner'];idfield='FLD-PAYMENT-ID' if domain=='payment' else 'CASE-ID';tenantfield='FLD-PAYMENT-TENANT' if domain=='payment' else 'CASE-TENANT'
 allrows={r['table']:r['rows'] for r in rows};ownerrows=allrows[symbol(root,'e')]
 if symbol('EVOLVE-REFERENCE-NOTE','f') in {c['column_name'] for c in columns}:raise ValueError('PROPOSED_FIELD_ALREADY_PRESENT')
 population=[{'resourceHex':r[symbol(idfield,'f')],'tenantHex':r[symbol(tenantfield,'f')]} for r in ownerrows]
 if len(population)!=3 or len({p['tenantHex'] for p in population})!=2:raise ValueError('REFERENCE_POPULATION')
 body={'format':'acp-retained-inventory/1','classification':'NEWLY_CONSTRUCTED_SYNTHETIC_REFERENCE_TEST_DEPLOYMENT',
  'domain':domain,'applicationId':pin['applicationId'],'sourceCommit':SOURCE,
  'predecessor':{'target':'acp-spring-vue-postgres/0.4.0','generator':'acp-spring-vue-generator/0.4.0','sourceCommit':OLD_SOURCE,'bundleDigest':OLD_BUNDLE,'provenanceDigest':sha((project/'acp/provenance.json').read_bytes()),'build':provenance['build'],'sealedArtifactsVerified':len(provenance['artifacts'])},
  'canonicalDigest':pin['previousDigest'],'database':metadata,'columns':columns,'schemaDefinition':schema_definition,
  'cellEncoding':'SQL NULL => JSON null; bytea => exact lowercase hex; all other SQL values => database text, never rounded JSON numbers',
  'fieldColumnMap':{n['id']:symbol(n['id'],'f') for n in json.loads((ROOT/'test-corpus/deterministic-v04'/(domain+'-canonical-candidate.json')).read_bytes())['content']['nodes'] if n['kind']=='Field'},
  'tables':allrows,'rowCounts':{name:len(values) for name,values in allrows.items()},
  'population':population,'ownerTable':symbol(root,'e'),'tenantIdentifiers':sorted({bytes.fromhex(p['tenantHex']).decode() for p in population}),
  'writerInventoryDigest':digest(writers),'freeze':'Seed harness exited; database default read-only enabled; repeatable-read read-only snapshot; recapture must match before any future approval/execution. Local superuser can remove fence, so artifacts and live drift check are required.',
  'migrationExecuted':False,'populationApproved':False,'historyStatus':'AUTHENTIC_HISTORY_UNAVAILABLE'}
 body['populationDigest']=population_digest(body)
 return {'body':body,'inventoryDigest':digest(body)}

def population_digest(body):
 stable=copy.deepcopy(body);stable.pop('populationDigest',None)
 stable['database'].pop('captureTimestamp',None);stable['database'].pop('transactionSnapshot',None)
 return digest(stable)

def verify(frozen,observed,writers):
 for document in (frozen,observed):
  body=document['body']
  if digest(body)!=document['inventoryDigest'] or population_digest(body)!=body['populationDigest']:raise ValueError('INVALID_INVENTORY_DIGEST')
  if body['domain'] not in PINS or body['applicationId']!=PINS[body['domain']]['applicationId']:raise ValueError('WRONG_APPLICATION')
  if digest(writers)!=body['writerInventoryDigest']:raise ValueError('WRITER_DRIFT')
 if frozen['body']['populationDigest']!=observed['body']['populationDigest']:raise ValueError('FROZEN_POPULATION_DRIFT')
 return {'result':'PASS','populationDigest':frozen['body']['populationDigest'],'authority':'NONE'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--database');p.add_argument('--domain',choices=PINS);p.add_argument('--projects',type=Path);p.add_argument('--output',type=Path);p.add_argument('--writers',type=Path,required=True);p.add_argument('--verify-frozen',type=Path);p.add_argument('--observed',type=Path);a=p.parse_args()
 writers=json.loads(a.writers.read_bytes())
 if writers!=writer_inventory():raise ValueError('STALE_SOURCE_WRITER_INVENTORY')
 if a.verify_frozen:
  if not a.observed:p.error('--observed is required for verification')
  print(json.dumps(verify(json.loads(a.verify_frozen.read_bytes()),json.loads(a.observed.read_bytes()),writers),indent=2))
 else:
  if not all((a.database,a.domain,a.projects,a.output)):p.error('capture requires --database --domain --projects --output')
  document=capture(a.domain,a.database,a.projects,writers);a.output.write_bytes(json_bytes(document))
