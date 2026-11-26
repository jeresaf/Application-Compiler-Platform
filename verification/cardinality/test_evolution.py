"""Synthetic accepted-history adapter checks for the cardinality candidate."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tooling'), str(ROOT / 'tooling/tests')]
from engineering.cardinality.successor import CardinalityCandidate
from test_canonical03_migrations import fixture


class CardinalityEvolutionTests(unittest.TestCase):
    def test_accepted_nullable_field_admitted(self):
        args = fixture(optional=True, nullable=True)
        result = CardinalityCandidate().plan_upgrade(*args).read()
        self.assertIn('ADD COLUMN', result['sql'])
        self.assertNotIn('UPDATE ', result['sql'])
        self.assertEqual(result['phase3PlanDigest'], args[2].read()['planDigest'])

    def test_guarded_bulk_backfill_rejected(self):
        with self.assertRaisesRegex(ValueError, 'CARDINALITY_UPGRADE_COORDINATED_BACKFILL_REQUIRED'):
            CardinalityCandidate().plan_upgrade(*fixture())

    def test_absent_accepted_history_still_rejected(self):
        class MissingHistory:
            def read_accepted_plan(self, digest):
                raise KeyError(digest)

        args = fixture(optional=True)
        with self.assertRaisesRegex(ValueError, 'UNACCEPTED_HISTORY'):
            CardinalityCandidate().plan_upgrade(*args[:-1], MissingHistory())
