"""External test-only correction; sealed reference generators remain byte-identical."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tooling'), str(ROOT / 'tooling/tests')]
from privacy_lifecycle_reference_tests import source as sealed_source


DECLARATION = 'close();due();var runtime=lifecycle();try(var pool='
WORKER_IDENTITY = 'identity("tenant-one","fixture:operator"),release());}));gate.countDown();'


def source(domain):
    text = sealed_source(domain)
    start = text.index('    @Test void concurrentWorkersFenceOneSuccessfulLogicalDisposal()')
    end = text.index('    @Test void domainRootLockSerializesLifecycle', start)
    method = text[start:end]
    if method.count(DECLARATION) != 1 or method.count(WORKER_IDENTITY) != 1:
        raise ValueError('SEALED_PRIVACY_FIXTURE_SHAPE_CHANGED')
    # Retain the sealed final-state assertions; replace only its execution harness.
    tail = method[method.index('assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit"'):]
    method = '    @Test void concurrentWorkersFenceOneSuccessfulLogicalDisposal() throws Exception {\n        contentionProof(2, false, 10_000);' + tail
    text = text[:start] + method + text[end:]
    # Exercise the real, unchanged SessionGate and lifecycle against PostgreSQL.
    tests = '''
    org.springframework.security.oauth2.jwt.Jwt workerIdentity(org.springframework.security.oauth2.jwt.Jwt event,int worker) {
        return org.springframework.security.oauth2.jwt.Jwt.withTokenValue(event.getTokenValue())
            .headers(h->h.putAll(event.getHeaders())).claims(c->c.putAll(event.getClaims()))
            .claim("sid","privacy-worker-"+worker).issuedAt(event.getIssuedAt()).expiresAt(event.getExpiresAt()).build();
    }
    org.springframework.security.oauth2.jwt.Jwt authenticationAt(java.time.Instant at,String sid) {
        return org.springframework.security.oauth2.jwt.Jwt.withTokenValue("ordering-fixture-only")
            .header("alg","none").subject("fixture:operator").claim("tenant","tenant-one")
            .claim("sid",sid).claim("amr",java.util.List.of("pwd","otp"))
            .claim("auth_time",at.getEpochSecond()).issuedAt(at).expiresAt(at.plusSeconds(600)).build();
    }
    void contentionProof(int threads,boolean abort,long competitorTimeoutMillis) throws Exception {
        close();due();
        var event=identity("tenant-one","fixture:operator");
        var first=workerIdentity(event,0);var second=workerIdentity(event,1);
        assertNotEquals(first.getClaimAsString("sid"),second.getClaimAsString("sid"));
        for(var worker:java.util.List.of(first,second)) {
            policy.actor(worker); // Real SessionGate commits its independent session transaction.
            assertFalse(org.springframework.transaction.support.TransactionSynchronizationManager.isActualTransactionActive());
            assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_sessions WHERE tenant=? AND subject=? AND sid=? AND authenticated_at=? AND NOT revoked",Integer.class,
                ExecutionStore.bytes(worker.getClaimAsString("tenant")),ExecutionStore.bytes(worker.getSubject()),ExecutionStore.bytes(worker.getClaimAsString("sid")),((Number)worker.getClaims().get("auth_time")).longValue()));
            System.out.println("CONTENTION SESSION_COMMITTED sid="+worker.getClaimAsString("sid"));
        }
        var acquired=new java.util.concurrent.CountDownLatch(1);var releaseFence=new java.util.concurrent.CountDownLatch(1);
        var permitted=new java.util.concurrent.atomic.AtomicBoolean(false);
        var winner=new java.util.concurrent.atomic.AtomicReference<String>();
        var delegate=new LifecycleActions(store);
        var actions=new LifecycleRuntime.Actions() {
            public LifecycleRuntime.Snapshot lock(String life,String resource,org.springframework.security.oauth2.jwt.Jwt principal) {
                assertEquals(first.getClaimAsString("sid"),principal.getClaimAsString("sid"));
                var snapshot=delegate.lock(life,resource,principal);
                winner.set(jdbc.queryForObject("SELECT pg_current_xact_id()::text",String.class));
                System.out.println("CONTENTION FENCE_ACQUIRED sid="+principal.getClaimAsString("sid")+" xid="+winner.get());acquired.countDown();
                try { if(!releaseFence.await(30,java.util.concurrent.TimeUnit.SECONDS))throw new IllegalStateException("FENCE_RELEASE_TIMEOUT"); }
                catch(InterruptedException failure){Thread.currentThread().interrupt();throw new IllegalStateException("FENCE_INTERRUPTED",failure);}
                if(!permitted.get())throw new IllegalStateException("PROOF_ABORTED");
                return snapshot;
            }
            public void apply(String life,String resource,org.springframework.security.oauth2.jwt.Jwt principal) {
                assertEquals(first.getClaimAsString("sid"),principal.getClaimAsString("sid"));delegate.apply(life,resource,principal);
            }
        };
        var held=new LifecycleRuntime(jdbc,new DataSourceTransactionManager(ds),model,policy,new Expressions(model),time,actions);
        var pool=java.util.concurrent.Executors.newFixedThreadPool(threads);
        java.util.concurrent.Future<LifecycleRuntime.Result> owner=null,competitor=null;
        try {
            owner=pool.submit(()->held.dispose(LIFECYCLE,"fixture-resource",first,release()));
            assertTrue(acquired.await(10,java.util.concurrent.TimeUnit.SECONDS),"FIRST_FENCE_NOT_ACQUIRED");
            assertFalse(owner.isDone());assertEquals(1,releaseFence.getCount());
            competitor=pool.submit(()->{
                System.out.println("CONTENTION COMPETITOR_ATTEMPT sid="+second.getClaimAsString("sid"));
                return lifecycle().dispose(LIFECYCLE,"fixture-resource",second,release());
            });
            assertEquals(LifecycleRuntime.Result.BUSY,competitor.get(competitorTimeoutMillis,java.util.concurrent.TimeUnit.MILLISECONDS));
            assertFalse(owner.isDone());assertEquals(1,releaseFence.getCount());
            System.out.println("CONTENTION COMPETITOR_BUSY fenceStillHeld=true");
            if(abort)throw new IllegalStateException("INJECTED_PROOF_FAILURE");
            permitted.set(true);releaseFence.countDown();
            assertEquals(LifecycleRuntime.Result.COMPLETED,owner.get(10,java.util.concurrent.TimeUnit.SECONDS));
            var anchor=jdbc.queryForMap("SELECT * FROM acp_lifecycle_anchor WHERE lifecycle=? AND tenant=? AND resource=?",LIFECYCLE,ExecutionStore.bytes("tenant-one"),ExecutionStore.bytes("fixture-resource"));
            assertEquals("COMPLETED",anchor.get("status"));assertNotNull(anchor.get("completed_ns"));
            assertEquals(winner.get(),anchor.get("attempt_xid"));
            assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_attempt WHERE lifecycle=? AND action_xid=? AND result='COMPLETED'",Integer.class,LIFECYCLE,winner.get()));
            assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit WHERE lifecycle=? AND tenant=? AND resource=? AND subject=? AND action_xid=?",Integer.class,LIFECYCLE,ExecutionStore.bytes("tenant-one"),ExecutionStore.bytes("fixture-resource"),ExecutionStore.bytes(first.getSubject()),winner.get()));
            assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));
            System.out.println("CONTENTION OWNER_COMPLETED sid="+first.getClaimAsString("sid")+" xid="+winner.get()+" anchor=COMPLETED releases=1");
        } finally {
            if(competitor!=null && !competitor.isDone())competitor.cancel(true);
            releaseFence.countDown();
            pool.shutdown();
            if(!pool.awaitTermination(10,java.util.concurrent.TimeUnit.SECONDS)) {
                pool.shutdownNow();assertTrue(pool.awaitTermination(10,java.util.concurrent.TimeUnit.SECONDS),"WORKER_CLEANUP_FAILED");
            }
            assertTrue(pool.isTerminated());
        }
    }
    @Test void serializedDisposalCannotSatisfyContentionProofAndCleansUp() throws Exception {
        assertThrows(java.util.concurrent.TimeoutException.class,()->contentionProof(1,false,250));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));
        assertEquals(LifecycleRuntime.Result.COMPLETED,dispose(release()));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));
    }
    @Test void failedContentionProofReleasesFenceAndRollsBack() throws Exception {
        var failure=assertThrows(IllegalStateException.class,()->contentionProof(2,true,10_000));
        assertEquals("INJECTED_PROOF_FAILURE",failure.getMessage());
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));
        assertEquals(LifecycleRuntime.Result.COMPLETED,dispose(release()));
        assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));
    }
    @Test void olderAuthenticationAfterNewerSameSessionIsRejectedBeforeDisposal() throws Exception {
        close();due();
        var now=java.time.Instant.now().minusSeconds(2).truncatedTo(java.time.temporal.ChronoUnit.SECONDS);
        var newer=authenticationAt(now,"ordering-session");var older=authenticationAt(now.minusSeconds(1),"ordering-session");
        var gate=new SessionGate(model,jdbc,new DataSourceTransactionManager(ds),java.time.Clock.fixed(now,java.time.ZoneOffset.UTC));
        gate.require(newer);
        var rejected=assertThrows(org.springframework.security.access.AccessDeniedException.class,
            ()->lifecycle().dispose(LIFECYCLE,"fixture-resource",older,release()));
        assertEquals("AUTHENTICATION_SESSION_DENIED",rejected.getMessage());
        assertEquals(now.getEpochSecond(),jdbc.queryForObject("SELECT authenticated_at FROM acp_sessions WHERE sid=?",Long.class,ExecutionStore.bytes("ordering-session")));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit",Integer.class));
    }
    @Test void independentWorkersPermitReversedClockSecondArrivalWithoutSharingSessionState() {
        var now=java.time.Instant.parse("2026-10-17T00:00:00Z");
        var event=authenticationAt(now,"event-only");var earlier=workerIdentity(event,0);var later=workerIdentity(event,1);
        assertNotEquals(earlier.getClaimAsString("sid"),later.getClaimAsString("sid"));
        assertEquals(earlier.getClaims().get("auth_time"),later.getClaims().get("auth_time"));
        new SessionGate(model,jdbc,new DataSourceTransactionManager(ds),java.time.Clock.fixed(now.plusSeconds(1),java.time.ZoneOffset.UTC)).require(later);
        new SessionGate(model,jdbc,new DataSourceTransactionManager(ds),java.time.Clock.fixed(now,java.time.ZoneOffset.UTC)).require(earlier);
        assertEquals(2,jdbc.queryForObject("SELECT count(*) FROM acp_sessions",Integer.class));
    }
    @Test void sharedAuthenticationRemainsValidAcrossClockSecondBoundary() {
        var now=java.time.Instant.parse("2026-10-17T00:00:00Z");
        var jwt=authenticationAt(now,"shared-ordering-session");
        new SessionGate(model,jdbc,new DataSourceTransactionManager(ds),java.time.Clock.fixed(now,java.time.ZoneOffset.UTC)).require(jwt);
        var later=new SessionGate(model,jdbc,new DataSourceTransactionManager(ds),java.time.Clock.fixed(now.plusSeconds(1),java.time.ZoneOffset.UTC));
        later.require(jwt);later.require(jwt);
        assertEquals(now.getEpochSecond(),jdbc.queryForObject("SELECT authenticated_at FROM acp_sessions WHERE sid=?",Long.class,ExecutionStore.bytes("shared-ordering-session")));
        assertEquals(now.plusSeconds(1).getEpochSecond(),jdbc.queryForObject("SELECT last_seen FROM acp_sessions WHERE sid=?",Long.class,ExecutionStore.bytes("shared-ordering-session")));
    }
'''.replace('LIFECYCLE', '"LIFECYCLE-ENT-PAYMENT"' if domain == 'payment' else '"LIFECYCLE-CASE"')
    return text.rstrip()[:-1] + tests + '}\n'
