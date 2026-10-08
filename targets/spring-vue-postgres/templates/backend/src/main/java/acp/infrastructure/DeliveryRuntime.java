package acp.infrastructure;

import java.math.*;
import java.util.*;
import org.springframework.jdbc.core.*;
import org.springframework.transaction.*;
import org.springframework.transaction.support.*;

/** Durable AT_LEAST_ONCE / PER_AGGREGATE profile. External transport is a port. */
public final class DeliveryRuntime {
    public interface Transport { boolean send(Occurrence occurrence); }
    public record Occurrence(String id,String tenant,String aggregate,String resource,String event,int revision,byte[] payload) {}
    public enum Result { EMPTY, BUSY, UNPROVEN, ACKNOWLEDGED, RETRY, UNSATISFIED }
    private final JdbcTemplate jdbc;private final InvocationCore.Time clock;private final Transport transport;
    private final TransactionTemplate tx;private final TargetModel model;
    public DeliveryRuntime(JdbcTemplate jdbc,PlatformTransactionManager manager,TargetModel model,InvocationCore.Time clock,Transport transport) {
        this.jdbc=jdbc;this.model=model;this.clock=clock;this.transport=Objects.requireNonNull(transport);
        tx=new TransactionTemplate(manager);tx.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        if(!"on".equals(jdbc.queryForObject("SHOW track_commit_timestamp",String.class)))throw new IllegalStateException("COMMIT_PROOF_REQUIRED");
    }
    private static String encode(Object value){try{return new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(value);}catch(Exception e){throw new IllegalArgumentException("DELIVERY_IDENTITY");}}
    private static BigInteger number(Object value){return new BigDecimal(value.toString()).toBigIntegerExact();}
    private BigInteger commit(Map<String,Object> row) {
        if(row.get("commit_ns")!=null)return number(row.get("commit_ns"));
        BigInteger xid=number(row.get("commit_xid"));
        BigInteger current=new BigInteger(jdbc.queryForObject("SELECT pg_snapshot_xmax(pg_current_snapshot())::text",String.class));
        if(current.subtract(xid).compareTo(BigInteger.ONE.shiftLeft(31))>=0)return null;
        Object value=jdbc.queryForObject("SELECT (extract(epoch FROM pg_xact_commit_timestamp(?::xid))*1000000000)::numeric",BigDecimal.class,xid.mod(BigInteger.ONE.shiftLeft(32)).toString());
        if(value==null)return null;
        BigInteger instant=number(value);tx.execute(s->{jdbc.update("UPDATE acp_outbox SET commit_ns=? WHERE id=? AND commit_ns IS NULL",new BigDecimal(instant),row.get("id"));return null;});return instant;
    }
    /** Each poll attempts only the earliest outstanding position of one aggregate. */
    public Result poll(String tenant,String aggregate,String resource) {
        String group=encode(List.of(tenant,aggregate,resource));
        return jdbc.execute((ConnectionCallback<Result>)connection->{
            boolean acquired;
            try(var ps=connection.prepareStatement("SELECT pg_try_advisory_lock(hashtextextended(?,0))")){ps.setString(1,group);try(var rs=ps.executeQuery()){rs.next();acquired=rs.getBoolean(1);}}
            if(!acquired)return Result.BUSY;
            try{return attempt(tenant,aggregate,resource);}
            finally{try(var ps=connection.prepareStatement("SELECT pg_advisory_unlock(hashtextextended(?,0))")){ps.setString(1,group);ps.execute();}}
        });
    }
    private Result attempt(String tenant,String aggregate,String resource) {
        // A legacy unknown commit is not silently overtaken after upgrade.
        if(jdbc.queryForObject("SELECT count(*) FROM acp_outbox WHERE tenant=? AND resource=? AND delivery_status='LEGACY_UNPROVEN'",Long.class,ExecutionStore.bytes(tenant),ExecutionStore.bytes(resource))>0)return Result.UNPROVEN;
        var rows=jdbc.queryForList("SELECT * FROM acp_outbox WHERE tenant=? AND aggregate_id=? AND resource=? AND delivery_status IN ('PENDING','CLAIMED') ORDER BY commit_sequence,step_ordinal,emission_ordinal LIMIT 1",ExecutionStore.bytes(tenant),aggregate,ExecutionStore.bytes(resource));
        if(rows.isEmpty())return Result.EMPTY;
        var row=rows.getFirst();String id=(String)row.get("id");BigInteger committed=commit(row);if(committed==null)return Result.UNPROVEN;
        var event=model.node((String)row.get("event"));var policy=model.node(event.path("data").path("delivery").path("id").asText()).path("data");
        BigInteger deadline=committed.add(BigInteger.valueOf(policy.path("windowSeconds").asLong()).multiply(InvocationCore.BILLION));
        BigInteger started=clock.now();if(started.compareTo(committed)<0)throw new InvocationCore.Outcome("CLOCK_REVERSED");
        if(started.compareTo(deadline)>=0){expire(id);return Result.UNSATISFIED;}
        int attempt=((Number)row.get("attempts")).intValue()+1;String owner=UUID.randomUUID().toString();
        tx.execute(s->{
            jdbc.update("UPDATE acp_delivery_attempt SET result='UNCERTAIN' WHERE occurrence=? AND finished_ns IS NULL",id);
            if(jdbc.update("UPDATE acp_outbox SET delivery_status='CLAIMED',claim_owner=?,attempts=? WHERE id=? AND delivery_status IN ('PENDING','CLAIMED')",owner,attempt,id)!=1)throw new IllegalStateException("DELIVERY_FENCE");
            jdbc.update("INSERT INTO acp_delivery_attempt(occurrence,attempt,started_ns,result) VALUES(?,?,?,'STARTED')",id,attempt,new BigDecimal(started));return null;
        });
        boolean acknowledged=false;String result="NO_ACK";
        java.util.concurrent.ExecutorService sender=java.util.concurrent.Executors.newVirtualThreadPerTaskExecutor();
        BigInteger dispatch=clock.now();
        if(dispatch.compareTo(started)<0){sender.shutdown();throw new InvocationCore.Outcome("CLOCK_REVERSED");}
        try {
            if(dispatch.compareTo(deadline)>=0)result="EXPIRED_BEFORE_SEND";
            else {
                var sent=sender.submit(()->transport.send(new Occurrence(id,tenant,aggregate,resource,(String)row.get("event"),((Number)row.get("event_revision")).intValue(),(byte[])row.get("payload"))));
                try {acknowledged=sent.get(deadline.subtract(dispatch).min(InvocationCore.BILLION).longValueExact(),java.util.concurrent.TimeUnit.NANOSECONDS);result=acknowledged?"ACK":"NO_ACK";}
                catch(java.util.concurrent.TimeoutException e){sent.cancel(true);result="TRANSPORT_TIMEOUT";}
                catch(InterruptedException e){Thread.currentThread().interrupt();sent.cancel(true);result="TRANSPORT_INTERRUPTED";}
                catch(java.util.concurrent.ExecutionException e){if(e.getCause() instanceof Error fatal)throw fatal;result="TRANSPORT_FAILURE";}
            }
        }finally{sender.shutdown();}
        // Error/process death deliberately leaves the persisted claim uncertain.
        BigInteger finished=clock.now();if(finished.compareTo(started)<0)throw new InvocationCore.Outcome("CLOCK_REVERSED");
        boolean timely=finished.compareTo(deadline)<0;String state=!timely?"UNSATISFIED":acknowledged?"ACKNOWLEDGED":"PENDING";
        boolean ack=acknowledged;String outcome=!timely&&ack?"LATE_ACK":result;
        tx.execute(s->{
            jdbc.update("UPDATE acp_delivery_attempt SET finished_ns=?,result=?,acknowledged=? WHERE occurrence=? AND attempt=?",new BigDecimal(finished),outcome,ack,id,attempt);
            if(jdbc.update("UPDATE acp_outbox SET delivery_status=?,claim_owner=NULL WHERE id=? AND claim_owner=?",state,id,owner)!=1)throw new IllegalStateException("DELIVERY_FENCE");return null;
        });
        return "ACKNOWLEDGED".equals(state)?Result.ACKNOWLEDGED:"UNSATISFIED".equals(state)?Result.UNSATISFIED:Result.RETRY;
    }
    private void expire(String id){tx.execute(s->{jdbc.update("UPDATE acp_outbox SET delivery_status='UNSATISFIED',claim_owner=NULL WHERE id=?",id);return null;});}
}
