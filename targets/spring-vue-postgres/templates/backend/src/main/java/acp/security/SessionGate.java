package acp.security;

import acp.infrastructure.TargetModel;
import acp.infrastructure.ExecutionStore;
import java.time.Clock;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

/** Signed issuer claims plus durable, server-side session activity/revocation. */
@Component
public final class SessionGate {
    private final TargetModel model;
    private final JdbcTemplate jdbc;
    private final TransactionTemplate transaction;
    private final Clock clock;
    @org.springframework.beans.factory.annotation.Autowired
    public SessionGate(TargetModel model, JdbcTemplate jdbc, PlatformTransactionManager manager) {
        this(model,jdbc,manager,Clock.systemUTC());
    }
    public SessionGate(TargetModel model, JdbcTemplate jdbc, PlatformTransactionManager manager, Clock clock) {
        this.model=model; this.jdbc=jdbc; this.clock=clock;
        transaction=new TransactionTemplate(manager);
        transaction.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    }
    public void require(Jwt jwt) {
        if (jwt==null || blank(jwt.getSubject()) || blank(jwt.getClaimAsString("tenant")) || blank(jwt.getClaimAsString("sid"))) deny();
        long now=clock.instant().getEpochSecond();
        Object raw=jwt.getClaims().get("auth_time");
        if (!(raw instanceof Long) && !(raw instanceof Integer)) deny();
        long authenticated=((Number)raw).longValue();
        if (authenticated<0 || authenticated>now || jwt.getExpiresAt()==null || !jwt.getExpiresAt().isAfter(clock.instant())) deny();
        var methods=jwt.getClaimAsStringList("amr");
        if (methods==null) deny();
        Set<String> factors=new HashSet<>(methods);
        for(var authentication:model.nodes("AuthenticationModel")) {
            var d=authentication.path("data");
            Set<String> needed=new HashSet<>();
            for(var mechanism:d.path("mechanisms")) {
                String factor=switch(mechanism.asText()) {
                    case "KNOWLEDGE" -> "pwd";
                    case "POSSESSION" -> "otp";
                    case "INHERENCE" -> "fpt";
                    default -> throw new AccessDeniedException("AUTHENTICATION_MECHANISM");
                };
                needed.add(factor);
            }
            if (!factors.containsAll(needed) || (d.path("assurance").asText().equals("MULTI_FACTOR") && needed.size()<2)) deny();
        }
        transaction.execute(status -> {
            byte[] tenant=ExecutionStore.bytes(jwt.getClaimAsString("tenant")), subject=ExecutionStore.bytes(jwt.getSubject()), sid=ExecutionStore.bytes(jwt.getClaimAsString("sid"));
            jdbc.update("INSERT INTO acp_sessions(tenant,subject,sid,started_at,last_seen,authenticated_at,revoked) VALUES(?,?,?,?,?,?,false) ON CONFLICT DO NOTHING", tenant,subject,sid,authenticated,authenticated,authenticated);
            Map<String,Object> row=jdbc.queryForMap("SELECT * FROM acp_sessions WHERE tenant=? AND subject=? AND sid=? FOR UPDATE",tenant,subject,sid);
            long started=((Number)row.get("started_at")).longValue(), last=((Number)row.get("last_seen")).longValue(), previousAuth=((Number)row.get("authenticated_at")).longValue();
            if (Boolean.TRUE.equals(row.get("revoked")) || authenticated<previousAuth || last>now || started>now) deny();
            for(var policy:model.nodes("SessionPolicy")) {
                var d=policy.path("data");
                if (now-started>=d.path("absoluteSeconds").asLong() || now-last>=d.path("idleSeconds").asLong() || now-authenticated>=d.path("reauthSeconds").asLong()) deny();
            }
            jdbc.update("UPDATE acp_sessions SET last_seen=?,authenticated_at=? WHERE tenant=? AND subject=? AND sid=?",now,authenticated,tenant,subject,sid);
            return null;
        });
    }
    private static boolean blank(String value) { return value==null || value.isBlank(); }
    private static void deny() { throw new AccessDeniedException("AUTHENTICATION_SESSION_DENIED"); }
}
