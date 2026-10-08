"""Independent generated PostgreSQL delivery, scheduler and pinned-rule checks."""
import json
from invocation_reference_tests import source as invocation_source
from phase6_reference_tests import symbol

def source(domain):
    s=invocation_source(domain);s=s[:s.index('    @Test void exactApprovedInvocation')].replace('class InvocationCoreTest','class DeliveryJobTest')
    s=s.replace('JdbcTemplate jdbc;','DriverManagerDataSource ds;TargetModel model;JdbcTemplate jdbc;').replace('var ds=new DriverManagerDataSource','ds=new DriverManagerDataSource').replace('var model=new TargetModel()','model=new TargetModel()')
    root='ENT-PAYMENT' if domain=='payment' else 'CASE';agg='AGG-ENT-PAYMENT' if domain=='payment' else 'AGG-CASE'
    events=1 if domain=='payment' else 3;q=json.dumps;v=lambda x:symbol(x,'v');e=lambda x:symbol(x,'e')
    invoke=f'inv.{v("UC-TASK")}(0,invocation("new"),"delivery-key",identity("tenant-one","fixture:operator"))'
    return s+f'''
    java.math.BigInteger commitInstant() {{return jdbc.queryForObject("SELECT (extract(epoch FROM pg_xact_commit_timestamp(commit_xid::xid))*1000000000)::numeric FROM acp_outbox LIMIT 1",java.math.BigDecimal.class).toBigIntegerExact();}}
    DeliveryRuntime delivery(DeliveryRuntime.Transport transport) {{return new DeliveryRuntime(jdbc,new DataSourceTransactionManager(ds),model,time,transport);}}
    DeliveryRuntime.Result poll(DeliveryRuntime runtime) {{return runtime.poll("tenant-one",{q(agg)},"fixture-resource");}}
    JobRuntime jobs(JobRuntime.Invocation action) {{return new JobRuntime(jdbc,new DataSourceTransactionManager(ds),model,time,(id,rev,handle)->identity("tenant-one","fixture:operator"),java.util.Map.of("JOB-TASK@3","opaque-test-handle"),action);}}
    java.math.BigInteger scheduled() {{return java.math.BigInteger.valueOf(java.time.Instant.parse("2026-10-08T06:00:00Z").getEpochSecond()).multiply(InvocationCore.BILLION);}}
    @Test void pinnedRulesNormalGapOverlapAndRejection() {{
        var schedule=new PinnedSchedule();
        assertEquals(java.time.Instant.parse("2026-10-08T06:00:00Z"),schedule.occurrence(java.time.LocalDateTime.parse("2026-10-08T09:00:00"),"Africa/Nairobi","SKIP","EARLIER"));
        assertNull(schedule.occurrence(java.time.LocalDateTime.parse("2026-03-08T02:30:00"),"America/New_York","SKIP","EARLIER"));
        assertEquals(java.time.Instant.parse("2026-11-01T05:30:00Z"),schedule.occurrence(java.time.LocalDateTime.parse("2026-11-01T01:30:00"),"America/New_York","SKIP","EARLIER"));
        assertEquals(java.time.Instant.parse("2026-11-01T06:30:00Z"),schedule.occurrence(java.time.LocalDateTime.parse("2026-11-01T01:30:00"),"America/New_York","SKIP","LATER"));
        assertThrows(IllegalArgumentException.class,()->schedule.occurrence(java.time.LocalDateTime.parse("2026-11-01T01:30:00"),"America/New_York","SKIP","REJECT"));
        assertThrows(IllegalArgumentException.class,()->schedule.occurrence(java.time.LocalDateTime.parse("2026-03-08T02:30:00"),"America/New_York","REJECT","EARLIER"));
        assertThrows(IllegalArgumentException.class,()->schedule.occurrence(java.time.LocalDateTime.parse("2102-01-01T09:00:00"),"Africa/Nairobi","SKIP","EARLIER"));
    }}
    @Test void committedOccurrencesHaveExactIdentityAndOrderedPositions() throws Exception {{
        {invoke};assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_outbox WHERE commit_xid IS NOT NULL AND aggregate_id IS NOT NULL AND operation_revision=3 AND event_revision=2 AND delivery_status='PENDING'",Integer.class));
        assertEquals(1,jdbc.queryForObject("SELECT count(DISTINCT commit_sequence) FROM acp_outbox",Integer.class));
        assertEquals({events},jdbc.queryForObject("SELECT count(DISTINCT step_ordinal) FROM acp_outbox",Integer.class));
        assertTrue(jdbc.queryForObject("SELECT bool_and(emission_ordinal=0) FROM acp_outbox",Boolean.class));
        assertTrue(jdbc.queryForObject("SELECT bool_and(length(id)=64) FROM acp_outbox",Boolean.class));
        time.fixed=commitInstant();var runtime=delivery(o->true);
        assertEquals(DeliveryRuntime.Result.ACKNOWLEDGED,poll(runtime));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_delivery_attempt WHERE result='ACK' AND acknowledged",Integer.class));
    }}
    @Test void firstFailureThenAcknowledgementAndBarrier() throws Exception {{
        {invoke};time.fixed=commitInstant();var sent=new java.util.ArrayList<String>();var counter=new java.util.concurrent.atomic.AtomicInteger();
        var runtime=delivery(o->{{sent.add(o.id());return counter.incrementAndGet()>1;}});
        assertEquals(DeliveryRuntime.Result.RETRY,poll(runtime));assertEquals(DeliveryRuntime.Result.ACKNOWLEDGED,poll(runtime));assertEquals(sent.get(0),sent.get(1));
        assertEquals(2,jdbc.queryForObject("SELECT count(*) FROM acp_delivery_attempt",Integer.class));
        assertEquals("NO_ACK",jdbc.queryForObject("SELECT result FROM acp_delivery_attempt WHERE attempt=1",String.class));
    }}
    @Test void exactDeadlineAndLateAcknowledgementCannotBecomeSuccess() throws Exception {{
        {invoke};var commit=commitInstant();time.fixed=commit;
        var runtime=delivery(o->{{time.fixed=commit.add(java.math.BigInteger.valueOf(3600).multiply(InvocationCore.BILLION));return true;}});
        assertEquals(DeliveryRuntime.Result.UNSATISFIED,poll(runtime));assertEquals("LATE_ACK",jdbc.queryForObject("SELECT result FROM acp_delivery_attempt",String.class));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox WHERE delivery_status='ACKNOWLEDGED'",Integer.class));
    }}
    @Test void deadlineBeforeFirstAttemptNeverSends() throws Exception {{
        {invoke};time.fixed=commitInstant().add(java.math.BigInteger.valueOf(3600).multiply(InvocationCore.BILLION));
        assertEquals(DeliveryRuntime.Result.UNSATISFIED,poll(delivery(o->{{fail("must not send");return true;}})));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_delivery_attempt",Integer.class));
    }}
    @Test void crashAfterSendThenRestartRedeliversExactOccurrence() throws Exception {{
        {invoke};time.fixed=commitInstant();var sent=new java.util.ArrayList<String>();
        assertThrows(AssertionError.class,()->poll(delivery(o->{{sent.add(o.id());throw new AssertionError("simulated process loss after send");}})));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_outbox WHERE delivery_status='CLAIMED'",Integer.class));
        assertEquals(DeliveryRuntime.Result.ACKNOWLEDGED,poll(delivery(o->{{sent.add(o.id());return true;}})));assertEquals(sent.get(0),sent.get(1));
        assertEquals("UNCERTAIN",jdbc.queryForObject("SELECT result FROM acp_delivery_attempt WHERE attempt=1",String.class));
    }}
    @Test void duplicateWorkersCannotSendSameOccurrenceConcurrently() throws Exception {{
        {invoke};time.fixed=commitInstant();var entered=new java.util.concurrent.CountDownLatch(1);var release=new java.util.concurrent.CountDownLatch(1);
        var runtime=delivery(o->{{entered.countDown();try{{assertTrue(release.await(5,java.util.concurrent.TimeUnit.SECONDS));}}catch(InterruptedException x){{throw new RuntimeException(x);}}return true;}});
        try(var executor=java.util.concurrent.Executors.newSingleThreadExecutor()) {{var future=executor.submit(()->poll(runtime));assertTrue(entered.await(5,java.util.concurrent.TimeUnit.SECONDS));assertEquals(DeliveryRuntime.Result.BUSY,poll(delivery(o->true)));release.countDown();assertEquals(DeliveryRuntime.Result.ACKNOWLEDGED,future.get());}}
    }}
    @Test void repeatedFailureExpiresThenReleasesNextPosition() throws Exception {{
        {invoke};time.fixed=commitInstant();var runtime=delivery(o->false);
        for(int i=0;i<3;i++)assertEquals(DeliveryRuntime.Result.RETRY,poll(runtime));
        assertEquals(1,jdbc.queryForObject("SELECT count(DISTINCT occurrence) FROM acp_delivery_attempt",Integer.class));
        time.fixed=time.fixed.add(java.math.BigInteger.valueOf(3600).multiply(InvocationCore.BILLION));assertEquals(DeliveryRuntime.Result.UNSATISFIED,poll(runtime));
        assertEquals({events-1},jdbc.queryForObject("SELECT count(*) FROM acp_outbox WHERE delivery_status='PENDING'",Integer.class));
    }}
    @Test void rollbackProducesNoDeliverableOccurrence() throws Exception {{
        jdbc.update({q('UPDATE '+e(root)+" SET acp_state='STATE-ARCHIVED'")});assertThrows(SemanticFailure.class,()->{invoke});
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));assertEquals(DeliveryRuntime.Result.EMPTY,poll(delivery(o->true)));
    }}
    @Test void schedulerExactActivationUsesApprovedBindingsAndNormalAuthorization() throws Exception {{
        time.fixed=scheduled();var runtime=jobs(new GeneratedJobs(jdbc,inv));runtime.activate("JOB-TASK","tenant-one",time.fixed);runtime.poll("JOB-TASK","tenant-one");
        assertEquals("COMPLETED",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));
        assertEquals("Explicit scheduled fixture text",jdbc.queryForObject({q('SELECT '+symbol('FLD-TASK-SUMMARY','f')+' FROM '+e(root))},byte[].class)==null?null:ExecutionStore.text(jdbc.queryForObject({q('SELECT '+symbol('FLD-TASK-SUMMARY','f')+' FROM '+e(root))},byte[].class)));
        assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
        assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_job_charge",Integer.class));
        runtime.poll("JOB-TASK","tenant-one");assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
    @Test void missedStrictlyBeforeActivationSkipsAndClockReversalRejects() throws Exception {{
        time.fixed=scheduled().add(java.math.BigInteger.ONE);var executions=new java.util.concurrent.atomic.AtomicInteger();var runtime=jobs((id,key,jwt)->{{executions.incrementAndGet();return "unexpected";}});
        runtime.activate("JOB-TASK","tenant-one",time.fixed);runtime.poll("JOB-TASK","tenant-one");assertEquals(0,executions.get());assertEquals("SKIPPED",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_job_skip_range",Integer.class));time.fixed=scheduled();assertThrows(InvocationCore.Outcome.class,()->runtime.poll("JOB-TASK","tenant-one"));
    }}
    @Test void twoSchedulersRaceOneLogicalOccurrenceAndCompletedRestartStaysCompleted() throws Exception {{
        time.fixed=scheduled();var entered=new java.util.concurrent.CountDownLatch(1);var release=new java.util.concurrent.CountDownLatch(1);var count=new java.util.concurrent.atomic.AtomicInteger();
        var runtime=jobs((id,key,jwt)->{{count.incrementAndGet();entered.countDown();try{{release.await(5,java.util.concurrent.TimeUnit.SECONDS);}}catch(Exception x){{throw new RuntimeException(x);}}return "done";}});runtime.activate("JOB-TASK","tenant-one",time.fixed);
        try(var executor=java.util.concurrent.Executors.newSingleThreadExecutor()){{var future=executor.submit(()->runtime.poll("JOB-TASK","tenant-one"));assertTrue(entered.await(5,java.util.concurrent.TimeUnit.SECONDS));jobs((id,key,jwt)->{{fail("duplicate execution");return null;}}).poll("JOB-TASK","tenant-one");release.countDown();future.get();}}
        var restarted=jobs((id,key,jwt)->{{fail("completed restart duplicate");return null;}});time.fixed=time.fixed.add(java.math.BigInteger.ONE);restarted.activate("JOB-TASK","tenant-one",time.fixed);restarted.poll("JOB-TASK","tenant-one");assertEquals(1,count.get());assertEquals("COMPLETED",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));
    }}
    @Test void startedOccurrenceIsRecoveredRatherThanSkipped() throws Exception {{
        time.fixed=scheduled();var first=jobs((id,key,jwt)->{{throw new InvocationCore.Outcome("IN_PROGRESS");}});first.activate("JOB-TASK","tenant-one",time.fixed);first.poll("JOB-TASK","tenant-one");assertEquals("INDETERMINATE",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));
        time.fixed=time.fixed.add(java.math.BigInteger.ONE);var recovered=jobs((id,key,jwt)->"recovered");recovered.activate("JOB-TASK","tenant-one",time.fixed);recovered.poll("JOB-TASK","tenant-one");assertEquals("COMPLETED",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));
    }}
    @Test void principalBindingIsMandatory() throws Exception {{
        assertThrows(IllegalStateException.class,()->new JobRuntime(jdbc,new DataSourceTransactionManager(ds),model,time,(id,rev,handle)->null,java.util.Map.of(),(id,key,jwt)->null));
        time.fixed=scheduled();var unauthorized=new JobRuntime(jdbc,new DataSourceTransactionManager(ds),model,time,(id,rev,handle)->identity("tenant-one","outsider"),java.util.Map.of("JOB-TASK@3","opaque"),new GeneratedJobs(jdbc,inv));unauthorized.activate("JOB-TASK","tenant-one",time.fixed);unauthorized.poll("JOB-TASK","tenant-one");assertEquals("FAILED",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_rate",Integer.class));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_idempotency",Integer.class));
    }}
}}
'''

_base_source=source
def source(domain):
    s=_base_source(domain)
    q=json.dumps;root='ENT-PAYMENT' if domain=='payment' else 'CASE';agg='AGG-ENT-PAYMENT' if domain=='payment' else 'AGG-CASE';v=lambda x:symbol(x,'v');e=lambda x:symbol(x,'e')
    from phase6_reference_tests import seed_sql
    seed=' '.join('jdbc.execute('+q(sql)+');' for sql in seed_sql(domain))
    from execution_semantics import local_occurrence
    vectors=[]
    for zone,local in [('Africa/Nairobi','2026-10-08T09:00:00'),('America/New_York','2026-03-08T02:30:00'),('America/New_York','2026-11-01T01:30:00'),('Europe/Berlin','2026-03-29T02:30:00'),('Europe/Berlin','2026-10-25T02:30:00')]:
        for overlap in ('EARLIER','LATER'):
            expected=local_occurrence(local,{'tzdbVersion':'2026d','timezone':zone,'gap':'SKIP','overlap':overlap})
            vectors.append([zone,local,overlap,None if expected is None else expected.isoformat().replace('+00:00','Z')])
    extra=f'''
    @Test void packagedRulesMatchAcceptedReferenceAlgebraVectors() throws Exception {{
        var vectors=mapper.readTree({q(json.dumps(vectors,separators=(',',':')))});var runtime=new PinnedSchedule();
        for(var vector:vectors){{var actual=runtime.occurrence(java.time.LocalDateTime.parse(vector.get(1).asText()),vector.get(0).asText(),"SKIP",vector.get(2).asText());assertEquals(vector.get(3).isNull()?null:java.time.Instant.parse(vector.get(3).asText()),actual);}}
    }}
    @Test void actualInvocationProfileDatabaseUpgradePreservesExistingState() throws Exception {{
        String url=System.getenv("ACP_TEST_DATABASE_URL"),user=System.getenv("ACP_TEST_DATABASE_USER"),password=System.getenv("ACP_TEST_DATABASE_PASSWORD");
        var clean=Flyway.configure().dataSource(url,user,password).schemas("acp_phase6_execution_test").defaultSchema("acp_phase6_execution_test").cleanDisabled(false).load();clean.clean();
        var directory=java.nio.file.Files.createTempDirectory("acp-invocation-v1-");
        try(var input=getClass().getResourceAsStream("/invocation-profile-V1.sql")){{assertNotNull(input);java.nio.file.Files.copy(input,directory.resolve("V1__initial.sql"));}}
        var old=Flyway.configure().dataSource(url,user,password).schemas("acp_phase6_execution_test").defaultSchema("acp_phase6_execution_test").locations("filesystem:"+directory).load();old.migrate();
        tx.execute(status->{{{seed}
            jdbc.update("INSERT INTO acp_rate(identity,tokens,last_ns) VALUES(?,?,?)",ExecutionStore.bytes("old-rate"),new java.math.BigDecimal("123456789012345"),new java.math.BigDecimal("567890"));
            jdbc.update("INSERT INTO acp_idempotency(identity,input_digest,owner,status,result,commit_xid) VALUES(?,?,?,'COMMITTED_RESULT',?,pg_current_xact_id()::text)",ExecutionStore.bytes("old-idem"),ExecutionStore.bytes("old-input"),"old-owner",ExecutionStore.bytes("{{\\"typed\\":\\"result\\"}}"));
            jdbc.update("INSERT INTO acp_outbox(id,tenant,event,resource,aggregate_version,payload) VALUES('old-event',?,?,?,1,?)",ExecutionStore.bytes("tenant-one"),{q('EVT-RECORDED' if domain=='payment' else 'EVT-REVIEWED')},ExecutionStore.bytes("fixture-resource"),ExecutionStore.bytes("{{}}"));
            jdbc.update("INSERT INTO acp_audit(tenant,subject,operation,resource) VALUES(?,?,?,?)",ExecutionStore.bytes("tenant-one"),ExecutionStore.bytes("fixture:operator"),"old-operation",ExecutionStore.bytes("fixture-resource"));return null;}});
        byte[] result=jdbc.queryForObject("SELECT result FROM acp_idempotency",byte[].class);var rate=jdbc.queryForObject("SELECT tokens FROM acp_rate",java.math.BigDecimal.class);
        clean.migrate();assertEquals(3,java.util.Arrays.stream(clean.info().applied()).filter(m->m.getVersion()!=null).count());
        assertEquals("old",ExecutionStore.text(jdbc.queryForObject({q('SELECT '+symbol('FLD-TASK-SUMMARY','f')+' FROM '+e(root))},byte[].class)));
        assertArrayEquals(result,jdbc.queryForObject("SELECT result FROM acp_idempotency",byte[].class));assertEquals(rate,jdbc.queryForObject("SELECT tokens FROM acp_rate",java.math.BigDecimal.class));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_audit",Integer.class));assertEquals("LEGACY_UNPROVEN",jdbc.queryForObject("SELECT delivery_status FROM acp_outbox",String.class));
        assertArrayEquals(ExecutionStore.bytes("{{}}"),jdbc.queryForObject("SELECT payload FROM acp_outbox",byte[].class));assertEquals(DeliveryRuntime.Result.UNPROVEN,delivery(o->true).poll("tenant-one",{q(agg)},"fixture-resource"));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_job_occurrence",Integer.class));
        java.nio.file.Files.delete(directory.resolve("V1__initial.sql"));java.nio.file.Files.delete(directory);
    }}
    @Test void jobTimeoutRetainsIndeterminateStateAndSameOccurrenceOnRecovery() throws Exception {{
        time.fixed=scheduled();var timed=jobs((id,key,jwt)->{{try{{Thread.sleep(60000);}}catch(InterruptedException x){{Thread.currentThread().interrupt();throw new InvocationCore.Outcome("INTERRUPTED");}}return "unexpected";}});
        timed.activate("JOB-TASK","tenant-one",time.fixed);long begin=System.nanoTime();timed.poll("JOB-TASK","tenant-one");long elapsed=System.nanoTime()-begin;
        assertTrue(elapsed>=java.util.concurrent.TimeUnit.SECONDS.toNanos(29));assertTrue(elapsed<java.util.concurrent.TimeUnit.SECONDS.toNanos(40));
        assertEquals("INDETERMINATE",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));String identity=jdbc.queryForObject("SELECT identity FROM acp_job_occurrence",String.class);
        jobs((id,key,jwt)->{{assertEquals(identity,key);return "recovered";}}).poll("JOB-TASK","tenant-one");assertEquals("COMPLETED",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
    @Test void jobUsesExactRetryPolicyWithoutRechargingLogicalInvocation() throws Exception {{
        jdbc.execute("CREATE FUNCTION job_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION USING ERRCODE='08006', MESSAGE='private fault'; END $$");jdbc.execute({q('CREATE TRIGGER job_fault BEFORE UPDATE ON '+e(root)+' FOR EACH ROW EXECUTE FUNCTION job_fault()')});
        time.fixed=scheduled();var runtime=jobs(new GeneratedJobs(jdbc,inv));runtime.activate("JOB-TASK","tenant-one",time.fixed);runtime.poll("JOB-TASK","tenant-one");
        assertEquals("FAILED",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));assertEquals(java.util.List.of(1L,2L),time.sleeps);assertEquals(3,jdbc.queryForObject("SELECT count(*) FROM acp_job_invocation_attempt WHERE outcome='ROLLED_BACK' AND failure_id='FAIL-TRANSIENT'",Integer.class));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_job_charge",Integer.class));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_idempotency",Integer.class));
    }}
'''
    return s[:s.rindex('}')]+extra+s[s.rindex('}'):]

_extended_source=source
def source(domain):
    s=_extended_source(domain);q=json.dumps;root='ENT-PAYMENT' if domain=='payment' else 'CASE';agg='AGG-ENT-PAYMENT' if domain=='payment' else 'AGG-CASE';events=1 if domain=='payment' else 3;v=lambda x:symbol(x,'v');e=lambda x:symbol(x,'e')
    from invocation_reference_tests import source as original
    original_tests=original(domain);clone_start=original_tests.index('    void insert(String id)');clone_end=original_tests.index('    @Test void unicodeOrder',clone_start);clone=original_tests[clone_start:clone_end]
    extra=clone+f'''
    @Test void consecutiveAggregateCommitsCannotOvertakeAndOtherAggregateProgresses() throws Exception {{
        var jwt=identity("tenant-one","fixture:operator");inv.{v('UC-TASK')}(0,invocation("new"),"first-commit",jwt);
        // Target-only fixture reset permits a second committed update without changing approved workflow meaning.
        jdbc.update({q('UPDATE '+e(root)+' SET acp_state=NULL')});inv.{v('UC-TASK')}({events},invocation("second"),"second-commit",jwt);
        assertEquals(2,jdbc.queryForObject("SELECT count(DISTINCT commit_sequence) FROM acp_outbox",Integer.class));
        var first=jdbc.queryForMap("SELECT id,commit_sequence FROM acp_outbox ORDER BY commit_sequence,step_ordinal,emission_ordinal LIMIT 1");time.fixed=new InvocationCore.SystemTime().now();
        var seen=new java.util.ArrayList<String>();var failing=delivery(o->{{seen.add(o.id());return false;}});
        assertEquals(DeliveryRuntime.Result.RETRY,poll(failing));assertEquals(DeliveryRuntime.Result.RETRY,poll(failing));assertEquals(java.util.List.of(first.get("id"),first.get("id")),seen);
        insert("independent-resource");
        var input={symbol('OPERATION-INPUT','T')}.read(mapper.createObjectNode().put("OPERATION-TEXT","independent"));
        tx.execute(status->tasks.{v('CMD-RECORD' if domain=='payment' else 'CMD-REVIEW')}(new {symbol(root,'T')}Id("independent-resource"),0,input,jwt));
        time.fixed=new InvocationCore.SystemTime().now();assertEquals(DeliveryRuntime.Result.ACKNOWLEDGED,delivery(o->true).poll("tenant-one",{q(agg)},"independent-resource"));
        var successful=delivery(o->true);for(int i=0;i<{events};i++)assertEquals(DeliveryRuntime.Result.ACKNOWLEDGED,poll(successful));
        var next=jdbc.queryForMap("SELECT id,commit_sequence FROM acp_outbox WHERE delivery_status='PENDING' ORDER BY commit_sequence,step_ordinal,emission_ordinal LIMIT 1");assertTrue(((Number)next.get("commit_sequence")).longValue()>((Number)first.get("commit_sequence")).longValue());
    }}
    @Test void jobCommittedThenLostResultRecoversThroughSameDurableIdempotencyIdentity() throws Exception {{
        time.fixed=scheduled();var action=new GeneratedJobs(jdbc,inv);
        var lost=jobs((id,key,jwt)->{{action.execute(id,key,jwt);throw new InvocationCore.Outcome("IN_PROGRESS");}});lost.activate("JOB-TASK","tenant-one",time.fixed);lost.poll("JOB-TASK","tenant-one");
        assertEquals("INDETERMINATE",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
        var tokens=jdbc.queryForObject("SELECT sum(tokens) FROM acp_rate",java.math.BigDecimal.class);String occurrence=jdbc.queryForObject("SELECT identity FROM acp_job_occurrence",String.class);
        time.fixed=new InvocationCore.SystemTime().now();var recovered=jobs(action);recovered.activate("JOB-TASK","tenant-one",time.fixed);recovered.poll("JOB-TASK","tenant-one");
        assertEquals("COMPLETED",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));assertEquals(occurrence,jdbc.queryForObject("SELECT identity FROM acp_job_occurrence",String.class));assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));assertEquals(tokens,jdbc.queryForObject("SELECT sum(tokens) FROM acp_rate",java.math.BigDecimal.class));
    }}
    @Test void actualDatabaseJobTimeoutKeepsUncertaintyUntilRollbackProofAndRecovery() throws Exception {{
        jdbc.execute("CREATE FUNCTION job_timeout() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(35); RETURN NEW; END $$");jdbc.execute({q('CREATE TRIGGER job_timeout BEFORE UPDATE ON '+e(root)+' FOR EACH ROW EXECUTE FUNCTION job_timeout()')});
        time.fixed=scheduled();var finished=new java.util.concurrent.CountDownLatch(1);var action=new GeneratedJobs(jdbc,inv);
        var runtime=jobs((id,key,jwt)->{{try{{return action.execute(id,key,jwt);}}finally{{finished.countDown();}}}});runtime.activate("JOB-TASK","tenant-one",time.fixed);runtime.poll("JOB-TASK","tenant-one");
        assertEquals("INDETERMINATE",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));assertTrue(finished.await(12,java.util.concurrent.TimeUnit.SECONDS));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_idempotency WHERE status='COMMITTED_RESULT'",Integer.class));
        for(var claim:jdbc.queryForList("SELECT attempt_xid FROM acp_idempotency")){{
            String xid=claim.get("attempt_xid").toString();String fact=jdbc.queryForObject("SELECT pg_xact_status(?::xid8)",String.class,xid);assertTrue(java.util.Set.of("in progress","aborted").contains(fact));
            if("in progress".equals(fact)){{jobs(action).poll("JOB-TASK","tenant-one");assertEquals("INDETERMINATE",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));
                jdbc.queryForList("SELECT pg_terminate_backend(pid,5000) FROM pg_stat_activity WHERE backend_xid::text=? AND datname=current_database() AND pid<>pg_backend_pid()",new java.math.BigInteger(xid).mod(java.math.BigInteger.ONE.shiftLeft(32)).toString());}}
            assertEquals("aborted",jdbc.queryForObject("SELECT pg_xact_status(?::xid8)",String.class,xid));
        }}
        jdbc.execute({q('DROP TRIGGER job_timeout ON '+e(root))});jobs(action).poll("JOB-TASK","tenant-one");assertEquals("COMPLETED",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
'''
    return s[:s.rindex('}')]+extra+s[s.rindex('}'):]

_final_source=source
def source(domain):
    s=_final_source(domain);q=json.dumps;root='ENT-PAYMENT' if domain=='payment' else 'CASE';table=symbol(root,'e')
    extra=f'''
    @Test void unboundInternalProviderFaultIsTerminalAndNeverJobRetry() throws Exception {{
        jdbc.execute("CREATE FUNCTION internal_job_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION USING ERRCODE='40001', MESSAGE='unbound provider fault'; END $$");jdbc.execute({q('CREATE TRIGGER internal_job_fault BEFORE UPDATE ON '+table+' FOR EACH ROW EXECUTE FUNCTION internal_job_fault()')});
        time.fixed=scheduled();var runtime=jobs(new GeneratedJobs(jdbc,inv));runtime.activate("JOB-TASK","tenant-one",time.fixed);runtime.poll("JOB-TASK","tenant-one");
        assertEquals("FAILED",jdbc.queryForObject("SELECT status FROM acp_job_occurrence",String.class));assertTrue(time.sleeps.isEmpty());assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_job_invocation_attempt",Integer.class));
        runtime.poll("JOB-TASK","tenant-one");assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_job_invocation_attempt",Integer.class));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
    @Test void stalledTransportIsBoundedAndCannotKeepExpiredBarrierClaimed() throws Exception {{
        inv.{symbol('UC-TASK','v')}(0,invocation("new"),"transport-timeout",identity("tenant-one","fixture:operator"));time.fixed=commitInstant();
        var release=new java.util.concurrent.CountDownLatch(1);var runtime=delivery(o->{{try{{release.await();}}catch(InterruptedException interrupted){{Thread.currentThread().interrupt();}}return true;}});
        assertEquals(DeliveryRuntime.Result.RETRY,poll(runtime));assertEquals("TRANSPORT_TIMEOUT",jdbc.queryForObject("SELECT result FROM acp_delivery_attempt",String.class));
        time.fixed=time.fixed.add(java.math.BigInteger.valueOf(3600).multiply(InvocationCore.BILLION));assertEquals(DeliveryRuntime.Result.UNSATISFIED,poll(runtime));release.countDown();assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox WHERE delivery_status='ACKNOWLEDGED'",Integer.class));
    }}
    @Test void actualGeneratedBootstrapRejectsMissingPrincipalAdapterAndHandle() throws Exception {{
        var beans=new org.springframework.beans.factory.support.DefaultListableBeanFactory();var environment=new org.springframework.mock.env.MockEnvironment();
        var missing=assertThrows(IllegalStateException.class,()->new RuntimeBootstrap(jdbc,new DataSourceTransactionManager(ds),model,inv,environment,beans.getBeanProvider(JobRuntime.PrincipalPort.class),beans.getBeanProvider(DeliveryRuntime.Transport.class)));assertEquals("JOB_PRINCIPAL_ADAPTER_REQUIRED",missing.getMessage());
        beans.registerSingleton("principal",(JobRuntime.PrincipalPort)(id,revision,handle)->identity("tenant-one","fixture:operator"));
        var handle=assertThrows(IllegalStateException.class,()->new RuntimeBootstrap(jdbc,new DataSourceTransactionManager(ds),model,inv,environment,beans.getBeanProvider(JobRuntime.PrincipalPort.class),beans.getBeanProvider(DeliveryRuntime.Transport.class)));assertEquals("JOB_PRINCIPAL_BINDING_REQUIRED",handle.getMessage());
    }}
'''
    return s[:s.rindex('}')]+extra+s[s.rindex('}'):]
