import json
from pathlib import Path
import tempfile
import unittest
from engineering.ci.measure import observation, compare


class MeasurementTests(unittest.TestCase):
    def test_overlapping_jobs_distinguish_wall_and_runner_time(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = {'id': 1, 'head_sha': 'a'*40, 'status': 'completed', 'conclusion': 'failure', 'created_at': '2026-10-13T00:00:00Z'}
            jobs = [{'name': name, 'status': 'completed', 'conclusion': result, 'started_at': '2026-10-13T00:00:10Z', 'completed_at': '2026-10-13T00:01:10Z', 'steps': []} for name, result in [('target','success'),('closure','failure')]]
            (root/'ci-run.json').write_text(json.dumps(run))
            (root/'ci-jobs.json').write_text(json.dumps({'jobs': jobs}))
            value = observation(root)
            self.assertEqual(value['wallSeconds'], 70)
            self.assertEqual(value['runnerMinutes'], 2)
            self.assertEqual(value['conclusion'], 'failure')
            run['status'] = 'in_progress'
            (root/'ci-run.json').write_text(json.dumps(run))
            with self.assertRaisesRegex(ValueError, 'COMPLETED_RUN'): observation(root)

    def test_faster_wall_time_can_cost_more_runner_time(self):
        value = compare({'wallSeconds': 100, 'runnerMinutes': 2}, {'wallSeconds': 70, 'runnerMinutes': 3})
        self.assertEqual(value['secondsSaved'], 30)
        self.assertEqual(value['wallImprovementPercent'], 30)
        self.assertEqual(value['runnerMinuteDelta'], 1)

    def test_dependency_change_reduces_critical_path_without_removing_work(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'ci-run.json').write_text(json.dumps({'id': 1, 'head_sha': 'a'*40, 'status': 'completed', 'conclusion': 'failure', 'created_at': '2026-10-13T00:00:00Z'}))
            names = ['contracts', 'phase5-experiments', 'phase5c-hard-gates', 'phase6-target', 'phase6-closure-audit']
            jobs = [{'name': n, 'status': 'completed', 'conclusion': 'success', 'started_at': '2026-10-13T00:00:00Z', 'completed_at': '2026-10-13T00:01:00Z', 'steps': []} for n in names]
            (root/'ci-jobs.json').write_text(json.dumps({'jobs': jobs}))
            old = observation(root)
            self.assertEqual(old['dagCriticalPathSeconds'], 240)
            jobs.append({'name': 'final-ci-aggregate', 'status': 'completed', 'conclusion': 'failure', 'started_at': '2026-10-13T00:00:00Z', 'completed_at': '2026-10-13T00:00:05Z', 'steps': []})
            (root/'ci-jobs.json').write_text(json.dumps({'jobs': jobs}))
            new = observation(root)
            self.assertEqual(new['dagCriticalPathSeconds'], 185)
            self.assertGreater(new['runnerMinutes'], old['runnerMinutes'])
