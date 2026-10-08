"""Exact reviewed failures pass only at real target negotiation, never earlier."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_json import load
from phase6_open_state import assert_expected_blocked
from target_worker import ROOT


class OpenStateTests(unittest.TestCase):
    def setUp(self):
        self.contract = load(ROOT / 'expected-open-blockers.json')
        self.report = {'targetManifest': {'profile': self.contract['target'], 'releaseStatus': 'INCOMPLETE'},
            'mode': 'FULL_NEGOTIATED_TARGET_GATE', 'result': 'BLOCKED', 'domains': {}}
        for domain, entry in self.contract['domains'].items():
            error = ';'.join(entry['blockers'])
            self.report['domains'][domain] = {'canonicalDigest': entry['canonicalDigest'], 'result': 'BLOCKED',
                'diagnostics': [{'code': 'ACP-COMPILER-CAPABILITY', 'stage': 'NegotiateLower'}],
                'admission': {'operation': 'lower', 'result': 'BLOCKED', 'error': error}, 'targetAdmission': error}

    def test_exact_state_and_reordered_blockers(self):
        self.assertTrue(assert_expected_blocked(self.report, self.contract))
        for entry in self.report['domains'].values():
            entry['targetAdmission'] = ';'.join(reversed(entry['targetAdmission'].split(';')))
            entry['admission']['error'] = entry['targetAdmission']
        self.assertTrue(assert_expected_blocked(self.report, self.contract))

    def test_added_removed_duplicate_and_missing_admission_fail(self):
        for change in ('added','removed','duplicate','missing'):
            report = copy.deepcopy(self.report); entry = report['domains']['payment']
            error = entry['targetAdmission']
            if change == 'added': error += ';UNSUPPORTED:Surprise/1'
            if change == 'removed': error = ';'.join(error.split(';')[1:])
            if change == 'duplicate': error += ';' + error.split(';')[0]
            entry['targetAdmission'] = entry['admission']['error'] = error
            if change == 'missing': entry['admission'] = None
            with self.assertRaises(ValueError, msg=change): assert_expected_blocked(report, self.contract)

    def test_wrong_snapshot_earlier_stage_success_and_release_state_fail(self):
        mutations = [lambda r: r['domains']['payment'].update(canonicalDigest='sha256:'+'0'*64),
            lambda r: r['domains']['payment']['diagnostics'][0].update(stage='Analyze'),
            lambda r: r['domains']['payment']['diagnostics'][0].update(code='ACP-COMPILER-INPUT'),
            lambda r: r.update(result='PASS'),
            lambda r: r['targetManifest'].update(releaseStatus='ACCEPTED'),
            lambda r: r['domains'].pop('case-management')]
        for mutate in mutations:
            report = copy.deepcopy(self.report); mutate(report)
            with self.assertRaises(ValueError): assert_expected_blocked(report, self.contract)

    def test_contract_cannot_authorize_different_content_or_silent_capability_change(self):
        for change in ('digest','removed','version'):
            contract = copy.deepcopy(self.contract)
            if change == 'digest': contract['domains']['payment']['canonicalDigest'] = 'sha256:'+'0'*64
            if change == 'removed': contract['domains']['payment']['blockers'].pop()
            if change == 'version': contract['contractVersion'] = '999'
            with self.assertRaises(ValueError): assert_expected_blocked(self.report, contract)
