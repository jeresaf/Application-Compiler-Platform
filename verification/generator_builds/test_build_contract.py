"""Fail-closed runner and hosted wiring regressions; real builds run separately."""
import ast
from pathlib import Path
import tempfile
import subprocess
import unittest
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engineering.generator_builds.qualify import sha, qualify, reject_substituted_source


class BuildContractTests(unittest.TestCase):
    def test_digest_rejects_missing_and_symlink_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source'
            with self.assertRaises(ValueError): sha(path)
            path.write_bytes(b'exact')
            self.assertEqual(len(sha(path)), 64)
            link = Path(directory) / 'link'
            link.symlink_to(path)
            with self.assertRaises(ValueError): sha(link)

    def test_workspace_collision_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileExistsError): qualify(directory)

    def test_runner_builds_generated_workspaces_without_database_execution(self):
        source = (ROOT / 'engineering/generator_builds/qualify.py').read_text()
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        commands = [ast.literal_eval(node.args[0]) for node in calls
                    if isinstance(node.func, ast.Name) and node.func.id == 'run' and isinstance(node.args[0], ast.List)]
        self.assertIn(['mvn', '-B', '-ntp', 'clean', 'test-compile'], commands)
        self.assertIn(['npm', 'run', 'build'], commands)
        self.assertIn(['npm', 'run', 'typecheck'], commands)
        self.assertNotIn('spring-boot:run', source)
        self.assertNotIn('psql', source)
        self.assertEqual(source.count('candidate.verify_materialized('), 2)
        self.assertIn('BUILD_MODIFIED_GENERATED_SOURCE', source)
        self.assertIn('NONREPRODUCIBLE_PLAN', source)

    def test_consumption_probe_requires_rejection_and_restores_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source'
            path.write_bytes(b'exact')
            reject_substituted_source(path, [sys.executable, '-c', 'raise SystemExit(1)'], directory)
            self.assertEqual(path.read_bytes(), b'exact')
            with self.assertRaisesRegex(ValueError, 'BUILD_DID_NOT_CONSUME_SOURCE'):
                reject_substituted_source(path, [sys.executable, '-c', 'pass'], directory)
            self.assertEqual(path.read_bytes(), b'exact')

    def test_hosted_job_is_mandatory_and_retains_evidence(self):
        workflow = (ROOT / '.github/workflows/phase6-v3-offline.yml').read_text()
        self.assertIn('successor-application-builds:', workflow)
        job = workflow.split('  successor-application-builds:', 1)[1]
        self.assertIn("python-version: '3.14.7'", job)
        self.assertIn("node-version: '24.21.0'", job)
        self.assertIn('engineering/generator_builds/qualify.py', job)
        self.assertNotIn('continue-on-error', job)
        self.assertIn('if: always()', job)
