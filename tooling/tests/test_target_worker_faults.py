"""Bounded Phase 6 supervision faults; no production-gate certification."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from target_worker import ROOT, ProductionTarget, TargetWorker, TargetWorkerError


class WorkerFaultTests(unittest.TestCase):
    def worker(self, source, **limits):
        return TargetWorker(command=(sys.executable, "-I", "-B", "-c", source), **limits)

    def test_malformed_and_ambiguous_output_fails_closed(self):
        for index, response in enumerate(["invalid", "[]", '{"ok":1,"result":{}}', '{"ok":true,"result":{},"extra":1}',
                         '{"ok":true,"ok":false,"result":{}}', '{"ok":true,"result":NaN}',
                         '{"ok":false,"error":"unsafe message with secrets"}',
                         '{"ok":true,"result":' + '[' * 2000 + '0' + ']' * 2000 + '}']):
            with self.subTest(case=index), self.assertRaisesRegex(TargetWorkerError, "WORKER_PROTOCOL"):
                self.worker("import sys; sys.stdout.write(" + repr(response) + ")").call("manifest", {})

    def test_oversized_output_is_stopped_while_streaming(self):
        source = "import os\nwhile True: os.write(1, b'x' * 65536)"
        start = time.monotonic()
        with self.assertRaisesRegex(TargetWorkerError, "WORKER_OUTPUT_LIMIT"):
            self.worker(source, output_limit=1024).call("manifest", {})
        self.assertLess(time.monotonic() - start, 5)

    def test_large_stderr_is_bounded_and_not_exposed(self):
        with self.assertRaisesRegex(TargetWorkerError, "WORKER_OUTPUT_LIMIT"):
            self.worker("import os\nwhile True: os.write(2, b'protected' * 8192)").call("manifest", {})
        with self.assertRaisesRegex(TargetWorkerError, "WORKER_STDERR"):
            self.worker("import sys; print('protected', file=sys.stderr); print('{\"ok\":true,\"result\":{}}')").call("manifest", {})

    def test_timeout_crash_and_signal_are_distinct_failures(self):
        for source, code in [("import time; time.sleep(60)", "WORKER_TIMEOUT"),
                             ("import os; os._exit(23)", "WORKER_EXIT"),
                             ("import os,signal; os.kill(os.getpid(), signal.SIGTERM)", "WORKER_SIGNAL")]:
            with self.subTest(code=code), self.assertRaisesRegex(TargetWorkerError, code):
                self.worker(source, timeout=0.2).call("manifest", {})

    def test_sandbox_setup_failure_never_runs_generation(self):
        source = f'''import sys
sys.path.insert(0, {str(ROOT / 'worker')!r})
import main
def fail(): raise OSError('private sandbox implementation detail')
main.sandbox = fail
main.main()
'''
        with self.assertRaisesRegex(TargetWorkerError, "^SANDBOX_SETUP$"):
            self.worker(source).call("manifest", {})

    def test_parallel_disposable_workers_return_identical_manifests(self):
        worker = TargetWorker()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: worker.call("manifest", {}), range(8)))
        self.assertTrue(all(value == results[0] for value in results))

    def test_changed_generator_bundle_blocks_before_and_after_call(self):
        target = ProductionTarget()
        with patch("target_worker.bundle_digest", return_value="changed"), self.assertRaisesRegex(TargetWorkerError, "BUNDLE_CHANGED"):
            target._call("manifest", {})
        with patch("target_worker.bundle_digest", side_effect=[target.bundle, "changed"]), self.assertRaisesRegex(TargetWorkerError, "BUNDLE_CHANGED"):
            target._call("manifest", {})


if __name__ == "__main__":
    unittest.main()
