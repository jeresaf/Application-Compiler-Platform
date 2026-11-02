package acp.api;
import acp.infrastructure.*;
import acp.security.ApplicationPolicy;
import com.fasterxml.jackson.databind.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.function.Supplier;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.transaction.*;
import org.springframework.transaction.support.TransactionTemplate;

/** Generated from a versioned ReportDefinition, never caller-provided SQL. */
@RestController
@ConditionalOnProperty(name="acp.reporting.mode",havingValue="preview")
public final class ReportingController {
 public static final String REPORT_ID=${REPORT_ID};
 private final JdbcTemplate jdbc;private final ApplicationPolicy policy;private final TargetModel model;
 private final ObjectMapper mapper=new ObjectMapper();private final JsonNode c;private final TransactionTemplate reads;
 public ReportingController(JdbcTemplate jdbc,ApplicationPolicy policy,TargetModel model,PlatformTransactionManager manager,@org.springframework.beans.factory.annotation.Value("${acp.runtime.mode:production}") String mode)throws Exception{
  if(!"development".equals(mode))throw new IllegalStateException("REPORT_PREVIEW_ONLY");
  this.jdbc=jdbc;this.policy=policy;this.model=model;
  try(var input=getClass().getResourceAsStream("/acp-report.json")){c=mapper.readTree(input);}
  if(!REPORT_ID.equals(c.path("id").asText())||!"UNAPPROVED_REPORT_PREVIEW".equals(c.path("scope").asText()))throw new IllegalStateException("REPORT_IDENTITY");
  reads=new TransactionTemplate(manager);reads.setReadOnly(true);reads.setPropagationBehavior(TransactionDefinition.PROPAGATION_REQUIRES_NEW);reads.setIsolationLevel(TransactionDefinition.ISOLATION_REPEATABLE_READ);
 }
 @ExceptionHandler(ResponseStatusException.class)
 public ResponseEntity<Map<String,String>> failure(ResponseStatusException e){return ResponseEntity.status(e.getStatusCode()).body(Map.of("code",e.getReason()));}
 private void bad(){throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"REPORT_INPUT");}
 private byte[] bytes(String s){return s.getBytes(StandardCharsets.UTF_8);}
 private void keys(JsonNode n,Set<String> allowed){if(!n.isObject())bad();n.fieldNames().forEachRemaining(k->{if(!allowed.contains(k))bad();});}
 private String text(JsonNode n,int max){if(!n.isTextual())bad();String s=n.asText();if(s.codePointCount(0,s.length())>max)bad();for(int i=0;i<s.length();i++){char x=s.charAt(i);if(Character.isHighSurrogate(x)){if(++i>=s.length()||!Character.isLowSurrogate(s.charAt(i)))bad();}else if(Character.isLowSurrogate(x))bad();}return s;}
 private int integer(JsonNode n,int fallback,int low,int high){if(n.isMissingNode())return fallback;if(!n.isIntegralNumber()||!n.canConvertToInt())bad();int x=n.asInt();if(x<low||x>high)bad();return x;}
 private void authorize(Jwt jwt,boolean audit){
  policy.actor(jwt); // Session enforcement precedes any projection or data query.
  var grant=c.path(audit?"auditPermission":"permission");
  boolean allowed=model.nodes("RoleAssignment").stream().anyMatch(n->{var d=n.path("data");return d.path("principal").asText().equals(jwt.getSubject())&&d.path("role").equals(grant.path("role"))&&d.path("actor").equals(grant.path("actor"))&&d.path("scope").equals(grant.path("scope"));});
  if(!allowed)throw new AccessDeniedException("REPORT_PERMISSION_DENIED");
  if(jdbc.queryForObject(c.path("principalSQL").asText(),Integer.class,bytes(jwt.getSubject()),bytes(jwt.getClaimAsString("tenant")))!=1)throw new AccessDeniedException("REPORT_PRINCIPAL_TENANT");
 }
 private List<Object> scope(Jwt jwt){return new ArrayList<>(List.of(bytes(jwt.getClaimAsString("tenant")),bytes(jwt.getSubject())));}
 private int page(JsonNode r){return integer(r.path("page"),0,0,c.path("pagination").path("maximumPage").asInt());}
 private int size(JsonNode r){return integer(r.path("size"),c.path("pagination").path("defaultSize").asInt(),1,c.path("pagination").path("maximumSize").asInt());}
 @PostMapping("${REPORT_PATH}")
 public Map<String,Object> report(@RequestBody JsonNode request,@AuthenticationPrincipal Jwt jwt){
  authorize(jwt,false);keys(request,Set.of("filters","sort","page","size"));
  int page=page(request),size=size(request);List<Object> parameters=scope(jwt);StringBuilder where=new StringBuilder(c.path("whereSQL").asText());
  JsonNode filters=request.path("filters");
  if(!filters.isMissingNode()){
   Set<String> names=new HashSet<>();c.path("filters").fieldNames().forEachRemaining(names::add);keys(filters,names);
   filters.fields().forEachRemaining(f->{var rule=c.path("filters").path(f.getKey());String value=text(f.getValue(),256);
    if("STATE".equals(rule.path("type").asText())){boolean known=false;for(var state:c.path("states"))if(state.path("id").asText().equals(value))known=true;if(!known)bad();}
    where.append(" AND ").append(rule.path("sql").asText());parameters.add(value);
   });
  }
  String order=c.path("defaultOrderSQL").asText();JsonNode sorting=request.path("sort");
  if(!sorting.isMissingNode()){
   keys(sorting,Set.of("field","direction"));String field=text(sorting.path("field"),180),direction=text(sorting.path("direction"),4);
   if(!c.path("sorts").has(field)||!(direction.equals("ASC")||direction.equals("DESC")))bad();
   order=c.path("sorts").path(field).asText()+" "+direction+","+c.path("identityColumn").asText()+" ASC";
  }
  final String orderSQL=order;
  return reads.execute(status->{
   Long total=jdbc.queryForObject("SELECT count(*) FROM "+c.path("table").asText()+" WHERE "+where,Long.class,parameters.toArray());
   var totals=jdbc.queryForList("SELECT acp_state AS state,count(*) AS count FROM "+c.path("table").asText()+" WHERE "+where+" GROUP BY acp_state ORDER BY acp_state",parameters.toArray());
   var args=new ArrayList<>(parameters);args.add(size);args.add(page*size);
   var rows=jdbc.query("SELECT "+c.path("selectSQL").asText()+" FROM "+c.path("table").asText()+" WHERE "+where+" ORDER BY "+orderSQL+" LIMIT ? OFFSET ?",(rs,index)->{
    Map<String,Object> values=new LinkedHashMap<>();for(var f:c.path("fields")){
     byte[] raw=rs.getBytes(f.path("column").asText());Object value=raw==null?null:new String(raw,StandardCharsets.UTF_8);
     if(value!=null&&!f.path("member").isNull())try{value=mapper.readTree((String)value).path(f.path("member").asText()).asText();}catch(Exception e){throw new IllegalStateException("REPORT_STORED_VALUE");}
     values.put(f.path("id").asText(),value);
    }
    return Map.<String,Object>of("resourceId",new String(rs.getBytes(c.path("identityColumn").asText()),StandardCharsets.UTF_8),"version",rs.getLong("acp_version"),"state",rs.getString("acp_state"),"values",values);
   },args.toArray());
   return Map.<String,Object>of("report",REPORT_ID,"items",rows,"total",total,"counts",totals,"page",page,"size",size);
  });
 }
 @PostMapping("${REPORT_PATH}/history")
 public Map<String,Object> history(@RequestBody JsonNode request,@AuthenticationPrincipal Jwt jwt){
  authorize(jwt,true);keys(request,Set.of("resourceId","page","size"));String id=text(request.path("resourceId"),256);if(id.isBlank())bad();int page=page(request),size=size(request);
  return reads.execute(status->{
   var owner=scope(jwt);owner.add(bytes(id));
   if(jdbc.queryForObject("SELECT count(*) FROM "+c.path("table").asText()+" WHERE "+c.path("whereSQL").asText()+" AND "+c.path("identityColumn").asText()+"=?",Integer.class,owner.toArray())!=1)throw new ResponseStatusException(HttpStatus.NOT_FOUND,"REPORT_RESOURCE_NOT_FOUND");
   var args=new ArrayList<Object>();args.add(bytes(jwt.getClaimAsString("tenant")));args.add(bytes(id));c.path("auditOperations").forEach(op->args.add(op.asText()));
   String where=c.path("auditWhereSQL").asText();Long total=jdbc.queryForObject("SELECT count(*) FROM acp_audit WHERE "+where,Long.class,args.toArray());args.add(size);args.add(page*size);
   var rows=jdbc.query("SELECT operation,occurred_at FROM acp_audit WHERE "+where+" ORDER BY occurred_at,id LIMIT ? OFFSET ?",(rs,n)->Map.of("operation",rs.getString("operation"),"occurredAt",rs.getTimestamp("occurred_at").toInstant().toString()),args.toArray());
   return Map.<String,Object>of("report",REPORT_ID,"resourceId",id,"items",rows,"total",total,"page",page,"size",size);
  });
 }
}
