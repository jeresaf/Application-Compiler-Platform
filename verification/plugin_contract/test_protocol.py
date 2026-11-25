import copy
import json
from pathlib import Path
import unittest

from engineering.evidence_admission.encoding import canonicalize, payload_digest
from engineering.plugin_contract import protocol as p


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.identity = dict(plugin='example', sourceDigest=p.digest(b'source'),
                             dependencyDigest=p.digest(b'lock'), provenanceDigest=p.digest(b'origin'),
                             protocol=p.PROTOCOL, compilerAPI='compiler/1', target='target/1',
                             profile='synthetic', limits=p.LIMITS, capabilities=['plan'])
        self.request = dict(protocol=p.PROTOCOL, execution='a'*32, nonce='b'*32,
                            canonicalDigest=p.digest(b'canonical'), identityDigest=payload_digest(self.identity),
                            targetIR={'items': []})
        self.artifact = dict(path='src/example.txt', content='example', contentDigest=p.digest(b'example'),
                             origins=[{'id': 'A', 'revision': 1}], obligations=['V1'])
        self.response = dict(protocol=p.PROTOCOL, execution=self.request['execution'], outcome='SUCCESS',
                             requestDigest=payload_digest(self.request), artifacts=[self.artifact])
        self.expected = {self.artifact['path']: (self.artifact['origins'], self.artifact['obligations'])}

    def wire(self, value):
        return p.frame(canonicalize(value))

    def identity_check(self, **overrides):
        raw = canonicalize(self.identity)
        args = dict(expected=raw, source=b'source', dependencies=b'lock', provenance=b'origin',
                    compiler_api='compiler/1', profiles={'synthetic'}, capabilities={'plan'}, target='target/1')
        return p.validate_identity(raw, **(args | overrides))

    def test_identity_does_not_admit(self):
        self.assertEqual(self.identity_check(), self.identity)
        self.assertFalse(p.HOSTILE_EXECUTION_ENABLED)
        self.assertEqual(p.admission_status(), 'BLOCKED_PENDING_OWNER_APPROVAL')

    def test_identity_rejections(self):
        for field, value in dict(expected=b'unknown', source=b'tampered', dependencies=b'latest',
                                 provenance=b'', compiler_api='wrong', profiles=set(),
                                 capabilities=set(), target='wrong').items():
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.identity_check(**{field: value})

    def test_request_and_response(self):
        request = p.validate_request(self.wire(self.request), identity=self.identity,
                                     canonical_digest=self.request['canonicalDigest'],
                                     target_ir_digest=payload_digest(self.request['targetIR']))
        self.assertEqual(p.validate_response(self.wire(self.response), request=request,
                                             expected_artifacts=self.expected), self.response)
        with self.assertRaises(ValueError):
            p.validate_request(self.wire(self.request), identity=self.identity,
                               canonical_digest=p.digest(b'stale'), target_ir_digest=p.digest(b'wrong'))

    def test_invalid_frames(self):
        for raw in (b'', p.frame(b'{"a":1,"a":2}'), p.frame(b'{"x":NaN}'),
                    p.frame(b'{}')+b'junk', b'x'*(p.MAX_BYTES+5)):
            with self.assertRaises(ValueError):
                p.decode(raw)

    def test_response_rejections(self):
        for field, value in dict(path='../escaped', content='substituted', origins=[], obligations=[]).items():
            response = copy.deepcopy(self.response)
            response['artifacts'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                p.validate_response(self.wire(response), request=self.request, expected_artifacts=self.expected)
        for response in (self.response | {'requestDigest': p.digest(b'stale')},
                         self.response | {'artifacts': []},
                         self.response | {'publish': True}):
            with self.assertRaises(ValueError):
                p.validate_response(self.wire(response), request=self.request, expected_artifacts=self.expected)

    def test_lab_cases_are_blocked(self):
        root = Path(__file__).resolve().parents[2]
        record = json.loads((root/'reviews/phase11-h10-2/status.json').read_bytes())
        self.assertEqual(len(record['labCases']), 22)
        self.assertEqual(set(record['labCases'].values()), {'NOT_RUN'})
        self.assertEqual(set(record['decisions'].values()), {'NOT_APPROVED'})
        self.assertFalse(p.HOSTILE_EXECUTION_ENABLED)
