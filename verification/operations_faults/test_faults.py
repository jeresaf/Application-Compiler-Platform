"""Deterministic regressions for external fixtures and metadata-only failure export."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
from engineering.operations.fixture import adapter_source
from engineering.operations.diagnostics import collect
from engineering.operations.run import public_evidence_paths,PUBLIC_EVIDENCE
from engineering.reliability.concurrency import earlier_test_occurrence

class Faults(unittest.TestCase):
 def test_hour_rollover_cannot_reuse_a_retained_occurrence(self):
  old_hour=1794204000;new_hour=old_hour+3600
  self.assertEqual(new_hour-3600,old_hour) # Original relative fixture collides.
  positions=[];minimum=old_hour
  for now in (new_hour-1,new_hour,new_hour+3600,new_hour+7200):
   value=earlier_test_occurrence(minimum,now);self.assertLess(value,minimum);self.assertEqual(value%3600,0);positions.append(value);minimum=value
  self.assertEqual(len(set(positions)),4);self.assertNotIn(old_hour,positions)
 def test_empty_population_is_also_in_the_past(self):
  self.assertEqual(earlier_test_occurrence(None,7201),3600)
 def test_failure_export_excludes_secrets_and_untrusted_messages(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'private';root.mkdir();token='secret-bearer-canary';(root/'demo-backend-1.log').write_text(token+'\nH4_EXCEPTION:java.sql.SQLException:23505\n')
   (root/'failure.json').write_text(json.dumps({'error':token}));(root/'private-key.pem').write_text(token)
   result=collect(root,Path(t)/'public');output=(Path(t)/'public/failure.json').read_text();self.assertNotIn(token,output);self.assertEqual(result['exceptions'][0]['sqlState'],'23505');self.assertEqual(len(list((Path(t)/'public').iterdir())),1)
 def test_public_export_excludes_raw_database_and_application_logs(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   for name in PUBLIC_EVIDENCE:p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
   (root/'runtime/sql-001.json').write_text('encoded-document-bytes');(root/'runtime/demo-backend-1.log').write_text('private-diagnostic')
   selected={p.relative_to(root).as_posix() for p in public_evidence_paths(root)};self.assertEqual(selected,set(PUBLIC_EVIDENCE));self.assertNotIn('runtime/sql-001.json',selected);self.assertNotIn('runtime/demo-backend-1.log',selected)
 def test_public_export_rejects_missing_or_symlink_evidence(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   with self.assertRaisesRegex(ValueError,'MISSING_OR_ESCAPE'):public_evidence_paths(root)
   for name in PUBLIC_EVIDENCE:p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
   victim=root/PUBLIC_EVIDENCE[0];victim.unlink();victim.symlink_to(root/PUBLIC_EVIDENCE[1])
   with self.assertRaisesRegex(ValueError,'MISSING_OR_ESCAPE'):public_evidence_paths(root)
 def test_export_cannot_overwrite_prior_evidence(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'input';root.mkdir();out=Path(t)/'out';out.mkdir()
   with self.assertRaisesRegex(ValueError,'COLLISION'):collect(root,out)

class Pressure(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='h6-pressure-probe-');cls.root=Path(cls.tmp.name)
  cls.cp=os.environ.get('ACP_H6_TEST_CLASSPATH') or Path('.audit-artifacts/phase11-h5-20261106/runtime-4/outputs/backend/target/browser-classpath').read_text().strip()
  text=adapter_source();body=text[text.index('  final java.util.concurrent.ExecutorService h6Pressure='):text.index('@GetMapping("/__test/facts")')]
  body=body.replace('@jakarta.annotation.PreDestroy','').replace('@GetMapping("/__test/h6-pressure-state")','').replace('@PostMapping("/__test/h6-pressure")','')
  source='''import java.util.*;import java.util.concurrent.*;import java.util.concurrent.atomic.*;import java.lang.reflect.*;import java.sql.*;import org.springframework.jdbc.core.JdbcTemplate;
public class PressureProbe{
 final JdbcTemplate jdbc;PressureProbe(javax.sql.DataSource ds){jdbc=new JdbcTemplate(ds);}
 BODY
 public static void main(String[] args)throws Exception{
  var serialGate=new Semaphore(1);var release=new CountDownLatch(1);var active=new AtomicInteger();var peak=new AtomicInteger();boolean fault=args[0].equals("fault"),serial=args[0].equals("serial");
  var ds=new org.springframework.jdbc.datasource.AbstractDataSource(){public Connection getConnection()throws SQLException{
   if(fault)throw new SQLTransientConnectionException("unit-secret-not-exported","08001");
   if(serial)try{serialGate.acquire();}catch(InterruptedException e){throw new SQLException("interrupted");}int current=active.incrementAndGet();peak.accumulateAndGet(current,Math::max);
   return (Connection)Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{Connection.class},(proxy,m,a)->{
    if(m.getName().equals("createStatement"))return Proxy.newProxyInstance(getClass().getClassLoader(),new Class[]{Statement.class},(p,method,b)->{if(method.getName().equals("execute")){if(!serial&&!release.await(10,TimeUnit.SECONDS))throw new SQLException("gate timeout");return true;}return null;});
    if(m.getName().equals("close")){active.decrementAndGet();if(serial)serialGate.release();return null;}return null;});}
   public Connection getConnection(String u,String p)throws SQLException{return getConnection();}};
  var fixture=new PressureProbe(ds);boolean rejected=false;
  try{fixture.h6Pressure();}catch(ExecutionException expected){rejected=true;}
  try{if(fault){if(!rejected||fixture.h6PressureErrors.size()!=1)throw new AssertionError("lost worker failure");}
   else if(serial){if(peak.get()==34)throw new AssertionError("serialized counterexample passed");}
   else if(active.get()!=34||peak.get()!=34)throw new AssertionError("real overlap missing");}
  finally{release.countDown();fixture.h6PressureClose();}
  try{fixture.h6Pressure();throw new AssertionError("hidden retry accepted");}catch(IllegalStateException expected){if(!expected.getMessage().equals("H6_PRESSURE_ALREADY_STARTED"))throw expected;}
  if(active.get()!=0)throw new AssertionError("leaked connection");System.out.println("VERIFIED");
 }
}'''.replace('BODY',body)
  p=cls.root/'PressureProbe.java';p.write_text(source);subprocess.run(['javac','-cp',cls.cp,'-d',str(cls.root),str(p)],capture_output=True,check=True)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def run_probe(self,mode):
  r=subprocess.run(['java','-cp',str(self.root)+':'+self.cp,'PressureProbe',mode],capture_output=True,text=True,timeout=25);self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(r.stdout.strip(),'VERIFIED')
 def test_all_borrowers_remain_concurrent_until_release(self):self.run_probe('overlap')
 def test_connection_failure_is_not_a_successful_submission(self):self.run_probe('fault')
 def test_serialized_counterexample_fails_overlap(self):self.run_probe('serial')
