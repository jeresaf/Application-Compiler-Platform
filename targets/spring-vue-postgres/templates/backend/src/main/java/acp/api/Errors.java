package acp.api;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class Errors {
    public record ErrorResponse(String code, String category, boolean retryable) {}
    @ExceptionHandler(Exception.class)
    ResponseEntity<ErrorResponse> handle(Exception error) {
        var mapped=FailureMapping.map(error);
        // Neither exception messages/causes nor resource values enter responses/logs.
        return ResponseEntity.status(mapped.status()).body(new ErrorResponse(mapped.code(),mapped.category(),mapped.retryable()));
    }
}
