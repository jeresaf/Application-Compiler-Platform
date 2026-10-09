"""Apply the dated delivery-fixture compatibility adapter to retained gates.

Keep the sealed generator, runtime and original gate implementations intact.
All original CLI validation and gate assertions run through their entrypoints.
"""
from pathlib import Path
import runpy
import sys

from delivery_components import delivery_source
import delivery_job_reference_tests

ENTRYPOINTS = {
    'target': 'check_phase6_target.py',
    'privacy': 'check_privacy_lifecycle_components.py',
}

if __name__ == '__main__':
    mode = sys.argv.pop(1)
    entrypoint = Path(__file__).resolve().parents[1] / ENTRYPOINTS[mode]
    delivery_job_reference_tests.source = delivery_source
    sys.argv[0] = str(entrypoint)
    runpy.run_path(str(entrypoint), run_name='__main__')
