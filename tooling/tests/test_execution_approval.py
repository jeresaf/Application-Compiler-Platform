"""Human instruction represented through bounded reference authority, not AI identity."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_ir import admit, CanonicalError
from canonical_json import load
from changes import ChangeError
from execution_approval import APPROVED, WHEN, PRINCIPAL, authority, approved_snapshot, record, apply_approved_upgrade
from execution_fixtures import DEST, evolution
from canonical_fixtures import synthetic_approved
from changes import genesis, request
from history_repository import HistoryRepository
from reference_authority import ReferenceAuthority


class ExecutionApprovalTests(unittest.TestCase):
    def test_explicit_approval_reproduces_and_binds_new_exact_content(self):
        stored = load(DEST / 'human-approval.json')
        self.assertEqual(record(), stored)
        self.assertEqual('2026-10-08', stored['date'])
        for example in stored['examples']:
            snapshot = approved_snapshot(example['domain'])
            self.assertEqual(APPROVED[example['domain']][0], snapshot['contentDigest'])
            self.assertNotEqual(example['request']['author'], PRINCIPAL)
            self.assertEqual(PRINCIPAL, authority().verify(example['proof'], example['request'], WHEN)['principal'])
            changed = copy.deepcopy(example['request'])
            changed['contentDigest'] = 'sha256:' + '0' * 64
            with self.assertRaises(ChangeError):
                authority().verify(example['proof'], changed, WHEN)
            old = load(DEST.parent / 'canonical' / (example['domain'] + '.json'))
            with self.assertRaises(CanonicalError):
                admit(snapshot, lambda q: q['contentDigest'] == old['contentDigest'])

    def test_reference_approval_does_not_relabel_ai_origins_as_human(self):
        for domain in APPROVED:
            snapshot = approved_snapshot(domain)
            decision = next(n for n in snapshot['content']['nodes'] if n['id'] == 'DEC-EXECUTION-V03')
            self.assertTrue(any(o['actorType'] == 'AI' for o in decision['origins']))
            self.assertFalse(any(o['actor'] == PRINCIPAL for o in decision['origins']))

    def test_human_reference_approval_admits_fresh_content_through_accepted_change_lifecycle(self):
        for domain in APPROVED:
            old, _ = evolution(domain)
            app = old['content']['applicationId']
            source = synthetic_approved({'modelVersion': '0.2.0', 'applicationId': app, 'snapshotId': 'HISTORICAL-REFERENCE-SEED',
                'nodes': old['content']['nodes'], 'issues': [], 'approvals': []})
            # Separate historical-corpus test authority; this is not the new
            # human approval and cannot approve the successor candidate.
            historical_auth = ReferenceAuthority(b'public-historical-reference-seed-key',
                {'author-session': 'author', 'historical-review': 'reference:historical-corpus'},
                {'reference:historical-corpus': [app + ':SEMANTIC', app + ':SECURITY']})
            with tempfile.TemporaryDirectory() as temporary:
                repo = HistoryRepository(Path(temporary) / 'history.sqlite')
                initial = genesis(source, 'author')
                previous = historical_auth.issue('historical-review', request(initial), WHEN - 1)
                repo.bootstrap(initial, previous, historical_auth, WHEN - 1, 'author-session')
                receipt = apply_approved_upgrade(repo, domain)
                self.assertEqual(old, repo.snapshot(0))
                self.assertEqual(approved_snapshot(domain), repo.snapshot(1))
                self.assertEqual('APPLIED', repo.proposal('CHANGE-EXECUTION-V03')['state'])
                entry = repo.history()[-1]
                self.assertEqual(PRINCIPAL, entry['approval']['verdict']['principal'])
                authority().verify_historical(receipt['proof'], request(entry['plan']), WHEN)
                with self.assertRaises(ChangeError):
                    authority().verify_historical(previous, request(entry['plan']), WHEN)


if __name__ == '__main__':
    unittest.main()
