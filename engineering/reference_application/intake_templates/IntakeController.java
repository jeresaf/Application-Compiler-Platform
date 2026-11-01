package acp.api;

import acp.infrastructure.*;
import acp.security.ApplicationPolicy;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

/** Generated generic intake executor. Only an explicitly opted-in synthetic contract. */
@RestController
@ConditionalOnProperty(name="acp.intake.mode",havingValue="synthetic-preview")
public final class IntakeController {
 private final JdbcTemplate jdbc; private final ApplicationPolicy policy; private final TargetModel model;
 private final InvocationCore invocations;private final ExecutionStore store;
 private final JsonNode contract;private final ObjectMapper mapper=new ObjectMapper();
 public IntakeController(JdbcTemplate jdbc,ApplicationPolicy policy,TargetModel model,InvocationCore invocations,ExecutionStore store,@org.springframework.beans.factory.annotation.Value("${acp.runtime.mode:production}") String mode)throws Exception{
  if(!"development".equals(mode))throw new IllegalStateException("INTAKE_LAB_ONLY");
  this.jdbc=jdbc;this.policy=policy;this.model=model;this.invocations=invocations;this.store=store;
  try(var input=getClass().getResourceAsStream("/acp-intake-preview.json")){contract=mapper.readTree(input);}
  if(!"SYNTHETIC_PREVIEW_ONLY".equals(contract.path("scope").asText()))throw new IllegalStateException("INTAKE_SCOPE");
 }
 @ExceptionHandler(ResponseStatusException.class)
 public ResponseEntity<Map<String,String>> failure(ResponseStatusException failure){return ResponseEntity.status(failure.getStatusCode()).body(Map.of("code",failure.getReason()==null?"INTAKE_INTERNAL":failure.getReason()));}
 private void bad(String reason){throw new ResponseStatusException(HttpStatus.BAD_REQUEST,reason);}
 private byte[] bytes(String value){return ExecutionStore.bytes(value);}
 @PostMapping("${INTAKE_PATH}")
 public Map<String,Object> create(@RequestBody JsonNode request,@AuthenticationPrincipal Jwt jwt)throws Exception{
  policy.actor(jwt); // Existing SessionGate: expiry, MFA, durable revocation and freshness.
  boolean allowed=model.nodes("RoleAssignment").stream().anyMatch(n->n.path("data").path("principal").asText().equals(jwt.getSubject())&&n.path("data").path("role").path("id").asText().equals(contract.path("role").asText()));
  if(!allowed)throw new AccessDeniedException("SYNTHETIC_CREATE_PERMISSION_DENIED");
  if(jdbc.queryForObject(contract.path("principalSQL").asText(),Integer.class,bytes(jwt.getSubject()),bytes(jwt.getClaimAsString("tenant")))!=1)throw new AccessDeniedException("SUBJECT_TENANT_BINDING");
  Set<String> expected=new HashSet<>();expected.add("idempotencyKey");contract.path("inputs").fieldNames().forEachRemaining(expected::add);
  Set<String> actual=new HashSet<>();request.fieldNames().forEachRemaining(actual::add);
  if(!request.isObject()||!expected.equals(actual))bad("INTAKE_FIELDS");
  var key=request.path("idempotencyKey");if(!key.isTextual()||key.asText().isBlank()||key.asText().length()>128||!validUnicode(key.asText()))bad("INTAKE_KEY");
  Map<String,Object> values=new TreeMap<>();
  var fields=contract.path("inputs").fields();
  while(fields.hasNext()){
   var f=fields.next();var value=request.path(f.getKey());if(!value.isTextual())bad("INTAKE_TYPE");
   String text=value.asText();int length=text.codePointCount(0,text.length());
   if(length<1||length>f.getValue().path("maxLength").asInt()||text.chars().anyMatch(x->x>=0xD800&&x<=0xDFFF)&&!validUnicode(text))bad("INTAKE_LENGTH_OR_UNICODE");
   values.put(f.getKey(),text);
  }
  String operation=contract.path("operation").asText();String typed=InvocationCore.typed("{\"kind\":\"SyntheticIntake\"}",values);
  var rate=contract.path("rate");
  if(!invocations.syntheticToken(operation+"-RATE",1,jwt.getClaimAsString("tenant"),jwt.getSubject(),rate.path("requests").asInt(),rate.path("windowSeconds").asInt(),rate.path("burst").asInt()))throw new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS,"INTAKE_RATE");
  var call=new InvocationCore.Call(operation,1,operation+"-IDEMPOTENCY",1,"NEW:"+jwt.getSubject(),InvocationCore.typed("{\"kind\":\"String\"}",key.asText()),typed,contract.path("idempotencySeconds").asInt());
  try{return invocations.invoke(List.of(call),null,jwt,()->{
   @SuppressWarnings("unchecked") Map<String,Object> replay=InvocationCore.replay(operation,Map.class);if(replay!=null)return replay;
   String id=UUID.randomUUID().toString();List<Object> parameters=new ArrayList<>();
   parameters.add(bytes(id));parameters.add(bytes(jwt.getClaimAsString("tenant")));parameters.add(bytes(jwt.getSubject()));
   for(var binding:contract.path("orderedInputs")){
    Object value=values.get(binding.path("name").asText());
    if(!binding.path("member").isNull())try{value=mapper.writeValueAsString(Map.of(binding.path("member").asText(),value));}catch(Exception e){throw new IllegalArgumentException("INTAKE_VALUE");}
    parameters.add(bytes((String)value));
   }
   jdbc.update(contract.path("insertSQL").asText(),parameters.toArray());store.audit(operation,id,jwt);
   List<String> written=new ArrayList<>();contract.path("writtenFields").forEach(f->written.add(f.asText()));store.classifiedAudit(operation,id,"WRITE",written.toArray(String[]::new),jwt);
   return InvocationCore.capture(operation,Map.<String,Object>of("resourceId",id,"version",0,"state",contract.path("initialState").asText()));
  });}catch(InvocationCore.Outcome e){throw switch(e.getMessage()){case "IDEMPOTENCY_CONFLICT"->new ResponseStatusException(HttpStatus.CONFLICT,"IDEMPOTENCY_CONFLICT");case "IN_PROGRESS"->new ResponseStatusException(HttpStatus.ACCEPTED,"IN_PROGRESS");case "RATE_DENIED"->new ResponseStatusException(HttpStatus.TOO_MANY_REQUESTS,"INTAKE_RATE");default->new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,"INTAKE_INTERNAL");};}
 }
 private static boolean validUnicode(String s){for(int i=0;i<s.length();i++){char c=s.charAt(i);if(Character.isHighSurrogate(c)){if(++i>=s.length()||!Character.isLowSurrogate(s.charAt(i)))return false;}else if(Character.isLowSurrogate(c))return false;}return true;}
}
