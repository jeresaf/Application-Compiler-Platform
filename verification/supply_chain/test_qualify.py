from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from engineering.supply_chain.qualify import maven_component, sbom, scan


class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [maven_component('org/example/x/1.0/x-1.0.jar', {'sha256': 'a'*64})]

    def test_coordinate_and_version_disagree(self):
        with self.assertRaisesRegex(ValueError, 'MAVEN_ARTIFACT_IDENTITY'):
            maven_component('org/example/x/2/x-1.jar', {'sha256': 'a'*64})

    def test_bom_preserves_hash_and_explicit_incompleteness(self):
        bom = sbom(self.rows, 'test')
        self.assertEqual(bom['components'][0]['hashes'][0]['content'], 'a'*64)
        self.assertEqual(bom['compositions'][0]['aggregate'], 'incomplete')

    def test_malformed_or_incomplete_scanner_response(self):
        with tempfile.TemporaryDirectory() as temp:
            for response in ({}, {'results': []}, {'results': [{'unknown': True}]}):
                result = scan(self.rows, Path(temp), request=lambda *args: response)
                self.assertEqual(result['status'], 'SCANNER_UNAVAILABLE')

    def test_transport_failure_remains_explicit(self):
        def unavailable(*args):
            raise HTTPError(args[0], 429, 'rate limited', {}, None)

        with tempfile.TemporaryDirectory() as temp:
            result = scan(self.rows, Path(temp), request=unavailable)
        self.assertEqual(result['httpStatus'], 429)
        self.assertEqual(result['status'], 'SCANNER_UNAVAILABLE')

    def test_empty_scan_has_only_bounded_meaning(self):
        with tempfile.TemporaryDirectory() as temp:
            result = scan(self.rows, Path(temp), request=lambda *args: {'results': [{}]})
        self.assertEqual(result['status'], 'NO_MATCHES_IN_QUERIED_SCOPE')
