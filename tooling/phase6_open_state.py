"""Versioned reviewed open-phase assertion, never a target-acceptance waiver."""
from execution_approval import APPROVED


def assert_expected_blocked(report, contract):
    def require(ok, code):
        if not ok:
            raise ValueError(code)
    require(set(contract) == {'contractVersion','target','releaseStatus','reviewBasis','domains'}, 'CONTRACT_SHAPE')
    require(contract['contractVersion'] in {'1.0.0','1.1.0','2.0.0'} and contract['releaseStatus'] == 'INCOMPLETE', 'CONTRACT_VERSION')
    approved = APPROVED
    if contract['contractVersion']=='2.0.0':
        from deterministic_approval import APPROVED as successor
        approved = {k:(v['contentDigest'],v['planDigest']) for k,v in successor.items()}
    manifest = report.get('targetManifest', {})
    require(manifest.get('releaseStatus') == 'INCOMPLETE' and manifest.get('profile') == contract['target'], 'TARGET_STATE')
    require(report.get('mode') == 'FULL_NEGOTIATED_TARGET_GATE' and report.get('result') == 'BLOCKED', 'EXPECTED_BLOCKED_RESULT')
    require(set(report.get('domains', {})) == set(contract['domains']) == set(approved), 'DOMAINS')
    for domain, expected in contract['domains'].items():
        require(set(expected) == {'canonicalDigest','blockers'}, 'DOMAIN_CONTRACT_SHAPE')
        actual = report['domains'][domain]
        require(actual.get('canonicalDigest') == expected['canonicalDigest'] == approved[domain][0], 'EXACT_APPROVED_SNAPSHOT')
        require(actual.get('result') == 'BLOCKED', 'DOMAIN_NOT_BLOCKED')
        diagnostics = actual.get('diagnostics', [])
        require(len(diagnostics) == 1 and diagnostics[0].get('code') == 'ACP-COMPILER-CAPABILITY' and
                diagnostics[0].get('stage') == 'NegotiateLower', 'EARLIER_OR_UNEXPECTED_STAGE_FAILURE')
        admission = actual.get('admission') or {}
        require(set(admission) == {'operation','result','error'} and admission['operation'] == 'lower' and
                admission['result'] == 'BLOCKED', 'REAL_TARGET_ADMISSION_NOT_REACHED')
        require(actual.get('targetAdmission') == admission['error'], 'ADMISSION_REPORT_MISMATCH')
        blockers = admission['error'].split(';')
        if contract['contractVersion']=='2.0.0':
            obsolete=('QUERY_ORDERING_REVIEW_REQUIRED','CLOSED_TRIGGER_BINDING_REVIEW_REQUIRED','ANONYMIZATION_VALUES_REVIEW_REQUIRED')
            require(not any(b.startswith(obsolete) for b in [*blockers,*expected['blockers']]), 'CANONICAL_03_ADOPTION_DEFECT')
        require(type(expected['blockers']) is list and all(type(b) is str and b for b in expected['blockers']), 'BLOCKER_CONTRACT_SHAPE')
        require(len(blockers) == len(set(blockers)) and len(expected['blockers']) == len(set(expected['blockers'])), 'DUPLICATE_BLOCKER')
        require(sorted(blockers) == sorted(expected['blockers']), 'BLOCKER_SET_CHANGED:' + domain)
    return True
