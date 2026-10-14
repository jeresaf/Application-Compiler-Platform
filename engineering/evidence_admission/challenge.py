"""Laboratory challenge construction/verification. No signing or execution API."""
import base64
from datetime import timedelta
import secrets
import re

from .encoding import parse_canonical, payload_digest
from .execution_context import LabExecutionContext, execution_contract
from .registration import authenticate_lab_registration, sha
from .signatures import require, utc, verify_record_signatures
from .trust import check_revocation
from .validation import validate_structure

SCHEMA = 'acp-phase6-evidence/execution-challenge/1'


def bindings(context):
    require(type(context) is LabExecutionContext, 'EXTERNAL_EXECUTION_CONTEXT_REQUIRED')
    contract = execution_contract(context.contract_raw)
    registration = authenticate_lab_registration(context.registration_raw, context.policy_raw,
                                                  context.verifier_source_root, context.trust)
    require(contract['registrationDigest'] == registration.registration_digest, 'WRONG_CONTRACT_REGISTRATION')
    registered = parse_canonical(context.registration_raw)['payload']
    require(set(contract['criteria']) <= set(registered['criteria']), 'WRONG_CRITERIA')
    require({s['application'] for s in contract['subjects']} == set(registered['requiredApplications']), 'WRONG_APPLICATION_SCOPE')
    witnesses = {(w['criterion'], w['witnessId']) for w in registered['witnessContracts'] if w['criterion'] in contract['criteria']}
    require({(c['criterion'], c['witnessId']) for c in contract['cases']} == witnesses, 'WRONG_WITNESS_INVENTORY')
    return contract


def construct_challenge_payload(context, record_id, reservation_seconds=900):
    """Unsigned proposed payload only; issuer must authenticate and durably issue it."""
    contract = bindings(context)
    require(type(record_id) is str and re.fullmatch(r'[0-9a-f]{32}', record_id), 'INVALID_CHALLENGE_ID')
    require(type(reservation_seconds) is int and 0 < reservation_seconds <= 900, 'INVALID_RESERVATION_WINDOW')
    now = context.trust.now
    require(now.microsecond == 0, 'WHOLE_SECOND_TIME_REQUIRED')
    policy = parse_canonical(context.policy_raw)['payload']
    registration = parse_canonical(context.registration_raw)['payload']
    expires = min(now + timedelta(seconds=reservation_seconds), utc(policy['expiresAt']), utc(registration['expiresAt']),
                  context.trust.revocation.expires_at, now + timedelta(seconds=policy['freshness']['maxChallengeAgeSeconds']))
    require(now < expires, 'NO_VALID_CHALLENGE_WINDOW')
    return {'schema': SCHEMA, 'recordId': record_id, 'repository': contract['repository'],
            'issuedAt': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'expiresAt': expires.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'policyRef': {'schema': 'acp-phase6-evidence/trust-policy/1', 'payloadDigest': contract['policyDigest']},
            'auditSessionId': contract['auditSessionId'], 'nonce': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip('='),
            'binding': contract['binding'], 'subjects': contract['subjects'], 'criteria': contract['criteria'],
            'registrationRef': {'schema': 'acp-phase6-evidence/verifier-registration/1', 'payloadDigest': contract['registrationDigest']},
            'issuerId': context.issuer_id}


def validate_challenge(raw, context):
    """Authenticated content only. Durable issuance/reservation remains mandatory."""
    require(validate_structure(raw).status == 'STRUCTURE_VALID_UNTRUSTED', 'INVALID_CHALLENGE_STRUCTURE')
    contract = bindings(context)
    record = parse_canonical(raw); payload = record['payload']; trust = context.trust
    require(payload['schema'] == SCHEMA, 'WRONG_CHALLENGE_SCHEMA')
    require(payload['issuerId'] == context.issuer_id, 'WRONG_CHALLENGE_ISSUER')
    require(payload['repository'] == contract['repository'] and payload['auditSessionId'] == contract['auditSessionId'], 'WRONG_CHALLENGE_SESSION')
    require(payload['policyRef'] == {'schema': 'acp-phase6-evidence/trust-policy/1', 'payloadDigest': contract['policyDigest']}, 'WRONG_POLICY')
    require(payload['registrationRef'] == {'schema': 'acp-phase6-evidence/verifier-registration/1', 'payloadDigest': contract['registrationDigest']}, 'WRONG_REGISTRATION')
    require(all(payload[k] == contract[k] for k in ('binding', 'subjects', 'criteria')), 'WRONG_CHALLENGE_BINDING')
    view = check_revocation(trust)
    require(record['payloadDigest'] not in view.revoked_records, 'REVOKED_CHALLENGE')
    policy = parse_canonical(context.policy_raw)['payload']
    require(SCHEMA in policy['supportedSchemas'], 'UNSUPPORTED_POLICY_SCHEMA')
    start, end = utc(payload['issuedAt']), utc(payload['expiresAt'])
    require(start <= trust.now < end and (end-start).total_seconds() <= min(900, policy['freshness']['maxChallengeAgeSeconds']), 'EXPIRED_OR_INVALID_CHALLENGE')
    require(end <= min(utc(policy['expiresAt']), utc(parse_canonical(context.registration_raw)['payload']['expiresAt'])), 'CHALLENGE_OUTLIVES_AUTHORITY')
    signers = verify_record_signatures(raw, trust.keys, 'CHALLENGE_ISSUER', 1, trust.now, view.revoked_keys, view.revoked_principals)
    require(signers == (context.issuer_id,), 'UNAUTHORIZED_ISSUER_SIGNERS')
    return {'schema': 'acp-phase6-lab-issuance/1', 'repository': payload['repository'],
            'auditSessionId': payload['auditSessionId'], 'challengeDigest': record['payloadDigest'],
            'recordId': payload['recordId'], 'nonce': payload['nonce'], 'contractDigest': context.expected_contract_digest,
            'registrationDigest': contract['registrationDigest'], 'policyDigest': contract['policyDigest'],
            'issuedAt': payload['issuedAt'], 'expiresAt': payload['expiresAt'], 'signedRecordDigest': sha(raw)}


def authenticate_challenge(raw, context, ledger):
    """Idempotent read-only authentication of an issued, still-unused challenge."""
    issuance = validate_challenge(raw, context)
    observed = ledger.observe(issuance['challengeDigest'])
    require(observed['issuance'] == issuance, 'ISSUANCE_CONTRACT_MISMATCH')
    require(observed['state'] == 'ISSUED', 'CHALLENGE_ALREADY_CONSUMED')
    return issuance['challengeDigest']  # content identity, never execution permission
