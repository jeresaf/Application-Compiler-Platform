# Phase 7 Source Intelligence — first increment

`acp-source-model/1` is a deterministic, read-only analysis result. It records native
Java/TypeScript definitions, imports, calls, references, containment, inheritance,
implementation and type-use edges, UTF-16 positions and UTF-8 byte ranges, source
hashes, exact compiler/dependency identities, ownership, drift and completeness.
It does not replace Canonical intent or authorize changes.
`NativeSourceAnalyzer` implements the existing `SourceAnalyzer.analyze(Document,
Document)` port. Its frozen host configuration binds the application and tools;
versioned source/query documents cannot select a different root or request source writes.
The port writes the graph to a separately configured output and returns its compact
hash-bound descriptor, preserving the existing `Document` byte limit.

Java uses JDK 21 javac Trees/Elements with annotation processing disabled.
TypeScript uses the existing reference applications' locked TypeScript 6.0.3
compiler API, including overload signatures and imported aliases. No scripts or
compiler plugins are executed. The caller supplies trusted tools/dependencies;
the model records observed byte identities, not operational authenticity.

Generate each approved reference through the existing eight-stage compiler and
retain its independently pinned original ArtifactPlan/provenance/ownership binding:

```bash
python3.14 engineering/source_intelligence/cli.py prepare \
  --domain payment --workspace /tmp/acp-source-payment
python3.14 engineering/source_intelligence/cli.py prepare \
  --domain case-management --workspace /tmp/acp-source-case
```

Use existing hash-verified Phase 6 Maven inputs and a previously installed,
lock-verified generated frontend dependency tree. These commands do not install
packages, build applications, start databases or alter application source:

```bash
python3.14 engineering/source_intelligence/cli.py analyze \
  --root /tmp/acp-source-payment/payment \
  --binding /tmp/acp-source-payment/source-baseline.json \
  --binding-sha256 "$(cat /tmp/acp-source-payment/source-baseline.sha256)" \
  --maven-repo "$ACP_SOURCE_MAVEN_REPO" \
  --node-modules "$ACP_SOURCE_NODE_MODULES" \
  --output /tmp/payment-source-model.json
sha256sum /tmp/payment-source-model.json
python3.14 engineering/source_intelligence/cli.py impact \
  --root /tmp/acp-source-payment/payment --model /tmp/payment-source-model.json \
  --model-sha256 '<exact preceding file SHA-256>' --semantic UC-TASK
```

`impact --symbol <exact symbol ID>` follows the known reverse dependency graph;
`compare --before ... --before-sha256 ... --after ... --after-sha256 ...` reports
native graph differences and invalidated locations. Ambiguous cross-version
correspondence is UNKNOWN. Dependency impact does not prove behavioral change.
The qualified rename regression updates actual native identifier locations in
disposable generated applications; the CLI itself performs no rewrites.

Semantic mappings mean **EMBEDS_SEMANTIC_ID**: a native declaration contains an
exact approved ID/revision carrier, in an unchanged artifact with matching original
provenance and ownership. This does not establish business implementation coverage.
Historical ARTIFACT_ONLY mappings remain intact. A changed artifact loses these
symbol mappings. A missing/forged sidecar cannot promote any symbol mapping.
The original baseline must be retained outside application source with its digest;
accepting a replacement baseline is a separate caller trust decision.

Bounded support: at most 128 Java/TS/TSX/Vue source files, 2 MiB per input file,
8 MiB total source, 90 seconds per native analysis and 16 MiB native output.
Vue SFC bodies/templates, CSS imports, compiler plugins and project-reference/
extended tsconfig resolution are unsupported and explicitly incomplete. Dynamic
Java/JavaScript runtime dispatch, reflection, external callers and full ecosystem
reachability are not proven. Native errors/unresolved bindings remain explicit;
partial models are useful observations and never reported fully resolved.
These are engineering bounds, not expanded target capacity contracts.

Run the focused native and both-application regressions using already provisioned
inputs (a fresh workspace generates the applications; an existing prepared one is
verified against its original binding):

```bash
python3.14 engineering/source_intelligence/qualification.py \
  --workspace /tmp/acp-source-qualification \
  --maven-repo "$ACP_SOURCE_MAVEN_REPO" --node-modules "$ACP_SOURCE_NODE_MODULES"
```

The separate Ubuntu 24.04 job provisions Python 3.14.7, Node 24.21.0, JDK 21 and
existing hash/lock-pinned dependencies only on a disposable GitHub runner. It
retains exact source commit, original bindings, models and results. Existing
Phase 6 jobs and release gates are unchanged.

Phase 7 is IN_PROGRESS, not complete. Phase 6 formal release closure remains
BLOCKED; generator 0.6.0 remains unsealed. Phases 8–12 are NOT_STARTED.
Operational security is NOT_ESTABLISHED; production release is NOT_AUTHORIZED.
