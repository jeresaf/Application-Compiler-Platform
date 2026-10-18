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
CI_PRESERVATION_FIX_HASHES = {'tooling/tests/test_retained_inventory.py': '37697d420ce5d80b552e483e956db19b4d4b95914bf0d99f45c4cf4cbcd3364d', 'verification/route_a/test_preservation.py': '71759afff11be1eb534170570c7f11dde6407563ea710c3497702b8e1327ea9c'}
CI_B0_STEPS = b'      - name: Verify Stage B0 laboratory evidence admission\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" - <<\'PYTHON\'\n          import platform, unittest\n          from pathlib import Path\n          assert platform.python_version() == \'3.14.7\', \'B0_WRONG_PYTHON\'\n          directory = Path(\'verification/evidence_admission/scoped\')\n          expected = {\'test_manifest.py\', \'test_witnesses.py\', \'test_human_reviews.py\', \'test_adversarial.py\', \'test_bridge.py\'}\n          assert {p.name for p in directory.glob(\'test*.py\')} == expected, \'B0_TEST_FILES\'\n          assert all((directory / name).is_file() and not (directory / name).is_symlink() for name in expected), \'B0_TEST_FILES\'\n          assert unittest.defaultTestLoader.discover(str(directory)).countTestCases() == 60, \'B0_TEST_COUNT\'\n          PYTHON\n          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" -m unittest discover -s verification/evidence_admission/scoped -v 2>&1 | tee "$RUNNER_TEMP/acp-b0-tests.log"\n          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" - <<\'PYTHON\'\n          import os, re\n          from pathlib import Path\n          log = (Path(os.environ[\'RUNNER_TEMP\']) / \'acp-b0-tests.log\').read_text()\n          assert re.findall(r\'^Ran ([0-9]+) tests in .+$\', log, re.MULTILINE) == [\'60\'], \'B0_EXECUTED_COUNT\'\n          assert log.rstrip().splitlines()[-1] == \'OK\', \'B0_FAILURE_OR_SKIP\'\n          assert all(re.search(r\'^test_N%02d_reject .* \\.\\.\\. ok$\' % n, log, re.MULTILINE) for n in range(1, 33)), \'B0_ADVERSARIAL_COVERAGE\'\n          PYTHON\n      - name: Retain Stage B0 laboratory verification log\n        if: always()\n        uses: actions/upload-artifact@v4\n        with:\n          name: stage-b0-laboratory-verification\n          path: ${{ runner.temp }}/acp-b0-tests.log\n          if-no-files-found: error\n'
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
V3_CI_HASHES = {'.github/workflows/phase6-v3-offline.yml': 'b5da4140bf09db8ca9cad83b73dc3055888962659acae577297a3c61e6fe4456', 'engineering/ci/PHASE6-QUALIFICATION.md': '39123fef8ac3a409e369c0b8a4f2ac979e793306983ebc56ec2d57eb0e037791', 'engineering/ci/inputs/.gitattributes': '83c5641d9288aad3c12c13948066115cf115c27ca77b5f86ef986b11b6f9d1cb', 'engineering/ci/inputs/phase6-wave3-cumulative.patch': '9706ba0c436f57560b0e8ace897cee7f1f258c2d40870e8bf1c9c2da70b791c8', 'engineering/ci/phase6-qualification-ci.json': 'c15dbb6fa1226fb22eb28a406ef54f12a1455013d350014794ae0570a6dc90fd', 'engineering/ci/phase6-qualification-manifest.json': '5033d915410e8f2eaf4d53f4a041795c931bb57c36abdf105ba88f57298176e6', 'engineering/ci/phase6_postgresql.py': 'ab32cc6d2146bcf0a5063b06c13e899a8c970e348c32b00380ec5e4b1efe32ec', 'engineering/ci/phase6_qualification.py': '4c01248510d0196af8d1255d3b000d49e6a7d23893daa40f8e0bf0354b0021e9', 'engineering/ci/phase6_v3_hosted.py': 'a60fcccb86b9736f9e620c268eb18617b7b9147d23048801c7ab9add083e1fd5', 'verification/phase6_v3_ci/test_phase6_v3_hosted.py': 'c790db7475c0d95e3fe377c141c2823892ed519df7395fac9895eb802d0a3844'}

GENERATOR_BUILD_HASHES = {'engineering/generator_builds/qualify.py': '659ca6f0e7c0559aa2e33753650a1097662195a65d9056db94169113574672b0', 'verification/generator_builds/test_build_contract.py': '0de23ce6d1be1e8ffe3a4cbdc954d167910722d0cea4f8cde4c8335be1342a50', 'engineering/generator_builds/runtime.py': '3f3df8f56b22f059ae19e0abd6ec773e530f6da852ffa82ec2f0f1b5c3ec77d7', 'verification/generator_runtime/test_runtime_contract.py': 'fdcbc61826e2eae80830d38b20947db29b22ce4608ce7aed9435e839dd6eaad2', 'engineering/generator_builds/privacy_fixture.py': '9b7a1416cd3c78f472e2cc1c62322781d4c35700109b9c9e1e7d7e3dd1ab5f6a', 'engineering/ci/privacy_gate.py': 'f819151305a9172b742ebcfb46b195138dac49c5b98e2122abe10e9a47a04290', 'verification/privacy_concurrency/test_fixture.py': '6bb2fa3da0d3dbf69258c9b5ea75be54571d78747294b3b8e05504c70478e4fa'}

SUCCESSOR_HASHES = {'engineering/generator_candidates/spring_vue_postgres_0_6/__init__.py': '39f14a327ca0cc2561f37b4a69113b4816f03a70c902061e1e87ee1dd458c4c0', 'engineering/generator_candidates/spring_vue_postgres_0_6/candidate.py': '6f7cbf6cffb632decdde1674665bdc81459a2078bb6c41b55085d91f10077807', 'engineering/generator_candidates/spring_vue_postgres_0_6/migrations.py': 'a9f95f769d9c05e56893e381db53d835ac8a8479a0aedffdcdb5be6c1df64628', 'engineering/generator_candidates/spring_vue_postgres_0_6/provenance.py': '4750708bf0eec9e152a5d7b72f073d15ff893a699c17de5df9a83978846d017b', 'engineering/generator_candidates/spring_vue_postgres_0_6/ancestry.json': '425476de76847fe426aadebbe9d4de3cbb408765e793441317c2c679406e76f5', 'engineering/generator_candidates/spring_vue_postgres_0_6/profile.json': '2ce1bd59fa29034725fa5e0813e2f424f6fb56c580499c0c19ba009a1b09c0fd', 'verification/generator_candidates/test_successor.py': 'dd2a22bb17d7064bad300a4233b170299d223bab0f6df6ea42676c63150c6bce'}

RELEASE_CI_STEPS = b'      - name: Verify inactive release-admission engineering boundary\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" - <<\'PYTHON\'\n          import platform, unittest\n          from pathlib import Path\n          assert platform.python_version() == \'3.14.7\'\n          directory = Path(\'verification/release_admission\')\n          assert {p.name for p in directory.glob(\'test*.py\')} == {\'test_release.py\'}\n          assert unittest.defaultTestLoader.discover(str(directory)).countTestCases() == 19\n          PYTHON\n          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" -m unittest discover -s verification/release_admission -v 2>&1 | tee "$RUNNER_TEMP/acp-release-admission-tests.log"\n          "$RUNNER_TEMP/acp-stage2a-venv/bin/python3.14" - <<\'PYTHON\'\n          import os, re\n          from pathlib import Path\n          log = (Path(os.environ[\'RUNNER_TEMP\']) / \'acp-release-admission-tests.log\').read_text()\n          assert re.findall(r\'^Ran ([0-9]+) tests in .+$\', log, re.MULTILINE) == [\'19\']\n          assert log.rstrip().splitlines()[-1] == \'OK\'\n          PYTHON\n      - name: Retain release-admission engineering log\n        if: always()\n        uses: actions/upload-artifact@v4\n        with:\n          name: release-admission-engineering-verification\n          path: ${{ runner.temp }}/acp-release-admission-tests.log\n          if-no-files-found: error\n'
DEPENDENCY_CI_JOB = b'\n  successor-dependency-determinism:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 45\n    steps:\n      - uses: actions/checkout@v6\n        with:\n          fetch-depth: 0\n          persist-credentials: false\n      - uses: actions/setup-python@v7.0.0\n        with:\n          python-version: \'3.14.7\'\n      - uses: actions/setup-node@v7\n        with:\n          node-version: \'24.21.0\'\n      - uses: actions/setup-java@v5\n        with:\n          distribution: temurin\n          java-version: \'21\'\n      - name: Provision existing hash-pinned compiler wheels in disposable runner\n        shell: bash\n        run: |\n          set -euo pipefail\n          python3.14 -m venv "$RUNNER_TEMP/acp-dependency-venv"\n          python3.14 -m pip download --require-hashes --only-binary=:all: -r engineering/dependency_resolution/compiler-requirements.txt -d "$RUNNER_TEMP/acp-compiler-wheels"\n          "$RUNNER_TEMP/acp-dependency-venv/bin/python3.14" -m pip install --no-index --find-links "$RUNNER_TEMP/acp-compiler-wheels" --require-hashes --only-binary=:all: -r engineering/dependency_resolution/compiler-requirements.txt\n          "$RUNNER_TEMP/acp-dependency-venv/bin/python3.14" -m pip check\n      - name: Reject dependency substitutions and mutable resolution\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-dependency-venv/bin/python3.14" -B - <<\'PYTHON\'\n          import unittest\n          from pathlib import Path\n          folder = Path(\'verification/dependency_resolution\')\n          assert {p.name for p in folder.glob(\'test*.py\')} == {\'test_inputs.py\'}\n          suite = unittest.defaultTestLoader.discover(str(folder))\n          assert suite.countTestCases() == 24\n          result = unittest.TextTestRunner(verbosity=2).run(suite)\n          assert result.wasSuccessful() and result.testsRun == 24 and not result.skipped\n          PYTHON\n      - name: Resolve once and freeze all runtime compiler and plugin inputs\n        shell: bash\n        run: |\n          set -euo pipefail\n          mkdir "$RUNNER_TEMP/acp-empty-m2" "$RUNNER_TEMP/acp-empty-npm"\n          "$RUNNER_TEMP/acp-dependency-venv/bin/python3.14" -B engineering/dependency_resolution/qualify.py prepare --workspace "$RUNNER_TEMP/acp-dependency-qualification" --maven-seed "$RUNNER_TEMP/acp-empty-m2" --npm-seed "$RUNNER_TEMP/acp-empty-npm" --wheels "$RUNNER_TEMP/acp-compiler-wheels" --online-acquire 2>&1 | tee "$RUNNER_TEMP/acp-dependency-prepare.log"\n      - name: Build both applications twice offline from independently clean exports\n        shell: bash\n        run: |\n          set -euo pipefail\n          read -r lock_digest < "$RUNNER_TEMP/acp-dependency-qualification/dependency-lock.sha256"\n          "$RUNNER_TEMP/acp-dependency-venv/bin/python3.14" -B engineering/dependency_resolution/qualify.py qualify --workspace "$RUNNER_TEMP/acp-dependency-qualification" --expected "$lock_digest" 2>&1 | tee "$RUNNER_TEMP/acp-dependency-qualify.log"\n      - name: Preserve exact inputs and independent clean-build outcomes\n        if: always()\n        uses: actions/upload-artifact@v4\n        with:\n          name: successor-dependency-determinism\n          path: |\n            ${{ runner.temp }}/acp-dependency-prepare.log\n            ${{ runner.temp }}/acp-dependency-qualify.log\n            ${{ runner.temp }}/acp-dependency-qualification/*.json\n            ${{ runner.temp }}/acp-dependency-qualification/*.sha256\n            ${{ runner.temp }}/acp-dependency-qualification/*.log\n            ${{ runner.temp }}/acp-dependency-qualification/clean-*/*.log\n            ${{ runner.temp }}/acp-dependency-qualification/clean-*/results.json\n          if-no-files-found: error\n'
PERFORMANCE_NEW_HASHES = {'engineering/performance/measure.py': '75fdb444d9096646115f29a92e89bed4fecd5f59e1f539bb99448d134e2a5309', 'engineering/performance/qualify.py': '9d69d7aa54729635eba4ffc35e8daba28009120574158ca01e363b80e940a4b4', 'engineering/performance/rate_regression.py': '4edd590626baf053e5a189c3ccecf411ae8fd612324ffbd4868e8b19a07c4d01', 'engineering/performance/runtime.py': '32d01dbefb1005ebeb0c846bdd56efddcac309a9e06b38a593928b997814b632', 'engineering/performance/scaling.py': 'ebfa7d8af861ef22807e1ec66a7d10221f29fed246f10e7bf8428c07d0938734', 'verification/performance/test_measurements.py': 'bcbd1b121083556cc55feb7b79f043f4966074bd23f79f8b5290291fd0a073fd'}
PERFORMANCE_CI_JOB = b'\n  successor-performance-scaling:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 60\n    steps:\n      - uses: actions/checkout@v6\n        with:\n          fetch-depth: 0\n          persist-credentials: false\n      - uses: actions/setup-python@v7.0.0\n        with:\n          python-version: \'3.14.7\'\n      - uses: actions/setup-node@v7\n        with:\n          node-version: \'24.21.0\'\n      - uses: actions/setup-java@v5\n        with:\n          distribution: temurin\n          java-version: \'21\'\n      - name: Provision pinned compiler dependencies on disposable runner\n        shell: bash\n        run: |\n          set -euo pipefail\n          python3.14 -c \'import platform; assert platform.python_version() == "3.14.7"\'\n          python3.14 -m venv "$RUNNER_TEMP/acp-performance-venv"\n          "$RUNNER_TEMP/acp-performance-venv/bin/python3.14" -m pip install --require-hashes --only-binary=:all: -r engineering/dependency_resolution/compiler-requirements.txt\n          "$RUNNER_TEMP/acp-performance-venv/bin/python3.14" -m pip check\n      - name: Verify bounded statistics fixtures limits and negative cases\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-performance-venv/bin/python3.14" -B - <<\'PYTHON\'\n          import unittest\n          suite = unittest.defaultTestLoader.discover(\'verification/performance\')\n          assert suite.countTestCases() == 14, \'PERFORMANCE_TEST_COUNT\'\n          result = unittest.TextTestRunner(verbosity=2).run(suite)\n          assert result.wasSuccessful() and result.testsRun == 14 and not result.skipped\n          PYTHON\n      - name: Obtain exact disposable PostgreSQL runtime\n        run: docker pull postgres@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336\n      - name: Measure both applications and unchanged compiler capacity bounds\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-performance-venv/bin/python3.14" -B engineering/performance/qualify.py --workspace "$RUNNER_TEMP/acp-performance" 2>&1 | tee "$RUNNER_TEMP/acp-performance.log"\n      - name: Retain exact measurements failures and generated build identities\n        if: always()\n        uses: actions/upload-artifact@v4\n        with:\n          name: successor-performance-scaling\n          path: |\n            ${{ runner.temp }}/acp-performance.log\n            ${{ runner.temp }}/acp-performance/qualification-results.json\n            ${{ runner.temp }}/acp-performance/applications/performance-results.json\n            ${{ runner.temp }}/acp-performance/applications/*-trial-*/\n            ${{ runner.temp }}/acp-performance/rate-regressions/results.json\n            ${{ runner.temp }}/acp-performance/rate-regressions/*/maven.log\n            ${{ runner.temp }}/acp-performance/rate-regressions/*/backend/src/\n            ${{ runner.temp }}/acp-performance/rate-regressions/*/backend/target/surefire-reports/\n            ${{ runner.temp }}/acp-performance/scaling/*.json\n            ${{ runner.temp }}/acp-performance/*-larger-logs/\n            ${{ runner.temp }}/acp-performance/*-build.zip\n          if-no-files-found: error\n'
TRACEABILITY_NEW_HASHES = {'engineering/traceability/qualification.py': 'bec1e0c8463a261048d24e177369ca85fbe4f7b50e9e575029bce8e6b7ffe4ba', 'engineering/traceability/runtime.py': 'e80f4ba5313c3cc7a6d67d762cd660af31df907e3b8092d84f9467f4f902f39b', 'verification/traceability/test_integrated.py': 'dc9a681d63d3ff73260137e255e850dc8b4bb0c9777eef1e01d4b920ee9b2daa', 'engineering/traceability/backend.py': '39377fa45cf082e6dd21f88121fdb70a192bc595f04c4dee4b917c07c27564e5', 'verification/traceability/test_backend.py': '19283de95ad639b9ebc343badf43781f84f25d9966d103c9411b6a4b82e5e5e6'}
TRACEABILITY_OLD_JOB = b'  successor-application-runtime:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 45\n    steps:\n      - uses: actions/checkout@v6\n        with:\n          fetch-depth: 0\n          persist-credentials: false\n      - uses: actions/setup-python@v7.0.0\n        with:\n          python-version: \'3.14.7\'\n      - uses: actions/setup-node@v7\n        with:\n          node-version: \'24.21.0\'\n      - uses: actions/setup-java@v5\n        with:\n          distribution: temurin\n          java-version: \'21\'\n      - name: Provision compiler dependencies on disposable runner\n        run: |\n          python3.14 -m venv "$RUNNER_TEMP/acp-build-venv"\n          "$RUNNER_TEMP/acp-build-venv/bin/python3.14" -m pip install --only-binary=:all: -r tooling/requirements.txt\n          "$RUNNER_TEMP/acp-build-venv/bin/python3.14" -m pip check\n      - name: Verify build runner contracts\n        run: \'"$RUNNER_TEMP/acp-build-venv/bin/python3.14" -B -m unittest discover -s verification/generator_runtime -v\'\n      - name: Obtain exact disposable PostgreSQL runtime\n        run: docker pull postgres@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336\n      - name: Exercise both generated applications with fresh isolated databases\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-build-venv/bin/python3.14" -B engineering/generator_builds/runtime.py --workspace "$RUNNER_TEMP/acp-successor-runtime" 2>&1 | tee "$RUNNER_TEMP/acp-successor-runtime.log"\n      - name: Retain runtime results and browser logs\n        if: always()\n        uses: actions/upload-artifact@v4\n        with:\n          name: successor-application-runtime\n          path: |\n            ${{ runner.temp }}/acp-successor-runtime.log\n            ${{ runner.temp }}/acp-successor-runtime/runtime-results.json\n            ${{ runner.temp }}/acp-successor-runtime/*-runtime/\n          if-no-files-found: error\n\n'
TRACEABILITY_NEW_JOB = b'  successor-application-runtime:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 45\n    steps:\n      - uses: actions/checkout@v6\n        with:\n          fetch-depth: 0\n          persist-credentials: false\n      - uses: actions/setup-python@v7.0.0\n        with:\n          python-version: \'3.14.7\'\n      - uses: actions/setup-node@v7\n        with:\n          node-version: \'24.21.0\'\n      - uses: actions/setup-java@v5\n        with:\n          distribution: temurin\n          java-version: \'21\'\n      - name: Provision compiler dependencies on disposable runner\n        run: |\n          python3.14 -m venv "$RUNNER_TEMP/acp-build-venv"\n          "$RUNNER_TEMP/acp-build-venv/bin/python3.14" -m pip install --only-binary=:all: -r tooling/requirements.txt\n          "$RUNNER_TEMP/acp-build-venv/bin/python3.14" -m pip check\n      - name: Verify build runner contracts\n        run: \'"$RUNNER_TEMP/acp-build-venv/bin/python3.14" -B -m unittest discover -s verification/generator_runtime -v\'\n      - name: Verify integrated ownership provenance and traceability regressions\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-build-venv/bin/python3.14" -B - <<\'PYTHON\'\n          import unittest\n          suite = unittest.defaultTestLoader.discover(\'verification/traceability\')\n          assert suite.countTestCases() == 11, \'TRACEABILITY_TEST_COUNT\'\n          result = unittest.TextTestRunner(verbosity=2).run(suite)\n          assert result.wasSuccessful() and result.testsRun == 11 and not result.skipped\n          PYTHON\n      - name: Obtain exact disposable PostgreSQL runtime\n        run: docker pull postgres@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336\n      # Wrap engineering/generator_builds/runtime.py without changing its assertions or cleanup.\n      - name: Exercise both generated applications with fresh isolated databases\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-build-venv/bin/python3.14" -B engineering/traceability/runtime.py --workspace "$RUNNER_TEMP/acp-successor-runtime" 2>&1 | tee "$RUNNER_TEMP/acp-successor-runtime.log"\n      - name: Retain runtime results and browser logs\n        if: always()\n        uses: actions/upload-artifact@v4\n        with:\n          name: successor-application-runtime\n          path: |\n            ${{ runner.temp }}/acp-successor-runtime.log\n            ${{ runner.temp }}/acp-successor-runtime/runtime-results.json\n            ${{ runner.temp }}/acp-successor-runtime/traceability-results.json\n            ${{ runner.temp }}/acp-successor-runtime/*-runtime/\n          if-no-files-found: error\n\n'
DEPENDENCY_NEW_HASHES = {'engineering/dependency_resolution/compiler-requirements.txt': '19395336638abc94735840687a2774ae5c208ca358a2fd589e4b9c5fb8472f28', 'engineering/dependency_resolution/inputs.py': 'b9c903129b9fdc76711d37c8093d6cbc58094f42aa7f5801a55b9cbc5ac1faf1', 'engineering/dependency_resolution/qualify.py': '1aa21f7d08f6dacc150115462e6bfb26783d83a0bb2ca17706f1e02a20713d5b', 'engineering/dependency_resolution/maven-artifacts.lock.json': 'c95e0ca5e043d8a1e2e80cbe42394943e963de5d5a96dff98df1bae45588ec72', 'verification/dependency_resolution/test_inputs.py': 'b657b5bf63259e16224aa71094d83bbaca48ceef026b7fb05dc6bd794f25ff4c'}

RELEASE_NEW_HASHES = {'engineering/evidence_admission/release.py': 'c8f30adcb5ae77ba170966e1cd86936e2458728e10cbb9730f1ca3b9bc3db1f1', 'verification/release_admission/test_release.py': '0d215ba8258dd33f715a371acfe32cf32a5e8ba4dd3b2c634989d6e5fcfc0e10'}

B0_NEW_HASHES = {'docs/phase6-evidence-admission-version-scoping.md': 'e072162c4f4eebe4b40b6d53857965d1f6dbf58cf7c2e18a79d02e9f1518e2ab', 'engineering/evidence_admission/scoped/context.py': 'af632774adb011fb77b1782b53557b87585b65d8a327b4a416b3e489d188db49', 'engineering/evidence_admission/scoped/human_reviews.py': 'ec51f21d3857f6ce7b3e322de5ed66ebaed0b9cc64cf72f794657330bc5ad1c1', 'engineering/evidence_admission/scoped/manifest.py': 'f995091471c61ae609a6df1f51fce09104d52186475768069a23d5a28865eb9e', 'engineering/evidence_admission/scoped/schemas/evaluation-manifest.schema.json': '204f4954663df4ee275915108937fcfbc8d5ca65d2d8c69b883b4179c2b38f7a', 'engineering/evidence_admission/scoped/schemas/execution-attestation-v2.schema.json': '42eac496732cef2c0f47373038449d7a89240bddd129a0321abba9d3d5bde563', 'engineering/evidence_admission/scoped/schemas/release-witness-scope.schema.json': 'c73dd556f96ad5d0fd3872bfda4216cf469667dba2e7cca4d89e4cfdaf6e8bbf', 'engineering/evidence_admission/scoped/verify.py': 'c4f17a0a2a4cb23ca6211d8135f0c90723440ecc04019ff10fd0d81a7b38a81c', 'engineering/evidence_admission/scoped/witnesses.py': 'c8425ab86261d5b104b0be9d3dcfdd8528b7696e041b2890763bd1b9b4effc15', 'tooling/audit/scoped_admission.py': 'f113aba688aeb43a75bbb1c47a72021c3c62affec3d6e4f8ba28e0d53c957c8f', 'verification/evidence_admission/scoped/test_adversarial.py': '083f90950b1bf7c1bbca5ae835d17d6fe155f9becb059942564f455b4bd310f8', 'verification/evidence_admission/scoped/test_bridge.py': 'fac46072ee367db330207b4617ae294a2c1536f3d50b035502100dd1fed5cd92', 'verification/evidence_admission/scoped/test_human_reviews.py': '090f14ed05102dc6fd6b12c999b8fc9e16f53824e0b1c62d757531dc13d7bea9', 'verification/evidence_admission/scoped/test_manifest.py': '27190e002601e69f618acd6a81b7fd8ad190b70539b8b94ccd4b4853176a6704', 'verification/evidence_admission/scoped/test_witnesses.py': 'ca24de9aa381575a1c73f4b807afde12d99781b2faf951b9439fd687ef5dbeab'}
B0_MODIFIED_HASHES = {'tooling/audit/criteria.py': '48b175977f9bcde3e9b5142bd185a43be5b4dd22e35aebe360d25d858e737adb', 'tooling/audit/phase6.py': '8bab77ed470ed440316b23321a89c4997d3004ec7848d438f42d6da94b4064fd'}

PRIVACY_MODIFIED_HASHES = {'.github/workflows/acp-contracts.yml': '356c3d6d7edd14c602b5c0456858c587634983babddce0b459545d1c1ea51d44', 'engineering/ci/parity.py': 'ef19b610de669c33f18abcc637cb576732a8880d8c61677006be2f6bb6c87a70'}


RATE_CLOCK_HASHES = {'engineering/generator_candidates/spring_vue_postgres_0_6/candidate.py': '599b5d0762665d98ddbac26be7ee17c3b8ae9b7c0ed14e2734579e76bf2a9292', 'engineering/generator_candidates/spring_vue_postgres_0_6/rate_clock.py': '3f7379f4695d6046cc57f5f2aacf85c978e1ef3273f23ecda61795a6c59eb35a', 'engineering/generator_candidates/spring_vue_postgres_0_6/rate_clock_tests.py': '7899c4e1a59702fecba7cbbe45af82531e2296240c7e5dbd8b542446b285740b'}

RATE_CLOCK_COMPAT_HASHES = {'verification/dependency_resolution/test_inputs.py': 'c6b549b272ec1804a6bddfc392fe898428d84823a962c995ae035e1702cbde75'}

RECOVERY_NEW_HASHES = {'engineering/recovery/fixtures.py': '521eecda15075848f6cb0a08fa8a8b5dfa02d358758660f512733a68c4140238', 'engineering/recovery/qualify.py': '70bea7391f79164179dda038b5784f0ed5cb77c84df64667f68537663122d496', 'verification/recovery/test_recovery.py': '050bad6ac35b8ce77883cf6ade304289565f0e0d3eeb9d832fc5211731c6bbb0'}
RECOVERY_CI_JOB = b'\n  successor-deployment-recovery:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 40\n    steps:\n      - uses: actions/checkout@v6\n        with:\n          fetch-depth: 0\n          persist-credentials: false\n      - uses: actions/setup-python@v7.0.0\n        with:\n          python-version: \'3.14.7\'\n      - uses: actions/setup-java@v5\n        with:\n          distribution: temurin\n          java-version: \'21\'\n      - name: Provision pinned compiler dependencies on disposable runner\n        shell: bash\n        run: |\n          set -euo pipefail\n          python3.14 -c \'import platform; assert platform.python_version() == "3.14.7"\'\n          python3.14 -m venv "$RUNNER_TEMP/acp-recovery-venv"\n          "$RUNNER_TEMP/acp-recovery-venv/bin/python3.14" -m pip install --require-hashes --only-binary=:all: -r engineering/dependency_resolution/compiler-requirements.txt\n          "$RUNNER_TEMP/acp-recovery-venv/bin/python3.14" -m pip check\n      - name: Reject incomplete recovery outcomes and unsafe cleanup\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-recovery-venv/bin/python3.14" -B - <<\'PYTHON\'\n          import unittest\n          suite = unittest.defaultTestLoader.discover(\'verification/recovery\')\n          assert suite.countTestCases() == 12, \'RECOVERY_TEST_COUNT\'\n          result = unittest.TextTestRunner(verbosity=2).run(suite)\n          assert result.wasSuccessful() and result.testsRun == 12 and not result.skipped\n          PYTHON\n      - name: Obtain exact disposable PostgreSQL runtime\n        run: docker pull postgres@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336\n      - name: Exercise migration failures and fresh JVM committed-state recovery\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-recovery-venv/bin/python3.14" -B engineering/recovery/qualify.py --workspace "$RUNNER_TEMP/acp-recovery" 2>&1 | tee "$RUNNER_TEMP/acp-recovery.log"\n      - name: Retain exact recovery states failures source and cleanup evidence\n        if: always()\n        uses: actions/upload-artifact@v4\n        with:\n          name: successor-deployment-recovery\n          path: |\n            ${{ runner.temp }}/acp-recovery.log\n            ${{ runner.temp }}/acp-recovery/*.json\n            ${{ runner.temp }}/acp-recovery/*-logs/\n            ${{ runner.temp }}/acp-recovery/*-migration-inputs/\n            ${{ runner.temp }}/acp-recovery/*/backend/src/test/java/acp/browser/\n            ${{ runner.temp }}/acp-recovery/*/backend/src/test/java/acp/recovery/\n          if-no-files-found: error\n'

def preserved_bytes(path):
    # Validate the exact two authorized CI-only modifications before comparing
    # the remainder to immutable historical bytes. No path-wide exception.
    actual = path.read_bytes()
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        return actual
    if relative in RATE_CLOCK_COMPAT_HASHES:
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest() == RATE_CLOCK_COMPAT_HASHES[relative], relative
        return subprocess.check_output(['git','show','99c0244052f01c0df3904af0c236de1d027fe77f:' + relative],cwd=ROOT)
    if relative == 'engineering/generator_candidates/spring_vue_postgres_0_6/candidate.py':
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest() == RATE_CLOCK_HASHES[relative], relative
        return subprocess.check_output(['git','show','355b8f72cf8012e17aa24f23042be3e8eebbff3f:' + relative],cwd=ROOT)
    if relative == '.github/workflows/phase6-v3-offline.yml':
        assert actual.endswith(RECOVERY_CI_JOB) and actual.count(RECOVERY_CI_JOB)==1, 'EXACT_RECOVERY_JOB_REQUIRED'
        actual=actual[:-len(RECOVERY_CI_JOB)]
        assert actual.endswith(PERFORMANCE_CI_JOB) and actual.count(PERFORMANCE_CI_JOB)==1, 'EXACT_PERFORMANCE_JOB_REQUIRED'
        actual=actual[:-len(PERFORMANCE_CI_JOB)]
        assert actual.count(TRACEABILITY_NEW_JOB) == 1, 'EXACT_TRACEABILITY_JOB_REQUIRED'
        actual = actual.replace(TRACEABILITY_NEW_JOB, TRACEABILITY_OLD_JOB, 1)
        assert actual.endswith(DEPENDENCY_CI_JOB) and actual.count(DEPENDENCY_CI_JOB) == 1, 'EXACT_DEPENDENCY_JOB_REQUIRED'
        return actual[:-len(DEPENDENCY_CI_JOB)]
    if relative in CI_PRESERVATION_FIX_HASHES:
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest() == CI_PRESERVATION_FIX_HASHES[relative], relative
        return subprocess.check_output(['git', 'show', '17ab4b2a533bc112cfbc8d73796347de94d938b6:' + relative], cwd=ROOT)
    if relative in B0_MODIFIED_HASHES:
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest() == B0_MODIFIED_HASHES[relative], relative
        return subprocess.check_output(['git', 'show', '17ab4b2a533bc112cfbc8d73796347de94d938b6:' + relative], cwd=ROOT)
    if relative == '.github/workflows/acp-contracts.yml':
        assert actual.count(RELEASE_CI_STEPS) == 1, 'EXACT_RELEASE_CI_INSERTION_REQUIRED'
        actual = actual.replace(RELEASE_CI_STEPS, b'', 1)
        assert actual.count(CI_B0_STEPS) == 1, 'EXACT_B0_CI_INSERTION_REQUIRED'
        actual = actual.replace(CI_B0_STEPS, b'', 1)
    if relative in PRIVACY_MODIFIED_HASHES:
        assert hashlib.sha256(actual).hexdigest() == PRIVACY_MODIFIED_HASHES[relative], relative
        return subprocess.check_output(['git', 'show', 'a668696d4068f5afe2ab919a7378eec9cdf48e10:' + relative], cwd=ROOT)
    return actual


def legacy_modifications(paths, accepted):
    paths = set(paths)
    for relative in (set(PRIVACY_MODIFIED_HASHES) | set(B0_MODIFIED_HASHES) | set(CI_PRESERVATION_FIX_HASHES)) & paths:
        original = subprocess.check_output(['git', 'show', accepted + ':' + relative], cwd=ROOT)
        if preserved_bytes(ROOT / relative) == original:
            paths.remove(relative)
    return paths


def ci_legacy_tree(tree):
    """Project only the exact CI allowance out of historical method comparisons."""
    import copy
    predicate = ast.dump(ast.parse('self.verified_ci_additions()', mode='eval').body)
    class Projection(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            node = self.generic_visit(node)
            if node.name == 'test_exact_v3_ci_allowance_rejects_modified_missing_and_symlink_input':
                for call in ast.walk(node):
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == 'assertEqual' and len(call.args) == 2:
                        if ast.unparse(call.args[0]) == 'len(self.verified_ci_additions())' and isinstance(call.args[1], ast.Constant) and call.args[1].value in (39, 41, 45, 46, 49, 51, 56, 59, 62):
                            call.args[1].value = 24
            return node
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
        def visit_List(self, node):
            node = self.generic_visit(node)
            node.elts = [value for value in node.elts if not (isinstance(value, ast.Constant)
                         and value.value in (':(exclude)engineering/ci/parity.py', ':(exclude)tooling/audit/criteria.py', ':(exclude)tooling/audit/phase6.py',':(exclude)tooling/tests/test_retained_inventory.py',':(exclude)verification/route_a/test_preservation.py'))]
            return node
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == 'preserved_bytes':
                return ast.Call(func=ast.Attribute(value=self.visit(node.args[0]), attr='read_bytes', ctx=ast.Load()), args=[], keywords=[])
            if isinstance(node.func, ast.Name) and node.func.id in ('ci_legacy_tree', 'legacy_modifications'):
                return self.visit(node.args[0])
            return self.generic_visit(node)
    return Projection().visit(copy.deepcopy(tree))


class PreservationTests(unittest.TestCase):
    def verified_ci_additions(self):
        for relative, expected in {**V3_CI_HASHES, **SUCCESSOR_HASHES, **GENERATOR_BUILD_HASHES, **B0_NEW_HASHES, **RELEASE_NEW_HASHES, **DEPENDENCY_NEW_HASHES, **TRACEABILITY_NEW_HASHES, **PERFORMANCE_NEW_HASHES, **RECOVERY_NEW_HASHES, **{p:h for p,h in RATE_CLOCK_HASHES.items() if p not in SUCCESSOR_HASHES}}.items():
            path = ROOT / relative
            self.assertFalse(path.is_symlink(), relative)
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(hashlib.sha256(preserved_bytes(path)).hexdigest(), expected, relative)
            self.assertFalse(path.stat().st_mode & 0o111, relative)
        return set(V3_CI_HASHES) | set(SUCCESSOR_HASHES) | set(GENERATOR_BUILD_HASHES) | set(B0_NEW_HASHES) | set(RELEASE_NEW_HASHES) | set(DEPENDENCY_NEW_HASHES) | set(TRACEABILITY_NEW_HASHES) | set(PERFORMANCE_NEW_HASHES) | set(RECOVERY_NEW_HASHES) | set(RATE_CLOCK_HASHES)

    def test_dependency_qualification_additions_and_job_are_exact(self):
        self.assertEqual(set(DEPENDENCY_NEW_HASHES), {'engineering/dependency_resolution/compiler-requirements.txt','engineering/dependency_resolution/inputs.py','engineering/dependency_resolution/qualify.py','engineering/dependency_resolution/maven-artifacts.lock.json','verification/dependency_resolution/test_inputs.py'})
        self.verified_ci_additions()
        real_read=Path.read_bytes
        for relative in (*DEPENDENCY_NEW_HASHES,'.github/workflows/phase6-v3-offline.yml'):
            path=ROOT/relative
            with patch.object(Path,'read_bytes',lambda item: real_read(item)+b'unreviewed' if item==path else real_read(item)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_release_admission_additions_are_exact_and_mutations_rejected(self):
        self.assertEqual(set(RELEASE_NEW_HASHES), {'engineering/evidence_admission/release.py', 'verification/release_admission/test_release.py'})
        real_read = Path.read_bytes
        self.verified_ci_additions()
        for relative in RELEASE_NEW_HASHES:
            path = ROOT / relative
            with patch.object(Path, 'read_bytes', lambda item: b'unreviewed' if item == path else real_read(item)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_ci_preservation_fixes_are_exact_and_mutations_are_rejected(self):
        real_read = Path.read_bytes
        for relative in CI_PRESERVATION_FIX_HASHES:
            path = ROOT / relative
            preserved_bytes(path)
            with patch.object(Path, 'read_bytes', lambda item: real_read(item)+b'unreviewed' if item == path else real_read(item)):
                with self.assertRaises(AssertionError):preserved_bytes(path)

    def test_b0_ci_allows_only_exact_append_and_preserves_failure_policy(self):
        workflow = ROOT / '.github/workflows/acp-contracts.yml'
        raw = workflow.read_bytes()
        accepted = subprocess.check_output(['git', 'show', '1e43974:.github/workflows/acp-contracts.yml'], cwd=ROOT)
        self.assertEqual(raw.replace(RELEASE_CI_STEPS,b'',1), accepted.replace(b'\n  phase5-experiments:', CI_B0_STEPS+b'\n  phase5-experiments:', 1))
        preserved_bytes(workflow)
        real_read = Path.read_bytes
        for changed in (raw.replace(b'== 60', b'>= 0'), raw.replace(b'set -euo pipefail', b'set -eu'), raw.replace(b'B0_FAILURE_OR_SKIP', b'UNREVIEWED'), raw.replace(CI_B0_STEPS,b'')):
            with patch.object(Path, 'read_bytes', lambda item: changed if item == workflow else real_read(item)):
                with self.assertRaises(AssertionError):preserved_bytes(workflow)

    def test_b0_exact_inventory_and_changed_source_rejection(self):
        self.assertEqual(len(B0_NEW_HASHES), 15)
        self.assertEqual(set(B0_MODIFIED_HASHES), {'tooling/audit/criteria.py', 'tooling/audit/phase6.py'})
        self.verified_ci_additions()
        real_read = Path.read_bytes
        for relative in B0_MODIFIED_HASHES:
            path = ROOT / relative
            preserved_bytes(path)
            with patch.object(Path, 'read_bytes', lambda item: b'unreviewed' if item == path else real_read(item)):
                with self.assertRaises(AssertionError):preserved_bytes(path)
        accepted = '17ab4b2a533bc112cfbc8d73796347de94d938b6'
        changes = set(subprocess.check_output(['git','diff','--name-only',accepted,'--'],cwd=ROOT,text=True).splitlines())
        untracked = set(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        added = set(subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
        head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        self.check_b0_changes(changes | untracked, untracked, added, head)

    def check_b0_changes(self, changes, untracked, added, head):
        transient = {'.ci-evidence/contracts.json'}
        self.check_source_additions(set(untracked) & transient, set(added) & transient, head)
        self.assertEqual(set(changes) - (set(untracked) & transient), set(DEPENDENCY_NEW_HASHES) | set(TRACEABILITY_NEW_HASHES) | set(PERFORMANCE_NEW_HASHES) | set(RECOVERY_NEW_HASHES) | set(RATE_CLOCK_HASHES) | {'.github/workflows/phase6-v3-offline.yml'} | set(RELEASE_NEW_HASHES) | set(B0_NEW_HASHES) | set(B0_MODIFIED_HASHES) | set(CI_PRESERVATION_FIX_HASHES) | {'verification/evidence_admission/test_preservation.py', '.github/workflows/acp-contracts.yml'})

    def test_b0_change_inventory_validates_transient_output_before_exclusion(self):
        head='a'*40
        expected=set(DEPENDENCY_NEW_HASHES) | set(TRACEABILITY_NEW_HASHES) | set(PERFORMANCE_NEW_HASHES) | set(RECOVERY_NEW_HASHES) | set(RATE_CLOCK_HASHES) | {'.github/workflows/phase6-v3-offline.yml'} | set(RELEASE_NEW_HASHES) | set(B0_NEW_HASHES) | set(B0_MODIFIED_HASHES) | set(CI_PRESERVATION_FIX_HASHES) | {'verification/evidence_admission/test_preservation.py', '.github/workflows/acp-contracts.yml'}
        transient='.ci-evidence/contracts.json'
        with tempfile.TemporaryDirectory() as directory,patch(__name__+'.ROOT',Path(directory)),patch.dict(os.environ):
            for key in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_JOB'):os.environ.pop(key,None)
            path=ROOT/transient;path.parent.mkdir()
            binding={'source':head,'run':'123','attempt':'2','job':'contracts'}
            path.write_text(json.dumps(binding))
            self.check_b0_changes(expected|{transient},{transient},set(),head)
            with self.assertRaises(AssertionError):self.check_b0_changes(expected|{transient},set(),{transient},head)
            with self.assertRaises(AssertionError):self.check_b0_changes(expected|{transient,'unexpected.py'},{transient,'unexpected.py'},set(),head)
            for value in (dict(binding,source='b'*40),dict(binding,extra='untrusted')):
                path.write_text(json.dumps(value))
                with self.assertRaises(AssertionError):self.check_b0_changes(expected|{transient},{transient},set(),head)

    def test_exact_v3_ci_allowance_rejects_modified_missing_and_symlink_input(self):
        self.assertEqual(len(V3_CI_HASHES), 10)
        self.assertEqual(len(SUCCESSOR_HASHES), 7)
        self.assertEqual(len(self.verified_ci_additions()), 62)
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

    def test_exact_successor_inputs_reject_unreviewed_edits(self):
        self.verified_ci_additions()
        original_read = Path.read_bytes
        for relative in ('engineering/generator_candidates/spring_vue_postgres_0_6/candidate.py',
                         *GENERATOR_BUILD_HASHES):
            path = ROOT / relative
            with patch.object(Path, 'read_bytes', lambda item: b'unreviewed' if item == path else original_read(item)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_stage2b2_exact_inventory_and_accepted_source(self):
        accepted='91181e1c62cfc6be6b82d64bc86f8d4f7166d09c'
        additions=legacy_modifications(set(subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines()),accepted)
        additions.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        if '.ci-evidence/contracts.json' in additions:
            self.check_source_additions(['.ci-evidence/contracts.json'],[],subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
            self.assertNotIn('.ci-evidence/contracts.json',subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
            additions.remove('.ci-evidence/contracts.json')
        self.assertEqual(additions-self.verified_ci_additions(),STAGE2B2_FILES)
        self.assertEqual(legacy_modifications(set(subprocess.check_output(['git','diff','--name-only','--diff-filter=MDRT',accepted,'--'],cwd=ROOT,text=True).splitlines()),accepted),{'verification/evidence_admission/test_preservation.py'})
        listing=subprocess.check_output(['git','ls-tree','-r','-z',accepted],cwd=ROOT)
        for row in listing.split(b'\0'):
            if not row:continue
            metadata,name=row.split(b'\t',1);relative=name.decode()
            if relative=='verification/evidence_admission/test_preservation.py':continue
            mode,kind,digest=metadata.split();path=ROOT/relative
            expected=subprocess.check_output(['git','cat-file','blob',digest.decode()],cwd=ROOT)
            actual=preserved_bytes(path)
            with self.subTest(path=relative):
                self.assertFalse(path.is_symlink());self.assertEqual(kind,b'blob')
                if actual!=expected:
                    self.assertEqual(hashlib.sha256(actual).hexdigest(),CHECKOUT_FORMS.get(relative))
                    self.assertEqual(actual.replace(b'\r\n',b'\n'),expected.replace(b'\r\n',b'\n'))
                self.assertEqual(bool(path.stat().st_mode & 0o111),mode==b'100755')

    def test_stage2b_final_exact_correction_and_workflow(self):
        accepted='ea5683c36300481f9d3a7a473290ec3e5923af6d'
        expected_changes=set(F20_EXACT_HASHES)|{'.github/workflows/acp-contracts.yml','verification/evidence_admission/test_preservation.py'}
        changes=legacy_modifications(set(subprocess.check_output(['git','diff','--name-only',accepted,'--'],cwd=ROOT,text=True).splitlines()),accepted)
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
            self.assertEqual(hashlib.sha256(preserved_bytes((ROOT/relative))).hexdigest(),digest,relative)
        workflow='.github/workflows/acp-contracts.yml'
        baseline=subprocess.check_output(['git','show',accepted+':'+workflow],cwd=ROOT)
        self.assertEqual(preserved_bytes((ROOT/workflow)),baseline.replace(b'\n  phase5-experiments:',CI_STAGE2B_STEPS+b'\n  phase5-experiments:',1))
        # Every other accepted tracked byte and mode is still enforced by the
        # earlier baseline comparisons, plus this exact current-baseline pass.
        listing=subprocess.check_output(['git','ls-tree','-r','-z',accepted],cwd=ROOT)
        for row in listing.split(b'\0'):
            if not row:continue
            metadata,name=row.split(b'\t',1);relative=name.decode()
            if relative in expected_changes:continue
            mode,kind,digest=metadata.split();path=ROOT/relative
            expected=subprocess.check_output(['git','cat-file','blob',digest.decode()],cwd=ROOT)
            actual=preserved_bytes(path)
            with self.subTest(path=relative):
                self.assertFalse(path.is_symlink());self.assertEqual(kind,b'blob')
                if actual!=expected:
                    self.assertEqual(hashlib.sha256(actual).hexdigest(),CHECKOUT_FORMS.get(relative))
                    self.assertEqual(actual.replace(b'\r\n',b'\n'),expected.replace(b'\r\n',b'\n'))
                self.assertEqual(bool(path.stat().st_mode & 0o111),mode==b'100755')

    def test_stage2b_ci_rejects_weakened_guards(self):
        workflow=ROOT/'.github/workflows/acp-contracts.yml';original=preserved_bytes(workflow)
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
        additions=legacy_modifications(set(subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines()),accepted)
        additions.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        if '.ci-evidence/contracts.json' in additions:
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            self.check_source_additions(['.ci-evidence/contracts.json'],[],head)
            self.assertNotIn('.ci-evidence/contracts.json',subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
            additions.remove('.ci-evidence/contracts.json')
        self.assertEqual(additions-self.verified_ci_additions(),STAGE2B1_FILES | STAGE2B2_FILES)
        modified=legacy_modifications(set(subprocess.check_output(['git','diff','--name-only','--diff-filter=MDRT',accepted,'--'],cwd=ROOT,text=True).splitlines()),accepted)
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
            actual=preserved_bytes((ROOT/relative))
            with self.subTest(path=relative):
                self.assertFalse((ROOT/relative).is_symlink());self.assertEqual(kind,b'blob')
                if actual!=expected:
                    self.assertEqual(hashlib.sha256(actual).hexdigest(),CHECKOUT_FORMS.get(relative))
                    self.assertEqual(actual.replace(b'\r\n',b'\n'),expected.replace(b'\r\n',b'\n'))
                self.assertEqual(bool((ROOT/relative).stat().st_mode & 0o111),mode==b'100755')

    def test_stage2a_exact_inventory_preserves_accepted_stage1(self):
        accepted='f44f8952ba7e86f879b0c21e1b56de9fbd3d01aa'
        additions=legacy_modifications(set(subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines()),accepted)
        additions.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        # Retain only the pre-existing, separately validated transient exception.
        if '.ci-evidence/contracts.json' in additions:
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            self.check_source_additions(['.ci-evidence/contracts.json'],[],head)
            self.assertNotIn('.ci-evidence/contracts.json',subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
            additions.remove('.ci-evidence/contracts.json')
        self.assertEqual(additions-self.verified_ci_additions(),STAGE2A_FILES | STAGE2B1_FILES | STAGE2B2_FILES)
        modified=legacy_modifications(set(subprocess.check_output(['git','diff','--name-only','--diff-filter=MDRT',accepted,'--'],cwd=ROOT,text=True).splitlines()),accepted)
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
        original=preserved_bytes(workflow)
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
        value=json.loads(preserved_bytes(path).decode('utf-8'),object_pairs_hook=unique_pairs)
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
        original=preserved_bytes(workflow)
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
        self.assertEqual(preserved_bytes(workflow),original)

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
                actual=preserved_bytes(path)
                if actual != expected:
                    self.assertEqual(hashlib.sha256(actual).hexdigest(),CHECKOUT_FORMS.get(name.decode()))
                    self.assertEqual(actual.replace(b'\r\n',b'\n'),expected.replace(b'\r\n',b'\n'))
                mode=metadata.split()[0]
                self.assertEqual(bool(path.stat().st_mode & 0o111),mode==b'100755')
        self.assertEqual(stream.read(),b'')
        subprocess.run(['git','diff','--exit-code','--diff-filter=MDRT',BASELINE,'--',':(exclude).github/workflows/acp-contracts.yml',':(exclude)engineering/ci/parity.py',':(exclude)tooling/audit/criteria.py',':(exclude)tooling/audit/phase6.py',':(exclude)tooling/tests/test_retained_inventory.py',':(exclude)verification/route_a/test_preservation.py'],cwd=ROOT,check=True,capture_output=True)
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
