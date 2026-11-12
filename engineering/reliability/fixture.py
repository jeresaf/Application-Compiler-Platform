"""External H2 synchronization controls. Never part of generated production artifacts."""
from engineering.jobs.fixture import adapter_source as parent
from engineering.source_intelligence.model import require

BEFORE = 62425101
AFTER = 62425102


def adapter_source():
    source = parent()
    slot='long slot=java.time.Instant.now().getEpochSecond()/3600*3600-((Number)body.get("offset")).longValue()*3600;'
    require(source.count(slot)==1,'H2_OCCURRENCE_FIXTURE_DRIFT')
    source=source.replace(slot,'long slot=body.containsKey("occurrence")?((Number)body.get("occurrence")).longValue():java.time.Instant.now().getEpochSecond()/3600*3600-((Number)body.get("offset")).longValue()*3600;',1)
    source = source.replace('Set.of("browser-report-tenant-two",',
                            'Set.of("browser-report-tenant-two-peer","browser-report-tenant-two",', 1)
    source = source.replace('token.equals("browser-report-tenant-two")',
                            'token.startsWith("browser-report-tenant-two")')
    source = source.replace('.claim("sid",token.equals("browser-competing")?',
                            '.claim("sid",token.equals("browser-report-tenant-two-peer")?"h2-tenant-two-peer":token.equals("browser-competing")?', 1)
    # Each restored lab authenticates fresh sessions; restarts retain the same
    # explicit event and namespace. Never renew an expired durable session in place.
    needle='.claim("sid",token.equals("browser-report-tenant-two-peer")?"h2-tenant-two-peer":token.equals("browser-competing")?"competing-session":"browser-session")'
    require(source.count(needle)==1,'H2_SESSION_FIXTURE_DRIFT')
    source=source.replace(needle,'.claim("sid",System.getenv().getOrDefault("ACP_H2_SESSION_NAMESPACE","")+(token.equals("browser-report-tenant-two-peer")?"h2-tenant-two-peer":token.equals("browser-competing")?"competing-session":"browser-session"))',1)
    marker = '@GetMapping("/__test/facts")'
    require(source.count(marker) == 1, 'H2_FIXTURE_DRIFT')
    methods = '''
  @org.springframework.beans.factory.annotation.Autowired acp.security.ApplicationPolicy h2Policy;
  @PostMapping("/__test/h2-session") Map<String,Object> h2Session(@org.springframework.security.core.annotation.AuthenticationPrincipal Jwt jwt){
   h2Policy.actor(jwt);
   return Map.of("sessions",jdbc.queryForList("SELECT convert_from(tenant,'UTF8') AS tenant,convert_from(subject,'UTF8') AS subject,convert_from(sid,'UTF8') AS sid,authenticated_at,revoked FROM acp_sessions WHERE tenant=? AND subject=? AND sid=?",jwt.getClaimAsString("tenant").getBytes(java.nio.charset.StandardCharsets.UTF_8),jwt.getSubject().getBytes(java.nio.charset.StandardCharsets.UTF_8),jwt.getClaimAsString("sid").getBytes(java.nio.charset.StandardCharsets.UTF_8)));
  }
  @PostMapping("/__test/h2-pause-claims") Map<String,Object> h2PauseClaims()throws Exception{
   // Isolated fault control: stop future polling, without interrupting the held action.
   var field=acp.api.IntegrityWorker.class.getDeclaredField("loops");field.setAccessible(true);
   ((java.util.concurrent.ScheduledExecutorService)field.get(integrity)).shutdown();
   return Map.of("futurePollingStopped",true);
  }
'''
    source = source.replace(marker, methods+marker)
    bean = '''
 @Bean org.springframework.web.filter.OncePerRequestFilter h2AcknowledgementGate(JdbcTemplate jdbc){
  return new org.springframework.web.filter.OncePerRequestFilter(){
   @Override protected void doFilterInternal(jakarta.servlet.http.HttpServletRequest request,jakarta.servlet.http.HttpServletResponse response,jakarta.servlet.FilterChain chain)throws java.io.IOException,jakarta.servlet.ServletException{
    if(!"hold".equals(request.getHeader("X-H2-After-Commit"))){chain.doFilter(request,response);return;}
    var buffered=new org.springframework.web.util.ContentCachingResponseWrapper(response);
    chain.doFilter(request,buffered);
    if(buffered.getStatus()==200)jdbc.queryForObject("SELECT pg_advisory_xact_lock(AFTER_GATE)",Object.class);
    buffered.copyBodyToResponse();
   }
  };
 }
'''.replace('AFTER_GATE', str(AFTER))
    marker = ' @Bean acp.infrastructure.JobRuntime.PrincipalPort'
    require(source.count(marker) == 1, 'H2_BEAN_DRIFT')
    return source.replace(marker, bean+marker, 1)
