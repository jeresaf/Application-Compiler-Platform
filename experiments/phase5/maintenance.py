"""Controlled local offline rebuilds and one native API patch upgrade."""
import json
import os
import shutil
import subprocess
import sys
import time
from run import AREA, ROOT, save

def run(args, **environment):
    start=time.perf_counter()
    result=subprocess.run(args,cwd=ROOT,env={**os.environ,**environment},capture_output=True,text=True,timeout=600)
    return {"exitCode":result.returncode,"elapsedMs":(time.perf_counter()-start)*1000,"stdout":result.stdout,"stderr":result.stderr}

if __name__ == "__main__":
    evidence={}
    old=run(["node",str(AREA/"langium/source-probe.mjs")],ACP_TS_MODULE=str(AREA/".cache/typescript-previous/node_modules/typescript/lib/typescript.js"))
    new=run(["node",str(AREA/"langium/source-probe.mjs")])
    evidence["typescriptUpgrade"]={"from":"5.9.2","to":"5.9.3","old":old,"new":new}
    if old["exitCode"]==new["exitCode"]==0:
        a,b=json.loads(old["stdout"]),json.loads(new["stdout"])
        evidence["typescriptUpgrade"]["nativeSemanticEquality"]=a["native"]==b["native"] and a["diagnostics"]==b["diagnostics"]
    evidence["npmOfflineRestore"]=run(["npm","--prefix",str(AREA/".cache/langium-clean"),"--cache","/tmp/acp-phase5-npm-cache","ci","--offline","--ignore-scripts","--no-audit","--no-fund"])
    evidence["mavenOfflineResolution"]=run(["mvn","-o","-B","-ntp","-f",str(AREA/"xtext/pom.xml"),f'-Dmaven.repo.local={AREA}/.cache/m2',"dependency:build-classpath","-Dmdep.outputFile=target/classpath.txt"])
    for candidate, directory in (("antlr","antlr/generated"),("xtext","xtext/generated")):
        path=AREA/directory
        if path.exists():
            destination=AREA/".cache"/f'{candidate}-previous-{time.time_ns()}'
            path.rename(destination)
        evidence[candidate+"CleanGeneratedRebuild"]=run([sys.executable,str(AREA/"build.py"),candidate])
    evidence["rustOfflineRebuild"]=run([str(AREA/".cache/cargo/bin/cargo"),"build","--locked","--offline","--release","--manifest-path",str(AREA/"core-runtime/Cargo.toml")],RUSTUP_HOME=str(AREA/".cache/rustup"),CARGO_HOME=str(AREA/".cache/cargo"))
    evidence["scope"]="Fresh generated outputs and cached offline resolution on the existing laptop; hosted CI separately rebuilds on a clean Ubuntu runner. This is not an air-gapped supply-chain reproducibility proof. ANTLR/Xtext/Langium framework-version upgrades and core toolchain upgrades NOT_RUN."
    save("maintenance.json",evidence)
    assert all(v.get("exitCode",0)==0 for v in evidence.values() if isinstance(v,dict)),evidence
