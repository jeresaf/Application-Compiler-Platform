"""Run retained delivery gates with occurrence-scoped recovery assertions.

The historical fixture starts on 2026-10-08 and recovers at real wall time.
After another daily boundary, the scheduler correctly records later SKIPPED
occurrences too. Recovery must assert the original identity, not assume the
entire occurrence table has one row. Runtime and generated artifacts are
unchanged; every retained test still runs.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_delivery_job_components as components

original_source = components.delivery_source


def delivery_source(domain):
    source = original_source(domain)
    start = source.index('    @Test void jobCommittedThenLostResult')
    end = source.index('    @Test void actualDatabaseJobTimeout', start)
    method = source[start:end]
    before, recovery = method.split('time.fixed=new InvocationCore.SystemTime().now();', 1)
    for column in ('status', 'identity'):
        old = f'"SELECT {column} FROM acp_job_occurrence",String.class'
        new = f'"SELECT {column} FROM acp_job_occurrence WHERE identity=?",String.class,occurrence'
        assert recovery.count(old) == 1
        recovery = recovery.replace(old, new)
    recovery = recovery.replace(
        'assertEquals("COMPLETED",',
        'assertEquals(1,jdbc.queryForObject("SELECT count(*) FROM acp_job_occurrence WHERE status<>\'SKIPPED\'",Integer.class));assertEquals("COMPLETED",',
        1,
    )
    return source[:start] + before + 'time.fixed=new InvocationCore.SystemTime().now();' + recovery + source[end:]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-builds', action='store_true')
    args = parser.parse_args()
    components.delivery_source = delivery_source
    raise SystemExit(components.run(args.output, args.run_builds))
