"""Real sealed 0.4 -> 0.5 target evolution of unchanged approved semantics.

No synthetic business ChangeSet/backfill is represented as human approved.
"""
import argparse,io,json,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'tooling')]
BASELINE='7e4e3438179e7a446c5f3737ad1d6d9cb07a96ea'

def run(projects,output):
 from target_release import verify_production_upgrade
 from target_provenance import read_provenance
 from invocation_reference_tests import source
 from check_target_profile_upgrade import after_source
 from phase6_reference_tests import symbol
 output.mkdir(parents=True,exist_ok=False);checkout=output/'sealed-04-source';checkout.mkdir()
 archive=subprocess.check_output(['git','archive',BASELINE],cwd=ROOT)
 with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(checkout,filter='data')
 old=output/'old-apps'
 generate="""import sys;from pathlib import Path;sys.path.insert(0,'tooling');from check_task_interface import ui_context;from compiler_core import compile_pipeline;from compiler_contracts import Success;from filesystem_artifacts import FilesystemArtifactStore;from target_worker import bundle_digest
assert bundle_digest()=='61c4647cfbe38cdbd97d03305685b3903f3ff24cfdb20d7c5b4502b478a0e06a'
for domain in ('payment','case-management'):
 src,ctx=ui_context(domain);result=compile_pipeline(src,ctx).result;assert isinstance(result,Success);FilesystemArtifactStore(Path(sys.argv[1])/domain).apply(result.output)
"""
 with (output/'sealed-04-generation.log').open('wb') as log:subprocess.run([sys.executable,'-c',generate,str(old)],cwd=checkout,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
 report={'policy':verify_production_upgrade('acp-spring-vue-postgres/0.4.0','acp-spring-vue-postgres/0.5.0'),'canonicalChange':'NONE_APPROVED_SNAPSHOTS_UNCHANGED','semanticEvolutionBoundary':'New String addition/backfills are synthetic test witnesses only; no new business approval exists. This target-release journey does not satisfy a complete semantic-evolution closure criterion.','domains':{}}
 for domain in ('payment','case-management'):
  seed=source(domain);seed=seed[:seed.index('    @Test void exactApprovedInvocation')].replace('class InvocationCoreTest','class RemediationSeedTest')
  seed+='    @Test void committedApprovedApplicationBeforeSuccessor() throws Exception {inv.'+symbol('UC-TASK','v')+'(0,invocation("before-successor"),"approved-target-upgrade",identity("tenant-one","fixture:operator"));}\n}\n'
  path=old/domain/'backend/src/test/java/acp/generated/RemediationSeedTest.java';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(seed)
  after=after_source(domain).replace('UpgradeAfterTest','RemediationUpgradeTest').replace('assertEquals("1",jdbc.queryForObject("SELECT max(version)', 'assertEquals("3",jdbc.queryForObject("SELECT max(version)').replace('assertEquals(2,flyway.migrate().migrationsExecuted)','assertEquals(0,flyway.migrate().migrationsExecuted)')
  lines=after.splitlines();after='\n'.join(line for line in lines if 'assertEquals(' not in line or 'count(*) FROM acp_outbox WHERE delivery_status=\'LEGACY_UNPROVEN\'' not in line)+'\n'
  # Both releases already use delivery-aware outbox rows. Preserve the old
  # committed rows and verify the successor adds its own rows, rather than
  # applying the historical 0.1 upgrade's empty-PENDING assumption.
  pending="SELECT count(*) FROM acp_outbox WHERE commit_xid IS NOT NULL AND delivery_status='PENDING'"
  after=after.replace('        insert("upgrade-resource");', '        int pendingBefore=jdbc.queryForObject("'+pending+'",Integer.class);\n        insert("upgrade-resource");')
  after=after.replace('assertEquals('+str(1 if domain=='payment' else 3)+',jdbc.queryForObject("'+pending+'",Integer.class))', 'assertEquals(pendingBefore+'+str(1 if domain=='payment' else 3)+',jdbc.queryForObject("'+pending+'",Integer.class))')
  path=projects/domain/'backend/src/test/java/acp/generated/RemediationUpgradeTest.java';path.write_text(after)
  for label,project,test in [('sealed-04',old/domain,'RemediationSeedTest'),('successor-05',projects/domain,'RemediationUpgradeTest')]:
   with (output/(domain+'-'+label+'.log')).open('wb') as log:subprocess.run(['mvn','-B','-ntp','-Dtest='+test,'test'],cwd=project/'backend',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
  previous=read_provenance(old/domain/'acp/provenance.json');current=read_provenance(projects/domain/'acp/provenance.json')
  newmaps={m['artifact']:m for m in current['artifacts']}
  for mapping in previous['artifacts']:
   if newmaps[mapping['artifact']]['origins']!=mapping['origins']:raise ValueError('UPGRADE_ORIGIN_LOSS')
  report['domains'][domain]={'previousBuild':previous['build'],'successorBuild':current['build'],'originsCompared':len(previous['artifacts']),'noCleanBetweenOldCommitAndSuccessor':True,'junit':str(projects/domain/'backend/target/surefire-reports/TEST-acp.generated.RemediationUpgradeTest.xml')}
 (output/'release-upgrade.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--projects',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.projects.resolve(),a.output.resolve())
