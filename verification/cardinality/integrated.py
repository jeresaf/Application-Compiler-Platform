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
sys.path[:0] = [str(ROOT), str(ROOT / 'tooling'), str(ROOT / 'tooling/tests')]
from engineering.cardinality.successor import MIGRATION
from engineering.cardinality.participation import MIGRATION as PARTICIPATION
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


def raw_lock(tenant='tenant-one'):
    return f"""SELECT pg_advisory_xact_lock((k >> 32)::int, (k & 4294967295)::bit(32)::int)
               FROM (SELECT acp_cardinality_key('{tenant}'::bytea) AS k) AS key;"""


def lock(tenant='tenant-one'):
    return f"SELECT acp_cardinality_enter('{tenant}'::bytea);"


def recover_interrupted_migration(container, schema, sql, expected_absent):
    with session(container, schema) as (send, receive):
        send('SELECT pg_backend_pid();')
        pid = int(receive().strip())
        send('BEGIN;\n' + sql)
        assert 'ERROR' not in receive(), 'MIGRATION_INTERRUPTION_SETUP'
        assert execute(container, f'SELECT pg_terminate_backend({pid}, 5000);') == 't'
    assert execute(container, f'SELECT {expected_absent};') == 't'
    execute(container, f'SET search_path={schema};\n' + sql)


def verify_payment_backfill(container, schema):
    # The test history is synthetic. It exercises the exact accepted-plan
    # port and SQL path without enrolling authority.
    from compiler_contracts import Document
    from engineering.cardinality.successor import CardinalityCandidate
    from test_canonical03_migrations import fixture
    from test_target_migrations import FixtureAcceptedHistory

    previous, current, plan, bindings, _ = fixture()
    approved = Document.of({**bindings.read(), 'cardinalityBackfillTenant': 'tenant-one'})
    migration_plan = CardinalityCandidate().plan_upgrade(
        previous, current, plan, approved, FixtureAcceptedHistory(plan, approved),
    ).read()
    try:
        execute(container, f'SET search_path={schema};\n' + migration_plan['sql'])
    except subprocess.CalledProcessError as error:
        import re
        state = re.search(r'ERROR:\s+([0-9A-Z]{5}):', error.output)
        raise ValueError('COORDINATED_BACKFILL_' + (state[1] if state else 'EXECUTION_FAILED')) from None
    field_node = next(node for node in current.read()['content']['nodes']
                      if node['id'] == 'EVOLUTION-required-field')
    table = symbol(field_node['data']['owner']['id'], 'e')
    field = symbol(field_node['id'], 'f')
    expected = approved.read()['requiredFieldBackfills']['EVOLUTION-required-field'].encode().hex()
    rows = execute(container, f"SET search_path={schema}; SELECT encode({field},'hex') FROM {table};")
    assert rows.splitlines() == [expected], 'COORDINATED_BACKFILL_BYTES'
    return True


def exercise(container, schema, project, domain, corrected):
    migrations = sorted((project / 'database').glob('V*.sql'))
    historic = [path for path in migrations if path.name not in (MIGRATION, PARTICIPATION)]
    seed = seed_sql(domain)
    seed += [sql.replace("'fixture-resource'", "'second-resource'") for sql in seed[2:]]
    execute(container, f'CREATE SCHEMA {schema}; SET search_path={schema};\n'
            + '\n'.join(path.read_text() for path in historic)
            + '\n'.join(sql + ';' for sql in seed))
    if corrected:
        v10 = (project / 'database' / MIGRATION).read_text()
        if domain == 'payment':
            edge = symbol('REL-MEMBER-PAYMENT', 'r')
            # Corrupt only the disposable pre-upgrade database to exercise
            # discovery of an invalid retained row.
            execute(container, f"SET search_path={schema}; ALTER TABLE {edge} DISABLE TRIGGER USER; "
                               f"DELETE FROM {edge} WHERE target_id='fixture-resource'; "
                               f"ALTER TABLE {edge} ENABLE TRIGGER USER;")
            with session(container, schema) as (send, receive):
                send('BEGIN;\n' + v10)
                assert '23514' in receive(), 'V10_INVALID_RETAINED_STATE_ACCEPTED'
                send('ROLLBACK;')
                receive()
            assert execute(container, f"SELECT to_regprocedure('{schema}.acp_cardinality_key(bytea)') IS NULL;") == 't'
            execute(container, f'SET search_path={schema}; ' + seed_sql(domain)[-1] + ';')
        recover_interrupted_migration(container, schema, v10,
                                      f"to_regprocedure('{schema}.acp_cardinality_key(bytea)') IS NULL")
        recover_interrupted_migration(container, schema, (project / 'database' / PARTICIPATION).read_text(),
                                      f"to_regclass('{schema}.acp_cardinality_participation') IS NULL")
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
            send('BEGIN;' + raw_lock() + update('fixture-resource'))
            assert '55000' in receive(), 'ADVISORY_LOCK_ALONE_ACCEPTED'
            send('ROLLBACK;')
            receive()

    if corrected:
        writer = schema + '_writer'
        retired = schema + '_retired'
        execute(container, f"""
            CREATE ROLE {writer} NOLOGIN;
            CREATE ROLE {retired} NOLOGIN;
            GRANT USAGE ON SCHEMA {schema} TO {writer}, {retired};
            GRANT SELECT, UPDATE ON {schema}.{table} TO {writer}, {retired};
            GRANT EXECUTE ON FUNCTION {schema}.acp_cardinality_enter(bytea) TO {writer};
        """)
        with session(container, schema) as (send, receive):
            send(f'SET ROLE {writer}; UPDATE acp_cardinality_participation SET transaction_id=pg_current_xact_id();')
            assert '42501' in receive(), 'WRITER_CAN_FORGE_PARTICIPATION'
            send('BEGIN; ' + lock() + update('fixture-resource') + 'ROLLBACK;')
            assert 'ERROR' not in receive(), 'PERMITTED_WRITER_FAILED'
            send(f'RESET ROLE; SET ROLE {retired}; SELECT 1;')
            assert 'ERROR' not in receive()
            # Revocation takes effect on this already-established session as
            # well as any future connection. The role has no inherited grants.
            execute(container, f'REVOKE SELECT, UPDATE ON {schema}.{table} FROM {retired};')
            send(update('fixture-resource'))
            assert '42501' in receive(), 'RETIRED_WRITER_STILL_HAS_ACCESS'

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
            with session(container, schema) as (independent, independent_read):
                independent("BEGIN; SET LOCAL statement_timeout='1s';" + lock('tenant-two')
                            + lock('tenant-two') + 'ROLLBACK;')
                assert 'ERROR' not in independent_read(), 'UNRELATED_TENANT_BLOCKED'
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
    if corrected:
        assert execute(container, f'SET search_path={schema}; SELECT count(*) FROM acp_cardinality_participation;') == '1'
    return {'committedWrites': count, 'deadlocks': 0 if corrected else 1,
            **({'v10InterruptionRolledBack': True, 'v11InterruptionRolledBack': True,
                'independentTenantProgress': True, 'participationRows': 1, 'writerRoleQualified': True,
                'retiredRoleRejected': True, 'advisoryOnlyRejected': True,
                'invalidRetainedStateRejected': domain == 'payment',
                'coordinatedBackfillVerified': verify_payment_backfill(container, schema)
                if domain == 'payment' else None} if corrected else {})}


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
