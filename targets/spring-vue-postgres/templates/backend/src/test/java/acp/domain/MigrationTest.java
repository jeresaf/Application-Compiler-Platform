package acp.domain;

import acp.infrastructure.TargetModel;
import java.sql.DriverManager;
import java.sql.SQLException;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/** Required real database evidence. The test fixture schema is never production. */
class MigrationTest {
    @Test void freshSchemaAndRepeatedFlywayExecution() throws Exception {
        String url = System.getenv("ACP_TEST_DATABASE_URL");
        assertNotNull(url, "ACP_TEST_DATABASE_URL is required; database tests cannot be skipped");
        String user = System.getenv("ACP_TEST_DATABASE_USER");
        String password = System.getenv("ACP_TEST_DATABASE_PASSWORD");
        var flyway = Flyway.configure().dataSource(url, user, password)
            .schemas("acp_phase6_test").defaultSchema("acp_phase6_test").cleanDisabled(false).load();
        try (var connection = DriverManager.getConnection(url, user, password)) {
            try (var version = connection.createStatement().executeQuery("SHOW server_version")) {
                assertTrue(version.next()); assertTrue(version.getString(1).startsWith("18.6"));
            }
        }
        flyway.clean();
        assertEquals(1, flyway.migrate().migrationsExecuted);
        assertEquals(0, flyway.migrate().migrationsExecuted);
        assertTrue(flyway.validateWithResult().validationSuccessful);
        try (var connection = DriverManager.getConnection(url, user, password)) {
            var model = new TargetModel();
            for (var table : model.model.path("tables")) {
                try (var query = connection.prepareStatement("SELECT count(*) FROM information_schema.tables WHERE table_schema=? AND table_name=?")) {
                    query.setString(1, "acp_phase6_test"); query.setString(2, table.path("name").asText());
                    try (var count = query.executeQuery()) { assertTrue(count.next()); assertEquals(1, count.getInt(1)); }
                }
                if (table.path("semantic").path("tenancy").asText().equals("SCOPED")) {
                    try (var query = connection.prepareStatement("SELECT count(*) FROM pg_indexes WHERE schemaname=? AND tablename=?")) {
                        query.setString(1, "acp_phase6_test"); query.setString(2, table.path("name").asText());
                        try (var count = query.executeQuery()) { assertTrue(count.next()); assertTrue(count.getInt(1) >= 3); }
                    }
                }
            }
            try (var check = connection.createStatement().executeQuery("SELECT count(*) FROM information_schema.table_constraints WHERE constraint_schema='acp_phase6_test' AND constraint_type='FOREIGN KEY'")) {
                assertTrue(check.next()); assertTrue(check.getInt(1) > 0);
            }
        }
    }
}
