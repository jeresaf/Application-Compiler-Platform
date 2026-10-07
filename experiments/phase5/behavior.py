"""Actual frontend semantic diagnostics and separate-process determinism probes."""
import copy
from dataclasses import replace
import json
import random
import sys
import time

from run import AREA, ROOT, command, invoke, save
from generate import encode
sys.path.insert(0, str(ROOT / "tooling/tests"))
from test_contracts import apply_edits
from validate import validate
from canonical_fixtures import synthetic_approved
from canonical_ir import normalize_candidate
from compiler_contracts import Document, SemanticAST, Stage, Success
from compiler_core import execute
from compiler_reference import fixture_context


def main(candidate):
    cases = json.loads((ROOT / "test-corpus/semantic/cases.json").read_text())
    selected = {"duplicate-id", "missing-reference", "stale-reference", "currency-mismatch", "boolean-money-literal", "terminal-outgoing", "ambiguous-transition", "conflict-blocks-compilation"}
    evidence = {"diagnostics": {}, "determinism": [], "stageBoundary": {}}
    for case in cases:
        if case["name"] not in selected:
            continue
        model = json.loads((ROOT / "test-corpus/semantic" / case["base"]).read_text())
        apply_edits(model, case["edits"])
        text = encode(model)
        filename = AREA / "corpora" / (case["name"] + ".acp")
        filename.write_text(text)
        result = invoke(command(candidate, filename))
        if result.get("output", {}).get("model"):
            lowered = result["output"]["model"]
            start = time.perf_counter()
            diagnostics = validate(lowered, case["mode"])
            result.update(exactAuthoringEquality=lowered == model, semanticMs=(time.perf_counter()-start)*1000,
                          diagnosticEquality=diagnostics == validate(model, case["mode"]), diagnostics=diagnostics,
                          deterministicDiagnostics=diagnostics == validate(lowered, case["mode"]),
                          sourceSpanCount=len(result["output"]["spans"]), relatedLocations="NOT_RUN: existing diagnostics expose subject/path; complete related-source projection is missing")
            del result["output"]["model"]
            del result["output"]["spans"]
        evidence["diagnostics"][case["name"]] = result
    original = json.loads((ROOT / "test-corpus/phase1/payment.json").read_text())
    expected = normalize_candidate(synthetic_approved(original))["contentDigest"]
    for i in range(3):
        model = copy.deepcopy(original)
        random.Random(7351+i).shuffle(model["nodes"])
        def reorder(v):
            if isinstance(v, dict): return {k:reorder(v[k]) for k in reversed(list(v))}
            if isinstance(v, list): return list(map(reorder,v))
            return v
        model = reorder(model)
        folder = AREA / ".cache" / f"determinism-{i}"
        folder.mkdir(exist_ok=True)
        filename = folder / "payment.acp"
        filename.write_text(encode(model))
        result = invoke(command(candidate, filename), LC_ALL="C" if i%2 else "C.UTF-8", TMPDIR=str(folder), PYTHONHASHSEED=str(i), ACP_IRRELEVANT=f"noise-{i}")
        if result.get("output", {}).get("model"):
            lowered = result["output"]["model"]
            result.update(canonicalEqual=normalize_candidate(synthetic_approved(lowered))["contentDigest"] == expected)
            del result["output"]
        evidence["determinism"].append(result)
    for domain in ("payment", "case-management"):
        result = invoke(command(candidate, AREA / f"corpora/{domain}.acp"))
        model = synthetic_approved(result["output"]["model"])
        _, context = fixture_context(model)
        context = replace(context, request=replace(context.request, start=Stage.ANALYZE, end=Stage.NORMALIZE))
        source_map = {}
        text = (AREA / f"corpora/{domain}.acp").read_text()
        for span in result["output"]["spans"]:
            if "range" in span:
                line, column = span["range"]["start"]["line"]+1, span["range"]["start"]["character"]+1
            elif "offset" in span:
                prefix = text[:span["offset"]]
                line, column = prefix.count("\n")+1, len(prefix.rsplit("\n",1)[-1])+1
            else:
                line, column = span["line"], span["column"]+1
            source_map[span["id"]] = f'corpora/{domain}.acp#L{line}C{column}'
        ast = SemanticAST(Document.of(model), Document.of(source_map))
        analyzed = execute(Stage.ANALYZE, ast, context)
        assert isinstance(analyzed, Success), analyzed
        normalized = execute(Stage.NORMALIZE, analyzed.output, context)
        assert isinstance(normalized, Success), normalized
        evidence["stageBoundary"][domain] = {"analyze":"PASS", "normalize":"PASS", "plainDocumentRoundTrip": ast.model.read()==model, "sourceMapPreserved": analyzed.output.source_map==ast.source_map, "scope":"Text adaptation precedes existing Phase 4 structured-only Ingest; Analyze and Normalize execute unchanged; no claim of production textual Ingest selection"}
    save(f"{candidate}-behavior.json", evidence)


if __name__ == "__main__":
    main(sys.argv[1])
