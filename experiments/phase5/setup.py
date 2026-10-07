"""Fetch only manifest-pinned parser generator tools into ignored local paths."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

AREA=Path(__file__).resolve().parent
versions=json.loads((AREA/"versions.json").read_text())
for key,path in [("antlr",AREA/"tools/antlr-4.13.2-complete.jar"),("xtextGeneratorAntlr",AREA/"xtext/.antlr-generator-3.2.0-patch.jar")]:
    entry=versions[key]
    if not path.exists():
        with urlopen(entry["url"],timeout=90) as response:
            data=response.read(32*1024*1024+1)
        if len(data)>32*1024*1024 or hashlib.sha256(data).hexdigest()!=entry["sha256"]:
            raise SystemExit(f"Artifact integrity failure: {key}")
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=entry["sha256"]:
        raise SystemExit(f"Cached artifact integrity failure: {key}")
