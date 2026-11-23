"""External H4/H6 diagnostic adapter; never packaged into generated production code."""
from engineering.operations.fixture import adapter_source as parent
from engineering.source_intelligence.model import require

def adapter_source():
    source=parent();marker=' @RestController static class Fixture';require(source.count(marker)==1,'H9_FIXTURE_DRIFT')
    diagnostic='''
 static String h9Hash(String s){try{return java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(s.getBytes(java.nio.charset.StandardCharsets.UTF_8)));}catch(Exception e){throw new IllegalStateException();}}
 @Bean org.springframework.boot.web.servlet.FilterRegistrationBean<org.springframework.web.filter.OncePerRequestFilter> h9Diagnostics(javax.sql.DataSource data,io.micrometer.core.instrument.MeterRegistry meters){
  var f=new org.springframework.web.filter.OncePerRequestFilter(){protected void doFilterInternal(jakarta.servlet.http.HttpServletRequest req,jakarta.servlet.http.HttpServletResponse res,jakarta.servlet.FilterChain chain)throws java.io.IOException,jakarta.servlet.ServletException{
   String correlation=res.getHeader("X-ACP-Correlation");if(correlation==null||!correlation.matches("[0-9a-f-]{36}"))throw new IllegalStateException("H9_NO_TRUSTED_CORRELATION");
   long begin=System.nanoTime();var principal=req.getUserPrincipal();String subject="NONE",tenant="NONE";
   if(principal instanceof org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken a){subject=h9Hash(a.getToken().getSubject());tenant=h9Hash(a.getToken().getClaimAsString("tenant"));}
   var pool=(com.zaxxer.hikari.HikariDataSource)data;var bean=pool.getHikariPoolMXBean();int before=bean.getActiveConnections();int awaiting=bean.getThreadsAwaitingConnection();var acquire=meters.find("hikaricp.connections.acquire").timer();long acquired=acquire==null?0:acquire.count();double nanos=acquire==null?0:acquire.totalTime(java.util.concurrent.TimeUnit.NANOSECONDS);
   try{chain.doFilter(req,res);}finally{Map<String,Object> d=new java.util.LinkedHashMap<>();d.put("correlation",correlation);d.put("subjectSHA256",subject);d.put("tenantSHA256",tenant);d.put("startedNanos",begin);d.put("finishedNanos",System.nanoTime());d.put("status",res.getStatus());d.put("activeBefore",before);d.put("activeAfter",bean.getActiveConnections());d.put("awaitingBefore",awaiting);d.put("awaitingAfter",bean.getThreadsAwaitingConnection());d.put("acquisitionMetricPresent",acquire!=null);d.put("acquisitionCountDelta",acquire==null?0:acquire.count()-acquired);d.put("acquisitionAggregateNanosDelta",acquire==null?0:acquire.totalTime(java.util.concurrent.TimeUnit.NANOSECONDS)-nanos);System.err.println("H9_DIAGNOSTIC:"+new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(d));}
  }};var registration=new org.springframework.boot.web.servlet.FilterRegistrationBean<org.springframework.web.filter.OncePerRequestFilter>(f);registration.setOrder(0);return registration;
 }
 '''
    source=source.replace(marker,diagnostic+marker,1)
    before='System.err.println("H4_EXCEPTION:"+cause.getClass().getName()+":"+(cause instanceof java.sql.SQLException sql?sql.getSQLState():""));'
    after='System.err.println("H9_EXCEPTION:"+java.util.Objects.toString(response.getHeader("X-ACP-Correlation"),"NONE")+":"+cause.getClass().getName()+":"+(cause instanceof java.sql.SQLException sql?sql.getSQLState():""));'
    require(source.count(before)==1,'H9_OBSERVER_DRIFT');source=source.replace(before,after,1)
    marker='@GetMapping("/__test/facts")';require(source.count(marker)==1,'H9_ENDPOINT_DRIFT')
    return source.replace(marker,'@GetMapping("/__test/h9-wrapped") Map<String,Object> h9Wrapped(){throw new RuntimeException(new org.springframework.web.servlet.resource.NoResourceFoundException(org.springframework.http.HttpMethod.GET,"h9","h9"));}\n static class H9Missing extends org.springframework.web.servlet.resource.NoResourceFoundException {H9Missing(){super(org.springframework.http.HttpMethod.GET,"h9","h9");}}\n @GetMapping("/__test/h9-subclass") Map<String,Object> h9Subclass()throws H9Missing{throw new H9Missing();}\n @GetMapping("/__test/h9-unexpected") Map<String,Object> h9Unexpected(){throw new NullPointerException("H9_SECRET_SENTINEL_NOT_FOR_EXPORT");}\n @GetMapping("/__test/h9-required") Map<String,Object> h9Required(@RequestParam("required") String required){return Map.of("present",true);}\n '+marker,1)
