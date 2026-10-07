"""Rebuild-backed Ubuntu/local interoperability gates, independent of timings."""
import json
import subprocess
import sys
from run import AREA, ROOT, command, invoke
from canonical_fixtures import synthetic_approved
from canonical_ir import normalize_candidate
from behavior import main as behavior

for candidate in ("antlr","langium","xtext"):
    for domain in ("payment","case-management"):
        result=invoke(command(candidate,AREA/f"corpora/{domain}.acp"))
        assert result["status"]=="PASS",result
        assert not result["output"]["errors"],result["output"]["errors"]
        model=result["output"]["model"]
        reference=json.loads((ROOT/f"test-corpus/phase1/{domain}.json").read_text())
        assert model==reference,(candidate,domain)
        assert normalize_candidate(synthetic_approved(model))==normalize_candidate(synthetic_approved(reference))
        assert {s["id"] for s in result["output"]["spans"]}=={n["id"] for n in model["nodes"]}
    behavior(candidate)
    evidence=json.loads((AREA/f"results/{candidate}-behavior.json").read_text())
    assert all(r.get("exactAuthoringEquality") and r.get("diagnosticEquality") and r.get("deterministicDiagnostics") for r in evidence["diagnostics"].values()),candidate
    assert all(r.get("canonicalEqual") for r in evidence["determinism"]),candidate
    filename=AREA/".cache/smoke-incomplete.acp";filename.parent.mkdir(exist_ok=True)
    filename.write_text((AREA/"corpora/payment.acp").read_text()[:-3])
    result=invoke(command(candidate,filename))
    assert result["status"]=="PASS" and result["output"]["errors"] and "model" not in result["output"],candidate
    filename.write_text('application {}; Entity "ENT-A" @ 1 {"id":"ENT-B"};')
    result=invoke(command(candidate,filename))
    assert result["status"]=="FAIL", (candidate,"identity body must not override declaration header")
cp=(AREA/"xtext/target/classpath.txt").read_text().strip()
subprocess.run(["javac","-cp",cp,"-d",str(AREA/"core-runtime/out"),str(AREA/"core-runtime/Canonical.java"),str(AREA/"core-runtime/Core.java")],check=True)
subprocess.run(["java","-XX:-UsePerfData","-cp",f"{AREA}/core-runtime/out:{cp}","Canonical",str(ROOT/"test-corpus/canonical")],check=True)
subprocess.run(["java","-XX:-UsePerfData","-cp",str(AREA/"core-runtime/out"),"Core","1000"],check=True)
subprocess.run(["node",str(AREA/"core-runtime/core.ts"),"1000"],check=True)
subprocess.run(["node",str(AREA/"langium/node_modules/typescript/bin/tsc"),"--noEmit","--strict","--target","es2022","--module","nodenext","--typeRoots",str(AREA/"langium/node_modules/@types"),str(AREA/"core-runtime/core.ts")],check=True)
print("Phase 5 experimental frontend/semantic/stage/Java canonical gates PASS; no technology selection inferred")
