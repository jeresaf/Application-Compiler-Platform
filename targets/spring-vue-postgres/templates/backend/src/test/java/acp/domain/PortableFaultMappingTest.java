package acp.domain;

import acp.api.FailureMapping;
import java.sql.SQLException;
import java.sql.SQLTimeoutException;
import java.util.concurrent.TimeoutException;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PortableFaultMappingTest {
    static class CustomSql extends SQLException { CustomSql(String state) { super("DEPENDENCY_UNAVAILABLE",state); } }
    static class CustomRuntime extends RuntimeException { CustomRuntime(Throwable cause) { super("TRANSIENT",cause); } }
    @Test void exactClassesStatesAndWrappersDoNotBroadenOrSelectSemanticFailures() {
        for (String state:new String[]{"40001","40P01"}) {
            var result=FailureMapping.map(new SQLException("any text",state));
            assertEquals("SERIALIZATION_CONFLICT",result.faultClass());assertFalse(result.retryable());
        }
        for (String state:new String[]{"08001","08006"}) {
            assertEquals("DEPENDENCY_UNAVAILABLE",FailureMapping.map(new SQLException("any text",state)).faultClass());
        }
        assertEquals("TIMEOUT",FailureMapping.map(new TimeoutException("secret")).faultClass());
        for (Exception error:new Exception[]{new SQLException("DEPENDENCY_UNAVAILABLE","ZZZZZ"),
                new SQLException("DEPENDENCY_UNAVAILABLE","08003"),new RuntimeException("DEPENDENCY_UNAVAILABLE"),
                new CustomSql("08001"),new CustomRuntime(new SQLException("secret","08001")),
                new SQLTimeoutException("secret","08001"),new RuntimeException(new TimeoutException("secret"))}) {
            var result=FailureMapping.map(error);
            assertNull(result.faultClass());assertEquals("INTERNAL",result.category());assertFalse(result.retryable());
        }
        assertEquals("DEPENDENCY_UNAVAILABLE",FailureMapping.map(new RuntimeException(new SQLException("secret","08001"))).faultClass());
        assertEquals("SERIALIZATION_CONFLICT",FailureMapping.map(new SQLException("DEPENDENCY_UNAVAILABLE","40001")).faultClass());
        // The outer recognized SQL condition wins; its cause cannot add another class.
        var outer=new SQLException("secret","40001");outer.initCause(new SQLException("secret","08001"));
        assertEquals("SERIALIZATION_CONFLICT",FailureMapping.map(outer).faultClass());
    }
}
