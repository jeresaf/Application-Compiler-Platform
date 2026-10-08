package acp.infrastructure;

import acp.security.*;
import acp.domain.Expressions;
import java.math.*;
import java.util.*;
import org.springframework.jdbc.core.*;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.*;
import org.springframework.transaction.support.*;

/** Management contract 1.0.0. No domain UseCase or implicit legal-hold release. */
public final class LifecycleRuntime {
    public record Snapshot(Map<String,Object> record,long version,String state) {}
    public interface Actions { Snapshot lock(String lifecycle,String resource,Jwt principal); void apply(String lifecycle,String resource,Jwt principal); }
    public record Release(String hold,int revision) {}
    public enum Result { BUSY, UNPROVEN, NOT_RETAINED, NOT_DUE, BLOCKED_HOLD, COMPLETED, INDETERMINATE }
    private final JdbcTemplate jdbc;private final TargetModel model;private final ApplicationPolicy policy;private final Expressions expressions;
    private final InvocationCore.Time clock;private final Actions actions;private final TransactionTemplate tx,isolated;
    public LifecycleRuntime(JdbcTemplate jdbc,PlatformTransactionManager manager,TargetModel model,ApplicationPolicy policy,Expressions expressions,InvocationCore.Time clock,Actions actions) {
        this.jdbc=jdbc;this.model=model;this.policy=policy;this.expressions=expressions;this.clock=clock;this.actions=actions;
        tx=new TransactionTemplate(manager);tx.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        isolated=new TransactionTemplate(manager);isolated.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        if(!"on".equals(jdbc.queryForObject("SHOW track_commit_timestamp",String.class)))throw new IllegalStateException("COMMIT_PROOF_REQUIRED");
    }
    private static BigInteger integer(Object n){return new BigDecimal(n.toString()).toBigIntegerExact();}
    private static String encode(Object o){try{return new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(o);}catch(Exception e){throw new IllegalArgumentException("LIFECYCLE_IDENTITY");}}
    private Object[] key(String life,int revision,String tenant,String resource){return new Object[]{life,revision,ExecutionStore.bytes(tenant),ExecutionStore.bytes(resource)};}
    private BigInteger anchor(Map<String,Object> row,Object[] key) {
        if(row.get("anchor_ns")!=null)return integer(row.get("anchor_ns"));
        if(row.get("anchor_xid")==null)return null;
        BigInteger xid=integer(row.get("anchor_xid")),current=new BigInteger(jdbc.queryForObject("SELECT pg_snapshot_xmax(pg_current_snapshot())::text",String.class));
        if(current.subtract(xid).signum()<0 || current.subtract(xid).compareTo(BigInteger.ONE.shiftLeft(31))>=0)return null;
        var value=jdbc.queryForObject("SELECT (extract(epoch FROM pg_xact_commit_timestamp(?::xid))*1000000000)::numeric",BigDecimal.class,xid.mod(BigInteger.ONE.shiftLeft(32)).toString());
        if(value==null)return null;
        isolated.execute(s->{jdbc.update("UPDATE acp_lifecycle_anchor SET anchor_ns=? WHERE lifecycle=? AND revision=? AND tenant=? AND resource=? AND anchor_ns IS NULL",value,key[0],key[1],key[2],key[3]);return null;});return integer(value);
    }
    /** Automatic polling observes eligibility only; literal-true holds never release. */
    public Result observe(String life,String tenant,String resource){return execute(life,tenant,resource,null,Set.of());}
    /** Every management action requires an authenticated tenant principal; releases are explicit exact references. */
    public Result dispose(String life,String resource,Jwt principal,Set<Release> releases){policy.actor(principal);return execute(life,principal.getClaimAsString("tenant"),resource,principal,Set.copyOf(releases));}
    private Result execute(String life,String tenant,String resource,Jwt principal,Set<Release> releases) {
        var node=model.node(life);if(!node.path("kind").asText().equals("DataLifecycle"))throw new IllegalArgumentException("LIFECYCLE_REQUIRED");
        int revision=node.path("revision").asInt();var data=node.path("data");Object[] key=key(life,revision,tenant,resource);
        String fence=encode(List.of(life,revision,tenant,resource));
        return jdbc.execute((ConnectionCallback<Result>)connection->{
            try(var p=connection.prepareStatement("SELECT pg_try_advisory_lock(hashtextextended(?,3))")){p.setString(1,fence);try(var r=p.executeQuery()){r.next();if(!r.getBoolean(1))return Result.BUSY;}}
            try {
                var rows=jdbc.queryForList("SELECT * FROM acp_lifecycle_anchor WHERE lifecycle=? AND revision=? AND tenant=? AND resource=?",key);
                if(rows.isEmpty())return Result.UNPROVEN;var row=rows.getFirst();
                if("COMPLETED".equals(row.get("status")))return Result.COMPLETED;
                BigInteger now=clock.now();if(row.get("last_ns")!=null && now.compareTo(integer(row.get("last_ns")))<0)throw new InvocationCore.Outcome("CLOCK_REVERSED");
                BigInteger committed=anchor(row,key);if(committed==null)return Result.UNPROVEN;
                if(now.compareTo(committed)<0)throw new InvocationCore.Outcome("CLOCK_REVERSED");
                if(row.get("attempt_xid")!=null) {
                    String status=jdbc.queryForObject("SELECT pg_xact_status(?::xid8)",String.class,row.get("attempt_xid"));
                    if(!Set.of("committed","aborted").contains(status==null?"unknown":status))return Result.INDETERMINATE;
                }
                var retention=model.node(data.path("retention").path("id").asText()).path("data");var deletion=model.node(data.path("deletion").path("id").asText()).path("data");
                if(now.compareTo(committed.add(BigInteger.valueOf(retention.path("minimumSeconds").asLong()).multiply(InvocationCore.BILLION)))<0)return record(key,now,Result.NOT_RETAINED);
                if(now.compareTo(committed.add(BigInteger.valueOf(deletion.path("afterSeconds").asLong()).multiply(InvocationCore.BILLION)))<0)return record(key,now,Result.NOT_DUE);
                if(principal==null)return record(key,now,Result.BLOCKED_HOLD);
                // Completed status and domain effects commit together. A separate
                // durable attempt XID is stored before any effect, never a lease.
                record(key,now,Result.INDETERMINATE);
                try {
                    Result result=tx.execute(s->{
                        var snapshot=actions.lock(life,resource,principal);var actor=policy.actor(principal);
                        if(!Objects.equals(snapshot.record().get(model.node(data.path("resource").path("id").asText()).path("data").path("tenantField").path("id").asText()),tenant))throw new org.springframework.security.access.AccessDeniedException("LIFECYCLE_SCOPE");
                        if(!row.get("closing_state").equals(snapshot.state()))throw new IllegalStateException("LIFECYCLE_STATE_CHANGED");
                        // Recheck time after waiting for the domain root lock.
                        BigInteger actionNow=clock.now();if(actionNow.compareTo(now)<0)throw new InvocationCore.Outcome("CLOCK_REVERSED");
                        BigInteger due=committed.add(BigInteger.valueOf(Math.max(retention.path("minimumSeconds").asLong(),deletion.path("afterSeconds").asLong())).multiply(InvocationCore.BILLION));
                        if(actionNow.compareTo(due)<0)throw new IllegalStateException("LIFECYCLE_NOT_DUE");
                        Set<Release> valid=new HashSet<>();
                        for(var ref:data.path("holds"))valid.add(new Release(ref.path("id").asText(),ref.path("revision").asInt()));
                        if(!valid.containsAll(releases))throw new org.springframework.security.access.AccessDeniedException("HOLD_RELEASE_REFERENCE");
                        for(var holdRef:data.path("holds")) {
                            var hold=model.node(holdRef.path("id").asText());var hd=hold.path("data");var release=new Release(hold.path("id").asText(),hold.path("revision").asInt());valid.add(release);
                            if(Boolean.TRUE.equals(expressions.evaluate(hd.path("condition"),snapshot.record(),actor))) {
                                if(!releases.contains(release))return Result.BLOCKED_HOLD;
                                policy.requirePermission(hd.path("release").path("id").asText(),snapshot.record(),principal);
                            }
                        }
                        if(!valid.containsAll(releases))throw new org.springframework.security.access.AccessDeniedException("HOLD_RELEASE_REFERENCE");
                        String xid=jdbc.queryForObject("SELECT pg_current_xact_id()::text",String.class);
                        isolated.execute(t->{jdbc.update("UPDATE acp_lifecycle_anchor SET attempt_xid=? WHERE lifecycle=? AND revision=? AND tenant=? AND resource=?",xid,key[0],key[1],key[2],key[3]);jdbc.update("INSERT INTO acp_lifecycle_attempt(lifecycle,revision,tenant,resource,observed_ns,result,action_xid) VALUES(?,?,?,?,?,'STARTED',?)",key[0],key[1],key[2],key[3],new BigDecimal(actionNow),xid);return null;});
                        for(Release release:releases) {
                            var hold=model.node(release.hold()).path("data");jdbc.update("INSERT INTO acp_lifecycle_release_audit(lifecycle,revision,tenant,resource,hold,hold_revision,permission,permission_revision,subject,action_xid) VALUES(?,?,?,?,?,?,?,?,?,?)",key[0],key[1],key[2],key[3],release.hold(),release.revision(),hold.path("release").path("id").asText(),hold.path("release").path("revision").asInt(),ExecutionStore.bytes(principal.getSubject()),xid);
                        }
                        actions.apply(life,resource,principal);
                        jdbc.update("UPDATE acp_lifecycle_anchor SET status='COMPLETED',completed_ns=? WHERE lifecycle=? AND revision=? AND tenant=? AND resource=?",new BigDecimal(actionNow),key[0],key[1],key[2],key[3]);
                        jdbc.update("UPDATE acp_lifecycle_attempt SET result='COMPLETED' WHERE action_xid=?",xid);return Result.COMPLETED;
                    });
                    return result==Result.COMPLETED?result:record(key,now,result);
                }catch(RuntimeException failure){record(key,now,Result.INDETERMINATE);throw new InvocationCore.Outcome("LIFECYCLE_ACTION_FAILED");}
            }finally{try(var p=connection.prepareStatement("SELECT pg_advisory_unlock(hashtextextended(?,3))")){p.setString(1,fence);p.execute();}}
        });
    }
    private Result record(Object[] key,BigInteger now,Result result){isolated.execute(s->{jdbc.update("UPDATE acp_lifecycle_anchor SET last_ns=?,status=? WHERE lifecycle=? AND revision=? AND tenant=? AND resource=? AND status<>'COMPLETED'",new BigDecimal(now),result.name(),key[0],key[1],key[2],key[3]);jdbc.update("INSERT INTO acp_lifecycle_attempt(lifecycle,revision,tenant,resource,observed_ns,result) VALUES(?,?,?,?,?,?)",key[0],key[1],key[2],key[3],new BigDecimal(now),result.name());return null;});return result;}
    public void poll(){for(var row:jdbc.queryForList("SELECT lifecycle,tenant,resource FROM acp_lifecycle_anchor WHERE status<>'COMPLETED'"))observe((String)row.get("lifecycle"),ExecutionStore.text((byte[])row.get("tenant")),ExecutionStore.text((byte[])row.get("resource")));}
}
