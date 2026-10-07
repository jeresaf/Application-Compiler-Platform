"""Logical ports, not a production plugin ABI. Effects remain outside pure passes."""
from dataclasses import dataclass
from typing import Protocol

from compiler_contracts import (ArtifactPlan, CacheEntry, CompilationRequest,
    AICandidate, Decision, Document, ExistingArtifact, Ingested, Realization, SemanticAST, Source, TargetIR)


class SnapshotRepository(Protocol):
    def read_exact(self, application: str, digest: str) -> Document: ...
    # Mutation remains the Phase 3 SnapshotRepository contract; compiler gets read only.


class Frontend(Protocol):
    identity: str
    def ingest(self, source: Source) -> Ingested: ...
    def elaborate(self, parsed: Ingested) -> SemanticAST: ...


@dataclass(frozen=True)
class SourceDiagnostic:
    """Bounded diagnostic metadata, never source text or adapter exception wording."""
    code: str
    subject: tuple[str, int] | None
    location: str | None
    related: tuple[tuple[str, int], ...] = ()
    related_locations: tuple[str, ...] = ()
    confidence: str = "UNRECOVERABLE"


class FrontendDiagnosticsFailure(Exception):
    def __init__(self, diagnostics: tuple[SourceDiagnostic, ...]):
        self.diagnostics = diagnostics
        super().__init__("Frontend diagnostics")


class ApprovalAuthority(Protocol):
    identity: str
    def approve_content(self, request: dict, evidence: Document) -> bool: ...
    def approve_decisions(self, snapshot_digest: str, decisions: tuple[Decision, ...], evidence: Document) -> bool: ...


class TargetCompiler(Protocol):
    identity: str
    generator: str
    capabilities: tuple[str, ...]
    def lower(self, realization: Realization, request: CompilationRequest) -> TargetIR: ...
    def plan(self, target: TargetIR, request: CompilationRequest) -> ArtifactPlan: ...


class ProjectTargetCompiler(TargetCompiler, Protocol):
    """Negotiated target.project-artifacts/1 extension; host supplies inventory."""
    def plan(self, target: TargetIR, request: CompilationRequest, *,
             inventory: tuple[ExistingArtifact, ...] = ()) -> ArtifactPlan: ...


class ArtifactStore(Protocol):
    def inventory(self) -> tuple[ExistingArtifact, ...]: ...
    def apply(self, plan: ArtifactPlan) -> None: ...


class SourceAnalyzer(Protocol):
    def analyze(self, source: Document, query: Document) -> Document: ...


class EvidenceExecutor(Protocol):
    def execute(self, plan: Document, input_digests: tuple[str, ...]) -> Document: ...


class AIProvider(Protocol):
    def propose(self, context: Document, policy: Document) -> AICandidate:
        """Candidate plus explicit model/config/input/output provenance; no mutation."""
        ...


class ClockProvider(Protocol):
    def instant(self, binding: str) -> Document: ...


class SecretProvider(Protocol):
    def resolve(self, opaque_handle: str, scope: str) -> Document: ...


class EnvironmentProvider(Protocol):
    def resolve(self, binding: str) -> Document: ...


class Control(Protocol):
    """Supervisor reports operational elapsed time/cancellation, never output meaning."""
    def elapsed_ms(self) -> int: ...
    def cancelled(self) -> bool: ...


class DeterministicCache(Protocol):
    def get(self, key: str) -> CacheEntry | None: ...
    def put(self, entry: CacheEntry) -> None: ...


@dataclass(frozen=True)
class CompilationContext:
    request: CompilationRequest
    snapshots: SnapshotRepository
    frontend: Frontend
    approval: ApprovalAuthority
    target: TargetCompiler
    cache: DeterministicCache
    control: Control
    inventory: tuple[ExistingArtifact, ...] = ()
    # AI/source/evidence/clock/secret/environment ports are intentionally absent.
    # A future effectful orchestrator must explicitly bind them, not pure passes.
