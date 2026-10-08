package acp.domain;

import acp.infrastructure.*;
import acp.security.*;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.flywaydb.core.Flyway;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.*;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.transaction.support.TransactionTemplate;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class ClassificationAuditTest {
    @Test void classificationAuditIsDurableSelectiveTransactionalAndContainsNoFieldValues() throws Exception {
        String url=System.getenv("ACP_TEST_DATABASE_URL");assertNotNull(url,"Real PostgreSQL required; no skip");
        String user=System.getenv("ACP_TEST_DATABASE_USER"),password=System.getenv("ACP_TEST_DATABASE_PASSWORD");
        var flyway=Flyway.configure().dataSource(url,user,password).schemas("acp_classification_test").defaultSchema("acp_classification_test").cleanDisabled(false).load();
        flyway.clean();flyway.migrate();
        var ds=new DriverManagerDataSource(url+(url.contains("?")?"&":"?")+"currentSchema=acp_classification_test",user,password);
        var jdbc=new JdbcTemplate(ds);var tx=new TransactionTemplate(new DataSourceTransactionManager(ds));
        var model=new TargetModel();var policy=mock(ApplicationPolicy.class);
        var store=new ExecutionStore(jdbc,policy,new PrivacyGuards(model,policy,new Expressions(model)));
        var field=model.nodes("Field").getFirst();String id=field.path("id").asText();
        var classification=(ObjectNode)model.node(field.path("data").path("classificationRef").path("id").asText()).path("data");
        var jwt=Jwt.withTokenValue("test-only").header("alg","none").subject("operator").claim("tenant","one").build();
        for (String audit:new String[]{"NONE","WRITE","READ_WRITE"}) {
            classification.put("audit",audit);jdbc.update("DELETE FROM acp_classification_audit");
            tx.execute(s->{store.classifiedAudit("operation","resource","READ",new String[]{id},jwt);store.classifiedAudit("operation","resource","WRITE",new String[]{id},jwt);return null;});
            assertEquals(audit.equals("NONE")?0:audit.equals("WRITE")?1:2,jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit",Integer.class));
        }
        jdbc.update("DELETE FROM acp_classification_audit");
        assertThrows(IllegalStateException.class,()->tx.execute(s->{store.classifiedAudit("operation","resource","WRITE",new String[]{id},jwt);throw new IllegalStateException("ROLLBACK");}));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit",Integer.class));
        assertThrows(IllegalStateException.class,()->store.classifiedAudit("operation","resource","WRITE",new String[]{id},jwt));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM information_schema.columns WHERE table_schema='acp_classification_test' AND table_name='acp_classification_audit' AND column_name IN ('value','payload','request')",Integer.class));
    }
}
