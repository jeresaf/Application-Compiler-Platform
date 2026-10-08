"""Exact bounded reference record of the user's explicit ADR-0016 approval.

Public reference key, never production IAM or an invented reviewer identity.
Frozen pins represent only reviewed commit 76e7700 and this dated instruction.
Historical proposal bytes and AI origins are retained unchanged.
"""
import hashlib
import json
from canonical_json import load, digest
from canonical_ir import admit, validate_snapshot
from changes import request, fingerprint
from deterministic_fixtures import DEST
from reference_authority import ReferenceAuthority

STATEMENT = 'Approve ADR-0016 and the complete deterministic-v04 fixture decisions, including the F-01 failure bindings.'
WHEN = 1791417600  # Dated reference clock, not a claimed wall-clock event timestamp.
PRINCIPAL = 'reference:explicit-human-project-authority'
KEY = b'public-deterministic-v04-reference-key-only'
REVIEWED_COMMIT = '76e7700758454b5cfd00c39a68475439c1a1e6ca'
APPROVED = {'payment': {'contentDigest': 'sha256:d0f6e8d96a07e8e8358ad8f1f558f9ec3d69fd8008cceb75e82f4f695e3cf47d', 'planDigest': 'sha256:882781981441c2ab50d71617a15edfca88c6b9ebaa25c130cf40f56ea8ce356e', 'proposalSourceDigest': 'sha256:fe3918f50bf9662b8714d30f77774b6a87d4d2c95e5668987cee7fed8822656a'}, 'case-management': {'contentDigest': 'sha256:5b3a69bb1d6e0e69ed620cd1dd32d10e8a07cec276583055b53ec03bfdcc6b90', 'planDigest': 'sha256:d904bc51285d778ba66784fbd08842bd151980e8a22f7662c6330e0f3fd51131', 'proposalSourceDigest': 'sha256:6e41954365f3a1accc7d999591cf5196580292eb6269ae020d0e00cace7abc28'}}
ASSETS = {'contracts/authoring-0.4.schema.json': 'sha256:2e60a19f9683d4515a0bd51fc5b0b964164990eea7fadd6715b50fdf11d25d60', 'contracts/canonical-0.3.schema.json': 'sha256:104bb574abac5eafd7b8e4e6ea5b030b08b30631f8207437ed6713cf9e3098ea', 'contracts/change-0.3.schema.json': 'sha256:7424c400b2887eafc5d572f7c55c702daa07956e3d79729bf0d6562fa931f491', 'docs/adr/0016-deterministic-query-lifecycle-and-rate-semantics.md': 'sha256:bc1dd54ba835442e49b0a4430c60b6ab00b9c13cf00301392b08f1c80bcb7e93'}


def authority():
    applications=[load(DEST/(d+'-canonical-candidate.json'))['content']['applicationId'] for d in APPROVED]
    return ReferenceAuthority(KEY,{'explicit-human-approval':PRINCIPAL},
        {PRINCIPAL:[app+':'+scope for app in applications for scope in
                    ('SEMANTIC','SECURITY','MIGRATION','IRREVERSIBLE','LOCKED_DECISION')]})


def header():
    return {'date':'2026-10-08','statement':STATEMENT,'status':'APPROVED_REFERENCE_SEMANTICS',
        'reviewedCommit':REVIEWED_COMMIT,'assets':ASSETS,
        'versions':{'authoring':'0.4.0','canonical':'0.3.0','change':'0.3.0'},
        'scope':'Complete ADR-0016 and both ACP synthetic reference fixtures, including F-01; not production business requirements or target support',
        'provenance':'AI proposed; human project authority explicitly approved in user instruction',
        'authorityRepresentation':'Bounded reference/test authority with public key; no manufactured reviewer identity or production credentials',
        'referenceClock':WHEN}


def checked(domain):
    if domain not in APPROVED:raise ValueError('UNAPPROVED_DOMAIN')
    for name,expected in ASSETS.items():
        actual='sha256:'+hashlib.sha256((DEST.parents[1]/name).read_bytes()).hexdigest()
        if actual!=expected:raise ValueError('FRESH_HUMAN_APPROVAL_REQUIRED')
    plan=load(DEST/(domain+'-plan.json'));snapshot=load(DEST/(domain+'-canonical-candidate.json'))
    source=load(DEST/(domain+'-proposal-authoring.json'))
    query=request(plan)
    actual={'contentDigest':query['contentDigest'],'planDigest':query['planDigest'],
            'proposalSourceDigest':digest(source,'authoring')}
    if actual!=APPROVED[domain] or snapshot!=plan['candidate']:
        raise ValueError('FRESH_HUMAN_APPROVAL_REQUIRED')
    if fingerprint({k:v for k,v in plan.items() if k!='planDigest'},'plan')!=plan['planDigest']:
        raise ValueError('PLAN_BINDING')
    validate_snapshot(snapshot)
    return query,snapshot


def record():
    auth=authority();examples=[]
    for domain in APPROVED:
        query,snapshot=checked(domain)
        proof=auth.issue('explicit-human-approval',query,WHEN,lifetime=86400)
        auth.verify(proof,query,WHEN)
        admit(snapshot,lambda q:q['applicationId']==query['applicationId'] and q['contentDigest']==query['contentDigest'])
        examples.append({'domain':domain,'proposalSourceDigest':APPROVED[domain]['proposalSourceDigest'],
                         'request':query,'proof':proof})
    return {**header(),'examples':examples}


def approved_snapshot(domain):
    stored=load(DEST/'human-approval.json')
    if {k:v for k,v in stored.items() if k!='examples'}!=header():raise ValueError('APPROVAL_BINDING')
    if sorted(e['domain'] for e in stored['examples'])!=sorted(APPROVED):raise ValueError('APPROVAL_BINDING')
    example=next(e for e in stored['examples'] if e['domain']==domain)
    query,snapshot=checked(domain)
    if example['request']!=query or example['proposalSourceDigest']!=APPROVED[domain]['proposalSourceDigest']:
        raise ValueError('FRESH_HUMAN_APPROVAL_REQUIRED')
    authority().verify_historical(example['proof'],query,stored['referenceClock'])
    admit(snapshot,lambda q:q['applicationId']==query['applicationId'] and q['contentDigest']==query['contentDigest'])
    return snapshot


if __name__=='__main__':
    (DEST/'human-approval.json').write_text(json.dumps(record(),indent=2)+'\n')
