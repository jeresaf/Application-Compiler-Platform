"""Independent PostgreSQL/observability expectations for the approved privacy subset."""
import json
from invocation_reference_tests import source as invocation_source
from phase6_reference_tests import symbol

def source(domain):
    s=invocation_source(domain);s=s[:s.index('    @Test void exactApprovedInvocation')].replace('class InvocationCoreTest','class PrivacyLifecycleTest')
    s=s.replace('import acp.security.ApplicationPolicy;', 'import acp.security.*;')
    s=s.replace('InvocationCore core; Invocations inv;','InvocationCore core; Invocations inv; org.springframework.jdbc.datasource.DriverManagerDataSource ds; TargetModel model; ApplicationPolicy policy; PrivacyGuards privacy;')
    s=s.replace('var ds=new DriverManagerDataSource','ds=new DriverManagerDataSource').replace('var model=new TargetModel(); var policy=','model=new TargetModel(); policy=')
    s=s.replace('tasks=new TypedTasks(store);','privacy=new PrivacyGuards(model,policy,new Expressions(model));tasks=new TypedTasks(store);')
    q=json.dumps;t=lambda x:symbol(x,'T');v=lambda x:symbol(x,'v');f=lambda x:symbol(x,'f');e=lambda x:symbol(x,'e')
    payment=domain=='payment';root='ENT-PAYMENT' if payment else 'CASE';life='LIFECYCLE-ENT-PAYMENT' if payment else 'LIFECYCLE-CASE';hold='HOLD-ENT-PAYMENT' if payment else 'HOLD-CASE';terminal='STATE-POSTED' if payment else 'STATE-ARCHIVED';field='FLD-AMOUNT' if payment else 'FLD-NOTE';events=1 if payment else 3
    close=f'inv.{v("UC-TASK")}(0,invocation("sentinel-domain"),"close",identity("tenant-one","fixture:operator"))'
    amount_sql='SELECT '+f('FLD-AMOUNT')+'::text FROM '+e(root) if payment else 'SELECT '+f('FLD-NOTE')+' IS NULL AND NOT '+symbol('FLD-NOTE','present')+' FROM '+e(root)
    effect_assert=f'assertEquals("1.00",jdbc.queryForObject({q(amount_sql)},String.class));' if payment else f'assertTrue(jdbc.queryForObject({q(amount_sql)},Boolean.class));'
    source=f'''
    LifecycleRuntime lifecycle() {{return new LifecycleRuntime(jdbc,new DataSourceTransactionManager(ds),model,policy,new Expressions(model),time,new LifecycleActions(store));}}
    java.util.Set<LifecycleRuntime.Release> release() {{return java.util.Set.of(new LifecycleRuntime.Release({q(hold)},3));}}
    void close() throws Exception {{{close};}}
    java.math.BigInteger committed() {{return jdbc.queryForObject("SELECT (extract(epoch FROM pg_xact_commit_timestamp(anchor_xid::xid))*1000000000)::numeric FROM acp_lifecycle_anchor",java.math.BigDecimal.class).toBigIntegerExact();}}
    void due() {{time.fixed=committed().add(java.math.BigInteger.valueOf(172800).multiply(InvocationCore.BILLION));}}
    LifecycleRuntime.Result dispose(java.util.Set<LifecycleRuntime.Release> releases) throws Exception {{return lifecycle().dispose({q(life)},"fixture-resource",identity("tenant-one","fixture:operator"),releases);}}
    @Test void exactClosureCommitAnchorAndReobservationNeverResets() throws Exception {{
        close();var anchor=jdbc.queryForMap("SELECT * FROM acp_lifecycle_anchor");assertEquals({q(life)},anchor.get("lifecycle"));assertEquals({q(terminal)},anchor.get("closing_state"));assertNotNull(anchor.get("anchor_xid"));
        assertEquals(LifecycleRuntime.Result.NOT_RETAINED,lifecycle().observe({q(life)},"tenant-one","fixture-resource"));
        assertEquals(committed(),jdbc.queryForObject("SELECT anchor_ns FROM acp_lifecycle_anchor",java.math.BigDecimal.class).toBigIntegerExact());
        var xid=anchor.get("anchor_xid");tx.execute(st->{{store.closed({q(root)},"fixture-resource",{q(terminal)},{q(terminal)},999,identity("tenant-one","fixture:operator"));return null;}});
        assertEquals(xid,jdbc.queryForObject("SELECT anchor_xid FROM acp_lifecycle_anchor",String.class));
    }}
    @Test void rollbackCreatesNoAnchorOrClassifiedWriteAudit() throws Exception {{
        var input=invocation("rollback-sentinel");var jwt=identity("tenant-one","fixture:operator");
        assertThrows(RuntimeException.class,()->tx.execute(st->{{tasks.{v('UC-TASK')}(0,input,jwt);throw new IllegalStateException("ROLLBACK");}}));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_anchor",Integer.class));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit",Integer.class));
    }}
    @Test void nanosecondRetentionAndDeletionBoundariesAndClockReversal() throws Exception {{
        close();var anchor=committed();var runtime=lifecycle();
        time.fixed=anchor.add(java.math.BigInteger.valueOf(86400).multiply(InvocationCore.BILLION)).subtract(java.math.BigInteger.ONE);assertEquals(LifecycleRuntime.Result.NOT_RETAINED,runtime.observe({q(life)},"tenant-one","fixture-resource"));
        time.fixed=time.fixed.add(java.math.BigInteger.ONE);assertEquals(LifecycleRuntime.Result.NOT_DUE,runtime.observe({q(life)},"tenant-one","fixture-resource"));
        time.fixed=anchor.add(java.math.BigInteger.valueOf(172800).multiply(InvocationCore.BILLION)).subtract(java.math.BigInteger.ONE);assertEquals(LifecycleRuntime.Result.NOT_DUE,runtime.observe({q(life)},"tenant-one","fixture-resource"));
        time.fixed=time.fixed.add(java.math.BigInteger.ONE);assertEquals(LifecycleRuntime.Result.BLOCKED_HOLD,runtime.observe({q(life)},"tenant-one","fixture-resource"));
        time.fixed=time.fixed.subtract(java.math.BigInteger.ONE);assertThrows(InvocationCore.Outcome.class,()->runtime.observe({q(life)},"tenant-one","fixture-resource"));
    }}
    @Test void permissionAloneDoesNotReleaseAndWrongExactReleaseFails() throws Exception {{
        close();due();assertEquals(LifecycleRuntime.Result.BLOCKED_HOLD,dispose(java.util.Set.of()));
        assertThrows(RuntimeException.class,()->lifecycle().dispose({q(life)},"fixture-resource",null,release()));
        assertThrows(RuntimeException.class,()->lifecycle().dispose({q(life)},"fixture-resource",identity("tenant-one","outsider"),release()));
        assertThrows(RuntimeException.class,()->dispose(java.util.Set.of(new LifecycleRuntime.Release({q(hold)},2))));
        assertEquals(LifecycleRuntime.Result.UNPROVEN,lifecycle().dispose({q(life)},"fixture-resource",identity("tenant-two","fixture:operator"),release()));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));
    }}
    @Test void exactAuthorizedDisposalIsAtomicTypedAndDoesNotRewriteHistory() throws Exception {{
        close();due();var payloads=jdbc.queryForList("SELECT encode(payload,'hex') AS payload FROM acp_outbox ORDER BY id");var results=jdbc.queryForList("SELECT encode(result,'hex') AS result FROM acp_idempotency ORDER BY identity");var summary=jdbc.queryForObject({q('SELECT convert_from('+f('FLD-TASK-SUMMARY')+",'UTF8') FROM "+e(root))},String.class);
        assertEquals(LifecycleRuntime.Result.COMPLETED,dispose(release()));{effect_assert}
        assertEquals(payloads,jdbc.queryForList("SELECT encode(payload,'hex') AS payload FROM acp_outbox ORDER BY id"));assertEquals(results,jdbc.queryForList("SELECT encode(result,'hex') AS result FROM acp_idempotency ORDER BY identity"));assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
        assertEquals(summary,jdbc.queryForObject({q('SELECT convert_from('+f('FLD-TASK-SUMMARY')+",'UTF8') FROM "+e(root))},String.class));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit WHERE operation=? AND field=? AND mode='WRITE'",Integer.class,{q(life)},{q(field)}));
        var count=jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit",Integer.class);assertEquals(LifecycleRuntime.Result.COMPLETED,dispose(java.util.Set.of()));assertEquals(count,jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit",Integer.class));
        var evidence=jdbc.queryForList("SELECT row_to_json(a)::text FROM acp_lifecycle_attempt a").toString();assertFalse(evidence.contains("sentinel-domain"));assertFalse(jdbc.queryForList("SELECT row_to_json(a)::text FROM acp_classification_audit a").toString().contains("private-note"));
    }}
    @Test void failedDisposalRollsBackEffectsReleaseAndAuditsThenHoldRelatches() throws Exception {{
        close();due();jdbc.execute("CREATE FUNCTION privacy_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'SENSITIVE_SENTINEL_PROVIDER'; END $$");jdbc.execute({q('CREATE TRIGGER privacy_fail BEFORE UPDATE ON '+e(root)+' FOR EACH ROW EXECUTE FUNCTION privacy_fail()')});
        assertThrows(RuntimeException.class,()->dispose(release()));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit WHERE operation=?",Integer.class,{q(life)}));
        jdbc.execute({q('DROP TRIGGER privacy_fail ON '+e(root))});assertEquals(LifecycleRuntime.Result.BLOCKED_HOLD,dispose(java.util.Set.of()));assertEquals(LifecycleRuntime.Result.COMPLETED,dispose(release()));
    }}
    @Test void concurrentWorkersFenceOneSuccessfulLogicalDisposal() throws Exception {{
        close();due();var runtime=lifecycle();try(var pool=java.util.concurrent.Executors.newFixedThreadPool(2)) {{
            var gate=new java.util.concurrent.CountDownLatch(1);var calls=new java.util.ArrayList<java.util.concurrent.Future<LifecycleRuntime.Result>>();for(int i=0;i<2;i++)calls.add(pool.submit(()->{{gate.await();return runtime.dispose({q(life)},"fixture-resource",identity("tenant-one","fixture:operator"),release());}}));gate.countDown();for(var call:calls)assertTrue(java.util.Set.of(LifecycleRuntime.Result.COMPLETED,LifecycleRuntime.Result.BUSY).contains(call.get()));
        }}assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));{effect_assert}
    }}
    @Test void domainRootLockSerializesLifecycleAndStaleCommandCannotLoseUpdate() throws Exception {{
        close();due();jdbc.update({q('UPDATE '+e(root)+' SET acp_state=NULL')});var commandInput=invocation("serialized-command");var entered=new java.util.concurrent.CountDownLatch(1);var unlock=new java.util.concurrent.CountDownLatch(1);var jwt=identity("tenant-one","fixture:operator");
        try(var pool=java.util.concurrent.Executors.newFixedThreadPool(2)) {{
            var holder=pool.submit(()->tx.execute(st->{{tasks.{v('UC-TASK')}({events},commandInput,jwt);entered.countDown();try{{unlock.await();}}catch(InterruptedException ex){{throw new IllegalStateException("INTERRUPTED");}}return null;}}));entered.await();var disposed=pool.submit(()->dispose(release()));Thread.sleep(100);assertFalse(disposed.isDone());unlock.countDown();holder.get();assertEquals(LifecycleRuntime.Result.COMPLETED,disposed.get());
        }}
        assertEquals("serialized-command",jdbc.queryForObject({q('SELECT convert_from('+f('FLD-TASK-SUMMARY')+",'UTF8') FROM "+e(root))},String.class));
        assertThrows(RuntimeException.class,()->inv.{v('UC-TASK')}({events*2},invocation("stale"),"stale",jwt));{effect_assert}
    }}
    @Test void classifiedMetadataMasksOmitsAndExportDeniesWithoutChangingDomainValues() throws Exception {{
        var sensitive=(com.fasterxml.jackson.databind.node.ObjectNode)model.node("CLASS-SENSITIVE").path("data");var secret=(com.fasterxml.jackson.databind.node.ObjectNode)model.node({q(field)}).path("data");
        var original=secret.get("classificationRef").deepCopy();secret.set("classificationRef",mapper.createObjectNode().put("id","CLASS-SENSITIVE").put("revision",2));
        var port=new Observability(privacy);for(var surface:Observability.Surface.values()) {{var metadata=port.metadata(surface,java.util.Map.of({q(field)},"SENSITIVE_SENTINEL_ABC"));assertEquals("[REDACTED]",metadata.get({q(field)}));assertFalse(metadata.toString().contains("SENSITIVE_SENTINEL_ABC"));}}
        secret.set("classificationRef",mapper.createObjectNode().put("id","CLASS-SECRET").put("revision",2));for(var surface:Observability.Surface.values())assertFalse(port.metadata(surface,java.util.Map.of({q(field)},"SECRET_SENTINEL_ABC")).containsKey({q(field)}));secret.set("classificationRef",original);
        assertThrows(org.springframework.security.access.AccessDeniedException.class,()->privacy.requireExport({q(field)},java.util.Map.of(),identity("tenant-one","fixture:operator")));
        close();assertEquals("sentinel-domain",jdbc.queryForObject({q('SELECT convert_from('+f('FLD-TASK-SUMMARY')+",'UTF8') FROM "+e(root))},String.class));
    }}
    @Test void adversarialDiagnosticsAcrossAllPathsContainNoClassifiedSentinels() throws Exception {{
        var logger=(ch.qos.logback.classic.Logger)org.slf4j.LoggerFactory.getLogger(Observability.class);var capture=new ch.qos.logback.core.read.ListAppender<ch.qos.logback.classic.spi.ILoggingEvent>();capture.start();logger.addAppender(capture);
        try{{var fd=(com.fasterxml.jackson.databind.node.ObjectNode)model.node({q(field)}).path("data");fd.set("classificationRef",mapper.createObjectNode().put("id","CLASS-SENSITIVE").put("revision",2));
            var port=new Observability(privacy);for(var diagnostic:Observability.Diagnostic.values())port.emit(diagnostic,java.util.Map.of({q(field)},"SENSITIVE_SENTINEL_ABC"));
            fd.set("classificationRef",mapper.createObjectNode().put("id","CLASS-SECRET").put("revision",2));for(var diagnostic:Observability.Diagnostic.values())port.emit(diagnostic,java.util.Map.of({q(field)},"SECRET_SENTINEL_ABC"));
            assertEquals(18,capture.list.size());for(var event:capture.list){{assertFalse(event.getFormattedMessage().contains("SENSITIVE_SENTINEL"));assertFalse(event.getFormattedMessage().contains("SECRET_SENTINEL"));assertNull(event.getThrowableProxy());}}
        }}finally{{logger.detachAppender(capture);capture.stop();}}
    }}
    @Test void legacyUnprovenClosureNeverUsesMigrationOrPollingTime() throws Exception {{
        close();jdbc.update("UPDATE acp_lifecycle_anchor SET anchor_xid=NULL,anchor_ns=NULL,status='LEGACY_UNPROVEN'");time.fixed=new InvocationCore.SystemTime().now().add(java.math.BigInteger.valueOf(999999).multiply(InvocationCore.BILLION));assertEquals(LifecycleRuntime.Result.UNPROVEN,dispose(release()));assertNull(jdbc.queryForObject("SELECT anchor_ns FROM acp_lifecycle_anchor",java.math.BigDecimal.class));
    }}
'''
    if not payment:source+=f'''
    @Test void nullableNullAndAbsentRemainDistinctBeforeAndAfterDisposal() throws Exception {{
        jdbc.update({q('UPDATE '+e(root)+' SET '+f('FLD-NOTE')+'=NULL,'+symbol('FLD-NOTE','present')+'=true')});assertTrue(jdbc.queryForObject({q('SELECT '+symbol('FLD-NOTE','present')+' FROM '+e(root))},Boolean.class));close();due();dispose(release());{effect_assert}
    }}
'''
    source+=f'''
    @Test void actualLifecycleProviderAndDeliveryDiagnosticsNeverExposeClassifiedValues() throws Exception {{
        var logger=(ch.qos.logback.classic.Logger)org.slf4j.LoggerFactory.getLogger(org.slf4j.Logger.ROOT_LOGGER_NAME);var capture=new ch.qos.logback.core.read.ListAppender<ch.qos.logback.classic.spi.ILoggingEvent>();capture.start();logger.addAppender(capture);
        try{{
            close();time.fixed=committed();var delivery=new DeliveryRuntime(jdbc,new DataSourceTransactionManager(ds),model,time,o->{{throw new IllegalStateException("SECRET_SENTINEL_PROVIDER");}});
            assertEquals(DeliveryRuntime.Result.RETRY,delivery.poll("tenant-one",{q('AGG-ENT-PAYMENT' if payment else 'AGG-CASE')},"fixture-resource"));due();assertEquals(LifecycleRuntime.Result.BLOCKED_HOLD,dispose(java.util.Set.of()));
            jdbc.execute("CREATE FUNCTION privacy_diagnostic_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'SENSITIVE_SENTINEL_PROVIDER'; END $$");jdbc.execute({q('CREATE TRIGGER privacy_diagnostic_fail BEFORE UPDATE ON '+e(root)+' FOR EACH ROW EXECUTE FUNCTION privacy_diagnostic_fail()')});
            var failure=assertThrows(RuntimeException.class,()->dispose(release()));assertFalse(failure.toString().contains("SENSITIVE_SENTINEL"));assertNull(failure.getCause());
            jdbc.execute({q('DROP TRIGGER privacy_diagnostic_fail ON '+e(root))});assertEquals(LifecycleRuntime.Result.COMPLETED,dispose(release()));
            for(var event:capture.list){{String text=event.getFormattedMessage()+(event.getThrowableProxy()==null?"":ch.qos.logback.classic.spi.ThrowableProxyUtil.asString(event.getThrowableProxy()));assertFalse(text.contains("SENSITIVE_SENTINEL"));assertFalse(text.contains("SECRET_SENTINEL"));}}
            for(String table:java.util.List.of("acp_audit","acp_classification_audit","acp_delivery_attempt","acp_lifecycle_attempt","acp_lifecycle_release_audit")){{var evidence=jdbc.queryForList("SELECT row_to_json(a)::text FROM "+table+" a").toString();assertFalse(evidence.contains("SENSITIVE_SENTINEL"));assertFalse(evidence.contains("SECRET_SENTINEL"));}}
        }}finally{{logger.detachAppender(capture);capture.stop();}}
    }}
'''
    prior=invocation_source(domain);start=prior.index('    void insert(String id)')
    source+=prior[start:prior.index('    @Test void unicodeOrder',start)]
    source+=f'''
    @Test void successfulReleaseCannotBeReusedForAnotherResource() throws Exception {{
        close();due();assertEquals(LifecycleRuntime.Result.COMPLETED,dispose(release()));insert("later-resource");
        var input=Contracts.{t('INPUT-TASK')}.read(mapper.createObjectNode().put("INPUT-TASK-RESOURCE","later-resource").put("INPUT-TASK-TEXT","later"));
        time.fixed=null;inv.{v('UC-TASK')}(0,input,"later-key",identity("tenant-one","fixture:operator"));
        time.fixed=jdbc.queryForObject("SELECT (extract(epoch FROM pg_xact_commit_timestamp(anchor_xid::xid))*1000000000)::numeric FROM acp_lifecycle_anchor WHERE resource=convert_to('later-resource','UTF8')",java.math.BigDecimal.class).toBigIntegerExact().add(java.math.BigInteger.valueOf(172800).multiply(InvocationCore.BILLION));
        assertEquals(LifecycleRuntime.Result.BLOCKED_HOLD,lifecycle().dispose({q(life)},"later-resource",identity("tenant-one","fixture:operator"),java.util.Set.of()));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));
        assertEquals(LifecycleRuntime.Result.COMPLETED,lifecycle().dispose({q(life)},"later-resource",identity("tenant-one","fixture:operator"),release()));
        assertEquals(2,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));
    }}
    @Test void uncertainActionBlocksUntilAuthoritativeRollbackThenRequiresFreshRelease() throws Exception {{
        close();due();try(var connection=ds.getConnection()){{connection.setAutoCommit(false);String xid;
            try(var statement=connection.createStatement();var result=statement.executeQuery("SELECT pg_current_xact_id()::text")){{result.next();xid=result.getString(1);}}
            jdbc.update("UPDATE acp_lifecycle_anchor SET attempt_xid=?,status='INDETERMINATE'",xid);
            assertEquals(LifecycleRuntime.Result.INDETERMINATE,dispose(release()));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));
            connection.rollback();assertEquals(LifecycleRuntime.Result.BLOCKED_HOLD,dispose(java.util.Set.of()));assertEquals(LifecycleRuntime.Result.COMPLETED,dispose(release()));
        }}
    }}
'''
    if payment:source+=f'''
    @Test void stagedReplacementMustSatisfyRetainedPositiveInvariant() throws Exception {{
        close();due();var stagedFailure=assertThrows(IllegalArgumentException.class,()->tx.execute(st->{{new InvalidLifecycleActions(store).apply({q(life)},"fixture-resource",identity("tenant-one","fixture:operator"));return null;}}));assertEquals("POST_DISPOSAL_INVARIANT",stagedFailure.getMessage());
        var runtime=new LifecycleRuntime(jdbc,new DataSourceTransactionManager(ds),model,policy,new Expressions(model),time,new InvalidLifecycleActions(store));
        assertThrows(RuntimeException.class,()->runtime.dispose({q(life)},"fixture-resource",identity("tenant-one","fixture:operator"),release()));assertEquals("12.50",jdbc.queryForObject({q(amount_sql)},String.class));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit WHERE operation=?",Integer.class,{q(life)}));
    }}
'''
    return s+source+'\n}\n'

def variants(domain,nodes):
    if domain!='payment':return {}
    from execution_codegen import ExecutionGenerator
    from privacy_lifecycle import actions
    text=actions(ExecutionGenerator(nodes,'0.3.0'))
    text=text.replace('class LifecycleActions','class InvalidLifecycleActions').replace('public LifecycleActions(','public InvalidLifecycleActions(').replace('new java.math.BigDecimal("1")','new java.math.BigDecimal("0")')
    return {'backend/src/test/java/acp/generated/InvalidLifecycleActions.java':text}


def http_source(domain):
    from invocation_reference_tests import http_source as previous
    s=previous(domain);s=s[:s.index('    @Test void typedInputBinding')].replace('InvocationHttpTest','PrivacyHttpTest')
    q=json.dumps;root='ENT-PAYMENT' if domain=='payment' else 'CASE';path='/api/'+symbol('UC-TASK','op')
    return s+f'''
    @Autowired acp.infrastructure.TargetModel model;
    @Test void actualHttpSuccessValidationAuthorizationFailureAndProviderErrorNeverLogValues() throws Exception {{
        var logger=(ch.qos.logback.classic.Logger)org.slf4j.LoggerFactory.getLogger(org.slf4j.Logger.ROOT_LOGGER_NAME);var capture=new ch.qos.logback.core.read.ListAppender<ch.qos.logback.classic.spi.ILoggingEvent>();capture.start();logger.addAppender(capture);
        var mapper=new com.fasterxml.jackson.databind.ObjectMapper();var field=(com.fasterxml.jackson.databind.node.ObjectNode)model.node("FLD-TASK-SUMMARY").path("data");var original=field.get("classificationRef").deepCopy();
        try{{for(String level:java.util.List.of("SENSITIVE","SECRET")){{seed();field.set("classificationRef",mapper.createObjectNode().put("id","CLASS-"+level).put("revision",2));String sentinel=level+"_ACTUAL_HTTP_SENTINEL";
            var body=mapper.createObjectNode().put("expectedVersion",0).put("idempotencyKey","privacy-http");body.set("input",mapper.createObjectNode().put("INPUT-TASK-RESOURCE","fixture-resource").put("INPUT-TASK-TEXT",sentinel));
            var denied=send({q(path)},body.toString(),false);assertEquals(401,denied.statusCode());assertFalse(denied.body().contains(sentinel));assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit",Integer.class));
            var invalid=body.deepCopy().put("expectedVersion",sentinel);var validation=send({q(path)},invalid.toString(),true);assertTrue(validation.statusCode()>=400);assertFalse(validation.body().contains(sentinel));
            jdbc.update({q('UPDATE '+symbol(root,'e')+" SET acp_state='STATE-ARCHIVED'")});var semantic=send({q(path)},body.toString(),true);assertEquals(422,semantic.statusCode());assertFalse(semantic.body().contains(sentinel));
            seed();jdbc.execute("CREATE FUNCTION privacy_http_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION '"+sentinel+"'; END $$");jdbc.execute({q('CREATE TRIGGER privacy_http_fail BEFORE UPDATE ON '+symbol(root,'e')+' FOR EACH ROW EXECUTE FUNCTION privacy_http_fail()')});
            var provider=send({q(path)},body.toString(),true);assertTrue(provider.statusCode()>=400);assertFalse(provider.body().contains(sentinel));
            seed();var success=send({q(path)},body.toString(),true);assertEquals(200,success.statusCode(),success.body());assertTrue(success.body().contains(sentinel));
            var readsBefore=jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit WHERE field='FLD-TASK-SUMMARY' AND mode='READ'",Integer.class);assertEquals({1 if domain=='payment' else 3},readsBefore);
            var selected=send({q('/api/'+symbol('QUERY-TASKS','op'))},mapper.createObjectNode().put("QUERY-TEXT",sentinel).toString(),true);assertEquals(200,selected.statusCode(),selected.body());assertTrue(selected.body().contains(sentinel));assertEquals(readsBefore+1,jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit WHERE field='FLD-TASK-SUMMARY' AND mode='READ'",Integer.class));
            assertFalse(jdbc.queryForList("SELECT row_to_json(a)::text FROM acp_classification_audit a").toString().contains(sentinel));assertFalse(jdbc.queryForList("SELECT row_to_json(a)::text FROM acp_audit a").toString().contains(sentinel));
            for(var event:capture.list){{assertFalse(event.getFormattedMessage().contains(sentinel));if(event.getThrowableProxy()!=null)assertFalse(ch.qos.logback.classic.spi.ThrowableProxyUtil.asString(event.getThrowableProxy()).contains(sentinel));}}
        }} }}finally{{field.set("classificationRef",original);logger.detachAppender(capture);capture.stop();}}
    }}
}}
'''
