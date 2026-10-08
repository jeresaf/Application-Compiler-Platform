package acp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class Errors {
    public record ErrorResponse(String code, String category, boolean retryable) {}
    @ExceptionHandler(acp.infrastructure.SemanticFailure.class)
    ResponseEntity<acp.infrastructure.SemanticFailure.Envelope> semantic(acp.infrastructure.SemanticFailure error) {
        int status=switch(error.envelope().category()) {case "BUSINESS" -> 422; case "SECURITY" -> 403; case "TRANSIENT" -> 503;default -> 500;};
        return ResponseEntity.status(status).header("ACP-Failure-Profile","1.0.0").body(error.envelope());
    }
    @ExceptionHandler(acp.infrastructure.InvocationCore.Outcome.class)
    ResponseEntity<ErrorResponse> invocation(acp.infrastructure.InvocationCore.Outcome error) {
        int status=switch(error.getMessage()) {case "IDEMPOTENCY_KEY_REQUIRED" -> 400;case "RATE_DENIED" -> 429;case "IN_PROGRESS" -> 202;case "IDEMPOTENCY_CONFLICT" -> 409;default -> 500;};
        return ResponseEntity.status(status).body(new ErrorResponse(error.getMessage(),"INVOCATION",false));
    }
    @ExceptionHandler(Exception.class)
    ResponseEntity<ErrorResponse> handle(Exception error) {
        var mapped=FailureMapping.map(error);
        // Neither exception messages/causes nor resource values enter responses/logs.
        return ResponseEntity.status(mapped.status()).body(new ErrorResponse(mapped.code(),mapped.category(),mapped.retryable()));
    }
}
