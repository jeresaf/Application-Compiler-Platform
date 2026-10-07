"""Evidence guard regressions; passing these does not select a production stack."""
import json
from pathlib import Path
import sys
from threading import Event
import unittest

AREA = Path(__file__).resolve().parent
sys.path.insert(0, str(AREA))
from generate import encode
from worker import exchange, WorkerFailure, MAX_MESSAGE


class EvidenceTests(unittest.TestCase):
    def test_preregistered_weights_and_gates(self):
        protocol = json.loads((AREA / "protocol.json").read_text())
        self.assertTrue(protocol["registeredBeforeMeasurements"])
        self.assertEqual(100, sum(protocol["softWeights"].values()))
        self.assertEqual(6, len(protocol["hardGates"]))

    def test_fixtures_are_regenerable_without_modifying_source(self):
        root = AREA.parents[1]
        for name in ("payment", "case-management"):
            source = json.loads((root / f"test-corpus/phase1/{name}.json").read_text())
            self.assertEqual(encode(source), (AREA / f"corpora/{name}.acp").read_text())

    def test_worker_round_trip_and_failures(self):
        self.assertEqual({"stableId": "ENT-1"}, exchange([sys.executable, str(AREA / "worker.py")], {"stableId": "ENT-1"})["payload"])
        scripts = {
            "CRASH": "raise SystemExit(2)",
            "MALFORMED": "print('???')",
            "VERSION": "print('{\"protocol\":\"other/2\"}')",
            "RESPONSE_SIZE": "print('x' * 1048577)",
            "TIMEOUT": "import time; time.sleep(5)",
        }
        for expected, code in scripts.items():
            with self.subTest(expected=expected), self.assertRaisesRegex(WorkerFailure, expected):
                exchange([sys.executable, "-c", code], {}, timeout=.2)
        event = Event(); event.set()
        with self.assertRaisesRegex(WorkerFailure, "CANCELLED"):
            exchange([sys.executable, str(AREA / "worker.py")], {}, cancelled=event)
        with self.assertRaisesRegex(WorkerFailure, "REQUEST_SIZE"):
            exchange([sys.executable, str(AREA / "worker.py")], "x" * MAX_MESSAGE)


if __name__ == "__main__":
    unittest.main()
