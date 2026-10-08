package acp.domain;

import acp.infrastructure.TargetModel;
import acp.security.SessionGate;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.*;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.oauth2.jwt.Jwt;
import static org.junit.jupiter.api.Assertions.*;

class SessionGateTest {
    static final Instant NOW=Instant.parse("2026-10-08T12:00:00Z");
    TargetModel model; JdbcTemplate jdbc; DataSourceTransactionManager manager;
    @BeforeEach void setup() throws Exception {
        String url=System.getenv("ACP_TEST_DATABASE_URL"); assertNotNull(url,"Database required; no skip");
        String user=System.getenv("ACP_TEST_DATABASE_USER"), password=System.getenv("ACP_TEST_DATABASE_PASSWORD");
        var flyway=Flyway.configure().dataSource(url,user,password).schemas("acp_phase6_sessions_test").defaultSchema("acp_phase6_sessions_test").cleanDisabled(false).load();
        flyway.clean(); flyway.migrate();
        var ds=new DriverManagerDataSource(url+(url.contains("?")?"&":"?")+"currentSchema=acp_phase6_sessions_test",user,password);
        jdbc=new JdbcTemplate(ds); manager=new DataSourceTransactionManager(ds); model=new TargetModel();
    }
    SessionGate gate(Instant time) { return new SessionGate(model,jdbc,manager,Clock.fixed(time,ZoneOffset.UTC)); }
    Jwt token(Instant authentication, List<String> methods) {
        return Jwt.withTokenValue("test-authority-only").header("alg","none").subject("fixture:operator")
            .claim("tenant","tenant-one").claim("sid","session-one").claim("amr",methods)
            .claim("auth_time",authentication.getEpochSecond()).issuedAt(authentication).expiresAt(NOW.plusSeconds(86400)).build();
    }
    long policy(String key) { return model.nodes("SessionPolicy").getFirst().path("data").path(key).asLong(); }
    @Test void multifactorIsRequiredAndActivityIsDurableAndSliding() {
        assertThrows(AccessDeniedException.class, () -> gate(NOW).require(token(NOW,List.of("pwd"))));
        var jwt=token(NOW,List.of("pwd","otp")); gate(NOW).require(jwt);
        long interval=policy("idleSeconds")/2;
        gate(NOW.plusSeconds(interval)).require(jwt);
        gate(NOW.plusSeconds(interval*2)).require(jwt);
        assertEquals(NOW.getEpochSecond()+interval*2,jdbc.queryForObject("SELECT last_seen FROM acp_sessions",Long.class));
    }
    @Test void idleAbsoluteReauthenticationAndRevocationAreIndependentGates() {
        var jwt=token(NOW,List.of("pwd","otp")); gate(NOW).require(jwt);
        assertThrows(AccessDeniedException.class, () -> gate(NOW.plusSeconds(policy("idleSeconds"))).require(jwt));
        jdbc.update("UPDATE acp_sessions SET started_at=?",NOW.getEpochSecond()-policy("absoluteSeconds"));
        assertThrows(AccessDeniedException.class, () -> gate(NOW).require(jwt));
        jdbc.update("UPDATE acp_sessions SET started_at=?,authenticated_at=?",NOW.getEpochSecond()-policy("reauthSeconds")-1,NOW.getEpochSecond()-policy("reauthSeconds"));
        var stale=token(NOW.minusSeconds(policy("reauthSeconds")),List.of("pwd","otp"));
        assertThrows(AccessDeniedException.class, () -> gate(NOW).require(stale));
        jdbc.update("UPDATE acp_sessions SET started_at=?,authenticated_at=?,revoked=true",NOW.getEpochSecond(),NOW.getEpochSecond());
        assertThrows(AccessDeniedException.class, () -> gate(NOW).require(jwt));
    }
    @Test void unauthenticatedAndFutureCredentialsCannotInitializeASession() {
        assertThrows(AccessDeniedException.class, () -> gate(NOW).require(null));
        assertThrows(AccessDeniedException.class, () -> gate(NOW).require(token(NOW.plusSeconds(1),List.of("pwd","otp"))));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_sessions",Integer.class));
    }
}
