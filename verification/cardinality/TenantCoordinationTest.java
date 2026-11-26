package acp.infrastructure;

import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.TransactionTemplate;

/** Run only against an owned disposable PostgreSQL database. */
public final class TenantCoordinationTest {
    private static void check(boolean condition) {
        if (!condition) throw new AssertionError("CARDINALITY_COORDINATION_CHECK");
    }

    private static void reject(String expected, Runnable action) {
        try {
            action.run();
            throw new AssertionError("COORDINATION_ACCEPTED_INVALID_BOUNDARY");
        } catch (IllegalStateException error) {
            check(expected.equals(error.getMessage()));
        }
    }

    public static void main(String[] args) throws Exception {
        var ds = new DriverManagerDataSource(System.getenv("ACP_TEST_DATABASE_URL"),
                System.getenv("ACP_TEST_DATABASE_USER"), System.getenv("ACP_TEST_DATABASE_PASSWORD"));
        var jdbc = new JdbcTemplate(ds);
        var manager = new DataSourceTransactionManager(ds);
        var tx = new TransactionTemplate(manager);
        var coordination = new TenantCoordination(jdbc, "application-a");
        reject("CARDINALITY_WRITE_TRANSACTION_REQUIRED", () -> coordination.acquire("tenant-a"));

        var repeatableRead = new TransactionTemplate(manager);
        repeatableRead.setIsolationLevel(TransactionDefinition.ISOLATION_REPEATABLE_READ);
        repeatableRead.executeWithoutResult(status ->
                reject("CARDINALITY_READ_COMMITTED_REQUIRED", () -> coordination.acquire("tenant-a")));

        try (var executor = Executors.newSingleThreadExecutor()) {
            for (boolean rollback : new boolean[] {false, true}) {
                int[] key = tx.execute(status -> {
                    coordination.acquire("tenant-a");
                    var parts = jdbc.queryForObject("""
                            SELECT classid::text, objid::text FROM pg_locks
                            WHERE pid = pg_backend_pid() AND locktype = 'advisory'
                              AND objsubid = 2 AND granted
                            """, (row, index) -> new int[]{
                                    (int) Long.parseLong(row.getString(1)),
                                    (int) Long.parseLong(row.getString(2))});
                    try {
                        check(executor.submit(() -> tx.execute(other -> {
                            jdbc.execute("SET LOCAL statement_timeout = '2s'");
                            check(Boolean.FALSE.equals(jdbc.queryForObject(
                                    "SELECT pg_try_advisory_xact_lock(?, ?)", Boolean.class,
                                    parts[0], parts[1])));
                            coordination.acquire("tenant-b");
                            new TenantCoordination(jdbc, "application-b").acquire("tenant-a");
                            return true;
                        })).get(5, TimeUnit.SECONDS));
                    } catch (Exception error) {
                        throw new AssertionError("COORDINATION_PEER", error);
                    }
                    if (rollback) status.setRollbackOnly();
                    return parts;
                });
                check(Boolean.TRUE.equals(jdbc.queryForObject(
                        "SELECT pg_try_advisory_xact_lock(?, ?)", Boolean.class, key[0], key[1])));
            }
        }
        System.out.println("PASS: transaction boundary, isolation, contention, tenant/application isolation, commit/rollback release");
    }
}
