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
    method = method.replace(DECLARATION, 'close();due();var runtime=lifecycle();var jwt=identity("tenant-one","fixture:operator");try(var pool=', 1)
    method = method.replace(WORKER_IDENTITY, 'workerJwt,release());}));}gate.countDown();', 1)
    loop = 'for(int i=0;i<2;i++)calls.add(pool.submit('
    if method.count(loop) != 1:
        raise ValueError('SEALED_PRIVACY_FIXTURE_LOOP_CHANGED')
    method = method.replace(loop, 'for(int i=0;i<2;i++){var workerJwt=workerIdentity(jwt,i);calls.add(pool.submit(', 1)
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
