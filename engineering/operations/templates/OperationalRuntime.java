package acp.operations;
import acp.infrastructure.TargetModel;
import acp.security.Observability;
import acp.api.IntegrityWorker;
import com.fasterxml.jackson.databind.*;
import com.zaxxer.hikari.HikariDataSource;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import java.io.IOException;
import java.nio.file.Path;
import java.time.*;
import java.util.*;
import java.util.concurrent.atomic.*;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.boot.health.contributor.*;
import org.springframework.context.event.EventListener;
import org.springframework.context.event.ContextClosedEvent;
import org.springframework.context.annotation.Bean;
import org.springframework.core.Ordered;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.filter.OncePerRequestFilter;
/** Fixed-cardinality operational metadata. Never a domain-value/audit export. */
@RestController
public final class OperationalRuntime {
 private static volatile OperationalRuntime active;
 private record Context(String id,String route,String origin){}
 private static final ThreadLocal<Context> context=new ThreadLocal<>();
 private static final Set<String> EVENTS=Set.of("STARTUP","MIGRATION","HTTP","AUTHENTICATION","AUTHORIZATION","DATABASE","TRANSACTION","IDEMPOTENCY","DOCUMENT","WORKFLOW","WORKER","READINESS","RECOVERY","SHUTDOWN");
 private static final Set<String> OUTCOMES=Set.of("SUCCEEDED","DENIED","FAILED","COMMITTED","ROLLED_BACK","INDETERMINATE","REPLAYED","UP","DOWN","STARTED","STOPPED");
 private static final List<String> ROUTES=List.of("HEALTH","METRICS","CREATE","QUERY","WORKFLOW","REPORT","DOCUMENT","JOB","OTHER");
 private final String metricsKey=System.getenv("ACP_METRICS_READ_KEY");private final acp.security.ApplicationPolicy policy;private final JsonNode profile,job,identity;private final TargetModel model;private final Observability observability;private final HikariDataSource pool;private final ObjectProvider<IntegrityWorker> workers;private final JdbcTemplate jdbc;
 private final Map<String,LongAdder> counters=new LinkedHashMap<>();private final Map<String,String[]> routes=new LinkedHashMap<>();private final AtomicBoolean ready=new AtomicBoolean(),stopping=new AtomicBoolean();private final AtomicReference<Boolean> lastReady=new AtomicReference<>(),lastDatabase=new AtomicReference<>(),lastWorker=new AtomicReference<>();private final AtomicLong budgetSecond=new AtomicLong();private final AtomicInteger budget=new AtomicInteger(),peakActive=new AtomicInteger(),peakAwaiting=new AtomicInteger();private final LongAdder instrumentationNanos=new LongAdder();private final LongAdder dropped=new LongAdder(),requestNanos=new LongAdder(),requests=new LongAdder();
 public OperationalRuntime(TargetModel model,Observability observability,HikariDataSource pool,ObjectProvider<IntegrityWorker> workers,acp.security.ApplicationPolicy policy)throws Exception{
  this.policy=policy;this.model=model;this.observability=observability;this.pool=pool;this.workers=workers;profile=OperationalConfiguration.profile();jdbc=new JdbcTemplate(pool);jdbc.setQueryTimeout(1);ObjectMapper mapper=new ObjectMapper();identity=mapper.readTree(OperationalConfiguration.read(Path.of(System.getenv("ACP_IDENTITY_CONFIG"))));
  try(var in=getClass().getResourceAsStream("/acp-background-job.json")){job=mapper.readTree(in);}
  for(String event:EVENTS)for(String outcome:OUTCOMES)counters.put(event+"."+outcome,new LongAdder());for(String route:ROUTES)for(int status=1;status<=5;status++)counters.put("HTTP."+route+"."+status,new LongAdder());
  for(var api:model.model.path("api"))routes.put(api.path("path").asText(),new String[]{model.node(api.path("origin").path("id").asText()).path("kind").asText().equals("Query")?"QUERY":"WORKFLOW",api.path("origin").path("id").asText()});
  for(String name:List.of("acp-intake-preview.json","acp-documents.json","acp-report.json","acp-background-job.json"))try(var in=getClass().getResourceAsStream("/"+name)){JsonNode c=mapper.readTree(in);String route=name.contains("intake")?"CREATE":name.contains("documents")?"DOCUMENT":name.contains("report")?"REPORT":"JOB";for(String suffix:List.of("","/upload","/download","/metadata","/list","/history","/results"))routes.put(c.path("path").asText()+suffix,new String[]{route,c.path("id").asText(c.path("operation").asText())});}
  active=this;
 }
 public static void record(String event,String outcome){OperationalRuntime value=active;if(value!=null){Context c=context.get();if(event.equals("WORKFLOW")&&(c==null||!c.route().equals("WORKFLOW")))return;value.event(event,outcome);}}
 public static void observeTransaction(){if(org.springframework.transaction.support.TransactionSynchronizationManager.isSynchronizationActive())org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(new org.springframework.transaction.support.TransactionSynchronization(){public void afterCompletion(int status){record("TRANSACTION",status==STATUS_COMMITTED?"COMMITTED":status==STATUS_ROLLED_BACK?"ROLLED_BACK":"INDETERMINATE");}});}
 public static void beginWorker(){OperationalRuntime value=active;if(value!=null){context.set(new Context(UUID.randomUUID().toString(),"JOB",value.job.path("id").asText()));record("WORKER","STARTED");}}
 public static void endWorker(){context.remove();}
 public static void observeWorkerResult(boolean successful){if(org.springframework.transaction.support.TransactionSynchronizationManager.isSynchronizationActive())org.springframework.transaction.support.TransactionSynchronizationManager.registerSynchronization(new org.springframework.transaction.support.TransactionSynchronization(){public void afterCompletion(int status){record("WORKER",status==STATUS_COMMITTED?(successful?"SUCCEEDED":"FAILED"):status==STATUS_ROLLED_BACK?"ROLLED_BACK":"INDETERMINATE");}});}
 private void samplePool(){var mx=pool.getHikariPoolMXBean();if(mx!=null){peakActive.accumulateAndGet(mx.getActiveConnections(),Math::max);peakAwaiting.accumulateAndGet(mx.getThreadsAwaitingConnection(),Math::max);}}
 private void event(String event,String outcome){long entered=System.nanoTime();try{
  if(!EVENTS.contains(event)||!OUTCOMES.contains(outcome))throw new IllegalArgumentException("OPERATIONAL_EVENT");counters.get(event+"."+outcome).increment();long now=System.nanoTime()/1_000_000_000L;
  synchronized(budget){if(budgetSecond.get()!=now){budgetSecond.set(now);budget.set(0);}if(budget.incrementAndGet()>profile.path("logEventsPerSecond").asInt()){dropped.increment();return;}}
  Context current=context.get();String id=current==null?UUID.randomUUID().toString():current.id(),origin=current==null?"OPERATIONAL_PROFILE":current.origin();observability.operational(event,id,outcome,origin);
 }finally{instrumentationNanos.add(System.nanoTime()-entered);}}
 private boolean trust(){try{return OperationalConfiguration.sha(OperationalConfiguration.read(Path.of(identity.path("keySetPath").asText()))).equals(identity.path("keySetSHA256").asText());}catch(Exception unavailable){return false;}}
 private boolean probeDatabase()throws Exception{try(var connection=pool.getConnection()){int previous=connection.getNetworkTimeout();connection.setNetworkTimeout(Runnable::run,1000);try(var statement=connection.createStatement()){statement.setQueryTimeout(1);try(var result=statement.executeQuery("SELECT 1=1")){return result.next()&&result.getBoolean(1);}}finally{if(!connection.isClosed())connection.setNetworkTimeout(Runnable::run,previous);}}}
 private boolean database(){samplePool();boolean up;try{up=pool.getHikariPoolMXBean()!=null&&pool.getHikariPoolMXBean().getActiveConnections()<pool.getMaximumPoolSize()&&probeDatabase();}catch(Exception unavailable){up=false;}Boolean before=lastDatabase.getAndSet(up);if(before==null||before!=up)event("DATABASE",up?"UP":"DOWN");return up;}
 private Map<String,Object> queueRow(String sql,Object... arguments){try(var connection=pool.getConnection()){int previous=connection.getNetworkTimeout();connection.setNetworkTimeout(Runnable::run,1000);try{var query=new JdbcTemplate(new org.springframework.jdbc.datasource.SingleConnectionDataSource(connection,true));query.setQueryTimeout(1);return query.queryForMap(sql,arguments);}finally{if(!connection.isClosed())connection.setNetworkTimeout(Runnable::run,previous);}}catch(Exception unavailable){throw new IllegalStateException("DEPENDENCY_UNAVAILABLE");}}
 private Map<String,Long> queue(){
  if(!profile.path("workersEnabled").asBoolean())return Map.of("depth",0L,"attempts",0L,"completed",0L,"failed",0L,"oldestSeconds",0L);
  var worker=workers.getIfAvailable();if(worker==null)throw new IllegalStateException("WORKER_REQUIRED");Set<String> tenants=worker.operationalTenants();if(tenants.isEmpty()||tenants.size()>32)throw new IllegalStateException("WORKER_SCOPE");String marks=String.join(",",Collections.nCopies(tenants.size(),"?"));String p=job.path("prefix").asText();if(!p.matches("j_[0-9a-f]{24}"))throw new IllegalStateException("JOB_STORAGE");
  var rows=queueRow("SELECT count(*) FILTER(WHERE state IN ('PENDING','RETRY','RUNNING')) AS depth,coalesce(sum(attempts),0) AS attempts,count(*) FILTER(WHERE state='COMPLETED') AS completed,count(*) FILTER(WHERE state='FAILED') AS failed,coalesce(floor(extract(epoch FROM clock_timestamp()-min(CASE WHEN state='RUNNING' THEN started_at WHEN state IN ('PENDING','RETRY') AND available_at<=clock_timestamp() THEN available_at END))),0) AS age FROM "+p+"_queue WHERE convert_from(tenant,'UTF8') IN ("+marks+")",tenants.toArray());
  return Map.of("depth",((Number)rows.get("depth")).longValue(),"attempts",((Number)rows.get("attempts")).longValue(),"completed",((Number)rows.get("completed")).longValue(),"failed",((Number)rows.get("failed")).longValue(),"oldestSeconds",Math.max(0,((Number)rows.get("age")).longValue()));
 }
 private boolean worker(){boolean up;if(!profile.path("workersEnabled").asBoolean())up=true;else try{IntegrityWorker w=workers.getIfAvailable();up=w!=null&&w.operationalRunning()&&w.operationalPulseAgeSeconds()<=profile.path("workerStallSeconds").asInt()&&queue().get("oldestSeconds")<profile.path("workerStallSeconds").asInt();}catch(Exception unavailable){up=false;}Boolean before=lastWorker.getAndSet(up);if(before==null||before!=up)event("WORKER",up?"UP":"DOWN");return up;}

 private Health health(boolean up){return up?Health.up().build():Health.down().build();}
 @Bean(name="acpDatabase") public HealthIndicator dependencyHealth(){return ()->health(database());}
 @Bean(name="acpIdentity") public HealthIndicator identityHealth(){return ()->health(trust());}
 @Bean(name="acpWorker") public HealthIndicator workerHealth(){return ()->health(worker());}
 @Bean(name="acpOperational") public HealthIndicator readinessHealth(){return ()->{boolean up=ready.get()&&!stopping.get()&&trust()&&database()&&worker();Boolean before=lastReady.getAndSet(up);if(before==null||before!=up){event("READINESS",up?"UP":"DOWN");if(Boolean.FALSE.equals(before)&&up)event("RECOVERY","SUCCEEDED");}return health(up);};}
 @EventListener(ApplicationReadyEvent.class) public void started(){ready.set(true);event("MIGRATION","SUCCEEDED");event("STARTUP","SUCCEEDED");}
 @EventListener(ContextClosedEvent.class) public void stopping(){stopping.set(true);ready.set(false);event("READINESS","DOWN");event("SHUTDOWN","STOPPED");if(active==this)active=null;}
 private String[] route(String path){if(path.startsWith("/actuator/health"))return new String[]{"HEALTH","OPERATIONAL_PROFILE"};if(path.equals("/internal/operations/metrics"))return new String[]{"METRICS","OPERATIONAL_PROFILE"};return routes.getOrDefault(path,new String[]{"OTHER","OPERATIONAL_PROFILE"});}
 @Bean public FilterRegistrationBean<OncePerRequestFilter> operationalFilter(){
  var filter=new OncePerRequestFilter(){protected void doFilterInternal(HttpServletRequest request,HttpServletResponse response,FilterChain chain)throws ServletException,IOException{
   String[] r=route(request.getRequestURI());String id=UUID.randomUUID().toString();context.set(new Context(id,r[0],r[1]));response.setHeader("X-ACP-Correlation",id);long start=System.nanoTime();int status=500;
   try{chain.doFilter(request,response);status=response.getStatus();}finally{
    requests.increment();requestNanos.add(System.nanoTime()-start);counters.get("HTTP."+r[0]+"."+Math.max(1,Math.min(5,status/100))).increment();
    try{if(status==403)event("AUTHORIZATION","DENIED");if(!r[0].equals("HEALTH")&&!r[0].equals("METRICS")){event("HTTP",status<400?"SUCCEEDED":"FAILED");if(r[0].equals("DOCUMENT"))event("DOCUMENT",status<400?"SUCCEEDED":"FAILED");}}finally{context.remove();}
   }
  }};var registration=new FilterRegistrationBean<OncePerRequestFilter>(filter);registration.setOrder(Ordered.HIGHEST_PRECEDENCE+10);return registration;
 }
 @GetMapping("/internal/operations/metrics") public Map<String,Object> metrics(HttpServletRequest request,@org.springframework.security.core.annotation.AuthenticationPrincipal org.springframework.security.oauth2.jwt.Jwt jwt){
  if(!Set.of("127.0.0.1","0:0:0:0:0:0:0:1","::1").contains(request.getRemoteAddr()))throw new org.springframework.security.access.AccessDeniedException("OPERATIONAL_ACCESS_DENIED");
  String supplied=request.getHeader("X-ACP-Metrics-Key");if(supplied==null||!java.security.MessageDigest.isEqual(metricsKey.getBytes(java.nio.charset.StandardCharsets.UTF_8),supplied.getBytes(java.nio.charset.StandardCharsets.UTF_8)))throw new org.springframework.security.access.AccessDeniedException("OPERATIONAL_ACCESS_DENIED");policy.actor(jwt);
  samplePool();Map<String,Object> values=new TreeMap<>();values.put("poolActivePeak",peakActive.get());values.put("poolAwaitingPeak",peakAwaiting.get());IntegrityWorker w=workers.getIfAvailable();values.put("workerRunning",w!=null&&w.operationalRunning());values.put("workerPulseAgeSeconds",w==null?0:w.operationalPulseAgeSeconds());counters.forEach((key,value)->values.put(key,value.sum()));values.put("eventEmissionNanos",instrumentationNanos.sum());values.put("requests",requests.sum());values.put("requestNanos",requestNanos.sum());values.put("droppedOperationalEvents",dropped.sum());values.put("logEventsPerSecondLimit",profile.path("logEventsPerSecond").asInt());values.put("workersEnabled",profile.path("workersEnabled").asBoolean());
  var mx=pool.getHikariPoolMXBean();values.put("poolActive",mx==null?0:mx.getActiveConnections());values.put("poolIdle",mx==null?0:mx.getIdleConnections());values.put("poolAwaiting",mx==null?0:mx.getThreadsAwaitingConnection());values.put("poolMaximum",pool.getMaximumPoolSize());values.put("queue",queue());return Collections.unmodifiableMap(values);
 }
}
