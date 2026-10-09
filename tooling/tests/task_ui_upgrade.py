"""Actual sealed 0.3 database upgrade fixture, including all row bytes."""
import io,json,subprocess,sys,tarfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
BASE='fc89eeeefa43b90c4d19764bc344c2063f73a53a'
DIGEST='6b2fce95708344c7b78888efdc71da76ef70981ffb9b36933dda36b83a436afc'

def run(output,new_projects):
 output.mkdir(parents=True,exist_ok=True);checkout=output/'sealed-0.3'
 if not checkout.exists():
  checkout.mkdir();archive=subprocess.check_output(['git','archive',BASE])
  with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(checkout,filter='data')
 digest=subprocess.check_output([sys.executable,'-c',"import sys;sys.path.insert(0,'tooling');from target_worker import bundle_digest;print(bundle_digest())"],cwd=checkout,text=True).strip();assert digest==DIGEST
 old_projects=output/'old-projects'
 if not (old_projects/'privacy-lifecycle-report.json').exists():
  with (output/'old-generation.log').open('wb') as log:subprocess.run([sys.executable,'tooling/check_privacy_lifecycle_components.py','--output',str(old_projects)],cwd=checkout,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 assert json.loads((old_projects/'privacy-lifecycle-report.json').read_text())['result']=='GENERATED_ONLY_NO_RUNTIME_CLAIM'
 report={'fromCheckpoint':BASE,'oldBundleDigest':DIGEST,'mode':'ACTUAL_0.3_TO_0.4_DATABASE_UNCHANGED','domains':{}}
 for domain in ('payment','case-management'):
  old=old_projects/domain;new=new_projects/domain
  assert json.loads((old/'acp/profile.json').read_text())['profile']=='acp-spring-vue-postgres/0.3.0'
  assert json.loads((old/'acp/provenance.json').read_text())['build']['bundleDigest']=='sha256:'+DIGEST
  code="""import sys;from pathlib import Path;sys.path.insert(0,'tooling');from invocation_reference_tests import source;from phase6_reference_tests import symbol
s=source(sys.argv[1]);s=s[:s.index('    @Test void exactApprovedInvocation')].replace('class InvocationCoreTest','class UIUpgradeSeedTest');s+='    @Test void actualOldInvocation() throws Exception {inv.'+symbol('UC-TASK','v')+'(0,invocation(\"old-ui-seed\"),\"ui-upgrade-seed\",identity(\"tenant-one\",\"fixture:operator\"));}\\n}\\n';Path(sys.argv[2]).write_text(s)
"""
  p=old/'backend/src/test/java/acp/generated/UIUpgradeSeedTest.java';subprocess.run([sys.executable,'-c',code,domain,str(p)],cwd=checkout,check=True)
  schema='acp_ui_upgrade_'+domain.replace('-','_');p.write_text(p.read_text().replace('acp_phase6_execution_test',schema))
  with (output/(domain+'-old-seed.log')).open('wb') as log:subprocess.run(['mvn','-B','-ntp','-Dtest=UIUpgradeSeedTest','test'],cwd=old/'backend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
  old_build=json.loads((old/'acp/provenance.json').read_text())['build']
  old_migrations={name:(old/'database'/name).read_bytes() for name in ['V1__initial.sql','V2__delivery_jobs.sql','V3__privacy_lifecycle.sql']}
  # Regenerate the actual old project using the new worker and an explicit
  # deployment-owned identity inventory. Full CAS behavior is proved by the
  # integrated compiler/materializer gate; here the upgrade also checks output.
  from target_worker import TargetWorker
  from compiler_contracts import Document,fingerprint
  extension='frontend/src/extensions/identity.ts'
  identity=old/extension
  # Explicit synthetic deployment preparation: the old adapter's existing
  # accessToken/permissions implementation is retained verbatim. New 0.4
  # identity hints and notifications must be supplied by its human owner.
  custom=identity.read_text()+'''\n// actual 0.3 deployment customization; prepared for the 0.4 integration interface
export type IdentityHints={actor:string;subject:string;tenant:string;permissions:ReadonlySet<string>};
export function identity():IdentityHints{return {actor:'',subject:'',tenant:'',permissions:permissions()};}
export function onIdentityChange(_notify:()=>void):()=>void{return ()=>{};}
'''
  identity.write_text(custom)
  for name,command in [('old-frontend-lock',['npm','ci','--ignore-scripts','--no-audit','--no-fund']),('old-frontend-types',['npm','run','typecheck']),('old-frontend-build',['npm','run','build'])]:
   with (output/(domain+'-'+name+'.log')).open('wb') as log:subprocess.run(command,cwd=old/'frontend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
  digest=fingerprint(Document.of({'encoding':'UTF-8','text':custom}),'artifact-content')
  model=json.loads((new/'contracts/target-ir.json').read_text())
  build=json.loads((new/'acp/provenance.json').read_text())['build']
  rows=TargetWorker().call('plan',{'model':model,'build':build,'inventory':[{'path':extension,'digest':digest,'owner':'HUMAN_OWNED'}]})
  assert extension not in {a['path'] for a in rows}
  for artifact in rows:
   path=old/artifact['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(artifact['text'])
  assert identity.read_text()==custom
  assert json.loads((old/'acp/profile.json').read_text())['profile']=='acp-spring-vue-postgres/0.4.0'
  for name,command in [('new-frontend-lock',['npm','ci','--ignore-scripts','--no-audit','--no-fund']),('new-frontend-types',['npm','run','typecheck']),('new-frontend-tests',['npm','test']),('new-frontend-build',['npm','run','build'])]:
   with (output/(domain+'-'+name+'.log')).open('wb') as log:subprocess.run(command,cwd=old/'frontend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
  # New-runtime test snapshots every table, validates Flyway with zero migrations,
  # then compares every stored row; no cleaning occurs between applications.
  java='''package acp.generated;
import org.junit.jupiter.api.Test;import static org.junit.jupiter.api.Assertions.*;import org.springframework.jdbc.core.JdbcTemplate;import org.springframework.jdbc.datasource.DriverManagerDataSource;import org.flywaydb.core.Flyway;import java.util.*;
class UIUpgradeAfterTest {
 @Test void allStoredStateAndMigrationBytesRemainExact(){String url=System.getenv("ACP_TEST_DATABASE_URL"),user=System.getenv("ACP_TEST_DATABASE_USER"),password=System.getenv("ACP_TEST_DATABASE_PASSWORD");var jdbc=new JdbcTemplate(new DriverManagerDataSource(url+(url.contains("?")?"&":"?")+"currentSchema=acp_phase6_execution_test",user,password));
 var tables=jdbc.queryForList("SELECT tablename FROM pg_tables WHERE schemaname='acp_phase6_execution_test' ORDER BY tablename",String.class);var before=new LinkedHashMap<String,List<String>>();for(String table:tables)before.put(table,jdbc.queryForList("SELECT row_to_json(x)::text FROM "+table+" x ORDER BY 1",String.class));
 assertTrue(jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class)>0);assertTrue(jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_anchor",Integer.class)>0);
 var flyway=Flyway.configure().dataSource(url,user,password).schemas("acp_phase6_execution_test").defaultSchema("acp_phase6_execution_test").load();assertTrue(flyway.validateWithResult().validationSuccessful);assertEquals(0,flyway.migrate().migrationsExecuted);
 for(String table:tables)assertEquals(before.get(table),jdbc.queryForList("SELECT row_to_json(x)::text FROM "+table+" x ORDER BY 1",String.class),table);
 }
}
'''
  p=old/'backend/src/test/java/acp/generated/UIUpgradeAfterTest.java';p.write_text(java.replace('acp_phase6_execution_test',schema))
  with (output/(domain+'-new-unchanged.log')).open('wb') as log:subprocess.run(['mvn','-B','-ntp','-Dtest=UIUpgradeAfterTest','test'],cwd=old/'backend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
  for migration in ['V1__initial.sql','V2__delivery_jobs.sql','V3__privacy_lifecycle.sql']:assert old_migrations[migration]==(new/'database'/migration).read_bytes()
  report['domains'][domain]={'oldProvenance':old_build,'newProvenance':json.loads((new/'acp/provenance.json').read_text())['build'],'allTablesRowForRow':'PASS','zeroMigrations':'PASS','actualOldProjectRegeneration':'PASS','humanIdentityCustomizationSurvived':'PASS','identityInterfacePreparation':'EXPLICIT_SYNTHETIC_DEPLOYMENT_FIXTURE_FOR_0.4','oldFrontendBuild':'PASS','newFrontendBuildAndTests':'PASS','V1V2V3Exact':'PASS'}
 report['result']='PASS';(output/'ui-upgrade-report.json').write_text(json.dumps(report,indent=2)+'\n');print('ACTUAL_UI_UPGRADE = PASS')
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--new-projects',type=Path,required=True);a=p.parse_args();run(a.output.resolve(),a.new_projects.resolve())
