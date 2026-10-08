package acp.security;

import java.util.Map;
/** Versioned target observability port. Never receives arbitrary bodies/errors. */
@org.springframework.stereotype.Component
public final class Observability {
    public static final String CONTRACT_VERSION="1.0.0";
    public enum Surface { LOG, TRACE, DIAGNOSTIC, ERROR, AUDIT }
    public enum Diagnostic { OPERATION_SUCCEEDED, VALIDATION_FAILED, AUTHORIZATION_DENIED, SEMANTIC_FAILURE, LIFECYCLE_HELD, LIFECYCLE_COMPLETED, PROVIDER_FAILED, RETRY_FAILED, DELIVERY_FAILED }
    private final PrivacyGuards privacy;
    public Observability(PrivacyGuards privacy){this.privacy=privacy;}
    public Map<String,Object> metadata(Surface surface,Map<String,Object> classifiedFields){java.util.Objects.requireNonNull(surface);return privacy.observability(classifiedFields);}
    public void emit(Diagnostic diagnostic,Map<String,Object> classifiedFields){
        try{org.slf4j.LoggerFactory.getLogger(Observability.class).info("ACP_DIAGNOSTIC {} {}",diagnostic,new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(metadata(Surface.LOG,classifiedFields)));}
        catch(com.fasterxml.jackson.core.JsonProcessingException invalid){throw new IllegalArgumentException("OBSERVABILITY_VALUE");}
    }
}
