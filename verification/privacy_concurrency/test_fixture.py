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

    def test_only_concurrency_harness_changes_and_final_assertions_remain(self):
        for domain in ('payment','case-management'):
            original = self.originals[domain]
            with patch.object(privacy_fixture,'sealed_source',return_value=original):
                fixed = privacy_fixture.source(domain)
            start = '    @Test void concurrentWorkersFence'
            end = '    @Test void domainRootLock'
            original_body = original[original.index(start):original.index(end)]
            fixed_body = fixed[fixed.index(start):fixed.index(end)]
            tail = original_body[original_body.index('assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_lifecycle_release_audit"'):]
            self.assertTrue(fixed_body.endswith(tail))
            self.assertIn('contentionProof(2, false, 10_000)',fixed_body)
            prefix = fixed[:fixed.index('    org.springframework.security.oauth2.jwt.Jwt workerIdentity')]
            self.assertEqual(prefix.replace(fixed_body,original_body,1).rstrip(),original.rstrip()[:-1].rstrip())
            self.assertEqual(fixed.count('@Test'),original.count('@Test')+5)
            self.assertLess(fixed.index('policy.actor(worker)'),fixed.index('owner=pool.submit'))
            self.assertLess(fixed.index('acquired.await('),fixed.index('competitor=pool.submit'))
            self.assertLess(fixed.index('competitor.get('),fixed.index('permitted.set(true)'))
            self.assertIn('contentionProof(1,false,250)',fixed)
            self.assertIn('pool.isTerminated()',fixed)

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
