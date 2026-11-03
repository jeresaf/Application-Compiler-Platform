"""Phase 8 capacity observations. No performance result is release approval."""
import hashlib,json,math
from pathlib import Path
from engineering.capacity.workload import PROFILE,OPERATIONS
from engineering.capacity.metrics import aggregate
from engineering.source_intelligence.model import require,sha
from compiler_contracts import fingerprint

SCENARIOS=frozenset(('workerCapacity','policyAdmittedCreate','invalidAndBoundedInputs','poolPressure','clientTimeout','shutdownUnderLoad','processKillUnderLoad','workerScopeLimit'))
FENCING=frozenset(('concurrentQueueClaims','leaseExpiryAndStaleCompletion','workerDeathAfterClaim'))


def validate(record):
    require(record['schema']=='acp-h3-execution/1' and record['scope']=='QUALIFICATION_ONLY','H3_SCOPE')
    require(record['productionCapacity']=='NOT_APPROVED' and record['G22']=='NOT_SATISFIED' and record['semanticApproval']=='NOT_APPROVED' and record['releaseClosure']=='BLOCKED','H3_AUTHORITY_BOUNDARY')
    require(record['workload']==PROFILE and record['workloadSHA256']==sha((Path(__file__).parent/'profile.json').read_bytes()),'H3_WORKLOAD_IDENTITY')
    require([r['clients'] for r in record['levels']]==[4,8,16] and [r['clients'] for r in record['warmups']]==[4,8,16],'H3_MISSING_LEVEL')
    require(len(record['sessions'])==16 and len({(s['tenant'],s['subject'],s['sid']) for s in record['sessions']})==16,'H3_SESSION_IDENTITY')
    for phase,levels,cycles in (('measured',record['levels'],8),('warmup',record['warmups'],1)):
        for level in levels:
            clients=level['clients'];raw=level['raw'];expected={(i,j,op) for i in range(clients) for j in range(cycles) for op in OPERATIONS}
            require(level['phase']==phase and level['cyclesPerClient']==cycles and len(raw)==len(expected) and {(r['client'],r['cycle'],r['operation']) for r in raw}==expected,'H3_INCOMPLETE_SAMPLES')
            for r in raw:
                require(r['phase']==phase and r['clients']==clients and r['error'] is None and r['status'] in ((200,429) if r['operation'] in ('create','query') else (200,)),'H3_INVALID_SAMPLE_STATUS')
                require(r['disposition']==('SUCCESS' if r['status']==200 else 'EXPECTED_REJECTION'),'H3_FALSE_DISPOSITION')
                require(all(type(r[k]) in (int,float) and math.isfinite(r[k]) for k in ('started','finished','milliseconds')) and r['finished']>=r['started'] and abs((r['finished']-r['started'])*1000-r['milliseconds'])<.001,'H3_INVALID_TIMING')
            require(level['summary']==aggregate(raw,level['summary']['elapsedSeconds']),'H3_FORGED_STATISTICS')
            require(set(level['perOperation'])==set(OPERATIONS),'H3_MISSING_OPERATION')
            for op in OPERATIONS:require(level['perOperation'][op]==aggregate([r for r in raw if r['operation']==op],level['summary']['elapsedSeconds']),'H3_OPERATION_STATISTICS')
            require(level['maximumObservedInFlight']>=min(clients,4) and level['synchronizedLatency']=='NONE; NORMAL_REQUESTS_HAVE_NO_HELD_GATES','H3_CONCURRENCY_OR_BARRIER')
            resources=level['resources'];require(resources['samples'] and resources['maxRSSBytes']>0 and resources['samplerExcludedFromPostgresCounts'],'H3_MISSING_RESOURCES')
            require(all(r['process']['rssBytes']>0 and r['application']['maximum']==PROFILE['applicationPoolConnections'] and r['application']['heapMaxBytes']<=512*1024*1024 for r in resources['samples']),'H3_RESOURCE_PROFILE')
    require(len(record['invariants'])==3 and all(r['result']=='PASS' and r['duplicates']==0 for r in record['invariants']),'H3_CORRECTNESS_MISSING')
    cases=record['scenarios'];require(len(cases)==len(SCENARIOS) and {r['scenario'] for r in cases}==SCENARIOS and all(r['result']=='PASS' for r in cases),'H3_MISSING_OR_FAILED_SCENARIO')
    by={r['scenario']:r for r in cases};worker=by['workerCapacity']
    require(worker['explicitOccurrences']==48 and worker['initialPending']>=48 and len(worker['rows'])==48 and len({r['queue'] for r in worker['rows']})==48 and 0<worker['maximumObservedConcurrentClaims']<=2,'H3_WORKER_CAPACITY')
    require(len({r['audit'] for r in worker['rows']})==48 and all(r['state']=='COMPLETED' and r['result']=='VALID' and r['tenant']==r['auditTenant'] for r in worker['rows']),'H3_WORKER_EFFECTS')
    require({r['mode'] for r in worker['retryExperiments']}=={'ONCE','ALWAYS_FAIL','TIMEOUT'},'H3_MISSING_RETRY_TEST')
    pressure=by['poolPressure'];require(pressure['configuration']['maximum']==2 and pressure['configuration']['active']==2 and pressure['configuration']['acquisitionTimeoutMs']==750 and pressure['duplicates']==0 and pressure['explicitRecoveryRequests']==4 and len(pressure['responses'])==4 and sum(r['status']==200 for r in pressure['responses'])==2,'H3_POOL_BOUNDARY')
    require(len(by['workerScopeLimit']['schedule'])==2 and by['workerScopeLimit']['unchangedMaximumDocumentsPerTenant']==20 and all(r['error']=='SCOPE_LIMIT_EXCEEDED' for r in by['workerScopeLimit']['schedule']),'H3_SCOPE_LIMIT_CHANGED')
    paced=by['policyAdmittedCreate'];require(len(paced['raw'])==24 and paced['summary']==aggregate(paced['raw'],paced['summary']['elapsedSeconds']),'H3_PACED_RAW_EVIDENCE')
    require(by['policyAdmittedCreate']['summary']['population']==24 and by['policyAdmittedCreate']['summary']['unexpectedErrors']==0,'H3_MISSING_ADMITTED_CREATE')
    for name in ('processKillUnderLoad','shutdownUnderLoad'):
        outcomes=by[name]['outcomes'];require(len(outcomes)==4 and {o['client'] for o in outcomes}=={0,1,2,3} and by[name]['duplicates']==0 and all(o['databaseOutcome'] in ('COMMITTED','ROLLED_BACK') and (not o['acknowledged'] or o['databaseOutcome']=='COMMITTED') for o in outcomes),'H3_INDETERMINATE_RECOVERY_EVIDENCE')
    require(by['clientTimeout']['response']['status'] is None and by['clientTimeout']['response']['error'] and by['clientTimeout']['outcomeAfterIndependentObservation'] in ('COMMITTED_ACK_LOST','ROLLED_BACK'),'H3_CLIENT_TIMEOUT_EVIDENCE')
    require(by['processKillUnderLoad']['exit']==-9 and by['shutdownUnderLoad']['migrationHistoryExact'] and by['clientTimeout']['duplicates']==0,'H3_RECOVERY_PROOF')
    proof={r['scenario']:r for r in record['h2Fencing']}
    if set(proof)==FENCING:
        claims=proof['concurrentQueueClaims'];stale=proof['leaseExpiryAndStaleCompletion'];death=proof['workerDeathAfterClaim']
        require(len(claims['queues'])==4 and len(set(claims['processes']))==2,'H3_INDEPENDENT_WORKERS')
        require(stale['winner']['token']==2 and stale['winner']['owner']!=stale['before']['owner'] and any(a['queue']==stale['before']['id'] and a['token']==1 and a['state']=='FENCED_RESULT' for a in stale['after']['attempts']),'H3_STALE_WORKER_PROOF')
        require(death['killed']['exit']==-9 and death['winner']['token']==2 and death['winner']['owner']!=death['before']['owner'],'H3_WORKER_DEATH_PROOF')
    require(len(record['h2Fencing'])==3 and {r['scenario'] for r in record['h2Fencing']}==FENCING and all(r['result']=='PASS' and r['duplicateEffects']==0 for r in record['h2Fencing']),'H3_H2_FENCING_MISSING')
    require(record['cleanup']=='VERIFIED' and record['resources'] and all(r['cleanup']=='OWN_CONTAINER_AND_VOLUME_REMOVED' for r in record['resources']),'H3_CLEANUP')
    require(record['sealed05']=='ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb' and record['h1PluginRealms']['status']=='PASS','H3_SEAL_OR_H1_CHANGED')
    return record


class Execution:
    def __init__(self,path):
        self.path=Path(path);self.pin=sha(self.path.read_bytes());self.context={'h3ExecutionSHA256':self.pin,'h3Scope':'QUALIFICATION_ONLY'}
    def apply(self,session,rows):
        require(sha(self.path.read_bytes())==self.pin,'H3_EXECUTION_CHANGED');r=validate(json.loads(self.path.read_bytes()))
        require(r['generator']['generator']==session.inputs['generator'] and r['canonicalDigest']==session.inputs['canonicalDigest'] and r['artifactPlanDigest']==fingerprint(session.plan) and r['sourceModelDigest']==session.model['digest'],'H3_EXECUTION_IDENTITY')
        from engineering.capacity.run import source_inventory
        require(r['sourceSHA256']==source_inventory(),'H3_SOURCE_INVENTORY_CHANGED')
        root=self.path.parent
        expected={'execution-resources.json','runtime/initial-history.json','runtime/before-workloads.json','runtime/workload-identities.json','runtime/scenarios.json','runtime/observations.json','runtime/query-plans.json','database/database-state.json','database/database-identity.json','database/migration-history.json','build/consumed-build.json'}|{f'runtime/{kind}-{n}.json' for n in (4,8,16) for kind in ('normal','warmup','after-level')}
        require(set(r['files'])==expected,'H3_EVIDENCE_INVENTORY')
        for name,pin in r['files'].items():
            path=root/name;require(path.resolve().is_relative_to(root.resolve()) and not path.is_symlink() and sha(path.read_bytes())==pin,'H3_EVIDENCE_CHANGED')
        require(json.loads((root/'execution-resources.json').read_bytes())==r['resources'],'H3_CLEANUP_EVIDENCE')
        for clients,level,warmup in zip((4,8,16),r['levels'],r['warmups']):
            require(json.loads((root/f'runtime/normal-{clients}.json').read_bytes())==level and json.loads((root/f'runtime/warmup-{clients}.json').read_bytes())==warmup,'H3_RAW_RESULT_CHANGED')
        require(json.loads((root/'runtime/scenarios.json').read_bytes())==r['scenarios'] and json.loads((root/'runtime/observations.json').read_bytes())['scenarios']==r['h2Fencing'],'H3_SCENARIO_EVIDENCE_CHANGED')
        require(json.loads((root/'runtime/initial-history.json').read_bytes())==json.loads((root/'database/migration-history.json').read_bytes()),'H3_MIGRATION_HISTORY_CHANGED')
        require(json.loads((root/'database/database-identity.json').read_bytes())['systemIdentifier']==r['database']['systemIdentifier'],'H3_DATABASE_IDENTITY')
        require(set(json.loads((root/'runtime/query-plans.json').read_bytes()))=={'tenantReport','documentMetadata','queueCandidate'},'H3_MISSING_QUERY_PLANS')
        state=json.loads((root/'database/database-state.json').read_bytes());audits={row['id']:row for row in state['acp_audit']}
        for table,data in state.items():
            if table.startswith('d_') and not table.endswith('_audit'):
                require(len({(x['tenant'],x['resource'],x['idempotency_key']) for x in data})==len(data),'H3_DUPLICATE_DOCUMENT_KEY')
                for row in data:
                    raw=bytes.fromhex(row['content'][2:]);require(len(raw)==row['size'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'H3_STORED_DOCUMENT_BYTES')
                    links=[a for a in state[table+'_audit'] if a['document']==row['id'] and audits[a['audit_id']]['operation']=='PERM-DOC-UPLOAD']
                    require(len(links)==1 and links[0]['sha256']==row['sha256'],'H3_DOCUMENT_AUDIT_COUNT')
                    audit=audits[links[0]['audit_id']];require(audit['tenant']==row['tenant'] and audit['resource']==row['resource'] and audit['subject']==row['principal'],'H3_DOCUMENT_AUDIT_OWNER')
            if table.startswith('j_') and table.endswith('_result'):
                require(len({row['queue'] for row in data})==len(data) and len({row['audit_id'] for row in data})==len(data),'H3_DUPLICATE_JOB_EFFECT')
                require(all(row['audit_id'] in audits and audits[row['audit_id']]['operation']=='JOB-INTEGRITY' and audits[row['audit_id']]['tenant']==row['tenant'] for row in data),'H3_JOB_AUDIT_LINK')
        session.check_fresh()
        return [*rows,*[{'id':'h3:'+str(level['clients']),'kind':'CANDIDATE_RUNTIME_OBSERVATION','result':'PASS','obligation':None,'origins':[{'application':session.request.application,'id':i,'revision':1} for i in ('CREATE-CASE','REPORT-CASES','DOC-ATTACHMENTS','JOB-INTEGRITY')],'artifacts':['backend/src/main/java/acp/api/IntakeController.java','backend/src/main/java/acp/api/DocumentController.java','backend/src/main/java/acp/api/IntegrityWorker.java'],'reasons':[],'observation':{'executionSHA256':self.pin,'scope':'QUALIFICATION_ONLY','clients':level['clients'],'capacity':'ENGINEERING_OBSERVATION_ONLY','G22':'NOT_SATISFIED'}} for level in r['levels']]]
