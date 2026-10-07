"""Measured ANTLR adapter operations on its actual plain-record parse output.

This is an experiment workspace index, not an LSP server. Reference locations are
declaration locations: exact reference-token spans and module scoping are missing.
"""
import copy
import json
import time
from run import AREA, command, invoke, save


def refs(value):
    if isinstance(value, dict):
        if set(value) == {"id", "revision"}:
            yield value
        else:
            for child in value.values(): yield from refs(child)
    elif isinstance(value, list):
        for child in value: yield from refs(child)


if __name__ == "__main__":
    result = invoke(command("antlr", AREA / "corpora/payment.acp"))
    model = result["output"]["model"]
    start = time.perf_counter()
    definitions = {n["id"]:n for n in model["nodes"]}
    references = {}
    for node in model["nodes"]:
        for ref in refs(node): references.setdefault((ref["id"],ref["revision"]),[]).append(node["id"])
    index_ms = (time.perf_counter()-start)*1000
    subject = model["nodes"][0]["id"]
    start = time.perf_counter(); completion = sorted(k for k in definitions if k.startswith("REQ-")); completion_ms=(time.perf_counter()-start)*1000
    start = time.perf_counter(); definition = definitions[subject]; navigation_ms=(time.perf_counter()-start)*1000
    start = time.perf_counter(); found = references.get((subject,1),[]); references_ms=(time.perf_counter()-start)*1000
    start = time.perf_counter(); renamed = copy.deepcopy(model)
    next(n for n in renamed["nodes"] if n["id"]==subject)["name"]="Renamed display label"
    rename_ms=(time.perf_counter()-start)*1000
    save("antlr-editor.json", {"candidate":"ANTLR custom Python index adapter", "indexMs":index_ms,"completionMs":completion_ms,"completionCount":len(completion),"definitionMs":navigation_ms,"definitionId":definition["id"],"referencesMs":references_ms,"references":found,"renameMs":rename_ms,"stableIdsPreserved":[n["id"] for n in model["nodes"]]==[n["id"] for n in renamed["nodes"]],"referencesPreserved":list(refs(model))==list(refs(renamed)),"limitations":["Not an LSP transport or editor UX benchmark", "Completion indexes stable IDs only", "Related references locate declarations, not reference tokens", "Cross-file import visibility, cyclic imports and incremental indexes NOT_RUN"]})
