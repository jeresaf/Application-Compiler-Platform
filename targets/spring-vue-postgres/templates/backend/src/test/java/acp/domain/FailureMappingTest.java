package acp.domain;

import acp.api.FailureMapping;
import java.sql.SQLException;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class FailureMappingTest {
    @Test void exactSqlStatesAndUnknownExceptionsNeverBecomeBusinessFailures() {
        for (String state:new String[]{"40001","40P01"}) {
            var mapped=FailureMapping.map(new RuntimeException("secret value",new SQLException("raw row secret",state)));
            assertEquals("TRANSIENT",mapped.category());assertEquals(503,mapped.status());assertFalse(mapped.retryable());
        }
        for (String state:new String[]{"23503","23505","23514"}) {
            var mapped=FailureMapping.map(new SQLException("secret",state));
            assertEquals("PERSISTENCE_CONFLICT",mapped.code());assertEquals("INTERNAL",mapped.category());assertFalse(mapped.retryable());
        }
        for (Exception error:new Exception[]{new SQLException("INVALID_STATE","ZZZZZ"),new RuntimeException("BUSINESS:INVALID_STATE"),new RuntimeException(new IllegalArgumentException("secret"))}) {
            var mapped=FailureMapping.map(error);
            assertEquals("INTERNAL_ERROR",mapped.code());assertEquals(500,mapped.status());assertFalse(mapped.retryable());
            assertFalse(mapped.toString().contains("secret"));
        }
        assertEquals("SECURITY",FailureMapping.map(new org.springframework.security.access.AccessDeniedException("secret")).category());
    }
}
