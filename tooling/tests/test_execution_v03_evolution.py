"""Six-step Canonical 0.2 history/migration compatibility; not target closure.

Evolution authorities/backfills are explicit synthetic test witnesses. The
project's human approval is limited to the pinned initial reference snapshots.
"""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_json import load
from change_fixtures import STEPS, evolution_change, change, revise
from changes import genesis, request, ChangeError, rewrite
from compiler_contracts import Document, fingerprint
from execution_fixtures import DEST, evolution
from canonical_fixtures import synthetic_approved
from history_repository import HistoryRepository
from reference_authority import ReferenceAuthority
from target_migrations import plan_upgrade


def effect_meaning(snapshot):
    keys = {'Command': ('input', 'output', 'writeFields', 'assignments', 'outputBindings', 'eventBindings'),
            'UseCase': ('steps', 'input', 'output', 'outputBindings'),
            'ExecutionStep': ('operation', 'resource', 'inputBindings'),
            'Query': ('input', 'predicate', 'projection'), 'Filter': ('inputField',),
            'Job': ('inputBindings',), 'Transition': ('eventBindings',)}
    # Dependency revision closure is expected; semantic IDs and expressions are
    # the comparison here. Exact revision admission is verified by the journal.
    def stable(value):
        if isinstance(value, dict):
            if set(value) == {'id', 'revision'}:
                return {'id': value['id']}
            return {k: stable(v) for k, v in value.items()}
        return [stable(v) for v in value] if isinstance(value, list) else value
    return {n['id']: stable({k: n['data'][k] for k in keys[n['kind']]})
            for n in snapshot['content']['nodes'] if n['kind'] in keys}


class AcceptedTestHistory:
    def __init__(self, repository, bindings):
        self.repository, self.bindings = repository, bindings

    def read_accepted_plan(self, digest):
        for entry in self.repository.history():
            if entry['plan']['planDigest'] == digest:
                return Document.of(entry['plan'])
        raise PermissionError()

    def read_approved_bindings(self, digest, binding_digest):
        self.read_accepted_plan(digest)
        if fingerprint(self.bindings, 'migration-bindings') != binding_digest:
            raise PermissionError()
        return self.bindings


class ExecutionEvolutionTests(unittest.TestCase):
    def test_six_steps_preserve_explicit_effects_and_require_fresh_approval(self):
        for domain in ('payment', 'case-management'):
            source = load(DEST / (domain + '-authoring.json'))
            snapshot = load(DEST / (domain + '-canonical.json'))
            app = snapshot['content']['applicationId']
            grants = [app + ':' + s for s in ('SEMANTIC', 'SECURITY', 'MIGRATION', 'IRREVERSIBLE', 'LOCKED_DECISION')]
            auth = ReferenceAuthority(b'public-evolution-test-authority-key-only',
                {'author-session': 'author', 'review-session': 'test:independent-evolution-reviewer'},
                {'test:independent-evolution-reviewer': grants})
            original_effects = effect_meaning(snapshot)
            with tempfile.TemporaryDirectory() as temporary:
                repo = HistoryRepository(Path(temporary) / 'history.sqlite')
                historical, _ = evolution(domain)
                historical_source = synthetic_approved({'modelVersion': '0.2.0', 'applicationId': app, 'snapshotId': 'HISTORICAL',
                    'nodes': historical['content']['nodes'], 'issues': [], 'approvals': []})
                initial = genesis(historical_source, 'author')
                proof = auth.issue('review-session', request(initial), 1000)
                repo.bootstrap(initial, proof, auth, 1000, 'author-session')
                _, upgrade = evolution(domain, repo.head())
                upgrade_plan = repo.propose(upgrade, auth, 'author-session')
                repo.review(upgrade['id'], auth, 'author-session')
                proof = auth.issue('review-session', request(upgrade_plan), 1000)
                repo.approve(upgrade['id'], proof, auth, 1000)
                repo.apply(upgrade['id'], 'explicit-upgrade', auth, 1000)
                self.assertEqual(snapshot, repo.snapshot())
                for step in STEPS:
                    before = repo.snapshot()
                    proposal = evolution_change(before, repo.head(), step)
                    proposal.update(changeVersion='0.2.0', canonicalVersion='0.2.0')
                    plan = repo.propose(proposal, auth, 'author-session')
                    self.assertEqual('0.2.0', plan['planVersion'])
                    self.assertEqual('0.2.0', plan['candidate']['content']['schemaVersion'])
                    self.assertEqual(original_effects, effect_meaning(plan['candidate']), (domain, step))
                    repo.review(proposal['id'], auth, 'author-session')
                    with self.assertRaises(ChangeError):
                        repo.approve(proposal['id'], proof, auth, 1000)
                    proof = auth.issue('review-session', request(plan), 1000)
                    repo.approve(proposal['id'], proof, auth, 1000)
                    repo.apply(proposal['id'], step, auth, 1000)
                    bindings = Document.of({'requiredFieldBackfills': {'EVOLUTION-required-field': 'explicit reference backfill'}})
                    migration = plan_upgrade(Document.of(before), Document.of(repo.snapshot()), Document.of(plan), bindings,
                                             AcceptedTestHistory(repo, bindings)).read()
                    if step == 'optional-relationship':
                        self.assertIn('CREATE TABLE r_', migration['sql'])
                        self.assertIn('DEFERRABLE INITIALLY DEFERRED', migration['sql'])
                    elif step == 'required-field':
                        self.assertIn('explicit reference backfill'.encode().hex(), migration['sql'])
                        self.assertIn('SET NOT NULL', migration['sql'])
                    else:
                        self.assertEqual('', migration['sql'])
                self.assertEqual(historical, repo.snapshot(0))
                self.assertEqual(snapshot, repo.snapshot(1))
                self.assertEqual(7, repo.audit(authority=auth)['entries'])
                # A real operation-meaning change advances the semantic revision
                # and cannot inherit the prior exact-content/plan proof.
                before = repo.snapshot()
                command = next(n for n in before['content']['nodes'] if n['kind'] == 'Command')
                data = copy.deepcopy(command['data'])
                effect = copy.deepcopy(data['assignments'][0])
                effect['value'] = {'tag': 'literal', 'type': {'kind': 'String'}, 'value': 'explicitly revised effect'}
                data['assignments'].append(effect)
                proposal = change('CHANGE-EFFECT-MEANING', repo.head(), [revise(before, command['id'], data=data)])
                proposal.update(changeVersion='0.2.0', canonicalVersion='0.2.0')
                plan = repo.propose(proposal, auth, 'author-session')
                self.assertNotEqual(original_effects, effect_meaning(plan['candidate']))
                diff = next(d for d in plan['diff'] if d['id'] == command['id'])
                self.assertGreater(diff['after']['revision'], diff['before']['revision'])
                repo.review(proposal['id'], auth, 'author-session')
                with self.assertRaises(ChangeError):
                    repo.approve(proposal['id'], proof, auth, 1000)


if __name__ == '__main__':
    unittest.main()
