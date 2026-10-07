"""Real textual frontend port: parsing runs inside Phase 4 Ingest, not before it."""
import tempfile
from pathlib import Path
from run import AREA, command, invoke
from modules import resolve
from compiler_contracts import Document, Ingested, SemanticAST

VERSIONS = {"antlr":"4.13.2", "langium":"4.4.0", "xtext":"2.44.0"}


class TextFrontend:
    def __init__(self, candidate, *, worker_child=False):
        self.candidate = candidate
        self.worker_child = worker_child
        self.identity = f"acp-experiment-{candidate}/{VERSIONS[candidate]}"

    def ingest(self, source):
        request = source.document.read()
        if not isinstance(request,dict) or set(request) != {"version","frontend","documents"} or request["version"] != "acp-text/1" or request["frontend"] != self.identity:
            raise ValueError("VERSION")
        if not isinstance(request["documents"],list) or not request["documents"] or len(request["documents"])>128:
            raise ValueError("INPUT")
        parsed, locations = [], {}
        with tempfile.TemporaryDirectory(prefix="acp-frontend-") as directory:
            for i, document in enumerate(request["documents"]):
                if not isinstance(document,dict) or set(document)!={"path","text"} or not all(isinstance(document[k],str) and document[k] for k in document):
                    raise ValueError("INPUT")
                path, text = document["path"], document["text"]
                if Path(path).is_absolute() or ".." in Path(path).parts or "\\" in path or ":" in path:
                    raise ValueError("INPUT")
                filename = Path(directory) / f"module-{i}.acp"
                filename.write_text(text)
                result = invoke(command(self.candidate, filename), isolate=not self.worker_child)
                output = result.get("output", {})
                expected={"antlr":"ANTLR 4.13.2 / Java 21", "langium":"Langium 4.4.0", "xtext":"Xtext 2.44.0 / Java 21"}[self.candidate]
                if not isinstance(output,dict) or output.get("candidate")!=expected:
                    raise ValueError("VERSION")
                if result["status"] != "PASS" or output.get("errors") or not isinstance(output.get("model"), dict):
                    raise ValueError("SYNTAX")
                nodes=output["model"].get("nodes")
                spans=output.get("spans")
                if not isinstance(nodes,list) or not isinstance(spans,list) or len(nodes)!=len(spans) or [n.get("id") for n in nodes]!=[s.get("id") for s in spans]:
                    raise ValueError("RESPONSE")
                parsed.append((path, output))
                for span in output["spans"]:
                    if "range" in span:
                        line, column = span["range"]["start"]["line"]+1, span["range"]["start"]["character"]+1
                    elif "offset" in span:
                        prefix = text[:span["offset"]]
                        line, column = prefix.count("\n")+1, len(prefix.rsplit("\n",1)[-1])+1
                    else:
                        line, column = span["line"], span["column"]+1
                    locations[span["id"]] = f"{path}#L{line}C{column}"
        model, _ = resolve(parsed)
        return Ingested(Document.of(model), Document.of(locations), self.identity)

    def elaborate(self, parsed):
        if parsed.dialect != self.identity:
            raise ValueError("VERSION")
        # Document's strict-byte constructor is the framework-object firewall.
        return SemanticAST(Document.of(parsed.representation.read()), parsed.source_map)
