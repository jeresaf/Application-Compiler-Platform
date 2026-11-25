import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest

from engineering.supply_chain.reconcile import package_members, version_status


class ReconciliationTests(unittest.TestCase):
    def test_package_inventory_and_substitution(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'app.tar'
            raw = b'exact'
            with tarfile.open(path, 'w') as tar:
                member = tarfile.TarInfo('backend/application.jar')
                member.size = len(raw)
                tar.addfile(member, io.BytesIO(raw))
            digest = lambda value: hashlib.sha256(value).hexdigest()
            expected = {'packageSHA256': digest(path.read_bytes()),
                        'files': {'backend/application.jar': digest(raw)}}
            self.assertEqual(package_members(path, expected)['backend/application.jar'], raw)
            for files in ({}, expected['files'] | {'missing': digest(raw)}):
                with self.assertRaisesRegex(ValueError, 'PACKAGE_MEMBER_INVENTORY'):
                    package_members(path, expected | {'files': files})
            with self.assertRaisesRegex(ValueError, 'PACKAGE_MEMBER_DIGEST'):
                package_members(path, expected | {'files': {'backend/application.jar': '0'*64}})
            path.write_bytes(b'substituted')
            with self.assertRaisesRegex(ValueError, 'PACKAGE_DIGEST'):
                package_members(path, expected)

    def test_semver_boundaries(self):
        package = {'ecosystem': 'npm', 'name': 'example'}
        advisory = {'affected': [{'package': package, 'ranges': [
            {'type': 'SEMVER', 'events': [{'introduced': '1.2.0'}, {'fixed': '1.3.0'}]}]}]}
        for version, outcome in [('1.1.9', 'VERSION_OUTSIDE_AFFECTED_RANGE'),
                                 ('1.2.0', 'CONFIRMED_AFFECTED_VERSION'),
                                 ('1.3.0', 'VERSION_OUTSIDE_AFFECTED_RANGE'),
                                 ('1.3.0-rc.1', 'VERSION_COMPARISON_UNSUPPORTED')]:
            self.assertEqual(version_status(package | {'version': version}, advisory), outcome)

    def test_maven_range_requires_supported_comparator_or_exact_version(self):
        package = {'ecosystem': 'Maven', 'name': 'org.example:example'}
        component = package | {'version': '1.0'}
        entry = {'package': package, 'ranges': [{'type': 'ECOSYSTEM'}]}
        self.assertEqual(version_status(component, {'affected': [entry]}), 'VERSION_COMPARISON_UNSUPPORTED')
        self.assertEqual(version_status(component, {'affected': [entry | {'versions': ['1.0']}]}),
                         'CONFIRMED_AFFECTED_VERSION')
        self.assertEqual(version_status(component, {'affected': []}), 'ADVISORY_DATA_INCOMPLETE')
