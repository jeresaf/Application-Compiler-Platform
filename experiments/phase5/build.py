"""Build pinned experimental Java parsers from already resolved dependencies."""
from pathlib import Path
import subprocess
import sys
import hashlib
import json

AREA = Path(__file__).resolve().parent
CP = (AREA / "xtext/target/classpath.txt").read_text().strip()
ANTLR = AREA / "tools/antlr-4.13.2-complete.jar"
VERSIONS = json.loads((AREA / "versions.json").read_text())


def verify(path, entry):
    if hashlib.sha256(path.read_bytes()).hexdigest() != VERSIONS[entry]["sha256"]:
        raise SystemExit(f"Dependency digest mismatch: {entry}")


def run(args, cwd=AREA):
    subprocess.run(list(map(str, args)), cwd=cwd, check=True, timeout=600)


if sys.argv[1] == "antlr":
    verify(ANTLR, "antlr")
    output = AREA / "antlr/generated"
    output.mkdir(exist_ok=True)
    run(["java", "-jar", ANTLR, "-o", output, AREA / "antlr/Acp.g4"])
    run(["javac", "-cp", f"{ANTLR}:{CP}", "-d", output,
         *output.glob("*.java"), AREA / "antlr/Probe.java"])
elif sys.argv[1] == "xtext":
    verify(AREA / "xtext/.antlr-generator-3.2.0-patch.jar", "xtextGeneratorAntlr")
    for project in ("org.acp.experiment", "org.acp.experiment.ide"):
        (AREA / "xtext/generated" / project).mkdir(parents=True, exist_ok=True)
    out = AREA / "xtext/out"
    out.mkdir(exist_ok=True)
    run(["javac", "-cp", CP, "-d", out, AREA / "xtext/Generator.java"])
    run(["java", "-Xmx1024m", "-cp", f"{out}:{CP}", "Generator", str(AREA / "xtext/Generate.mwe2")], AREA / "xtext")
    sources = list((AREA / "xtext/generated").rglob("*.java"))
    run(["javac", "-cp", CP, "-d", out, *sources, AREA / "xtext/XtextProbe.java"])
else:
    raise SystemExit("Expected antlr or xtext")
