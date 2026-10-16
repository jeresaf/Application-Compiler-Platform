"""Stage 1 must add only authorized paths and preserve every pinned baseline byte."""
import ast
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
BASELINE='c1a201c779621963b0334a1bee4423b23315884f'
ALLOWED=('engineering/evidence_admission/', 'verification/evidence_admission/')
DOC='docs/phase6-evidence-admission-contract.md'
BLOCKERS=[5,8,9,10,12,13,14,15,18,20,21,22,24,25,26,27,28,30,31,32,33]
STAGE2A_FILES={
 'engineering/evidence_admission/signatures.py',
 'engineering/evidence_admission/trust.py',
 'engineering/evidence_admission/registration.py',
 'engineering/evidence_admission/requirements.txt',
 'verification/evidence_admission/stage2a/lab_fixtures.py',
 'verification/evidence_admission/stage2a/test_signatures.py',
 'verification/evidence_admission/stage2a/test_trust.py',
 'verification/evidence_admission/stage2a/test_registration.py',
 'docs/phase6-evidence-admission-stage2a.md',
}
STAGE2B1_FILES={
 'engineering/evidence_admission/execution_context.py',
 'engineering/evidence_admission/challenge.py',
 'engineering/evidence_admission/execution_ledger.py',
 'verification/evidence_admission/stage2b/lab_fixtures.py',
 'verification/evidence_admission/stage2b/test_challenge.py',
 'verification/evidence_admission/stage2b/test_execution_ledger.py',
 'docs/phase6-evidence-admission-stage2b.md',
}
STAGE2B2_FILES={
 'engineering/evidence_admission/host_capabilities.py',
 'engineering/evidence_admission/isolation.py',
 'verification/evidence_admission/stage2b2/lab_fixtures.py',
 'verification/evidence_admission/stage2b2/test_host_capabilities.py',
 'verification/evidence_admission/stage2b2/test_isolation.py',
 'docs/phase6-evidence-admission-stage2b2.md',
}
CI_STAGE2A_STEPS=b"""      - name: Install isolated Stage 2A laboratory dependencies
        shell: bash
        run: |
          set -euo pipefail
          python3.14 -m venv "$RUNNER_TEMP/acp-stage2a-venv"
          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" -m pip install --require-hashes --only-binary=:all: --report "$RUNNER_TEMP/acp-stage2a-install.json" -r engineering/evidence_admission/requirements.txt
          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" -m pip check
          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" -m pip list --format=json > "$RUNNER_TEMP/acp-stage2a-packages.json"
          cat "$RUNNER_TEMP/acp-stage2a-packages.json"
          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" - <<'PYTHON'
          import importlib.metadata as metadata
          import json, os, platform
          from pathlib import Path
          from cryptography.hazmat.backends.openssl.backend import backend
          assert platform.python_version() == '3.14.7', 'WRONG_PYTHON'
          requirements = Path('engineering/evidence_admission/requirements.txt').read_text().splitlines()
          expected = dict(line.split()[0].split('==') for line in requirements if line and not line.startswith('#'))
          for name, version in expected.items():
              assert metadata.version(name) == version, ('WRONG_PACKAGE', name)
          report = json.loads((Path(os.environ['RUNNER_TEMP']) / 'acp-stage2a-install.json').read_text())
          installed = report['install']
          assert len(installed) == len(expected), 'INCOMPLETE_WHEEL_INSTALL'
          for item in installed:
              download = item['download_info']
              assert download['url'].split('?')[0].endswith('.whl'), 'SOURCE_BUILD_FORBIDDEN'
              assert 'sha256' in download['archive_info']['hashes'], 'MISSING_WHEEL_HASH'
          openssl = backend.openssl_version_text()
          assert openssl == 'OpenSSL 4.0.3 29 Sep 2026', ('WRONG_BUNDLED_OPENSSL', openssl)
          print(json.dumps({'python': platform.python_version(), 'lockedPackages': expected, 'bundledOpenSSL': openssl}, sort_keys=True))
          PYTHON
      - name: Verify Stage 2A laboratory verifier registration
        shell: bash
        run: |
          set -euo pipefail
          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" - <<'PYTHON'
          import unittest
          from pathlib import Path
          directory = Path('verification/evidence_admission/stage2a')
          expected = {'test_signatures.py', 'test_trust.py', 'test_registration.py'}
          assert {path.name for path in directory.glob('test*.py')} == expected, 'STAGE2A_TEST_FILES'
          suite = unittest.defaultTestLoader.discover(str(directory))
          assert suite.countTestCases() == 52, 'STAGE2A_TEST_COUNT'
          PYTHON
          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" -m unittest discover -s verification/evidence_admission/stage2a -v
"""
CI_STAGE2B_STEPS=b"""      - name: Verify Stage 2B-1 laboratory challenges and durable reservations
        shell: bash
        run: |
          set -euo pipefail
          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" - <<'PYTHON'
          import unittest
          from pathlib import Path
          directory = Path('verification/evidence_admission/stage2b')
          expected = {'test_challenge.py', 'test_execution_ledger.py'}
          assert {path.name for path in directory.glob('test*.py')} == expected, 'STAGE2B_TEST_FILES'
          assert all((directory / name).is_file() and not (directory / name).is_symlink() for name in expected), 'STAGE2B_TEST_FILES'
          suite = unittest.defaultTestLoader.discover(str(directory))
          assert suite.countTestCases() == 47, 'STAGE2B_TEST_COUNT'
          PYTHON
          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" -m unittest discover -s verification/evidence_admission/stage2b -v 2>&1 | tee "$RUNNER_TEMP/acp-stage2b-tests.log"
          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" - <<'PYTHON'
          import os, re
          from pathlib import Path
          log = (Path(os.environ['RUNNER_TEMP']) / 'acp-stage2b-tests.log').read_text()
          assert re.findall(r'^Ran ([0-9]+) tests in .+$', log, re.MULTILINE) == ['47'], 'STAGE2B_EXECUTED_COUNT'
          assert log.rstrip().splitlines()[-1] == 'OK', 'STAGE2B_FAILURE_OR_SKIP'
          PYTHON
"""
F20_EXACT_HASHES={'engineering/evidence_admission/challenge.py': '65fab7f23f1fce5fd45c4cae9e03889c91c365b93178073297872ce0a77b376d', 'verification/evidence_admission/stage2b/test_challenge.py': '543bc6f5d539e063b4bb6ff905c1597d9b7054750c351e64f218ad4b9ac1c873', 'docs/phase6-evidence-admission-stage2b.md': '59fd5f545cb11a3d39383f0149d63b877bd619bd4c7a3f633b7a083cba91d027'}
# Existing local checkout representations, observed without rewriting any corpus.
# Fresh LF checkouts must match the Git blob; only these exact existing byte
# hashes are permitted as alternatives, never arbitrary normalized file changes.
CHECKOUT_FORMS={
 'test-corpus/canonical/byte-vectors.json':'25a205fe39eb4d2bbf435765110679880de8e99e0d5a39e9cbdd38bfc14158ea',
 'test-corpus/canonical/case-management.json':'6092dfba10dc94cafbb42e738d2ee94a379b6ca082f303f5b4a2dc61a3690d08',
 'test-corpus/canonical/manifest.json':'3ae456668c9ed03052e41e9a6ac8bf9b859ac0230443d943ca00d1fe50ed8215',
 'test-corpus/canonical/payment.json':'dc9ac48b6437182f2cc83d5c522e59bfacd018dbcbfa682391df4264fd0f537b',
 'test-corpus/change/evolution.json':'000703f0ad15085ab8e1e047a662e5a7b8ee212cb852e5ea198129f97a70f1a5',
 'test-corpus/phase1/case-management.json':'95f245c9b53550a778258e4effc7ff5511c9eb431f3f9a2a5ef7438073c38ca5',
 'test-corpus/phase1/cases.json':'c4fa5a1e6608ff99a0b7509f340bc8dc0d725a6f7269594ae38170b8261335a8',
 'test-corpus/phase1/payment.json':'4c08bcd214a7a83ae36e41008a0ceda0b9ee977040f76c226a95c3e697927c56',
 'test-corpus/semantic/approved.json':'c1ccc5692d0aa7e41cc46006ae8b6f73dc2a0351ae74b018f44d2a6a3ae3ea8f',
 'test-corpus/semantic/cases.json':'a7f7c16a63664acccb629a0afab08a990a118390708272d30f0942dc9a1572d0',
 'test-corpus/semantic/reference.json':'84c6c27469f7dc439c6b8b7f74631782c0880b398795e21e71ded1f381fe6b7a',
}


# Exact reviewed CI-only additions; no directory-wide exception.
V3_CI_HASHES = {'.github/workflows/phase6-v3-offline.yml': '9517940c14fa95ad7e18bebc5d0c967b9181f82b0452243f68569cbbc2f91fe8', 'engineering/ci/PHASE6-QUALIFICATION.md': '39123fef8ac3a409e369c0b8a4f2ac979e793306983ebc56ec2d57eb0e037791', 'engineering/ci/inputs/.gitattributes': '83c5641d9288aad3c12c13948066115cf115c27ca77b5f86ef986b11b6f9d1cb', 'engineering/ci/inputs/phase6-wave3-cumulative.patch': '9706ba0c436f57560b0e8ace897cee7f1f258c2d40870e8bf1c9c2da70b791c8', 'engineering/ci/phase6-qualification-ci.json': 'c15dbb6fa1226fb22eb28a406ef54f12a1455013d350014794ae0570a6dc90fd', 'engineering/ci/phase6-qualification-manifest.json': '5033d915410e8f2eaf4d53f4a041795c931bb57c36abdf105ba88f57298176e6', 'engineering/ci/phase6_postgresql.py': 'ab32cc6d2146bcf0a5063b06c13e899a8c970e348c32b00380ec5e4b1efe32ec', 'engineering/ci/phase6_qualification.py': '4c01248510d0196af8d1255d3b000d49e6a7d23893daa40f8e0bf0354b0021e9', 'engineering/ci/phase6_v3_hosted.py': 'a60fcccb86b9736f9e620c268eb18617b7b9147d23048801c7ab9add083e1fd5', 'verification/phase6_v3_ci/test_phase6_v3_hosted.py': 'c790db7475c0d95e3fe377c141c2823892ed519df7395fac9895eb802d0a3844'}


def ci_legacy_tree(tree):
    """Project only the exact CI allowance out of historical method comparisons."""
    import copy
    predicate = ast.dump(ast.parse('self.verified_ci_additions()', mode='eval').body)
    class Projection(ast.NodeTransformer):
        def visit_BinOp(self, node):
            if isinstance(node.op, ast.Sub) and ast.dump(node.right) == predicate:
                return self.visit(node.left)
            return self.generic_visit(node)
        def visit_BoolOp(self, node):
            node = self.generic_visit(node)
            node.values = [value for value in node.values
                           if not (isinstance(value, ast.Compare) and len(value.comparators) == 1
                                   and isinstance(value.ops[0], ast.In)
                                   and ast.dump(value.comparators[0]) == predicate)]
            return node.values[0] if len(node.values) == 1 else node
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == 'ci_legacy_tree':
                return self.visit(node.args[0])
            return self.generic_visit(node)
    return Projection().visit(copy.deepcopy(tree))


class PreservationTests(unittest.TestCase):
    def verified_ci_additions(self):
        for relative, expected in V3_CI_HASHES.items():
            path = ROOT / relative
            self.assertFalse(path.is_symlink(), relative)
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected, relative)
            self.assertFalse(path.stat().st_mode & 0o111, relative)
        return set(V3_CI_HASHES)

    def test_exact_v3_ci_allowance_rejects_modified_missing_and_symlink_input(self):
        self.assertEqual(len(self.verified_ci_additions()), 10)
        path = ROOT / 'engineering/ci/inputs/phase6-wave3-cumulative.patch'
        original_read = Path.read_bytes
        with patch.object(Path, 'read_bytes', lambda item: b'changed' if item == path else original_read(item)):
            with self.assertRaises(AssertionError):self.verified_ci_additions()
        original_file = Path.is_file
        with patch.object(Path, 'is_file', lambda item: False if item == path else original_file(item)):
            with self.assertRaises(AssertionError):self.verified_ci_additions()
        original_link = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda item: True if item == path else original_link(item)):
            with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_stage2b2_exact_inventory_and_accepted_source(self):
        accepted='91181e1c62cfc6be6b82d64bc86f8d4f7166d09c'
        additions=set(subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
        additions.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        if '.ci-evidence/contracts.json' in additions:
            self.check_source_additions(['.ci-evidence/contracts.json'],[],subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
            self.assertNotIn('.ci-evidence/contracts.json',subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
            additions.remove('.ci-evidence/contracts.json')
        self.assertEqual(additions-self.verified_ci_additions(),STAGE2B2_FILES)
        self.assertEqual(set(subprocess.check_output(['git','diff','--name-only','--diff-filter=MDRT',accepted,'--'],cwd=ROOT,text=True).splitlines()),{'verification/evidence_admission/test_preservation.py'})
        listing=subprocess.check_output(['git','ls-tree','-r','-z',accepted],cwd=ROOT)
        for row in listing.split(b'\0'):
            if not row:continue
            metadata,name=row.split(b'\t',1);relative=name.decode()
            if relative=='verification/evidence_admission/test_preservation.py':continue
            mode,kind,digest=metadata.split();path=ROOT/relative
            expected=subprocess.check_output(['git','cat-file','blob',digest.decode()],cwd=ROOT)
            actual=path.read_bytes()
            with self.subTest(path=relative):
                self.assertFalse(path.is_symlink());self.assertEqual(kind,b'blob')
                if actual!=expected:
                    self.assertEqual(hashlib.sha256(actual).hexdigest(),CHECKOUT_FORMS.get(relative))
                    self.assertEqual(actual.replace(b'\r\n',b'\n'),expected.replace(b'\r\n',b'\n'))
                self.assertEqual(bool(path.stat().st_mode & 0o111),mode==b'100755')

    def test_stage2b_final_exact_correction_and_workflow(self):
        accepted='ea5683c36300481f9d3a7a473290ec3e5923af6d'
        expected_changes=set(F20_EXACT_HASHES)|{'.github/workflows/acp-contracts.yml','verification/evidence_admission/test_preservation.py'}
        changes=set(subprocess.check_output(['git','diff','--name-only',accepted,'--'],cwd=ROOT,text=True).splitlines())
        self.assertEqual(changes-STAGE2B2_FILES-self.verified_ci_additions(),expected_changes)
        additions=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
        for addition in additions:
            if addition in STAGE2B2_FILES or addition in self.verified_ci_additions():continue
            self.assertEqual(addition,'.ci-evidence/contracts.json')
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            self.check_source_additions([addition],[],head)
        self.assertEqual(set(F20_EXACT_HASHES),{'engineering/evidence_admission/challenge.py',
            'verification/evidence_admission/stage2b/test_challenge.py','docs/phase6-evidence-admission-stage2b.md'})
        for relative,digest in F20_EXACT_HASHES.items():
            self.assertEqual(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest(),digest,relative)
        workflow='.github/workflows/acp-contracts.yml'
        baseline=subprocess.check_output(['git','show',accepted+':'+workflow],cwd=ROOT)
        self.assertEqual((ROOT/workflow).read_bytes(),baseline.replace(b'\n  phase5-experiments:',CI_STAGE2B_STEPS+b'\n  phase5-experiments:',1))
        # Every other accepted tracked byte and mode is still enforced by the
        # earlier baseline comparisons, plus this exact current-baseline pass.
        listing=subprocess.check_output(['git','ls-tree','-r','-z',accepted],cwd=ROOT)
        for row in listing.split(b'\0'):
            if not row:continue
            metadata,name=row.split(b'\t',1);relative=name.decode()
            if relative in expected_changes:continue
            mode,kind,digest=metadata.split();path=ROOT/relative
            expected=subprocess.check_output(['git','cat-file','blob',digest.decode()],cwd=ROOT)
            actual=path.read_bytes()
            with self.subTest(path=relative):
                self.assertFalse(path.is_symlink());self.assertEqual(kind,b'blob')
                if actual!=expected:
                    self.assertEqual(hashlib.sha256(actual).hexdigest(),CHECKOUT_FORMS.get(relative))
                    self.assertEqual(actual.replace(b'\r\n',b'\n'),expected.replace(b'\r\n',b'\n'))
                self.assertEqual(bool(path.stat().st_mode & 0o111),mode==b'100755')

    def test_stage2b_ci_rejects_weakened_guards(self):
        workflow=ROOT/'.github/workflows/acp-contracts.yml';original=workflow.read_bytes()
        for old,new in [(b"suite.countTestCases() == 47",b"suite.countTestCases() >= 0"),
                        (b"{'test_challenge.py', 'test_execution_ledger.py'}",b"{'test_challenge.py'}"),
                        (b"log.rstrip().splitlines()[-1] == 'OK'",b"True"),
                        (b'-s verification/evidence_admission/stage2b -v 2>&1 | tee',b'-s missing-tests -v 2>&1 | tee')]:
            self.assertIn(old,original);changed=original.replace(old,new,1);real_read=Path.read_bytes
            with self.subTest(change=old),patch.object(Path,'read_bytes',lambda path:changed if path==workflow else real_read(path)):
                probe=PreservationTests('test_baseline_bytes_and_pinned_existing_checkout_forms')
                with self.assertRaises(AssertionError):probe.test_baseline_bytes_and_pinned_existing_checkout_forms()

    def test_stage2b1_exact_inventory_and_accepted_methods(self):
        accepted='1db415af4486bb03392978d07091afd609fe9f02'
        additions=set(subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
        additions.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        if '.ci-evidence/contracts.json' in additions:
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            self.check_source_additions(['.ci-evidence/contracts.json'],[],head)
            self.assertNotIn('.ci-evidence/contracts.json',subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
            additions.remove('.ci-evidence/contracts.json')
        self.assertEqual(additions-self.verified_ci_additions(),STAGE2B1_FILES | STAGE2B2_FILES)
        modified=set(subprocess.check_output(['git','diff','--name-only','--diff-filter=MDRT',accepted,'--'],cwd=ROOT,text=True).splitlines())
        self.assertEqual(modified,{'verification/evidence_admission/test_preservation.py', '.github/workflows/acp-contracts.yml'})
        path='verification/evidence_admission/test_preservation.py'
        before=subprocess.check_output(['git','show',accepted+':'+path],cwd=ROOT,text=True)
        # These three exact inventory predicate changes are the entire exception.
        before=before.replace('self.assertEqual(additions,STAGE2A_FILES)',
                              'self.assertEqual(additions,STAGE2A_FILES | STAGE2B1_FILES | STAGE2B2_FILES)',1)
        before=before.replace("call.args[0].values.append(ast.parse('path in STAGE2A_FILES',mode='eval').body)",
                              "call.args[0].values.append(ast.parse('path in STAGE2A_FILES',mode='eval').body)\n                        call.args[0].values.append(ast.parse('path in STAGE2B1_FILES',mode='eval').body)",1)
        before=before.replace('or path in STAGE2A_FILES,path', 'or path in STAGE2A_FILES or path in STAGE2B1_FILES or path in STAGE2B2_FILES,path')
        before=before.replace('step+CI_STAGE2A_STEPS+marker','step+CI_STAGE2A_STEPS+CI_STAGE2B_STEPS+marker')
        before=before.replace('self.assertEqual(additions,STAGE2A_FILES | STAGE2B1_FILES)',
                              'self.assertEqual(additions,STAGE2A_FILES | STAGE2B1_FILES | STAGE2B2_FILES)',1)
        before=before.replace("call.args[0].values.append(ast.parse('path in STAGE2B1_FILES',mode='eval').body)",
                              "call.args[0].values.append(ast.parse('path in STAGE2B1_FILES',mode='eval').body)\n                        call.args[0].values.append(ast.parse('path in STAGE2B2_FILES',mode='eval').body)",1)
        old=ast.parse(before);new=ast.parse((ROOT/path).read_text())
        new_methods={n.name:ast.dump(ci_legacy_tree(n)) for c in new.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef)}
        for node in old.body:
            if isinstance(node,ast.ClassDef):
                for method in node.body:
                    if isinstance(method,ast.FunctionDef):self.assertEqual(ast.dump(method),new_methods[method.name],method.name)
            else:self.assertIn(ast.dump(node),[ast.dump(n) for n in new.body])
        # Compare every other accepted file byte-for-byte with the checkout,
        # retaining only the already pinned local checkout representations.
        listing=subprocess.check_output(['git','ls-tree','-r','-z',accepted],cwd=ROOT)
        for row in listing.split(b'\0'):
            if not row:continue
            metadata,name=row.split(b'\t',1);relative=name.decode()
            if relative==path:continue
            mode,kind,digest=metadata.split()
            expected=subprocess.check_output(['git','cat-file','blob',digest.decode()],cwd=ROOT)
            if relative=='.github/workflows/acp-contracts.yml':
                expected=expected.replace(b'\n  phase5-experiments:',CI_STAGE2B_STEPS+b'\n  phase5-experiments:',1)
            actual=(ROOT/relative).read_bytes()
            with self.subTest(path=relative):
                self.assertFalse((ROOT/relative).is_symlink());self.assertEqual(kind,b'blob')
                if actual!=expected:
                    self.assertEqual(hashlib.sha256(actual).hexdigest(),CHECKOUT_FORMS.get(relative))
                    self.assertEqual(actual.replace(b'\r\n',b'\n'),expected.replace(b'\r\n',b'\n'))
                self.assertEqual(bool((ROOT/relative).stat().st_mode & 0o111),mode==b'100755')

    def test_stage2a_exact_inventory_preserves_accepted_stage1(self):
        accepted='f44f8952ba7e86f879b0c21e1b56de9fbd3d01aa'
        additions=set(subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
        additions.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        # Retain only the pre-existing, separately validated transient exception.
        if '.ci-evidence/contracts.json' in additions:
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            self.check_source_additions(['.ci-evidence/contracts.json'],[],head)
            self.assertNotIn('.ci-evidence/contracts.json',subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
            additions.remove('.ci-evidence/contracts.json')
        self.assertEqual(additions-self.verified_ci_additions(),STAGE2A_FILES | STAGE2B1_FILES | STAGE2B2_FILES)
        modified=set(subprocess.check_output(['git','diff','--name-only','--diff-filter=MDRT',accepted,'--'],cwd=ROOT,text=True).splitlines())
        self.assertEqual(modified,{'verification/evidence_admission/test_preservation.py', '.github/workflows/acp-contracts.yml'})
        path='verification/evidence_admission/test_preservation.py'
        before=ast.parse(subprocess.check_output(['git','show',accepted+':'+path],cwd=ROOT,text=True))
        after=ast.parse((ROOT/path).read_text())
        old_class=next(n for n in before.body if isinstance(n,ast.ClassDef))
        new_class=next(n for n in after.body if isinstance(n,ast.ClassDef))
        methods={n.name:n for n in new_class.body if isinstance(n,ast.FunctionDef)}
        for method in old_class.body:
            if isinstance(method,ast.FunctionDef):
                if method.name=='check_source_additions':
                    calls=[n for n in ast.walk(method) if isinstance(n,ast.Call) and
                           isinstance(n.func,ast.Attribute) and n.func.attr=='assertTrue']
                    self.assertEqual(len(calls),2)
                    for call in calls:
                        self.assertIsInstance(call.args[0],ast.BoolOp)
                        call.args[0].values.append(ast.parse('path in STAGE2A_FILES',mode='eval').body)
                        call.args[0].values.append(ast.parse('path in STAGE2B1_FILES',mode='eval').body)
                        call.args[0].values.append(ast.parse('path in STAGE2B2_FILES',mode='eval').body)
                if method.name=='test_baseline_bytes_and_pinned_existing_checkout_forms':
                    class AuthorizedInsertion(ast.NodeTransformer):
                        def visit_BinOp(self,node):
                            if ast.dump(node)==ast.dump(ast.parse('step+marker',mode='eval').body):
                                return ast.parse('step+CI_STAGE2A_STEPS+CI_STAGE2B_STEPS+marker',mode='eval').body
                            return self.generic_visit(node)
                    method=AuthorizedInsertion().visit(method)
                self.assertEqual(ast.dump(method),ast.dump(ci_legacy_tree(methods[method.name])),method.name)
        for node in before.body:
            if not isinstance(node,ast.ClassDef):
                self.assertIn(ast.dump(node),[ast.dump(n) for n in after.body])

    def test_stage2a_workflow_insertion_rejects_weakened_commands(self):
        workflow=ROOT/'.github/workflows/acp-contracts.yml'
        original=workflow.read_bytes()
        for old,new in ((b'--require-hashes',b''), (b'--only-binary=:all:',b''),
                        (b"suite.countTestCases() == 52",b"suite.countTestCases() >= 0"),
                        (b"'3.14.7', 'WRONG_PYTHON'",b"'3.14.6', 'WRONG_PYTHON'"),
                        (b'"$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" -m unittest',b'python3.14 -m unittest'),
                        (b'      - name: Verify Stage 2A laboratory verifier registration',
                         b'      - continue-on-error: true\n        name: Verify Stage 2A laboratory verifier registration')):
            self.assertIn(old,original)
            changed=original.replace(old,new,1)
            real_read=Path.read_bytes
            with self.subTest(change=old),patch.object(Path,'read_bytes',lambda path:changed if path==workflow else real_read(path)):
                probe=PreservationTests('test_baseline_bytes_and_pinned_existing_checkout_forms')
                with self.assertRaises(AssertionError):probe.test_baseline_bytes_and_pinned_existing_checkout_forms()

    def check_source_additions(self, untracked, added, head):
        # Committed or staged additions never receive the transient exception.
        for path in added:self.assertTrue(path.startswith(ALLOWED) or path==DOC or path in STAGE2A_FILES or path in STAGE2B1_FILES or path in STAGE2B2_FILES or path in self.verified_ci_additions(),path)
        for path in untracked:
            if path == '.ci-evidence/contracts.json':
                self.check_contracts_binding(ROOT/path,head)
            else:self.assertTrue(path.startswith(ALLOWED) or path==DOC or path in STAGE2A_FILES or path in STAGE2B1_FILES or path in STAGE2B2_FILES or path in self.verified_ci_additions(),path)

    def check_contracts_binding(self, path, head):
        self.assertFalse(path.parent.is_symlink(),'SYMLINK_EVIDENCE_DIRECTORY')
        self.assertFalse(path.is_symlink(),'SYMLINK_EVIDENCE_FILE')
        self.assertTrue(path.is_file(),'BINDING_FILE_REQUIRED')
        self.assertLessEqual(path.stat().st_size,4096,'OVERSIZED_SOURCE_BINDING')
        def unique_pairs(pairs):
            result={}
            for key,value in pairs:
                self.assertNotIn(key,result,'DUPLICATE_BINDING_KEY')
                result[key]=value
            return result
        value=json.loads(path.read_bytes().decode('utf-8'),object_pairs_hook=unique_pairs)
        self.assertIs(type(value),dict)
        self.assertEqual(set(value),{'source','run','attempt','job'})
        for item in value.values():self.assertIs(type(item),str)
        self.assertIsNotNone(re.fullmatch(r'[0-9a-f]{40}',value['source']))
        self.assertEqual(value['source'],head,'WRONG_CHECKOUT_SOURCE')
        self.assertEqual(value['job'],'contracts','WRONG_BINDING_JOB')
        for key in ('run','attempt'):
            self.assertIsNotNone(re.fullmatch(r'[1-9][0-9]*',value[key]),'INVALID_CI_IDENTITY')
        for key,variable in (('source','GITHUB_SHA'),('run','GITHUB_RUN_ID'),
                             ('attempt','GITHUB_RUN_ATTEMPT'),('job','GITHUB_JOB')):
            if variable in os.environ:
                self.assertEqual(value[key],os.environ[variable],'WRONG_'+variable)

    def test_transient_contracts_binding_has_exact_structure_and_identity(self):
        head='a'*40
        binding={'source':head,'run':'123','attempt':'2','job':'contracts'}
        environment={'GITHUB_SHA':head,'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'2','GITHUB_JOB':'contracts'}
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,environment):
            path=Path(directory)/'contracts.json';path.write_text(json.dumps(binding))
            self.check_contracts_binding(path,head)
            for variable in environment:
                with self.subTest(environment=variable),patch.dict(os.environ,{variable:'wrong-current-identity'}):
                    with self.assertRaises(AssertionError):self.check_contracts_binding(path,head)
            for key,bad in (('source','b'*40),('run','124'),('attempt','3'),('job','phase6-target'),
                            ('run',123),('run','01'),('attempt','0'),('attempt','2\n'),('source',head+'\n')):
                value=dict(binding);value[key]=bad;path.write_text(json.dumps(value))
                with self.subTest(key=key,bad=bad),self.assertRaises(AssertionError):
                    self.check_contracts_binding(path,head)
            for missing in binding:
                value=dict(binding);del value[missing];path.write_text(json.dumps(value))
                with self.subTest(missing=missing),self.assertRaises(AssertionError):
                    self.check_contracts_binding(path,head)
            malformed=[json.dumps(dict(binding,extra=True)), 'null', '[]', '{bad',
                       '{"source":"'+head+'","source":"'+head+'","run":"123","attempt":"2","job":"contracts"}']
            for raw in malformed:
                path.write_text(raw)
                with self.subTest(raw=raw),self.assertRaises((AssertionError,ValueError)):
                    self.check_contracts_binding(path,head)
            path.write_bytes(b'\xff')
            with self.assertRaises(UnicodeError):self.check_contracts_binding(path,head)
            path.write_bytes(b' ' * 4097)
            with self.assertRaises(AssertionError):self.check_contracts_binding(path,head)

    def test_transient_exception_never_allows_tracked_or_other_files(self):
        head='a'*40
        with tempfile.TemporaryDirectory() as directory,patch(__name__+'.ROOT',Path(directory)):
            path=ROOT/'.ci-evidence/contracts.json';path.parent.mkdir()
            path.write_text(json.dumps({'source':head,'run':'123','attempt':'2','job':'contracts'}))
            # Clear only hosted identity variables for this synthetic local case.
            with patch.dict(os.environ):
                for key in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_JOB'):os.environ.pop(key,None)
                self.check_source_additions(['.ci-evidence/contracts.json'],[],head)
                for untracked,added in (([],['.ci-evidence/contracts.json']),
                                         (['.ci-evidence/contracts.json'],['.ci-evidence/contracts.json']),
                                         (['.ci-evidence/other.json'],[]),
                                         (['.ci-evidence/contracts.json.bak'],[]),
                                         (['unauthorized-source.py'],[]),
                                         ([],['unauthorized-source.py'])):
                    with self.subTest(untracked=untracked,added=added),self.assertRaises(AssertionError):
                        self.check_source_additions(untracked,added,head)
                path.write_text('{}')
                with self.assertRaises(AssertionError):self.check_source_additions(['.ci-evidence/contracts.json'],[],head)

    def test_transient_binding_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'target.json'
            target.write_text(json.dumps({'source':'a'*40,'run':'123','attempt':'2','job':'contracts'}))
            link=root/'contracts.json';link.symlink_to(target)
            with self.assertRaises(AssertionError):self.check_contracts_binding(link,'a'*40)
            real=root/'real';real.mkdir();(real/'contracts.json').write_bytes(target.read_bytes())
            alias=root/'alias';alias.symlink_to(real,target_is_directory=True)
            with self.assertRaises(AssertionError):self.check_contracts_binding(alias/'contracts.json','a'*40)

    def test_only_exact_ci_insertion_is_allowed(self):
        workflow=ROOT/'.github/workflows/acp-contracts.yml'
        original=workflow.read_bytes()
        mutations=[
            (workflow,b'node tooling/check_canonical_vectors.mjs',b'true'),
            (workflow,b'needs: [contracts, phase5c-hard-gates]',b'needs: [contracts]'),
            (workflow,b'path: .ci-evidence/contracts.json',b'path: omitted.json'),
            (workflow,b'contents: read',b'contents: write'),
            (workflow,b'run: python3.14 engineering/ci/aggregate.py hosted',b'run: true'),
            (workflow,b'      - name: Verify Stage 1 evidence contract structures\n',b'      - name: Renamed Stage 1 check\n'),
            (ROOT/'tooling/target_worker.py',b'def bundle_digest():',b'def changed_digest():'),
            (ROOT/'test-corpus/deterministic-v04/payment-canonical-candidate.json',None,None),
        ]
        real_read=Path.read_bytes
        for target,old,new in mutations:
            before=real_read(target)
            if old is not None:
                self.assertIn(old,before);changed=before.replace(old,new,1)
            else:changed=before+b' '
            def read(path):return changed if path==target else real_read(path)
            with self.subTest(path=target,change=old),patch.object(Path,'read_bytes',read):
                probe=PreservationTests('test_baseline_bytes_and_pinned_existing_checkout_forms')
                with self.assertRaises(AssertionError):probe.test_baseline_bytes_and_pinned_existing_checkout_forms()
        self.assertEqual(workflow.read_bytes(),original)

    def test_baseline_bytes_and_pinned_existing_checkout_forms(self):
        listing=subprocess.check_output(['git','ls-tree','-r','-z',BASELINE],cwd=ROOT)
        rows=[row.split(b'\t',1) for row in listing.split(b'\0') if row]
        ids=[metadata.split()[2] for metadata,_ in rows]
        raw=subprocess.check_output(['git','cat-file','--batch'],cwd=ROOT,input=b'\n'.join(ids)+b'\n')
        stream=io.BytesIO(raw)
        self.assertEqual(len(rows),852)
        for metadata,name in rows:
            _,kind,size=stream.readline().split();expected=stream.read(int(size));self.assertEqual(stream.read(1),b'\n')
            path=ROOT/name.decode()
            with self.subTest(path=name.decode()):
                self.assertEqual(kind,b'blob')
                self.assertTrue(path.is_file());self.assertFalse(path.is_symlink())
                if name == b'.github/workflows/acp-contracts.yml':
                    marker=b'\n  phase5-experiments:'
                    step=(b'      - name: Verify Stage 1 evidence contract structures\n'
                          b'        run: python3.14 -m unittest discover -s verification/evidence_admission -v\n')
                    self.assertEqual(expected.count(marker),1)
                    expected=expected.replace(marker,step+CI_STAGE2A_STEPS+CI_STAGE2B_STEPS+marker,1)
                actual=path.read_bytes()
                if actual != expected:
                    self.assertEqual(hashlib.sha256(actual).hexdigest(),CHECKOUT_FORMS.get(name.decode()))
                    self.assertEqual(actual.replace(b'\r\n',b'\n'),expected.replace(b'\r\n',b'\n'))
                mode=metadata.split()[0]
                self.assertEqual(bool(path.stat().st_mode & 0o111),mode==b'100755')
        self.assertEqual(stream.read(),b'')
        subprocess.run(['git','diff','--exit-code','--diff-filter=MDRT',BASELINE,'--',':(exclude).github/workflows/acp-contracts.yml'],cwd=ROOT,check=True,capture_output=True)
        added=subprocess.check_output(['git','diff','--name-only','--diff-filter=A',BASELINE,'--'],cwd=ROOT,text=True).splitlines()
        new=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        self.check_source_additions(new,added,head)

    def test_all_39_criterion_definitions_and_historical_blockers_preserved(self):
        source=(ROOT/'tooling/audit/criteria.py').read_text()
        tree=ast.parse(source)
        numbers=[]
        for node in tree.body:
            if isinstance(node,ast.Assign):
                for target in node.targets:
                    if isinstance(target,ast.Subscript) and isinstance(target.value,ast.Name) and target.value.id=='SPECS' and isinstance(target.slice,ast.Constant):
                        numbers.append(target.slice.value)
        self.assertEqual(numbers,list(range(1,40)))
        evidence=ROOT/'proposals/phase6-route-a-implementation-review/security-remediation/governance-finalization/hosted/38365033881/closure-report.json.gz'
        report=json.loads(gzip.decompress(evidence.read_bytes()))
        self.assertEqual([r['requirement'] for r in report['blockers']],BLOCKERS)
        self.assertEqual(sum(r['status']=='PASS' for r in report['criteria']),18)
        # This is preservation of historical evidence, not a newly executed audit.
        self.assertEqual(report['recommendation'],'PHASE6_CLOSURE_BLOCKED')
        self.assertEqual(report['phase6'],'IN_PROGRESS');self.assertEqual(report['phase7'],'NOT_STARTED')

    def test_exact_current_seal_and_approved_snapshot_bytes(self):
        sys.path.insert(0,str(ROOT/'tooling'))
        from target_worker import bundle_digest
        from deterministic_approval import approved_snapshot
        self.assertEqual(bundle_digest(),'ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb')
        expected={'payment':'sha256:d0f6e8d96a07e8e8358ad8f1f558f9ec3d69fd8008cceb75e82f4f695e3cf47d',
                  'case-management':'sha256:5b3a69bb1d6e0e69ed620cd1dd32d10e8a07cec276583055b53ec03bfdcc6b90'}
        for domain,digest in expected.items():self.assertEqual(approved_snapshot(domain)['contentDigest'],digest)


if __name__=='__main__':unittest.main()
