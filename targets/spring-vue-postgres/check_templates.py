"""Reproduce INCOMPLETE Phase 6 template checks, never claim target acceptance.

Full-domain negotiation must remain visibly separate from unnegotiated template
compilation. Remove this development-only bypass when complete admission exists.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tooling"))
sys.path.insert(0, str(TARGET / "worker"))
from canonical_ir import validate_snapshot
from canonical_json import load
from generation import plan
from model import lower
from target_worker import PROFILE, TargetWorker, TargetWorkerError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--acknowledge-unnegotiated-templates", action="store_true", required=True)
    parser.add_argument("--run-builds", action="store_true")
    args = parser.parse_args()
    output = args.output.absolute()
    if output.exists():
        parser.error("output must be a new directory; existing files are never overwritten")
    templates = {p.relative_to(TARGET / "templates").as_posix(): p.read_text(encoding="utf-8")
                 for p in sorted((TARGET / "templates").rglob("*")) if p.is_file()}
    worker = TargetWorker()
    report = {"version": "0.1.0", "validationMode": "UNNEGOTIATED_TEMPLATE_TEST",
              "phase6": "NOT_CLOSED", "domains": {}}
    for domain in ("payment", "case-management"):
        snapshot = load(ROOT / "test-corpus/canonical" / (domain + ".json"))
        validate_snapshot(snapshot)
        nodes = snapshot["content"]["nodes"]
        try:
            worker.call("negotiate", {"nodes": nodes, "required": [], "decisions": PROFILE["decisions"]})
            admission = "ACCEPTED"
        except TargetWorkerError as error:
            admission = str(error)
        rows = plan(lower(nodes, PROFILE), templates, PROFILE)
        worker.call("validate-plan", {"artifacts": rows})
        directory = output / domain
        for row in rows:
            path = directory / row["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(row["text"].encode("utf-8"))
        evidence = {"canonicalDigest": snapshot["contentDigest"], "admission": admission,
                    "artifacts": len(rows), "checks": {}}
        if args.run_builds:
            commands = [("backend", "backend", ["mvn", "-B", "-ntp", "test"]),
                        ("frontend-lock", "frontend", ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"]),
                        ("frontend-types", "frontend", ["npm", "run", "typecheck"]),
                        ("frontend-components", "frontend", ["npm", "test"]),
                        ("frontend-build", "frontend", ["npm", "run", "build"])]
            for name, folder, command in commands:
                log = output / (domain + "-" + name + ".log")
                with log.open("wb") as handle:
                    result = subprocess.run(command, cwd=directory / folder, stdout=handle, stderr=subprocess.STDOUT, timeout=600)
                evidence["checks"][name] = "PASS" if result.returncode == 0 else "FAIL"
                if result.returncode:
                    report["domains"][domain] = evidence
                    (output / "template-report.json").write_text(json.dumps(report, indent=2) + "\n")
                    print(json.dumps({"phase6": "NOT_CLOSED", "failed": domain + ":" + name, "log": str(log)}))
                    return 1
        report["domains"][domain] = evidence
    (output / "template-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
