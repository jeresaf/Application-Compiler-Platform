"""Closed laboratory companion contracts. Parsing conveys no authority."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from jsonschema import Draft202012Validator, FormatChecker
from engineering.evidence_admission.encoding import canonicalize, parse_canonical, utf16_key

SCHEMAS = Path(__file__).with_name('schemas')
MAX_TOTAL = 256 * 1024 * 1024


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def time(value):
    return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)


def unique(rows, key, reason):
    keys = [key(row) for row in rows]
    require(len(keys) == len(set(keys)), reason)


def parse(raw, schema='evaluation-manifest'):
    require(type(raw) is bytes and len(raw) <= 1024 * 1024, 'MANIFEST_SIZE_OR_TYPE')
    value = parse_canonical(raw)
    definition = json.loads((SCHEMAS / (schema + '.schema.json')).read_bytes())
    Draft202012Validator.check_schema(definition)
    errors = list(Draft202012Validator(definition, format_checker=FormatChecker()).iter_errors(value))
    require(not errors, 'CLOSED_SCHEMA:' + (errors[0].json_path if errors else ''))
    return value


def digest(raw):
    return sha(b'ACP-PHASE6-EVALUATION-MANIFEST\0' + raw)


def path(value):
    require(type(value) is str and len(value) <= 512 and re.fullmatch(
        r'(?:[A-Za-z0-9_-][A-Za-z0-9._-]*/)*[A-Za-z0-9_-][A-Za-z0-9._-]*', value), 'UNSAFE_PATH')
    require(all(p not in ('.', '..') and not p.endswith('.') for p in value.split('/')), 'UNSAFE_PATH')
    return value


def manifest(raw):
    value = parse(raw)
    require((value['purpose'] == 'CANDIDATE_QUALIFICATION') ==
            (value['release']['kind'] == 'UNSEALED_CANDIDATE'), 'RELEASE_PURPOSE_MISMATCH')
    unique(value['applications'], lambda x: x['application'], 'DUPLICATE_APPLICATION')
    unique(value['executions'], lambda x: x['executionId'], 'DUPLICATE_EXECUTION')
    unique(value['criteria'], lambda x: x['criterion'], 'DUPLICATE_CRITERION')
    unique(value['artifacts'], lambda x: path(x['path']).casefold(), 'AMBIGUOUS_ARTIFACT_PATH')
    require(sum(a['size'] for a in value['artifacts']) <= MAX_TOTAL, 'ARTIFACT_TOTAL_LIMIT')
    require(time(value['createdAt']) < time(value['expiresAt']), 'MANIFEST_TIME_ORDER')
    for rows,key in ((value['applications'],lambda a:a['application']), (value['executions'],lambda e:e['executionId']), (value['criteria'],lambda c:c['criterion']), (value['artifacts'],lambda a:a['path'])):
        keys=[key(r) for r in rows]
        ordered=sorted(keys,key=utf16_key) if keys and isinstance(keys[0],str) else sorted(keys)
        require(keys==ordered,'NONCANONICAL_SET_ORDER')
    paths = {a['path'] for a in value['artifacts']}
    apps = {a['application'] for a in value['applications']}
    executions = {e['executionId'] for e in value['executions']}
    require(value['applicationSource']['inventory'] in paths, 'MISSING_SOURCE_INVENTORY')
    for execution in value['executions']:
        require(time(execution['startedAt']) <= time(execution['finishedAt']) <= time(value['createdAt']), 'EXECUTION_TIME_ORDER')
    for c in value['criteria']:
        require(set(c['applicationScope']) <= apps, 'UNRELATED_APPLICATION')
        require(set(c['artifactPaths']) <= paths, 'MISSING_ARTIFACT_REFERENCE')
        unique(c['witnesses'], lambda w: (w['application'], w['witnessId'], w['caseId'], w['executionId']), 'DUPLICATE_WITNESS')
        if c['evidenceKind'] != 'HUMAN_REVIEW':
            require(c['registrationRef'] is not None and c['witnesses'], 'MISSING_AUTOMATED_WITNESS')
        for w in c['witnesses']:
            require(w['application'] in c['applicationScope'] and w['executionId'] in executions, 'UNRELATED_WITNESS')
            require(set(w['assertionArtifactPaths']) <= paths, 'MISSING_ASSERTION_ARTIFACT')
    return value
