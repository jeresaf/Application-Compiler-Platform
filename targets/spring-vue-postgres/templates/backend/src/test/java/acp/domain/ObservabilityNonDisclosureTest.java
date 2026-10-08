package acp.domain;

import acp.api.Errors;
import acp.api.FailureMapping;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.SQLException;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import static org.junit.jupiter.api.Assertions.*;

/** Existing value-free diagnostics only; no proposed classification capability. */
class ObservabilityNonDisclosureTest {
    @Test void diagnosticResponsesAndEmittedLogsNeverIncludeExceptionValuesOrTraces() throws Exception {
        String sensitive="SENSITIVE-private-row-8675309", secret="SECRET-token-abcdef";
        var appender=new ListAppender<ILoggingEvent>();appender.start();
        var root=(Logger)LoggerFactory.getLogger(org.slf4j.Logger.ROOT_LOGGER_NAME);
        root.addAppender(appender);
        try {
            var handler=Errors.class.getDeclaredMethod("handle",Exception.class);handler.setAccessible(true);
            for (Exception error:new Exception[]{new RuntimeException(sensitive,new SQLException(secret,"40001")),
                    new IllegalArgumentException(sensitive),new RuntimeException(secret)}) {
                var response=handler.invoke(new Errors(),error);
                String diagnostic=new ObjectMapper().writeValueAsString(response);
                assertFalse(diagnostic.contains(sensitive));assertFalse(diagnostic.contains(secret));
                assertFalse(FailureMapping.map(error).toString().contains(sensitive));
            }
            for (var entry:appender.list) {
                assertFalse(entry.getFormattedMessage().contains(sensitive));
                assertFalse(entry.getFormattedMessage().contains(secret));
                assertNull(entry.getThrowableProxy(),"No exception stack/trace carrying domain values");
            }
        } finally { root.detachAppender(appender);appender.stop(); }
    }
}
