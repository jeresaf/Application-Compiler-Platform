"""Read-only source inspection and laboratory registration authentication.

No verifier entrypoint is executed; no activation, journal, admission or human
deployment decision is produced. Git is used only for built-in object reads.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess

from .encoding import canonicalize, parse_canonical, payload_digest, utf16_key
from .validation import validate_structure
from .signatures import require, utc, verify_record_signatures
from .trust import LabTrustContext, check_revocation, verify_lab_policy

REGISTRATION_SCHEMA = 'acp-phase6-evidence/verifier-registration/1'
SOURCE_DOMAIN = b'ACP-PHASE6-VERIFIER-SOURCE\0'
REVIEW_DOMAIN = b'ACP-PHASE6-REGISTRATION-REVIEW-SUBJECT\0'


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def valid_path(value):
    return type(value) is str and len(value) <= 512 and re.fullmatch(
        r'(?:[A-Za-z0-9_-][A-Za-z0-9._-]*/)*[A-Za-z0-9_-][A-Za-z0-9._-]*', value) is not None


def source_inventory(root):
    """Inventory actual regular files; Git metadata is not verifier source."""
    root = Path(root)
    require(root.is_absolute() and '..' not in root.parts and root.is_dir() and not root.is_symlink(), 'INVALID_SOURCE_ROOT')
    require(not any(p.is_symlink() for p in root.parents), 'SYMLINK_SOURCE_PARENT')
    entries = []
    total = 0
    def unreadable(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=unreadable):
        for name in list(dirs):
            path = Path(directory) / name
            require(not path.is_symlink(), 'SYMLINK_SOURCE_DIRECTORY')
            if path == root / '.git':
                dirs.remove(name)
        for name in files:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            require(valid_path(relative), 'INVALID_SOURCE_PATH')
            mode = path.lstat().st_mode
            require(stat.S_ISREG(mode) and not path.is_symlink(), 'NONREGULAR_SOURCE_FILE')
            size = path.stat().st_size
            total += size
            require(total <= 8 * 1024 * 1024 and len(entries) < 4096, 'SOURCE_INVENTORY_LIMIT')
            raw = path.read_bytes()
            require(len(raw) == size, 'SOURCE_CHANGED_DURING_READ')
            entries.append({'path': relative, 'mode': format(stat.S_IMODE(mode), '04o'),
                            'size': size, 'sha256': sha(raw)})
    entries.sort(key=lambda e: utf16_key(e['path']))
    return canonicalize({'schema': 'acp-phase6-verifier-source/1', 'files': entries})


def source_tree_digest(inventory):
    value = parse_canonical(inventory)
    require(type(value) is dict and set(value) == {'schema', 'files'} and
            value['schema'] == 'acp-phase6-verifier-source/1' and type(value['files']) is list, 'INVALID_SOURCE_INVENTORY')
    paths = []
    for row in value['files']:
        require(type(row) is dict and set(row) == {'path', 'mode', 'size', 'sha256'}, 'INVALID_SOURCE_ENTRY')
        require(valid_path(row['path']) and re.fullmatch(r'[0-7]{4}', row['mode']) is not None, 'INVALID_SOURCE_ENTRY')
        require(type(row['size']) is int and row['size'] >= 0 and re.fullmatch(r'sha256:[0-9a-f]{64}', row['sha256']) is not None,
                'INVALID_SOURCE_ENTRY')
        paths.append(row['path'])
    require(paths == sorted(set(paths), key=utf16_key), 'AMBIGUOUS_SOURCE_PATHS')
    return sha(SOURCE_DOMAIN + inventory)


def git_read(root, *args):
    # Never use status, checkout, clean filters, hooks, submodules or candidate
    # scripts. Remove Git redirection variables inherited from the caller.
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C', 'GIT_CONFIG_NOSYSTEM': '1',
           'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_SYSTEM': '/dev/null', 'GIT_NO_REPLACE_OBJECTS': '1'}
    result = subprocess.run(['/usr/bin/git', '--no-pager', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
                             '-C', str(root), *args], env=env, capture_output=True, timeout=30)
    require(result.returncode == 0, 'SOURCE_GIT_READ_FAILED')
    return result.stdout


def verify_source(root, source, context):
    root = Path(root)
    actual = source_inventory(root)
    require(actual == context.source_inventory, 'SOURCE_INVENTORY_MISMATCH')
    require(source['treeDigest'] == source_tree_digest(actual), 'SOURCE_TREE_DIGEST_MISMATCH')
    require((root / '.git').is_dir() and not (root / '.git').is_symlink(), 'ORDINARY_GIT_CHECKOUT_REQUIRED')
    top = Path(git_read(root, 'rev-parse', '--show-toplevel').decode().strip())
    require(top.resolve() == root.resolve(), 'WRONG_SOURCE_ROOT')
    commit = git_read(root, 'rev-parse', '--verify', 'HEAD').decode().strip()
    require(commit == context.source_commit == source['commit'], 'WRONG_SOURCE_COMMIT')
    rows = git_read(root, 'ls-tree', '-r', '-z', commit).split(b'\0')
    inventory = parse_canonical(actual)['files']
    by_path = {row['path']: row for row in inventory}
    tracked = set()
    for row in rows:
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        mode, kind, digest = metadata.split()
        path = name.decode('utf-8')
        require(kind == b'blob' and mode in (b'100644', b'100755') and path in by_path, 'UNSUPPORTED_SOURCE_GIT_ENTRY')
        tracked.add(path)
        raw = git_read(root, 'cat-file', 'blob', digest.decode())
        require(sha(raw) == by_path[path]['sha256'], 'SOURCE_NOT_AT_COMMIT')
        require(bool(int(by_path[path]['mode'], 8) & 0o111) == (mode == b'100755'), 'SOURCE_MODE_NOT_AT_COMMIT')
    require(tracked == set(by_path), 'UNTRACKED_SOURCE_FILE')
    require(valid_path(context.entrypoint) and source['entrypoint'] == context.entrypoint and
            context.entrypoint in by_path, 'WRONG_ENTRYPOINT')
    require(valid_path(context.dependency_path) and context.dependency_path in by_path, 'MISSING_DEPENDENCY_MANIFEST')
    require(by_path[context.dependency_path]['sha256'] == source['dependencyManifestDigest'] == context.dependency_digest,
            'DEPENDENCY_MANIFEST_MISMATCH')
    for witness in context.witness_contracts:
        require(valid_path(witness.path) and witness.path in by_path and
                by_path[witness.path]['sha256'] == witness.digest, 'MISSING_OR_CHANGED_ASSERTION_CONTRACT')
    require(source_inventory(root) == actual, 'SOURCE_CHANGED_DURING_INSPECTION')


def review_subject_digest(payload):
    require(payload.get('schema') == REGISTRATION_SCHEMA, 'WRONG_REVIEW_SUBJECT_TYPE')
    require('technicalReviewDigests' in payload and 'securityReviewDigests' in payload, 'MISSING_REVIEW_FIELDS')
    subject = {k: v for k, v in payload.items() if k not in ('technicalReviewDigests', 'securityReviewDigests')}
    return sha(REVIEW_DOMAIN + canonicalize(subject))


def verify_reviews(payload, signers, context, view):
    reviews = {sha(raw): raw for raw in context.reviews}
    require(len(reviews) == len(context.reviews), 'DUPLICATE_REVIEW_CONTEXT')
    grants = {g.principal_id: g for g in context.reviewer_grants}
    subject = review_subject_digest(payload)
    purposes = {}
    for field, purpose in (('technicalReviewDigests', 'TECHNICAL'), ('securityReviewDigests', 'SECURITY')):
        identities = set()
        for digest in payload[field]:
            require(digest in reviews and digest not in view.revoked_records, 'UNTRUSTED_OR_REVOKED_REVIEW')
            value = parse_canonical(reviews[digest])
            require(type(value) is dict and set(value) == {'schema', 'subjectDigest', 'purpose', 'reviewerId',
                    'criteria', 'applications', 'issuedAt', 'expiresAt'}, 'INVALID_LAB_REVIEW')
            require(value['schema'] == 'acp-phase6-lab-review/1' and value['purpose'] == purpose and
                    value['subjectDigest'] == subject, 'WRONG_REVIEW_SUBJECT_OR_PURPOSE')
            reviewer = value['reviewerId']
            grant = grants.get(reviewer)
            require(grant is not None and purpose in grant.purposes, 'INELIGIBLE_REVIEWER')
            require(any(k.principal_id == reviewer and 'REVIEWER' in k.roles and
                        k.key_id not in view.revoked_keys and k.valid_from <= context.now < k.valid_until
                        for k in context.keys), 'REVIEWER_ROLE_OR_KEY_UNAVAILABLE')
            require(reviewer not in context.candidate_authors and reviewer not in view.revoked_principals, 'NONINDEPENDENT_OR_REVOKED_REVIEWER')
            custodians = {k.principal_id for k in context.keys if 'REGISTRATION_CUSTODIAN' in k.roles} | set(signers)
            require(context.allow_reviewer_custodian_combination or reviewer not in custodians, 'CUSTODIAN_REVIEWER_COMBINATION_FORBIDDEN')
            require(value['criteria'] == payload['criteria'] and value['applications'] == payload['requiredApplications'], 'REVIEW_SCOPE_MISMATCH')
            require(set(payload['criteria']) <= grant.criteria and set(payload['requiredApplications']) <= grant.applications, 'REVIEWER_SCOPE_MISMATCH')
            require(grant.valid_from <= utc(value['issuedAt']) <= context.now < grant.valid_until and
                    utc(value['issuedAt']) <= context.now < utc(value['expiresAt']), 'EXPIRED_REVIEW')
            require(reviewer not in identities, 'DUPLICATE_REVIEWER')
            identities.add(reviewer)
        require(identities, 'MISSING_INDEPENDENT_REVIEW')
        purposes[purpose] = identities
    require(purposes['TECHNICAL'].isdisjoint(purposes['SECURITY']), 'TECHNICAL_SECURITY_REVIEWERS_NOT_DISTINCT')


@dataclass(frozen=True)
class LabRegistrationResult:
    registration_digest: str
    verifier_id: str
    policy_digest: str
    signer_ids: tuple[str, ...]
    status: str = 'LAB_REGISTRATION_VERIFIED'
    laboratory: bool = True


def authenticate_lab_registration(raw, policy_raw, source_root, context):
    require(type(context) is LabTrustContext and context.laboratory is True, 'EXTERNAL_LAB_CONTEXT_REQUIRED')
    require(validate_structure(raw).status == 'STRUCTURE_VALID_UNTRUSTED', 'INVALID_REGISTRATION_STRUCTURE')
    record = parse_canonical(raw)
    payload = record['payload']
    require(payload['schema'] == REGISTRATION_SCHEMA, 'UNSUPPORTED_REGISTRATION_VERSION')
    verify_lab_policy(policy_raw, context)
    policy = parse_canonical(policy_raw)['payload']
    require(payload['policyRef'] == {'schema': 'acp-phase6-evidence/trust-policy/1', 'payloadDigest': context.policy_digest}, 'WRONG_POLICY_BINDING')
    require(payload['schema'] in policy['supportedSchemas'], 'UNSUPPORTED_VERIFIER_VERSION')
    view = check_revocation(context)
    signers = verify_record_signatures(raw, context.keys, 'REGISTRATION_CUSTODIAN', context.registration_threshold,
                                       context.now, view.revoked_keys, view.revoked_principals)
    require(not set(signers) & context.candidate_authors, 'CANDIDATE_SELF_REGISTRATION')
    verify_reviews(payload, signers, context, view)
    verify_source(source_root, payload['source'], context)
    require(set(payload['criteria']) <= context.criteria, 'WRONG_CRITERION_SCOPE')
    expected = [{'criterion': w.criterion, 'witnessId': w.witness_id, 'assertionContractDigest': w.digest}
                for w in sorted(context.witness_contracts, key=lambda w: (w.criterion, w.witness_id)) if w.criterion in payload['criteria']]
    require(payload['witnessContracts'] == expected, 'WRONG_WITNESS_CONTRACTS')
    require({c['criterion'] for c in policy['criterionContracts']} >= set(payload['criteria']), 'POLICY_CRITERION_MISSING')
    require(payload['requiredApplications'] == sorted(context.applications), 'WRONG_APPLICATION_SCOPE')
    require(set(payload['executorIds']) <= context.executor_ids and
            payload['environmentContractDigest'] == context.environment_contract_digest, 'WRONG_EXECUTION_ENVIRONMENT_SCOPE')
    require(utc(payload['issuedAt']) <= context.now < utc(payload['expiresAt']), 'EXPIRED_REGISTRATION')
    require(record['payloadDigest'] not in view.revoked_records, 'REVOKED_REGISTRATION')
    heads = {v: (head, previous) for v, head, previous in context.registration_heads}
    require(payload['verifierId'] in heads, 'UNKNOWN_REGISTRATION_HEAD')
    head, previous = heads[payload['verifierId']]
    require(record['payloadDigest'] == head, 'SUPERSEDED_OR_REPLAYED_REGISTRATION')
    expected_previous = None if previous is None else {'schema': REGISTRATION_SCHEMA, 'payloadDigest': previous}
    require(payload['supersedes'] == expected_previous, 'WRONG_REGISTRATION_PREDECESSOR')
    return LabRegistrationResult(record['payloadDigest'], payload['verifierId'], context.policy_digest, signers)
