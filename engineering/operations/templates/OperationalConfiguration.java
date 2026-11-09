package acp.operations;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import com.fasterxml.jackson.databind.*;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.env.*;
/** Deployment settings, not business semantics. No secret values in the profile. */
public final class OperationalConfiguration implements EnvironmentPostProcessor,Ordered {
 public static final String PROFILE="acp-operational-lab/1";
 public int getOrder(){return Ordered.LOWEST_PRECEDENCE;}
 private static void need(boolean ok){if(!ok)throw new IllegalArgumentException();}
 public static String sha(byte[] raw)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw));}
 public static byte[] read(Path p)throws Exception{need(p.isAbsolute()&&!Files.isSymbolicLink(p)&&Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)&&Files.size(p)<=32768);byte[] raw=Files.readAllBytes(p);need(raw.length<=32768);return raw;}
 public static JsonNode profile()throws Exception{
  String file=System.getenv("ACP_OPERATIONAL_CONFIG"),pin=System.getenv("ACP_OPERATIONAL_CONFIG_SHA256");need(file!=null&&pin!=null&&pin.matches("[0-9a-f]{64}"));byte[] raw=read(Path.of(file));need(sha(raw).equals(pin));
  JsonNode c=new ObjectMapper().enable(com.fasterxml.jackson.core.JsonParser.Feature.STRICT_DUPLICATE_DETECTION).readTree(raw);Set<String> fields=new HashSet<>();c.fieldNames().forEachRemaining(fields::add);
  need(fields.equals(Set.of("profile","runtimeMode","databaseUserRef","databasePasswordRef","poolConnections","acquisitionTimeoutMs","workersEnabled","workerConcurrency","workerStallSeconds","workerPolicy","sessionPolicy","metricsPolicy","metricsReadKeyRef","logEventsPerSecond","maxHeapMiB","maxProcessors")));
  for(String key:List.of("profile","runtimeMode","databaseUserRef","databasePasswordRef","workerPolicy","sessionPolicy","metricsPolicy","metricsReadKeyRef"))need(c.path(key).isTextual());
  need(c.path("profile").asText().equals(PROFILE)&&c.path("runtimeMode").asText().equals("development")&&c.path("databaseUserRef").asText().equals("ACP_DATABASE_USER")&&c.path("databasePasswordRef").asText().equals("ACP_DATABASE_PASSWORD"));
  need(c.path("workerPolicy").asText().equals("CANONICAL_UNMODIFIED")&&c.path("sessionPolicy").asText().equals("CANONICAL_UNMODIFIED")&&c.path("metricsPolicy").asText().equals("LOOPBACK_JWT_AND_HOST_READ_CAPABILITY")&&c.path("metricsReadKeyRef").asText().equals("ACP_METRICS_READ_KEY")&&c.path("workersEnabled").isBoolean());
  integer(c,"poolConnections",4,64);integer(c,"acquisitionTimeoutMs",250,5000);integer(c,"workerConcurrency",2,2);integer(c,"workerStallSeconds",1,300);integer(c,"logEventsPerSecond",1,64);integer(c,"maxHeapMiB",128,1024);integer(c,"maxProcessors",1,4);return c;
 }
 private static int integer(JsonNode c,String name,int lo,int hi){JsonNode n=c.path(name);need(n.isIntegralNumber()&&n.canConvertToInt()&&n.asInt()>=lo&&n.asInt()<=hi);return n.asInt();}
 private static void bind(ConfigurableEnvironment env,Map<String,Object> values,String key,Object value){for(PropertySource<?> source:env.getPropertySources()){Object old=source.getProperty(key);need(old==null||env.resolvePlaceholders(String.valueOf(old)).equals(String.valueOf(value)));}values.put(key,value);}
 public void postProcessEnvironment(ConfigurableEnvironment env,SpringApplication app){
  try{
   JsonNode c=profile();need(env.getActiveProfiles().length==0||Arrays.equals(env.getActiveProfiles(),new String[]{"lab"}));need(Runtime.getRuntime().maxMemory()<=c.path("maxHeapMiB").asLong()*1024*1024&&Runtime.getRuntime().availableProcessors()<=c.path("maxProcessors").asInt());
   String url=env.getProperty("spring.datasource.url",System.getenv("ACP_DATABASE_URL"));need(url!=null&&url.matches("jdbc:postgresql://127\\.0\\.0\\.1:[0-9]+/[A-Za-z0-9_]+(?:\\?currentSchema=[A-Za-z0-9_]+)?"));
   for(String name:List.of("ACP_DATABASE_USER","ACP_DATABASE_PASSWORD","ACP_IDENTITY_CONFIG","ACP_IDENTITY_CONFIG_SHA256","ACP_METRICS_READ_KEY"))need(System.getenv(name)!=null&&!System.getenv(name).isBlank());
   need(System.getenv("ACP_METRICS_READ_KEY").length()>=32);
   for(String key:List.of("acp.integrity.concurrency","acp.integrity.lease-seconds","acp.integrity.max-attempts","acp.session.timeout","acp.runtime.session-policy"))need(env.getProperty(key)==null);
   for(PropertySource<?> source:env.getPropertySources())if(source instanceof EnumerablePropertySource<?> e)for(String name:e.getPropertyNames())if(name.toLowerCase(java.util.Locale.ROOT).replace('_','.').startsWith("logging.level.")){String value=String.valueOf(e.getProperty(name));need(!Set.of("DEBUG","TRACE","ALL").contains(value.toUpperCase(java.util.Locale.ROOT)));}
   Map<String,Object> values=new LinkedHashMap<>();bind(env,values,"spring.flyway.enabled",true);bind(env,values,"acp.runtime.mode","development");bind(env,values,"acp.runtime.poll-enabled",false);bind(env,values,"acp.integrity.enabled",c.path("workersEnabled").asBoolean());
   bind(env,values,"spring.datasource.hikari.maximum-pool-size",c.path("poolConnections").asInt());bind(env,values,"spring.datasource.hikari.connection-timeout",c.path("acquisitionTimeoutMs").asInt());
   bind(env,values,"logging.level.root","INFO");bind(env,values,"logging.structured.format.console","ecs");bind(env,values,"spring.mvc.log-request-details",false);bind(env,values,"management.endpoint.health.show-details","never");bind(env,values,"management.endpoints.web.exposure.include","health,info");bind(env,values,"management.observations.enable.http.server.requests",false);bind(env,values,"management.metrics.enable.http.server.requests",false);
   for(String key:List.of("server.error.include-message","server.error.include-stacktrace","server.error.include-binding-errors"))bind(env,values,key,"never");
   env.getPropertySources().addFirst(new MapPropertySource("acp-h6-pinned-operational-profile",Collections.unmodifiableMap(values)));
  }catch(Exception invalid){System.err.println("{\"contract\":\"acp-h6-operations/1\",\"event\":\"CONFIGURATION_REJECTED\",\"outcome\":\"FAILED\"}");throw new IllegalStateException("OPERATIONAL_CONFIGURATION_INVALID");}
 }
}
