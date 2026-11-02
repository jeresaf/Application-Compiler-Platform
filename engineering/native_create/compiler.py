"""Version-scoped binding of the existing compiler kernel, not a second compiler.

Only the kernel's two fixed frontend/version dispatch tables are specialized.
All stage algorithms, budgets, approval ports, ownership and publication checks
are reused. No imported module's globals or functions are modified.
"""
import types
from dataclasses import replace
from engineering.native_create import semantics
from engineering.native_create.schema import FEATURE, KINDS
import compiler_core as core
from compiler_contracts import (Document, Source, Subject, Decision,
    CompilationRequest, fingerprint, COMPILER, PIPELINE)
from compiler_ports import CompilationContext
from compiler_reference import (StructuredFrontendV04, FixtureApproval, MemorySnapshots,
    MemoryCache, ReferenceControl, SyntheticTarget)

FRONTEND = 'acp-structured-reference/0.4.0'
COMPILER_ID = COMPILER + '+native-create.1'
PIPELINE_ID = PIPELINE + '+native-create.1'


def _dispatch(code):
    """Closed, explicit version dispatch specialization; no runtime source eval."""
    mapping = {'acp-structured-reference/0.3.0': FRONTEND,
               'acp.deterministic-execution.0.4': FEATURE, '0.4.0': '0.5.0'}
    def value(v):
        if isinstance(v, str):
            return mapping.get(v, v)
        if isinstance(v, tuple):
            return tuple(value(x) for x in v)
        if isinstance(v, frozenset):
            return frozenset(value(x) for x in v)
        if isinstance(v, types.CodeType):
            return _dispatch(v)
        return v
    return code.replace(co_consts=tuple(value(v) for v in code.co_consts))


def kernel():
    namespace = dict(vars(core))
    # Functions share a private binding table; root kernel state remains untouched.
    for name, fn in vars(core).items():
        if isinstance(fn, types.FunctionType) and fn.__module__ == core.__name__:
            code = _dispatch(fn.__code__) if name in {'_manifest', '_perform'} else fn.__code__
            bound = types.FunctionType(code, namespace, fn.__name__, fn.__defaults__, fn.__closure__)
            bound.__kwdefaults__ = fn.__kwdefaults__
            namespace[name] = bound
    namespace.update(validate=semantics.diagnostics,
        normalize_candidate=semantics.normalize_candidate,
        validate_snapshot=semantics.validate_snapshot, admit=semantics.admit,
        COMPILER=COMPILER_ID, PIPELINE=PIPELINE_ID,
        APPLICATION_KINDS=core.APPLICATION_KINDS | KINDS)
    categories = {k: set(v) for k, v in core.CATEGORIES.items()}
    categories['authorization'].update({'CreateOperation', 'CreatePermission'})
    categories['audit'].add('CreateOperation')
    categories['tests'].update(KINDS)
    categories['reliability'].add('CreateOperation')
    namespace['CATEGORIES'] = categories
    return namespace


class NativeFrontend(StructuredFrontendV04):
    identity = FRONTEND


def fixture_context(source, target=None, inventory=()):
    """Exact-byte synthetic preview allowlist. Never human semantic approval."""
    snapshot = Document.of(semantics.normalize_candidate(source))
    document = Source(Document.of(source))
    content = snapshot.read()['content']
    root = next(n for n in content['nodes'] if n['kind'] == 'Decision')
    origin = (Subject(content['applicationId'], root['id'], root['revision']),)
    target = target or SyntheticTarget()
    choices = getattr(target,'profile',{}).get('decisions',{})
    decisions = tuple(Decision('native-preview-' + role, role, origin,
        Document.of({'choice': choices.get(role,'framework-neutral-native-create-preview'),
                     'status': 'TEST_ONLY'})) for role in ('architecture', 'design'))
    evidence = Document.of({'scope': 'UNAPPROVED_SYNTHETIC_PREVIEW_ONLY',
                            'feature': FEATURE})
    request = CompilationRequest(content['applicationId'], snapshot.read()['contentDigest'],
        fingerprint(document, 'source'), evidence, decisions,
        tuple(sorted(fingerprint(d, 'decision') for d in decisions)))
    request = replace(request, compiler=COMPILER_ID, pipeline=PIPELINE_ID,
        frontend=FRONTEND, features=(FEATURE,), target=target.identity,
        generator=target.generator,
        required_capabilities=tuple(sorted((*request.required_capabilities,
                                            'semantic.execution-dataflow/0.3',
                                            *(('target.project-artifacts/1', FEATURE) if target.identity != SyntheticTarget.identity else ())))))
    return document, CompilationContext(request, MemorySnapshots((snapshot,)),
        NativeFrontend(), FixtureApproval((snapshot,), decisions, evidence), target,
        MemoryCache(), ReferenceControl(), tuple(inventory))


def compile_pipeline(source, context, *, repeat=False):
    # Other historical dialects continue through their original public entrypoint.
    if context.request.frontend != FRONTEND or context.request.features != (FEATURE,):
        raise ValueError('NATIVE_CREATE_EXACT_VERSION_REQUIRED')
    return kernel()['compile_pipeline'](source, context, repeat=repeat)
