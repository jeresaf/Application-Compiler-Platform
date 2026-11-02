"""Actual generated workers in independent JVMs; only fault setup is test-only."""
import json,time,uuid,os
from pathlib import Path
from engineering.demo import reference as demo
from engineering.reference_application.evolution import api
from engineering.source_intelligence.model import require
from engineering.reference_application import lifecycle as life

def wait(read,predicate,label,seconds=20):
 deadline=time.monotonic()+seconds
 while True:
  value=read()
  if predicate(value):return value
  if time.monotonic()>=deadline:raise AssertionError(label+':'+json.dumps(value,default=str)[:1600])
  time.sleep(.05)

def worker_env(session,enabled):
 session.env.update(ACP_INTEGRITY_MODE='preview',ACP_INTEGRITY_ENABLED='true' if enabled else 'false')
 session.env['JAVA_TOOL_OPTIONS']=session.env.get('JAVA_TOOL_OPTIONS','')+' -Dacp.integrity.worker-identity=service:reference-integrity -Dacp.integrity.worker-tenants=tenant-one,tenant-two'
 return session

def exercise(root,logs,first):
 sessions=[first];second=None;record={};offset=1
 def admin(body):
  status,value=api(sessions[0],'/__test/job-admin',body);require(status==200,'JOB_LAB_ADMIN:'+str(value));return value
 def state():
  status,value=api(sessions[0],'/__test/job-state');require(status==200,'JOB_LAB_STATE');return value
 def qstate(q):return next(r for r in state()['queue'] if r['id']==q)
 def enqueue(mode='NONE',**extra):
  nonlocal offset
  q=str(uuid.uuid4());admin({'action':'ENQUEUE_FAULT','queue':q,'resource':saved['resource'],'document':saved['document']['documentId'],'sha256':saved['document']['sha256'],'offset':offset,'mode':mode,**extra});offset+=1;return q
 def finished(q,status='COMPLETED'):
  return wait(lambda:qstate(q),lambda r:r['state']==status,'JOB_FINISH:'+q)
 saved=json.loads((logs/'committed.json.documents').read_bytes());require(api(first,'/__test/job-admin',{'action':'INIT'})[0]==200,'JOB_LAB_INIT');first.close()
 try:
  record['authorityRejections']=[]
  for index,override in enumerate(('worker-identity=service:unauthorized','worker-tenants=','worker-tenants=tenant-three')):
   probe=worker_env(demo.Session(root,'case-management',logs),True);probe.backend_port=18083;probe.sequence=50+index;sessions.append(probe);probe.env['JAVA_TOOL_OPTIONS']+=' -Dacp.integrity.'+override
   try:
    try:probe.launch()
    except ValueError:
     text=(logs/f'demo-backend-{probe.sequence}.log').read_text();require('WORKER_AUTHORITY_REQUIRED' in text,'JOB_WRONG_AUTHORITY_REJECTION');record['authorityRejections'].append(override)
    else:raise AssertionError('JOB_UNAUTHORIZED_SERVICE_STARTED')
   finally:probe.close();sessions.remove(probe)
  first=worker_env(demo.Session(root,'case-management',logs),True);sessions[0]=first;first.sequence=100;first.launch();first.start_frontend();secondary_logs=logs.parent/'secondary-runtime';secondary_logs.mkdir();second=worker_env(demo.Session(root,'case-management',secondary_logs),True);second.backend_port=18082;sessions.append(second);second.launch()
  initial=wait(state,lambda s:len(s['queue'])==4 and len(s['results'])==4 and all(r['state']=='COMPLETED' for r in s['queue']),'JOB_REAL_SCHEDULE')
  require(all(r['status']=='VALID' for r in initial['results']),'JOB_INITIAL_INTEGRITY');record['scheduled']=initial
  admin({'action':'MISSED'});skipped=wait(state,lambda s:all(r['skipped']>=3 for r in s['schedule']),'JOB_MISSED');require(len(skipped['queue'])==4,'JOB_DUPLICATE_ENQUEUE');record['missed']=skipped['schedule']
  q=enqueue('ONCE',failures=1);row=finished(q);require(row['attempts']==2,'JOB_RETRY_COUNT');record['transient']=row
  q=enqueue('ALWAYS_FAIL');row=finished(q,'FAILED');require(row['attempts']==3 and row['error']=='DEPENDENCY_UNAVAILABLE','JOB_RETRY_EXHAUSTION');record['exhaustion']=row
  q=enqueue('TIMEOUT');row=finished(q,'FAILED');require(row['attempts']==3 and row['error']=='EXECUTION_TIMEOUT','JOB_TIMEOUT');record['timeout']=row
  q=enqueue(invalid=True);row=finished(q,'FAILED');require(row['error']=='INVALID_PAYLOAD','JOB_INVALID_PAYLOAD');record['invalid']=row
  q=enqueue(document=str(uuid.uuid4()));row=finished(q,'FAILED');require(row['error']=='MISSING_DOCUMENT','JOB_MISSING');record['missing']=row
  foreign=json.loads((logs/'committed.json.report').read_bytes())['ids']['foreign'];q=enqueue(resource=foreign);row=finished(q,'FAILED');require(row['error']=='MISSING_DOCUMENT','JOB_CROSS_TENANT');record['foreign']=row
  require(api(first,'/__test/document-tamper',{})[0]==200,'JOB_CORRUPT_SETUP');q=enqueue();row=finished(q,'FAILED');require(row['error']=='HASH_MISMATCH','JOB_CORRUPTION');require(api(first,'/__test/document-tamper',{})[0]==200,'JOB_CORRUPT_RESTORE');record['corrupt']=row
  # Force a result-transaction failure after claim, then remove it for recovery.
  q=enqueue('HOLD_FIRST');wait(state,lambda s:any(c['queue']==q and c['entered'] for c in s['controls']),'JOB_ROLLBACK_GATE');admin({'action':'ROLLBACK_ON','queue':q});admin({'action':'RELEASE','queue':q});wait(lambda:qstate(q),lambda r:r['state']=='RETRY','JOB_ROLLBACK_RETRY');snapshot=state();require(not any(r['queue']==q for r in snapshot['results']),'JOB_PARTIAL_RESULT');admin({'action':'ROLLBACK_OFF','queue':q});row=finished(q);record['rollback']={'beforeRecovery':snapshot,'after':row}
  q=enqueue('HOLD_FIRST');held=wait(state,lambda s:any(c['queue']==q and c['entered'] for c in s['controls']),'JOB_FENCE_GATE');admin({'action':'EXPIRE','queue':q});row=finished(q);require(row['token']==2,'JOB_RECLAIM_TOKEN');admin({'action':'RELEASE','queue':q});proof=wait(state,lambda s:any(a['queue']==q and a['token']==1 and a['state']=='FENCED_RESULT' for a in s['attempts']),'JOB_STALE_FENCE');require(len([r for r in proof['results'] if r['queue']==q])==1,'JOB_DUPLICATE_EFFECT');record['fenced']={'held':held,'after':proof}
  q=enqueue('HOLD_FIRST');held=wait(state,lambda s:any(c['queue']==q and c['entered'] for c in s['controls']),'JOB_CRASH_GATE');running=qstate(q);require(running['state']=='RUNNING','JOB_CRASH_NOT_RUNNING');owners={api(s,'/__test/worker-owner')[1]['owner']:s for s in sessions};victim=owners[running['owner']];victim.process.kill();victim.process.wait(timeout=10)
  # Move test administration to the surviving process; no HTTP invokes execution.
  survivor=next(s for s in sessions if s is not victim);sessions.remove(survivor);sessions.insert(0,survivor);row=finished(q);require(row['attempts']==2 and row['owner']!=running['owner'],'JOB_CRASH_RECOVERY');record['crash']={'before':running,'after':row,'killedPid':victim.process.pid}
  victim.close();replacement=worker_env(demo.Session(root,'case-management',victim.logs),True);replacement.backend_port=victim.backend_port;replacement.sequence=300;sessions[sessions.index(victim)]=replacement;replacement.launch()
  q=enqueue(tenant='tenant-three');s=state();require(qstate(q)['attempts']==0,'JOB_UNAUTHORIZED_WORKER_SCOPE');record['outOfScopeQueue']=q
  final=state();require(len(final['audits'])==len(final['results']) and len({r['audit_id'] for r in final['results']})==len(final['results']),'JOB_EFFECT_AUDIT_DUPLICATION');require(all(len([r for r in final['results'] if r['queue']==q['id']])<=1 for q in final['queue']),'JOB_DUPLICATE_RESULT');life.save(logs.parent/'job-execution.json',record);life.save(logs.parent/'job-state.json',final)
  # Leave only the primary web instance, with workers disabled for stable replay.
  for s in sessions:s.close()
  finalsession=worker_env(demo.Session(root,'case-management',logs),False);finalsession.sequence=400;sessions.append(finalsession);finalsession.launch();finalsession.start_frontend();return finalsession,record
 except:
  for s in sessions:s.close()
  raise
