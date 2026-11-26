package acp.infrastructure;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Objects;
import javax.sql.DataSource;
import java.sql.SQLException;
import org.springframework.jdbc.UncategorizedSQLException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceUtils;
import org.springframework.transaction.support.TransactionSynchronizationManager;

/**
 * Successor coordination for an already authorized tenant. Call before any
 * endpoint row lock, using the data source bound to the business transaction.
 */
public final class TenantCoordination {
    private final DataSource dataSource;
    private final String application;

    public TenantCoordination(JdbcTemplate jdbc, String application) {
        this.dataSource = Objects.requireNonNull(jdbc.getDataSource());
        this.application = identity(application);
    }

    public void acquire(String authorizedTenant) {
        long key = lockKey(application, identity(authorizedTenant));
        if (!TransactionSynchronizationManager.isActualTransactionActive()
                || TransactionSynchronizationManager.isCurrentTransactionReadOnly()) {
            throw new IllegalStateException("CARDINALITY_WRITE_TRANSACTION_REQUIRED");
        }
        var connection = DataSourceUtils.getConnection(dataSource);
        try {
            if (!DataSourceUtils.isConnectionTransactional(connection, dataSource)
                    || connection.getAutoCommit()) {
                throw new IllegalStateException("CARDINALITY_TRANSACTION_CONNECTION_REQUIRED");
            }
            try (var statement = connection.createStatement();
                 var result = statement.executeQuery("SHOW transaction_isolation")) {
                if (!result.next() || !"read committed".equals(result.getString(1))) {
                    throw new IllegalStateException("CARDINALITY_READ_COMMITTED_REQUIRED");
                }
            }
            // The two-integer key space is separate from the existing bigint
            // advisory locks. Collisions serialize extra work, never authorize it.
            try (var statement = connection.prepareStatement(
                    "SELECT pg_advisory_xact_lock(?, ?)")) {
                statement.setInt(1, (int) (key >>> 32));
                statement.setInt(2, (int) key);
                statement.execute();
            }
        } catch (SQLException error) {
            throw new UncategorizedSQLException("Acquire tenant coordination", null, error);
        } finally {
            DataSourceUtils.releaseConnection(connection, dataSource);
        }
    }

    private static String identity(String value) {
        if (value == null || value.isEmpty() || !StandardCharsets.UTF_8.newEncoder().canEncode(value)) {
            throw new IllegalArgumentException("CARDINALITY_IDENTITY");
        }
        return value;
    }

    private static long lockKey(String application, String tenant) {
        try {
            var digest = MessageDigest.getInstance("SHA-256");
            digest.update("ACP\0CARDINALITY-TENANT/1\0".getBytes(StandardCharsets.UTF_8));
            for (var value : new String[] {application, tenant}) {
                byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                digest.update(ByteBuffer.allocate(Integer.BYTES).putInt(bytes.length).array());
                digest.update(bytes);
            }
            return ByteBuffer.wrap(digest.digest()).getLong();
        } catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException("CARDINALITY_DIGEST_UNAVAILABLE", error);
        }
    }
}
