"""Independent approved-domain expectations for generated Java integration tests.

This is a host test harness, never production lowering or a source of effects.
Only the two explicitly approved reference snapshots may use these expectations.
"""
import hashlib
import json
import copy


def symbol(id, prefix):
    return prefix + '_' + hashlib.sha256(id.encode()).hexdigest()[:24]


def seed_sql(domain):
    if domain == 'payment':
        ids = ('ENT-PAYMENT', 'ENT-TENANT', 'ENT-MEMBER', 'FLD-PAYMENT-ID', 'FLD-PAYMENT-TENANT', 'FLD-TENANT-ID', 'FLD-MEMBER-ID', 'FLD-MEMBER-TENANT')
        extra, values = ['FLD-AMOUNT'], ["'12.50'"]
    elif domain == 'case-management':
        ids = ('CASE', 'ORG', 'USER', 'CASE-ID', 'CASE-TENANT', 'ORG-ID', 'USER-ID', 'USER-TENANT')
        extra, values = ['CASE-ASSIGNEE', 'FLD-CASE-TITLE', 'FLD-NOTE'], ["'fixture:operator'", "decode('" + b'{"FLD-TITLE":"Approved title"}'.hex() + "','hex')", "'private-note'"]
    else:
        raise ValueError('NOT_AN_APPROVED_REFERENCE_DOMAIN')
    root, tenant, actor, root_id, root_tenant, tenant_id, actor_id, actor_tenant = ids
    e = lambda id: symbol(id, 'e')
    f = lambda id: symbol(id, 'f')
    statements = [f"INSERT INTO {e(tenant)}({f(tenant_id)}) VALUES('tenant-one'),('tenant-two')",
                  f"INSERT INTO {e(actor)}({f(actor_id)},{f(actor_tenant)}) VALUES('fixture:operator','tenant-one')",
                  f"INSERT INTO {e(root)}(" + ','.join([*(f(c) for c in [root_id, root_tenant, 'FLD-TASK-SUMMARY', *extra]), *([symbol('FLD-NOTE', 'present')] if domain == 'case-management' else [])]) + ") VALUES(" + ','.join(["'fixture-resource'", "'tenant-one'", "'old'", *values, *(['true'] if domain == 'case-management' else [])]) + ')']
    if domain == 'payment':
        statements.append(f"INSERT INTO {symbol('REL-MEMBER-PAYMENT', 'r')}(tenant,source_id,target_id) VALUES('tenant-one','fixture:operator','fixture-resource')")
    return statements


def source(domain):
    if domain not in ('payment', 'case-management'):
        raise ValueError('NOT_AN_APPROVED_REFERENCE_DOMAIN')
    q = lambda x: json.dumps(x)
    typ = lambda x: symbol(x, 'T')
    var = lambda x: symbol(x, 'v')
    table = lambda x: symbol(x, 'e')
    column = lambda x: symbol(x, 'f')
    payment = domain == 'payment'
    root = 'ENT-PAYMENT' if payment else 'CASE'
    tenant = 'ENT-TENANT' if payment else 'ORG'
    actor = 'ENT-MEMBER' if payment else 'USER'
    root_id = 'FLD-PAYMENT-ID' if payment else 'CASE-ID'
    root_tenant = 'FLD-PAYMENT-TENANT' if payment else 'CASE-TENANT'
    tenant_id = 'FLD-TENANT-ID' if payment else 'ORG-ID'
    actor_id = 'FLD-MEMBER-ID' if payment else 'USER-ID'
    actor_tenant = 'FLD-MEMBER-TENANT' if payment else 'USER-TENANT'
    seed = seed_sql(domain)
    checks = (f'assertEquals("12.50",jdbc.queryForObject({q("SELECT " + column("FLD-AMOUNT") + "::text FROM " + table(root))},String.class));'
              if payment else f'''assertEquals("Approved title",jdbc.queryForObject({q("SELECT " + "convert_from(" + column("FLD-CASE-TITLE") + ",'UTF8')::json->>'FLD-TITLE' FROM " + table(root))},String.class));
              assertEquals("private-note",jdbc.queryForObject({q("SELECT " + "convert_from(" + column("FLD-NOTE") + ",'UTF8') FROM " + table(root))},String.class));
              ''' + '\n'.join(f'assertEquals(0,jdbc.queryForObject({q("SELECT count(*) FROM " + table(child))},Integer.class));' for child in ('REVIEW','APPROVAL','ASSIGNMENT','COMMENT','DOCUMENT')))
    events = 1 if payment else 3
    final = 'STATE-RECORDED' if payment else 'STATE-ARCHIVED'
    # Discover actual payment target state's semantic ID from the reviewed source
    # explicitly below; no production behavior is selected by this test helper.
    from execution_fixtures import DEST
    from canonical_json import load
    reviewed = load(DEST / (domain + '-canonical.json'))
    if payment:
        final = next(n['data']['to']['id'] for n in reviewed['content']['nodes'] if n['id'] == 'TRANS-RECORD')
    payload_check = ('assertEquals("12.50",payload.path("FLD-AMOUNT").asText());' if payment else 'assertEquals("Approved title",payload.path("FLD-CASE-TITLE").path("FLD-TITLE").asText());')
    if payment:
        money = next(n['data']['type'] for n in reviewed['content']['nodes'] if n['id'] == 'FLD-AMOUNT')
        money_type = 'D' + hashlib.sha256(json.dumps(money, sort_keys=True).encode()).hexdigest()[:24]
        type_tests = f'''var exact=new {money_type}(new java.math.BigDecimal("12.50"));
        assertEquals("UGX",exact.currency()); assertEquals("\\"12.50\\"",mapper.writeValueAsString(exact));
        assertThrows(ArithmeticException.class, () -> new {money_type}(new java.math.BigDecimal("12.501")));
        assertThrows(IllegalArgumentException.class, () -> new {money_type}(new java.math.BigDecimal("10000000000000000")));
        assertThrows(IllegalArgumentException.class, () -> decimal(mapper.readTree("\\"1e2\\"")));
        assertThrows(IllegalArgumentException.class, () -> decimal(mapper.readTree("\\"01.00\\"")));'''
    else:
        typeref = typ('TYPE-CASE-CODE')
        note = var('FLD-NOTE')
        type_tests = f'''assertEquals("x",{typeref}.read(mapper.readTree("\\"x\\"")).value());
        assertThrows(IllegalArgumentException.class, () -> new {typeref}(""));
        assertThrows(IllegalArgumentException.class, () -> new {typeref}("x".repeat(41)));
        var row=mapper.createObjectNode().put("CASE-ID","fixture-resource").put("CASE-TENANT","tenant-one").put("CASE-ASSIGNEE","fixture:operator").put("FLD-TASK-SUMMARY","old");
        row.set("FLD-CASE-TITLE",mapper.createObjectNode().put("FLD-TITLE","Approved title"));
        var absent={typ(root)}.read(row); assertFalse(absent.{note}().present());
        assertFalse(mapper.readTree(mapper.writeValueAsString(absent)).has("FLD-NOTE"));
        row.putNull("FLD-NOTE"); var explicitNull={typ(root)}.read(row);
        assertTrue(explicitNull.{note}().present()); assertNull(explicitNull.{note}().value());
        assertTrue(mapper.readTree(mapper.writeValueAsString(explicitNull)).has("FLD-NOTE"));'''
    call = f'tasks.{var("UC-TASK")}(0, invocation("new 🦋"), identity("tenant-one", "fixture:operator"))'
    last_event = 'EVT-RECORDED' if payment else 'EVT-ARCHIVE'
    state_tests = f'''
    @Test void preStateReadsAndPostStateReadsRemainDistinct() throws Exception {{
        var input=invocation("new");
        var before=new PreReadsTasks(store);
        var result=tx.execute(s -> before.{var('UC-TASK')}(0,input,identity("tenant-one","fixture:operator")));
        assertEquals("old",result.output().{var('OUTPUT-TASK-TEXT')}());
    }}
    @Test void postStateReadsObserveEarlierOrderedAssignments() throws Exception {{
        var input=invocation("new"); var after=new PostReadsTasks(store);
        var result=tx.execute(s -> after.{var('UC-TASK')}(0,input,identity("tenant-one","fixture:operator")));
        assertEquals("new",result.output().{var('OUTPUT-TASK-TEXT')}());
    }}
    @Test void invariantsObserveAllStagedAssignmentsBeforeDatabaseWrites() throws Exception {{
        var input=invocation("new"); var invalid=new InvalidStagedTasks(store);
        var error=assertThrows(IllegalArgumentException.class, () -> tx.execute(s -> invalid.{var('UC-TASK')}(0,input,identity("tenant-one","fixture:operator"))));
        assertEquals("INVARIANT",error.getMessage());
        assertEquals("old",jdbc.queryForObject({q("SELECT convert_from(" + column('FLD-TASK-SUMMARY') + ", 'UTF8') FROM " + table(root))},String.class));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}''' if payment else f'''
    @Test void aTransactionCannotSwitchAggregateRootInstances() throws Exception {{
        var input=invocation("new"); var switched=new RootSwitchTasks(store);
        var error=assertThrows(IllegalArgumentException.class, () -> tx.execute(s -> switched.{var('UC-TASK')}(0,input,identity("tenant-one","fixture:operator"))));
        assertEquals("TRANSACTION_RESOURCE",error.getMessage());
        assertEquals("old",jdbc.queryForObject({q("SELECT convert_from(" + column('FLD-TASK-SUMMARY') + ", 'UTF8') FROM " + table(root))},String.class));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
    @Test void workflowGuardUsesPreCommandState() throws Exception {{
        var input=invocation("new"); var guarded=new PreGuardTasks(store);
        var result=tx.execute(s -> guarded.{var('UC-TASK')}(0,input,identity("tenant-one","fixture:operator")));
        assertEquals("new",result.output().{var('OUTPUT-TASK-TEXT')}());
        assertEquals("STATE-ARCHIVED",result.state());
    }}'''
    if payment:
        child_table, child_id = table(root), column(root_id)
        child_insert = seed_sql(domain)[2].replace("'fixture-resource'", "'related-child'")
        parent_insert = f"INSERT INTO {table(actor)}({column(actor_id)},{column(actor_tenant)}) VALUES('another-parent','tenant-one')"
        parent_key, parent_table, parent_id = 'fixture:operator', table(actor), column(actor_id)
        relation = symbol('REL-MEMBER-PAYMENT', 'r')
    else:
        child_table, child_id = table('APPROVAL'), column('APPROVAL-ID')
        child_insert = f"INSERT INTO {child_table}({child_id},{column('APPROVAL-TENANT')},{column('APPROVAL-reason')}) VALUES('related-child','tenant-one','reference reason')"
        parent_insert = seed_sql(domain)[2].replace("'fixture-resource'", "'another-parent'")
        parent_key, parent_table, parent_id = 'fixture-resource', table(root), column(root_id)
        relation = symbol('REL-CASE-APPROVAL', 'r')
    edge = f"INSERT INTO {relation}(tenant,source_id,target_id) VALUES('tenant-one','{parent_key}','related-child')"
    relation_tests = f'''
    @Test void requiredRelationCannotBeOmittedButMayBeConstructedInOneTransaction() {{
        assertThrows(RuntimeException.class, () -> tx.execute(s -> {{ jdbc.execute({q(child_insert)}); return null; }}));
        assertEquals(0,jdbc.queryForObject({q("SELECT count(*) FROM " + child_table + " WHERE " + child_id + "='related-child'")},Integer.class));
        tx.execute(s -> {{ jdbc.execute({q(child_insert)}); jdbc.execute({q(edge)}); return null; }});
        assertEquals(1,jdbc.queryForObject({q("SELECT count(*) FROM " + child_table + " WHERE " + child_id + "='related-child'")},Integer.class));
    }}
    @Test void maximumCardinalityAndSameTenantReferencesAreDatabaseEnforced() {{
        tx.execute(s -> {{ jdbc.execute({q(child_insert)}); jdbc.execute({q(edge)}); return null; }});
        jdbc.execute({q(parent_insert)});
        assertThrows(RuntimeException.class, () -> tx.execute(s -> {{ jdbc.execute({q(edge.replace("'" + parent_key + "'", "'another-parent'"))}); return null; }}));
        assertThrows(RuntimeException.class, () -> jdbc.execute({q("UPDATE " + relation + " SET tenant='tenant-two' WHERE target_id='related-child'")}));
        assertThrows(RuntimeException.class, () -> jdbc.execute({q("DELETE FROM " + parent_table + " WHERE " + parent_id + "='" + parent_key + "'")}));
    }}
'''
    return f'''package acp.generated;
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
class ExplicitExecutionTest {{
    JdbcTemplate jdbc; TransactionTemplate tx; TypedTasks tasks; ExecutionStore store;
    ObjectMapper mapper=new ObjectMapper();
    @BeforeEach void setup() throws Exception {{
        String url=System.getenv("ACP_TEST_DATABASE_URL"); assertNotNull(url,"Database is required; no skip");
        String user=System.getenv("ACP_TEST_DATABASE_USER"), password=System.getenv("ACP_TEST_DATABASE_PASSWORD");
        var flyway=Flyway.configure().dataSource(url,user,password).schemas("acp_phase6_execution_test").defaultSchema("acp_phase6_execution_test").cleanDisabled(false).load();
        flyway.clean(); flyway.migrate();
        var ds=new DriverManagerDataSource(url+(url.contains("?")?"&":"?")+"currentSchema=acp_phase6_execution_test",user,password);
        jdbc=new JdbcTemplate(ds); tx=new TransactionTemplate(new DataSourceTransactionManager(ds));
        var model=new TargetModel(); var policy=new ApplicationPolicy(model,new Expressions(model),new acp.security.SessionGate(model,jdbc,new DataSourceTransactionManager(ds)));
        store=new ExecutionStore(jdbc,policy,new acp.security.PrivacyGuards(model,policy,new Expressions(model))); tasks=new TypedTasks(store);
        tx.execute(s -> {{ {' '.join('jdbc.execute(' + q(sql) + ');' for sql in seed)} return null; }});
    }}
    Jwt identity(String tenant,String subject) {{
        var now=java.time.Instant.now();
        return Jwt.withTokenValue("reference-only").header("alg","none").subject(subject).claim("tenant",tenant)
            .claim("sid","reference-session").claim("amr",java.util.List.of("pwd","otp"))
            .claim("auth_time",now.getEpochSecond()).issuedAt(now).expiresAt(now.plusSeconds(600)).build();
    }}
    {typ('INPUT-TASK')} invocation(String text) throws Exception {{
        var n=mapper.createObjectNode().put("INPUT-TASK-TEXT",text).put("INPUT-TASK-RESOURCE","fixture-resource");
        return {typ('INPUT-TASK')}.read(n);
    }}
    @Test void exactEffectsResultsEventsAndUnchangedFields() throws Exception {{
        var output=tx.execute(status -> {{ try {{ return {call}; }} catch(Exception e) {{ throw new RuntimeException(e); }} }});
        assertEquals("new 🦋",output.output().{var('OUTPUT-TASK-TEXT')}());
        assertTrue(jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit WHERE mode='WRITE'",Integer.class)>0);
        assertTrue(jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit WHERE mode='READ'",Integer.class)>0);
        assertEquals("fixture-resource",output.resourceId()); assertEquals({events},output.version());
        assertEquals({q(final)},output.state());
        assertEquals("new 🦋",jdbc.queryForObject({q("SELECT convert_from(" + column('FLD-TASK-SUMMARY') + ", 'UTF8') FROM " + table(root))},String.class));
        assertEquals("fixture-resource",jdbc.queryForObject({q("SELECT convert_from(" + column(root_id) + ", 'UTF8') FROM " + table(root))},String.class));
        assertEquals("tenant-one",jdbc.queryForObject({q("SELECT convert_from(" + column(root_tenant) + ", 'UTF8') FROM " + table(root))},String.class));
        {checks}
        assertEquals({events},jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
        for(var raw:jdbc.queryForList("SELECT convert_from(payload,'UTF8') FROM acp_outbox ORDER BY aggregate_version",String.class)) {{ var payload=mapper.readTree(raw); {payload_check} }}
    }}
    @Test void nulAndEmptyStringsRoundTripWithoutNarrowingSemanticStrings() throws Exception {{
        String text="a"+(char)0+"🦋";
        var input=invocation(text);
        var output=tx.execute(s -> tasks.{var('UC-TASK')}(0,input,identity("tenant-one","fixture:operator")));
        assertEquals(text,output.output().{var('OUTPUT-TASK-TEXT')}());
        assertEquals(text,ExecutionStore.text(jdbc.queryForObject({q('SELECT ' + column('FLD-TASK-SUMMARY') + ' FROM ' + table(root))},byte[].class)));
        var filter={typ('QUERY-INPUT')}.read(mapper.createObjectNode().put("QUERY-TEXT",String.valueOf((char)0)));
        assertEquals(1,tx.execute(s -> tasks.{var('QUERY-TASKS')}(filter,0,1,identity("tenant-one","fixture:operator"))).size());
        assertEquals("",invocation("").{var('INPUT-TASK-TEXT')}());
        assertThrows(IllegalArgumentException.class, () -> new {typ(root)}Id(String.valueOf((char)0x85)));
        assertThrows(IllegalArgumentException.class, () -> new {typ(root)}Id(String.valueOf((char)0xa0)));
    }}
    @Test void invalidTypedInputsFailBeforeEffects() throws Exception {{
        assertThrows(IllegalArgumentException.class, () -> {typ('INPUT-TASK')}.read(mapper.readTree("{{}}")));
        assertThrows(IllegalArgumentException.class, () -> {typ('INPUT-TASK')}.read(mapper.readTree("{{\\"INPUT-TASK-TEXT\\":null,\\"INPUT-TASK-RESOURCE\\":\\"fixture-resource\\"}}")));
        assertThrows(IllegalArgumentException.class, () -> {typ('INPUT-TASK')}.read(mapper.readTree("{{\\"INPUT-TASK-TEXT\\":4,\\"INPUT-TASK-RESOURCE\\":\\"fixture-resource\\"}}")));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_audit",Integer.class));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit",Integer.class));
    }}
    @Test void exactTypedContractsAndStrictHttpCodec() throws Exception {{
        {type_tests}
        var strict=acp.api.TypedJsonConfiguration.mapper();
        var parsed=strict.readValue("{{\\"INPUT-TASK-TEXT\\":\\"new\\",\\"INPUT-TASK-RESOURCE\\":\\"fixture-resource\\"}}",{typ('INPUT-TASK')}.class);
        assertEquals("new",parsed.{var('INPUT-TASK-TEXT')}());
        assertThrows(Exception.class, () -> strict.readValue("{{\\"INPUT-TASK-TEXT\\":\\"a\\",\\"INPUT-TASK-TEXT\\":\\"b\\",\\"INPUT-TASK-RESOURCE\\":\\"fixture-resource\\"}}",{typ('INPUT-TASK')}.class));
        assertThrows(Exception.class, () -> strict.readValue("{{\\"INPUT-TASK-TEXT\\":\\"a\\",\\"INPUT-TASK-RESOURCE\\":\\"fixture-resource\\",\\"unknown\\":true}}",{typ('INPUT-TASK')}.class));
    }}
    @Test void crossTenantUnknownResourceAndUnauthorizedActorFail() throws Exception {{
        var input=invocation("new");
        assertThrows(RuntimeException.class, () -> tx.execute(s -> tasks.{var('UC-TASK')}(0,input,identity("tenant-two","fixture:operator"))));
        assertThrows(RuntimeException.class, () -> tx.execute(s -> tasks.{var('UC-TASK')}(0,input,identity("tenant-one","unassigned"))));
        var unknown={typ('INPUT-TASK')}.read(mapper.createObjectNode().put("INPUT-TASK-TEXT","new").put("INPUT-TASK-RESOURCE","missing"));
        assertThrows(RuntimeException.class, () -> tx.execute(s -> tasks.{var('UC-TASK')}(0,unknown,identity("tenant-one","fixture:operator"))));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
    @Test void failedEventPersistenceRollsBackAllEffectsAndTransitions() throws Exception {{
        jdbc.execute("CREATE FUNCTION fail_reference_event() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'injected-failure'; END $$");
        jdbc.execute("CREATE TRIGGER fail_reference_event BEFORE INSERT ON acp_outbox FOR EACH ROW WHEN (NEW.event='{last_event}') EXECUTE FUNCTION fail_reference_event()");
        var input=invocation("new");
        assertThrows(RuntimeException.class, () -> tx.execute(s -> tasks.{var('UC-TASK')}(0,input,identity("tenant-one","fixture:operator"))));
        assertEquals("old",jdbc.queryForObject({q("SELECT convert_from(" + column('FLD-TASK-SUMMARY') + ", 'UTF8') FROM " + table(root))},String.class));
        assertEquals(0,jdbc.queryForObject({q('SELECT acp_version FROM ' + table(root))},Long.class));
        assertNull(jdbc.queryForObject({q('SELECT acp_state FROM ' + table(root))},String.class));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_audit",Integer.class));
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
    @Test void databasePredicateIsCaseSensitiveUnicodeAndBeforePagination() throws Exception {{
        tx.execute(s -> {{jdbc.update({q('UPDATE ' + table(root) + ' SET ' + column('FLD-TASK-SUMMARY') + '=?')},acp.infrastructure.ExecutionStore.bytes("A🦋é")); return null; }});
        var yes={typ('QUERY-INPUT')}.read(mapper.createObjectNode().put("QUERY-TEXT","🦋"));
        var no={typ('QUERY-INPUT')}.read(mapper.createObjectNode().put("QUERY-TEXT","a"));
        var composed={typ('QUERY-INPUT')}.read(mapper.createObjectNode().put("QUERY-TEXT","é"));
        assertEquals(1,tx.execute(s -> tasks.{var('QUERY-TASKS')}(yes,0,1,identity("tenant-one","fixture:operator"))).size());
        assertEquals(0,tx.execute(s -> tasks.{var('QUERY-TASKS')}(no,0,1,identity("tenant-one","fixture:operator"))).size());
        assertEquals(0,tx.execute(s -> tasks.{var('QUERY-TASKS')}(composed,0,1,identity("tenant-one","fixture:operator"))).size());
        assertEquals(0,tx.execute(s -> tasks.{var('QUERY-TASKS')}(yes,0,1,identity("tenant-two","fixture:operator"))).size());
    }}
    {state_tests}
    {relation_tests}
}}
'''


def variants(domain):
    """Adversarial test-only semantics; never admitted as approved applications."""
    from canonical_json import load
    from execution_fixtures import DEST
    from execution_codegen import ExecutionGenerator
    base = load(DEST / (domain + '-canonical.json'))['content']['nodes']
    generated = {}
    changes = ('PreReadsTasks', 'PostReadsTasks', 'InvalidStagedTasks') if domain == 'payment' else ('RootSwitchTasks', 'PreGuardTasks')
    for cls in changes:
        nodes = copy.deepcopy(base); by = {n['id']: n for n in nodes}
        r = lambda id: {'id': id, 'revision': by[id]['revision']}
        if cls in ('PreReadsTasks', 'PostReadsTasks'):
            d = by['CMD-RECORD']['data']
            effect = copy.deepcopy(d['assignments'][0])
            effect['value'] = ({'tag': 'field', 'binding': 'resource', 'ref': r('FLD-TASK-SUMMARY')} if cls == 'PreReadsTasks'
                               else {'tag': 'postField', 'field': r('FLD-TASK-SUMMARY')})
            d['assignments'].append(effect)
        elif cls == 'InvalidStagedTasks':
            d = by['CMD-RECORD']['data']; d['writeFields'].append(r('FLD-AMOUNT'))
            d['assignments'].append({'resource': d['resource'], 'field': r('FLD-AMOUNT'),
                'value': {'tag': 'literal', 'type': by['FLD-AMOUNT']['data']['type'], 'value': '-1.00'}})
        elif cls == 'RootSwitchTasks':
            by['STEP-CMD-APPROVE']['data']['resource'] = {'tag': 'literal', 'type': {'kind': 'Identifier', 'entity': r('CASE')}, 'value': 'different-instance'}
        else:
            transition = next(n for n in nodes if n['kind'] == 'Transition' and n['data']['command']['id'] == 'CMD-REVIEW')
            transition['data']['guard'] = {'tag': 'binary', 'op': 'and', 'left': transition['data']['guard'],
                'right': {'tag': 'binary', 'op': 'eq', 'left': {'tag': 'field', 'binding': 'resource', 'ref': r('FLD-TASK-SUMMARY')},
                          'right': {'tag': 'literal', 'type': {'kind': 'String'}, 'value': 'old'}}}
        code = ExecutionGenerator(nodes).source()['backend/src/main/java/acp/generated/TypedTasks.java']
        code = code.replace('public class TypedTasks', 'public class ' + cls).replace('public TypedTasks(', 'public ' + cls + '(')
        # No component annotation: these intentionally altered test programs must
        # never replace the approved application's service in a Spring context.
        code = code.replace('@org.springframework.stereotype.Service\n', '')
        generated['backend/src/test/java/acp/generated/' + cls + '.java'] = code
    return generated


def http_source(domain):
    q = json.dumps
    path = '/api/' + symbol('UC-TASK', 'op')
    query = '/api/' + symbol('QUERY-TASKS', 'op')
    return f'''package acp.generated;
import static org.junit.jupiter.api.Assertions.*;
import java.net.URI;
import java.net.http.*;
import java.time.Instant;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.context.annotation.Bean;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.oauth2.jwt.*;
import org.springframework.test.context.*;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;
import org.flywaydb.core.Flyway;

/** Real Spring HTTP binding/commit barrier. Decoder is an explicit test-authority port. */
@SpringBootTest(classes={{acp.Application.class,TypedHttpTest.Identity.class}},webEnvironment=SpringBootTest.WebEnvironment.RANDOM_PORT,
    properties={{"spring.security.oauth2.resourceserver.jwt.issuer-uri=https://reference.invalid", "spring.security.oauth2.resourceserver.jwt.audiences=reference-test"}})
class TypedHttpTest {{
    @LocalServerPort int port;
    @Autowired JdbcTemplate jdbc;
    @Autowired PlatformTransactionManager manager;
    @DynamicPropertySource static void database(DynamicPropertyRegistry r) {{
        String url=System.getenv("ACP_TEST_DATABASE_URL"); assertNotNull(url,"Database required; no skip");
        // Explicitly ephemeral test schema, cleaned before Boot validates it.
        Flyway.configure().dataSource(url,System.getenv("ACP_TEST_DATABASE_USER"),System.getenv("ACP_TEST_DATABASE_PASSWORD"))
            .schemas("acp_phase6_http_test").defaultSchema("acp_phase6_http_test").cleanDisabled(false).load().clean();
        r.add("spring.datasource.url", () -> url+(url.contains("?")?"&":"?")+"currentSchema=acp_phase6_http_test");
        r.add("spring.datasource.username", () -> System.getenv("ACP_TEST_DATABASE_USER"));
        r.add("spring.datasource.password", () -> System.getenv("ACP_TEST_DATABASE_PASSWORD"));
        r.add("spring.flyway.schemas", () -> "acp_phase6_http_test");
        r.add("spring.flyway.default-schema", () -> "acp_phase6_http_test");
    }}
    @TestConfiguration static class Identity {{
        @Bean JwtDecoder referenceOnlyDecoder() {{ return token -> {{
            if (!token.equals("reference-only-token")) throw new JwtException("NOT_REFERENCE_AUTHORITY");
            var now=Instant.now();
            return Jwt.withTokenValue(token).header("alg","reference-test-only").subject("fixture:operator")
                .claim("tenant","tenant-one").claim("sid","http-reference-session").claim("amr",java.util.List.of("pwd","otp"))
                .claim("auth_time",now.getEpochSecond()).issuedAt(now).expiresAt(now.plusSeconds(600)).build();
        }}; }}
    }}
    @BeforeEach void seed() {{
        String url=System.getenv("ACP_TEST_DATABASE_URL");
        var flyway=Flyway.configure().dataSource(url,System.getenv("ACP_TEST_DATABASE_USER"),System.getenv("ACP_TEST_DATABASE_PASSWORD"))
            .schemas("acp_phase6_http_test").defaultSchema("acp_phase6_http_test").cleanDisabled(false).load();
        flyway.clean(); flyway.migrate();
        new TransactionTemplate(manager).execute(s -> {{ {' '.join('jdbc.execute(' + q(sql) + ');' for sql in seed_sql(domain))} return null; }});
    }}
    HttpResponse<String> send(String path,String body,boolean authenticated) throws Exception {{
        var builder=HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+path));
        if (authenticated) builder.header("Authorization","Bearer reference-only-token");
        if (body==null) builder.GET(); else builder.header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(body));
        return HttpClient.newHttpClient().send(builder.build(),HttpResponse.BodyHandlers.ofString());
    }}
    @Test void typedInputBindingAndOutputSerializationUseTheActualMvcCodec() throws Exception {{
        String input="{{\\"expectedVersion\\":0,\\"input\\":{{\\"INPUT-TASK-TEXT\\":\\"new\\",\\"INPUT-TASK-RESOURCE\\":\\"fixture-resource\\"}}}}";
        var response=send({q(path)},input,true); assertEquals(200,response.statusCode(),response.body());
        var output=new com.fasterxml.jackson.databind.ObjectMapper().readTree(response.body());
        assertEquals("new",output.path("output").path("OUTPUT-TASK-TEXT").asText());
        assertEquals("fixture-resource",output.path("resourceId").asText());
        assertTrue(jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class)>0);
    }}
    @Test void missingInputAndDuplicateMembersFailBeforeSemanticWrites() throws Exception {{
        assertTrue(send({q(path)},"{{\\"expectedVersion\\":0,\\"input\\":{{}}}}",true).statusCode()>=400);
        assertTrue(send({q(path)},"{{\\"expectedVersion\\":0,\\"expectedVersion\\":1,\\"input\\":{{}}}}",true).statusCode()>=400);
        assertEquals(0,jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class));
    }}
    @Test void unauthenticatedRequestsAreDeniedAndFilterUsesExplicitQueryMember() throws Exception {{
        assertEquals(401,send({q(query)},"{{\\"QUERY-TEXT\\":\\"old\\"}}",false).statusCode());
        var response=send({q(query)},"{{\\"QUERY-TEXT\\":\\"old\\"}}",true); assertEquals(200,response.statusCode(),response.body());
        assertEquals(1,new com.fasterxml.jackson.databind.ObjectMapper().readTree(response.body()).size());
    }}
}}
'''.replace('acp_phase6_http_test', 'acp_phase6_http_' + domain.replace('-', '_'))
