"""External PostgreSQL regressions; no production authentication adapters."""
from pathlib import Path

def sources(domain):
    from invocation_reference_tests import source
    original=source(domain)
    prefix=original[:original.index('    @Test void exactApproved')].replace('class InvocationCoreTest','class RateClockTest')
    tests=r'''
    static void await(java.util.concurrent.CountDownLatch latch) {
        try {assertTrue(latch.await(10,java.util.concurrent.TimeUnit.SECONDS),"bounded gate");}
        catch(InterruptedException error){Thread.currentThread().interrupt();throw new AssertionError(error);}
    }
    static class GateJdbc extends JdbcTemplate {
        final java.util.concurrent.CountDownLatch paused=new java.util.concurrent.CountDownLatch(1),release=new java.util.concurrent.CountDownLatch(1);
        final java.util.concurrent.atomic.AtomicBoolean once=new java.util.concurrent.atomic.AtomicBoolean();
        GateJdbc(javax.sql.DataSource ds){super(ds);}
        void gate(){if(Thread.currentThread().getName().equals("rate-first")&&once.compareAndSet(false,true)){paused.countDown();await(release);}}
        @Override public int update(String sql,Object...args){if(sql.startsWith("INSERT INTO acp_rate"))gate();return super.update(sql,args);}
        @Override public void execute(String sql){if(sql.startsWith("SELECT pg_advisory_xact_lock("))gate();super.execute(sql);}
        @Override public java.util.Map<String,Object> queryForMap(String sql,Object...args){if(sql.contains("FOR UPDATE"))gate();return super.queryForMap(sql,args);}
    }
    void reordered(boolean frozen) throws Exception {
        var gated=new GateJdbc(jdbc.getDataSource());var clock=new java.util.concurrent.atomic.AtomicLong();
        var manager=new DataSourceTransactionManager(jdbc.getDataSource());
        InvocationCore.Time liveTime=new InvocationCore.Time(){public java.math.BigInteger now(){return java.math.BigInteger.valueOf(clock.getAndIncrement());}public void sleep(long seconds){throw new AssertionError("unexpected sleep");}};
        FrozenClockCore.Time oldTime=new FrozenClockCore.Time(){public java.math.BigInteger now(){return java.math.BigInteger.valueOf(clock.getAndIncrement());}public void sleep(long seconds){throw new AssertionError("unexpected sleep");}};
        var live=new InvocationCore(gated,new TargetModel(),manager,liveTime);
        var old=new FrozenClockCore(gated,new TargetModel(),manager,oldTime);
        var jwt=identity("tenant-one","fixture:operator");
        java.util.concurrent.Callable<String> operation=()->{try{if(frozen)old.charge("QUERY-TASKS",jwt);else live.charge("QUERY-TASKS",jwt);return "OK";}catch(RuntimeException error){return error.getMessage();}};
        var pool=java.util.concurrent.Executors.newFixedThreadPool(2);
        try {
            var first=pool.submit(()->{Thread.currentThread().setName("rate-first");return operation.call();});
            await(gated.paused);
            var second=pool.submit(operation);assertEquals("OK",second.get(10,java.util.concurrent.TimeUnit.SECONDS));
            gated.release.countDown();assertEquals(frozen?"CLOCK_REVERSED":"OK",first.get(10,java.util.concurrent.TimeUnit.SECONDS));
            assertEquals(2,clock.get());assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_rate",Integer.class));
            assertEquals(0,java.math.BigInteger.ONE.compareTo(jdbc.queryForObject("SELECT last_ns FROM acp_rate",java.math.BigDecimal.class).toBigIntegerExact()));
            var expected=new java.math.BigDecimal(frozen?"540000000000":"480000000100");
            assertEquals(0,expected.compareTo(jdbc.queryForObject("SELECT tokens FROM acp_rate",java.math.BigDecimal.class)));
            System.out.println("ACP_RATE_ORDER|"+(frozen?"FROZEN_REPRODUCED":"SUCCESSOR_ORDERED")+"|second-before-first|last=1");
        } finally {gated.release.countDown();pool.shutdownNow();assertTrue(pool.awaitTermination(10,java.util.concurrent.TimeUnit.SECONDS));}
    }
    @Test void frozenTemplateDeterministicallyReproducesClockReversal() throws Exception {reordered(true);}
    @Test void successorOrdersClockSamplingAfterPartitionAdmission() throws Exception {reordered(false);}
    @Test void unrelatedPartitionsProgressWhileFirstClockIsHeld() throws Exception {
        var held=new java.util.concurrent.CountDownLatch(1);var release=new java.util.concurrent.CountDownLatch(1);
        InvocationCore.Time clock=new InvocationCore.Time(){public java.math.BigInteger now(){if(Thread.currentThread().getName().equals("held-clock")){held.countDown();await(release);}return java.math.BigInteger.ZERO;}public void sleep(long seconds){throw new AssertionError("unexpected sleep");}};
        var live=new InvocationCore(jdbc,new TargetModel(),new DataSourceTransactionManager(jdbc.getDataSource()),clock);
        var pool=java.util.concurrent.Executors.newFixedThreadPool(2);
        try {
            var first=pool.submit(()->{Thread.currentThread().setName("held-clock");live.charge("QUERY-TASKS",identity("tenant-one","fixture:operator"));});await(held);
            pool.submit(()->live.charge("QUERY-TASKS",identity("tenant-two","fixture:operator"))).get(5,java.util.concurrent.TimeUnit.SECONDS);
            pool.submit(()->live.charge("QUERY-TASKS",identity("tenant-one","different-actor"))).get(5,java.util.concurrent.TimeUnit.SECONDS);
            release.countDown();first.get(10,java.util.concurrent.TimeUnit.SECONDS);
            assertEquals(3,jdbc.queryForObject("SELECT count(*) FROM acp_rate",Integer.class));
        }finally{release.countDown();pool.shutdownNow();assertTrue(pool.awaitTermination(10,java.util.concurrent.TimeUnit.SECONDS));}
    }
    @Test void genuineBackwardTimeRejectsWithoutMutationAndLocksRelease() {
        time.fixed=java.math.BigInteger.TEN;core.charge("QUERY-TASKS",identity("tenant-one","fixture:operator"));
        var before=jdbc.queryForList("SELECT encode(identity,'hex') AS identity,tokens,last_ns FROM acp_rate");time.fixed=java.math.BigInteger.ONE;
        assertEquals("CLOCK_REVERSED",assertThrows(InvocationCore.Outcome.class,()->core.charge("QUERY-TASKS",identity("tenant-one","fixture:operator"))).getMessage());
        assertEquals(before,jdbc.queryForList("SELECT encode(identity,'hex') AS identity,tokens,last_ns FROM acp_rate"));
        time.fixed=java.math.BigInteger.TEN;core.charge("QUERY-TASKS",identity("tenant-one","fixture:operator"));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_rate",Integer.class));
    }
    @Test void sqlFailureRollsBackAdmissionAndReleasesPartitionLock() throws Exception {
        var fail=new java.util.concurrent.atomic.AtomicBoolean(true);
        var broken=new JdbcTemplate(jdbc.getDataSource()) {
            @Override public java.util.Map<String,Object> queryForMap(String sql,Object...args){
                if(sql.contains("FOR UPDATE")&&fail.getAndSet(false))throw new IllegalStateException("injected-storage-failure");
                return super.queryForMap(sql,args);
            }
        };
        var live=new InvocationCore(broken,new TargetModel(),new DataSourceTransactionManager(jdbc.getDataSource()),time);
        assertEquals("injected-storage-failure",assertThrows(IllegalStateException.class,()->live.charge("QUERY-TASKS",identity("tenant-one","fixture:operator"))).getMessage());
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_rate",Integer.class));
        live.charge("QUERY-TASKS",identity("tenant-one","fixture:operator"));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_rate",Integer.class));
    }
'''
    root=Path(__file__).resolve().parents[3]
    frozen=(root/'targets/spring-vue-postgres/templates/backend/src/main/java/acp/infrastructure/InvocationCore.java').read_text().replace('InvocationCore','FrozenClockCore')
    return {'backend/src/test/java/acp/generated/RateClockTest.java':prefix+tests+'}\n',
            'backend/src/test/java/acp/infrastructure/FrozenClockCore.java':frozen}
