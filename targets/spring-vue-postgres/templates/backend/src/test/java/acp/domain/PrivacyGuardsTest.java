package acp.domain;

import acp.infrastructure.TargetModel;
import acp.security.ApplicationPolicy;
import acp.security.PrivacyGuards;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.oauth2.jwt.Jwt;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class PrivacyGuardsTest {
    @Test void auditModesExportAndExactPermissionFailClosed() throws Exception {
        var model=new TargetModel(); var policy=mock(ApplicationPolicy.class);
        var guards=new PrivacyGuards(model,policy,new Expressions(model));
        var field=model.nodes("Field").getFirst(); String id=field.path("id").asText();
        var data=(ObjectNode)field.path("data");
        var classification=(ObjectNode)model.node(data.path("classificationRef").path("id").asText()).path("data");
        for (String mode:new String[]{"NONE","WRITE","READ_WRITE"}) {
            classification.put("audit",mode);
            assertEquals(mode.equals("READ_WRITE"),guards.audit(id,"READ"));
            assertEquals(!mode.equals("NONE"),guards.audit(id,"WRITE"));
        }
        var jwt=Jwt.withTokenValue("test-only").header("alg","none").subject("operator").claim("tenant","one").build();
        var resource=Map.<String,Object>of();
        classification.put("export","DENY");
        assertThrows(AccessDeniedException.class,()->guards.requireExport(id,resource,jwt));
        var permission=model.nodes("Permission").getFirst();
        data.set("owner",permission.path("data").path("resource").deepCopy());
        data.set("exportPermission",com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.objectNode().put("id",permission.path("id").asText()).put("revision",permission.path("revision").asInt()));
        classification.put("export","PERMISSION_REQUIRED");
        doThrow(new AccessDeniedException("denied")).when(policy).requirePermission(permission.path("id").asText(),resource,jwt);
        assertThrows(AccessDeniedException.class,()->guards.requireExport(id,resource,jwt));
        doNothing().when(policy).requirePermission(permission.path("id").asText(),resource,jwt);
        assertDoesNotThrow(()->guards.requireExport(id,resource,jwt));
        verify(policy,times(2)).requirePermission(permission.path("id").asText(),resource,jwt);
    }
    @Test void literalTrueHoldCannotBeBypassedByReleaseAuthorization() throws Exception {
        var model=new TargetModel();var policy=mock(ApplicationPolicy.class);
        when(policy.actor(null)).thenReturn(Map.of());
        var guards=new PrivacyGuards(model,policy,new Expressions(model));
        for (var hold:model.nodes("LegalHold")) {
            String resource=hold.path("data").path("resource").path("id").asText();
            assertThrows(AccessDeniedException.class,()->guards.requireNoHold(resource,Map.of(),null));
            String permission=hold.path("data").path("release").path("id").asText();
            doThrow(new AccessDeniedException("denied")).when(policy).requirePermission(permission,Map.of(),null);
            assertThrows(AccessDeniedException.class,()->guards.requireReleasePermission(hold.path("id").asText(),Map.of(),null));
            doNothing().when(policy).requirePermission(permission,Map.of(),null);
            guards.requireReleasePermission(hold.path("id").asText(),Map.of(),null);
            assertThrows(AccessDeniedException.class,()->guards.requireNoHold(resource,Map.of(),null));
            ((ObjectNode)hold.path("data").path("condition")).put("value",false);
            assertDoesNotThrow(()->guards.requireNoHold(resource,Map.of(),null));
        }
    }
}
