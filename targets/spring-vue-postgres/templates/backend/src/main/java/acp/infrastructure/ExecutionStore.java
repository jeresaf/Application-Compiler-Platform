package acp.infrastructure;

import acp.security.ApplicationPolicy;
import acp.security.PrivacyGuards;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronizationManager;

/** Infrastructure ports only. Generated code supplies exact effects and typed contracts. */
@Component
public final class ExecutionStore {
    private final JdbcTemplate jdbc;
    private final ApplicationPolicy policy;
    private final PrivacyGuards privacy;
    private final ObjectMapper mapper = new ObjectMapper();
    public ExecutionStore(JdbcTemplate jdbc, ApplicationPolicy policy, PrivacyGuards privacy) {
        this.jdbc=jdbc; this.policy=policy; this.privacy=privacy;
        if (!"UTF8".equals(jdbc.queryForObject("SHOW server_encoding",String.class))) throw new IllegalStateException("POSTGRESQL_UTF8_REQUIRED");
        String version=jdbc.queryForObject("SHOW server_version",String.class);
        if (version==null || !version.matches("18\\.6(?:\\s.*)?")) throw new IllegalStateException("POSTGRESQL_18_6_REQUIRED");
    }
    public record Row<T>(T value, long version, String state) {}
    public record Completion<T>(T output, String resourceId, long version, String state) {}

    public <T> Row<T> lock(String table, String identity, String tenant, String id, Jwt jwt, RowMapper<Row<T>> reader) {
        transaction();
        if (id == null || id.isBlank() || jwt == null || jwt.getClaimAsString("tenant") == null || jwt.getClaimAsString("tenant").isBlank())
            throw new IllegalArgumentException("RESOURCE_IDENTITY_TENANT");
        var rows=jdbc.query("SELECT * FROM " + table + " WHERE " + identity + "=? AND " + tenant + "=? FOR UPDATE", reader, bytes(id), bytes(jwt.getClaimAsString("tenant")));
        if (rows.size()!=1) throw new IllegalArgumentException("RESOURCE_NOT_FOUND");
        return rows.getFirst();
    }
    public <T> List<Row<T>> query(String sql, RowMapper<Row<T>> reader, Object... parameters) {
        return jdbc.query(sql, reader, parameters);
    }
    public void authorize(String operation, Map<String,Object> preState, Jwt jwt) { policy.require(operation, preState, jwt); }
    public void authenticate(Jwt jwt) { policy.actor(jwt); }
    public void update(String sql, Object... parameters) {
        transaction();
        if (jdbc.update(sql,parameters)!=1) throw new IllegalStateException("VERSION_CONFLICT");
    }
    public void audit(String operation, String resource, Jwt jwt) {
        transaction();
        jdbc.update("INSERT INTO acp_audit(tenant,subject,operation,resource) VALUES(?,?,?,?)", bytes(jwt.getClaimAsString("tenant")), bytes(jwt.getSubject()), operation, bytes(resource));
    }
    public void classifiedAudit(String operation, String resource, String mode, String[] fields, Jwt jwt) {
        transaction();
        for (String field:fields) if (privacy.audit(field,mode))
            jdbc.update("INSERT INTO acp_classification_audit(tenant,subject,operation,resource,field,mode) VALUES(?,?,?,?,?,?)",
                bytes(jwt.getClaimAsString("tenant")),bytes(jwt.getSubject()),operation,bytes(resource),field,mode);
    }
    public void event(String operation, String event, String resource, long version, Object typedPayload, Jwt jwt) {
        transaction();
        String tenant=jwt.getClaimAsString("tenant");
        String id=TargetModel.identifier(tenant+":"+operation+":"+resource+":"+version+":"+event,"event");
        jdbc.update("INSERT INTO acp_outbox(id,tenant,event,resource,aggregate_version,payload) VALUES(?,?,?,?,?,?)", id,bytes(tenant),event,bytes(resource),version,bytes(encode(typedPayload)));
    }
    private static final Object EVENT_CONTEXT=new Object();
    private static final class EventContext { int step; final Map<String,Long> sequence=new HashMap<>(); }
    private EventContext events() {
        transaction();
        EventContext c=(EventContext)TransactionSynchronizationManager.getResource(EVENT_CONTEXT);
        if(c==null) {
            c=new EventContext();TransactionSynchronizationManager.bindResource(EVENT_CONTEXT,c);
            TransactionSynchronizationManager.registerSynchronization(new org.springframework.transaction.support.TransactionSynchronization() {
                @Override public void suspend(){TransactionSynchronizationManager.unbindResourceIfPossible(EVENT_CONTEXT);}
                @Override public void resume(){TransactionSynchronizationManager.bindResource(EVENT_CONTEXT,captured);}
                private final EventContext captured=(EventContext)TransactionSynchronizationManager.getResource(EVENT_CONTEXT);
                @Override public void afterCompletion(int status){TransactionSynchronizationManager.unbindResourceIfPossible(EVENT_CONTEXT);}
            });
        }
        return c;
    }
    public void stepOrdinal(int step){events().step=step;}
    public void event(String operation,int operationRevision,String event,int eventRevision,String aggregate,int aggregateRevision,int emission,String resource,long version,Object payload,Jwt jwt) {
        EventContext c=events();String tenant=jwt.getClaimAsString("tenant");
        String group=encode(List.of(tenant,aggregate,aggregateRevision,resource));
        long sequence=c.sequence.computeIfAbsent(group,k->version);
        String identity=encode(List.of(tenant,aggregate,aggregateRevision,resource,sequence,operation,operationRevision,event,eventRevision,c.step,emission));
        String id;
        try{id=java.util.HexFormat.of().formatHex(java.security.MessageDigest.getInstance("SHA-256").digest(bytes(identity)));}
        catch(java.security.NoSuchAlgorithmException e){throw new IllegalStateException("SHA256_REQUIRED");}
        jdbc.update("INSERT INTO acp_outbox(id,tenant,event,resource,aggregate_version,payload,operation,operation_revision,event_revision,aggregate_id,aggregate_revision,commit_sequence,step_ordinal,emission_ordinal,commit_xid,delivery_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,pg_current_xact_id()::text,'PENDING')",
            id,bytes(tenant),event,bytes(resource),version,bytes(encode(payload)),operation,operationRevision,eventRevision,aggregate,aggregateRevision,sequence,c.step,emission);
    }
    /** Exact terminal entry fact, captured in the same semantic transaction. */
    public void closed(String entity,String resource,String previous,String state,long version,Jwt jwt) {
        transaction();
        for(var life:privacy.model().nodes("DataLifecycle")) {
            var data=life.path("data");if(!entity.equals(data.path("resource").path("id").asText()))continue;
            var anchor=data.path("anchor");if(!"CLOSED_COMMIT".equals(anchor.path("kind").asText()))continue;
            for(var closing:anchor.path("states"))if(closing.path("id").asText().equals(state) && !java.util.Objects.equals(previous,state))
                jdbc.update("INSERT INTO acp_lifecycle_anchor(lifecycle,revision,tenant,resource,entity,machine,machine_revision,closing_state,state_revision,anchor_xid,root_version,status) VALUES(?,?,?,?,?,?,?,?,?,pg_current_xact_id()::text,?,'ANCHORED') ON CONFLICT DO NOTHING",life.path("id").asText(),life.path("revision").asInt(),bytes(jwt.getClaimAsString("tenant")),bytes(resource),entity,anchor.path("machine").path("id").asText(),anchor.path("machine").path("revision").asInt(),state,closing.path("revision").asInt(),version);
        }
    }
    private static void transaction() {
        if (!TransactionSynchronizationManager.isActualTransactionActive()) throw new IllegalStateException("TRANSACTION_REQUIRED");
    }
    public JsonNode json(String value) {
        try { return mapper.readTree(value); } catch (Exception e) { throw new IllegalArgumentException("STORED_VALUE",e); }
    }
    public String encode(Object typed) {
        try { return mapper.writeValueAsString(typed); } catch (Exception e) { throw new IllegalArgumentException("TYPED_VALUE",e); }
    }
    public static byte[] bytes(String text) {
        if (text==null) return null;
        try {
            var buffer=java.nio.charset.StandardCharsets.UTF_8.newEncoder()
                .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
                .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT).encode(java.nio.CharBuffer.wrap(text));
            byte[] result=new byte[buffer.remaining()]; buffer.get(result); return result;
        } catch (java.nio.charset.CharacterCodingException error) { throw new IllegalArgumentException("UNICODE_SCALAR",error); }
    }
    public static String text(byte[] bytes) {
        if (bytes==null) return null;
        try {
            return java.nio.charset.StandardCharsets.UTF_8.newDecoder()
                .onMalformedInput(java.nio.charset.CodingErrorAction.REPORT)
                .onUnmappableCharacter(java.nio.charset.CodingErrorAction.REPORT).decode(java.nio.ByteBuffer.wrap(bytes)).toString();
        } catch (java.nio.charset.CharacterCodingException error) { throw new IllegalArgumentException("STORED_UNICODE_SCALAR",error); }
    }
    public static Map<String,Object> semantic(Object[]... pairs) {
        Map<String,Object> result=new HashMap<>();
        var mapper=new ObjectMapper();
        for (var p:pairs) {
            Object v=p[1];
            if (v!=null && v.getClass().isRecord()) {
                JsonNode node=mapper.valueToTree(v);
                if (node.isTextual()) v=node.textValue();
            }
            result.put((String)p[0],v);
        }
        return result;
    }
    public static BigDecimal number(Object typed) {
        if (typed==null) throw new IllegalArgumentException("NULL_NUMBER");
        JsonNode n=new ObjectMapper().valueToTree(typed);
        if (!n.isTextual() && !n.isNumber()) throw new IllegalArgumentException("NUMBER_REQUIRED");
        return new BigDecimal(n.asText());
    }
}
