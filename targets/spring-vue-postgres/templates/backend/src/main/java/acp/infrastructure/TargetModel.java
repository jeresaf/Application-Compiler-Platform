package acp.infrastructure;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import org.springframework.stereotype.Component;

@Component
public final class TargetModel {
    public final JsonNode model;

    public TargetModel() throws Exception {
        try (var input = getClass().getResourceAsStream("/acp-model.json")) {
            if (input == null) throw new IllegalStateException("MISSING_TARGET_MODEL");
            model = new ObjectMapper().readTree(input);
        }
    }

    public JsonNode node(String id) {
        for (var node : model.path("nodes")) if (node.path("id").asText().equals(id)) return node;
        throw new IllegalArgumentException("UNKNOWN_SEMANTIC_ID");
    }

    public List<JsonNode> nodes(String kind) {
        List<JsonNode> result = new ArrayList<>();
        for (var node : model.path("nodes")) if (node.path("kind").asText().equals(kind)) result.add(node);
        return List.copyOf(result);
    }

    public JsonNode table(String id) {
        for (var table : model.path("tables")) if (table.path("origin").path("id").asText().equals(id)) return table;
        throw new IllegalArgumentException("UNKNOWN_RESOURCE");
    }

    public static String identifier(String id, String role) {
        try {
            return role + "_" + HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(id.getBytes(StandardCharsets.UTF_8))).substring(0, 24);
        } catch (Exception error) {
            throw new IllegalStateException("IDENTIFIER", error);
        }
    }
}
