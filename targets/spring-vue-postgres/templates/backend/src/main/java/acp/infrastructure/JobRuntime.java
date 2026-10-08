package acp.infrastructure;

import java.math.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.jdbc.core.*;
import org.springframework.transaction.*;
import org.springframework.transaction.support.*;
import org.springframework.security.oauth2.jwt.Jwt;

/** LOCAL_DAILY/SKIP durable scheduler. Polling time never defines occurrence identity. */
public final class JobRuntime {
    public static String principalKey(String job,int revision){return job+"@"+revision;}
    public interface PrincipalPort { Jwt resolve(String job,int revision,String opaqueHandle); }
    public interface Invocation { Object execute(String job,String occurrence,Jwt principal); }
    private final JdbcTemplate jdbc;private final TransactionTemplate tx;private final TargetModel model;
    private final InvocationCore.Time clock;private final PrincipalPort principals;private final Map<String,String> handles;
    private final Invocation invocation;private final PinnedSchedule schedule=new PinnedSchedule();
    public JobRuntime(JdbcTemplate jdbc,PlatformTransactionManager manager,TargetModel model,InvocationCore.Time clock,PrincipalPort principals,Map<String,String> handles,Invocation invocation) {
        this.jdbc=jdbc;this.model=model;this.clock=clock;this.principals=Objects.requireNonNull(principals);this.handles=Map.copyOf(handles);this.invocation=invocation;
        tx=new TransactionTemplate(manager);tx.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);
        for(var job:model.nodes("Job"))if(!handles.containsKey(principalKey(job.path("id").asText(),job.path("revision").asInt())) || handles.get(principalKey(job.path("id").asText(),job.path("revision").asInt())).isBlank())throw new IllegalStateException("JOB_PRINCIPAL_BINDING_REQUIRED");
    }
    private static BigInteger ns(Instant instant){return BigInteger.valueOf(instant.getEpochSecond()).multiply(InvocationCore.BILLION).add(BigInteger.valueOf(instant.getNano()));}
    private static Instant instant(BigInteger ns){var qr=ns.divideAndRemainder(InvocationCore.BILLION);if(qr[1].signum()<0){qr[0]=qr[0].subtract(BigInteger.ONE);qr[1]=qr[1].add(InvocationCore.BILLION);}return Instant.ofEpochSecond(qr[0].longValueExact(),qr[1].longValueExact());}
    private static BigInteger integer(Object n){return new BigDecimal(n.toString()).toBigIntegerExact();}
    private static String encode(Object x){try{return new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(x);}catch(Exception e){throw new IllegalArgumentException("JOB_IDENTITY");}}
    public void activate(String jobId,String tenant,BigInteger activation) {
        var job=model.node(jobId);int revision=job.path("revision").asInt();var sd=model.node(job.path("data").path("schedule").path("id").asText()).path("data");
        LocalDate date=schedule.dateAt(instant(activation),sd.path("timezone").asText());
        tx.execute(s->{
            jdbc.queryForObject("SELECT pg_advisory_xact_lock(hashtextextended(?,2))",Object.class,encode(List.of(jobId,revision,tenant)));
            var old=jdbc.queryForList("SELECT * FROM acp_scheduler WHERE job=? AND revision=? AND scope=? FOR UPDATE",jobId,revision,ExecutionStore.bytes(tenant));
            BigInteger previous=old.isEmpty()?null:integer(old.getFirst().get("activation_ns"));
            if(!old.isEmpty() && activation.compareTo(integer(old.getFirst().get("last_ns")))<0)throw new InvocationCore.Outcome("CLOCK_REVERSED");
            jdbc.update("INSERT INTO acp_job_skip_range(job,revision,scope,from_ns,to_ns) VALUES(?,?,?,?,?)",jobId,revision,ExecutionStore.bytes(tenant),previous==null?null:new BigDecimal(previous),new BigDecimal(activation));
            jdbc.update("UPDATE acp_job_occurrence SET status='SKIPPED' WHERE job=? AND revision=? AND scope=? AND status='SCHEDULED' AND scheduled_ns<?",jobId,revision,ExecutionStore.bytes(tenant),new BigDecimal(activation));
            jdbc.update("INSERT INTO acp_scheduler(job,revision,scope,activation_ns,last_ns,last_date) VALUES(?,?,?,?,?,?) ON CONFLICT(job,revision,scope) DO UPDATE SET activation_ns=EXCLUDED.activation_ns,last_ns=EXCLUDED.last_ns,last_date=EXCLUDED.last_date",jobId,revision,ExecutionStore.bytes(tenant),new BigDecimal(activation),new BigDecimal(activation),java.sql.Date.valueOf(date.minusDays(1)));return null;
        });
    }
    public void poll(String jobId,String tenant) {
        var job=model.node(jobId);int revision=job.path("revision").asInt();var ref=job.path("data").path("schedule");var sd=model.node(ref.path("id").asText()).path("data");BigInteger now=clock.now();
        tx.execute(s->{
            var state=jdbc.queryForMap("SELECT * FROM acp_scheduler WHERE job=? AND revision=? AND scope=? FOR UPDATE",jobId,revision,ExecutionStore.bytes(tenant));
            if(now.compareTo(integer(state.get("last_ns")))<0)throw new InvocationCore.Outcome("CLOCK_REVERSED");
            LocalDate cursor=((java.sql.Date)state.get("last_date")).toLocalDate().plusDays(1),today=schedule.dateAt(instant(now),sd.path("timezone").asText());
            int count=0;
            while(!cursor.isAfter(today)) {
                if(++count>36600)throw new IllegalStateException("SCHEDULER_RECOVERY_BOUND");
                Instant occurrence=schedule.daily(cursor,sd);
                if(occurrence!=null && ns(occurrence).compareTo(now)>0)break;
                if(occurrence!=null) {
                    BigInteger due=ns(occurrence);String id=encode(List.of(jobId,revision,ref.path("id").asText(),ref.path("revision").asInt(),tenant,due.toString()));
                    String status=due.compareTo(integer(state.get("activation_ns")))<0?"SKIPPED":"SCHEDULED";
                    jdbc.update("INSERT INTO acp_job_occurrence(identity,job,revision,schedule,schedule_revision,scope,scheduled_ns,status) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",id,jobId,revision,ref.path("id").asText(),ref.path("revision").asInt(),ExecutionStore.bytes(tenant),new BigDecimal(due),status);
                }
                jdbc.update("UPDATE acp_scheduler SET last_date=? WHERE job=? AND revision=? AND scope=?",java.sql.Date.valueOf(cursor),jobId,revision,ExecutionStore.bytes(tenant));cursor=cursor.plusDays(1);
            }
            jdbc.update("UPDATE acp_scheduler SET last_ns=? WHERE job=? AND revision=? AND scope=?",new BigDecimal(now),jobId,revision,ExecutionStore.bytes(tenant));return null;
        });
        for(var row:jdbc.queryForList("SELECT identity FROM acp_job_occurrence WHERE job=? AND revision=? AND scope=? AND status IN ('SCHEDULED','STARTED','INDETERMINATE') ORDER BY scheduled_ns",jobId,revision,ExecutionStore.bytes(tenant)))run((String)row.get("identity"),jobId,tenant);
    }
    private void run(String identity,String jobId,String tenant) {
        jdbc.execute((ConnectionCallback<Void>)connection->{
            boolean locked;try(var ps=connection.prepareStatement("SELECT pg_try_advisory_lock(hashtextextended(?,1))")){ps.setString(1,identity);try(var rs=ps.executeQuery()){rs.next();locked=rs.getBoolean(1);}}
            if(!locked)return null;
            try {
                var row=jdbc.queryForMap("SELECT * FROM acp_job_occurrence WHERE identity=?",identity);
                if(!Set.of("SCHEDULED","STARTED","INDETERMINATE").contains((String)row.get("status")))return null;
                var job=model.node(jobId);Jwt principal=principals.resolve(jobId,job.path("revision").asInt(),handles.get(principalKey(jobId,job.path("revision").asInt())));
                if(principal==null || !tenant.equals(principal.getClaimAsString("tenant")))throw new IllegalStateException("JOB_PRINCIPAL_SCOPE");
                String owner=UUID.randomUUID().toString();
                tx.execute(s->{jdbc.update("UPDATE acp_job_occurrence SET status='STARTED',owner=?,attempt=attempt+1 WHERE identity=?",owner,identity);return null;});
                // JDBC transaction timeout and task cancellation are both bounded.
                // A timeout never asserts rollback: durable claims retain proof/uncertainty.
                ExecutorService executor=Executors.newVirtualThreadPerTaskExecutor();
                Future<Object> future=executor.submit(()->InvocationCore.job(identity,job.path("data").path("timeoutSeconds").asInt(),()->invocation.execute(jobId,identity,principal)));
                String status;byte[] result=null;
                try{Object output=future.get(job.path("data").path("timeoutSeconds").asLong(),TimeUnit.SECONDS);status="COMPLETED";result=ExecutionStore.bytes(encode(output));}
                catch(TimeoutException e){future.cancel(true);status="INDETERMINATE";}
                catch(InterruptedException e){Thread.currentThread().interrupt();future.cancel(true);status="INDETERMINATE";}
                catch(ExecutionException e){
                    Throwable fault=e.getCause();
                    boolean unresolved=fault instanceof InvocationCore.Outcome o && Set.of("IN_PROGRESS","INTERRUPTED").contains(o.getMessage());
                    boolean records=jdbc.queryForObject("SELECT count(*) FROM acp_idempotency WHERE job_occurrence=?",Long.class,identity)>0;
                    // Every domain effect requires a durable claim first. A retained
                    // claim/result means recovery; a completed failure with no claim
                    // is terminal, including nonretryable INTERNAL failures.
                    status=unresolved||records?"INDETERMINATE":"FAILED";
                }
                finally{executor.shutdown();}
                String finalStatus=status;byte[] finalResult=result;
                tx.execute(s->{if(jdbc.update("UPDATE acp_job_occurrence SET status=?,result=? WHERE identity=? AND owner=?",finalStatus,finalResult,identity,owner)!=1)throw new IllegalStateException("JOB_FENCE");return null;});return null;
            }finally{try(var ps=connection.prepareStatement("SELECT pg_advisory_unlock(hashtextextended(?,1))")){ps.setString(1,identity);ps.execute();}}
        });
    }
}
