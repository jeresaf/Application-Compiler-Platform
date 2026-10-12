package acp.generated;
import static acp.generated.Contracts.*;
import static org.junit.jupiter.api.Assertions.*;
import acp.infrastructure.*;
import acp.security.ApplicationPolicy;
import acp.domain.Expressions;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.*;
import org.flywaydb.core.Flyway;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.*;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.security.oauth2.jwt.Jwt;

/** Independent approved reference meanings, exercised against real PostgreSQL. */
class InventorySeedTest {
    JdbcTemplate jdbc; TransactionTemplate tx; TypedTasks tasks; ExecutionStore store;
    ObjectMapper mapper=new ObjectMapper();
    InvocationCore core; Invocations inv;
    TestTime time=new TestTime();
    static final class TestTime implements InvocationCore.Time {
        volatile java.math.BigInteger fixed;
        java.util.Deque<java.math.BigInteger> scripted=new java.util.ArrayDeque<>();
        java.util.List<Long> sleeps=new java.util.ArrayList<>();
        public java.math.BigInteger now() {if(!scripted.isEmpty())return scripted.removeFirst();return fixed==null?new InvocationCore.SystemTime().now():fixed;}
        public void sleep(long seconds) {sleeps.add(seconds);}
    }
    @BeforeEach void setup() throws Exception {
        String url=System.getenv("ACP_TEST_DATABASE_URL"); assertNotNull(url,"Database is required; no skip");
        String user=System.getenv("ACP_TEST_DATABASE_USER"), password=System.getenv("ACP_TEST_DATABASE_PASSWORD");
        var flyway=Flyway.configure().dataSource(url,user,password).schemas("acp_retained_inventory").defaultSchema("acp_retained_inventory").cleanDisabled(false).load();
        flyway.migrate();
        var ds=new DriverManagerDataSource(url+(url.contains("?")?"&":"?")+"currentSchema=acp_retained_inventory",user,password);
        jdbc=new JdbcTemplate(ds); tx=new TransactionTemplate(new DataSourceTransactionManager(ds));
        var model=new TargetModel(); var policy=new ApplicationPolicy(model,new Expressions(model),new acp.security.SessionGate(model,jdbc,new DataSourceTransactionManager(ds)));
        store=new ExecutionStore(jdbc,policy,new acp.security.PrivacyGuards(model,policy,new Expressions(model))); tasks=new TypedTasks(store);core=new InvocationCore(jdbc,model,new DataSourceTransactionManager(ds),time);inv=new Invocations(tasks,store,core);
        tx.execute(s -> { jdbc.execute("INSERT INTO e_0e6739cd5c48f9356c70c968(f_68c58c7f147359be3f4b386a) VALUES('tenant-one'),('tenant-two')"); jdbc.execute("INSERT INTO e_92b7b421992ef490f3b75898(f_8cdd520f7d3d409ff608ae27,f_4880a1ae752d8f5fc59008f6) VALUES('fixture:operator','tenant-one')"); jdbc.execute("INSERT INTO e_d35114736c127b0a4f015cde(f_bf60325b4cdc299c2172f24c,f_883bd4a687ba22abd76d5b51,f_a3c92c5b2195fe53206f71ca,f_be31db7214bd8af99867f486,f_44b27cbadb64ee9d56f21805,f_00dc7107adbf703eb0967a39,present_00dc7107adbf703eb0967a39) VALUES('fixture-resource','tenant-one','old','fixture:operator',decode('7b22464c442d5449544c45223a22417070726f766564207469746c65227d','hex'),'private-note',true)"); return null; });
    }
    Jwt identity(String tenant,String subject) {
        var now=java.time.Instant.now();
        return Jwt.withTokenValue("reference-only").header("alg","none").subject(subject).claim("tenant",tenant)
            .claim("sid","reference-session").claim("amr",java.util.List.of("pwd","otp"))
            .claim("auth_time",now.getEpochSecond()).issuedAt(now).expiresAt(now.plusSeconds(600)).build();
    }
    T_305cfa7a67e100113cf3b5c1 invocation(String text) throws Exception {
        var n=mapper.createObjectNode().put("INPUT-TASK-TEXT",text).put("INPUT-TASK-RESOURCE","fixture-resource");
        return T_305cfa7a67e100113cf3b5c1.read(n);
    }

    void insert(String id) {tx.execute(status -> {jdbc.update("INSERT INTO e_d35114736c127b0a4f015cde(f_be31db7214bd8af99867f486,f_bf60325b4cdc299c2172f24c,f_883bd4a687ba22abd76d5b51,f_44b27cbadb64ee9d56f21805,f_00dc7107adbf703eb0967a39,present_00dc7107adbf703eb0967a39,f_a3c92c5b2195fe53206f71ca) SELECT f_be31db7214bd8af99867f486,?,f_883bd4a687ba22abd76d5b51,f_44b27cbadb64ee9d56f21805,f_00dc7107adbf703eb0967a39,present_00dc7107adbf703eb0967a39,f_a3c92c5b2195fe53206f71ca FROM e_d35114736c127b0a4f015cde WHERE f_bf60325b4cdc299c2172f24c='fixture-resource'",ExecutionStore.bytes(id));return null;});}
    @Test void retainedSyntheticReferencePopulation() throws Exception {
        insert("retained-same-tenant");
        tx.execute(s -> {jdbc.execute("INSERT INTO e_92b7b421992ef490f3b75898(f_8cdd520f7d3d409ff608ae27,f_4880a1ae752d8f5fc59008f6) VALUES('fixture:operator-two','tenant-two')");jdbc.execute("INSERT INTO e_d35114736c127b0a4f015cde(f_bf60325b4cdc299c2172f24c,f_883bd4a687ba22abd76d5b51,f_a3c92c5b2195fe53206f71ca,f_be31db7214bd8af99867f486,f_44b27cbadb64ee9d56f21805,f_00dc7107adbf703eb0967a39,present_00dc7107adbf703eb0967a39) VALUES('retained-tenant-two','tenant-two','old','fixture:operator-two',decode('7b22464c442d5449544c45223a22417070726f766564207469746c65227d','hex'),'private-note',true)");return null;});
        assertThrows(RuntimeException.class,()->inv.v_225e20f12f0b359413f7a725(0,invocation("forbidden"),"cross-tenant",identity("tenant-two","fixture:operator-two")));
        inv.v_225e20f12f0b359413f7a725(0,invocation("inventory completed 🦋"),"inventory-reference-call",identity("tenant-one","fixture:operator"));
        assertEquals(3,jdbc.queryForObject("SELECT count(*) FROM e_d35114736c127b0a4f015cde",Integer.class));
    }
}
