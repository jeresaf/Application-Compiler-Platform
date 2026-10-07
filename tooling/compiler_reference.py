"""In-memory test adapters and synthetic target. No files, SQL, AI or network calls."""
from canonical_ir import normalize_candidate
from canonical_json import canonical_bytes, load
from compiler_contracts import (VERSION, TARGET, GENERATOR, Stage, Document, Source,
    Subject, Decision, CompilationRequest, Ingested, Derived, TargetIR, Artifact,
    ArtifactPlan, Owner, CacheEntry, fingerprint)
from compiler_core import (derived_id, _provenance, validate_plan, CompilerFault)
from compiler_ports import CompilationContext


class MemorySnapshots:
    def __init__(self, snapshots=()):
        self._snapshots = {(s.read()["content"]["applicationId"], s.read()["contentDigest"]): s for s in snapshots}

    def read_exact(self, application, digest):
        return self._snapshots[(application, digest)]


class StructuredFrontend:
    identity = "acp-structured-reference/0.1.0"

    def ingest(self, source):
        return Ingested(source.document, source.source_map)

    def elaborate(self, parsed):
        from compiler_contracts import SemanticAST
        return SemanticAST(parsed.representation, parsed.source_map)


class FixtureApproval:
    """Host-injected allowlist, bound to exact bytes/decisions/evidence. NOT production IAM."""
    identity = "acp-fixture-approval/0.1.0"

    def __init__(self, snapshots, decisions, evidence):
        self._content = {(s.read()["content"]["applicationId"], s.read()["contentDigest"],
                          canonical_bytes(s.read()["content"])) for s in snapshots}
        self._decisions = tuple(sorted(fingerprint(d, "decision") for d in decisions))
        self._evidence = evidence
        self._bases = {s.read()["contentDigest"] for s in snapshots}
        self.revoked = False

    def approve_content(self, query, evidence):
        return not self.revoked and evidence == self._evidence and (query["applicationId"], query["contentDigest"], query["contentBytes"]) in self._content

    def approve_decisions(self, snapshot_digest, decisions, evidence):
        return (not self.revoked and evidence == self._evidence and snapshot_digest in self._bases and
                tuple(sorted(fingerprint(d, "decision") for d in decisions)) == self._decisions)


class MemoryCache:
    def __init__(self):
        self.entries = {}

    def get(self, key):
        return self.entries.get(key)

    def put(self, entry: CacheEntry):
        self.entries[entry.key] = entry


class ReferenceControl:
    def __init__(self, elapsed=0, cancelled=False):
        self.elapsed, self.is_cancelled = elapsed, cancelled

    def elapsed_ms(self):
        return self.elapsed

    def cancelled(self):
        return self.is_cancelled


class SyntheticTarget:
    identity = TARGET
    generator = GENERATOR
    capabilities = ("reference.obligations/1", "reference.records/1")

    def lower(self, realization, request):
        objects = tuple(Derived(derived_id(o.provenance.origins, str(Stage.LOWER)), str(Stage.LOWER), o.semantic,
            # No ambient inputs: each output binds the exact previous object.
            o.provenance.__class__(o.provenance.origins, Stage.LOWER, request.compiler,
                                   request.pipeline, tuple(sorted((fingerprint(o), fingerprint((request.target, request.required_capabilities), "target-manifest")))))) for o in realization.objects)
        return TargetIR(self.identity, objects, tuple(sorted(request.required_capabilities)), realization.projections.obligations, realization.projections.source_map)

    def plan(self, target, request):
        artifacts = []
        for obj in target.objects:
            provenance = obj.provenance.__class__(obj.provenance.origins, Stage.GENERATE,
                request.compiler, request.pipeline, tuple(sorted((fingerprint(obj), fingerprint(request.generator, "generator-manifest")))))
            content = Document.of({"kind": "SyntheticSemanticRecord", "version": VERSION,
                                   "target": self.identity, "semantic": obj.semantic.read()})
            obligations = tuple(o.id for o in target.obligations if set(o.origins) & set(obj.provenance.origins))
            artifacts.append(Artifact("reference/" + obj.id.split(":")[1] + ".json", "SYNTHETIC_RECORD",
                content, fingerprint(content, "artifact-content"), Owner.COMPILER, provenance,
                obj.provenance.origins, "CREATE", None, "COMPARE_AND_SWAP",
                tuple(sorted({"reference-record-integrity", *obligations})),
                tuple(sorted({target.source_map.read()[s.id] for s in obj.provenance.origins if s.id in target.source_map.read()}))))
        return ArtifactPlan(tuple(sorted(artifacts, key=lambda a: a.path)), target.obligations)


class MemoryArtifactStore:
    """Atomic, compare-and-swap reference store; never touches the working tree."""
    def __init__(self, records=()):
        self.records = {artifact.path: artifact for artifact in records}

    def inventory(self):
        from compiler_contracts import ExistingArtifact
        return tuple(ExistingArtifact(a.path, a.content_digest, a.owner) for a in sorted(self.records.values(), key=lambda a: a.path))

    def apply(self, plan):
        validate_plan(plan, self.inventory(), plan.obligations)
        updated = dict(self.records)
        for artifact in plan.artifacts:
            if artifact.intent != "NO_OP":
                updated[artifact.path] = artifact
        self.records = updated


def fixture_context(model, *, cache=None, inventory=(), dependencies=(), dependency_snapshots=()):
    """Explicitly approved synthetic fixtures; this is not an authoring approval path."""
    source = Source(Document.of(model))
    snapshot = Document.of(normalize_candidate(model))
    content = snapshot.read()["content"]
    root = next(n for n in content["nodes"] if n["kind"] == "Decision")
    origin = (Subject(content["applicationId"], root["id"], root["revision"]),)
    decisions = tuple(Decision("fixture-" + role, role, origin,
        Document.of({"choice": "framework-neutral-reference-" + role, "status": "TEST_ONLY"})) for role in ("architecture", "design"))
    evidence = Document.of({"fixture": "independent-host-test-allowlist", "version": VERSION})
    request = CompilationRequest(content["applicationId"], snapshot.read()["contentDigest"],
        fingerprint(source, "source"), evidence, decisions,
        tuple(sorted(fingerprint(d, "decision") for d in decisions)), tuple(dependencies))
    authority = FixtureApproval((snapshot, *dependency_snapshots), decisions, evidence)
    return source, CompilationContext(request, MemorySnapshots((snapshot, *dependency_snapshots)),
        StructuredFrontend(), authority, SyntheticTarget(), cache if cache is not None else MemoryCache(),
        ReferenceControl(), tuple(inventory))


def main():
    """Offline reproducible reference compilation; emits plan identity, never writes artifacts."""
    import argparse
    import json
    from canonical_fixtures import synthetic_approved
    from compiler_core import compile_pipeline
    from compiler_contracts import Success
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", help="explicit synthetic authoring fixture JSON")
    args = parser.parse_args()
    from pathlib import Path
    source, context = fixture_context(synthetic_approved(load(Path(args.model))))
    compilation = compile_pipeline(source, context)
    if isinstance(compilation.result, Success):
        print(json.dumps({"status": compilation.audit.status, "target": TARGET,
                          "artifactPlanDigest": compilation.audit.artifact_plan_digest,
                          "outstandingObligations": len(compilation.result.obligations)}))
        return 0
    print(json.dumps({"status": "FAILED", "codes": [d.code for d in compilation.result.diagnostics]}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
