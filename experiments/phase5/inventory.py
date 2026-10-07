"""Resolved dependency/license and implementation-volume inventory, not a score."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from run import AREA, ROOT, save

def run(args, **kwargs):
    p=subprocess.run(args,capture_output=True,text=True,timeout=90,**kwargs)
    return {"exitCode":p.returncode,"stdout":p.stdout,"stderr":p.stderr}

if __name__ == "__main__":
    npm=json.loads((AREA/"langium/package-lock.json").read_text())
    node=[{"path":k,"version":v.get("version"),"license":v.get("license"),"integrity":v.get("integrity")} for k,v in npm["packages"].items() if k]
    ns={"m":"http://maven.apache.org/POM/4.0.0"}
    java=[]
    for jar in (AREA/"xtext/target/classpath.txt").read_text().strip().split(":"):
        p=Path(jar);pom=p.with_suffix(".pom");licenses=[]
        if pom.exists():
            tree=ET.parse(pom)
            licenses=[e.findtext("m:name",namespaces=ns) for e in tree.findall("m:licenses/m:license",ns)]
        java.append({"artifact":str(p.relative_to(AREA/".cache/m2")),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"declaredPomLicenses":licenses,"licenseNote":"Empty means inherited/unresolved in this inventory; no licensing clearance inferred"})
    volumes={}
    for directory in ("antlr","langium","xtext","core-runtime","source-analysis"):
        sources=[p for p in (AREA/directory).rglob("*") if p.suffix in {".py",".java",".ts",".mjs",".rs",".g4",".xtext",".langium"} and not any(k in p.parts for k in ("node_modules","target","generated","out"))]
        volumes[directory]={"files":{str(p.relative_to(AREA)):len(p.read_text().splitlines()) for p in sources},"handwrittenLines":sum(len(p.read_text().splitlines()) for p in sources)}
    generated=[p for folder in (AREA/"antlr/generated",AREA/"xtext/generated") for p in folder.rglob("*.java")]
    save("inventory.json",{"node":node,"jvm":java,"rustLockSha256":hashlib.sha256((AREA/"core-runtime/Cargo.lock").read_bytes()).hexdigest(),"toolchain":{"java":run(["java","-version"]),"maven":run(["mvn","-version"]),"node":run(["node","--version"]),"npm":run(["npm","--version"])},"volume":volumes,"generatedJavaFiles":len(generated),"generatedJavaLines":sum(len(p.read_text().splitlines()) for p in generated),"interpretation":"Volume is packaging/maintenance evidence only; no quality score follows from LOC"})
