"""Bounded reference representation of explicit human approval, never production IAM.

The public test key and reference principal below represent the project authority's
2026-10-08 instruction. They are not a claimed reviewer name or credentials.
AI proposal origins and all approved semantic bytes remain unchanged.
"""
import json
from canonical_ir import admit, normalize_candidate
from canonical_json import load
from changes import request
from execution_fixtures import DEST
from execution_fixtures import evolution
from reference_authority import ReferenceAuthority

STATEMENT = 'Approve ADR-0015 and the execution-v03 fixture decisions.'
WHEN = 1791417600  # 2026-10-08 00:00:00 UTC; reference clock for dated approval.
PRINCIPAL = 'reference:explicit-human-project-authority'
KEY = b'public-execution-v03-reference-test-key-only'
APPROVED = {
    'payment': ('sha256:d2cd65d09c4739f53d4c57dddd1d29eb5456bc421c5fac745b336459590d25ac',
                'sha256:9f32a52a87ef1faa12daf0a24dbbbb6687d2c59e10cb07ea9f1b6035e5f448a0'),
    'case-management': ('sha256:4207852923d9e7e16f7e273d5bedbaa78bc2f10d82efa6f5568f00d23b89055b',
                        'sha256:9d79387aa309a5e6b3d979edb2a796c93da2461f6d5d8efd42effca017eefb10'),
}


def authority():
    applications = [load(DEST / (d + '-canonical.json'))['content']['applicationId']
                    for d in ('payment', 'case-management')]
    scopes = [a + ':' + s for a in applications for s in
              ('SEMANTIC', 'SECURITY', 'MIGRATION', 'IRREVERSIBLE', 'LOCKED_DECISION')]
    return ReferenceAuthority(KEY, {'human-approval-reference': PRINCIPAL}, {PRINCIPAL: scopes})


def header():
    return {'date': '2026-10-08', 'statement': STATEMENT,
            'status': 'APPROVED_REFERENCE_SEMANTICS',
            'scope': 'ACP synthetic reference applications/corpora only; not production business requirements',
            'provenance': 'AI proposed; human project authority explicitly approved in user instruction',
            'authorityRepresentation': 'Bounded test/reference authority; public test key; no manufactured reviewer identity',
            'referenceClock': WHEN}


def record():
    auth = authority()
    examples = []
    for domain in ('payment', 'case-management'):
        plan = load(DEST / (domain + '-plan.json'))
        query = request(plan)
        if (query['contentDigest'], query['planDigest']) != APPROVED[domain]:
            raise ValueError('FRESH_HUMAN_APPROVAL_REQUIRED')
        proof = auth.issue('human-approval-reference', query, WHEN, lifetime=86400)
        auth.verify(proof, query, WHEN)
        snapshot = load(DEST / (domain + '-canonical.json'))
        if snapshot != plan['candidate'] or snapshot != normalize_candidate(load(DEST / (domain + '-authoring.json'))):
            raise ValueError('APPROVED_CONTENT_CHANGED')
        admit(snapshot, lambda q: q['contentDigest'] == query['contentDigest'])
        examples.append({'domain': domain, 'request': query, 'proof': proof})
    return {**header(), 'examples': examples}


def approved_snapshot(domain):
    stored = load(DEST / 'human-approval.json')
    if {k: v for k, v in stored.items() if k != 'examples'} != header():
        raise ValueError('APPROVAL_BINDING')
    example = next(e for e in stored['examples'] if e['domain'] == domain)
    plan = load(DEST / (domain + '-plan.json'))
    if (example['request'] != request(plan) or
            (example['request']['contentDigest'], example['request']['planDigest']) != APPROVED[domain]):
        raise ValueError('FRESH_HUMAN_APPROVAL_REQUIRED')
    authority().verify_historical(example['proof'], example['request'], stored['referenceClock'])
    snapshot = load(DEST / (domain + '-canonical.json'))
    if snapshot != plan['candidate'] or normalize_candidate(load(DEST / (domain + '-authoring.json'))) != snapshot:
        raise ValueError('APPROVED_CONTENT_CHANGED')
    admit(snapshot, lambda q: q['contentDigest'] == example['request']['contentDigest'])
    return snapshot


def apply_approved_upgrade(repository, domain):
    """Admit the approved exact content through real reference change lifecycle.

The existing historical journal is an input, never rewritten or reapproved here.
Its actual head changes the plan digest, so issue a fresh reference proof for
that plan, after verifying the operation list and approved candidate exactly.
This is a bounded executable representation of the explicit human instruction.
"""
    historical, proposal = evolution(domain, repository.head())
    if repository.snapshot() != historical:
        raise ValueError('HISTORICAL_BASE_REQUIRED')
    expected_change = load(DEST / (domain + '-change.json'))
    if {k: v for k, v in proposal.items() if k != 'base'} != {k: v for k, v in expected_change.items() if k != 'base'}:
        raise ValueError('FRESH_HUMAN_APPROVAL_REQUIRED')
    # Author authentication and reviewer authentication are separate host ports.
    auth = authority()
    author = proposal['author']
    author_auth = ReferenceAuthority(KEY, {'proposal-author-reference': author}, {})
    plan = repository.propose(proposal, author_auth, 'proposal-author-reference')
    if plan['candidate'] != approved_snapshot(domain):
        raise ValueError('FRESH_HUMAN_APPROVAL_REQUIRED')
    repository.review(proposal['id'], author_auth, 'proposal-author-reference')
    proof = auth.issue('human-approval-reference', request(plan), WHEN, lifetime=86400)
    repository.approve(proposal['id'], proof, auth, WHEN)
    receipt = repository.apply(proposal['id'], 'explicit-human-execution-v03-upgrade', auth, WHEN)
    return {'head': receipt, 'planDigest': plan['planDigest'], 'proof': proof,
            'authorityRepresentation': 'test/reference representation of explicit human approval'}


if __name__ == '__main__':
    (DEST / 'human-approval.json').write_text(json.dumps(record(), indent=2) + '\n')
