package acp.application;

import acp.domain.Expressions;
import acp.infrastructure.TargetModel;
import acp.security.ApplicationPolicy;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Task execution starts with canonical UseCase/Command/Query, never table CRUD. */
@Service
public class TaskService {
    private final TargetModel model;
    private final ApplicationPolicy policy;
    private final Expressions expressions;
    private final JdbcTemplate jdbc;
    public TaskService(TargetModel model, ApplicationPolicy policy, Expressions expressions, JdbcTemplate jdbc) {
        this.model = model; this.policy = policy; this.expressions = expressions; this.jdbc = jdbc;
    }

    @Transactional
    public Map<String, Object> execute(String operation, String resourceId, long expectedVersion, Map<String, Object> input, Jwt jwt) {
        var node = model.node(operation);
        if (node.path("kind").asText().equals("UseCase")) {
            String inputType = node.path("data").path("input").path("id").asText();
            for (var field : model.nodes("Field")) {
                var data = field.path("data");
                if (data.path("owner").path("id").asText().equals(inputType) && !data.path("optional").asBoolean()) {
                    Object value = input.get(field.path("id").asText());
                    if (!(value instanceof String text) || text.isBlank()) throw new IllegalArgumentException("REQUIRED_INPUT");
                }
            }
            Map<String, Object> result = Map.of();
            long version = expectedVersion;
            for (var step : node.path("data").path("steps")) {
                var execution = model.node(step.path("id").asText()).path("data");
                result = command(execution.path("operation").path("id").asText(), resourceId, version, jwt);
                version = ((Number) result.get("version")).longValue();
            }
            return result;
        }
        if (!node.path("kind").asText().equals("Command")) throw new IllegalArgumentException("COMMAND_REQUIRED");
        return command(operation, resourceId, expectedVersion, jwt);
    }

    private Map<String, Object> command(String operation, String resourceId, long expectedVersion, Jwt jwt) {
        var command = model.node(operation).path("data");
        String entity = command.path("resource").path("id").asText();
        var table = model.table(entity);
        var semantic = table.path("semantic");
        String identity = TargetModel.identifier(semantic.path("identity").get(0).path("id").asText(), "f");
        String tenant = TargetModel.identifier(semantic.path("tenantField").path("id").asText(), "f");
        var rows = jdbc.queryForList("SELECT * FROM " + table.path("name").asText() + " WHERE " + identity + "=? AND " + tenant + "=? FOR UPDATE", resourceId, jwt.getClaimAsString("tenant"));
        if (rows.size() != 1) throw new IllegalArgumentException("RESOURCE_NOT_FOUND");
        var row = rows.get(0);
        var resource = semanticFields(table, row);
        policy.require(operation, resource, jwt);
        long version = ((Number) row.get("acp_version")).longValue();
        if (version != expectedVersion) throw new IllegalStateException("VERSION_CONFLICT");
        var actor = policy.actor(jwt);
        for (var ref : command.path("invariants")) {
            if (!Boolean.TRUE.equals(expressions.evaluate(model.node(ref.path("id").asText()).path("data").path("predicate"), resource, actor))) throw new IllegalArgumentException("INVARIANT");
        }
        String state = (String) row.get("acp_state");
        List<JsonNode> transitions = new ArrayList<>();
        for (var transition : model.nodes("Transition")) {
            var data = transition.path("data");
            if (data.path("command").path("id").asText().equals(operation)) transitions.add(data);
        }
        if (!transitions.isEmpty()) {
            boolean found = false;
            for (var transition : transitions) {
                var machine = model.node(transition.path("machine").path("id").asText()).path("data");
                String current = state == null ? machine.path("initial").path("id").asText() : state;
                if (transition.path("from").path("id").asText().equals(current) && Boolean.TRUE.equals(expressions.evaluate(transition.path("guard"), resource, actor))) {
                    state = transition.path("to").path("id").asText(); found = true; break;
                }
            }
            if (!found) throw new IllegalStateException("TRANSITION_DENIED");
        }
        int changed = jdbc.update("UPDATE " + table.path("name").asText() + " SET acp_state=?,acp_version=acp_version+1 WHERE " + identity + "=? AND " + tenant + "=? AND acp_version=?", state, resourceId, jwt.getClaimAsString("tenant"), version);
        if (changed != 1) throw new IllegalStateException("VERSION_CONFLICT");
        jdbc.update("INSERT INTO acp_audit(tenant,subject,operation,resource) VALUES(?,?,?,?)", jwt.getClaimAsString("tenant"), jwt.getSubject(), operation, resourceId);
        for (var event : command.path("emits")) {
            String eventId = event.path("id").asText();
            String outboxId = TargetModel.identifier(jwt.getClaimAsString("tenant") + ":" + operation + ":" + resourceId + ":" + (version + 1) + ":" + eventId, "event");
            jdbc.update("INSERT INTO acp_outbox(id,tenant,event,resource,aggregate_version) VALUES(?,?,?,?,?)", outboxId, jwt.getClaimAsString("tenant"), eventId, resourceId, version + 1);
        }
        return Map.of("resourceId", resourceId, "version", version + 1, "state", state == null ? "" : state);
    }

    @Transactional(readOnly = true)
    public List<Map<String, Object>> query(String operation, int offset, int limit, String search, Jwt jwt) {
        var query = model.node(operation);
        if (!query.path("kind").asText().equals("Query")) throw new IllegalArgumentException("QUERY_REQUIRED");
        var data = query.path("data");
        if (offset < 0 || limit < 1 || limit > data.path("maximumResults").asInt()) throw new IllegalArgumentException("PAGINATION");
        var table = model.table(data.path("resource").path("id").asText());
        String tenantId = table.path("semantic").path("tenantField").path("id").asText();
        policy.require(operation, Map.of(tenantId, jwt.getClaimAsString("tenant")), jwt);
        String identityId = table.path("semantic").path("identity").get(0).path("id").asText();
        String tenant = TargetModel.identifier(tenantId, "f"), identity = TargetModel.identifier(identityId, "f");
        List<Map<String, Object>> result = new ArrayList<>();
        for (var row : jdbc.queryForList("SELECT * FROM " + table.path("name").asText() + " WHERE " + tenant + "=? ORDER BY " + identity + " LIMIT ? OFFSET ?", jwt.getClaimAsString("tenant"), limit, offset)) {
            var resource = semanticFields(table, row);
            var projected = new LinkedHashMap<String, Object>();
            projected.put("resourceId", resource.get(identityId)); projected.put("version", row.get("acp_version"));
            projected.put("state", row.get("acp_state"));
            for (var projection : data.path("projection")) projected.put(projection.path("field").path("id").asText(), expressions.evaluate(projection.path("value"), resource, policy.actor(jwt)));
            if (search.isEmpty() || projected.values().stream().anyMatch(value -> value != null && value.toString().contains(search))) result.add(projected);
        }
        return List.copyOf(result);
    }

    private static Map<String, Object> semanticFields(JsonNode table, Map<String, Object> row) {
        var result = new HashMap<String, Object>();
        for (var column : table.path("columns")) result.put(column.path("origin").path("id").asText(), row.get(column.path("name").asText()));
        return result;
    }
}
