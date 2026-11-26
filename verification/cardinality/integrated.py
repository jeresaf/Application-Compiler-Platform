"""Exercise exact generated migrations and concurrent writes in owned PostgreSQL."""
import argparse
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tooling')]
from engineering.cardinality.successor import MIGRATION
from engineering.generator_builds.runtime import database
from engineering.recovery.qualify import authenticated_database_ready
from phase6_reference_tests import seed_sql, symbol


def command(container):
    return ['docker', 'exec', '-i', container, 'sh', '-c', 'exec psql "$@" 2>&1', 'psql', '-X', '-Atq',
            '-v', 'VERBOSITY=verbose', '-U', 'acp_runtime']


@contextmanager
def session(container, schema):
    process = subprocess.Popen(command(container), stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        buffer = bytearray()

        def send(sql):
            process.stdin.write((sql + '\n\\echo ACP_BARRIER\n').encode())

        def receive():
            deadline = time.monotonic() + 25
            marker = b'ACP_BARRIER\n'
            while marker not in buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise TimeoutError('CARDINALITY_DATABASE_BARRIER')
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    raise RuntimeError('CARDINALITY_DATABASE_SESSION_CLOSED')
                buffer.extend(data)
            index = buffer.index(marker)
            reply = buffer[:index].decode()
            del buffer[:index + len(marker)]
            return reply

        try:
            send(f"SET search_path={schema}; SET statement_timeout='20s';")
            assert not receive()
            yield send, receive
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=25)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdout.close()


def execute(container, sql):
    return subprocess.check_output(command(container) + ['-v', 'ON_ERROR_STOP=1', '-1'],
                                   input=sql, text=True, timeout=90).strip()


def lock(tenant='tenant-one'):
    return f"""SELECT pg_advisory_xact_lock((k >> 32)::int, (k & 4294967295)::bit(32)::int)
               FROM (SELECT acp_cardinality_key('{tenant}'::bytea) AS k) AS key;"""


def exercise(container, schema, project, domain, corrected):
    migrations = sorted((project / 'database').glob('V*.sql'))
    historic = [path for path in migrations if path.name != MIGRATION]
    seed = seed_sql(domain)
    seed += [sql.replace("'fixture-resource'", "'second-resource'") for sql in seed[2:]]
    execute(container, f'CREATE SCHEMA {schema}; SET search_path={schema};\n'
            + '\n'.join(path.read_text() for path in historic)
            + '\n'.join(sql + ';' for sql in seed))
    if corrected:
        execute(container, f'SET search_path={schema};\n' + (project / 'database' / MIGRATION).read_text())
    table = symbol('ENT-PAYMENT' if domain == 'payment' else 'CASE', 'e')
    identity = symbol('FLD-PAYMENT-ID' if domain == 'payment' else 'CASE-ID', 'f')
    summary = symbol('FLD-TASK-SUMMARY', 'f')

    def update(resource):
        return f"UPDATE {table} SET {summary}='updated' WHERE {identity}='{resource}';"

    if corrected:
        with session(container, schema) as (send, receive):
            send(update('fixture-resource'))
            reply = receive()
            assert '55000' in reply, 'UNCOORDINATED_WRITER_NOT_REJECTED_AS_EXPECTED'

    with ExitStack() as peers:
        first, first_read = peers.enter_context(session(container, schema))
        second, second_read = peers.enter_context(session(container, schema))
        first("BEGIN; " + (lock() if corrected else '') + update('fixture-resource'))
        assert 'ERROR' not in first_read()
        second("BEGIN; " + (lock() if corrected else '') + update('second-resource'))
        if corrected:
            deadline = time.monotonic() + 10
            while execute(container, "SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND objsubid=2 AND NOT granted;") != '1':
                if time.monotonic() >= deadline:
                    raise TimeoutError('COORDINATION_WAITER_NOT_OBSERVED')
            first('COMMIT;')
            left = first_read()
            assert 'ERROR' not in second_read()
            second('COMMIT;')
            right = second_read()
            assert 'ERROR' not in left + right
        else:
            assert 'ERROR' not in second_read()
            first('COMMIT;')
            second('COMMIT;')
            left, right = first_read(), second_read()
            assert sum('40P01' in result for result in (left, right)) == 1
            assert sum('ERROR' in result for result in (left, right)) == 1
    count = int(execute(container, f"SET search_path={schema}; SELECT count(*) FROM {table} WHERE {summary}='updated';"))
    assert count == (2 if corrected else 1)
    return {'committedWrites': count, 'deadlocks': 0 if corrected else 1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('generated', type=Path)
    args = parser.parse_args()
    with database() as container:
        authenticated_database_ready(container, os.environ['ACP_TEST_DATABASE_PASSWORD'])
        results = {}
        for index, domain in enumerate(('payment', 'case-management')):
            project = args.generated / domain
            results[domain] = {
                'baseline': exercise(container, f'baseline_{index}', project, domain, False),
                'successor': exercise(container, f'successor_{index}', project, domain, True),
            }
    print(json.dumps(results, sort_keys=True))


if __name__ == '__main__':
    main()
