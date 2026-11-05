"""Controlled CREATE pool exhaustion, separate from original-failure attribution."""
from concurrent.futures import ThreadPoolExecutor
import json,urllib.request
from engineering.capacity.workload import request,token
from engineering.reliability.fixture import BEFORE
from engineering.reference_application import lifecycle as life
from engineering.source_intelligence.model import require


def create_pool(lab,session,pool):
    before=lab.counts();payloads=[{'title':'H4 pool '+str(pool)+' '+str(i),'summary':'Authorized disposable resource experiment','idempotencyKey':'h4-pool-'+str(pool)+'-'+str(i)} for i in (0,1)]
    lab.trigger(lab.table,True)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            with lab.gate(BEFORE):
                first=workers.submit(request,session,lab.create['path'],payloads[0],token(0));lab.blocked(BEFORE,1)
                second=workers.submit(request,session,lab.create['path'],payloads[1],token(1))
                if pool==2:
                    rejected=second.result(timeout=6);require(rejected['status']==500,'H4_POOL_NOT_EXHAUSTED:'+str(rejected))
                    require(not first.done(),'H4_FIRST_NOT_HELD')
                else:
                    lab.blocked(BEFORE,2);require(not first.done() and not second.done(),'H4_POOL_COUNTEREXAMPLE_SERIALIZED')
                with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(session.backend_port)+'/__test/h3-resources',headers={'Authorization':'Bearer browser-authorized'}),timeout=2) as response:observed=json.load(response)
                life.save(lab.logs/'h4-pool-held.json',observed)
                require(observed['maximum']==pool and observed['active']==(1 if pool==2 else 2) and observed['acquisitionTimeoutMs']==750,'H4_POOL_IDENTITY:'+str(observed))
                require(lab.counts()[lab.table]==before[lab.table],'H4_UNCOMMITTED_CASE_VISIBLE')
            results=[first.result(timeout=10),second.result(timeout=10)]
        require(results[0]['status']==200 and results[1]['status']==(500 if pool==2 else 200),'H4_POOL_OUTCOMES')
    finally:lab.trigger(lab.table,False)
    after=lab.counts();commits=1 if pool==2 else 2
    for table in (lab.table,'acp_audit'):require(after[table]==before[table]+commits,'H4_PARTIAL_OR_DUPLICATE_CREATE')
    recovered=None
    if pool==2:
        recovered=request(session,lab.create['path'],payloads[1],token(1));require(recovered['status']==200,'H4_EXPLICIT_RECOVERY_FAILED')
        after=lab.counts()
    for table in (lab.table,'acp_audit','acp_idempotency'):require(after[table]==before[table]+2,'H4_RECOVERY_DUPLICATE_EFFECT')
    require(after['acp_classification_audit']==before['acp_classification_audit']+2*len(lab.create['writtenFields']),'H4_CLASSIFICATION_AUDIT')
    for i,r in enumerate((results[0],recovered if recovered else results[1])):
        require(lab.ownership(r['value']['resourceId'])=={'tenant':'tenant-one' if i==0 else 'tenant-two','subject':'fixture:operator' if i==0 else 'fixture:reporter-two'},'H4_CREATE_OWNER')
    return {'scenario':'controlledCreatePool','pool':pool,'observedPool':observed,'responses':[{k:v for k,v in r.items() if k!='value'} for r in results],'before':before,'after':after,'explicitRecoveryRequests':1 if recovered else 0,'originalH3Attribution':'NOT_ESTABLISHED','productionCapacity':'NOT_APPROVED','scope':'QUALIFICATION_ONLY'}
