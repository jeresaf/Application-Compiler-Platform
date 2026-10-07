"""Versioned Phase 4 reference contracts. No production runtime/target selection."""
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
import hashlib
from typing import Generic, TypeVar

from canonical_json import canonical_bytes, loads

VERSION = "0.1.0"
COMPILER = "acp-reference-compiler/0.1.0"
PIPELINE = "acp-reference-pipeline/0.1.0"
TARGET = "acp-synthetic-test-target/0.1.0"
GENERATOR = "acp-artifact-plan-fixture/0.1.0"


class Stage(StrEnum):
    INGEST = "Ingest"
    ELABORATE = "Elaborate"
    ANALYZE = "Analyze"
    NORMALIZE = "Normalize"
    PROJECT = "Project"
    REALIZE = "Realize"
    LOWER = "NegotiateLower"
    GENERATE = "Generate"


STAGES = tuple(Stage)


@dataclass(frozen=True)
class Document:
    """Deep immutability through strict canonical bytes; reads return detached data."""
    data: bytes

    def __post_init__(self):
        if canonical_bytes(loads(self.data)) != self.data:
            raise ValueError("Document must use the accepted byte profile")

    @classmethod
    def of(cls, value):
        return cls(canonical_bytes(value))

    def read(self):
        return loads(self.data)


def wire(value):
    if isinstance(value, Document):
        return value.read()
    if isinstance(value, StrEnum):
        return str(value)
    if is_dataclass(value):
        return {f.name: wire(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, tuple):
        return [wire(v) for v in value]
    if isinstance(value, bytes):
        return value.hex()
    return value


def fingerprint(value, domain="object"):
    return "sha256:" + hashlib.sha256(("ACP\0compiler-core-0.1\0" + domain + "\0").encode() + canonical_bytes(wire(value))).hexdigest()


@dataclass(frozen=True, order=True)
class Subject:
    application: str
    id: str
    revision: int


@dataclass(frozen=True)
class Provenance:
    origins: tuple[Subject, ...]
    stage: Stage
    compiler: str
    pipeline: str
    inputs: tuple[str, ...]


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: str
    stage: Stage
    subjects: tuple[Subject, ...]
    location: str | None
    related: tuple[Subject, ...]
    explanation: str
    remediation: str
    provenance: Provenance
    related_locations: tuple[str, ...] = ()
    location_confidence: str = "UNSPECIFIED"


@dataclass(frozen=True)
class Obligation:
    id: str
    category: str
    origins: tuple[Subject, ...]
    status: str = "OUTSTANDING"


@dataclass(frozen=True)
class Metrics:
    work: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


T = TypeVar("T")


@dataclass(frozen=True)
class Success(Generic[T]):
    output: T
    output_digest: str
    provenance: Provenance
    obligations: tuple[Obligation, ...]
    diagnostics: tuple[Diagnostic, ...]
    metrics: Metrics


@dataclass(frozen=True)
class Failure:
    diagnostics: tuple[Diagnostic, ...]
    provenance: Provenance
    metrics: Metrics


@dataclass(frozen=True)
class Resources:
    input_bytes: int = 1_048_576
    output_bytes: int = 1_048_576
    nodes: int = 2000
    depth: int = 48
    work: int = 200_000
    diagnostics: int = 32
    timeout_ms: int = 60_000


@dataclass(frozen=True)
class Cancellation:
    cancelled: bool = False
    after_work: int | None = None


@dataclass(frozen=True, order=True)
class Dependency:
    identity: str
    digest: str
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class Decision:
    id: str
    role: str
    origins: tuple[Subject, ...]
    choice: Document


@dataclass(frozen=True)
class CompilationRequest:
    application: str
    snapshot_digest: str
    source_digest: str
    approval_evidence: Document
    decisions: tuple[Decision, ...]
    decision_digests: tuple[str, ...]
    dependencies: tuple[Dependency, ...] = ()
    accepted_ai_candidates: tuple[str, ...] = ()
    change_plan_digest: str | None = None
    change_obligations: tuple[Obligation, ...] = ()
    features: tuple[str, ...] = ("acp.phase1.0.2",)
    required_capabilities: tuple[str, ...] = ("reference.records/1", "reference.obligations/1")
    configuration: Document = Document.of({})
    resources: Resources = Resources()
    cancellation: Cancellation = Cancellation()
    version: str = VERSION
    compiler: str = COMPILER
    pipeline: str = PIPELINE
    authority: str = "acp-fixture-approval/0.1.0"
    frontend: str = "acp-structured-reference/0.1.0"
    target: str = TARGET
    generator: str = GENERATOR
    start: Stage = Stage.INGEST
    end: Stage = Stage.GENERATE
    repository_root: str = "."
    allowed_ports: tuple[str, ...] = ("frontend", "snapshots", "approval", "target", "cache", "control")
    required_decisions: tuple[str, ...] = ("architecture", "design")


    def __post_init__(self):
        # These manifests are sets/keyed collections, unlike ordered semantic steps.
        for name in ("features", "required_capabilities", "accepted_ai_candidates", "decision_digests", "allowed_ports", "required_decisions"):
            value = getattr(self, name)
            if type(value) is tuple:
                object.__setattr__(self, name, tuple(sorted(value)))
        if type(self.decisions) is tuple:
            object.__setattr__(self, "decisions", tuple(sorted(self.decisions, key=lambda d: d.id)))
        if type(self.dependencies) is tuple:
            object.__setattr__(self, "dependencies", tuple(sorted(self.dependencies)))


@dataclass(frozen=True)
class Source:
    document: Document
    source_map: Document = Document.of({})


@dataclass(frozen=True)
class Ingested:
    representation: Document
    source_map: Document
    dialect: str = "acp-structured-reference/0.1.0"
    source_details: Document = Document.of({})


@dataclass(frozen=True)
class SemanticAST:
    model: Document
    source_map: Document
    version: str = VERSION
    source_details: Document = Document.of({})


@dataclass(frozen=True)
class ResolvedModel:
    model: Document
    source_map: Document
    dependency_digests: tuple[str, ...]
    obligations: tuple[Obligation, ...]
    version: str = VERSION


@dataclass(frozen=True)
class CanonicalModel:
    snapshot: Document
    admission: Document
    obligations: tuple[Obligation, ...]
    source_map: Document = Document.of({})
    version: str = VERSION


@dataclass(frozen=True)
class Derived:
    id: str
    role: str
    semantic: Document
    provenance: Provenance


@dataclass(frozen=True)
class Projection:
    role: str
    objects: tuple[Derived, ...]


@dataclass(frozen=True)
class Projections:
    snapshot: Document
    views: tuple[Projection, ...]
    obligations: tuple[Obligation, ...]
    source_map: Document = Document.of({})
    version: str = VERSION


@dataclass(frozen=True)
class Realization:
    projections: Projections
    architecture: tuple[Decision, ...]
    design: tuple[Decision, ...]
    objects: tuple[Derived, ...]
    version: str = VERSION


@dataclass(frozen=True)
class TargetIR:
    target: str
    objects: tuple[Derived, ...]
    capabilities: tuple[str, ...]
    obligations: tuple[Obligation, ...]
    source_map: Document = Document.of({})
    version: str = VERSION


class Owner(StrEnum):
    COMPILER = "COMPILER_OWNED"
    FRAMEWORK = "FRAMEWORK_OWNED"
    AI = "AI_MANAGED"
    HUMAN = "HUMAN_OWNED"


@dataclass(frozen=True)
class ExistingArtifact:
    path: str
    digest: str
    owner: Owner


@dataclass(frozen=True)
class Artifact:
    path: str
    role: str
    content: Document
    content_digest: str
    owner: Owner
    provenance: Provenance
    mappings: tuple[Subject, ...]
    intent: str
    expected_digest: str | None
    write_policy: str
    verification: tuple[str, ...]
    source_locations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArtifactPlan:
    artifacts: tuple[Artifact, ...]
    obligations: tuple[Obligation, ...]
    version: str = VERSION


@dataclass(frozen=True)
class StageAudit:
    stage: Stage
    identity: str
    input_digest: str
    output_digest: str
    provenance_digest: str
    metrics: Metrics


@dataclass(frozen=True)
class CompilationAudit:
    input_canonical_digest: str
    compiler: str
    pipeline: str
    stages: tuple[StageAudit, ...]
    dependencies: tuple[Dependency, ...]
    configuration: Document
    obligations: tuple[Obligation, ...]
    artifact_plan_digest: str | None
    provenance_digest: str
    status: str
    version: str = VERSION


@dataclass(frozen=True)
class Compilation:
    result: Success | Failure
    stages: tuple[StageAudit, ...]
    audit: CompilationAudit | None


@dataclass(frozen=True)
class CacheEntry:
    key: str
    value: Derived
    digest: str


@dataclass(frozen=True)
class Impact:
    changed: tuple[str, ...]
    closure: tuple[str, ...]
    projections: tuple[str, ...]
    passes: tuple[Stage, ...]


@dataclass(frozen=True)
class AICandidate:
    provider: str
    model: str
    input_digest: str
    policy_digest: str
    configuration: Document
    candidate: Document
    candidate_digest: str
    provenance: Provenance
    # Deliberately no canonical/architecture mutation or self-approval operation.
    version: str = VERSION
