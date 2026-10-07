package acp.domain;

import acp.infrastructure.TargetModel;
import com.fasterxml.jackson.databind.JsonNode;
import java.math.BigDecimal;
import java.util.Map;
import java.util.Objects;
import org.springframework.stereotype.Component;

@Component
public final class Expressions {
    private final TargetModel model;
    public Expressions(TargetModel model) { this.model = model; }

    public Object evaluate(JsonNode expression, Map<String, Object> resource, Map<String, Object> actor) {
        return switch (expression.path("tag").asText()) {
            case "literal" -> literal(expression.path("value"));
            case "parameter" -> literal(model.node(expression.path("ref").path("id").asText()).path("data").path("value"));
            case "field" -> (expression.path("binding").asText().equals("resource") ? resource : actor).get(expression.path("ref").path("id").asText());
            case "binary" -> binary(expression, resource, actor);
            default -> throw new IllegalArgumentException("UNSUPPORTED_EXPRESSION");
        };
    }

    private Object binary(JsonNode e, Map<String, Object> resource, Map<String, Object> actor) {
        Object left = evaluate(e.path("left"), resource, actor);
        Object right = evaluate(e.path("right"), resource, actor);
        return switch (e.path("op").asText()) {
            case "and" -> Boolean.TRUE.equals(left) && Boolean.TRUE.equals(right);
            case "or" -> Boolean.TRUE.equals(left) || Boolean.TRUE.equals(right);
            case "identityEq", "eq" -> left != null && right != null && Objects.equals(left, right);
            case "gt" -> left != null && right != null && new BigDecimal(left.toString()).compareTo(new BigDecimal(right.toString())) > 0;
            case "gte" -> left != null && right != null && new BigDecimal(left.toString()).compareTo(new BigDecimal(right.toString())) >= 0;
            default -> throw new IllegalArgumentException("UNSUPPORTED_OPERATOR");
        };
    }

    private Object literal(JsonNode value) {
        if (value.isNull()) return null;
        if (value.isBoolean()) return value.asBoolean();
        if (value.isNumber()) return value.decimalValue();
        if (value.isTextual()) return value.asText();
        throw new IllegalArgumentException("UNSUPPORTED_LITERAL");
    }
}
