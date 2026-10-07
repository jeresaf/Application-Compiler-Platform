package acp.api;

import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class Errors {
    @ExceptionHandler(IllegalArgumentException.class)
    ResponseEntity<Map<String, String>> invalid(IllegalArgumentException error) {
        return ResponseEntity.unprocessableEntity().body(Map.of("code", "VALIDATION_FAILED"));
    }
    @ExceptionHandler(IllegalStateException.class)
    ResponseEntity<Map<String, String>> conflict(IllegalStateException error) {
        return ResponseEntity.status(409).body(Map.of("code", "STATE_CONFLICT"));
    }
    @ExceptionHandler(AccessDeniedException.class)
    ResponseEntity<Map<String, String>> denied(AccessDeniedException error) {
        return ResponseEntity.status(403).body(Map.of("code", "POLICY_DENIED"));
    }
}
