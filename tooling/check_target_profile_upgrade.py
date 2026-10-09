"""Generate the actual accepted 0.1 application, execute it, then upgrade in place.

No clean occurs between the old application's commit and the new migration/check.
Both generated provenance maps are preserved as upgrade evidence.
"""
from target_provenance import read_provenance
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
CHECKPOINT='bba16c9e64bd0a16e60343d4aaf11060f209e931'
OLD_BUNDLE='20ab8a9e2554bed8c17a163eb69ab8a37099a014a5cc4c4803c49afd3e2fd6dd'


def after_source(domain):
    from delivery_job_reference_tests import source
    from invocation_reference_tests import source as prior
    from phase6_reference_tests import symbol
    q=json.dumps
    s=source(domain);s=s[:s.index('    @Test void pinnedRules')].replace('class DeliveryJobTest','class UpgradeAfterTest').replace('@BeforeEach void setup()','void unusedFreshSetup()')
    p=prior(domain);start=p.index('    void insert(String id)');s+=p[start:p.index('    @Test void unicodeOrder',start)]
    root='ENT-PAYMENT' if domain=='payment' else 'CASE'
    fields='java.util.List.of('+','.join(q(symbol(x,'e')) for x in (('ENT-PAYMENT','ENT-TENANT','ENT-MEMBER') if domain=='payment' else ('CASE','ORG','USER')))+')'
    return s+f'''
    java.util.List<String> rows(String table,java.util.List<String> columns) {{String projection=columns.stream().map(c->"\\\""+c+"\\\"").collect(java.util.stream.Collectors.joining(","));return jdbc.queryForList("SELECT row_to_json(x)::text FROM (SELECT "+projection+" FROM "+table+") x ORDER BY 1",String.class);}}
    @Test void oldApplicationStateAndOriginMappingsSurviveActualTargetUpgrade() throws Exception {{
        String url=System.getenv("ACP_TEST_DATABASE_URL"),user=System.getenv("ACP_TEST_DATABASE_USER"),password=System.getenv("ACP_TEST_DATABASE_PASSWORD");
        ds=new DriverManagerDataSource(url+(url.contains("?")?"&":"?")+"currentSchema=acp_phase6_execution_test",user,password);jdbc=new JdbcTemplate(ds);tx=new TransactionTemplate(new DataSourceTransactionManager(ds));model=new TargetModel();var policy=new ApplicationPolicy(model,new Expressions(model),new acp.security.SessionGate(model,jdbc,new DataSourceTransactionManager(ds)));store=new ExecutionStore(jdbc,policy,new acp.security.PrivacyGuards(model,policy,new Expressions(model)));tasks=new TypedTasks(store);core=new InvocationCore(jdbc,model,new DataSourceTransactionManager(ds),time);inv=new Invocations(tasks,store,core);
        assertEquals("1",jdbc.queryForObject("SELECT max(version) FROM flyway_schema_history WHERE version IS NOT NULL",String.class));
        var tables=new java.util.ArrayList<String>({fields});tables.addAll(java.util.List.of("acp_idempotency","acp_rate","acp_audit","acp_classification_audit","acp_outbox","acp_sessions"));
        var columns=new java.util.LinkedHashMap<String,java.util.List<String>>();var before=new java.util.LinkedHashMap<String,java.util.List<String>>();
        for(String table:tables){{var names=jdbc.queryForList("SELECT column_name FROM information_schema.columns WHERE table_schema='acp_phase6_execution_test' AND table_name=? ORDER BY ordinal_position",String.class,table);assertFalse(names.isEmpty());columns.put(table,names);before.put(table,rows(table,names));}}
        for(String table:java.util.List.of("acp_idempotency","acp_rate","acp_audit","acp_outbox"))assertFalse(before.get(table).isEmpty(),table);
        var flyway=Flyway.configure().dataSource(url,user,password).schemas("acp_phase6_execution_test").defaultSchema("acp_phase6_execution_test").load();assertEquals(2,flyway.migrate().migrationsExecuted);assertEquals(0,flyway.migrate().migrationsExecuted);assertTrue(flyway.validateWithResult().validationSuccessful);
        for(String table:tables)assertEquals(before.get(table),rows(table,columns.get(table)),table);
        assertEquals({1 if domain=='payment' else 3},jdbc.queryForObject("SELECT count(*) FROM acp_outbox WHERE delivery_status='LEGACY_UNPROVEN'",Integer.class));
        insert("upgrade-resource");var input=Contracts.{symbol('INPUT-TASK','T')}.read(mapper.createObjectNode().put("INPUT-TASK-RESOURCE","upgrade-resource").put("INPUT-TASK-TEXT","new-profile"));
        inv.{symbol('UC-TASK','v')}(0,input,"upgrade-key",identity("tenant-one","fixture:operator"));assertEquals({1 if domain=='payment' else 3},jdbc.queryForObject("SELECT count(*) FROM acp_outbox WHERE commit_xid IS NOT NULL AND delivery_status='PENDING'",Integer.class));
    }}
}}
'''


def run(output,new_projects):
    output.mkdir(parents=True,exist_ok=False);checkout=output/'accepted-invocation-source';checkout.mkdir()
    archive=subprocess.check_output(['git','archive',CHECKPOINT],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(checkout,filter='data')
    code="import sys;sys.path.insert(0,'tooling');from target_worker import bundle_digest;print(bundle_digest())"
    old_bundle=subprocess.check_output([sys.executable,'-c',code],cwd=checkout,text=True).strip()
    if old_bundle!=OLD_BUNDLE:raise ValueError('HISTORICAL_GENERATOR_BUNDLE_CHANGED')
    old_projects=output/'old-projects'
    with (output/'old-generation.log').open('wb') as log:
        subprocess.run([sys.executable,str(checkout/'tooling/check_invocation_components.py'),'--output',str(old_projects)],cwd=checkout,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    report={'mode':'ACTUAL_GENERATED_0.1_TO_0.3_UPGRADE','oldCheckpoint':CHECKPOINT,'oldBundleDigest':'sha256:'+old_bundle,'domains':{}}
    for domain in ('payment','case-management'):
        old=old_projects/domain;new=new_projects/domain
        # Compile the accepted old implementation, with one old-runtime seed test.
        seed_code="""import sys;from pathlib import Path;sys.path.insert(0,'tooling');from invocation_reference_tests import source;from phase6_reference_tests import symbol
s=source(sys.argv[1]);s=s[:s.index('    @Test void exactApprovedInvocation')].replace('class InvocationCoreTest','class UpgradeSeedTest');s+='    @Test void commitActualInvocationProfileState() throws Exception {inv.'+symbol('UC-TASK','v')+'(0,invocation(\"old-profile-seed\"),\"old-profile-upgrade-key\",identity(\"tenant-one\",\"fixture:operator\"));}\\n}\\n';Path(sys.argv[2]).write_text(s)
"""
        seed=old/'backend/src/test/java/acp/generated/UpgradeSeedTest.java'
        subprocess.run([sys.executable,'-c',seed_code,domain,str(seed)],cwd=checkout,check=True,timeout=120)
        after=new/'backend/src/test/java/acp/generated/UpgradeAfterTest.java';after.write_text(after_source(domain))
        for label,project,test in [('old-runtime-seed',old,'UpgradeSeedTest'),('new-in-place-upgrade',new,'UpgradeAfterTest')]:
            with (output/(domain+'-'+label+'.log')).open('wb') as log:result=subprocess.run(['mvn','-B','-ntp','-Dtest='+test,'test'],cwd=project/'backend',stdout=log,stderr=subprocess.STDOUT,timeout=600)
            if result.returncode:raise ValueError(domain+'_'+label+'_FAILED')
            xml=ET.parse(project/('backend/target/surefire-reports/TEST-acp.generated.'+test+'.xml')).getroot()
            if any(int(xml.attrib[k]) for k in ('failures','errors','skipped')):raise ValueError('UPGRADE_TEST_NOT_GREEN')
        old_provenance=read_provenance(old/'acp/provenance.json');new_provenance=read_provenance(new/'acp/provenance.json')
        new_maps={m['artifact']:m for m in new_provenance['artifacts']}
        for mapping in old_provenance['artifacts']:
            new_mapping=new_maps.get(mapping['artifact'])
            if new_mapping is None or mapping['origins']!=new_mapping['origins']:raise ValueError('UPGRADE_ORIGIN_MAPPING_LOSS')
        report['domains'][domain]={'oldProfile':json.loads((old/'acp/profile.json').read_text()),'oldProvenance':json.loads((old/'acp/provenance.json').read_text()),'newProfile':json.loads((new/'acp/profile.json').read_text()),'newProvenance':json.loads((new/'acp/provenance.json').read_text()),'schemaUpgrade':'PASS','originMappingsPreserved':'PASS','realOldInvocationCommitted':'PASS','preservedTables':['domain','acp_idempotency','acp_rate','acp_audit','acp_classification_audit','acp_outbox','acp_sessions'],'newProfileInvocationCommitted':'PASS'}
        (output/'target-upgrade-report.json').write_text(json.dumps(report,indent=2)+'\n')
    report['result']='PASS';(output/'target-upgrade-report.json').write_text(json.dumps(report,indent=2)+'\n');print('ACTUAL_TARGET_PROFILE_UPGRADE = PASS')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--new-projects',type=Path,required=True);args=parser.parse_args();run(args.output.resolve(),args.new_projects.resolve())
