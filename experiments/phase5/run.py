"""Serial, bounded measurements; raw outcomes precede any ranking."""
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import tempfile
import signal

AREA = Path(__file__).resolve().parent
ROOT = AREA.parents[1]
sys.path.insert(0, str(ROOT / "tooling"))
from canonical_ir import normalize_candidate
from canonical_fixtures import synthetic_approved
from canonical_json import canonical_bytes
from validate import validate


def command(candidate, filename, runs=1):
    cp = (AREA / "xtext/target/classpath.txt").read_text().strip()
    if candidate == "antlr":
        return ["java", "-XX:-UsePerfData", "-Xmx768m", "-cp", f'{AREA}/antlr/generated:{AREA}/tools/antlr-4.13.2-complete.jar:{cp}', "Probe", str(filename), str(runs)]
    if candidate == "langium":
        return ["node", "--max-old-space-size=768", str(AREA / "langium/probe.mjs"), str(filename), str(runs)]
    return ["java", "-XX:-UsePerfData", "-Xmx768m", "-cp", f'{AREA}/xtext/out:{AREA}/xtext/generated/org.acp.experiment/src-gen:{cp}', "XtextProbe", str(filename), str(runs)]


def invoke(args, *, timeout=90, isolate=True, working_directory=None, **env):
    start = time.perf_counter()
    try:
        with tempfile.NamedTemporaryFile(prefix="acp-phase5-rss-") as memory:
            with subprocess.Popen(["/usr/bin/time", "-f", "%M", "-o", memory.name, *args], cwd=working_directory or ROOT, env={**os.environ, **env}, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=isolate) as process:
                try:
                    stdout, stderr = process.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    if isolate:
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.communicate()
                    raise
                result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
            rss = Path(memory.name).read_text().splitlines()[-1]
        raw = {"exitCode": result.returncode, "elapsedMs": (time.perf_counter()-start)*1000, "peakRssBytes": int(rss)*1024, "stderr": result.stderr}
        if result.returncode:
            return {**raw, "status": "FAIL", "stdout": result.stdout[-4000:]}
        return {**raw, "status": "PASS", "output": json.loads(result.stdout)}
    except subprocess.TimeoutExpired:
        return {"status": "TIMEOUT", "elapsedMs": (time.perf_counter()-start)*1000}
    except json.JSONDecodeError as error:
        return {"status": "FAIL", "reason": str(error), "stdout": result.stdout[-4000:]}


def save(name, value):
    (AREA / "results" / name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+"\n")


def frontend(candidate):
    evidence = {"candidate": candidate, "domains": {}, "recovery": {}, "scale": {}}
    for domain in ("payment", "case-management"):
        filename = AREA / f"corpora/{domain}.acp"
        result = invoke(command(candidate, filename))
        if result["status"] == "PASS" and not result["output"]["errors"]:
            model = result["output"]["model"]
            reference = json.loads((ROOT / f"test-corpus/phase1/{domain}.json").read_text())
            start = time.perf_counter()
            diagnostics = validate(model)
            analysis_ms = (time.perf_counter()-start)*1000
            normalized = normalize_candidate(synthetic_approved(model))
            result.update(exactAuthoringEquality=model==reference, canonicalEquality=canonical_bytes(normalized)==canonical_bytes(normalize_candidate(synthetic_approved(reference))), contentDigest=normalized["contentDigest"], analysisMs=analysis_ms, diagnosticCount=len(diagnostics), approvalScope="Existing synthetic fixture approval applied equally to both inputs; not production approval")
            # Keep full plain output as reproducible regression evidence.
        evidence["domains"][domain] = result
    text = (AREA / "corpora/payment.acp").read_text()
    for name, broken in {"incomplete": text[:text.index("\n")+40], "missing-close": text[:-3], "malformed": text.replace("application", "???", 1)}.items():
        filename = AREA / ".cache" / f"{name}.acp"
        filename.write_text(broken)
        result = invoke(command(candidate, filename))
        if result.get("output"):
            result["rejectsProduction"] = bool(result["output"]["errors"]) and "model" not in result["output"]
        evidence["recovery"][name] = result
    for size in (1000, 10000, 100000):
        filename = AREA / f".cache/corpora/scale-{size}.acp"
        cold = []
        for _ in range(3):
            if cold and cold[-1]["status"] != "PASS":
                cold.append({"status":"NOT_RUN", "reason":"Previous run exceeded resource budget or failed"})
            else:
                cold.append(invoke(command(candidate, filename), ACP_PARSE_ONLY="1"))
        warm = invoke(command(candidate, filename, 6), ACP_PARSE_ONLY="1") if all(r["status"] == "PASS" for r in cold) else {"status":"NOT_RUN", "reason":"Cold workload failed"}
        evidence["scale"][str(size)] = {"sourceBytes": filename.stat().st_size, "sha256": hashlib.sha256(filename.read_bytes()).hexdigest(), "cold": cold, "warm": warm, "warmInterpretation": "First parse discarded; remaining five retained", "semanticValidation": "NOT_SUPPORTED: synthetic parse-only declarations omit required semantic records; baseline node/byte limits unchanged", "incremental": "NOT_RUN", "rename": "NOT_RUN"}
        save(f"{candidate}.json", evidence)
    save(f"{candidate}.json", evidence)


if __name__ == "__main__":
    if sys.argv[1] in ("antlr", "langium", "xtext"):
        frontend(sys.argv[1])
    elif sys.argv[1] == "core":
        results = {}
        for size in (1000,10000,100000):
            results[str(size)] = {
                "java": invoke(["java", "-XX:-UsePerfData", "-Xmx768m", "-cp", str(AREA / "core-runtime/out"), "Core", str(size)]),
                "typescript": invoke(["node", "--max-old-space-size=768", str(AREA / "core-runtime/core.ts"), str(size)]),
                "rust": invoke([str(AREA / "core-runtime/out/core"), str(size)])}
        save("core-runtime.json", results)
    elif sys.argv[1] == "metadata":
        metadata = {"platform": platform.platform(), "python": platform.python_version(), "cpu": Path("/proc/cpuinfo").read_text(), "memory": Path("/proc/meminfo").read_text(), "osRelease": Path("/etc/os-release").read_text(), "protocolSha256": hashlib.sha256((AREA / "protocol.json").read_bytes()).hexdigest(), "environmentScope": "Local Linux laptop; hosted CI recorded separately"}
        save("machine.json", metadata)
