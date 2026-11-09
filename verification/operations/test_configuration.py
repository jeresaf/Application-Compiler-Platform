"""Real JVM validation of closed lab settings; no application or database starts."""
import hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
from engineering.operations.configuration import profile
from engineering.source_intelligence.model import encode
ROOT=Path(__file__).resolve().parents[2]
class ConfigurationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='h6-config-probe-');cls.base=Path(cls.temp.name)
  retained=ROOT/'.audit-artifacts/phase11-h5-20261106/runtime-4/outputs/backend/target'
  override=os.environ.get('ACP_H6_TEST_CLASSPATH')
  if override:cls.cp=override
  else:cls.cp=(retained/'browser-classpath').read_text().strip()
  source=cls.base/'ProfileProbe.java';source.write_text('''import acp.operations.OperationalConfiguration;public class ProfileProbe{public static void main(String[] args){try{if(args[0].equals("bootstrap")){var env=new org.springframework.core.env.StandardEnvironment();env.getPropertySources().addFirst(new org.springframework.core.env.MapPropertySource("fixture-cli",java.util.Map.of("acp.runtime.mode","development")));new OperationalConfiguration().postProcessEnvironment(env,new org.springframework.boot.SpringApplication());}else OperationalConfiguration.profile();System.out.println("VALIDATED");}catch(Exception rejected){System.out.println("REJECTED");System.exit(2);}}}''')
  subprocess.run(['javac','-cp',cls.cp,'-d',str(cls.base),str(ROOT/'engineering/operations/templates/OperationalConfiguration.java'),str(source)],capture_output=True,check=True)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def probe(self,value=None,*,mode='profile',environment=None,pin=None,raw=None,symlink=False):
  with tempfile.TemporaryDirectory(prefix='h6-settings-') as t:
   p=Path(t)/'profile.json';data=raw if raw is not None else encode(profile() if value is None else value);p.write_bytes(data)
   if symlink:q=Path(t)/'link.json';q.symlink_to(p);p=q
   env={k:v for k,v in os.environ.items() if not k.startswith(('ACP_','SPRING_','LOGGING_','JAVA_TOOL_OPTIONS'))};env.update(ACP_OPERATIONAL_CONFIG=str(p),ACP_OPERATIONAL_CONFIG_SHA256=hashlib.sha256(data).hexdigest() if pin is None else pin,ACP_DATABASE_USER='unit-only-user',ACP_DATABASE_PASSWORD='unit-only-not-an-operational-secret',ACP_DATABASE_URL='jdbc:postgresql://127.0.0.1:12345/unit',ACP_IDENTITY_CONFIG='/unit-reference-not-opened-by-this-probe',ACP_IDENTITY_CONFIG_SHA256='0'*64,ACP_METRICS_READ_KEY='unit-only-capability-not-an-operational-secret')
   env.update(environment or {});r=subprocess.run(['java','-Xmx512m','-XX:ActiveProcessorCount=2','-cp',str(self.base)+':'+self.cp,'ProfileProbe',mode],env=env,capture_output=True,text=True,timeout=15);self.assertNotIn(env['ACP_DATABASE_PASSWORD'],r.stdout+r.stderr);return r.returncode
 def test_valid_closed_profile(self):self.assertEqual(self.probe(),0)
 def test_valid_bootstrap_context(self):self.assertEqual(self.probe(mode='bootstrap'),0)
 def test_profile_hash_mismatch(self):self.assertEqual(self.probe(pin='0'*64),2)
 def test_unknown_fields_and_secret_values_rejected(self):
  for k in ('extra','databasePassword','identityShortcut'):
   with self.subTest(k=k):self.assertEqual(self.probe(dict(profile(),**{k:'not-a-real-secret'})),2)
 def test_numeric_types_and_bounds(self):
  for k,v in [('poolConnections',0),('poolConnections',4294967296),('acquisitionTimeoutMs',0),('workerConcurrency',8),('logEventsPerSecond',100000),('maxHeapMiB',True),('maxProcessors',0),('workerStallSeconds',1.5)]:
   with self.subTest(k=k,v=v):self.assertEqual(self.probe(dict(profile(),**{k:v})),2)
 def test_production_profile_is_not_a_development_fallback(self):self.assertEqual(self.probe(dict(profile(),runtimeMode='production')),2)
 def test_unsupported_secret_reference(self):self.assertEqual(self.probe(dict(profile(),metricsReadKeyRef='ANY_OTHER_SECRET')),2)
 def test_session_policy_is_not_overridable(self):self.assertEqual(self.probe(dict(profile(),sessionPolicy='DISABLED')),2)
 def test_duplicate_profile_field(self):self.assertEqual(self.probe(raw=b'{"profile":"one","profile":"two"}'),2)
 def test_symlink_profile_rejected(self):self.assertEqual(self.probe(symlink=True),2)
 def test_shadowed_production_mode_is_conflicting(self):self.assertEqual(self.probe(mode='bootstrap',environment={'ACP_RUNTIME_MODE':'production'}),2)
 def test_unsafe_trace_logging_rejected(self):self.assertEqual(self.probe(mode='bootstrap',environment={'LOGGING_LEVEL_ORG_SPRINGFRAMEWORK_SECURITY':'TRACE'}),2)
 def test_required_secret_reference_missing(self):self.assertEqual(self.probe(mode='bootstrap',environment={'ACP_METRICS_READ_KEY':''}),2)
 def test_nonlocal_database_not_activated(self):self.assertEqual(self.probe(mode='bootstrap',environment={'ACP_DATABASE_URL':'jdbc:postgresql://unapproved.invalid/prod'}),2)
 def test_runtime_cannot_mutate_canonical_retry_policy(self):self.assertEqual(self.probe(mode='bootstrap',environment={'ACP_INTEGRITY_LEASE_SECONDS':'1'}),2)
