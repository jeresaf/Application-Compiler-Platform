import sys
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engineering.generator_builds import privacy_fixture
from engineering.ci.privacy_gate import corrected_fixture
import privacy_lifecycle_reference_tests


class PrivacyFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = {domain: privacy_fixture.sealed_source(domain) for domain in ('payment','case-management')}

    def test_only_concurrency_identity_changes_and_all_assertions_remain(self):
        for domain in ('payment','case-management'):
            original = self.originals[domain]
            with patch.object(privacy_fixture,'sealed_source',return_value=original):
                fixed = privacy_fixture.source(domain)
            original_body = original[original.index('    @Test void concurrentWorkersFence'):original.index('    @Test void domainRootLock')]
            fixed_body = fixed[fixed.index('    @Test void concurrentWorkersFence'):fixed.index('    @Test void domainRootLock')]
            restored = fixed_body.replace('var jwt=identity("tenant-one","fixture:operator");','',1).replace('workerJwt,release());}));}gate.countDown();', privacy_fixture.WORKER_IDENTITY,1).replace('for(int i=0;i<2;i++){var workerJwt=workerIdentity(jwt,i);calls.add(pool.submit(', 'for(int i=0;i<2;i++)calls.add(pool.submit(',1)
            self.assertEqual(restored,original_body)
            prefix = fixed[:fixed.index('    org.springframework.security.oauth2.jwt.Jwt workerIdentity')]
            prefix = prefix.replace(fixed_body, original_body, 1)
            self.assertEqual(prefix.rstrip(), original.rstrip()[:-1].rstrip())
            for token in ('LifecycleRuntime.Result.COMPLETED,LifecycleRuntime.Result.BUSY','call.get()', 'SELECT count(*) FROM acp_lifecycle_release_audit'):
                self.assertIn(token,fixed_body)
            self.assertEqual(fixed.count('@Test'),original.count('@Test')+3)
            self.assertEqual(fixed[:fixed.index('    @Test void concurrentWorkersFence')], original[:original.index('    @Test void concurrentWorkersFence')])

    def test_unknown_sealed_fixture_shape_fails_closed(self):
        original=self.originals['payment']
        with patch.object(privacy_fixture,'sealed_source',return_value=original.replace(privacy_fixture.DECLARATION,'changed')):
            with self.assertRaisesRegex(ValueError,'SHAPE_CHANGED'):privacy_fixture.source('payment')

    def test_scoped_substitution_restores_frozen_module_even_on_exception(self):
        original=privacy_lifecycle_reference_tests.source
        with self.assertRaises(RuntimeError):
            with corrected_fixture():
                self.assertIs(privacy_lifecycle_reference_tests.source,privacy_fixture.source)
                raise RuntimeError('abort')
        self.assertIs(privacy_lifecycle_reference_tests.source,original)

    def test_exact_ci_changes_reject_any_unreviewed_bytes(self):
        from verification.evidence_admission.test_preservation import PRIVACY_MODIFIED_HASHES, preserved_bytes
        original=Path.read_bytes
        for relative in PRIVACY_MODIFIED_HASHES:
            path=ROOT/relative
            with patch.object(Path,'read_bytes',lambda item: b'unreviewed' if item==path else original(item)):
                with self.assertRaises(AssertionError):preserved_bytes(path)
