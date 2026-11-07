"""Cryptographic fixture and immutable successor regression checks."""
import json,ssl,tempfile,unittest,urllib.request
from pathlib import Path
from unittest.mock import patch
import jwt
from engineering.identity.issuer import Issuer
from engineering.identity.target import IdentityTarget,source_digest
from engineering.identity.fixture import adapter_source
from engineering.identity.run import scan,safe_maven_logs
from engineering.identity.scenarios import NEGATIVES,configuration

class IdentityTests(unittest.TestCase):
 def setUp(self):self.issuer=Issuer();self.addCleanup(self.issuer.close)
 def decode(self,token,key='h5-k1',**kwargs):return jwt.decode(token,self.issuer.keys[key].public_key(),algorithms=['RS256'],audience='acp-h5',issuer=self.issuer.url,**kwargs)
 def test_signed_https_issuance(self):
  token=self.issuer.obtain();self.assertEqual(self.decode(token)['sub'],'fixture:operator');self.assertIn('/token',self.issuer.paths)
 def test_tenant_and_session_binding(self):
  a=self.decode(self.issuer.obtain());b=self.decode(self.issuer.obtain(subject='fixture:reporter-two',tenant='tenant-two'));self.assertNotEqual(a['sid'],b['sid']);self.assertNotEqual(a['tenant'],b['tenant'])
 def test_rotation_preserves_authentication_event(self):
  a=self.decode(self.issuer.obtain());self.issuer.active='h5-k2';b=self.decode(self.issuer.obtain(),'h5-k2');self.assertEqual(a['auth_time'],b['auth_time']);self.assertEqual(a['sid'],b['sid'])
 def test_signature_substitution_rejected(self):
  with self.assertRaises(jwt.InvalidSignatureError):self.decode(self.issuer.mint(kid='untrusted',headers={'kid':'h5-k1'}))
 def test_algorithm_confusion_rejected(self):
  with self.assertRaises(jwt.InvalidAlgorithmError):self.decode(self.issuer.mint(algorithm='HS256'))
 def test_tls_requires_fixture_trust(self):
  with self.assertRaises(urllib.error.URLError):urllib.request.urlopen(self.issuer.url+'/jwks',timeout=3)
  with urllib.request.urlopen(self.issuer.url+'/jwks',context=self.issuer.context,timeout=3) as r:self.assertEqual(json.load(r),self.issuer.jwks())
 def test_configuration_contains_only_public_keys(self):
  with tempfile.TemporaryDirectory() as t:
   config,keys=configuration(self.issuer,Path(t),('h5-k1','h5-k2'),'identity');self.assertEqual(len(json.loads(keys.read_bytes())['keys']),2);self.assertNotIn('PRIVATE',keys.read_text());self.assertEqual(json.loads(config.read_bytes())['algorithm'],'RS256')
 def test_external_adapter_has_no_trusted_decoder(self):
  s=adapter_source();self.assertNotIn('@Bean JwtDecoder decoder()',s);self.assertNotIn('decoder.decode("browser-authorized")',s);self.assertIn('INTERACTIVE_WORKER_IMPERSONATION_FORBIDDEN',s)
 def test_export_rejects_bearer_leak(self):
  with tempfile.TemporaryDirectory() as t:
   token=self.issuer.obtain();Path(t,'leak').write_text(token)
   with self.assertRaisesRegex(ValueError,'H5_CREDENTIAL_EXPORT_BLOCKED'):scan(t,[token.encode()])
 def test_exact_source_mutation_rejected(self):
  target=IdentityTarget()
  with patch('engineering.identity.target.source_digest',return_value='0'*64):
   with self.assertRaisesRegex(ValueError,'H5_SOURCE_CHANGED'):target._verify()
 def test_version_scoped_successor(self):
  target=IdentityTarget();target._verify();self.assertEqual(target.bundle,source_digest());self.assertEqual(target.descriptor()['scope'],'QUALIFICATION_ONLY');self.assertEqual(target.h1_bundle,'f982b13e43e0efd070ea1b0773da5aedcdbf2486363c6e902f27c36ba00bcb02')
 def test_private_issuer_cleanup(self):
  root=Path(self.issuer.temp.name);self.issuer.close();self.assertFalse(root.exists());self.assertFalse(self.issuer.thread.is_alive());self.issuer.close=lambda:None
 def test_required_adversarial_inventory(self):self.assertEqual(len(NEGATIVES),35);self.assertTrue({'signatureSubstitution','algorithmConfusion','trustedShortcut','revokedSession','crossTenantDocument'}<=NEGATIVES)

 def test_maven_environment_is_redacted_before_evidence(self):
  from engineering.demo import reference as demo
  def raw(args,cwd,path):Path(path).write_bytes(b'[DEBUG] env.SECRET: sensitive\nplugin realm verified\n')
  with tempfile.TemporaryDirectory() as t,patch.object(demo,'command',raw):
   with safe_maven_logs():demo.command(['mvn'],Path(t),Path(t,'evidence.log'))
   self.assertEqual(Path(t,'evidence.log').read_bytes(),b'[DEBUG] Environment property redacted\nplugin realm verified\n')
 def test_maven_redaction_preserves_failure(self):
  from engineering.demo import reference as demo
  def raw(args,cwd,path):Path(path).write_bytes(b'[DEBUG] env.SECRET: sensitive\nBUILD FAILURE\n');raise ValueError('COMMAND_FAILED')
  with tempfile.TemporaryDirectory() as t,patch.object(demo,'command',raw):
   with self.assertRaisesRegex(ValueError,'COMMAND_FAILED'):
    with safe_maven_logs():demo.command(['mvn'],Path(t),Path(t,'evidence.log'))
   self.assertNotIn(b'sensitive',Path(t,'evidence.log').read_bytes());self.assertIn(b'BUILD FAILURE',Path(t,'evidence.log').read_bytes())
