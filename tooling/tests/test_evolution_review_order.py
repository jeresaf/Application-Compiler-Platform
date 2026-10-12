"""Human review must preserve execution order, independently of node/ID sorting."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / 'proposals/phase6-evolution-review'


class EvolutionReviewOrderTests(unittest.TestCase):
    def test_documented_sequence_matches_canonical_execution_graph(self):
        for domain in ('payment', 'case-management'):
            with self.subTest(domain=domain):
                snapshot = json.loads((ROOT / 'test-corpus/deterministic-v04' /
                    (domain + '-canonical-candidate.json')).read_text())
                nodes = {n['id']: n for n in snapshot['content']['nodes']}
                steps = nodes['UC-TASK']['data']['steps']
                expected = [nodes[ref['id']]['data']['operation']['id'] for ref in steps]
                notes = (PACKAGES / (domain + '-human-review.md')).read_text()
                match = re.search(r'the exact command sequence is ([^.]+)\.', notes)
                self.assertIsNotNone(match)
                self.assertEqual(expected, match.group(1).split(' → '))
                package = json.loads((PACKAGES / (domain + '-human-review.json')).read_text())
                self.assertEqual([ref['id'] for ref in steps],
                    [step['id'] for step in package['operations']['steps']])
                self.assertEqual(expected, [step['data']['operation']['id']
                    for step in package['operations']['steps']])
                if domain == 'case-management':
                    self.assertEqual(['CMD-REVIEW', 'CMD-APPROVE', 'CMD-ARCHIVE'], expected)
                    self.assertNotEqual(sorted(expected), expected)


if __name__ == '__main__':
    unittest.main()
