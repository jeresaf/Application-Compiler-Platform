"""External H3 test identities and read-only pool instrumentation, never production."""
from engineering.reliability.fixture import adapter_source as parent
from engineering.source_intelligence.model import require


def adapter_source():
    source=parent();marker='@Bean JwtDecoder decoder(){return token->{'
    require(source.count(marker)==1,'H3_DECODER_DRIFT')
    source=source.replace(marker,marker+'''
  String originalToken=token;
  if(token.matches("browser-h3-(?:[0-9]|1[0-5])"))token=Integer.parseInt(token.substring(11))%2==0?"browser-authorized":"browser-report-tenant-two";
''',1)
    source=source.replace('Jwt.withTokenValue(token)','Jwt.withTokenValue(originalToken)',1)
    marker='.claim("sid",System.getenv().getOrDefault("ACP_H2_SESSION_NAMESPACE","")+'
    require(source.count(marker)==1,'H3_SESSION_DRIFT')
    source=source.replace(marker,'.claim("sid",System.getenv().getOrDefault("ACP_H2_SESSION_NAMESPACE","")+(originalToken.startsWith("browser-h3-")?originalToken:',1)
    marker='?"competing-session":"browser-session")).claim("amr"'
    require(source.count(marker)==1,'H3_SESSION_END_DRIFT')
    source=source.replace(marker,'?"competing-session":"browser-session"))).claim("amr"',1)
    marker='@GetMapping("/__test/facts")'
    require(source.count(marker)==1,'H3_RESOURCE_FIXTURE_DRIFT')
    return source.replace(marker,'''
  @GetMapping("/__test/h3-resources") Map<String,Object> h3Resources(){
   var pool=(com.zaxxer.hikari.HikariDataSource)java.util.Objects.requireNonNull(jdbc.getDataSource());
   var bean=pool.getHikariPoolMXBean();var heap=java.lang.management.ManagementFactory.getMemoryMXBean().getHeapMemoryUsage();
   return Map.of("active",bean.getActiveConnections(),"idle",bean.getIdleConnections(),"waiting",bean.getThreadsAwaitingConnection(),"total",bean.getTotalConnections(),"maximum",pool.getMaximumPoolSize(),"acquisitionTimeoutMs",pool.getConnectionTimeout(),"heapUsedBytes",heap.getUsed(),"heapMaxBytes",heap.getMax());
  }
'''+marker,1)
