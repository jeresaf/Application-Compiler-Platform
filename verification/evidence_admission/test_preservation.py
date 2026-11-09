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

SECURITY_NEW_HASHES = {'engineering/security/qualification.py': '0826239eac86e1e0fdfb18806c408869e4ce90419a2b24fa4d4ef2216bb4082f', 'verification/security/test_security.py': 'd7d83b9e5462362582ff14d2d95d86cc6bb227f5aa142498b2343c2588a1a50a'}
SECURITY_CI_JOB = b'\n  successor-security-readiness:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 30\n    steps:\n      - uses: actions/checkout@v6\n        with:\n          fetch-depth: 0\n          persist-credentials: false\n      - uses: actions/setup-python@v7.0.0\n        with:\n          python-version: \'3.14.7\'\n      - uses: actions/setup-node@v7\n        with:\n          node-version: \'24.21.0\'\n      - uses: actions/setup-java@v5\n        with:\n          distribution: temurin\n          java-version: \'21\'\n      - name: Provision isolated pinned compiler dependencies\n        shell: bash\n        run: |\n          set -euo pipefail\n          python3.14 -c \'import platform; assert platform.python_version() == "3.14.7"\'\n          python3.14 -m venv "$RUNNER_TEMP/acp-security-venv"\n          "$RUNNER_TEMP/acp-security-venv/bin/python3.14" -m pip install --require-hashes --only-binary=:all: -r engineering/dependency_resolution/compiler-requirements.txt\n          "$RUNNER_TEMP/acp-security-venv/bin/python3.14" -m pip check\n      - name: Verify fail-closed security assessment and protocol regressions\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-security-venv/bin/python3.14" -B - <<\'PYTHON\'\n          import unittest\n          suite = unittest.defaultTestLoader.discover(\'verification/security\')\n          assert suite.countTestCases() == 12\n          result = unittest.TextTestRunner(verbosity=2).run(suite)\n          assert result.wasSuccessful() and result.testsRun == 12 and not result.skipped\n          PYTHON\n          "$RUNNER_TEMP/acp-security-venv/bin/python3.14" -B -m unittest discover -s tooling/tests -p test_target_worker_faults.py -v\n      - name: Exercise real worker limits and generated package startup contracts\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-security-venv/bin/python3.14" -B engineering/security/qualification.py --workspace "$RUNNER_TEMP/acp-security" 2>&1 | tee "$RUNNER_TEMP/acp-security.log"\n      - name: Retain assessment findings without claiming release acceptance\n        if: always()\n        uses: actions/upload-artifact@v4\n        with:\n          name: successor-security-readiness\n          path: |\n            ${{ runner.temp }}/acp-security.log\n            ${{ runner.temp }}/acp-security/*.json\n            ${{ runner.temp }}/acp-security/*-scan/\n            ${{ runner.temp }}/acp-security/*.log\n            ${{ runner.temp }}/acp-security/*/backend/target/surefire-reports/\n          if-no-files-found: error\n'
RECOVERY_NEW_HASHES = {'engineering/recovery/fixtures.py': '521eecda15075848f6cb0a08fa8a8b5dfa02d358758660f512733a68c4140238', 'engineering/recovery/qualify.py': '70bea7391f79164179dda038b5784f0ed5cb77c84df64667f68537663122d496', 'verification/recovery/test_recovery.py': '050bad6ac35b8ce77883cf6ade304289565f0e0d3eeb9d832fc5211731c6bbb0'}
RECOVERY_CI_JOB = b'\n  successor-deployment-recovery:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 40\n    steps:\n      - uses: actions/checkout@v6\n        with:\n          fetch-depth: 0\n          persist-credentials: false\n      - uses: actions/setup-python@v7.0.0\n        with:\n          python-version: \'3.14.7\'\n      - uses: actions/setup-java@v5\n        with:\n          distribution: temurin\n          java-version: \'21\'\n      - name: Provision pinned compiler dependencies on disposable runner\n        shell: bash\n        run: |\n          set -euo pipefail\n          python3.14 -c \'import platform; assert platform.python_version() == "3.14.7"\'\n          python3.14 -m venv "$RUNNER_TEMP/acp-recovery-venv"\n          "$RUNNER_TEMP/acp-recovery-venv/bin/python3.14" -m pip install --require-hashes --only-binary=:all: -r engineering/dependency_resolution/compiler-requirements.txt\n          "$RUNNER_TEMP/acp-recovery-venv/bin/python3.14" -m pip check\n      - name: Reject incomplete recovery outcomes and unsafe cleanup\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-recovery-venv/bin/python3.14" -B - <<\'PYTHON\'\n          import unittest\n          suite = unittest.defaultTestLoader.discover(\'verification/recovery\')\n          assert suite.countTestCases() == 12, \'RECOVERY_TEST_COUNT\'\n          result = unittest.TextTestRunner(verbosity=2).run(suite)\n          assert result.wasSuccessful() and result.testsRun == 12 and not result.skipped\n          PYTHON\n      - name: Obtain exact disposable PostgreSQL runtime\n        run: docker pull postgres@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336\n      - name: Exercise migration failures and fresh JVM committed-state recovery\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-recovery-venv/bin/python3.14" -B engineering/recovery/qualify.py --workspace "$RUNNER_TEMP/acp-recovery" 2>&1 | tee "$RUNNER_TEMP/acp-recovery.log"\n      - name: Retain exact recovery states failures source and cleanup evidence\n        if: always()\n        uses: actions/upload-artifact@v4\n        with:\n          name: successor-deployment-recovery\n          path: |\n            ${{ runner.temp }}/acp-recovery.log\n            ${{ runner.temp }}/acp-recovery/*.json\n            ${{ runner.temp }}/acp-recovery/*-logs/\n            ${{ runner.temp }}/acp-recovery/*-migration-inputs/\n            ${{ runner.temp }}/acp-recovery/*/backend/src/test/java/acp/browser/\n            ${{ runner.temp }}/acp-recovery/*/backend/src/test/java/acp/recovery/\n          if-no-files-found: error\n'

DELIVERY_NEW_HASHES = {'engineering/demo/pipeline.py': 'f140771d1ed7d4b95a5be2c0b53cb4a05611fcc46d7a6cc3014d9e15025c3a80', 'engineering/demo/reference.py': '8a2d693342d748710a0326b2af5e8e21af6677600a2c797ff928d7ead7b16fa7', 'verification/demo/test_demo.py': '0588134cf30c504044b5416f2a6f8c1d83ccabdec2259af890d90f57e13c6219', 'engineering/generator_candidates/spring_vue_postgres_0_6/dependencies.py': 'a6a5883a5daa7d977d6ef1056cc0177afed25dc24e9a55c02f2b86e99f82b38f'}
DELIVERY_MODIFIED_HASHES = {'engineering/generator_candidates/spring_vue_postgres_0_6/candidate.py': '8751d0fdf4393266154f8ba9f7ff5fcc2ed1d71514f4bfe21af86935054d784a', 'engineering/dependency_resolution/maven-artifacts.lock.json': '6afefcd376cf8229962d63305d6ff9b9530dd7c32013e1d4f1d14ddd34c0db9e', 'engineering/generator_builds/runtime.py': '692d72831adeece05aa6e5e3059843d9642cf7e87dbfb6307397f0be5a274185', 'DEV_LINUX.md': '09b824e40213da1fcf0efc68ffaff3366c60b3df12cc8af932aabc2001d08183', 'docs/roadmap.md': '2208939f5b357addaef548cf6783d90e4d19af1621f4d74077d93f878f55b1f3', 'verification/dependency_resolution/test_inputs.py': 'b3019e0a04d539b9cc9db365d2d5bd57734681e80a8da28710f9bd9d3c6ac3fc', 'verification/route_a/test_preservation.py': '7efcc4c52d591f8fda9baf2f6b3884ecf3411651cc98acfa03c9b1311c90e840'}
DELIVERY_CI_JOB = b'\n  successor-reference-demonstration:\n    runs-on: ubuntu-24.04\n    timeout-minutes: 50\n    steps:\n      - uses: actions/checkout@v6\n        with:\n          fetch-depth: 0\n          persist-credentials: false\n      - uses: actions/setup-python@v7.0.0\n        with:\n          python-version: \'3.14.7\'\n      - uses: actions/setup-node@v7\n        with:\n          node-version: \'24.21.0\'\n      - uses: actions/setup-java@v5\n        with:\n          distribution: temurin\n          java-version: \'21\'\n      - name: Provision hash-pinned compiler dependencies on disposable runner\n        shell: bash\n        run: |\n          set -euo pipefail\n          python3.14 -c \'import platform; assert platform.python_version() == "3.14.7"\'\n          python3.14 -m venv "$RUNNER_TEMP/acp-demo-venv"\n          "$RUNNER_TEMP/acp-demo-venv/bin/python3.14" -m pip install --require-hashes --only-binary=:all: -r engineering/dependency_resolution/compiler-requirements.txt\n          "$RUNNER_TEMP/acp-demo-venv/bin/python3.14" -m pip check\n      - name: Verify compiler integration and owned-database boundaries\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-demo-venv/bin/python3.14" -B - <<\'PYTHON\'\n          import unittest\n          suite = unittest.defaultTestLoader.discover(\'verification/demo\')\n          assert suite.countTestCases() == 10, \'DEMO_TEST_COUNT\'\n          result = unittest.TextTestRunner(verbosity=2).run(suite)\n          assert result.wasSuccessful() and result.testsRun == 10 and not result.skipped\n          PYTHON\n      - name: Obtain exact disposable PostgreSQL runtime\n        run: docker pull postgres@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336\n      - name: Compile build browse restart and replay both approved applications\n        shell: bash\n        run: |\n          set -euo pipefail\n          "$RUNNER_TEMP/acp-demo-venv/bin/python3.14" -B engineering/demo/reference.py qualify --workspace "$RUNNER_TEMP/acp-demo" 2>&1 | tee "$RUNNER_TEMP/acp-demo.log"\n      - name: Retain actual compiler package browser restart and cleanup evidence\n        if: always()\n        uses: actions/upload-artifact@v4\n        with:\n          name: successor-reference-demonstration\n          path: |\n            ${{ runner.temp }}/acp-demo.log\n            ${{ runner.temp }}/acp-demo/*.json\n            ${{ runner.temp }}/acp-demo/*-runtime/\n            ${{ runner.temp }}/acp-demo/*/acp/provenance.json\n            ${{ runner.temp }}/acp-demo/*-runtime-outputs/frontend/browser-results.json\n            ${{ runner.temp }}/acp-demo/*-runtime-outputs/frontend/test-results/\n            ${{ runner.temp }}/acp-demo/*-runtime-outputs/backend/src/test/java/acp/browser/\n            ${{ runner.temp }}/acp-demo-inputs/owner.json\n          if-no-files-found: error\n'

# Separately authorized Phase 7 deltas; all old evidence and seal bytes remain pinned.
PHASE7_NEW_HASHES = {'.github/workflows/phase7-source-intelligence.yml': '97c17187c018f6352ce0ccdf49a38ec58596bfcc239ec2021b41448782aea815', 'docs/phase7-source-intelligence.md': '540996b8e88c603d8539d24f1e5beb6de78aa319eac2cf9b7c44826d69c4cab2', 'engineering/source_intelligence/NativeSource.java': 'dc4788fc47458111f8b337c3e88d137fb432490b3b723124d7d52bbaa0f27186', 'engineering/source_intelligence/analysis.py': '52ef63d3c1d22fac953ecc1ce0d62dd0aa5c39eff140f6ea80f33eea7f477ee3', 'engineering/source_intelligence/cli.py': 'cea46d24ce8c915d77c9733e9b7c6ad35e432164904589da3be57f4a586ce1f5', 'engineering/source_intelligence/model.py': 'aa303bdb245686082f5f813c533a4d575241783c39db55dca8f6a3728c42deca', 'engineering/source_intelligence/native.py': 'd7831d4ed9a568526b62b71403fb005aaf948ed2bdb20c8af3bb0cfd75ccb2c4', 'engineering/source_intelligence/qualification.py': 'b54c2f7df1bef409630a0aa0a07b237cbba4419a3465661f6110c523da758621', 'engineering/source_intelligence/typescript.mjs': '7824e5296f90f5f788270ba71d731008a2cea99fc3b649da20dbd8322742ea3f', 'verification/source_intelligence/test_graph.py': 'b2f035922b4c4137161844a98320e66b9fa5f5db265fb7f59fcb5d9007f08321', 'verification/source_intelligence/test_native.py': '6dd7b56bd149bf34d0b7422ca3bad07117aa72ad99d95a49a0163202af5b55ce'}
PHASE7_MODIFIED_HASHES = {'DEV_LINUX.md': '5c695670cf16abc491a0e67814f738d933a21857e8984a2de9bdae012750262b', 'docs/roadmap.md': 'e624826a3de27f49d341a4f018eac1c6cbaaf4e27d5a67b22def7f12f67e75ad', 'verification/route_a/test_preservation.py': '6a769d06155c47cadbc002e3e487a49e13a3a6b38a93c083e22c8b78c5f9ad53', 'README.md': '45e74e0455a8b06f89df1a96f615c2f516dd2dfd28824fffbdfbef2541ede6b9'}

# Authorized Phase 8 integration deltas; no release evidence or predicate changes.
PHASE8_NEW_HASHES = {'.github/workflows/phase8-verification.yml': '83fddf6afa3d41e81235b4383c1d3bf813de109e27f3f66c03132e750d2d486a', 'docs/phase8-verification.md': '741c992614a447556d7fb5f21fcdbe6a80b0dcc02032b67c9e0954c9ba3fdf30', 'engineering/verification/cli.py': 'e293bf0ef280ffa59a2f4ad4f2b3e07655d719188eff808849f57da1665bff9e', 'engineering/verification/inputs.py': '39829feeb6bb4ea32dea520d3bba48b84585a2f381f51fa578cd378434ff5ea1', 'engineering/verification/integration.py': '31fef0758cef1335b907009f02e943887113a81ed6601114138b77ae929f68f8', 'engineering/verification/qualification.py': '604dd2cae738e276200c534a3c08c7da7ca20bb3b97117e983c42af242cf66dd', 'verification/verification/test_integration.py': 'e3713b5d34ade0422bbb36564d70fec65eaf1a5a8169aaaebc24a10ac37ce69a'}
PHASE8_MODIFIED_HASHES = {'README.md': 'f509489a12080ffa69bb167ea4a1d7330f8f372c41fc60424de538ab18bc1623', 'DEV_LINUX.md': '039c6541c7858aca8f4bff7bac56c04776bbfaee7587f41b91f5ff1195371ff7', 'docs/roadmap.md': 'fa9b63945eab68c9ae565c3fd8535e0b202a86a17787ade9a731b3df75d3817e', 'verification/route_a/test_preservation.py': '8c68679979625838139546d9e8a2a62746c0ac2c4bb45940e6cef59be25bf0ff'}

# Exact execution-evidence integration; old accepted source hashes stay immutable.
EXECUTION_NEW_HASHES = {'engineering/verification/execution.py': 'd1ed8f75abdd82f08288e75825366c698c7490051b82f3c8015ed5cf42f9b652'}
EXECUTION_MODIFIED_HASHES = {'.github/workflows/phase8-verification.yml': 'f6ed722d69448d643fead40ed5173ab22cebf871e47b303712cc046e52318b50', 'docs/phase8-verification.md': 'a9c2f28f05e54d21df896956472a4c9b2ca073dbfaa4546293a14961ed231a4c', 'engineering/verification/cli.py': '49d8d449f328b36d28c136fa3f9c3765098fce2c4fc6486b3f90284005a2f577', 'engineering/verification/integration.py': '1a7d5b4ffdd7e7a42c25c3516571d5b5aaa247aec96c8909f311d7bf735fe5cd', 'engineering/verification/qualification.py': 'bef98703ccd289a052a3f1dc465952a25e17a0ec2021ad0402585b7d763daf07', 'verification/verification/test_integration.py': '23deb99b9aa42648679851c69cf0060446ba26948bd6d9544df2cb67ff4a2437'}

PHASE9_NEW_HASHES = {'.github/workflows/phase9-mcp.yml': '1ca812e012b32412eaed75ac5100b748b491d74b00801eeec5d6460b04797ea6', 'docs/phase9-mcp.md': '7c37c7bfe4f30465c2fdeb2ce2f86749102fad649e1671c892a6fa6907b7a048', 'engineering/mcp_adapter/requirements.txt': '2a41fe3820dc1a3f6673457e52cbf956977e5bdbb9c06b1cd0023590be182adc', 'engineering/mcp_adapter/service.py': '635a57769c016ab4d23631be32bdfd0515ee49a65c8f3e59e6163ca6faafb41b', 'engineering/mcp_adapter/server.py': '36590526317aa4baa69cdd09a57c13a983cffcb9e8b3661a23990c10c0de1454', 'engineering/mcp_adapter/prepare.py': 'dcaa245049b8961cb591468bf86e10ac87d22f4e591d853602b080a3b6b35470', 'engineering/mcp_adapter/qualification.py': 'a18b195815bb1baaa60fee8e6628027c56930293917514bca0df3841b44d8864', 'verification/mcp_adapter/test_protocol.py': '9f899fce8499fdfe0d6e2b87d19ac25a4d156aeafdbe45e8b3e1e2dd0a9c810b'}

PHASE9_MODIFIED_HASHES = {'README.md': '404ee312fbdaac2e396d6279272d07266cf21ef4571def19c79a307f288a8e71', 'DEV_LINUX.md': 'de2b0d811715eb56670239d987b4d3f1fbe139bcbe1dea97ae4c40bad190ac97', 'docs/roadmap.md': '3d1199f5b662b05ce8ccfdb3334f2b0b421a7b39b447a44c5841424e34a2439b', 'verification/route_a/test_preservation.py': '7514fad3da45f26fe341d05341818fdc6af944c04e46c1d1928cc83128cd99e0'}

PHASE10_NEW_HASHES = {'.github/workflows/phase10-reference.yml': 'f81b7e4c69d487f170cb561c11419d07be0cc306146ea6aaab010c2cdf8a8880', 'docs/phase10-reference-application.md': 'b7032f291bfa4d15f4d7115b6d41cf908800bc8cbe7ee6f22c7b026d664184e3', 'engineering/reference_application/lifecycle.py': 'b15d31a1ea9bdbf89bc50d584f7f3342899fd177a8cf4f1f0dc73531984fe6ca', 'engineering/reference_application/inspection.py': 'cb183cec767eeb3d74af13c09d0ec06c003b94fb762dbb9d8e2a6483709b357f', 'verification/reference_application/test_lifecycle.py': '2ecf98e094728ffc0df06b5c793ea351ae9d6a181d317e593edd8493ae2d8f31'}

PHASE10_MODIFIED_HASHES = {'README.md': 'c2c0d72e705bf7c0d8f25f84e64bc9fecf97baf4f32eda382fd59d72076db375', 'DEV_LINUX.md': '942a286fc2a447746c13fac505521d0f59d30a1584dcdb2924d03abc8bacba79', 'docs/roadmap.md': '16e990c877188b9ac8e614091a1a2ca4ab39be5a63d0645db9aa837a259d2c68', 'verification/route_a/test_preservation.py': '41c6b4c9ba04af9ad3758ce5cbe3a572ca9f740404afcc416474a00048f83652'}

R2_NEW_HASHES = {'engineering/reference_application/evolution.py': '911c8fe9f909c428fb6cbc58e980bf764f1eeb22ab910819c23a66a5699154e4', 'verification/reference_application/test_evolution.py': '534924872287de86abf773e04090090f6b7f9666864db752d4f6e9e3a7fe8d6d', '.github/workflows/phase10-r2.yml': 'e8441db29be5d4633d80713e9a7d2cc77a1f77d6d6cdf08f24b87dd632bcd188', 'docs/phase10-r2-preview.md': '4ac6ea9bae5f369cdf5f008fb6be1050292e08ebf679724b493f911cb8954aec'}

R2_MODIFIED_HASHES = {'.github/workflows/phase10-reference.yml': 'a5c57a2efe40f5773e3ff0aeb67ca76142ca1dd33329a030ca30606bbce44e44'}

H6_NEW_HASHES = {'.github/workflows/phase11-h6.yml': 'fd3dfcfec784943e4af2133a90d0c48caa1a80733d84cd39ca9b3b72eada8cbe', 'docs/phase11-h6-observability.md': '3d5f8a0ca3dac92e7c73c8e8911d9c9d198978f6008a1b0e7ce66a67724c8dd1', 'engineering/operations/application.py': '324825786f34a165f75c3300a1e92e01bb16c67869159a0be37d536a97fd8478', 'engineering/operations/configuration.py': 'dca232f165ea544f3b50f788c948295f8ec370caec937c3f8d1337d3fe9a904b', 'engineering/operations/fixture.py': 'e1fe41a90c3d88da979167104ab1a27045ec2d173bc52d3c29cb03125d7f0c5e', 'engineering/operations/lab.py': '570a148efd92ff4487925c0d87cd44a5e8c61f305f0b8c10d8ab769818e2b4d8', 'engineering/operations/run.py': 'eb4cad21aaef633b48934d7676ecb6eff0b6528e9711c4a3c23e45483497b6a4', 'engineering/operations/scenarios.py': '0389beeeb68e4c00a37e788d4fc4afb6139a35eb32e7bd7f2b8edcd9b7692bef', 'engineering/operations/target.py': '7eff98da21a35dfc8278fd9f45b368a3f6849d78afb0a4b4ae5a0d521490f6e7', 'engineering/operations/templates/OperationalConfiguration.java': '5aa226994602e209d94994bdc58466898025552863387d3243b442faa652e44e', 'engineering/operations/templates/OperationalRuntime.java': '4ab8677c97c79103254763850f6cdcbccd45c35348a2cc18c7b28bdbe8c665fd', 'verification/operations/test_configuration.py': '75960bae7a9208fa007be3b98f6fc1614c00f570e1e806f5daab32825ddf4f52', 'verification/operations/test_target.py': '1bb258ae170bad38450b43b58acbcf83ccd96999c353bfbd91f6f3b974948ce2'}

H5_NEW_HASHES = {'.github/workflows/phase11-h5.yml': '21abff03bb501cb74fc6b90896dec847c68e0124847dcc780edea46c6aa49528', 'docs/phase11-h5-identity.md': 'ffde6d0ba355201873fe24a93517c125cf23e2f749bea104ca21a8a94a6f174e', 'engineering/identity/application.py': 'e0c59d0147ec4f77e71689eb9ae37e2de59276ee58d7104d6a2b7168400812bc', 'engineering/identity/fixture.py': '5a41dcfd0fd6507f0a3908892a712342d6a5e8ad8c26945162514118ed165bf0', 'engineering/identity/issuer.py': 'cf68ffd39a491cebb0f12af5cbd39942be125d1319043f2f5e926c85bed73825', 'engineering/identity/run.py': '2dbbf0c19698bf4119a2dadcd598388e9b96d27627022c93be3ae7c1acc8e25b', 'engineering/identity/scenarios.py': 'd27ba347f4863d302e6bcd0f9ce389adc9b3878fb1577781176734e4cd602839', 'engineering/identity/target.py': '3d8f2eaa8f6958d8532c939d2727f48f5bfec2ca72f095676ef212d325685d28', 'engineering/identity/templates/SecurityConfiguration.java': '60f53599c98c122298f837fddca7f1500f247b9a91d2770fcd0b9b857d19eaf6', 'verification/identity/test_identity.py': '6916172cc53742c61cdf004365d8dcf352d8991c9690deda284ccdd312ad0bb3'}

H4_NEW_HASHES = {'.github/workflows/phase11-h4.yml': 'f086206e9d5aae435ce25c7dc917ab8359b8fc4f74e66e4d8ba6866e267b7145', 'docs/phase11-h4-create-reliability.md': '5497e0bdaccd602dd197bce22774f5cc704cb097149554dfa9e9c660a993b5d1', 'engineering/create_reliability/diagnostic.py': '193d5e53d0f3271ea8355e68d82717d0343f8eb36a54cba2a83107ab5167b27e', 'engineering/create_reliability/fixture.py': '8b378ed43d47810e4609c76798c894e2cf318b101e54b9eaf7c88018c7473a52', 'engineering/create_reliability/probes.py': '279bbf329aafae4b0c81146799f3012c0fb1e5ae1076f7cced95da9bcd2a12cd', 'engineering/create_reliability/run.py': '334f4240ae595e2a35436b749ed397bfe8826517b5d44f276a131cb4072d5a74', 'verification/create_reliability/test_retained.py': 'ab4bfd11e86781faf4e3b47a0bc6f5739e88317d20d4ad22faa76fbb53318f08'}

H3_NEW_HASHES = {'.github/workflows/phase11-h3.yml': '2a280a0d3326e881bc24ea85b05ed0af08059017dbbe1983b06eac71eceb9fd5', 'docs/phase11-h3-capacity.md': '6f74056753bcf64716507c8f2e40cbcebf2e42e63e8412cf1b9c74096bc707c3', 'engineering/capacity/fixture.py': 'c03790e68b7968943345d8d2b19da1b0b88f3766bf9b7d1fd4b84f8b907afcd7', 'engineering/capacity/metrics.py': 'b7bbc717bad30b9af4ecc2a2317662eb3e0e218202897f919ac82c43b0b988d8', 'engineering/capacity/profile.json': 'b5312b841118d834748241bb6f0e2534e7baa88d078cd55854cb4bf19b8b02bc', 'engineering/capacity/resource-contract-proposal.json': 'd08f25cb68dbe61d9b1de3debda1801b3a55e91e35d71b82f763f6ca36d3a4ea', 'engineering/capacity/run.py': '15d42fea08b338bfc99134c19f8bf6360b77be7955242316d4152a96f840805f', 'engineering/capacity/scenarios.py': '24ff7d4fb3fa926b5d02a2c75eb9ed45aca673c321088ff8aff577614efe8caa', 'engineering/capacity/verification.py': 'c35d0a09fe0dd08873e747417417982285be5760ab2289182029057413e0da76', 'engineering/capacity/workload.py': '3a259feb5df8f104004cf4e594eaa88b1d31ff50932acb1b5dadf397451cd8f9', 'verification/capacity/test_evidence.py': 'e02ccbfedf32d2138a6cffe12633300f075c7c89397383510e43d2812ebdfe64', 'verification/capacity/test_hosted.py': '7fb491510725af611d868fcff6e7df7e27b764883554fbab8d52a592bc5ab46c', 'verification/capacity/test_measurements.py': '77cac84d6d73eec3595c9db09103717f55779a585b4f8636f691cf414db497ab'}

H2_NEW_HASHES = {'.github/workflows/phase11-h2.yml': '8e3e71d518a953595b5623bb8170c6402385c4d8ecc11ef8f8ff01f3cfd7288c', 'docs/phase11-h2-recovery.md': 'bb3830a4b9c7ce53a57c8d586723ab351f8d374a05c08cd00a29b94eddaca2b7', 'engineering/reliability/concurrency.py': 'a6c7b949a26e8b57db3fa3d819c7c68b46eec3a930236001b3949c47e3f6b06a', 'engineering/reliability/database.py': 'fb1ca2faef15aae4da9873982cc220766f4dbaefc4474de81b68c8c9b57c58ee', 'engineering/reliability/fixture.py': '6af3f025f10b7ffa7249c0b99f2b16ea69d4105d96ab67cb8bc2bc4ec5fe4a00', 'engineering/reliability/run.py': '50104f5db75fc99f8213addb3745b879625cd4a416d198c63ac6d88a488a993c', 'engineering/reliability/verification.py': '6a5dc88ebad50f6be5374b10a61fdff45304432656aa4f8ac3c6a281ab3d37cc', 'verification/reliability/test_contract.py': '7b6aec798a11550c2ec275c50c2b77791f92e2e5b1e9b2bae62a7aea113166ad', 'verification/reliability/test_hosted.py': 'c13484d0701cb5c5bedba2450eeb140d6c9ddeba0975b32d0f7a8b1accea4252', 'verification/reliability/test_receipt.py': '5019b6f8daa2630c9edd70bfff3cce5bfb4bbb356cc2945c341500b515d25bff'}
H2_MODIFIED_HASHES = {'engineering/application_evolution/plan.py': 'd9c663419dcb43bfed52548dcc2e8d6871601fb5f13334fe9a85eb7bc34ee317', 'engineering/source_intelligence/model.py': '8bed64c188247a7d0f67a17ed6f1c6d706d3f1f8ddbadba18cbaa0f4e763b8ba'}

H1_NEW_HASHES = {'.github/workflows/phase11-h1.yml': '9e4bf0b3a7020ae1fbc14290aed4a562b479a44bf09b0d13ef3de72e369f3e81', 'docs/phase11-h1-hardening.md': 'f3cf0b80e39fcd8e0034668cdd8f48c6e797408ddd79be29a7348c9573cdcdfa', 'engineering/hardening/application.py': '0c0446b3cf924ff2f9d6cb51df406949176d23dd051e96f9a6b59739c4e2d8ef', 'engineering/hardening/assessment.py': 'b371024c0a3945171bd2293db002381cd4ca3eea3ea86ca4a9a7d631db8c283e', 'engineering/hardening/plugin-inputs.lock.json': '767c441f114bf2066f6f41f29f234177eb32a6705f3a773c42bea25ef9b74fec', 'engineering/hardening/run.py': 'ca3737ace606d7bd35b007317b1a682e163d432ef1e832a49d9b19735743c99d', 'engineering/hardening/target.py': 'bca15a27e8273ff48cff443b3c4cd312ba79587fc4e7405c9c1e376d2119a794', 'verification/hardening/test_assessment.py': '09068a1136a42327106b1ed3a5beecfb2a29337b397aef943a78abcc3da65504', 'verification/hardening/test_hosted.py': '191eba3e4984ce2108d51fb9a009adece923658f14cb09c0d50cf83989a4d307', 'verification/hardening/test_target.py': '923a43efe1458f53403a2c8db80ce79bcf504df22486b5f9a95abfda4319d2c7'}

R8_NEW_HASHES = {'.github/workflows/phase10-r8.yml': 'b36abfc5a00b7a450384a7c4aae0e39be9ce8a09e931d7d18cf0c0c716a529f8', 'docs/phase10-r8-evolution.md': 'c66d8e6b269f6900dedde3a018c14038c3d49d99e69328764020ee19be6ec56d', 'engineering/application_evolution/execution.py': '0be4a3a95e065b3fda30aafec51df304ac1be7ef303489e6697584383843e5f3', 'engineering/application_evolution/journey.ts': '7bfc3152383e4927fa91817ba386c1a0990eae0bb8617eb772b0b0427631f980', 'engineering/application_evolution/plan.py': '57a94dbb1a9c8481305a3da088e63a4052c6b707c31873eb705011281f5b8483', 'engineering/application_evolution/run.py': '46a78d682fc774e029705e8562e1f27ef5377beaf43fa4bbdea51434f9435ef7', 'verification/application_evolution/test_hosted.py': '18615ad7b4c525b7596a8c52a6445a5c793261574919ce5243149001097ef3fc', 'verification/application_evolution/test_plan.py': 'a8c2e2e52450cae9960cf3e924e6e72b84814f51c07b155eece90b3fd56a80f5'}

R7_NEW_HASHES = {'.github/workflows/phase10-r7.yml': '601cc14c01e47d2409dfc07183e81dd96bab385c0faf3f294f440a689352f330', 'docs/phase10-r7-jobs.md': 'eb12bf3d44d841936b6859413261a0df2f0eeab8252595f7696abee3e9ecc1c5', 'engineering/jobs/application.py': '46c141a2e1459e93ac1489af57121ff05bbe16af7467ba98b2e6ca865b8a4244', 'engineering/jobs/compiler.py': 'ece4e879145cc031bca573b9b39efd2789e84cbce5c336b73414cc19fa6495f7', 'engineering/jobs/contracts/authoring-0.8.schema.json': '5f00301618fbe73343d65ea2b155d2316d8b1b4e8e6fd0e8d8254e5b6f5f2159', 'engineering/jobs/contracts/canonical-0.7.schema.json': 'ee67019d917fb7ea5e26efcbc0c389d51ef6f840c1a5deabe3808f6f3a79782b', 'engineering/jobs/execution.py': '66a61f9adeba367b7b0e64d00108d9112eb2ac225ea29692ec1ef3e7f9020513', 'engineering/jobs/fixture.py': '07f46f15a75876ad7c8558c1653d28f46c7ff1f30dfe8a9670a7b9d59717f1b7', 'engineering/jobs/inspection.py': 'f8b62185f99947756125f29064eb3d1ac65faab4ecb14d7efb4b9114cee3903e', 'engineering/jobs/journey.ts': '13b06b8863d9207e0fdc25b529fd1f1a385a5a90c1117c7147a3b49eb35478b6', 'engineering/jobs/mcp.py': '0c915ff6c5dc811f74c25e2eeeb4695ffe39356056766a934f55a354da8f228e', 'engineering/jobs/reference.py': 'eacfcf0ae62ab06197923368dc916edb70b5e50fb6f4b8f8c818f93ca4260bf8', 'engineering/jobs/run.py': 'dec508618aa92ac274a646a9206fb091b84d61e3d04f47a0b809fa35ed1db7e6', 'engineering/jobs/scenarios.py': '0972bffe84aed155bee83c601c52d202aed1a9d23ea7d6315c260d63f1a9525c', 'engineering/jobs/schema.py': '411edf42d8ab277fc184177874f5065f6095dfb8b63e0442eb6b60b48a8a4fab', 'engineering/jobs/semantics.py': '68b2c6103bb4e29515326787d2d40e8f70703ae126e7cdf26043ac20b076f823', 'engineering/jobs/target.py': '5e7169d1e5957d7df60533730d9104a0987f77f7dab5a35333df8a2eb2bf7ce4', 'engineering/jobs/templates/IntegrityWorker.java': 'e3c7faf7d9ae0962591f7079377c7d4b94c63752aae9166208e5d65f8426dec2', 'engineering/jobs/templates/JobController.java': '3d89579db8f7d58573e06e2022a5b2b55d85e39a796ae6c217095c981e11491d', 'engineering/jobs/templates/JobPanel.vue': '9a6b37e54a7d4664c79750be0189f229a749c6a917c73c33e7ab697ad0f6df22', 'proposals/phase10-r7-jobs/authoring.json': '1648d31e973d7828e8cdf695847906bd35fc2e458e03101325683f84c87cb0f2', 'proposals/phase10-r7-jobs/candidate.json': 'acaefd6931b0645c967ec634e977bf82749b8b2c9e27b0c3b3560006e420ebe7', 'proposals/phase10-r7-jobs/review.json': 'b9858b3d4d36a7d60cfb3ae25f5e0b56d60987bf5bbc13cd1de96dde54331b7f', 'verification/jobs/test_hosted.py': '3f6c785305e254df01fb8e7ed0ee3d1348c40b39941a7e19143516bbe6018e7a', 'verification/jobs/test_jobs.py': 'd6b2d085804fbb06a8ae3195ca81b85c300aba65215f9bc0003e77ff7f21ebbf'}

R6_NEW_HASHES = {'.github/workflows/phase10-r6.yml': '3e659face6c138d780aab5d414d498bcba5d05eed9ba830677f59c590131ee7f', 'docs/phase10-r6-documents.md': '973929dfda0b5c8e0df6fe00ac4bdeadb530db86cae3dc3ff2324b870fef8b27', 'engineering/documents/application.py': '759133ad6d63fe97327e3f3ce14edf934443a2556414562812468d79a82498d7', 'engineering/documents/compiler.py': '5730970fa3b09c1da93580865eea72b134beed961b9c12c95372f14e775ed4f0', 'engineering/documents/contracts/authoring-0.7.schema.json': '24df02d3cd8cc815350e27ecb1f5edf8f146a6991cd7dc4fa2582ebdc17057e6', 'engineering/documents/contracts/canonical-0.6.schema.json': '548385ee3dfe366ae635fac2b01713a3d69fba00515a6f32079af53731b07597', 'engineering/documents/execution.py': '0dbc13f5d4bdf931306962b9975341780972bac4a8e4369888aa689ebfba9510', 'engineering/documents/inspection.py': '0fc20dd96f4811776aab24d32e49dbf5682b8cc6eb4931070c23df424a47198c', 'engineering/documents/journey.ts': 'f5226b4b3b7a06206e39440f84bfc7446a57b2f031229159184769997fdd4fde', 'engineering/documents/mcp.py': '94fd21c4ba04f94cb37cead758ea7fdc4004b21757785a954972996519d5e26c', 'engineering/documents/reference.py': '93e5aa4e66c302770d827240cb04cb423c7ef68e67ccfa82caeb8af2038d49b8', 'engineering/documents/run.py': '114e02a497028eac195907930f1f2eb2bef37ec7df6ffe64adec7621ca9ecc38', 'engineering/documents/schema.py': '410e68e5e99ee14472df47aba810b40cfa433dcddff0ae97d413ddbeeea727dd', 'engineering/documents/semantics.py': '4a30b88055a71241aff387e42305add166146723913cbcd8a2463856dabc5a85', 'engineering/documents/target.py': 'e4acecfd14b29e71867ff26ea6c33252a6c0f991b0bd4872ac6eed52e3882d34', 'engineering/documents/templates/DocumentController.java': 'af80801cdd43d6f4bf9bd00a968669675dda541eefff9a821f395445c0575eaa', 'engineering/documents/templates/DocumentPanel.vue': '3a44514f840fb7f5a0f9f284e012ee128d6ed08bf7c9ee07497901227f8c69c5', 'proposals/phase10-r6-documents/authoring.json': 'c520f4e5199768bf25e08c7006459b7443525198c71173a713ef8a073dddf7ed', 'proposals/phase10-r6-documents/candidate.json': 'e44bb757eede3a422113fb639c904df9463b9b0a769f13bbabfde1f20832f7c4', 'proposals/phase10-r6-documents/review.json': 'c12f6fe5ca22846968769075b886c20a85e5a6c1bb8f51ad495e4b76f3c82b99', 'verification/documents/test_documents.py': '8da2add816d000b0f4e01b34ee4a24e2b0b123979bdd63596415b975d8e61f5f', 'verification/documents/test_hosted.py': '08b6bd52f65928598b3cf6041eb4a6b9f7913e54c1b8497cb05672f2aba34e97'}
R6_RUNBOOK_SHA256 = '7c9dfa2cf48caac53c997f2441d9d9038e6169e2b922ea50ab849cfb256cdd3c'

R5_NEW_HASHES = {'.github/workflows/phase10-r5.yml': '90ac730bb62768f7708fc0d8f5e32880d7512c73297e74fdb2ebf0ff0cd13aa1', 'docs/phase10-r5-reporting.md': 'c70dc077001f79ae51a9d37b00e94fb94d48dcb9ff39ea4d216e8e493ee94dbe', 'engineering/compiler_extensions/dispatch.py': '062d0b47d937d08adcadd571f12cae358703d16a73e0973c49097786f1be4d47', 'engineering/reporting/application.py': '0d36e679a65924e04149daee38d0da03b6e4b02e1cf2262efb5d376040a26db4', 'engineering/reporting/compiler.py': 'dd0a1294caa0216d78e41ba9e349ac113eae2c9ba0dfee4c3a826381335de272', 'engineering/reporting/contracts/authoring-0.6.schema.json': 'a3e9c18b0de6ee8b420b07a6bda7bd1fe3ad0cfad926c887053f1a23d0cc375f', 'engineering/reporting/contracts/canonical-0.5.schema.json': '8b72c091d0a556bc0afbc938e3da344e269211ba91f359a608c2aebe342aa5d5', 'engineering/reporting/inspection.py': 'b5ff0669f556a14b09c64ac53e58211bad311a814a46f8e28ea6e90c8abd353c', 'engineering/reporting/journey.ts': 'b9d9d7a04f7eb1dc8d5147a46527ef8c11db5d071fcb1bd4b30182693289bf57', 'engineering/reporting/mcp.py': 'c240cde7c337512da652fc27cb0a74dd673618c73b336cbc971f09b9a49bd93a', 'engineering/reporting/reference.py': 'bbbdb069134c2b42e0ed83285a5b437761aa27a5d19013bd49bcf6b6f9832a22', 'engineering/reporting/run.py': '488db28a1d428bcf6e380c5afe0c25a84328cfce59ada9ec28f78520aef8beb2', 'engineering/reporting/schema.py': 'dd01249c6db28bbbe16ee81ed80487a6b55603ad063a1b715cd9f100eda0ef3a', 'engineering/reporting/semantics.py': '9fa55b34b0a22031c8dd533a8cc5e426c23f598b1abd0c1ac096138e5c1bf737', 'engineering/reporting/target.py': 'db1608ba4b9268e0d762723ef531a77b5e9faf74bba8274b0c52293ed6f0bd2e', 'engineering/reporting/templates/ReportPanel.vue': '89f6477ce7625b05687572fcd02f9d8c6991a75b522c653f731dcf636c61854a', 'engineering/reporting/templates/ReportingController.java': 'c4d8403bb7b41cecb92885e1fc41a77d7a902e2f0d1ee1479bd4f24f56adf71f', 'proposals/phase10-r5-reporting/authoring.json': '24d26b5b1a8dcd1c156d076ceaa70d9d360f81abbccac0c31898bcea4185b0f8', 'proposals/phase10-r5-reporting/candidate.json': 'baadf9230500d8e7e86b524af531de43b1fd87a2cf3d9006eae9276fc6c6c856', 'proposals/phase10-r5-reporting/review.json': '34f0980084b953ad5c78dd2c4b16b2cfde4b30cacd4ae917db5f402233722020', 'verification/reporting/test_reporting.py': 'e0ae0e4ae1c637fb05f194716595d2e62c89030d1f950f4bff9c3f44e91d614b'}

R4_NEW_HASHES = {'.github/workflows/phase10-r4.yml': '8d2cc575056fdbcce65866682e15d6dc1f6e1f927d13b8d4dd01ef2a62ab792d', 'docs/phase10-r4-native-create.md': '4a4119deaec13def625c0d33dfad8fb65d0db85b067a6f1db87940f9d7175c2b', 'engineering/native_create/application.py': 'b978cb3bc2f33b0bec4ce8d48bda3597da471ba9138f2678f5eb60d3d59527ad', 'engineering/native_create/compiler.py': '1461a2855b5e37d9c51b001f9afc28cba3276d242f21aaae291146bbf91406fe', 'engineering/native_create/mcp.py': '6b67fa44da19db70ddb1e4bbf17c10fa7ca0cb0e79867f5ea813fce80f907fdd', 'engineering/native_create/preview.py': '08ba2191bfe15081a33c21c6db975e509c570e5d0d760ac0574585f6c6b7b067', 'engineering/native_create/reference.py': '39a580f9257be1834bc433d1e2ee3b95889fe0080a58a96572c53db854afb838', 'engineering/native_create/run.py': '5bba96900f3f9d28f439174d4edc2dc1ff6d440a48cfbf85cae2bf2de713f003', 'engineering/native_create/schema.py': '935b87ff4a4892bdcd8fbc2151d269d9828f46245c1fd9b08ce6530998e7f9cf', 'engineering/native_create/semantics.py': '4442ef2b25e6b7ba96f1be20a2c7e9ae7fadcbc3ef8bd9c0088e9c5d4903bc70', 'engineering/native_create/target.py': '7b2a10044cd9d4892c2aa4ffaf79d05e4f4eadcbe3fd2a3d2a0ed3033afae370', 'engineering/native_create/contracts/authoring-0.5.schema.json': 'a4a6fefaa59205210800869544be8018f27baae36d52c801eaf115ca5022052f', 'engineering/native_create/contracts/canonical-0.4.schema.json': '36fcb805b68586daea1fe102a38825b1fbd43ecf4170332d492d3ce4f8a06588', 'verification/native_create/test_compiler.py': 'c0f26a08a31c4038ee6fab3c72c2898abdcbadef864590f28f451ddcabf24b5f', 'verification/native_create/test_semantics.py': '8427f7163038d8d9e25e1cece825afca6ac41631cac7aec9c8c8b86bd2a8926f', 'verification/native_create/test_target.py': '36ce643238183f43e06e6b354cca205377853d411712a163351066724c38f642', 'proposals/phase10-r4-create/authoring.json': 'c50cd79ef188b13bc556758bff165e1b62206f3a885dfae568a3312d936aca2c', 'proposals/phase10-r4-create/candidate.json': '921c80ccb69655dc82799da43fa1c18d34c8e1fae636da8d615c19bcd238a675', 'proposals/phase10-r4-create/review.json': '1124195571df13ff033676457257847d7090a4ae122a35b29db4914f10441b3a'}

R3_NEW_HASHES = {'.github/workflows/phase10-r3.yml': '1532ed5c12cfbb70f5a79b0006b48146f0e55bb3e57102c8e93ae10645347203', 'docs/phase10-r3-intake.md': '5ba24eac503008ac5f6df6e83d5019beea27510408aae8f2432a8885f82a542a', 'engineering/reference_application/intake.py': '4517f1325e1bf49654f14e7adcf60231c02d5ed23951ddd0991c9de54ef667eb', 'engineering/reference_application/intake_run.py': '064c2347586e0032c434483c6da44b4fd1afde7165f4d5b117d2582d6e2031e5', 'engineering/reference_application/intake_templates/IntakeController.java': '76cd92e77756328ef84f28cd62d915ee11d944f0320564971a89ec7f598e4e7a', 'engineering/reference_application/intake_templates/IntakeForm.vue': 'b9e05b5b5d82e0b17fb3251b451ef9f230b43c2014736749b21c725abc2d3956', 'verification/reference_application/test_intake.py': 'c229653e08b732555f237ebabada26f9efc92860a894b6c91a6594b9db218573', 'proposals/phase10-r3-intake/candidate.json': '9a331fca17392a5bd093d3035f22cd72ad2fb82c8e62e5f2b7f2bc1082235ab3', 'proposals/phase10-r3-intake/change.json': '4662d3f7019fd1a34df8403c0b87ca0564b202a4b7576bc0e44999c455271c85', 'proposals/phase10-r3-intake/plan.json': 'a5cf60cdcc21a5dcfd7f84e906ffdec98abcbe3ef953e04b4f792997db75b323', 'proposals/phase10-r3-intake/review.json': '8c7cf8ca9f6fe8d1a05465fb8e030bd3d6ff269855ccc9cdf33218bcc9ec24b8', 'proposals/phase10-r3-intake/synthetic-contract.json': 'b84a5c1caff6e4738eaf3e407ff90bcd40cd7e6c515d7470a9c857f243d988cc'}

def preserved_bytes(path):
    # Validate the exact two authorized CI-only modifications before comparing
    # the remainder to immutable historical bytes. No path-wide exception.
    actual = path.read_bytes()
    try:
        relative = path.relative_to(ROOT).as_posix()
    except ValueError:
        return actual
    if relative == 'docs/phase10-reference-application.md':
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest()==R6_RUNBOOK_SHA256,relative
        original=subprocess.check_output(['git','show','eb2cad7caead8a14e7f3c32a5bb1cf148ac44f05:'+relative],cwd=ROOT)
        assert actual.startswith(original) and len(actual)>len(original),relative
        actual=original
    if relative in R2_MODIFIED_HASHES:
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest()==R2_MODIFIED_HASHES[relative],relative
        actual=subprocess.check_output(['git','show','fea3c1a6e29cc13cec2e33d8abf8bcd90a4bbc47:'+relative],cwd=ROOT)
    if relative in PHASE10_MODIFIED_HASHES:
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest()==PHASE10_MODIFIED_HASHES[relative],relative
        actual=subprocess.check_output(['git','show','4a3db4ca30dcdc41f598c098f3de02534072035b:'+relative],cwd=ROOT)
    if relative in PHASE9_MODIFIED_HASHES:
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest()==PHASE9_MODIFIED_HASHES[relative],relative
        actual=subprocess.check_output(['git','show','9396b1a6f999da0c3c2f16156a8efca3f353149d:'+relative],cwd=ROOT)
    if relative in EXECUTION_MODIFIED_HASHES:
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest()==EXECUTION_MODIFIED_HASHES[relative],relative
        actual=subprocess.check_output(['git','show','9fd0fe07249fc1b23e9850175c478d303e1e06c8:'+relative],cwd=ROOT)
    if relative in PHASE8_MODIFIED_HASHES:
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest() == PHASE8_MODIFIED_HASHES[relative], relative
        actual = subprocess.check_output(['git','show','8b351ce75ca44da2bf7516414ff4e94c645563f9:' + relative],cwd=ROOT)
    if relative in PHASE7_MODIFIED_HASHES:
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest() == PHASE7_MODIFIED_HASHES[relative], relative
        actual = subprocess.check_output(['git','show','c265466a23100054f48e9c53cbde7b33d65b81aa:' + relative],cwd=ROOT)
    if relative in DELIVERY_MODIFIED_HASHES:
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest() == DELIVERY_MODIFIED_HASHES[relative], relative
        actual = subprocess.check_output(['git','show','3c10461c7bb5ee2042ccf4f36f949d748d359625:' + relative],cwd=ROOT)
    if relative in RATE_CLOCK_COMPAT_HASHES:
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest() == RATE_CLOCK_COMPAT_HASHES[relative], relative
        return subprocess.check_output(['git','show','99c0244052f01c0df3904af0c236de1d027fe77f:' + relative],cwd=ROOT)
    if relative == 'engineering/generator_candidates/spring_vue_postgres_0_6/candidate.py':
        assert not path.is_symlink() and hashlib.sha256(actual).hexdigest() == RATE_CLOCK_HASHES[relative], relative
        return subprocess.check_output(['git','show','355b8f72cf8012e17aa24f23042be3e8eebbff3f:' + relative],cwd=ROOT)
    if relative == '.github/workflows/phase6-v3-offline.yml':
        assert actual.endswith(DELIVERY_CI_JOB) and actual.count(DELIVERY_CI_JOB)==1, 'EXACT_DELIVERY_JOB_REQUIRED'
        actual=actual[:-len(DELIVERY_CI_JOB)]
        assert actual.endswith(SECURITY_CI_JOB) and actual.count(SECURITY_CI_JOB)==1, 'EXACT_SECURITY_JOB_REQUIRED'
        actual=actual[:-len(SECURITY_CI_JOB)]
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
    for relative in (set(PRIVACY_MODIFIED_HASHES) | set(B0_MODIFIED_HASHES) | set(CI_PRESERVATION_FIX_HASHES) | set(DELIVERY_MODIFIED_HASHES) | set(PHASE7_MODIFIED_HASHES) | set(PHASE8_MODIFIED_HASHES) | set(EXECUTION_MODIFIED_HASHES) | set(PHASE9_MODIFIED_HASHES) | set(PHASE10_MODIFIED_HASHES) | set(R2_MODIFIED_HASHES)) & paths:
        if subprocess.run(['git','cat-file','-e',accepted+':'+relative],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:continue
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
                        if ast.unparse(call.args[0]) == 'len(self.verified_ci_additions())' and isinstance(call.args[1], ast.Constant) and call.args[1].value in (39, 41, 45, 46, 49, 51, 56, 59, 62, 64, 68, 79, 86, 87, 95, 100, 104, 116, 135, 156, 177, 178, 203, 211):
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
            node.elts = [value for value in node.elts if not (isinstance(value, ast.Starred) and ast.unparse(value) in ("*(':(exclude)' + name for name in DELIVERY_MODIFIED_HASHES)", "*(':(exclude)' + name for name in PHASE7_MODIFIED_HASHES)", "*(':(exclude)' + name for name in PHASE8_MODIFIED_HASHES)", "*(':(exclude)' + name for name in PHASE9_MODIFIED_HASHES)", "*(':(exclude)' + name for name in PHASE10_MODIFIED_HASHES)", "*(':(exclude)' + name for name in R2_MODIFIED_HASHES)"))]
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
    def test_r8_exact_evolution_rejects_unreviewed_mutations(self):
        self.assertEqual(len(R8_NEW_HASHES),8)
        self.verified_ci_additions()
        real=Path.read_bytes
        for name in R8_NEW_HASHES:
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda p:real(p)+b'unreviewed' if p==path else real(p)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_r7_exact_jobs_rejects_unreviewed_mutations(self):
        self.assertEqual(len(R7_NEW_HASHES),25)
        self.verified_ci_additions()
        real=Path.read_bytes
        for name in R7_NEW_HASHES:
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda p:real(p)+b'unreviewed' if p==path else real(p)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_r6_exact_document_source_and_runbook_append(self):
        self.assertEqual(len(R6_NEW_HASHES),22)
        self.verified_ci_additions()
        real=Path.read_bytes
        for name in [*R6_NEW_HASHES,'docs/phase10-reference-application.md']:
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda p:real(p)+b'unreviewed' if p==path else real(p)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_r5_exact_reporting_rejects_unreviewed_mutations(self):
        self.assertEqual(len(R5_NEW_HASHES),21)
        self.verified_ci_additions()
        real=Path.read_bytes
        for name in R5_NEW_HASHES:
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda p:real(p)+b'unreviewed' if p==path else real(p)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_r4_exact_native_create_rejects_unreviewed_mutations(self):
        self.assertEqual(len(R4_NEW_HASHES),19)
        self.verified_ci_additions()
        real=Path.read_bytes
        for name in R4_NEW_HASHES:
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda p:real(p)+b'unreviewed' if p==path else real(p)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_r3_exact_intake_rejects_unreviewed_mutations(self):
        self.assertEqual(len(R3_NEW_HASHES),12)
        self.verified_ci_additions()
        real=Path.read_bytes
        for name in R3_NEW_HASHES:
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda item: real(item)+b'unreviewed' if item==path else real(item)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_r2_exact_preview_rejects_unreviewed_mutations(self):
        self.assertEqual(len(R2_NEW_HASHES),4)
        self.assertEqual(set(R2_MODIFIED_HASHES),{'.github/workflows/phase10-reference.yml'})
        self.verified_ci_additions()
        real=Path.read_bytes
        for name in (*R2_NEW_HASHES,*R2_MODIFIED_HASHES):
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda item: real(item)+b'unreviewed' if item==path else real(item)):
                with self.assertRaises(AssertionError):
                    if name in R2_MODIFIED_HASHES:preserved_bytes(path)
                    else:self.verified_ci_additions()

    def test_phase10_exact_lifecycle_rejects_unreviewed_mutations(self):
        self.assertEqual(len(PHASE10_NEW_HASHES),5)
        self.assertEqual(set(PHASE10_MODIFIED_HASHES),{'README.md','DEV_LINUX.md','docs/roadmap.md','verification/route_a/test_preservation.py'})
        self.verified_ci_additions()
        real=Path.read_bytes
        for name in (*PHASE10_NEW_HASHES,*PHASE10_MODIFIED_HASHES):
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda item: real(item)+b'unreviewed' if item==path else real(item)):
                with self.assertRaises(AssertionError):
                    if name in PHASE10_MODIFIED_HASHES:preserved_bytes(path)
                    else:self.verified_ci_additions()

    def test_phase9_exact_readonly_adapter_rejects_unreviewed_mutations(self):
        self.assertEqual(len(PHASE9_NEW_HASHES),8)
        self.assertEqual(set(PHASE9_MODIFIED_HASHES),{'README.md','DEV_LINUX.md','docs/roadmap.md','verification/route_a/test_preservation.py'})
        self.verified_ci_additions()
        real=Path.read_bytes
        for name in (*PHASE9_NEW_HASHES,*PHASE9_MODIFIED_HASHES):
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda item: real(item)+b'unreviewed' if item==path else real(item)):
                with self.assertRaises(AssertionError):
                    if name in PHASE9_MODIFIED_HASHES:preserved_bytes(path)
                    else:self.verified_ci_additions()

    def test_execution_integration_rejects_any_unreviewed_byte(self):
        self.assertEqual(set(EXECUTION_NEW_HASHES), {'engineering/verification/execution.py'})
        self.assertEqual(len(EXECUTION_MODIFIED_HASHES), 6)
        self.verified_ci_additions()
        real=Path.read_bytes
        for name in (*EXECUTION_NEW_HASHES,*EXECUTION_MODIFIED_HASHES):
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda item: real(item)+b'unreviewed' if item==path else real(item)):
                with self.assertRaises(AssertionError):
                    if name in EXECUTION_MODIFIED_HASHES:preserved_bytes(path)
                    else:self.verified_ci_additions()

    def test_phase8_exact_integration_and_document_changes_reject_mutation(self):
        self.assertEqual(set(PHASE8_MODIFIED_HASHES), {'README.md','DEV_LINUX.md','docs/roadmap.md','verification/route_a/test_preservation.py'})
        self.assertEqual(len(PHASE8_NEW_HASHES), 7)
        self.verified_ci_additions()
        real_read=Path.read_bytes
        for name in (*PHASE8_NEW_HASHES,*PHASE8_MODIFIED_HASHES):
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda item: real_read(item)+b'unreviewed' if item==path else real_read(item)):
                with self.assertRaises(AssertionError):
                    if name in PHASE8_MODIFIED_HASHES:preserved_bytes(path)
                    else:self.verified_ci_additions()

    def test_phase7_exact_source_and_document_changes_reject_mutation(self):
        self.assertEqual(set(PHASE7_MODIFIED_HASHES), {'README.md','DEV_LINUX.md','docs/roadmap.md','verification/route_a/test_preservation.py'})
        self.assertEqual(len(PHASE7_NEW_HASHES), 11)
        self.verified_ci_additions()
        real_read=Path.read_bytes
        for name in (*PHASE7_NEW_HASHES,*PHASE7_MODIFIED_HASHES):
            path=ROOT/name
            with patch.object(Path,'read_bytes',lambda item: real_read(item)+b'unreviewed' if item==path else real_read(item)):
                with self.assertRaises(AssertionError):
                    if name in PHASE7_MODIFIED_HASHES:preserved_bytes(path)
                    else:self.verified_ci_additions()

    def test_h1_exact_successor_rejects_mutated_source_and_workflow(self):
        self.assertEqual(len(H1_NEW_HASHES), 10)
        self.verified_ci_additions()
        real = Path.read_bytes
        for name in H1_NEW_HASHES:
            path = ROOT / name
            with patch.object(Path, 'read_bytes', lambda p: real(p)+b'unreviewed' if p==path else real(p)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_h2_exact_runtime_and_successor_binding_reject_mutation(self):
        self.assertEqual(len(H2_NEW_HASHES), 10)
        self.assertEqual(set(H2_MODIFIED_HASHES), {'engineering/application_evolution/plan.py', 'engineering/source_intelligence/model.py'})
        self.verified_ci_additions()
        original = Path.read_bytes
        for name in {**H2_NEW_HASHES, **H2_MODIFIED_HASHES}:
            path = ROOT / name
            with self.subTest(path=name), patch.object(Path, 'read_bytes', lambda item: b'unreviewed' if item == path else original(item)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_h3_exact_capacity_sources_and_workflow_reject_mutation(self):
        self.assertEqual(len(H3_NEW_HASHES), 13)
        self.verified_ci_additions()
        original = Path.read_bytes
        for name in H3_NEW_HASHES:
            path = ROOT / name
            with self.subTest(path=name), patch.object(Path, 'read_bytes', lambda item: b'unreviewed' if item == path else original(item)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_h4_exact_observation_sources_reject_mutation(self):
        self.assertEqual(len(H4_NEW_HASHES),7)
        self.verified_ci_additions()
        original=Path.read_bytes
        for name in H4_NEW_HASHES:
            path=ROOT/name
            with self.subTest(path=name),patch.object(Path,'read_bytes',lambda item:b'unreviewed' if item==path else original(item)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def test_h5_exact_identity_sources_reject_mutation(self):
        self.assertEqual(len(H5_NEW_HASHES),10)
        self.verified_ci_additions()
        original=Path.read_bytes
        for name in H5_NEW_HASHES:
            path=ROOT/name
            with self.subTest(path=name),patch.object(Path,'read_bytes',lambda item:b'unreviewed' if item==path else original(item)):
                with self.assertRaises(AssertionError):self.verified_ci_additions()

    def verified_ci_additions(self):
        for relative, expected in {**H6_NEW_HASHES, **H5_NEW_HASHES, **H4_NEW_HASHES, **H3_NEW_HASHES, **H2_NEW_HASHES, **H1_NEW_HASHES, **R8_NEW_HASHES, **R7_NEW_HASHES, **R6_NEW_HASHES, **R5_NEW_HASHES, **R4_NEW_HASHES, **R3_NEW_HASHES, **R2_NEW_HASHES, **PHASE10_NEW_HASHES, **PHASE9_NEW_HASHES, **EXECUTION_NEW_HASHES, **PHASE8_NEW_HASHES, **PHASE7_NEW_HASHES, **DELIVERY_NEW_HASHES, **V3_CI_HASHES, **SUCCESSOR_HASHES, **GENERATOR_BUILD_HASHES, **B0_NEW_HASHES, **RELEASE_NEW_HASHES, **DEPENDENCY_NEW_HASHES, **TRACEABILITY_NEW_HASHES, **PERFORMANCE_NEW_HASHES, **RECOVERY_NEW_HASHES, **SECURITY_NEW_HASHES, **{p:h for p,h in RATE_CLOCK_HASHES.items() if p not in SUCCESSOR_HASHES}, **H2_MODIFIED_HASHES}.items():
            path = ROOT / relative
            self.assertFalse(path.is_symlink(), relative)
            self.assertTrue(path.is_file(), relative)
            self.assertEqual(hashlib.sha256(preserved_bytes(path)).hexdigest(), expected, relative)
            self.assertFalse(path.stat().st_mode & 0o111, relative)
        return set(H6_NEW_HASHES) | set(H5_NEW_HASHES) | set(H4_NEW_HASHES) | set(H3_NEW_HASHES) | set(H2_NEW_HASHES) | set(H2_MODIFIED_HASHES) | set(H1_NEW_HASHES) | set(R8_NEW_HASHES) | set(R7_NEW_HASHES) | set(R6_NEW_HASHES) | set(R5_NEW_HASHES) | set(R4_NEW_HASHES) | set(R3_NEW_HASHES) | set(R2_NEW_HASHES) | set(PHASE10_NEW_HASHES) | set(PHASE9_NEW_HASHES) | set(EXECUTION_NEW_HASHES) | set(PHASE8_NEW_HASHES) | set(PHASE7_NEW_HASHES) | set(DELIVERY_NEW_HASHES) | set(V3_CI_HASHES) | set(SUCCESSOR_HASHES) | set(GENERATOR_BUILD_HASHES) | set(B0_NEW_HASHES) | set(RELEASE_NEW_HASHES) | set(DEPENDENCY_NEW_HASHES) | set(TRACEABILITY_NEW_HASHES) | set(PERFORMANCE_NEW_HASHES) | set(RECOVERY_NEW_HASHES) | set(SECURITY_NEW_HASHES) | set(RATE_CLOCK_HASHES)

    def test_delivery_changes_are_exact_and_reject_mutated_source_or_job(self):
        self.assertEqual(len(DELIVERY_NEW_HASHES), 4)
        self.assertEqual(len(DELIVERY_MODIFIED_HASHES), 7)
        self.verified_ci_additions()
        real_read = Path.read_bytes
        for relative in (*DELIVERY_NEW_HASHES, *DELIVERY_MODIFIED_HASHES, '.github/workflows/phase6-v3-offline.yml'):
            path = ROOT / relative
            if relative in DELIVERY_MODIFIED_HASHES:preserved_bytes(path)
            with patch.object(Path, 'read_bytes', lambda item: real_read(item)+b'unreviewed' if item == path else real_read(item)):
                with self.assertRaises(AssertionError):
                    if relative in DELIVERY_MODIFIED_HASHES:preserved_bytes(path)
                    else:self.verified_ci_additions()

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
        self.assertEqual(set(changes) - (set(untracked) & transient), set(H6_NEW_HASHES) | set(H5_NEW_HASHES) | set(H4_NEW_HASHES) | set(H3_NEW_HASHES) | set(H2_NEW_HASHES) | set(H2_MODIFIED_HASHES) | set(H1_NEW_HASHES) | set(R8_NEW_HASHES) | set(R7_NEW_HASHES) | set(R6_NEW_HASHES) | set(R5_NEW_HASHES) | set(R4_NEW_HASHES) | set(R3_NEW_HASHES) | set(R2_NEW_HASHES) | set(R2_MODIFIED_HASHES) | set(PHASE10_NEW_HASHES) | set(PHASE10_MODIFIED_HASHES) | set(PHASE9_NEW_HASHES) | set(PHASE9_MODIFIED_HASHES) | set(EXECUTION_NEW_HASHES) | set(EXECUTION_MODIFIED_HASHES) | set(PHASE8_NEW_HASHES) | set(PHASE8_MODIFIED_HASHES) | set(PHASE7_NEW_HASHES) | set(PHASE7_MODIFIED_HASHES) | set(DELIVERY_NEW_HASHES) | set(DELIVERY_MODIFIED_HASHES) | set(DEPENDENCY_NEW_HASHES) | set(TRACEABILITY_NEW_HASHES) | set(PERFORMANCE_NEW_HASHES) | set(RECOVERY_NEW_HASHES) | set(SECURITY_NEW_HASHES) | set(RATE_CLOCK_HASHES) | {'.github/workflows/phase6-v3-offline.yml'} | set(RELEASE_NEW_HASHES) | set(B0_NEW_HASHES) | set(B0_MODIFIED_HASHES) | set(CI_PRESERVATION_FIX_HASHES) | {'verification/evidence_admission/test_preservation.py', '.github/workflows/acp-contracts.yml'})

    def test_b0_change_inventory_validates_transient_output_before_exclusion(self):
        head='a'*40
        expected=set(H6_NEW_HASHES) | set(H5_NEW_HASHES) | set(H4_NEW_HASHES) | set(H3_NEW_HASHES) | set(H2_NEW_HASHES) | set(H2_MODIFIED_HASHES) | set(H1_NEW_HASHES) | set(R8_NEW_HASHES) | set(R7_NEW_HASHES) | set(R6_NEW_HASHES) | set(R5_NEW_HASHES) | set(R4_NEW_HASHES) | set(R3_NEW_HASHES) | set(R2_NEW_HASHES) | set(R2_MODIFIED_HASHES) | set(PHASE10_NEW_HASHES) | set(PHASE10_MODIFIED_HASHES) | set(PHASE9_NEW_HASHES) | set(PHASE9_MODIFIED_HASHES) | set(EXECUTION_NEW_HASHES) | set(EXECUTION_MODIFIED_HASHES) | set(PHASE8_NEW_HASHES) | set(PHASE8_MODIFIED_HASHES) | set(PHASE7_NEW_HASHES) | set(PHASE7_MODIFIED_HASHES) | set(DELIVERY_NEW_HASHES) | set(DELIVERY_MODIFIED_HASHES) | set(DEPENDENCY_NEW_HASHES) | set(TRACEABILITY_NEW_HASHES) | set(PERFORMANCE_NEW_HASHES) | set(RECOVERY_NEW_HASHES) | set(SECURITY_NEW_HASHES) | set(RATE_CLOCK_HASHES) | {'.github/workflows/phase6-v3-offline.yml'} | set(RELEASE_NEW_HASHES) | set(B0_NEW_HASHES) | set(B0_MODIFIED_HASHES) | set(CI_PRESERVATION_FIX_HASHES) | {'verification/evidence_admission/test_preservation.py', '.github/workflows/acp-contracts.yml'}
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
        self.assertEqual(len(self.verified_ci_additions()), 274)
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
        subprocess.run(['git','diff','--exit-code','--diff-filter=MDRT',BASELINE,'--',':(exclude).github/workflows/acp-contracts.yml',':(exclude)engineering/ci/parity.py',':(exclude)tooling/audit/criteria.py',':(exclude)tooling/audit/phase6.py',':(exclude)tooling/tests/test_retained_inventory.py',':(exclude)verification/route_a/test_preservation.py', *(':(exclude)'+name for name in DELIVERY_MODIFIED_HASHES), *(':(exclude)'+name for name in PHASE7_MODIFIED_HASHES), *(':(exclude)'+name for name in PHASE8_MODIFIED_HASHES), *(':(exclude)'+name for name in PHASE9_MODIFIED_HASHES), *(':(exclude)'+name for name in PHASE10_MODIFIED_HASHES), *(':(exclude)'+name for name in R2_MODIFIED_HASHES)],cwd=ROOT,check=True,capture_output=True)
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
