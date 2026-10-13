"""Additive developer feedback. Hosted full admission remains mandatory."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PYTHON = str(ROOT/'.venv/bin/python3.14')
ROUTE = str(ROOT/'engineering/route_a_gateway/.venv/bin/python3.14')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('group', choices=('integrity', 'route-a', 'compiler', 'modules', 'full-local'))
    parser.add_argument('modules', nargs='*', help='Explicit tooling.tests.* or verification.* unittest modules')
    args = parser.parse_args()
    integrity = [[PYTHON, '-m', 'pip', 'check'], [PYTHON, 'tooling/check_repository.py'], [PYTHON, 'tooling/check_target_release.py'], [PYTHON, 'tooling/package_target_tzdb.py', '--check'],
                 ['node', 'tooling/check_canonical_vectors.mjs'],
                 ['node', 'tooling/check_canonical_vectors.mjs', 'test-corpus/execution-v03'],
                 ['node', 'tooling/check_canonical_vectors.mjs', 'test-corpus/deterministic-v04'],
                 [PYTHON, '-m', 'unittest', 'discover', '-s', 'verification/ci', '-v']]
    route = [[ROUTE, '-m', 'unittest', 'discover', '-s', 'verification/route_a', '-v']]
    compiler = [[PYTHON, '-m', 'unittest', 'discover', '-s', 'tooling/tests', '-v']]
    if args.group == 'modules':
        if not args.modules or any(not m.startswith(('tooling.tests.', 'verification.')) or not all(c.isalnum() or c in '._' for c in m) for m in args.modules):
            parser.error('supply explicit tooling.tests.* or verification.* modules')
        commands = [[ROUTE, '-m', 'unittest', *args.modules, '-v']]
    else:
        if args.modules: parser.error('module arguments require modules group')
        commands = {'integrity': integrity, 'route-a': route, 'compiler': compiler, 'full-local': integrity+compiler+route}[args.group]
    print('FOCUSED_CHECKS_ONLY — local feedback; not hosted release admission', flush=True)
    try:
        for command in commands:
            subprocess.run(command, cwd=ROOT, check=True)
    finally:
        print('FOCUSED_CHECKS_ONLY — hosted full verification and closure remain required', flush=True)


if __name__ == '__main__': main()
