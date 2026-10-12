"""Pure replay regressions. No repository, authority, session or proof is created."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tooling'))
from canonical_json import canonical_bytes, digest, load
from canonical_ir import CanonicalError, validate_snapshot
from canonical_fixtures import synthetic_approved
from reference_models import models
from changes import ChangeError, genesis, prepare, check_sources

PINS = {
    'payment': (
        'sha256:eaec1ba1aeb76a96bda57fab383ff6ce87a05f16d1ebea56f5727883255d9f6e',
        'sha256:d2cd65d09c4739f53d4c57dddd1d29eb5456bc421c5fac745b336459590d25ac',
        'sha256:d0f6e8d96a07e8e8358ad8f1f558f9ec3d69fd8008cceb75e82f4f695e3cf47d'),
    'case-management': (
        'sha256:3ee1b350e4222870270c871a379a36c48b8d6fbb684c05ad4ed7438b0b065779',
        'sha256:4207852923d9e7e16f7e273d5bedbaa78bc2f10d82efa6f5568f00d23b89055b',
        'sha256:5b3a69bb1d6e0e69ed620cd1dd32d10e8a07cec276583055b53ec03bfdcc6b90'),
}


class PureReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.chains = {}
        for filename, model in models().items():
            domain = filename[:-5]
            # Reproduce existing historical structural fixture labels only.
            source = synthetic_approved(model)
            initial = load(ROOT / 'test-corpus/canonical' / filename)
            snapshots = [initial]
            transitions = []
            for corpus, suffix in [('execution-v03', 'canonical'),
                                   ('deterministic-v04', 'canonical-candidate')]:
                folder = ROOT / 'test-corpus' / corpus
                change = load(folder / f'{domain}-change.json')
                plan = prepare(snapshots[-1], change)
                transitions.append((change, plan, load(folder / f'{domain}-plan.json')))
                snapshots.append(load(folder / f'{domain}-{suffix}.json'))
            cls.chains[domain] = (source, genesis(source, 'author'), snapshots, transitions)

    def test_exact_genesis_source_receipt_and_revision_one(self):
        manifest = load(ROOT / 'test-corpus/canonical/manifest.json')
        for domain, (source, plan, snapshots, _) in self.chains.items():
            with self.subTest(domain=domain):
                expected = next(e for e in manifest['examples'] if e['file'] == domain + '.json')
                self.assertEqual(expected['sourceDigest'], digest(source, 'authoring'))
                self.assertEqual(canonical_bytes(snapshots[0]), canonical_bytes(plan['candidate']))
                self.assertEqual(PINS[domain][0], plan['candidate']['contentDigest'])
                self.assertTrue(all(n['revision'] == 1 for n in snapshots[0]['content']['nodes']))
                self.assertEqual(['SEMANTIC', 'SECURITY'], plan['requiredScopes'])
                check_sources(plan['sources'])

    def test_exact_all_transition_plans_snapshots_and_scopes(self):
        for domain, (_, _, snapshots, transitions) in self.chains.items():
            for stage, (_, plan, stored) in enumerate(transitions, 1):
                with self.subTest(domain=domain, stage=stage):
                    self.assertEqual(canonical_bytes(stored), canonical_bytes(plan))
                    self.assertEqual(canonical_bytes(snapshots[stage]), canonical_bytes(plan['candidate']))
                    self.assertEqual(PINS[domain][stage], plan['candidate']['contentDigest'])
                    self.assertEqual(['MIGRATION', 'SECURITY', 'SEMANTIC'] if stage == 1
                                     else ['SECURITY', 'SEMANTIC'], plan['requiredScopes'])

    def test_all_revision_bytes_immutable_and_basis_resolves(self):
        for domain, (_, _, snapshots, _) in self.chains.items():
            with self.subTest(domain=domain):
                records = {}
                for snapshot in snapshots:
                    for node in snapshot['content']['nodes']:
                        key = (node['id'], node['revision'])
                        if key in records:
                            self.assertEqual(records[key], canonical_bytes(node))
                        records[key] = canonical_bytes(node)
                    for node in snapshot['content']['nodes']:
                        for ref in node['basis']:
                            self.assertIn((ref['id'], ref['revision']), records)
                self.assertEqual(250 if domain == 'payment' else 357, len(records))

    def test_wrong_base_digest_rejected(self):
        for domain, (_, _, snapshots, transitions) in self.chains.items():
            c = copy.deepcopy(transitions[0][0])
            c['base']['digest'] = PINS[domain][2]
            with self.subTest(domain=domain), self.assertRaises(ChangeError) as error:
                prepare(snapshots[0], c)
            self.assertEqual('ACP-CHANGE-BASE', error.exception.code)

    def test_skipped_version_transition_rejected(self):
        for domain, (_, _, snapshots, transitions) in self.chains.items():
            c = copy.deepcopy(transitions[1][0])
            c['base']['digest'] = PINS[domain][0]
            with self.subTest(domain=domain), self.assertRaises(ChangeError) as error:
                prepare(snapshots[0], c)
            self.assertEqual('ACP-CHANGE-VERSION', error.exception.code)

    def test_stale_and_skipped_explicit_revision_rejected(self):
        for domain, (_, _, snapshots, transitions) in self.chains.items():
            for mutation in ('stale', 'skip'):
                c = copy.deepcopy(transitions[0][0])
                op = next(o for o in c['operations'] if o['op'] == 'REVISE')
                if mutation == 'stale':
                    op['expectedRevision'] += 1
                else:
                    op['node']['revision'] += 1
                with self.subTest(domain=domain, mutation=mutation), self.assertRaises(ChangeError) as error:
                    prepare(snapshots[0], c)
                self.assertEqual('ACP-CHANGE-REVISION', error.exception.code)

    def test_later_revision_add_rejected(self):
        for domain, (_, _, snapshots, transitions) in self.chains.items():
            c = copy.deepcopy(transitions[0][0])
            next(o for o in c['operations'] if o['op'] == 'ADD')['node']['revision'] = 2
            with self.subTest(domain=domain), self.assertRaises(ChangeError) as error:
                prepare(snapshots[0], c)
            self.assertEqual('ACP-CHANGE-IDENTITY', error.exception.code)

    def test_tampered_source_receipt_rejected(self):
        for domain, (_, initial, snapshots, transitions) in self.chains.items():
            c = copy.deepcopy(transitions[0][0])
            c['sources'] = copy.deepcopy(initial['sources'])
            c['sources'][0]['receipt']['targetDigest'] = PINS[domain][2]
            with self.subTest(domain=domain), self.assertRaises(ChangeError) as error:
                prepare(snapshots[0], c)
            self.assertEqual('ACP-CHANGE-SOURCE', error.exception.code)

    def test_required_migration_cannot_be_removed(self):
        for domain, (_, _, snapshots, transitions) in self.chains.items():
            c = copy.deepcopy(transitions[0][0])
            c['migration'].update(mode='NONE', steps=[], preconditions=[], verification=[],
                                  recovery='No data operation')
            with self.subTest(domain=domain), self.assertRaises(ChangeError) as error:
                prepare(snapshots[0], c)
            self.assertEqual('ACP-CHANGE-MIGRATION', error.exception.code)

    def test_modified_snapshot_rejected_by_digest_validation(self):
        for domain, (_, _, snapshots, _) in self.chains.items():
            candidate = copy.deepcopy(snapshots[2])
            candidate['content']['nodes'][0]['name'] += ' tampered'
            with self.subTest(domain=domain), self.assertRaises(CanonicalError):
                validate_snapshot(candidate)

    def test_altered_meaning_cannot_match_exact_approved_endpoint(self):
        for domain, (_, _, snapshots, transitions) in self.chains.items():
            c = copy.deepcopy(transitions[1][0])
            decision = next(o['node'] for o in c['operations']
                            if o['op'] == 'ADD' and o['node']['kind'] == 'Decision')
            decision['data']['statement'] += ' changed meaning'
            candidate = prepare(snapshots[1], c)['candidate']
            with self.subTest(domain=domain):
                self.assertNotEqual(PINS[domain][2], candidate['contentDigest'])
                self.assertNotEqual(canonical_bytes(snapshots[2]), canonical_bytes(candidate))


if __name__ == '__main__':
    unittest.main()
