"""Adversarial H9.1 toolchain checks; real approved Maven executes only in CI."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from engineering.dependency_resolution import maven_toolchain as m


class MavenTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='acp-maven-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'maven'
        self.root.mkdir(); (self.root / 'bin').mkdir()
        (self.root / 'bin/mvn').write_bytes(b'approved executable'); (self.root / 'bin/mvn').chmod(0o755)
        self.files = m.inventory(self.root)

    def test_missing_and_untrusted_digest(self):
        for c in ({}, {'sha256': '0' * 64, 'sha512': m.SHA512}):
            with self.assertRaisesRegex(ValueError, 'UNTRUSTED'): m.archive_bytes(b'bytes', c)

    def test_substituted_archive(self):
        with self.assertRaisesRegex(ValueError, 'ARCHIVE_SUBSTITUTION'):
            m.archive_bytes(b'wrong bytes', m.configuration())

    def test_both_digests_required_before_extraction(self):
        with patch.object(m.hashlib, 'sha256') as h:
            h.return_value.hexdigest.return_value = m.SHA256
            with self.assertRaisesRegex(ValueError, 'ARCHIVE_SUBSTITUTION'):
                m.archive_bytes(b'wrong sha512', m.configuration())

    def test_valid_executable_selection(self):
        self.assertEqual(m.selected(self.root, self.files, str(self.root / 'bin')), self.root / 'bin/mvn')

    def test_wrong_precedence(self):
        other = self.root.parent / 'wrong'; other.mkdir(); (other / 'mvn').write_text('wrong'); (other / 'mvn').chmod(0o755)
        with self.assertRaisesRegex(ValueError, 'PRECEDENCE'):
            m.selected(self.root, self.files, str(other) + os.pathsep + str(self.root / 'bin'))

    def test_executable_substitution(self):
        (self.root / 'bin/mvn').write_bytes(b'substitution')
        with self.assertRaisesRegex(ValueError, 'CONTENTS'): m.selected(self.root, self.files)

    def test_modified_distribution(self):
        (self.root / 'extra').write_text('added')
        with self.assertRaisesRegex(ValueError, 'CONTENTS'): m.selected(self.root, self.files)

    def test_escaping_symlink(self):
        (self.root / 'bin/mvn').unlink(); (self.root / 'bin/mvn').symlink_to('/bin/sh')
        with self.assertRaisesRegex(ValueError, 'SYMLINK'): m.selected(self.root, self.files)

    def test_symlink_root(self):
        alias = self.root.parent / 'alias'; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'ROOT_BINDING'): m.selected(alias, self.files)

    def test_wrong_version(self):
        for v in ('Apache Maven 3.10.1 (other)', 'Apache Maven 3.10.0-evil (x)'):
            with patch.object(m.subprocess, 'check_output', return_value=v):
                with self.assertRaisesRegex(ValueError, 'MAVEN_VERSION'): m.version(self.root / 'bin/mvn')

    def test_valid_version_contract(self):
        v = 'Apache Maven 3.10.0 (c43a36b8d67be7e0805a411bc0898af1a51f5472)\n'
        with patch.object(m.subprocess, 'check_output', return_value=v): self.assertEqual(m.version(self.root / 'bin/mvn'), v)

    def test_stale_source_or_artifact_receipt(self):
        r = {'source': m.binding(), 'root': str(self.root), 'archiveSHA256': m.SHA256,
             'archiveSHA512': m.SHA512, 'files': m.configuration()['files']}
        for key in ('source', 'archiveSHA256', 'files', 'root'):
            bad = copy.deepcopy(r); bad[key] = {} if isinstance(r[key], dict) else 'wrong'
            p = self.root.parent / 'receipt.json'; p.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, 'STALE_OR_MISMATCHED'): m.verify(self.root, p)

    def test_mismatched_toolchain_inventory(self):
        r = {'source': m.binding(), 'root': str(self.root), 'archiveSHA256': m.SHA256,
             'archiveSHA512': m.SHA512, 'files': m.configuration()['files'], 'versionOutput': 'different output'}
        p = self.root.parent / 'receipt.json'; p.write_text(json.dumps(r))
        with patch.object(m, 'selected', return_value=self.root / 'bin/mvn'), patch.object(m, 'version', return_value='actual output'):
            with self.assertRaisesRegex(ValueError, 'TOOLCHAIN_INVENTORY'): m.verify(self.root, p)

    def test_archive_paths_and_symlinks(self):
        for name, mode in (('../escape', 0o100644), ('apache-maven-3.10.0/link', 0o120777)):
            raw = io.BytesIO()
            with zipfile.ZipFile(raw, 'w') as z:
                i = zipfile.ZipInfo(name); i.external_attr = mode << 16; z.writestr(i, b'/bin/sh')
            with self.assertRaisesRegex(ValueError, 'ARCHIVE_PATH'): m.extract(raw.getvalue(), self.root.parent / 'out', {})

    def test_archive_inventory_rejection(self):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as z: z.writestr('apache-maven-3.10.0/bin/mvn', b'wrong')
        with self.assertRaisesRegex(ValueError, 'CONTENTS'): m.extract(raw.getvalue(), self.root.parent / 'out', self.files)
        self.assertFalse((self.root.parent / 'out').exists())

    def test_scoped_reference_inventory(self):
        c = m.configuration()
        self.assertEqual(len(c['files']), 113)
        self.assertEqual(c['inventorySource']['run'], 43679701552)
        self.assertEqual(c['scope'], 'H9.1_ENGINEERING_QUALIFICATION_ONLY')

    def test_ambient_selection_is_observation_not_approved_identity(self):
        with patch.object(m.shutil, 'which', return_value='/usr/bin/mvn'), patch.object(m.subprocess, 'check_output', return_value='Apache Maven 3.10.1 (runner)'):
            result = m.ambient_observation()
        self.assertEqual(result['executable'], '/usr/bin/mvn')
        self.assertIn('3.10.1', result['versionOutput'])

    def test_workflow_keeps_original_qualification(self):
        workflow = (m.ROOT / '.github/workflows/phase6-v3-offline.yml').read_text()
        job = workflow.split('  successor-dependency-determinism:', 1)[1].split('  successor-performance-scaling:', 1)[0]
        self.assertIn('maven_toolchain.py provision', job)
        self.assertEqual(job.count('maven_toolchain.py verify'), 3)
        self.assertIn('suite.countTestCases() == 24', job)
        self.assertIn('qualify.py qualify', job)
        self.assertNotIn('continue-on-error', job)


if __name__ == '__main__': unittest.main()
