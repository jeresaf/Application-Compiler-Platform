"""Exact documentary human decisions. Not a compiler approval authority or proof issuer."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_json import canonical_bytes, digest

ROOT = Path(__file__).resolve().parents[2]
PROPOSALS = ROOT/'proposals/phase6-evolution-review'
RECORDS = ROOT/'targets/spring-vue-postgres/evidence/semantic-content-decisions/2026-10-12'
SOURCE = {'branch':'codex/phase6-production-remediation','commit':'f0c2e37640d8b87f7cf9ebc6fe73f236f298a583'}
STATEMENT = ('On 2026-10-12, the project authority explicitly approved the bounded synthetic semantic '
             'requirements and ChangeSet content for PAYMENT and CASE MANAGEMENT independently, following the architecture review.')
SCOPE = 'SYNTHETIC_REFERENCE_SEMANTIC_CONTENT_ONLY'
PINS = {
 'payment': {'applicationId':'APP-FIXTURE','owner':'ENT-PAYMENT',
  'previousDigest':'sha256:d0f6e8d96a07e8e8358ad8f1f558f9ec3d69fd8008cceb75e82f4f695e3cf47d',
  'candidateDigest':'sha256:5c54e0692524ec907b5c5373b8b5536e4f053122ce033dda70957320a53281cf',
  'changeSetFileDigest':'sha256:3fffe5ef53a9446b4c827a8ab220b8fa5d7e02760f941b7f8d7b227dc3facefa'},
 'case-management': {'applicationId':'APP-CASE-MANAGEMENT','owner':'CASE',
  'previousDigest':'sha256:5b3a69bb1d6e0e69ed620cd1dd32d10e8a07cec276583055b53ec03bfdcc6b90',
  'candidateDigest':'sha256:e57eaee3f979f3b77feb255dde470772321b3354001547e71e02fbaadca2b59d',
  'changeSetFileDigest':'sha256:55a53d04dfc196505880699f51e68d039232a8a37de88d4f9102c9c61f8fbcc0'}}
CRITERIA = ['AC-EVOLVE-RETAINED','AC-EVOLVE-NEW-WRITE','AC-EVOLVE-UPDATE','AC-EVOLVE-ROLLOUT']
APPROVED = ['Exact proposed semantic candidate content','New synthetic reference-only Requirement',
 'Four associated AcceptanceCriteria','Required String field semantics','Existing update behavior preservation',
 'Explicit new-record value requirements','BREAKING final-schema compatibility classification','REVIEW_REQUIRED staged rollout intent']
EXCLUSIONS = ['Independent retained-data backfill bindings','Production tenant applicability',
 'Real accepted-history journal rebase','Preview plan approval','Migration execution authority','Exact SQL',
 'Schema deployment','Production identity/security assurance','Phase 6 closure']


def sha(data):
    return 'sha256:'+hashlib.sha256(data).hexdigest()


def expected_record(domain):
    pin = PINS[domain]
    return {'recordVersion':'1.0.0','decisionId':'PHASE6-SEMANTIC-'+domain.upper()+'-2026-10-12',
        'status':'APPROVED_CONTENT','date':'2026-10-12','humanProjectAuthorityStatement':STATEMENT,
        'source':dict(SOURCE),'domain':domain,**pin,'scope':SCOPE,
        'requirement':{'id':'REQ-EVOLVE-REFERENCE-NOTE','revision':1},
        'acceptanceCriteria':[{'id':id,'revision':1} for id in CRITERIA],
        'field':{'id':'EVOLVE-REFERENCE-NOTE','revision':1},
        'approvedMeaning':list(APPROVED),'exclusions':list(EXCLUSIONS),
        'proposalProvenance':{'actorType':'AI','source':'proposal:phase6-evolution-review',
                             'locator':domain,'actor':'assistant:proposal','relabeledAsHuman':False},
        'authenticatedApprovalProof':'PENDING_HUMAN_SIGNING','acceptedJournalPlan':'PENDING_AUTHENTIC_HISTORY',
        'dataBinding':'REVIEW_REQUIRED','migration':'NOT_AUTHORIZED','deployment':'NOT_AUTHORIZED',
        'authorityRepresentation':'Documentary record of explicit user-provided project-authority decision; no reviewer identity, signature, key, session or journal receipt is asserted',
        'executionAuthority':False,'phase6':'IN_PROGRESS','phase7':'NOT_STARTED'}


def verify_decision(domain, record, candidate, change_bytes, source):
    """Document integrity only. A successful return cannot authorize any compiler port."""
    if domain not in PINS or record != expected_record(domain) or source != SOURCE:
        raise ValueError('SEMANTIC_DECISION_IDENTITY_OR_SCOPE')
    pin = PINS[domain]
    if (candidate['content']['applicationId'] != pin['applicationId'] or
        candidate['contentDigest'] != pin['candidateDigest'] or
        digest(candidate['content'],'canonical') != pin['candidateDigest'] or
        sha(change_bytes) != pin['changeSetFileDigest']):
        raise ValueError('SEMANTIC_DECISION_CONTENT_BINDING')
    change = json.loads(change_bytes)
    if change['base']['digest'] != pin['previousDigest']:
        raise ValueError('SEMANTIC_DECISION_PREDECESSOR')
    return {'status':'APPROVED_CONTENT','domain':domain,'scope':SCOPE,
            'authenticatedProofIssued':False,'executionAuthority':False}


class NoExecutionAuthority:
    """Explicit denial port: documentary semantic decisions do not grant migration authority."""
    def read_accepted_plan(self, plan_digest):
        raise PermissionError('PENDING_AUTHENTIC_HISTORY')
    def read_approved_bindings(self, *args):
        raise PermissionError('INDEPENDENT_DATA_BINDINGS_NOT_APPROVED')


def immutable_write(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('IMMUTABLE_DECISION_RECORD:'+str(path))
        return
    with path.open('xb') as stream:
        stream.write(data)


def json_bytes(value):
    return (json.dumps(value,indent=2,ensure_ascii=True)+'\n').encode()


def signing_request(domain, record_bytes):
    payload = {'kind':'SEMANTIC_CONTENT_RECORD_ATTESTATION','domain':domain,
        'applicationId':PINS[domain]['applicationId'],'source':dict(SOURCE),'date':'2026-10-12',
        'decisionRecordDigest':sha(record_bytes),'candidateDigest':PINS[domain]['candidateDigest'],
        'changeSetFileDigest':PINS[domain]['changeSetFileDigest'],'scope':SCOPE,
        'executionAuthority':False,'exclusions':list(EXCLUSIONS)}
    message = b'ACP\0phase6-semantic-content-attestation-v1\0'+canonical_bytes(payload)
    return {'status':'PENDING_HUMAN_SIGNING','payload':payload,
        'exactMessageEncoding':'hex; domain-separated prefix followed by ACP canonical JSON payload bytes',
        'messageHex':message.hex(),'messageSha256':sha(message),
        'signerIdentity':None,'keyIdentity':None,'signature':None,
        'requiredAction':'Human authority supplies an authenticated signing identity, trusted verification channel and actual signature over exact message. No key/session/signature is generated here.',
        'useLimit':'Content attestation only, not a full-plan SEMANTIC/SECURITY/MIGRATION authorization. Existing ReferenceAuthority cannot express this separate content-decision type without a separately reviewed adapter.'}


def main():
    manifest = {'status':'DOCUMENTARY_SEMANTIC_DECISIONS_RECORDED','source':SOURCE,'records':{}}
    for domain in PINS:
        record = expected_record(domain)
        candidate = json.loads((PROPOSALS/(domain+'-canonical-candidate.json')).read_bytes())
        change = (PROPOSALS/(domain+'-change.json')).read_bytes()
        verify_decision(domain,record,candidate,change,SOURCE)
        data = json_bytes(record)
        immutable_write(RECORDS/(domain+'.json'),data)
        request = json_bytes(signing_request(domain,data))
        immutable_write(RECORDS/(domain+'-signing-request.json'),request)
        manifest['records'][domain] = {'decisionRecordDigest':sha(data),'signingRequestFileDigest':sha(request),
                                     'status':'APPROVED_CONTENT','authenticatedProof':'PENDING_HUMAN_SIGNING'}
    immutable_write(RECORDS/'manifest.json',json_bytes(manifest))
    print(json.dumps(manifest,indent=2))

if __name__ == '__main__':
    main()
