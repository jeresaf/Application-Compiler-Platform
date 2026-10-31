# Read-only ACP MCP adapter

Phase 9 is IN_PROGRESS. This local stdio increment wraps the existing compiler,
Canonical validation, Phase 7 graph and Phase 8 retained verification ports.
It grants no semantic approval, file-write, command-execution or deployment authority.
Phase 6 release closure remains blocked; operational security is not established.
Phase 7 formal acceptance remains pending. Phase 10–12 are not started.

The maintained official [Python SDK](https://github.com/modelcontextprotocol/python-sdk)
2.3.0 handles MCP 2026-07-28 discovery/capabilities and legacy initialization,
dispatch, errors and cancellation. No HTTP listener is exposed.
The adapter's schemas are `acp-mcp-request/1`, `acp-mcp-tool-result/1` and
`acp-mcp-response/1`. Tool discovery supplies the exact JSON schemas.

Use CPython 3.14.7. With dependency installation authorized, create an isolated
virtual environment outside application roots and install
`engineering/mcp_adapter/requirements.txt` using `--require-hashes --only-binary=:all:`;
run `pip check`. Existing compiler/sealed dependencies are unchanged.
All commands below use that environment's `python3.14`.

The existing ACP environment can provision this separate environment without
changing its own dependencies (installation still requires operator approval):

```bash
python3.14 -m venv --without-pip /tmp/acp-phase9-sdk
.venv/bin/python3.14 -m pip --python /tmp/acp-phase9-sdk/bin/python3.14 install --require-hashes --only-binary=:all: -r engineering/mcp_adapter/requirements.txt
.venv/bin/python3.14 -m pip --python /tmp/acp-phase9-sdk/bin/python3.14 check
```

Use a new path if that directory already exists. Select this environment's
interpreter explicitly in subsequent commands and the client configuration.

Obtain the exact existing hosted artifacts using authenticated GitHub access:

```bash
gh api --hostname github.com repos/jeresaf/Application-Compiler-Platform/actions/artifacts/12988799586/zip > /tmp/acp-phase9-phase7.zip
gh api --hostname github.com repos/jeresaf/Application-Compiler-Platform/actions/artifacts/13039542414/zip > /tmp/acp-phase9-phase8.zip
python3.14 -B -m engineering.mcp_adapter.prepare --workspace /tmp/acp-phase9-host --phase7-archive /tmp/acp-phase9-phase7.zip --phase8-archive /tmp/acp-phase9-phase8.zip
python3.14 -B -m engineering.mcp_adapter.server --host-config /tmp/acp-phase9-host/host.json
```

Preparation requires a new destination, verifies pinned archive hashes and
reconstructs the actual original compiler plans. It generates disposable source
only during this explicit host step. It does not run application builds/tests.
The server never prepares or executes qualification on a tool invocation.
Original Phase 7 and Phase 8 records remain unchanged. An expired/unavailable
artifact blocks preparation; it is never replaced by invented results.
Temporary application copies are owned by this execution. Retain qualification
results before removing them under the workspace/evidence custody policy.

Configure a stdio-compatible MCP client with the absolute virtual-environment
Python executable, arguments `-B -m engineering.mcp_adapter.server --host-config
/tmp/acp-phase9-host/host.json`, and this repository as its working directory.
Do not pass GitHub credentials to the server. Host configuration selects both
application roots and pins all model, plan, baseline and result files; no client
argument selects a filesystem path. The host/configuration owner is trusted;
this process is not a sandbox against a compromised host or configuration owner.

Discover tools, then call `project.summary` with
`{"application":"payment"}` or `{"application":"case-management"}`.
`spec.query` lists approved semantic IDs; pass `ids:["<returned ID>"]` for exact
selection. `project.context` accepts up to eight IDs or a 256-character lexical
task (unresolved tasks are rejected). It follows existing forward/reverse semantic
dependency closures, returning original objects, mappings and related verification.
`source.symbol` returns native IDs; use `symbol` with `source.references` or
`source.impact`. A single semantic ID is also an impact selector.
`compiler.plan` inspects original artifact paths, hashes, ownership and origins.
`spec.validate` invokes actual Canonical validation without changing approval.
`compiler.verify` inspects retained results, optionally filtered by
`status: "PASS" | "FAIL" | "BLOCKED" | "NOT_RUN"` and semantic IDs.

Responses retain analysis limitations, whole-application verification counts,
failed checks, release restrictions and historical execution timing. They do not
claim a new or currently fresh execution. Evidence timestamps and original source
identities remain visible. Missing verification remains NOT_RUN/BLOCKED, and
security findings remain FAIL. Source symbol projections omit literal bodies,
raw source, internal logs and private configuration.

Defaults: 20 items, 16,384 ACP payload UTF-8 bytes; maximum 50 items / 32,768 bytes.
MCP carries this projection as structured content with a text fallback.
Use `limit`, `budget` and the returned `next` value as `cursor` with exactly the
same query to continue. `complete: false` explicitly marks a partial page. Required limitations and failed-check summaries are never
silently dropped. An individually oversized item fails with an explicit budget
error. No tokenizer is bundled: tests report measured UTF-8 bytes, not invented
token counts. Frame size is capped at 65,536 bytes, inspection at 30 seconds;
SDK clients may cancel requests. Cancellation abandons only read-only inspection.

Run actual subprocess client tests:

```bash
python3.14 -B -m engineering.mcp_adapter.qualification --host-config /tmp/acp-phase9-host/host.json --output /tmp/acp-phase9-results
```

The focused Ubuntu 24.04 / Python 3.14.7 workflow retains exact source identity,
installed versions, test outcomes and bounded/equivalent full-context response byte measurements.
No sealed-release predicate or existing workflow is changed.
