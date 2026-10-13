"""Compare completed Actions API observations without changing repository evidence."""
from datetime import datetime
import json
from pathlib import Path
import sys


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def observation(directory):
    root = Path(directory)
    run = json.loads((root/'ci-run.json').read_text())
    jobs = json.loads((root/'ci-jobs.json').read_text())['jobs']
    if run['status'] != 'completed' or any(j['status'] != 'completed' for j in jobs):
        raise ValueError('MEASUREMENT_REQUIRES_COMPLETED_RUN')
    rows = []
    for job in jobs:
        steps = [{'name': s['name'], 'seconds': (stamp(s['completed_at'])-stamp(s['started_at'])).total_seconds()} for s in job.get('steps', []) if s.get('started_at') and s.get('completed_at')]
        setup = [s for s in steps if s['name'].startswith(('Set up', 'Run actions/setup-', 'Run actions/checkout', 'Initialize containers', 'Install ', 'Enable authoritative'))]
        rows.append({'name': job['name'], 'conclusion': job['conclusion'], 'start': job['started_at'], 'end': job['completed_at'],
                     'seconds': (stamp(job['completed_at'])-stamp(job['started_at'])).total_seconds(), 'setupSeconds': sum(s['seconds'] for s in setup), 'steps': steps})
    end = max(stamp(j['completed_at']) for j in jobs)
    durations = {j['name']: j['seconds'] for j in rows}
    optimized = 'final-ci-aggregate' in durations
    dependencies = {'contracts': (), 'phase5-experiments': (), 'phase5c-hard-gates': ('contracts', 'phase5-experiments'),
                    'phase6-target': ('contracts', 'phase5c-hard-gates'),
                    'phase6-closure-audit': ('contracts', 'phase5c-hard-gates') if optimized else ('contracts', 'phase5c-hard-gates', 'phase6-target')}
    if optimized: dependencies['final-ci-aggregate'] = tuple(dependencies)
    def finish(name):
        return durations[name]+max((finish(parent) for parent in dependencies[name]), default=0)
    critical = max(finish(name) for name in dependencies) if set(dependencies) <= set(durations) else None
    return {'source': run['head_sha'], 'run': run['id'], 'conclusion': run['conclusion'], 'jobs': rows,
            'wallSeconds': (end-stamp(run['created_at'])).total_seconds(),
            'dagCriticalPathSeconds': critical,
            'runnerMinutes': sum(j['seconds'] for j in rows)/60,
            'setupSeconds': sum(j['setupSeconds'] for j in rows),
            'measurement': 'Workflow creation through last job completion; queue gaps included. DAG critical path sums job durations without queue gaps. Runner time is sum of job durations, not billing rounding. Setup classification is listed explicitly.'}


def compare(old, new):
    saved = old['wallSeconds']-new['wallSeconds']
    return {'baseline': old, 'optimized': new, 'secondsSaved': saved,
            'wallImprovementPercent': 100*saved/old['wallSeconds'],
            'runnerMinuteDelta': new['runnerMinutes']-old['runnerMinutes']}


if __name__ == '__main__':
    if len(sys.argv) != 3: raise SystemExit('usage: measure.py BASELINE_API_DIRECTORY OPTIMIZED_API_DIRECTORY')
    print(json.dumps(compare(observation(sys.argv[1]), observation(sys.argv[2])), indent=2))
