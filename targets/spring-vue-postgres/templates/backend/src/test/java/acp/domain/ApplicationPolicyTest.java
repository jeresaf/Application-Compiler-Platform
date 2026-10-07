package acp.domain;

import acp.infrastructure.TargetModel;
import acp.security.ApplicationPolicy;
import java.util.HashMap;
import org.junit.jupiter.api.Test;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.oauth2.jwt.Jwt;
import static org.junit.jupiter.api.Assertions.*;

class ApplicationPolicyTest {
    @Test void tenantPoliciesRequireCanonicalAssignmentAndDenyCrossTenant() throws Exception {
        var model = new TargetModel();
        var policy = new ApplicationPolicy(model, new Expressions(model));
        var identity = Jwt.withTokenValue("test-only").header("alg", "none").subject("fixture:operator").claim("tenant", "tenant-one").build();
        for (var query : model.nodes("Query")) {
            String action = query.path("id").asText();
            var scope = model.node(query.path("data").path("scope").path("id").asText()).path("data");
            var resource = new HashMap<String, Object>();
            resource.put(scope.path("resourceTenant").path("id").asText(), "tenant-one");
            assertDoesNotThrow(() -> policy.require(action, resource, identity));
            resource.put(scope.path("resourceTenant").path("id").asText(), "tenant-two");
            assertThrows(AccessDeniedException.class, () -> policy.require(action, resource, identity));
        }
        assertThrows(AccessDeniedException.class, () -> policy.actor(null));
    }
}
