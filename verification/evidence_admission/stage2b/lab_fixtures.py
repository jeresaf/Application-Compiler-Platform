"""Synthetic authority only. Reuse accepted Stage 2A fixtures; never launch workloads."""
import copy
from dataclasses import replace
from datetime import timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from engineering.evidence_admission.encoding import canonicalize, payload_digest
from engineering.evidence_admission.execution_context import LabExecutionContext, contract_digest
from engineering.evidence_admission.challenge import construct_challenge_payload
from engineering.evidence_admission.execution_ledger import ExecutionLedger
from engineering.evidence_admission.signatures import LabKey

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stage2a_reused_lab_fixtures', BASE/'stage2a/lab_fixtures.py')
accepted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(accepted)
signed = accepted.signed
NOW = accepted.NOW


class Fixture:
    def __init__(self, test):
        self.test = test
        self.base = accepted.LabFixture(test)
        private = Ed25519PrivateKey.from_private_bytes(hashlib.sha256(b'PUBLIC STAGE2B TEST ISSUER').digest())
        self.base.private['issuer'] = private
        key = LabKey('key:issuer', 'principal:issuer', private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw),
                     frozenset(['CHALLENGE_ISSUER']), accepted.START, accepted.END)
        self.base.context = replace(self.base.context, keys=(*self.base.context.keys, key))
        self.base.policy['signerRoles'].append({'signerId': 'principal:issuer', 'role': 'CHALLENGE_ISSUER', 'keyIds': ['key:issuer']})
        self.base.policy['signerRoles'].sort(key=lambda r: (r['signerId'], r['role']))
        self.base.repin_policy()
        examples = json.loads((BASE/'fixtures/synthetic-records.json').read_text())['records']
        binding = copy.deepcopy(examples['execution-challenge']['payload']['binding'])
        self.contract = {'schema': 'acp-phase6-lab-execution-contract/1', 'repository': self.base.context.repository,
            'auditSessionId': 'session:synthetic-only', 'registrationDigest': payload_digest(self.base.payload),
            'policyDigest': self.base.context.policy_digest, 'binding': binding,
            'subjects': [{'application': app, 'snapshotDigest': binding['canonicalDigests'][name], 'packageDigest': 'sha256:' + digit*64}
                         for app, name, digit in [('CASE_MANAGEMENT', 'case-management', 'a'), ('PAYMENT', 'payment', 'b')]],
            'criteria': [8], 'cases': [{'criterion': 8, 'application': app, 'witnessId': 'integratedCrossOwnerTransitions',
                                      'caseId': 'syntheticCase'} for app in ['CASE_MANAGEMENT', 'PAYMENT']],
            'commands': [{'commandId': 'verify', 'argv': ['bin/python3.14', '-m', 'synthetic_verifier'],
                          'executablePath': 'bin/python3.14', 'executableDigest': 'sha256:'+'c'*64,
                          'dependencyDigest': 'sha256:'+'d'*64, 'workingDirectory': 'workspace',
                          'workingDirectoryDigest': 'sha256:'+'e'*64, 'environment': {'LANG': 'C.UTF-8'}}],
            'artifacts': [{'path': app+'.tar', 'role': 'PACKAGE', 'mediaType': 'application/x-tar', 'expectedDigest': 'sha256:'+digit*64,
                           'maxBytes': 1048576} for app, digit in [('case', 'a'), ('payment', 'b')]],
            'limits': {'maxArtifacts': 20, 'maxTotalBytes': 10485760, 'memoryBytes': 268435456, 'processes': 8,
                       'cpuSeconds': 120, 'executionTimeoutSeconds': 3600}, 'isolationProfileDigest': 'sha256:'+'f'*64}
        self.refresh_context()
        self.payload = construct_challenge_payload(self.context, '11111111111111111111111111111111')
        self.raw = signed(self.payload, ['issuer'], self.base.private)
        temp = tempfile.TemporaryDirectory(prefix='acp-stage2b-ledger-');test.addCleanup(temp.cleanup)
        self.path = Path(temp.name)/'ledger.sqlite'
        self.ledger = ExecutionLedger(self.path, create=True);test.addCleanup(self.ledger.close)

    def refresh_context(self):
        raw = canonicalize(self.contract)
        self.context = LabExecutionContext(self.base.context, raw, contract_digest(raw), 'principal:issuer',
                                          self.base.raw, self.base.policy_raw, str(self.base.root))

    def sign(self, payload=None):
        return signed(self.payload if payload is None else payload, ['issuer'], self.base.private)

    def issue(self):
        return self.ledger.issue(self.raw, self.context)
