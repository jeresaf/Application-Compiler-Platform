"""Synthetic review verification only; no accepted_reviews authority is issued."""
from types import MappingProxyType
from engineering.evidence_admission.encoding import parse_canonical
from .manifest import require, sha, time
from .witnesses import authenticate

HUMAN = frozenset((12,13,15,20,26,27,28))


def verify_reviews(records, manifest, manifest_digest, artifacts, context):
    require(type(records) is tuple and all(type(r) is bytes for r in records), 'IMMUTABLE_REVIEW_RECORDS')
    result={}
    grants=[parse_canonical(r) for r in context.review_grants]
    expected={c['criterion'] for c in manifest['criteria'] if c['evidenceKind'] in ('HUMAN_REVIEW','COMBINED')}
    for raw in records:
        record=parse_canonical(raw);p=authenticate(record,context,{'REVIEWER'})
        require(set(p)=={'schema','laboratory','manifestDigest','release','criterion','applications','reviewDigest','reviewerId','grantId','independenceDigest','purpose','disposition','reservations','exclusions','issuedAt','expiresAt'}, 'REVIEW_CLOSED_SCHEMA')
        require(p['schema']=='acp-phase6-lab-human-review/1' and p['laboratory'] is True, 'UNSUPPORTED_REVIEW_PROFILE')
        n=p['criterion'];require(type(n) is int and n in HUMAN and n in expected and n not in result,'WRONG_REVIEW_CRITERION')
        require(p['purpose']=='DEPLOYMENT_REVIEW' and p['disposition']=='ACCEPT' and p['reservations']==[] and p['exclusions']==[], 'UNSATISFIED_OR_EXCLUDED_OBLIGATION')
        require(p['manifestDigest']==manifest_digest and p['release']==manifest['release'], 'WRONG_REVIEW_SUBJECT')
        require(p['reviewerId']==record['signatures'][0]['signerId'] and p['reviewerId'] not in context.author_ids, 'REVIEWER_NOT_INDEPENDENT')
        matches=[g for g in grants if g['grantId']==p['grantId']];require(len(matches)==1,'UNREGISTERED_REVIEW_GRANT')
        g=matches[0]
        require(set(g)=={'grantId','reviewerId','keyId','criteria','applications','release','validFrom','validUntil','independenceDigest'},'GRANT_CLOSED_SCHEMA')
        require(g['reviewerId']==p['reviewerId'] and g['keyId']==record['signatures'][0]['keyId'] and n in g['criteria'] and g['release']==p['release'], 'GRANT_SCOPE')
        apps=[a['application'] for a in manifest['applications']]
        require(p['applications']==apps and set(apps)<=set(g['applications']) and p['independenceDigest']==g['independenceDigest'], 'REVIEW_APPLICATION_OR_INDEPENDENCE')
        require(time(g['validFrom']) <= time(p['issuedAt']) <= context.now < time(g['validUntil']), 'EXPIRED_REVIEW_GRANT')
        review=artifacts.get('deployment-review.json');require(review is not None and sha(review)==p['reviewDigest'], 'REVIEW_RAW_DIGEST')
        # Raw document hash is never replaced by normalized or merged per-application bytes.
        import json
        document=json.loads(review)
        require(document.get('criteria',{}).get(str(n))=={'authority':'EXPLICIT_HUMAN_ACCEPTANCE','verification':'REVIEWED_EXTERNAL_OBLIGATION'},'REVIEW_DOCUMENT_CONTENT')
        result[n]=p['reviewDigest']
    require(set(result)==expected,'MISSING_REVIEW_DECISION')
    return MappingProxyType(result)  # laboratory diagnostic only, never supplied to assess()
