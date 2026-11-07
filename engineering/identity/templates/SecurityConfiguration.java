package acp.security;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.interfaces.RSAPublicKey;
import java.time.Duration;
import java.util.*;
import com.fasterxml.jackson.databind.*;
import com.nimbusds.jose.jwk.*;
import com.nimbusds.jwt.SignedJWT;
import acp.infrastructure.TargetModel;
import org.springframework.context.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.authorization.AuthorizationDecision;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.core.*;
import org.springframework.security.oauth2.jose.jws.SignatureAlgorithm;
import org.springframework.security.oauth2.jwt.*;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.security.web.SecurityFilterChain;
/** H5 host-pinned JWT profile. No token-controlled discovery or key retrieval. */
@Configuration
public class SecurityConfiguration {
 private final JsonNode config;private final Path keys;private final String keyDigest;private final Map<String,NimbusJwtDecoder> decoders;
 private static byte[] bounded(Path path)throws Exception{
  if(Files.isSymbolicLink(path)||!Files.isRegularFile(path,LinkOption.NOFOLLOW_LINKS)||Files.size(path)>32768)throw new IllegalArgumentException("IDENTITY_INPUT");
  byte[] raw=Files.readAllBytes(path);if(raw.length>32768)throw new IllegalArgumentException("IDENTITY_INPUT");return raw;
 }
 private static String sha(byte[] raw)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw));}
 private static void need(boolean value){if(!value)throw new IllegalArgumentException("IDENTITY_CONFIGURATION");}
 public SecurityConfiguration()throws Exception{
  String file=System.getenv("ACP_IDENTITY_CONFIG"),pin=System.getenv("ACP_IDENTITY_CONFIG_SHA256");need(file!=null&&pin!=null&&pin.matches("[0-9a-f]{64}"));
  need(Path.of(file).isAbsolute());byte[] raw=bounded(Path.of(file));need(sha(raw).equals(pin));config=new ObjectMapper().enable(com.fasterxml.jackson.core.JsonParser.Feature.STRICT_DUPLICATE_DETECTION).readTree(raw);
  Set<String> fields=new HashSet<>();config.fieldNames().forEachRemaining(fields::add);
  need(fields.equals(Set.of("profile","issuer","audience","algorithm","clockSkewSeconds","tenantClaim","roleMapping","keySetPath","keySetSHA256","tokenType","tokenUse")));
  for(String field:fields)if(!field.equals("clockSkewSeconds"))need(config.path(field).isTextual());
  need(config.path("profile").asText().equals("acp-bound-jwt/1")&&config.path("algorithm").asText().equals("RS256")&&config.path("clockSkewSeconds").isIntegralNumber()&&config.path("clockSkewSeconds").canConvertToInt()&&config.path("clockSkewSeconds").asInt()==0);
  need(config.path("issuer").asText().startsWith("https://")&&!config.path("audience").asText().isBlank()&&config.path("tenantClaim").asText().equals("tenant")&&config.path("roleMapping").asText().equals("CANONICAL_ROLE_ASSIGNMENT"));
  need(config.path("tokenType").asText().equals("JWT")&&config.path("tokenUse").asText().equals("access"));
  java.net.URI issuer=java.net.URI.create(config.path("issuer").asText());need("https".equals(issuer.getScheme())&&issuer.getHost()!=null&&issuer.getRawUserInfo()==null&&issuer.getRawQuery()==null&&issuer.getRawFragment()==null);
  keys=Path.of(config.path("keySetPath").asText());need(keys.isAbsolute());keyDigest=config.path("keySetSHA256").asText();need(keyDigest.matches("[0-9a-f]{64}"));
  byte[] publicSet=bounded(keys);need(sha(publicSet).equals(keyDigest));JWKSet set=JWKSet.parse(new String(publicSet,StandardCharsets.UTF_8));Map<String,NimbusJwtDecoder> map=new HashMap<>();
  need(!set.getKeys().isEmpty()&&set.getKeys().size()<=8);
  for(JWK jwk:set.getKeys()){
   need(jwk instanceof RSAKey&&!jwk.isPrivate()&&jwk.getKeyID()!=null&&jwk.getKeyID().matches("[A-Za-z0-9_-]{1,64}")&&com.nimbusds.jose.JWSAlgorithm.RS256.equals(jwk.getAlgorithm())&&KeyUse.SIGNATURE.equals(jwk.getKeyUse()));
   RSAPublicKey key=((RSAKey)jwk).toRSAPublicKey();need(key.getModulus().bitLength()>=2048);
   NimbusJwtDecoder decoder=NimbusJwtDecoder.withPublicKey(key).signatureAlgorithm(SignatureAlgorithm.RS256).build();
   decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<Jwt>(new JwtTimestampValidator(Duration.ZERO),new JwtIssuerValidator(config.path("issuer").asText()),jwt->{
    boolean ok=jwt.getAudience().contains(config.path("audience").asText())&&jwt.getExpiresAt()!=null&&jwt.getNotBefore()!=null&&jwt.getIssuedAt()!=null&&!jwt.getIssuedAt().isAfter(java.time.Instant.now())&&"access".equals(jwt.getClaimAsString("token_use"));
    return ok?OAuth2TokenValidatorResult.success():OAuth2TokenValidatorResult.failure(new OAuth2Error("invalid_token"));
   }));need(map.put(jwk.getKeyID(),decoder)==null);
  }decoders=Map.copyOf(map);
 }
 @Bean JwtDecoder boundJwtDecoder(){return token->{
  try{
   if(token.length()>8192||!sha(bounded(keys)).equals(keyDigest))throw new IllegalArgumentException();
   SignedJWT parsed=SignedJWT.parse(token);var header=parsed.getHeader();
   if(!header.toJSONObject().keySet().equals(Set.of("alg","kid","typ"))||!"RS256".equals(header.getAlgorithm().getName())||header.getType()==null||!"JWT".equals(header.getType().toString()))throw new IllegalArgumentException();
   var claims=parsed.getJWTClaimsSet().getClaims();
   JsonNode raw=new ObjectMapper().enable(com.fasterxml.jackson.core.JsonParser.Feature.STRICT_DUPLICATE_DETECTION).readTree(parsed.getPayload().toString());
   JsonNode audience=raw.path("aud");if(!audience.isTextual()&&!audience.isArray())throw new IllegalArgumentException();if(audience.isArray())for(JsonNode item:audience)if(!item.isTextual())throw new IllegalArgumentException();
   for(String field:List.of("exp","nbf","iat","auth_time"))if(!raw.path(field).isIntegralNumber()||!raw.path(field).canConvertToLong()||raw.path(field).asLong()<0)throw new IllegalArgumentException();
   for(String name:List.of("sub","tenant","sid"))if(!(claims.get(name) instanceof String value)||!value.matches("[A-Za-z0-9:_-]{1,128}"))throw new IllegalArgumentException();
   if(!(claims.get("auth_time") instanceof Number)||!(claims.get("amr") instanceof List<?> amr)||amr.stream().anyMatch(x->!(x instanceof String)))throw new IllegalArgumentException();
   NimbusJwtDecoder decoder=decoders.get(header.getKeyID());if(decoder==null)throw new IllegalArgumentException();return decoder.decode(token);
  }catch(Exception error){throw new BadJwtException("INVALID_BEARER_TOKEN");}
 };}
 private boolean principalBound(TargetModel model,JdbcTemplate jdbc,Jwt jwt){
  for(var actor:model.nodes("Actor")){
   var table=model.table(actor.path("data").path("subject").path("id").asText());var semantic=table.path("semantic");
   if(!semantic.path("tenancy").asText().equals("SCOPED")||semantic.path("identity").size()!=1)throw new IllegalStateException("IDENTITY_BINDING_UNSUPPORTED");
   String identity=TargetModel.identifier(semantic.path("identity").get(0).path("id").asText(),"f"),tenant=TargetModel.identifier(semantic.path("tenantField").path("id").asText(),"f");
   if(jdbc.queryForObject("SELECT count(*) FROM "+table.path("name").asText()+" WHERE "+identity+"=? AND "+tenant+"=?",Integer.class,jwt.getSubject().getBytes(StandardCharsets.UTF_8),jwt.getClaimAsString("tenant").getBytes(StandardCharsets.UTF_8))==1)return true;
  }return false;
 }
 @Bean SecurityFilterChain apiSecurity(HttpSecurity http,TargetModel model,JdbcTemplate jdbc)throws Exception{
  return http.csrf(csrf->csrf.disable()).sessionManagement(session->session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
   .authorizeHttpRequests(auth->auth.requestMatchers("/actuator/health","/actuator/health/**").permitAll().anyRequest().access((authentication,context)->new AuthorizationDecision(authentication.get() instanceof JwtAuthenticationToken bearer&&principalBound(model,jdbc,bearer.getToken()))))
   .oauth2ResourceServer(oauth->oauth.jwt(jwt->jwt.jwtAuthenticationConverter(token->new JwtAuthenticationToken(token,List.of())))).build();
 }
}
