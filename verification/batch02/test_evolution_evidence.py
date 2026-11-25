"""Reject substituted or incomplete R8 state and migration observations."""

import copy
from pathlib import Path
import tempfile
import unittest

from verification.batch02.verify_evolution import continuity, evidence_file, versions


class EvolutionEvidenceTests(unittest.TestCase):
    def test_reject_missing_or_modified_historical_migrations(self):
        old = [{'version': version, 'success': True} for version in (None, '1', '2', '3', '4')]
        fifth = {'version': '5', 'script': 'V5__integrity_jobs.sql', 'success': True}
        versions(old, [*old, fifth])
        cases = [old, [*old[:-1], fifth], [*old, {**fifth, 'success': False}],
                 [{**old[0], 'checksum': 1234}, *old[1:], fifth]]
        for candidate in cases:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                versions(old, candidate)

    def test_reject_loss_duplicate_and_modified_idempotency(self):
        old = {'acp_idempotency': [{'identity': 'abc', 'commit_ns': None,
                                   'status': 'COMMITTED_RESULT', 'result': 'original'}],
               'd_document': [{'id': 'd1', 'data': 'exact'}], 'audit': [{'id': 'a1'}]}
        after = copy.deepcopy(old)
        after['acp_idempotency'][0]['commit_ns'] = 123
        after['audit'].append({'id': 'a2'})
        self.assertEqual(continuity(old, after)['idempotencyKeys'], 1)
        for table, rows in (
            ('d_document', [{'id': 'd1', 'data': 'changed'}]),
            ('audit', [{'id': 'a2'}]),
            ('acp_idempotency', after['acp_idempotency'] * 2),
            ('acp_idempotency', [{**after['acp_idempotency'][0], 'result': 'changed'}]),
        ):
            with self.subTest(table=table, rows=rows), self.assertRaises(ValueError):
                continuity(old, {**after, table: rows})

    def test_reject_symbolic_and_escaping_evidence_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp).resolve()
            root = parent / 'observations'
            root.mkdir()
            (parent / 'outside').write_bytes(b'outside')
            (root / 'file').write_bytes(b'expected')
            (root / 'alias').symlink_to(root / 'file')
            self.assertEqual(evidence_file(root, 'file'), b'expected')
            for relative in ('../outside', 'alias', str(root / 'file'), 'missing'):
                with self.subTest(path=relative), self.assertRaisesRegex(ValueError, 'EVIDENCE_PATH'):
                    evidence_file(root, relative)
