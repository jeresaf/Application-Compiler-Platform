package acp.api;
import acp.infrastructure.*;
import acp.security.ApplicationPolicy;
import com.fasterxml.jackson.databind.*;
import java.nio.*;
import java.nio.charset.*;
import java.security.*;
import java.util.*;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartHttpServletRequest;
import org.springframework.transaction.*;
import org.springframework.transaction.support.TransactionTemplate;

/** Generated transactional content, never a filename-based filesystem store. */
@RestController @ConditionalOnProperty(name="acp.documents.mode",havingValue="preview")
public final class DocumentController {
 public static final String DOCUMENT_ID=${DOCUMENT_ID};
 private final JdbcTemplate jdbc;private final ApplicationPolicy policy;private final TargetModel model;private final JsonNode c;private final TransactionTemplate tx;private final int maximum;
 private final ObjectMapper mapper=new ObjectMapper();
 public DocumentController(JdbcTemplate jdbc,ApplicationPolicy policy,TargetModel model,PlatformTransactionManager manager,@org.springframework.beans.factory.annotation.Value("${acp.runtime.mode:production}") String mode,@org.springframework.beans.factory.annotation.Value("${acp.documents.maximum-bytes:0}") int configured)throws Exception{
  if(!mode.equals("development"))throw new IllegalStateException("DOCUMENT_PREVIEW_ONLY");this.jdbc=jdbc;this.policy=policy;this.model=model;
  try(var in=getClass().getResourceAsStream("/acp-documents.json")){c=mapper.readTree(in);}
  if(!DOCUMENT_ID.equals(c.path("id").asText())||!"UNAPPROVED_DOCUMENT_PREVIEW".equals(c.path("scope").asText()))throw new IllegalStateException("DOCUMENT_IDENTITY");
  maximum=configured==0?c.path("maximumBytes").asInt():configured;if(maximum<1||maximum>c.path("maximumBytes").asInt())throw new IllegalStateException("DOCUMENT_SIZE_POLICY");tx=new TransactionTemplate(manager);
 }
 @ExceptionHandler(org.springframework.web.server.ResponseStatusException.class)
 public ResponseEntity<Map<String,String>> failure(org.springframework.web.server.ResponseStatusException e){return ResponseEntity.status(e.getStatusCode()).body(Map.of("code",e.getReason()));}
 private void reject(int status,String code){throw new org.springframework.web.server.ResponseStatusException(HttpStatusCode.valueOf(status),code);}
 private byte[] bytes(String s){return s.getBytes(StandardCharsets.UTF_8);}
 private String hash(byte[] raw){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw));}catch(Exception e){throw new IllegalStateException(e);}}
 private String token(String s,int maximum){if(s==null||!s.matches("[A-Za-z0-9][A-Za-z0-9_-]{0,"+(maximum-1)+"}"))reject(400,"DOCUMENT_IDENTIFIER");return s;}
 private void grant(Jwt jwt,boolean upload){policy.actor(jwt);var g=c.path(upload?"uploadPermission":"readPermission");if(model.nodes("RoleAssignment").stream().noneMatch(n->{var d=n.path("data");return d.path("principal").asText().equals(jwt.getSubject())&&d.path("actor").equals(g.path("actor"))&&d.path("role").equals(g.path("role"))&&d.path("scope").equals(g.path("scope"));}))throw new AccessDeniedException("DOCUMENT_PERMISSION_DENIED");}
 private void resource(Jwt jwt,String id){
  var rows=jdbc.queryForList("SELECT acp_state FROM "+c.path("resourceTable").asText()+" WHERE "+c.path("resourceTenant").asText()+"=? AND "+c.path("resourceOwner").asText()+"=? AND "+c.path("resourceIdentity").asText()+"=? FOR UPDATE",bytes(jwt.getClaimAsString("tenant")),bytes(jwt.getSubject()),bytes(id));
  if(rows.size()!=1)reject(404,"DOCUMENT_RESOURCE_NOT_FOUND");
  if(jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_anchor WHERE tenant=? AND resource=? AND entity=? AND status IN ('COMPLETED','INDETERMINATE')",Integer.class,bytes(jwt.getClaimAsString("tenant")),bytes(id),c.path("resourceEntity").asText())!=0)reject(404,"DOCUMENT_RESOURCE_NOT_FOUND");
 }
 private void audit(Jwt jwt,String resource,String operation,String id,String hash){Long audit=jdbc.queryForObject("INSERT INTO acp_audit(tenant,subject,operation,resource) VALUES(?,?,?,?) RETURNING id",Long.class,bytes(jwt.getClaimAsString("tenant")),bytes(jwt.getSubject()),operation,bytes(resource));jdbc.update("INSERT INTO "+c.path("table").asText()+"_audit(audit_id,document,sha256) VALUES(?,?,?)",audit,UUID.fromString(id),hash);}
 private Map<String,Object> metadata(Map<String,Object> row){return Map.of("documentId",row.get("id").toString(),"filename",row.get("filename"),"mediaType",row.get("media_type"),"size",row.get("size"),"sha256",row.get("sha256"),"createdAt",((java.sql.Timestamp)row.get("created_at")).toInstant().toString());}
 private String fields(){return "id,filename,media_type,size,sha256,created_at";}
 private Map<String,Object> find(Jwt jwt,String resource,String id){
  if(id==null||!id.matches("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"))reject(400,"DOCUMENT_IDENTIFIER");
  var rows=jdbc.queryForList("SELECT "+fields()+",content FROM "+c.path("table").asText()+" WHERE tenant=? AND resource=? AND id=?",bytes(jwt.getClaimAsString("tenant")),bytes(resource),UUID.fromString(id));if(rows.size()!=1)reject(404,"DOCUMENT_NOT_FOUND");var row=rows.getFirst();byte[] raw=(byte[])row.get("content");if(raw.length!=((Number)row.get("size")).intValue()||!hash(raw).equals(row.get("sha256")))reject(409,"DOCUMENT_CONTENT_INTEGRITY");return row;
 }
 private String string(JsonNode n){if(!n.isTextual())reject(400,"DOCUMENT_INPUT");return n.asText();}
 private void keys(JsonNode body,Set<String> keys){if(body==null||!body.isObject())reject(400,"DOCUMENT_INPUT");body.fieldNames().forEachRemaining(k->{if(!keys.contains(k))reject(400,"DOCUMENT_INPUT");});}
 @PostMapping(value="${DOCUMENT_PATH}/upload",consumes=MediaType.MULTIPART_FORM_DATA_VALUE)
 public Map<String,Object> upload(MultipartHttpServletRequest request,@AuthenticationPrincipal Jwt jwt)throws Exception{
  grant(jwt,true);if(!request.getParameterMap().keySet().equals(Set.of("resourceId","idempotencyKey","sha256"))||request.getParameterMap().values().stream().anyMatch(v->v.length!=1)||!request.getMultiFileMap().keySet().equals(Set.of("content"))||request.getMultiFileMap().get("content").size()!=1)reject(400,"DOCUMENT_INPUT");
  String resource=token(request.getParameter("resourceId"),128),key=token(request.getParameter("idempotencyKey"),80),claimed=request.getParameter("sha256");var file=request.getFile("content");if(file==null||file.isEmpty())reject(400,"DOCUMENT_EMPTY");if(file.getSize()>maximum)reject(413,"DOCUMENT_TOO_LARGE");String filename=file.getOriginalFilename(),mime=file.getContentType();
  if(filename==null||filename.length()>120||!filename.endsWith(".txt")||filename.contains("..")||filename.contains("/")||filename.contains("\\")||filename.contains(":")||filename.startsWith(".")||filename.chars().anyMatch(x->x<32||x==127)||!filename.matches("[A-Za-z0-9][A-Za-z0-9 ._-]*\\.txt"))reject(400,"DOCUMENT_FILENAME");
  if(!"text/plain".equals(mime))reject(415,"DOCUMENT_MEDIA_TYPE");byte[] raw=file.getBytes();String text;
  try{text=StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(raw)).toString();}catch(CharacterCodingException e){reject(415,"DOCUMENT_CONTENT_TYPE");return Map.of();}
  if(text.chars().anyMatch(x->x==0||(x<32&&x!=9&&x!=10&&x!=13)))reject(415,"DOCUMENT_CONTENT_TYPE");String digest=hash(raw);if(!digest.equals(claimed))reject(409,"DOCUMENT_CONTENT_INTEGRITY");String requestHash=hash(mapper.writeValueAsBytes(new TreeMap<>(Map.of("filename",filename,"mediaType",mime,"sha256",digest,"principal",jwt.getSubject()))));
  return tx.execute(status->{resource(jwt,resource);var existing=jdbc.queryForList("SELECT "+fields()+",request_hash,content FROM "+c.path("table").asText()+" WHERE tenant=? AND resource=? AND idempotency_key=?",bytes(jwt.getClaimAsString("tenant")),bytes(resource),key);
   if(!existing.isEmpty()){var row=existing.getFirst();if(!requestHash.equals(row.get("request_hash")))reject(409,"DOCUMENT_IDEMPOTENCY_CONFLICT");return metadata(find(jwt,resource,row.get("id").toString()));}
   UUID id=UUID.randomUUID();jdbc.update("INSERT INTO "+c.path("table").asText()+"(id,tenant,resource,principal,filename,media_type,content,sha256,size,idempotency_key,request_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?)",id,bytes(jwt.getClaimAsString("tenant")),bytes(resource),bytes(jwt.getSubject()),filename,mime,raw,digest,raw.length,key,requestHash);audit(jwt,resource,c.path("uploadOperation").asText(),id.toString(),digest);return metadata(find(jwt,resource,id.toString()));});
 }
 @PostMapping("${DOCUMENT_PATH}/list")
 public Map<String,Object> list(@RequestBody JsonNode body,@AuthenticationPrincipal Jwt jwt){grant(jwt,false);keys(body,Set.of("resourceId","page","size"));String resource=token(string(body.path("resourceId")),128);int page=number(body.path("page"),0,0,1000),size=number(body.path("size"),20,1,20);return tx.execute(status->{resource(jwt,resource);var args=new Object[]{bytes(jwt.getClaimAsString("tenant")),bytes(resource)};Long total=jdbc.queryForObject("SELECT count(*) FROM "+c.path("table").asText()+" WHERE tenant=? AND resource=?",Long.class,args);var items=jdbc.queryForList("SELECT "+fields()+" FROM "+c.path("table").asText()+" WHERE tenant=? AND resource=? ORDER BY created_at,id LIMIT ? OFFSET ?",args[0],args[1],size,page*size).stream().map(this::metadata).toList();return Map.<String,Object>of("items",items,"total",total,"page",page,"size",size);});}
 private int number(JsonNode n,int fallback,int low,int high){if(n.isMissingNode())return fallback;if(!n.isIntegralNumber()||!n.canConvertToInt()||n.asInt()<low||n.asInt()>high)reject(400,"DOCUMENT_PAGE");return n.asInt();}
 @PostMapping("${DOCUMENT_PATH}/metadata")
 public Map<String,Object> metadata(@RequestBody JsonNode body,@AuthenticationPrincipal Jwt jwt){grant(jwt,false);keys(body,Set.of("resourceId","documentId"));String resource=token(string(body.path("resourceId")),128),id=string(body.path("documentId"));return tx.execute(status->{resource(jwt,resource);return metadata(find(jwt,resource,id));});}
 @PostMapping("${DOCUMENT_PATH}/download")
 public ResponseEntity<byte[]> download(@RequestBody JsonNode body,@AuthenticationPrincipal Jwt jwt){grant(jwt,false);keys(body,Set.of("resourceId","documentId"));String resource=token(string(body.path("resourceId")),128),id=string(body.path("documentId"));return tx.execute(status->{resource(jwt,resource);var row=find(jwt,resource,id);audit(jwt,resource,c.path("downloadOperation").asText(),id,row.get("sha256").toString());return ResponseEntity.ok().contentType(MediaType.APPLICATION_OCTET_STREAM).header("Content-Disposition",ContentDisposition.attachment().filename(row.get("filename").toString(),StandardCharsets.UTF_8).build().toString()).header("X-Content-Type-Options","nosniff").header("Cache-Control","no-store").header("Content-Security-Policy","sandbox; default-src 'none'").header("X-Content-SHA256",row.get("sha256").toString()).body((byte[])row.get("content"));});}
}
