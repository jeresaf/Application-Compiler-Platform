package acp.infrastructure;

import acp.api.FailureMapping;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigInteger;
import java.time.Instant;
import java.util.*;
import java.util.function.Supplier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

/** Target invocation profile 1.0. No scheduler, transport or production IAM. */
@Component
public final class InvocationCore {
    public interface Time { BigInteger now(); void sleep(long seconds); }
    public static final class SystemTime implements Time {
        public BigInteger now() { Instant t=Instant.now(); return BigInteger.valueOf(t.getEpochSecond()).multiply(BILLION).add(BigInteger.valueOf(t.getNano())); }
        public void sleep(long seconds) { try { Thread.sleep(Math.multiplyExact(seconds,1000)); } catch(InterruptedException e) { Thread.currentThread().interrupt(); throw new Outcome("INTERRUPTED"); } }
    }
    public static final BigInteger BILLION=BigInteger.valueOf(1_000_000_000L);
    public static final class Outcome extends RuntimeException { public Outcome(String code) { super(code); } }
    public record Call(String operation,int revision,String policy,int policyRevision,String resource,
                       String typedKey,String typedInput,int windowSeconds) {}
    private record Claim(Call call,byte[] identity,String owner,JsonNode replay) {}
    private final class Attempt {
        final List<Call> calls; final List<Claim> claims; final Jwt jwt;
        Attempt(List<Call> calls,List<Claim> claims,Jwt jwt) {this.calls=calls;this.claims=claims;this.jwt=jwt;for(Claim c:claims)if(c.replay()!=null)replay.put(c.call().operation(),c.replay());}
        void enter(String operation) {
            Claim claim=claims.stream().filter(c->c.call().operation().equals(operation)).findFirst().orElse(null);
            if(claim==null) {
                Call call=calls.stream().filter(c->c.operation().equals(operation)).findFirst().orElseThrow(()->new Outcome("UNDECLARED_INVOCATION"));
                BigInteger instant=time.now();charge(operation,jwt,instant);claim=reserve(call,jwt,instant);claims.add(claim);
                if(claim.replay()!=null)replay.put(operation,claim.replay());
            }
            if(claim.owner()!=null) {
                String xid=jdbc.queryForObject("SELECT pg_current_xact_id()::text",String.class);
                Claim selected=claim;
                isolated.execute(status -> {if(jdbc.update("UPDATE acp_idempotency SET attempt_xid=? WHERE identity=? AND owner=? AND status='IN_FLIGHT'",xid,selected.identity(),selected.owner())!=1)throw new Outcome("FENCE_REJECTED");return null;});
                var row=jdbc.queryForMap("SELECT owner,status FROM acp_idempotency WHERE identity=? FOR UPDATE",claim.identity());
                if(!claim.owner().equals(row.get("owner")) || !"IN_FLIGHT".equals(row.get("status")))throw new Outcome("FENCE_REJECTED");
            }
        }
        final Map<String,JsonNode> replay=new HashMap<>(); final Map<String,Object> result=new HashMap<>();
    }
    // Only transient execution context; all authoritative state is in PostgreSQL.
    private static final ThreadLocal<Attempt> CURRENT=new ThreadLocal<>();
    private final JdbcTemplate jdbc; private final TargetModel model; private final ObjectMapper mapper=new ObjectMapper();
    private final TransactionTemplate isolated,boundary; private final Time time;
    @org.springframework.beans.factory.annotation.Autowired
    public InvocationCore(JdbcTemplate jdbc,TargetModel model,PlatformTransactionManager manager) { this(jdbc,model,manager,new SystemTime()); }
    public InvocationCore(JdbcTemplate jdbc,TargetModel model,PlatformTransactionManager manager,Time time) {
        this.jdbc=jdbc;this.model=model;this.time=time;
        isolated=new TransactionTemplate(manager); isolated.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        boundary=new TransactionTemplate(manager); boundary.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
    }
    public static <T> T replay(String operation,Class<T> output) {
        Attempt a=CURRENT.get(); if(a==null)return null; a.enter(operation); if(!a.replay.containsKey(operation))return null;
        try { return new ObjectMapper().treeToValue(a.replay.get(operation),output); } catch(Exception e) { throw new Outcome("STORED_RESULT_INVALID"); }
    }
    public static <T> T capture(String operation,T result) { Attempt a=CURRENT.get();if(a!=null)a.result.put(operation,result); return result; }
    private static byte[] bytes(String value) { return ExecutionStore.bytes(value); }
    private static BigInteger integer(Object n) { return new java.math.BigDecimal(n.toString()).toBigIntegerExact(); }
    private static String canonical(JsonNode n) {
        if(n.isObject()) { List<String> keys=new ArrayList<>(); n.fieldNames().forEachRemaining(keys::add);Collections.sort(keys);List<String> parts=new ArrayList<>();for(String k:keys)parts.add(quote(k)+":"+canonical(n.get(k)));return "{"+String.join(",",parts)+"}"; }
        if(n.isArray()) { List<String> values=new ArrayList<>();n.forEach(v->values.add(canonical(v)));return "["+String.join(",",values)+"]"; }
        return n.toString();
    }
    private static String quote(String s) { try { return new ObjectMapper().writeValueAsString(s); } catch(Exception e) { throw new Outcome("TYPED_VALUE_INVALID"); } }
    /** Generator supplies the exact type declaration and typed, normalized value. */
    public static String typed(String type,Object value) {
        try { return "{\"type\":"+canonical(new ObjectMapper().readTree(type))+",\"value\":"+canonical(new ObjectMapper().valueToTree(value))+"}"; }
        catch(Exception e) { throw new Outcome("TYPED_VALUE_INVALID"); }
    }
    private static byte[] digest(String value) { try { return java.security.MessageDigest.getInstance("SHA-256").digest(bytes(value)); }catch(Exception e) { throw new Outcome("DIGEST_UNAVAILABLE"); } }
    public boolean token(String policy,int revision,String tenant,String actor,int requests,int seconds,int burst,BigInteger now) {
        if(now.signum()<0)throw new Outcome("SEMANTIC_TIME");
        return isolated.execute(status -> {
            byte[] key=digest(canonical(mapper.valueToTree(List.of(policy,revision,tenant,actor))));
            BigInteger denominator=BigInteger.valueOf(seconds).multiply(BILLION), capacity=BigInteger.valueOf(burst).multiply(denominator);
            jdbc.update("INSERT INTO acp_rate(identity,tokens,last_ns) VALUES(?,?,?) ON CONFLICT DO NOTHING",key,new java.math.BigDecimal(capacity),new java.math.BigDecimal(now));
            var row=jdbc.queryForMap("SELECT * FROM acp_rate WHERE identity=? FOR UPDATE",key);
            BigInteger last=integer(row.get("last_ns")); if(now.compareTo(last)<0)throw new Outcome("CLOCK_REVERSED");
            BigInteger tokens=integer(row.get("tokens")).add(now.subtract(last).multiply(BigInteger.valueOf(requests))).min(capacity);
            boolean allowed=tokens.compareTo(denominator)>=0;
            if(allowed)tokens=tokens.subtract(denominator);
            jdbc.update("UPDATE acp_rate SET tokens=?,last_ns=? WHERE identity=?",new java.math.BigDecimal(tokens),new java.math.BigDecimal(now),key);
            return allowed;
        });
    }
    /** Must be called only after generated session/authorization/tenant checks. */
    public void charge(String operation,Jwt jwt) { charge(operation,jwt,time.now()); }
    private void charge(String operation,Jwt jwt,BigInteger instant) {
        for(var rate:model.nodes("RatePolicy")) {
            var d=rate.path("data");var permission=model.node(d.path("permission").path("id").asText());
            if(!operation.equals(permission.path("data").path("action").path("id").asText()))continue;
            String actor="ACTOR".equals(d.path("partition").asText())?jwt.getSubject():"";
            if(!token(rate.path("id").asText(),rate.path("revision").asInt(),jwt.getClaimAsString("tenant"),actor,d.path("requests").asInt(),d.path("windowSeconds").asInt(),d.path("burst").asInt(),instant))throw new Outcome("RATE_DENIED");
        }
    }
    private BigInteger commitTime(Object xid) {
        // PostgreSQL's actual commit record, never arrival/worker completion.
        BigInteger full=integer(xid);
        BigInteger current=new BigInteger(jdbc.queryForObject("SELECT pg_snapshot_xmax(pg_current_snapshot())::text",String.class));
        // Never confuse a wrapped/reused xid with the original commit.
        if(current.subtract(full).compareTo(BigInteger.ONE.shiftLeft(31))>=0)return null;
        var rows=jdbc.queryForList("SELECT (extract(epoch FROM pg_xact_commit_timestamp(?::xid))*1000000000)::numeric AS ns",full.mod(BigInteger.ONE.shiftLeft(32)).toString());
        Object n=rows.getFirst().get("ns");return n==null?null:integer(n);
    }
    private Claim reserve(Call call,Jwt jwt,BigInteger now) {
        String tenant=jwt.getClaimAsString("tenant");
        byte[] identity=digest(canonical(mapper.valueToTree(List.of(call.policy(),call.policyRevision(),tenant,call.resource(),call.operation(),call.revision(),call.typedKey()))));
        byte[] input=digest("ACP\0acp-jcs-safe-v1\0canonical\0"+call.typedInput());String owner=UUID.randomUUID().toString();
        return isolated.execute(status -> {
            // A live domain transaction may hold the row lock. MVCC read returns
            // IN_PROGRESS immediately; no waiting for the original request.
            var existing=jdbc.queryForList("SELECT * FROM acp_idempotency WHERE identity=?",identity);
            if(!existing.isEmpty()) {
                var row=existing.getFirst(); String state=(String)row.get("status");
                if(!"COMMITTED_RESULT".equals(state)) {
                    Object attempt=row.get("attempt_xid");
                    String fact=attempt==null?null:jdbc.queryForObject("SELECT pg_xact_status(?::xid8)",String.class,attempt.toString());
                    if("aborted".equals(fact)) {
                        // Trusted PostgreSQL no-effect proof, not an elapsed lease.
                        jdbc.update("DELETE FROM acp_idempotency WHERE identity=? AND owner=? AND status='IN_FLIGHT'",identity,row.get("owner"));
                        int inserted=jdbc.update("INSERT INTO acp_idempotency(identity,input_digest,owner,status) VALUES(?,?,?,'IN_FLIGHT') ON CONFLICT DO NOTHING",identity,input,owner);
                        if(inserted!=1)conflictOrProgress(identity,input);
                        return new Claim(call,identity,owner,null);
                    }
                    if(!Arrays.equals(input,(byte[])row.get("input_digest")))throw new Outcome("IDEMPOTENCY_CONFLICT");
                    throw new Outcome("IN_PROGRESS");
                }
                BigInteger commit=row.get("commit_ns")==null?commitTime(row.get("commit_xid")):integer(row.get("commit_ns"));
                if(commit!=null && row.get("commit_ns")==null)jdbc.update("UPDATE acp_idempotency SET commit_ns=? WHERE identity=? AND owner=? AND status='COMMITTED_RESULT'",new java.math.BigDecimal(commit),identity,row.get("owner"));
                if(commit==null)throw new Outcome("IN_PROGRESS"); // unavailable proof never expires uncertainty
                if(now.compareTo(commit)<0)throw new Outcome("CLOCK_REVERSED");
                if(now.compareTo(commit.add(BigInteger.valueOf(call.windowSeconds()).multiply(BILLION)))<0) {
                    if(!Arrays.equals(input,(byte[])row.get("input_digest")))throw new Outcome("IDEMPOTENCY_CONFLICT");
                    try {return new Claim(call,identity,null,mapper.readTree(ExecutionStore.text((byte[])row.get("result"))));}catch(Exception e){throw new Outcome("STORED_RESULT_INVALID");}
                }
                // Recheck under lock at the exact half-open expiry boundary.
                jdbc.queryForMap("SELECT * FROM acp_idempotency WHERE identity=? FOR UPDATE",identity);
                jdbc.update("DELETE FROM acp_idempotency WHERE identity=? AND owner=? AND status='COMMITTED_RESULT'",identity,row.get("owner"));
            }
            int inserted=jdbc.update("INSERT INTO acp_idempotency(identity,input_digest,owner,status) VALUES(?,?,?,'IN_FLIGHT') ON CONFLICT DO NOTHING",identity,input,owner);
            if(inserted!=1)conflictOrProgress(identity,input);
            return new Claim(call,identity,owner,null);
        });
    }
    private void conflictOrProgress(byte[] identity,byte[] input) {
        var rows=jdbc.queryForList("SELECT input_digest FROM acp_idempotency WHERE identity=?",identity);
        if(!rows.isEmpty() && !Arrays.equals(input,(byte[])rows.getFirst().get("input_digest")))throw new Outcome("IDEMPOTENCY_CONFLICT");
        throw new Outcome("IN_PROGRESS");
    }
    public static String portable(RuntimeException error) {
        Throwable fault=error;
        // Exact JDBC adapter wrappers only; arbitrary subclasses/causes stay INTERNAL.
        if(Set.of("org.springframework.jdbc.UncategorizedSQLException","org.springframework.jdbc.CannotGetJdbcConnectionException","org.springframework.dao.DataAccessResourceFailureException").contains(error.getClass().getName()) && error.getCause()!=null)fault=error.getCause();
        return FailureMapping.map(fault).faultClass();
    }
    public <T> T invoke(List<Call> calls,String retryPolicy,Jwt jwt,Supplier<T> action) {
        if(!"on".equals(jdbc.queryForObject("SHOW track_commit_timestamp",String.class)))throw new Outcome("COMMIT_PROOF_REQUIRED");
        if(CURRENT.get()!=null)throw new Outcome("NESTED_INVOCATION");
        List<Claim> claims=new ArrayList<>();
        JsonNode retry=retryPolicy==null?null:model.node(retryPolicy).path("data");
        int max=retry==null?1:retry.path("maxAttempts").asInt();
        for(int attempt=1;;attempt++) {
            Attempt context=new Attempt(calls,claims,jwt);
            boolean[] rollback={false};
            try {
                CURRENT.set(context);
                return boundary.execute(status -> {
                    TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                        @Override public void afterCompletion(int completion) { rollback[0]=completion==STATUS_ROLLED_BACK; }
                    });
                    T result=action.get();
                    for(Claim c:claims)if(c.owner()!=null) {
                        Object output=context.result.get(c.call().operation());if(output==null)throw new Outcome("MISSING_TYPED_RESULT");
                        try {
                            jdbc.update("UPDATE acp_idempotency SET status='COMMITTED_RESULT',result=?,commit_xid=pg_current_xact_id()::text WHERE identity=? AND owner=?",bytes(mapper.writeValueAsString(output)),c.identity(),c.owner());
                        }catch(com.fasterxml.jackson.core.JsonProcessingException e){throw new Outcome("TYPED_RESULT_INVALID");}
                    }
                    return result;
                });
            } catch(RuntimeException error) {
                if(rollback[0] && error instanceof SemanticFailure f && eligible(f,retry) && attempt<max) {
                    BigInteger delay=BigInteger.valueOf(retry.path("initialSeconds").asLong()).multiply(BigInteger.valueOf(retry.path("multiplier").asLong()).pow(attempt-1)).min(BigInteger.valueOf(retry.path("maxDelaySeconds").asLong()));
                    time.sleep(delay.longValueExact()); continue;
                }
                if(rollback[0])clear(claims); // definitive transaction-manager rollback only
                // Unknown/indeterminate commit keeps durable IN_FLIGHT forever.
                throw error;
            } finally {CURRENT.remove();}
        }
    }
    public boolean eligible(SemanticFailure f,JsonNode retry) {
        if(retry==null || !"TRANSIENT".equals(f.envelope().category()) || !f.envelope().retryable())return false;
        var definition=model.node(f.envelope().failureId());
        if(definition.path("revision").asInt()!=f.envelope().failureRevision() || !definition.path("data").path("category").asText().equals(f.envelope().category()) || definition.path("data").path("retryable").asBoolean()!=f.envelope().retryable())return false;
        var operation=model.node(f.envelope().operationId());
        if(operation.path("revision").asInt()!=f.envelope().operationRevision())return false;
        boolean bound=false;
        for(var binding:operation.path("data").path("failureBindings"))if(binding.path("failure").path("id").asText().equals(f.envelope().failureId()) && binding.path("failure").path("revision").asInt()==f.envelope().failureRevision() && binding.path("stage").asText().equals(f.stage()))bound=true;
        if(!bound)return false;
        for(var ref:retry.path("failures"))if(ref.path("id").asText().equals(f.envelope().failureId()) && ref.path("revision").asInt()==f.envelope().failureRevision())return true;
        return false;
    }
    private void clear(List<Claim> claims) {
        isolated.execute(status -> {for(Claim c:claims)if(c.owner()!=null)jdbc.update("DELETE FROM acp_idempotency WHERE identity=? AND owner=? AND status='IN_FLIGHT'",c.identity(),c.owner());return null;});
    }
}
