"""Retain the complete native privacy gate, with one scoped test-fixture correction."""
from contextlib import contextmanager
from pathlib import Path
import runpy
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tooling'), str(ROOT / 'tooling/tests')]
import privacy_lifecycle_reference_tests
from engineering.generator_builds.privacy_fixture import source


@contextmanager
def corrected_fixture():
    original = privacy_lifecycle_reference_tests.source
    privacy_lifecycle_reference_tests.source = source
    try:
        yield
    finally:
        privacy_lifecycle_reference_tests.source = original


if __name__ == '__main__':
    entrypoint = ROOT / 'tooling/tests/phase6_gates.py'
    sys.argv.insert(1, 'privacy')
    sys.argv[0] = str(entrypoint)
    with corrected_fixture():
        runpy.run_path(str(entrypoint), run_name='__main__')
