package acp.api;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.SQLException;
import java.util.Collections;
import java.util.IdentityHashMap;

/** Versioned target mechanism. This does not manufacture declared business failures. */
public final class FailureMapping {
    private static final JsonNode CONTRACT = load();
    private FailureMapping() {}
    public record Result(String code, String category, int status, boolean retryable) {}
    private static JsonNode load() {
        try (var input=FailureMapping.class.getResourceAsStream("/acp-failure-mapping.json")) {
            if (input==null) throw new IllegalStateException("FAILURE_MAPPING_REQUIRED");
            var value=new ObjectMapper().readTree(input);
            if (!"1.0.0".equals(value.path("contractVersion").asText())) throw new IllegalStateException("FAILURE_MAPPING_VERSION");
            return value;
        } catch (Exception error) { throw new ExceptionInInitializerError("FAILURE_MAPPING_INVALID"); }
    }
    public static Result map(Throwable error) {
        var seen=Collections.newSetFromMap(new IdentityHashMap<Throwable,Boolean>());
        // Only recognized SQL states are unwrapped; arbitrary nested validation errors
        // cannot turn an unknown wrapper into a business or retryable failure.
        for (var cause=error; cause!=null && seen.add(cause); cause=cause.getCause()) {
            if (cause instanceof SQLException sql) {
                var match=CONTRACT.path("sqlStates").path(sql.getSQLState()==null ? "" : sql.getSQLState());
                return result(match.isMissingNode() ? CONTRACT.path("unknown") : match);
            }
        }
        JsonNode match=CONTRACT.path("exceptions").path(error.getClass().getName());
        return result(match.isMissingNode() ? CONTRACT.path("unknown") : match);
    }
    private static Result result(JsonNode value) {
        return new Result(value.path("code").asText(),value.path("category").asText(),value.path("status").asInt(),false);
    }
}
