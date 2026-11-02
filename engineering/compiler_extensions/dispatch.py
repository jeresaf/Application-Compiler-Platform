"""Explicit version registration over the frozen compiler's stage engine.

No code constants are changed. Only frontend transport dispatch is versioned;
all six subsequent stage algorithms, checks, budgets and ports are unchanged.
"""
from dataclasses import dataclass,replace
import types
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tooling'))
import compiler_core as core
from compiler_contracts import Document,Ingested,SemanticAST,Stage,VERSION

@dataclass(frozen=True)
class Registration:
    frontend:str
    model_version:str
    features:tuple
    compiler:str
    pipeline:str
    semantics:object
    application_kinds:frozenset
    categories:tuple

class TransportIdentity:
    identity='acp-structured-reference/0.1.0'


def kernel(registration):
    """Bind a trusted immutable registration; never register from source data."""
    if type(registration) is not Registration or not registration.features:
        raise ValueError('UNREGISTERED_COMPILER_EXTENSION')
    ns=dict(vars(core))
    for name,fn in vars(core).items():
        if isinstance(fn,types.FunctionType) and fn.__module__==core.__name__:
            bound=types.FunctionType(fn.__code__,ns,fn.__name__,fn.__defaults__,fn.__closure__)
            bound.__kwdefaults__=fn.__kwdefaults__;ns[name]=bound
    def manifest(ctx):
        r=ctx.request
        if (r.frontend,r.features,r.compiler,r.pipeline)!=(registration.frontend,registration.features,registration.compiler,registration.pipeline) or ctx.frontend.identity!=registration.frontend:
            core.fail('VERSION')
        # Reuse the original transport/port manifest validator, not its closed
        # historical dialect table. This validation view never leaves this call.
        view=replace(ctx,frontend=TransportIdentity(),request=replace(r,
            frontend=TransportIdentity.identity,features=('acp.phase1.0.2',),
            compiler=core.COMPILER,pipeline=core.PIPELINE))
        core._manifest(view)
        if 'semantic.execution-dataflow/0.3' not in r.required_capabilities:core.fail('CAPABILITY')
    original=ns['_perform']
    def perform(stage,value,ctx,budget):
        r=ctx.request
        if stage==Stage.INGEST:
            if core.fingerprint(value,'source')!=r.source_digest:core.fail('INPUT')
            model=value.document.read();locations=value.source_map.read()
            if type(model) is not dict or model.get('modelVersion')!=registration.model_version:core.fail('VERSION')
            if len(model.get('nodes',[]))>r.resources.nodes:core.fail('RESOURCE')
            identities={n.get('id') for n in model.get('nodes',[]) if type(n) is dict}
            if type(locations) is not dict or set(locations)-identities or any(type(v) is not str or v.startswith('/') or '\\' in v or ':' in v or '..' in v.split('/') for v in locations.values()):core.fail('INPUT')
            ns['_port'](ctx,'frontend');result=ctx.frontend.ingest(value)
            if type(result) is not Ingested or result.representation!=value.document or result.source_map!=value.source_map or result.dialect!=r.frontend:core.fail('INPUT')
            return result,0,0
        if stage==Stage.ELABORATE:
            if value.dialect!=r.frontend:core.fail('VERSION')
            ns['_port'](ctx,'frontend');ast=ctx.frontend.elaborate(value)
            if type(ast) is not SemanticAST or type(ast.model) is not Document or type(ast.source_map) is not Document or ast.version!=VERSION:core.fail('INPUT')
            model=ast.model.read();locations=ast.source_map.read()
            if type(model) is not dict or model.get('modelVersion')!=registration.model_version:core.fail('VERSION')
            if type(locations) is not dict or set(locations)-{n.get('id') for n in model.get('nodes',[]) if type(n) is dict}:core.fail('INPUT')
            return ast,0,0
        return original(stage,value,ctx,budget)
    s=registration.semantics
    ns.update(_manifest=manifest,_perform=perform,validate=s.diagnostics,
        normalize_candidate=s.normalize_candidate,validate_snapshot=s.validate_snapshot,admit=s.admit,
        APPLICATION_KINDS=core.APPLICATION_KINDS|registration.application_kinds,
        CATEGORIES={k:set(v) for k,v in registration.categories})
    return ns
