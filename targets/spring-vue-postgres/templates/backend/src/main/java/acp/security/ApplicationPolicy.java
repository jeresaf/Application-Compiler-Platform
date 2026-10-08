package acp.security;

import acp.domain.Expressions;
import acp.infrastructure.TargetModel;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;

@Component
public final class ApplicationPolicy {
    private final TargetModel model;
    private final Expressions expressions;
    private final SessionGate sessions;
    public ApplicationPolicy(TargetModel model, Expressions expressions, SessionGate sessions) { this.model = model; this.expressions = expressions; this.sessions = sessions; }

    public Map<String, Object> actor(Jwt jwt) {
        sessions.require(jwt);
        if (jwt == null || jwt.getSubject() == null || jwt.getClaimAsString("tenant") == null) deny();
        var result = new HashMap<String, Object>();
        for (var actor : model.nodes("Actor")) {
            var entity = model.node(actor.path("data").path("subject").path("id").asText()).path("data");
            for (var identity : entity.path("identity")) result.put(identity.path("id").asText(), jwt.getSubject());
            if (entity.has("tenantField")) result.put(entity.path("tenantField").path("id").asText(), jwt.getClaimAsString("tenant"));
        }
        return result;
    }

    public void require(String action, Map<String, Object> resource, Jwt jwt) {
        var actor = actor(jwt);
        Set<String> roles = new HashSet<>();
        for (var assignment : model.nodes("RoleAssignment")) {
            var binding = assignment.path("data");
            if (binding.path("principal").asText().equals(jwt.getSubject())) roles.add(binding.path("role").path("id").asText() + "@" + binding.path("scope").path("id").asText() + "@" + binding.path("actor").path("id").asText());
        }
        boolean allowed = false;
        for (var policy : model.nodes("Policy")) {
            var data = policy.path("data");
            if (!data.path("action").path("id").asText().equals(action)) continue;
            boolean roleAllowed = false;
            for (var role : data.path("roles")) {
                String roleId = role.path("id").asText();
                if (!roles.contains(roleId + "@" + data.path("scope").path("id").asText() + "@" + data.path("actor").path("id").asText())) continue;
                for (var permission : model.node(roleId).path("data").path("permissions")) {
                    if (permission.path("id").asText().equals(data.path("permission").path("id").asText())) roleAllowed = true;
                }
            }
            if (!roleAllowed) continue;
            var scope = model.node(data.path("scope").path("id").asText()).path("data");
            String resourceTenant = scope.path("resourceTenant").path("id").asText();
            String actorTenant = scope.path("actorTenant").path("id").asText();
            if (!java.util.Objects.equals(resource.get(resourceTenant), actor.get(actorTenant)) || resource.get(resourceTenant) == null) continue;
            if (Boolean.TRUE.equals(expressions.evaluate(data.path("predicate"), resource, actor))) {
                if (data.path("effect").asText().equals("DENY")) deny();
                if (data.path("effect").asText().equals("ALLOW")) allowed = true;
            }
        }
        if (!allowed) deny();
    }

    private static void deny() { throw new AccessDeniedException("POLICY_DENIED"); }
}
