package acp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class Errors {
    public record ErrorResponse(String code) {}
    @ExceptionHandler(IllegalArgumentException.class)
    ResponseEntity<ErrorResponse> invalid(IllegalArgumentException error) {
        return ResponseEntity.unprocessableEntity().body(new ErrorResponse("VALIDATION_FAILED"));
    }
    @ExceptionHandler(IllegalStateException.class)
    ResponseEntity<ErrorResponse> conflict(IllegalStateException error) {
        return ResponseEntity.status(409).body(new ErrorResponse("STATE_CONFLICT"));
    }
    @ExceptionHandler(AccessDeniedException.class)
    ResponseEntity<ErrorResponse> denied(AccessDeniedException error) {
        return ResponseEntity.status(403).body(new ErrorResponse("POLICY_DENIED"));
    }
}
