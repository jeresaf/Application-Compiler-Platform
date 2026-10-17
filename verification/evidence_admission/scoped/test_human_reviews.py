import unittest
from dataclasses import replace
from test_manifest import Fixture,canonicalize,parse_canonical


class HumanReviewTests(unittest.TestCase):
    def test_synthetic_review_remains_qualification_only(self):
        f=Fixture(human=True);self.addCleanup(f.close)
        result=f.run();self.assertEqual(result.status,'QUALIFICATION_ONLY')
        self.assertFalse(hasattr(result,'accepted_reviews'))

    def test_raw_document_changes_fail_even_with_equivalent_json(self):
        f=Fixture(human=True);self.addCleanup(f.close)
        p=f.artifacts/'deployment-review.json';p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaises(ValueError):f.run()

    def test_revoked_reviewer_and_expired_grant(self):
        for revoked in (True,False):
            with self.subTest(revoked=revoked):
                f=Fixture(human=True);self.addCleanup(f.close)
                if revoked:f.context=replace(f.context,revoked_keys=frozenset({'key:reviewer'}))
                else:
                    grant=parse_canonical(f.context.review_grants[0]);grant['validUntil']='2026-10-17T11:59:00Z'
                    f.context=replace(f.context,review_grants=(canonicalize(grant),))
                with self.assertRaises(ValueError):f.run()
