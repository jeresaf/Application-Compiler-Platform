package acp.security;

import acp.domain.Expressions;
import acp.infrastructure.TargetModel;
import java.util.Map;
import java.util.Set;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;

/** Classified application surfaces; infrastructure encryption remains OUTSTANDING. */
@Component
public final class PrivacyGuards {
    private final TargetModel model;
    private final ApplicationPolicy policy;
    private final Expressions expressions;
    public PrivacyGuards(TargetModel model, ApplicationPolicy policy, Expressions expressions) {
        this.model=model; this.policy=policy; this.expressions=expressions;
    }
    public TargetModel model(){return model;}
    /** Non-domain metadata only; typed domain/API/Event values never pass here. */
    public Map<String,Object> observability(Map<String,Object> values) {
        var safe=new java.util.LinkedHashMap<String,Object>();
        for(var entry:values.entrySet()) {
            var field=model.node(entry.getKey());if(!field.path("kind").asText().equals("Field"))throw new IllegalArgumentException("CLASSIFIED_FIELD_REQUIRED");
            var classification=model.node(field.path("data").path("classificationRef").path("id").asText()).path("data");
            switch(classification.path("redaction").asText()) {
                case "MASK" -> safe.put(entry.getKey(),"[REDACTED]");
                case "OMIT" -> {} // No value, hash, length or marker for omitted fields.
                case "NONE" -> safe.put(entry.getKey(),entry.getValue());
                default -> throw new IllegalStateException("REDACTION_REQUIRED");
            }
        }
        return java.util.Collections.unmodifiableMap(safe);
    }
    public boolean audit(String field, String mode) {
        if (!Set.of("READ","WRITE").contains(mode)) throw new IllegalArgumentException("AUDIT_MODE");
        var f=model.node(field).path("data");
        var classification=model.node(f.path("classificationRef").path("id").asText()).path("data");
        String configured=classification.path("audit").asText();
        return configured.equals("READ_WRITE") || (mode.equals("WRITE") && configured.equals("WRITE"));
    }
    public void requireExport(String field, Map<String,Object> resource, Jwt jwt) {
        var f=model.node(field).path("data");
        var classification=model.node(f.path("classificationRef").path("id").asText()).path("data");
        if (!classification.path("export").asText().equals("PERMISSION_REQUIRED") || !f.has("exportPermission"))
            throw new AccessDeniedException("EXPORT_DENIED");
        var permission=model.node(f.path("exportPermission").path("id").asText()).path("data");
        if (!permission.path("resource").equals(f.path("owner"))) throw new AccessDeniedException("EXPORT_PERMISSION_RESOURCE");
        policy.requirePermission(f.path("exportPermission").path("id").asText(),resource,jwt);
    }
    public void requireNoHold(String resourceId, Map<String,Object> resource, Jwt jwt) {
        var actor=policy.actor(jwt);
        for (var hold:model.nodes("LegalHold")) {
            var data=hold.path("data");
            if (data.path("resource").path("id").asText().equals(resourceId) &&
                    Boolean.TRUE.equals(expressions.evaluate(data.path("condition"),resource,actor)))
                throw new AccessDeniedException("LEGAL_HOLD_ACTIVE");
        }
    }
    public void requireReleasePermission(String holdId, Map<String,Object> resource, Jwt jwt) {
        var hold=model.node(holdId);
        if (!hold.path("kind").asText().equals("LegalHold")) throw new AccessDeniedException("HOLD_REQUIRED");
        policy.requirePermission(hold.path("data").path("release").path("id").asText(),resource,jwt);
        // Authorization is not a release. No lifetime/override is invented here.
    }
}
