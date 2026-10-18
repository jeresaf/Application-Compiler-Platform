"""External loopback-only fixtures; never emitted by the candidate generator."""
from task_ui_browser import server_source

MIGRATOR=r'''package acp.recovery;
import org.flywaydb.core.Flyway;
public class MigrationProbe {
 public static void main(String[] args) {
  var f=Flyway.configure().dataSource(System.getenv("ACP_DATABASE_URL"),System.getenv("ACP_DATABASE_USER"),System.getenv("ACP_DATABASE_PASSWORD"))
   .schemas(args[2]).defaultSchema(args[2]).locations("filesystem:"+args[1]).cleanDisabled(true).load();
  switch(args[0]){case "migrate"->f.migrate();case "validate"->f.validate();default->throw new IllegalArgumentException("CLOSED_MIGRATION_OPERATION");}
  System.out.println("ACP_MIGRATION|"+args[0]+"|SUCCESS");
 }
}'''

# Buffer the response until a test-controlled transaction barrier after the
# generated controller/transaction has returned. Kill the JVM at this boundary.
FILTER=r'''package acp.browser;
@org.springframework.stereotype.Component
public class RecoveryResponseGate extends org.springframework.web.filter.OncePerRequestFilter {
 private final org.springframework.jdbc.core.JdbcTemplate jdbc;
 private final org.springframework.transaction.support.TransactionTemplate transaction;
 public RecoveryResponseGate(org.springframework.jdbc.core.JdbcTemplate jdbc,org.springframework.transaction.PlatformTransactionManager manager){this.jdbc=jdbc;transaction=new org.springframework.transaction.support.TransactionTemplate(manager);}
 protected void doFilterInternal(jakarta.servlet.http.HttpServletRequest request,jakarta.servlet.http.HttpServletResponse response,jakarta.servlet.FilterChain chain)throws jakarta.servlet.ServletException,java.io.IOException {
  if(!"hold".equals(request.getHeader("X-ACP-Test-After-Commit"))){chain.doFilter(request,response);return;}
  var buffered=new org.springframework.web.util.ContentCachingResponseWrapper(response);chain.doFilter(request,buffered);
  if(buffered.getStatus()==200)transaction.execute(status->{jdbc.execute("SELECT pg_advisory_xact_lock(62425002)");return null;});
  buffered.copyBodyToResponse();
 }
}'''


def server(domain):
    source=server_source(domain)
    source=source.replace('var now=Instant.now();return Jwt','var now=Instant.parse(System.getenv("ACP_RECOVERY_AUTH_EVENT"));return Jwt')
    source=source.replace('BrowserServer.Fixture.class}', 'BrowserServer.Fixture.class,RecoveryResponseGate.class,RecoveryRuntimeProbe.class}')
    # The test fixture's destructive reset endpoint is deliberately inaccessible
    # in this runner. Provision once through the existing seed statements.
    start=source.index('  @PostMapping("/__test/reset")')
    end=source.index('  @GetMapping("/__test/facts")',start)
    return source[:start]+source[end:]

RUNTIME_PROBE=r'''package acp.browser;
@org.springframework.web.bind.annotation.RestController
public class RecoveryRuntimeProbe {
 private final org.springframework.jdbc.core.JdbcTemplate jdbc;
 private final org.springframework.transaction.PlatformTransactionManager manager;
 private final acp.infrastructure.TargetModel model;
 private final acp.infrastructure.RuntimeBootstrap bootstrap;
 private final acp.generated.Invocations invocations;
 private final org.springframework.security.oauth2.jwt.JwtDecoder decoder;
 public RecoveryRuntimeProbe(org.springframework.jdbc.core.JdbcTemplate jdbc,org.springframework.transaction.PlatformTransactionManager manager,acp.infrastructure.TargetModel model,acp.infrastructure.RuntimeBootstrap bootstrap,acp.generated.Invocations invocations,org.springframework.security.oauth2.jwt.JwtDecoder decoder){this.jdbc=jdbc;this.manager=manager;this.model=model;this.bootstrap=bootstrap;this.invocations=invocations;this.decoder=decoder;}
 @org.springframework.web.bind.annotation.PostMapping("/__test/recovery-observe")
 public java.util.Map<String,Object> observe(){
  var instant=java.time.Instant.parse(System.getenv("ACP_RECOVERY_AUTH_EVENT")).atZone(java.time.ZoneOffset.UTC).toLocalDate().atTime(6,0).toInstant(java.time.ZoneOffset.UTC);
  var ns=java.math.BigInteger.valueOf(instant.getEpochSecond()).multiply(acp.infrastructure.InvocationCore.BILLION);
  acp.infrastructure.InvocationCore.Time clock=new acp.infrastructure.InvocationCore.Time(){public java.math.BigInteger now(){return ns;}public void sleep(long s){throw new AssertionError("NO_SCHEDULER_RETRY");}};
  var jobs=new acp.infrastructure.JobRuntime(jdbc,manager,model,clock,(id,revision,handle)->decoder.decode("browser-authorized"),java.util.Map.of("JOB-TASK@3","browser-test-only"),new acp.generated.GeneratedJobs(jdbc,invocations));
  if(jdbc.queryForObject("SELECT count(*) FROM acp_scheduler",Integer.class)==0)jobs.activate("JOB-TASK","tenant-one",ns.subtract(java.math.BigInteger.ONE));
  jobs.poll("JOB-TASK","tenant-one");
  var delivery=new acp.infrastructure.DeliveryRuntime(jdbc,manager,model,new acp.infrastructure.InvocationCore.SystemTime(),occurrence->{
   jdbc.update("INSERT INTO recovery_transport(identity,payload) VALUES(?,?) ON CONFLICT DO NOTHING",occurrence.id(),occurrence.payload());return true;
  });
  int attempts=0;
  for(var row:jdbc.queryForList("SELECT DISTINCT tenant,aggregate_id,resource FROM acp_outbox")){
   for(int i=0;i<32;i++){
    var result=delivery.poll(acp.infrastructure.ExecutionStore.text((byte[])row.get("tenant")),(String)row.get("aggregate_id"),acp.infrastructure.ExecutionStore.text((byte[])row.get("resource")));
    if(result==acp.infrastructure.DeliveryRuntime.Result.EMPTY)break;
    if(result!=acp.infrastructure.DeliveryRuntime.Result.ACKNOWLEDGED)throw new IllegalStateException("DELIVERY_NOT_ACKNOWLEDGED:"+result);
    attempts++;if(i==31)throw new IllegalStateException("DELIVERY_BOUND");
   }
  }
  for(var row:jdbc.queryForList("SELECT lifecycle,tenant,resource FROM acp_lifecycle_anchor"))bootstrap.management().observe((String)row.get("lifecycle"),acp.infrastructure.ExecutionStore.text((byte[])row.get("tenant")),acp.infrastructure.ExecutionStore.text((byte[])row.get("resource")));
  return java.util.Map.of("deliveryAttempts",attempts,"jobCompleted",jdbc.queryForObject("SELECT count(*) FROM acp_job_occurrence WHERE status='COMPLETED'",Integer.class));
 }
}'''
