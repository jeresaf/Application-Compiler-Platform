"""Independent host expectations; generated tests execute real PostgreSQL boundaries.

Test-only variants exercise lowering restrictions, not new approved snapshots.
"""
import copy
import json
from phase6_reference_tests import source as old_source, symbol


def source(domain):
    s=old_source(domain);s=s[:s.index('    @Test void exactEffects')]
    s=s.replace('class ExplicitExecutionTest','class InvocationCoreTest')
    s=s.replace('ObjectMapper mapper=new ObjectMapper();','''ObjectMapper mapper=new ObjectMapper();
    InvocationCore core; Invocations inv;
    TestTime time=new TestTime();
    static final class TestTime implements InvocationCore.Time {
        volatile java.math.BigInteger fixed;
        java.util.Deque<java.math.BigInteger> scripted=new java.util.ArrayDeque<>();
        java.util.List<Long> sleeps=new java.util.ArrayList<>();
        public java.math.BigInteger now() {if(!scripted.isEmpty())return scripted.removeFirst();return fixed==null?new InvocationCore.SystemTime().now():fixed;}
        public void sleep(long seconds) {sleeps.add(seconds);}
    }''')
    s=s.replace('tasks=new TypedTasks(store);','tasks=new TypedTasks(store);core=new InvocationCore(jdbc,model,new DataSourceTransactionManager(ds),time);inv=new Invocations(tasks,store,core);')
    q=json.dumps;v=lambda x:symbol(x,'v');t=lambda x:symbol(x,'T');f=lambda x:symbol(x,'f');e=lambda x:symbol(x,'e')
    payment=domain=='payment';root='ENT-PAYMENT' if payment else 'CASE';rootid='FLD-PAYMENT-ID' if payment else 'CASE-ID'
    cmd='CMD-RECORD' if payment else 'CMD-REVIEW'; events=1 if payment else 3
    summary=f('FLD-TASK-SUMMARY');table=e(root)
    opinput=f'''{t('OPERATION-INPUT')}.read(mapper.createObjectNode().put("OPERATION-TEXT","new"))'''
    call=f'''inv.{v('UC-TASK')}(0,invocation("new"),"key",identity("tenant-one","fixture:operator"))'''
    direct=f'''tasks.{v(cmd)}(new {t(root)}Id("fixture-resource"),0,input,jwt)'''
    meta=f'''new InvocationCore.Call({q(cmd)},3,"IDEM-OPERATION",2,"fixture-resource",InvocationCore.typed("{{\\"kind\\":\\"String\\"}}","concurrent"),InvocationCore.typed("{{\\"kind\\":\\"Value\\",\\"definition\\":{{\\"id\\":\\"OPERATION-INPUT\\",\\"revision\\":1}}}}",input),86400)'''
    from deterministic_invocation import typed_input_digest
    from deterministic_approval import approved_snapshot
    by={n['id']:n for n in approved_snapshot(domain)['content']['nodes']}
    input_digest=typed_input_digest({'kind':'Value','definition':by[cmd]['data']['input']},{'OPERATION-TEXT':'new'},by).removeprefix('sha256:')
    tests=f'''
    @Test void exactApprovedInvocationReplayConflictAndAtomicResults() throws Exception {{
        var first={call};time.fixed=new InvocationCore.SystemTime().now(); var again={call};assertEquals(first,again);
        assertEquals({q(input_digest)},java.util.HexFormat.of().formatHex(jdbc.queryForObject("SELECT input_digest FROM acp_idempotency LIMIT 1",byte[].class)));
        var chargedBeforeConflict=jdbc.queryForObject("SELECT sum(tokens) FROM acp_rate",java.math.BigDecimal.class);
        assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
        assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_idempotency WHERE status='COMMITTED_RESULT' AND result IS NOT NULL AND commit_xid IS NOT NULL",Integer.class));
        var conflict=assertThrows(InvocationCore.Outcome.class,()->inv.{v('UC-TASK')}(0,invocation("different"),"key",identity("tenant-one","fixture:operator")));
        assertEquals("IDEMPOTENCY_CONFLICT",conflict.getMessage());
        // Replay remains charged; two successes and one conflict consume three.
        assertEquals(0,chargedBeforeConflict.subtract(new java.math.BigDecimal("60000000000")).compareTo(jdbc.queryForObject("SELECT sum(tokens) FROM acp_rate",java.math.BigDecimal.class)));
        time.fixed=jdbc.queryForObject("SELECT (extract(epoch FROM pg_xact_commit_timestamp(commit_xid::xid))*1000000000)::numeric FROM acp_idempotency LIMIT 1",java.math.BigDecimal.class).toBigIntegerExact().add(java.math.BigInteger.valueOf(86400).multiply(InvocationCore.BILLION));
        // Exact deadline expires the result, so the canonical terminal workflow
        // now fails instead of replaying. No second event/domain write commits.
        assertThrows(SemanticFailure.class,()->{call.replace("(0,", "("+str(events)+",")});
        assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
    @Test void unauthorizedRequestsCreateNoRateOrIdempotencyState() throws Exception {{
        assertThrows(org.springframework.security.access.AccessDeniedException.class,()->inv.{v('UC-TASK')}(0,invocation("secret"),"key",identity("tenant-one","outsider")));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_rate",Integer.class));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_idempotency",Integer.class));
    }}
    @Test void exactRationalRateBoundariesAndConcurrentCapacity() throws Exception {{
        for(int i=0;i<10;i++)assertTrue(core.token("test",1,"tenant","actor",100,60,10,java.math.BigInteger.ZERO));
        assertFalse(core.token("test",1,"tenant","actor",100,60,10,java.math.BigInteger.ZERO));
        assertFalse(core.token("test",1,"tenant","actor",100,60,10,java.math.BigInteger.valueOf(599999999)));
        assertTrue(core.token("test",1,"tenant","actor",100,60,10,java.math.BigInteger.valueOf(600000000)));
        assertFalse(core.token("test",1,"tenant","actor",100,60,10,java.math.BigInteger.valueOf(600000000)));
        try(var pool=java.util.concurrent.Executors.newFixedThreadPool(16)) {{
            var futures=new java.util.ArrayList<java.util.concurrent.Future<Boolean>>();
            for(int i=0;i<32;i++)futures.add(pool.submit(()->core.token("parallel",1,"tenant","actor",100,60,10,java.math.BigInteger.ZERO)));
            int admitted=0;for(var future:futures)if(future.get(10,java.util.concurrent.TimeUnit.SECONDS))admitted++;assertEquals(10,admitted);
            futures.clear();for(int i=0;i<16;i++)futures.add(pool.submit(()->core.token("parallel",1,"tenant","actor",100,60,10,java.math.BigInteger.valueOf(600000000))));
            admitted=0;for(var future:futures)if(future.get(10,java.util.concurrent.TimeUnit.SECONDS))admitted++;assertEquals(1,admitted);
        }}
        assertThrows(InvocationCore.Outcome.class,()->core.token("test",1,"tenant","actor",100,60,10,java.math.BigInteger.ZERO));
    }}
    @Test void sameKeyInFlightReturnsImmediatelyAndCommittedReplaySurvivesRestart() throws Exception {{
        var input={opinput};var jwt=identity("tenant-one","fixture:operator");var call={meta};
        var ready=new java.util.concurrent.CountDownLatch(1);var release=new java.util.concurrent.CountDownLatch(1);
        try(var pool=java.util.concurrent.Executors.newFixedThreadPool(2)) {{
            var original=pool.submit(()->core.invoke(java.util.List.of(call),null,jwt,()->{{ var result={direct}; ready.countDown();try{{assertTrue(release.await(10,java.util.concurrent.TimeUnit.SECONDS));}}catch(InterruptedException ex){{throw new RuntimeException(ex);}}return result;}}));
            assertTrue(ready.await(10,java.util.concurrent.TimeUnit.SECONDS));
            var duplicate=pool.submit(()->assertThrows(InvocationCore.Outcome.class,()->core.invoke(java.util.List.of(call),null,jwt,()->{direct})).getMessage());
            try {{
                assertEquals("IN_PROGRESS",duplicate.get(2,java.util.concurrent.TimeUnit.SECONDS));
                var different=new InvocationCore.Call(call.operation(),call.revision(),call.policy(),call.policyRevision(),call.resource(),call.typedKey(),call.typedInput().replace("new","different"),call.windowSeconds());
                var conflicting=pool.submit(()->assertThrows(InvocationCore.Outcome.class,()->core.invoke(java.util.List.of(different),null,jwt,()->{direct})).getMessage());
                assertEquals("IDEMPOTENCY_CONFLICT",conflicting.get(2,java.util.concurrent.TimeUnit.SECONDS));
            }}finally{{release.countDown();}}
            var result=original.get(10,java.util.concurrent.TimeUnit.SECONDS);
            var restarted=new InvocationCore(jdbc,new TargetModel(),new DataSourceTransactionManager(jdbc.getDataSource()),time);
            var replay=restarted.invoke(java.util.List.of(call),null,jwt,()->{direct});assertEquals(result,replay);
            assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
        }}
    }}
    @Test void rateAndReplayShareOneInvocationInstantAtWindowEdge() throws Exception {{
        var input={opinput};var jwt=identity("tenant-one","fixture:operator");var call={meta};
        var original=core.invoke(java.util.List.of(call),null,jwt,()->{direct});
        var deadline=jdbc.queryForObject("SELECT (extract(epoch FROM pg_xact_commit_timestamp(commit_xid::xid))*1000000000)::numeric FROM acp_idempotency",java.math.BigDecimal.class).toBigIntegerExact().add(InvocationCore.BILLION.multiply(java.math.BigInteger.valueOf(86400)));
        time.scripted.add(deadline.subtract(java.math.BigInteger.ONE));time.scripted.add(deadline.add(java.math.BigInteger.ONE));
        // Admission begins inside the replay interval. A later clock read must
        // not reinterpret that logical invocation as an expired reservation.
        assertEquals(original,core.invoke(java.util.List.of(call),null,jwt,()->{direct}));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
    @Test void actualWorkflowFailureRollsBackAndStopsLaterSteps() throws Exception {{
        jdbc.update({q('UPDATE '+table+" SET acp_state='STATE-ARCHIVED'")});
        var failure=assertThrows(SemanticFailure.class,()->{call});
        assertEquals("FAIL-BUSINESS",failure.envelope().failureId());assertEquals(1,failure.envelope().failureRevision());
        assertEquals({q(cmd)},failure.envelope().operationId());assertEquals("PRE_STATE",failure.stage());
        assertFalse(failure.envelope().retryable());
        assertEquals("old",ExecutionStore.text(jdbc.queryForObject({q('SELECT '+summary+' FROM '+table)},byte[].class)));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_idempotency",Integer.class));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_rate",Integer.class)); // later steps never charged
        String envelope=mapper.writeValueAsString(failure.envelope());assertFalse(envelope.contains("old"));assertFalse(envelope.contains("fixture-resource"));assertFalse(envelope.contains("stack"));
    }}
    @Test void actualProviderFaultBindingRollbackAndRetryTiming() throws Exception {{
        // The real server raises an exact portable dependency fault at an
        // actually reached write. No message parsing or speculative future fault.
        jdbc.execute("CREATE FUNCTION invocation_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION USING ERRCODE='08006', MESSAGE='private injected data'; END $$");
        jdbc.execute({q('CREATE TRIGGER invocation_fault BEFORE UPDATE ON '+table+' FOR EACH ROW EXECUTE FUNCTION invocation_fault()')});
        var input={opinput};var jwt=identity("tenant-one","fixture:operator");var call={meta};
        var failure=assertThrows(SemanticFailure.class,()->core.invoke(java.util.List.of(call),"RETRY-TASK",jwt,()->{direct}));
        assertEquals("FAIL-TRANSIENT",failure.envelope().failureId());assertEquals("INFRASTRUCTURE",failure.stage());assertEquals(java.util.List.of(1L,2L),time.sleeps);
        assertEquals("old",ExecutionStore.text(jdbc.queryForObject({q('SELECT '+summary+' FROM '+table)},byte[].class)));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_idempotency",Integer.class));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_rate",Integer.class)); // retries retain one logical invocation
        assertNull(InvocationCore.portable(new RuntimeException(new java.sql.SQLException("hidden","99999"))));
        assertEquals("SERIALIZATION_CONFLICT",InvocationCore.portable(new RuntimeException(new java.sql.SQLException("hidden","40001"))));
        jdbc.execute("DROP TRIGGER invocation_fault ON {table}");
        jdbc.execute("CREATE OR REPLACE FUNCTION invocation_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION USING ERRCODE='40001', MESSAGE='not dependency'; END $$");
        jdbc.execute({q('CREATE TRIGGER invocation_fault BEFORE UPDATE ON '+table+' FOR EACH ROW EXECUTE FUNCTION invocation_fault()')});
        time.sleeps.clear();assertThrows(RuntimeException.class,()->core.invoke(java.util.List.of(call),"RETRY-TASK",jwt,()->{direct}));assertTrue(time.sleeps.isEmpty());
    }}
'''
    # Clone exact persisted columns inside a real transaction.
    from deterministic_approval import approved_snapshot
    by={n['id']:n for n in approved_snapshot(domain)['content']['nodes']}
    fields=sorted((n for n in by.values() if n['kind']=='Field' and n['data']['owner']['id']==root),key=lambda n:n['id'])
    columns=[];values=[]
    for field in fields:
        columns.append(f(field['id']));values.append('?' if field['id']==rootid else f(field['id']))
        if field['data']['optional'] and field['data']['type']['kind']=='Nullable':columns.append(symbol(field['id'],'present'));values.append(symbol(field['id'],'present'))
    clone='INSERT INTO '+table+'('+','.join(columns)+') SELECT '+','.join(values)+' FROM '+table+' WHERE '+f(rootid)+"='fixture-resource'"
    relation=('REL-MEMBER-PAYMENT' if payment else None)
    relationInsert=(f'jdbc.update("INSERT INTO {symbol(relation,"r")}(tenant,source_id,target_id) VALUES(?,?,?)",ExecutionStore.bytes("tenant-one"),ExecutionStore.bytes("fixture:operator"),ExecutionStore.bytes(id));' if payment else '')
    tests+=f'''
    void insert(String id) {{tx.execute(status -> {{jdbc.update({q(clone)},ExecutionStore.bytes(id));{relationInsert}return null;}});}}
    @Test void unicodeOrderPaginationIsStableAndOffsetPagesHaveNoSnapshotClaim() throws Exception {{
        var ids=java.util.List.of("A","a","Z","🦋","\\uE000","𐀀");for(String id:ids)insert(id);
        var filter={t('QUERY-INPUT')}.read(mapper.createObjectNode().put("QUERY-TEXT",""));var jwt=identity("tenant-one","fixture:operator");
        var rows=tx.execute(status->tasks.{v('QUERY-TASKS')}(filter,0,100,jwt));
        assertEquals(java.util.List.of("A","Z","a","fixture-resource","\\uE000","𐀀","🦋"),rows.stream().map(ExecutionStore.Completion::resourceId).toList());
        var page=tx.execute(status->tasks.{v('QUERY-TASKS')}(filter,2,2,jwt));assertEquals(page,tx.execute(status->tasks.{v('QUERY-TASKS')}(filter,2,2,jwt)));
        insert("B");var after=tx.execute(status->tasks.{v('QUERY-TASKS')}(filter,2,2,jwt));assertEquals(java.util.List.of("Z","a"),after.stream().map(ExecutionStore.Completion::resourceId).toList());
    }}
'''
    tests+=f'''
    @Test void stagedPredicateFailuresAndBoundInvariantRollback() throws Exception {{
        var input={opinput};var jwt=identity("tenant-one","fixture:operator");
        var pre=new PreFailureTasks(store);var post=new PostFailureTasks(store);
        var first=assertThrows(SemanticFailure.class,()->tx.execute(status->pre.{v(cmd)}(new {t(root)}Id("fixture-resource"),0,input,jwt)));
        assertEquals("PRE_STATE",first.stage());
        var second=assertThrows(SemanticFailure.class,()->tx.execute(status->post.{v(cmd)}(new {t(root)}Id("fixture-resource"),0,input,jwt)));
        assertEquals("POST_ASSIGNMENT",second.stage());assertEquals("FAIL-BUSINESS",second.envelope().failureId());
        assertEquals("old",ExecutionStore.text(jdbc.queryForObject({q('SELECT '+summary+' FROM '+table)},byte[].class)));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
    @Test void orderedKeyPrecedenceAndDescendingIdentityAreCompiledExactly() throws Exception {{
        insert("A");insert("a");insert("🦋");
        jdbc.update({q('UPDATE '+table+' SET '+summary+"='old'")});
        var ordered=new OrderedTasks(store);var filter={t('QUERY-INPUT')}.read(mapper.createObjectNode().put("QUERY-TEXT",""));
        var rows=tx.execute(status->ordered.{v('QUERY-TASKS')}(filter,0,100,identity("tenant-one","fixture:operator")));
        assertEquals(java.util.List.of("🦋","fixture-resource","a","A"),rows.stream().map(ExecutionStore.Completion::resourceId).toList());
    }}
    @Test void inputNormalizationBindsSemanticValuesAndNominalIdentity() throws Exception {{
        var a={t('INPUT-TASK')}.read(mapper.readTree("{{\\"INPUT-TASK-TEXT\\":\\"new\\",\\"INPUT-TASK-RESOURCE\\":\\"fixture-resource\\"}}"));
        var b=invocation("new");
        assertEquals(InvocationCore.typed("{{\\"kind\\":\\"Value\\"}}",a),InvocationCore.typed("{{\\"kind\\":\\"Value\\"}}",b));
        assertNotEquals(InvocationCore.typed("{{\\"kind\\":\\"Value\\"}}",a),InvocationCore.typed("{{\\"kind\\":\\"Named\\"}}",b));
    }}
    @Test void durableClaimSurvivesLostProcessAndRecoversOnlyFromDatabaseProof() throws Exception {{
        var input={opinput};var jwt=identity("tenant-one","fixture:operator");var call={meta};
        var reached=new java.util.concurrent.CountDownLatch(1);var terminate=new java.util.concurrent.CountDownLatch(1);var pid=new java.util.concurrent.atomic.AtomicInteger();
        try(var pool=java.util.concurrent.Executors.newSingleThreadExecutor()) {{
            var dying=pool.submit(()->core.invoke(java.util.List.of(call),null,jwt,()->{{var result={direct};pid.set(jdbc.queryForObject("SELECT pg_backend_pid()",Integer.class));reached.countDown();try{{terminate.await();}}catch(InterruptedException ex){{throw new RuntimeException(ex);}}jdbc.execute("SELECT 1");return result;}}));
            assertTrue(reached.await(10,java.util.concurrent.TimeUnit.SECONDS));
            assertTrue(jdbc.queryForObject("SELECT pg_terminate_backend(?)",Boolean.class,pid.get()));terminate.countDown();
            assertThrows(java.util.concurrent.ExecutionException.class,()->dying.get(10,java.util.concurrent.TimeUnit.SECONDS));
        }}
        assertEquals("old",ExecutionStore.text(jdbc.queryForObject({q('SELECT '+summary+' FROM '+table)},byte[].class)));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
        var restarted=new InvocationCore(jdbc,new TargetModel(),new DataSourceTransactionManager(jdbc.getDataSource()),time);
        var recovered=restarted.invoke(java.util.List.of(call),null,jwt,()->{direct});assertNotNull(recovered);
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
        // No attempt/commit fact is deliberate uncertainty, with no time lease.
        jdbc.update("UPDATE acp_idempotency SET status='INDETERMINATE',result=NULL,commit_xid=NULL,attempt_xid=NULL");
        time.fixed=new InvocationCore.SystemTime().now().add(InvocationCore.BILLION.multiply(java.math.BigInteger.valueOf(999999)));
        var uncertain=assertThrows(InvocationCore.Outcome.class,()->restarted.invoke(java.util.List.of(call),null,jwt,()->{direct}));assertEquals("IN_PROGRESS",uncertain.getMessage());
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
'''
    if payment:
        tests+=f'''
    @Test void exactInvariantBindingProducesFailureBeforeAnySqlWrite() throws Exception {{
        var variant=new InvariantFailureTasks(store);var input={opinput};var jwt=identity("tenant-one","fixture:operator");
        var failure=assertThrows(SemanticFailure.class,()->tx.execute(status->variant.{v(cmd)}(new {t(root)}Id("fixture-resource"),0,input,jwt)));
        assertEquals("INVARIANT",failure.stage());assertEquals("FAIL-BUSINESS",failure.envelope().failureId());
        assertEquals("12.50",jdbc.queryForObject({q('SELECT '+f('FLD-AMOUNT')+'::text FROM '+table)},String.class));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
'''
    else:
        tests+=f'''
    @Test void absenceNullAndValuePlacementRemainDistinctFromDirection() throws Exception {{
        insert("absent");insert("null");insert("value");
        jdbc.update({q('UPDATE '+table+' SET '+symbol('FLD-NOTE','present')+'=false,'+f('FLD-NOTE')+"=NULL WHERE "+f(rootid)+"='absent'")});
        jdbc.update({q('UPDATE '+table+' SET '+symbol('FLD-NOTE','present')+'=true,'+f('FLD-NOTE')+"=NULL WHERE "+f(rootid)+"='null'")});
        var ordered=new NullableOrderTasks(store);var filter={t('QUERY-INPUT')}.read(mapper.createObjectNode().put("QUERY-TEXT",""));
        var rows=tx.execute(status->ordered.{v('QUERY-TASKS')}(filter,0,100,identity("tenant-one","fixture:operator")));
        assertEquals(java.util.List.of("absent","fixture-resource","value","null"),rows.stream().map(ExecutionStore.Completion::resourceId).toList());
    }}
'''
    if not payment:
        tests+=f'''
    @Test void eachDeclaredCaseWorkflowBindingProducesItsExactOperationIdentity() throws Exception {{
        var input={opinput};var jwt=identity("tenant-one","fixture:operator");
        var approve=assertThrows(SemanticFailure.class,()->tx.execute(status->tasks.{v('CMD-APPROVE')}(new {t(root)}Id("fixture-resource"),0,input,jwt)));
        assertEquals("CMD-APPROVE",approve.envelope().operationId());assertEquals("FAIL-BUSINESS",approve.envelope().failureId());
        var archive=assertThrows(SemanticFailure.class,()->tx.execute(status->tasks.{v('CMD-ARCHIVE')}(new {t(root)}Id("fixture-resource"),0,input,jwt)));
        assertEquals("CMD-ARCHIVE",archive.envelope().operationId());assertEquals("FAIL-BUSINESS",archive.envelope().failureId());
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
'''
    return s+tests+'\n}\n'


def variants(domain,nodes):
    from execution_codegen import ExecutionGenerator
    def build(label,mutate):
        changed=copy.deepcopy(nodes);mutate(changed)
        text=ExecutionGenerator(changed,'0.3.0').source()['backend/src/main/java/acp/generated/TypedTasks.java']
        return ('backend/src/test/java/acp/generated/'+label+'.java',text.replace('class TypedTasks','class '+label).replace('public TypedTasks(','public '+label+'('))
    def predicate(stage):
        def mutate(ns):
            for n in ns:
                if n['kind']=='Command':
                    d=n['data'];condition={'tag':'binary','op':'eq','left':{'tag':'postField','field':d['assignments'][0]['field']},'right':{'tag':'input','scope':'OPERATION','field':d['assignments'][0]['value']['field']}} if stage=='POST_ASSIGNMENT' else {'tag':'literal','type':{'kind':'Boolean'},'value':True}
                    d['failureBindings'].insert(1,{'failure':d['failureBindings'][0]['failure'],'stage':stage,'trigger':{'kind':'PREDICATE','condition':condition}})
        return mutate
    def ordered(ns):
        by={n['id']:n for n in ns}
        for n in ns:
            if n['kind']=='Query':
                n['data']['orderBy'][0]['direction']='DESC'
                summary=by['FLD-TASK-SUMMARY'];n['data']['orderBy'].insert(0,{'field':{'id':summary['id'],'revision':summary['revision']},'direction':'ASC'})
    result=dict([build('PreFailureTasks',predicate('PRE_STATE')),build('PostFailureTasks',predicate('POST_ASSIGNMENT')),build('OrderedTasks',ordered)])
    if domain=='payment':
        def invariant(ns):
            by={n['id']:n for n in ns};cmd=by['CMD-RECORD']['data'];amount=by['FLD-AMOUNT'];field={'id':amount['id'],'revision':amount['revision']}
            cmd['assignments'].append({'field':field,'resource':cmd['resource'],'value':{'tag':'literal','type':amount['data']['type'],'value':'-1'}})
            cmd['writeFields'].append(field)
            cmd['failureBindings'].insert(1,{'failure':cmd['failureBindings'][0]['failure'],'stage':'INVARIANT','trigger':{'kind':'INVARIANT_FAILURE','invariant':cmd['invariants'][0]}})
        result.update([build('InvariantFailureTasks',invariant)])
    else:
        def nullorder(ns):
            by={n['id']:n for n in ns};note=by['FLD-NOTE'];query=by['QUERY-TASKS']['data']
            query['orderBy'].insert(0,{'field':{'id':note['id'],'revision':note['revision']},'direction':'DESC','nulls':'LAST','absent':'FIRST'})
        result.update([build('NullableOrderTasks',nullorder)])
    return result


def http_source(domain):
    from phase6_reference_tests import http_source as previous
    s=previous(domain).replace('TypedHttpTest','InvocationHttpTest')
    s=s.replace('properties={', 'properties={"acp.runtime.mode=development", "acp.jobs.JOB-TASK.revision-3.credential-handle=test-only-handle", "acp.runtime.poll-enabled=false",')
    s=s.replace('@TestConfiguration static class Identity {', '@TestConfiguration static class Identity { @Bean acp.infrastructure.JobRuntime.PrincipalPort jobPrincipal() {return (id,rev,handle)->referenceOnlyDecoder().decode("reference-only-token");}')
    s=s.replace('String input="{\\"expectedVersion\\":0,', 'String input="{\\"idempotencyKey\\":\\"http-key\\",\\"expectedVersion\\":0,')
    path='/api/'+symbol('UC-TASK','op');q=json.dumps
    root='ENT-PAYMENT' if domain=='payment' else 'CASE'
    tests=f'''
    @Test void exactSemanticFailureEnvelopeUsesVersionedHttpProfile() throws Exception {{
        jdbc.update({q('UPDATE '+symbol(root,'e')+" SET acp_state='STATE-ARCHIVED'")});
        var body=new com.fasterxml.jackson.databind.ObjectMapper().createObjectNode().put("expectedVersion",0).put("idempotencyKey","failure-key");
        body.set("input",new com.fasterxml.jackson.databind.ObjectMapper().createObjectNode().put("INPUT-TASK-TEXT","raw-private-value").put("INPUT-TASK-RESOURCE","fixture-resource"));
        var response=send({q(path)},body.toString(),true);assertEquals(422,response.statusCode(),response.body());
        assertEquals("1.0.0",response.headers().firstValue("ACP-Failure-Profile").orElseThrow());
        var failure=new com.fasterxml.jackson.databind.ObjectMapper().readTree(response.body());assertEquals("FAIL-BUSINESS",failure.path("failureId").asText());assertEquals(1,failure.path("failureRevision").asInt());assertEquals(3,failure.path("operationRevision").asInt());
        assertFalse(failure.path("retryable").asBoolean());assertFalse(failure.path("correlationId").asText().isBlank());assertEquals(8,failure.size());
        assertFalse(response.body().contains("raw-private-value"));assertFalse(response.body().contains("fixture-resource"));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
    @Test void typedInputPropertyOrderAndUnicodeKeyReplayExactly() throws Exception {{
        var mapper=new com.fasterxml.jackson.databind.ObjectMapper();var body=mapper.createObjectNode().put("expectedVersion",0).put("idempotencyKey","a"+(char)0+"🦋");
        body.set("input",mapper.createObjectNode().put("INPUT-TASK-RESOURCE","fixture-resource").put("INPUT-TASK-TEXT","new"));
        var invalid=body.deepCopy().put("idempotencyKey",123);assertEquals(422,send({q(path)},invalid.toString(),true).statusCode());
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_idempotency",Integer.class));
        var first=send({q(path)},body.toString(),true);assertEquals(200,first.statusCode(),first.body());
        body.set("input",mapper.createObjectNode().put("INPUT-TASK-TEXT","new").put("INPUT-TASK-RESOURCE","fixture-resource"));
        var replay=send({q(path)},body.toString(),true);assertEquals(200,replay.statusCode(),replay.body());assertEquals(first.body(),replay.body());
        body.set("input",mapper.createObjectNode().put("INPUT-TASK-TEXT","different").put("INPUT-TASK-RESOURCE","fixture-resource"));
        assertEquals(409,send({q(path)},body.toString(),true).statusCode());
        assertEquals({1 if domain=='payment' else 3},jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
        body.set("input",mapper.createObjectNode().put("INPUT-TASK-TEXT","new").put("INPUT-TASK-RESOURCE","fixture-resource"));
        jdbc.update("UPDATE acp_idempotency SET status='INDETERMINATE',result=NULL,commit_xid=NULL,commit_ns=NULL,attempt_xid=NULL");
        assertEquals(202,send({q(path)},body.toString(),true).statusCode());
    }}
'''
    return s[:s.rindex('}')]+tests+s[s.rindex('}'):]
