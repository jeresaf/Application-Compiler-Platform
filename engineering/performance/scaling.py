"""Synthetic-only fixture scaling through the existing bounded compiler."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tooling')]
from canonical_json import canonical_bytes, load
from canonical_ir import normalize_candidate
from compiler_contracts import Document, Success, Stage, fingerprint, wire
from compiler_core import compile_pipeline
from compiler_reference import fixture_context, FixtureApproval
from target_worker import ProductionTarget
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate


def fixture(domain, extra):
    if type(extra) is not int or extra < 0:
        raise ValueError('FIXTURE_SIZE')
    content = load(ROOT / f'test-corpus/deterministic-v04/{domain}-canonical-candidate.json')['content']
    nodes = copy.deepcopy(content['nodes'])
    by = {n['id']: n for n in nodes}
    # Test-only optional storage fields increase real schema/domain/provenance
    # work without altering any existing query, workflow, policy or UI contract.
    # The target explicitly supports only one task table column; do not raise it.
    for index in range(extra):
        field = copy.deepcopy(by['FLD-TASK-SUMMARY'])
        field.update(id=f'PERF-FIELD-{index:04d}', name=f'Test field {index:04d}', revision=1)
        field['data']['optional']=True
        field['origins'] = [{'source':'fixture:performance-test-only', 'locator':field['id'], 'actor':'fixture:author', 'actorType':'HUMAN'}]
        nodes.append(field)
    model = {'modelVersion':'0.4.0','applicationId':content['applicationId'], 'snapshotId':'PERFORMANCE-TEST-ONLY',
             'nodes':nodes,'issues':copy.deepcopy(content['issues']),
             'approvals':[{'subject':{'id':n['id'],'revision':n['revision']},'reviewer':'synthetic-test-only','evidence':'NOT_HUMAN_APPROVAL'} for n in nodes]}
    return model


class CandidatePort(SuccessorCandidate):
    identity = 'acp-spring-vue-postgres/0.6.0'
    capabilities = ProductionTarget.capabilities

    def lower(self, realization, request):
        nodes = sorted((o.semantic.read() for o in realization.objects), key=lambda n:n['id'])
        self._model.negotiate(nodes, ['semantic.execution-dataflow/0.3','acp.deterministic-execution.0.4'], self.profile['decisions'], self.profile, '0.3.0')
        from compiler_reference import SyntheticTarget
        target = SyntheticTarget.lower(self, realization, request)
        return replace(target, target_model=Document.of(self._model.lower(nodes, self.profile, '0.3.0')))

    def plan(self, target, request, *, inventory=()):
        return ProductionTarget.plan(self, target, request, inventory=inventory)


def compile_fixture(domain, extra, *, nodes=None):
    model = fixture(domain, extra)
    source, context = fixture_context(model)
    target = CandidatePort()
    decisions = tuple(replace(d, choice=Document.of({'choice':target.profile['decisions'][d.role]})) for d in context.request.decisions)
    limits = context.request.resources
    # Same existing full-UI work policy. Never increase byte, node or depth caps.
    limits = replace(limits, work=1_000_000, timeout_ms=120_000, **({'nodes':nodes} if nodes is not None else {}))
    request = replace(context.request, target=target.identity, generator=target.generator,
        required_capabilities=tuple(sorted(target.capabilities)), decisions=decisions,
        decision_digests=tuple(sorted(fingerprint(d,'decision') for d in decisions)), resources=limits)
    snapshot = Document.of(normalize_candidate(model))
    context = replace(context, target=target, request=request,
        approval=FixtureApproval((snapshot,), decisions, request.approval_evidence))
    started = time.perf_counter()
    class Clock:
        def elapsed_ms(self):return int((time.perf_counter()-started)*1000)
        def cancelled(self):return False
    context=replace(context,control=Clock())
    compilation = compile_pipeline(source, context)
    elapsed = (time.perf_counter() - started) * 1000
    result = compilation.result
    report = {'domain':domain,'extraOptionalFields':extra,'nodes':len(model['nodes']), 'inputBytes':len(canonical_bytes(model)),
              'wallMs':elapsed,'peakRssKiB':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'limits':wire(limits),'snapshot':snapshot.read()['contentDigest'],'synthetic':'TEST_ONLY_NOT_APPROVED',
              'status':'PASS' if isinstance(result,Success) else 'REJECTED',
              'diagnostics':[] if isinstance(result,Success) else [d.code for d in result.diagnostics],
              'diagnosticStages':[] if isinstance(result,Success) else [str(d.stage) for d in result.diagnostics]}
    if isinstance(result, Success):
        plan = result.output
        report.update(artifactPlanBytes=len(canonical_bytes(wire(plan))), artifactPlanDigest=result.output_digest,
            sourceBytes=sum(len(a.content.read()['text'].encode()) for a in plan.artifacts), artifacts=len(plan.artifacts),
            frontendBytes=sum(len(a.content.read()['text'].encode()) for a in plan.artifacts if a.path.startswith('frontend/')),
            provenanceBytes=sum(len(a.content.read()['text'].encode()) for a in plan.artifacts if a.path=='acp/provenance.json'))
    return report, result, snapshot, request


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('domain');p.add_argument('extra',type=int);a=p.parse_args()
    print(json.dumps(compile_fixture(a.domain,a.extra)[0],sort_keys=True))


def validate_trials(trials, *, baseline=False):
    passed=[row for row in trials if row['status']=='PASS']
    if len({row['artifactPlanDigest'] for row in passed})>1:
        raise ValueError('NONDETERMINISTIC_SCALING_PLAN')
    if any(row['status']!='PASS' and row['diagnostics']!=['ACP-COMPILER-RESOURCE'] for row in trials):
        raise ValueError('INVALID_SCALING_FIXTURE')
    if baseline and not passed:
        raise ValueError('BASELINE_COMPILER_RESOURCE_FAILURE')
    # Wall-time budgets intentionally depend on real host scheduling. A rejected
    # timed sample is retained as a failure; it is not semantic nondeterminism.


def measure_curve(workspace):
    """Fresh interpreter per sample: peak RSS is not contaminated by prior tiers."""
    import subprocess
    workspace=Path(workspace);workspace.mkdir(mode=0o700,exist_ok=False)
    rows=[]
    for domain in ('payment','case-management'):
        for extra in (0,3,8,32,64):
            trials=[]
            for repetition in range(3):
                completed=subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),domain,str(extra)],cwd=ROOT,
                    check=True,capture_output=True,text=True,timeout=240)
                row=json.loads(completed.stdout)
                row['repetition']=repetition;trials.append(row);rows.append(row)
                (workspace/'compiler-scaling.json').write_text(json.dumps(rows,sort_keys=True,indent=2)+'\n')
                print(domain,extra,repetition,row['status'],round(row['wallMs']),flush=True)
            validate_trials(trials,baseline=extra==0)
    return rows
