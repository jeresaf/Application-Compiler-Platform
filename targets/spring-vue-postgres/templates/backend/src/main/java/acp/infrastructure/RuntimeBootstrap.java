package acp.infrastructure;

import acp.generated.*;
import java.util.*;
import java.util.concurrent.*;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;

/** Explicit credential/transport adapter boundary; no generated secrets or broker. */
public final class RuntimeBootstrap implements AutoCloseable {
    private final ScheduledExecutorService timer=Executors.newSingleThreadScheduledExecutor(r->{Thread t=new Thread(r,"acp-runtime-poll");t.setDaemon(true);return t;});
    private final JobRuntime jobs;private final DeliveryRuntime delivery;private final TargetModel model;private final JdbcTemplate jdbc;
    private final Map<String,String> tenants=new HashMap<>();
    public RuntimeBootstrap(JdbcTemplate jdbc,PlatformTransactionManager manager,TargetModel model,Invocations invocations,Environment env,ObjectProvider<JobRuntime.PrincipalPort> principalProvider,ObjectProvider<DeliveryRuntime.Transport> transportProvider) {
        this.jdbc=jdbc;this.model=model;var clock=new InvocationCore.SystemTime();
        var principal=principalProvider.getIfAvailable();if(principal==null)throw new IllegalStateException("JOB_PRINCIPAL_ADAPTER_REQUIRED");
        Map<String,String> handles=new HashMap<>();
        for(var job:model.nodes("Job")) {
            String id=job.path("id").asText();String handle=env.getProperty("acp.jobs."+id+".revision-"+job.path("revision").asInt()+".credential-handle");if(handle==null || handle.isBlank())throw new IllegalStateException("JOB_PRINCIPAL_BINDING_REQUIRED");
            handles.put(JobRuntime.principalKey(id,job.path("revision").asInt()),handle);var jwt=principal.resolve(id,job.path("revision").asInt(),handle);
            if(jwt==null || jwt.getClaimAsString("tenant")==null)throw new IllegalStateException("JOB_PRINCIPAL_SCOPE");tenants.put(id,jwt.getClaimAsString("tenant"));
        }
        jobs=new JobRuntime(jdbc,manager,model,clock,principal,handles,new GeneratedJobs(jdbc,invocations));
        var transport=transportProvider.getIfAvailable();delivery=new DeliveryRuntime(jdbc,manager,model,clock,transport==null?o->{throw new IllegalStateException("TRANSPORT_ADAPTER_REQUIRED");}:transport);
    }
    public void start() {
        var clock=new InvocationCore.SystemTime();tenants.forEach((job,tenant)->jobs.activate(job,tenant,clock.now()));
        timer.scheduleWithFixedDelay(()->{
            try{
                tenants.forEach((job,tenant)->jobs.poll(job,tenant));
                if(delivery!=null)for(var row:jdbc.queryForList("SELECT DISTINCT tenant,aggregate_id,resource FROM acp_outbox WHERE delivery_status IN ('PENDING','CLAIMED')"))delivery.poll(ExecutionStore.text((byte[])row.get("tenant")),(String)row.get("aggregate_id"),ExecutionStore.text((byte[])row.get("resource")));
            }catch(RuntimeException e){org.slf4j.LoggerFactory.getLogger(RuntimeBootstrap.class).warn("ACP_RUNTIME_POLL_FAILED");}
        },0,1,TimeUnit.SECONDS);
    }
    @Override public void close(){timer.shutdownNow();}
}
