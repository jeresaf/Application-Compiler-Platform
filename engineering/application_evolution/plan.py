"""Bounded R6→R7 preview adapter over native diff, dependency graph and ArtifactPlans.

No HistoryRepository, approvals, journal anchors or accepted MigrationPlan are issued.
"""
import json
from functools import lru_cache
from pathlib import Path
from engineering.source_intelligence.model import encode,sha,require
from engineering.documents.semantics import validate_snapshot as validate6
from engineering.jobs.semantics import validate_snapshot as validate7
from changes import semantic_diff,graph,closure,reverse,fingerprint
from compiler_contracts import wire,fingerprint as compiler_fingerprint

@lru_cache(maxsize=4)
def validated(raw,version):
 value=json.loads(raw);({'0.6.0':validate6,'0.7.0':validate7}[version])(value);return True

def artifacts(plan):
 return {a['path']:a for a in (wire(plan) if not isinstance(plan,dict) else plan)['artifacts']}

def preview(before,after,old_plan,new_plan,old_identity,new_identity,*,successor=None):
 validated(encode(before),'0.6.0');validated(encode(after),'0.7.0')
 require(before['content']['applicationId']==after['content']['applicationId'],'EVOLUTION_APPLICATION')
 diff=semantic_diff(before,after);require(diff and all(d['operation']=='ADD' and d['after']['revision']==1 for d in diff),'EVOLUTION_ADDITIVE_ONLY')
 from engineering.documents.target import DocumentTarget
 from engineering.jobs.target import JobTarget
 if successor is not None:
  from engineering.hardening.target import HardeningTarget
  require(type(successor) is HardeningTarget,'EVOLUTION_UNREGISTERED_SUCCESSOR')
  successor._verify()
  registered=HardeningTarget()
  require(successor.generator==registered.generator and successor.bundle==registered.bundle and successor.profile==registered.profile,'EVOLUTION_SUCCESSOR_BINDING')
  successor=registered
 for snapshot,plan,identity,target in ((before,old_plan,old_identity,DocumentTarget()),(after,new_plan,new_identity,successor if successor is not None else JobTarget())):
  require(set(identity)=={'candidate','generator','compiler','pipeline','artifactPlan'} and identity['candidate']==snapshot['contentDigest'] and identity['generator']==target.generator and identity['artifactPlan']==compiler_fingerprint(plan),'EVOLUTION_COMPILATION_IDENTITY')
  require(all(a['provenance']['compiler']==identity['compiler'] and a['provenance']['pipeline']==identity['pipeline'] for a in artifacts(plan).values()),'EVOLUTION_COMPILER_IDENTITY')
 a,b=artifacts(old_plan),artifacts(new_plan);require(set(a)<=set(b),'EVOLUTION_ARTIFACT_REMOVAL')
 # Artifact bytes are the compiler's canonical immutable Document transport.
 def text(row):
  value=row['content'];require(value['encoding']=='UTF-8' and isinstance(value['text'],str),'EVOLUTION_ARTIFACT_ENCODING');return value['text']
 oldsql={p:sha(text(v).encode()) for p,v in a.items() if p.startswith('backend/src/main/resources/db/migration/')}
 newsql={p:sha(text(v).encode()) for p,v in b.items() if p.startswith('backend/src/main/resources/db/migration/')}
 require(len(oldsql)==4 and all(newsql.get(p)==h for p,h in oldsql.items()),'EVOLUTION_HISTORICAL_MIGRATION')
 added=set(newsql)-set(oldsql);require(added=={'backend/src/main/resources/db/migration/V5__integrity_jobs.sql'},'EVOLUTION_MIGRATION_SET')
 changes=[{'path':p,'operation':'ADD' if p not in a else 'REGENERATE','before':sha(encode(a[p])) if p in a else None,'after':sha(encode(b[p])),'origins':b[p]['mappings']} for p in sorted(b) if p not in a or a[p]['content']!=b[p]['content']]
 seeds={d['id'] for d in diff};impact=sorted(closure(seeds,reverse(graph(after))))
 change={'schema':'acp-engineering-preview-change/1','applicationId':before['content']['applicationId'],'base':before['contentDigest'],'candidate':after['contentDigest'],'operations':diff,'impact':impact,'compatibility':'REVIEW_REQUIRED','requiredScopes':['SEMANTIC','SECURITY','MIGRATION'],'authority':'NOT_APPROVED','acceptedHistory':'UNAVAILABLE_NOT_CONSTRUCTED'}
 body={'schema':'acp-application-evolution-preview/1','scope':'ISOLATED_SYNTHETIC_ENGINEERING_ONLY','change':change,'changeDigest':fingerprint(change,'record'),'before':old_identity,'after':new_identity,'migration':{'existing':oldsql,'additions':{p:newsql[p] for p in sorted(added)},'mode':'STOP_MIGRATE_RESTART','transactional':True,'oldWriters':'FENCED_BEFORE_MIGRATION','rollback':'ROLLBACK_UNCOMMITTED_DDL; VERIFIED_R6_RESTORE_FOR_COMMITTED_STATE','productionApproval':'NOT_AUTHORIZED'},'artifactImpact':changes,'acceptedProtocol':'HistoryRepository/changes.prepare do not support these preview Canonical versions; NO ACCEPTED OPERATIONS','semanticApproval':'NOT_APPROVED','releaseDisposition':'PHASE6_RELEASE_CLOSURE_BLOCKED'}
 return {**body,'planDigest':fingerprint(body,'plan')}

def validate_plan(plan):
 require(plan['planDigest']==fingerprint({k:v for k,v in plan.items() if k!='planDigest'},'plan'),'EVOLUTION_PLAN_DIGEST')
 require(plan['scope']=='ISOLATED_SYNTHETIC_ENGINEERING_ONLY' and plan['semanticApproval']=='NOT_APPROVED' and plan['migration']['mode']=='STOP_MIGRATE_RESTART','EVOLUTION_SCOPE')
 return plan

def preconditions(plan,observed,expected,sql):
 validate_plan(plan);require(set(observed)=={'databaseIdentity','schema','history','populationDigest','source','target'},'EVOLUTION_OBSERVATION_FIELDS');require(observed==expected,'EVOLUTION_STALE_DATABASE_OR_SOURCE')
 require(list(plan['migration']['additions'].values())==[sha(sql.encode())],'EVOLUTION_SQL_IDENTITY');require(observed['source']==plan['change']['base'] and observed['target']==plan['change']['candidate'],'EVOLUTION_CANDIDATE_IDENTITY');require(observed['schema']=='acp_browser_case_management' and [r.get('version') for r in observed['history'] if r.get('type')=='SQL']==['1','2','3','4'] and all(r.get('success') is True for r in observed['history']),'EVOLUTION_SCHEMA_PREREQUISITE')
 return {'scope':'ENGINEERING_PREVIEW_ONLY','planDigest':plan['planDigest'],'observationSHA256':sha(encode(observed)),'sqlSHA256':sha(sql.encode()),'acceptedMigrationApproval':False}

CAPTURE_FILES=frozenset({'database.sql','database-state.json','migration-history.json','database-identity.json'})
def verify_capture(folder,pins):
 folder=Path(folder);require(set(pins)==CAPTURE_FILES and folder.is_dir() and not folder.is_symlink(),'EVOLUTION_CAPTURE_INVENTORY')
 for name,digest in pins.items():
  path=folder/name;require(path.is_file() and not path.is_symlink() and sha(path.read_bytes())==digest,'EVOLUTION_CAPTURE_HASH')
 return dict(pins)
