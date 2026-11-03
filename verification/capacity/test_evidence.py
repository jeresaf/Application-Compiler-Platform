"""Explicit synthetic unit receipts. These never establish runtime or human authority."""
import copy,unittest
from pathlib import Path
from engineering.capacity.verification import validate,SCENARIOS,FENCING
from engineering.capacity.workload import PROFILE,OPERATIONS
from engineering.capacity.metrics import aggregate
from engineering.source_intelligence.model import sha


def sample(i,j,op,clients,phase):return {'client':i,'cycle':j,'operation':op,'clients':clients,'phase':phase,'started':0,'finished':.001,'milliseconds':1.,'status':200,'error':None,'disposition':'SUCCESS'}
def level(clients,phase,cycles):
    raw=[sample(i,j,op,clients,phase) for i in range(clients) for j in range(cycles) for op in OPERATIONS]
    return {'clients':clients,'phase':phase,'cyclesPerClient':cycles,'raw':raw,'summary':aggregate(raw,2),'perOperation':{op:aggregate([r for r in raw if r['operation']==op],2) for op in OPERATIONS},'maximumObservedInFlight':clients,'synchronizedLatency':'NONE; NORMAL_REQUESTS_HAVE_NO_HELD_GATES','resources':{'samples':[{'process':{'rssBytes':1},'application':{'maximum':PROFILE['applicationPoolConnections'],'heapMaxBytes':512*1024*1024}}],'maxRSSBytes':1,'samplerExcludedFromPostgresCounts':True}}
def receipt():
    cases={name:{'scenario':name,'result':'PASS'} for name in SCENARIOS}
    cases['workerCapacity'].update(explicitOccurrences=48,initialPending=48,maximumObservedConcurrentClaims=2,rows=[{'queue':str(i),'audit':i,'state':'COMPLETED','result':'VALID','tenant':'unit','auditTenant':'unit'} for i in range(48)],retryExperiments=[{'mode':m} for m in ('ONCE','ALWAYS_FAIL','TIMEOUT')])
    cases['poolPressure'].update(configuration={'maximum':2,'active':2,'acquisitionTimeoutMs':750},duplicates=0,explicitRecoveryRequests=4,responses=[{'status':s} for s in (200,200,500,500)])
    cases['workerScopeLimit'].update(unchangedMaximumDocumentsPerTenant=20,schedule=[{'error':'SCOPE_LIMIT_EXCEEDED'} for _ in range(2)])
    raw=[sample(i%4,i//4,'create',4,'paced') for i in range(24)];cases['policyAdmittedCreate'].update(raw=raw,summary=aggregate(raw,3))
    for name in ('processKillUnderLoad','shutdownUnderLoad'):cases[name].update(exit=-9 if name.startswith('process') else 0,migrationHistoryExact=True,duplicates=0,outcomes=[{'client':i,'databaseOutcome':'COMMITTED','acknowledged':True} for i in range(4)])
    cases['clientTimeout'].update(duplicates=0,response={'status':None,'error':'TimeoutError'},outcomeAfterIndependentObservation='COMMITTED_ACK_LOST')
    fencing={name:{'scenario':name,'result':'PASS','duplicateEffects':0} for name in FENCING};fencing['concurrentQueueClaims'].update(queues=list('abcd'),processes=[1,2]);fencing['leaseExpiryAndStaleCompletion'].update(before={'id':'unit','owner':'old'},winner={'owner':'new','token':2},after={'attempts':[{'queue':'unit','token':1,'state':'FENCED_RESULT'}]});fencing['workerDeathAfterClaim'].update(before={'owner':'old'},winner={'owner':'new','token':2},killed={'exit':-9})
    return {'schema':'acp-h3-execution/1','scope':'QUALIFICATION_ONLY','fixtureOrigin':'SYNTHETIC_UNIT_NOT_RUNTIME','productionCapacity':'NOT_APPROVED','G22':'NOT_SATISFIED','semanticApproval':'NOT_APPROVED','releaseClosure':'BLOCKED','workload':copy.deepcopy(PROFILE),'workloadSHA256':sha(Path('engineering/capacity/profile.json').read_bytes()),'sessions':[{'tenant':'unit','subject':'unit','sid':str(i)} for i in range(16)],'levels':[level(n,'measured',8) for n in (4,8,16)],'warmups':[level(n,'warmup',1) for n in (4,8,16)],'invariants':[{'result':'PASS','duplicates':0} for _ in range(3)],'scenarios':list(cases.values()),'h2Fencing':list(fencing.values()),'cleanup':'VERIFIED','resources':[{'cleanup':'OWN_CONTAINER_AND_VOLUME_REMOVED'}],'sealed05':'ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb','h1PluginRealms':{'status':'PASS'}}


class Evidence(unittest.TestCase):
    def setUp(self):self.record=receipt()
    def reject(self,change):
        change(self.record)
        with self.assertRaises((ValueError,KeyError,TypeError)):validate(self.record)
    def test_closed_positive_unit_receipt(self):self.assertEqual(validate(self.record)['fixtureOrigin'],'SYNTHETIC_UNIT_NOT_RUNTIME')
    def test_wrong_scope(self):self.reject(lambda r:r.update(scope='RELEASE'))
    def test_g22_claim(self):self.reject(lambda r:r.update(G22='PASS'))
    def test_semantic_approval(self):self.reject(lambda r:r.update(semanticApproval='APPROVED'))
    def test_missing_level(self):self.reject(lambda r:r['levels'].pop())
    def test_wrong_client_count(self):self.reject(lambda r:r['levels'][0].update(clients=5))
    def test_missing_warmup(self):self.reject(lambda r:r['warmups'].pop())
    def test_missing_operation_sample(self):self.reject(lambda r:r['levels'][0]['raw'].pop())
    def test_duplicate_sample(self):self.reject(lambda r:r['levels'][0]['raw'].__setitem__(0,r['levels'][0]['raw'][1]))
    def test_unexpected_http_failure(self):self.reject(lambda r:r['levels'][0]['raw'][0].update(status=500))
    def test_false_expected_disposition(self):self.reject(lambda r:r['levels'][0]['raw'][0].update(disposition='EXPECTED_REJECTION'))
    def test_rate_rejection_for_upload(self):self.reject(lambda r:next(x for x in r['levels'][0]['raw'] if x['operation']=='upload').update(status=429))
    def test_forged_percentile(self):self.reject(lambda r:r['levels'][0]['summary']['allRequests'].update(p99Ms=0))
    def test_nan_timing(self):self.reject(lambda r:r['levels'][0]['raw'][0].update(milliseconds=float('nan')))
    def test_missing_resources(self):self.reject(lambda r:r['levels'][0]['resources'].update(samples=[]))
    def test_changed_pool_configuration(self):self.reject(lambda r:r['levels'][0]['resources']['samples'][0]['application'].update(maximum=100))
    def test_missing_correctness(self):self.reject(lambda r:r.update(invariants=[]))
    def test_duplicate_business_effect(self):self.reject(lambda r:r['invariants'][0].update(duplicates=1))
    def test_missing_scenario(self):self.reject(lambda r:r['scenarios'].pop())
    def test_failed_scenario(self):self.reject(lambda r:r['scenarios'][0].update(result='FAIL'))
    def test_missing_cleanup(self):self.reject(lambda r:r.update(cleanup='PENDING'))
    def test_changed_seal(self):self.reject(lambda r:r.update(sealed05='changed'))
    def test_shared_sessions(self):self.reject(lambda r:r['sessions'][0].update(sid=r['sessions'][1]['sid']))
    def test_missing_h2_fencing(self):self.reject(lambda r:r.update(h2Fencing=[]))
    def test_changed_workload(self):self.reject(lambda r:r['workload'].update(measuredCyclesPerClient=1))
