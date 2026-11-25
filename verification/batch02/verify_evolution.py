"""Independently reconcile retained R8 laboratory database and source evidence."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

REPOSITORY = Path(__file__).resolve().parents[2]


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()


def evidence_file(root, relative):
    logical = PurePosixPath(relative)
    require(not logical.is_absolute() and bool(logical.parts) and '..' not in logical.parts,
            'EVIDENCE_PATH')
    path = root / logical
    require(path.resolve() == path and path.is_file(),
            'EVIDENCE_PATH')
    return path.read_bytes()


def versions(before, after):
    require([row['version'] for row in before] == [None, '1', '2', '3', '4']
            and all(row['success'] is True for row in before), 'HISTORICAL_MIGRATIONS')
    require(len(after) == len(before) + 1 and after[:-1] == before, 'MIGRATION_PREFIX')
    final = after[-1]
    require(final['version'] == '5' and final['script'] == 'V5__integrity_jobs.sql'
            and final['success'] is True, 'MIGRATION_SUCCESSOR')


def continuity(before, after):
    require(set(before) <= set(after), 'MISSING_TABLE')
    documents = [name for name in before if name.startswith('d_') and not name.endswith('_audit')]
    require(documents and all(before[name] == after[name] for name in documents), 'DOCUMENT_BYTES')
    for table, rows in before.items():
        if table in ('acp_idempotency', 'flyway_schema_history'):
            continue
        old = Counter(encode(row) for row in rows)
        new = Counter(encode(row) for row in after[table])
        require(old <= new, 'LOST_ROW:' + table)
    old = {row['identity']: row for row in before['acp_idempotency']}
    new = {row['identity']: row for row in after['acp_idempotency']}
    require(len(old) == len(before['acp_idempotency'])
            and len(new) == len(after['acp_idempotency']) and new.keys() == old.keys(),
            'IDEMPOTENCY_INVENTORY')
    for key, row in old.items():
        observed = new[key]
        if row['commit_ns'] is None and row['status'] == 'COMMITTED_RESULT':
            # Timestamp enrichment is independently checked by the actual R8
            # PostgreSQL oracle. This comparison checks retained business state.
            observed = {**observed, 'commit_ns': None}
        require(row == observed, 'IDEMPOTENCY_BUSINESS_STATE')
    return {'historicalTables': len(before), 'documentTables': len(documents),
            'idempotencyKeys': len(old)}


def verify(root, source):
    root = root.resolve()

    def read(relative):
        return json.loads(evidence_file(root, relative))

    record = read('result.json')
    require(record['sourceCommit'] == source, 'SOURCE_COMMIT')
    require(record['scope'] == 'QUALIFICATION_ONLY'
            and record['semanticApproval'] == 'NOT_APPROVED'
            and record['acceptedHistory'] == 'NOT_CONSTRUCTED'
            and record['releaseDisposition'] == 'PHASE6_RELEASE_CLOSURE_BLOCKED', 'EVIDENCE_SCOPE')
    observation = read('execution-observation.json')
    require(observation['sourceSHA256'] == record['sourceSHA256']
            and observation['scope'] == record['scope']
            and observation['semanticApproval'] == record['semanticApproval']
            and observation['candidateDigest'] == record['afterCandidate'], 'OBSERVATION_BINDING')
    require(len(source) == 40 and all(char in '0123456789abcdef' for char in source), 'SOURCE_FORMAT')
    sources = subprocess.check_output(
        ['git', 'ls-tree', '-r', '--name-only', source, '--', 'engineering/application_evolution'],
        cwd=REPOSITORY, text=True).splitlines()
    expected_sources = {name for name in sources if name.endswith(('.py', '/journey.ts'))}
    require(expected_sources and set(observation['sourceSHA256']) == expected_sources, 'SOURCE_INVENTORY')
    for name, pin in observation['sourceSHA256'].items():
        historical = subprocess.check_output(['git', 'show', f'{source}:{name}'], cwd=REPOSITORY)
        require(sha(historical) == pin, 'SOURCE_BYTES')
    require(record['executorSHA256'] == observation['sourceSHA256']['engineering/application_evolution/run.py'],
            'EXECUTOR_BINDING')
    required = {'before.json', 'after.json', 'evolution-plan.json', 'capture-manifest.json',
                'r6-database/migration-history.json', 'r7-database/migration-history.json',
                'restore/result.json', 'successor-committed.json', 'successor-replayed.json'}
    files = observation['files']
    require(required <= set(files), 'MISSING_EVIDENCE')
    for name, pin in files.items():
        require(sha(evidence_file(root, name)) == pin, 'EVIDENCE_HASH')
    plan = read('evolution-plan.json')
    require(plan['planDigest'] == record['planDigest'] and plan['changeDigest'] == record['changeDigest']
            and plan['change']['base'] == record['beforeCandidate']
            and plan['change']['candidate'] == record['afterCandidate'], 'PLAN_BINDING')
    migration = record['migration']
    old, new = read('r6-database/migration-history.json'), read('r7-database/migration-history.json')
    versions(old, new)
    require((migration['before'], migration['after']) == (old, new)
            and migration['sourceDatabase'] == migration['targetDatabase'], 'DATABASE_BINDING')
    restore = read('restore/result.json')
    capture = read('capture-manifest.json')
    require(restore == record['restore'] and restore['originalCaptureSHA256'] == capture['files']
            and restore['databaseIdentity']['systemIdentifier'] != migration['sourceDatabase']['systemIdentifier']
            and restore['exactRowsBeforeMigration'] is True and restore['auditAndIdempotencyExact'] is True
            and restore['cleanup'] == 'OWN_NEW_DATABASE_REMOVED', 'RESTORE_BINDING')
    for name, pin in capture['files'].items():
        require(sha(evidence_file(root, 'r6-database/' + name)) == pin, 'RESTORE_CAPTURE_HASH')
    before, after = read('before.json'), read('after.json')
    require(sha(encode(before)) == capture['stateDigest'], 'BASE_POPULATION_BINDING')
    preserved = continuity(before, after)
    writes = record['successorWrites']
    require(sha(encode(read('successor-committed.json'))) == writes['beforeRestartDigest']
            and sha(encode(read('successor-replayed.json'))) == writes['afterRestartDigest'],
            'RESTART_POPULATION_BINDING')
    compatibility = record['compatibility']
    require(compatibility['policy'] == 'CONTROLLED_STOP_MIGRATE_RESTART'
            and compatibility['olderWriter'] == 'FENCED_REAL_OLD_BINARY_STARTUP_REJECTED'
            and compatibility['zeroDowntime'] == 'NOT_CLAIMED', 'WRITER_SCOPE')
    require(record['faults']['interruptedMigration']['rollbackObserved'] is True
            and record['faults']['failedMigration']['exit'] != 0, 'FAILURE_EVIDENCE')
    browser = [read(name)['stats'] for name in sorted(files) if name.endswith('-browser.json')]
    require(len(browser) == 9 and all(row['expected'] == 1
            and row['unexpected'] == row['skipped'] == row['flaky'] == 0 for row in browser),
            'BROWSER_EVIDENCE')
    require(record['cleanup'] == {'database': 'REMOVED', 'processes': 'REAPED'}, 'CLEANUP_RECORD')
    return {'sourceCommit': source, 'scope': 'QUALIFICATION_ONLY', 'actualMigrationVersion': '5',
            'retainedBrowserJourneys': len(browser), 'preserved': preserved,
            'observationSHA256': sha(evidence_file(root, 'execution-observation.json')),
            'resultSHA256': sha(evidence_file(root, 'result.json')),
            'releaseDisposition': record['releaseDisposition']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.workspace, args.source)
    with args.output.open('xb') as stream:
        stream.write(encode(result))


if __name__ == '__main__':
    main()
