"""Real fixed-commit export and fail-closed prerequisite regressions; no database."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import tempfile
import unittest

from engineering.ci import phase6_v3_hosted as hosted

ROOT = Path(__file__).resolve().parents[2]


class V3HostedTests(unittest.TestCase):
    def test_real_commit_export_retains_external_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            # Preserved exact artifact, checked in without reconstruction.
            external = ROOT / 'engineering/ci/inputs/phase6-wave3-cumulative.patch'
            hosted.verify_patch(external)
            source = hosted.export_candidate(ROOT, base / 'source', external)
            self.assertFalse((source / '.git').exists())
            files = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in source.rglob('*') if p.is_file()}
            self.assertEqual(905, len(files))
            digest = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            self.assertEqual(hosted.CANDIDATE, digest)
            self.assertEqual(hosted.MANIFEST, files[hosted.MANIFEST_PATH])
            self.assertNotIn('engineering/ci/phase6_v3_hosted.py', files)
            with self.assertRaises(FileExistsError):
                hosted.export_candidate(ROOT, source, external)

    def test_missing_wrong_and_symlink_patch_fail_before_export(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            wrong = base / 'wrong'; wrong.write_text('not the reviewed patch')
            link = base / 'link'; link.symlink_to(wrong)
            for path in (wrong, link, base / 'missing'):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    hosted.export_candidate(ROOT, base / 'export', path)
                self.assertFalse((base / 'export').exists())

    def test_only_exact_baseline_checkout_conversion_is_allowed(self):
        data = b'{"reference":1}\n'
        expected = hashlib.sha256(data.replace(b'\n', b'\r\n')).hexdigest()
        name = 'test-corpus/canonical/reference.json'
        self.assertEqual(data.replace(b'\n', b'\r\n'), hosted.restore_checkout_bytes(name, data, {name: expected}))
        self.assertEqual(data, hosted.restore_checkout_bytes(name, data, {name: '0' * 64}))
        self.assertEqual(data, hosted.restore_checkout_bytes('other.json', data, {'other.json': expected}))
        mixed_name = 'test-corpus/semantic/cases.json'
        mixed = b'{\r\n  "value": "99.0.0"\n}\r\n'
        lf = mixed.replace(b'\r\n', b'\n')
        self.assertEqual(mixed, hosted.restore_checkout_bytes(mixed_name, lf, {mixed_name: hashlib.sha256(mixed).hexdigest()}))

    def test_actual_runtime_is_not_silently_relaxed(self):
        if platform.python_version() != '3.14.7' or platform.python_implementation() != 'CPython':
            with self.assertRaisesRegex(ValueError, 'MISSING_PINNED_CPYTHON'):
                hosted.prerequisites(ROOT)
        else:
            # A pinned runtime must either expose all exact dependencies or fail closed.
            expected = dict(line.split('==') for line in (ROOT / 'tooling/requirements.txt').read_text().splitlines()
                            if line and not line.startswith('#'))
            try:
                actual = {name: importlib.metadata.version(name) for name in expected}
            except importlib.metadata.PackageNotFoundError:
                with self.assertRaisesRegex(ValueError, 'PREPROVISIONED_DEPENDENCY'):
                    hosted.prerequisites(ROOT)
            else:
                if actual != expected:
                    with self.assertRaisesRegex(ValueError, 'PREPROVISIONED_DEPENDENCY'):
                        hosted.prerequisites(ROOT)
                else:
                    self.assertEqual(expected, hosted.prerequisites(ROOT))

    def test_hosted_provisioning_is_runner_scoped_and_source_bound(self):
        workflow = (ROOT / '.github/workflows/phase6-v3-offline.yml').read_text()
        self.assertIn("python-version: '3.14.7'", workflow)
        self.assertIn('fetch-depth: 0', workflow)
        self.assertIn(hosted.COMMIT + ':tooling/requirements.txt', workflow)
        self.assertIn('"$RUNNER_TEMP/acp-v3-venv/bin/python3.14" -m pip install --only-binary=:all:', workflow)
        self.assertIn('"$RUNNER_TEMP/acp-v3-venv/bin/python3.14" -m pip check', workflow)
        self.assertIn(hosted.PATCH, workflow)
        self.assertNotIn('ACP_PHASE6_WAVE3_PATCH_URL', workflow)
        self.assertNotIn('curl ', workflow)
        self.assertNotIn('continue-on-error', workflow)
        self.assertNotIn('services:', workflow)
        attributes = (ROOT / 'engineering/ci/inputs/.gitattributes').read_text()
        self.assertIn('phase6-wave3-cumulative.patch binary', attributes)
