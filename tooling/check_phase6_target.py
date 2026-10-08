"""Strict negotiated Phase 6 gate. No direct lowering/template bypass.

Failure is expected until the complete domains earn every target capability.
Successful component tests cannot substitute for this gate.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from canonical_json import load
from compiler_contracts import Document, Success, fingerprint, wire
from compiler_core import compile_pipeline
from compiler_reference import FixtureApproval, fixture_context
from execution_approval import approved_snapshot, header
from execution_fixtures import DEST
from filesystem_artifacts import FilesystemArtifactStore
from phase6_reference_tests import source as test_source, http_source, variants
from target_worker import ROOT, PROFILE, ProductionTarget, TargetWorkerError
sys.path.insert(0, str(ROOT / "worker"))
from target_provenance import inspect_mapping


def context_for(domain):
    # Verifies the fresh human-reference proof before exposing host approval.
    approved = Document.of(approved_snapshot(domain))
    source, context = fixture_context(load(DEST / (domain + '-authoring.json')))
    target = ProductionTarget()
    decisions = tuple(replace(d, choice=Document.of({'choice': PROFILE['decisions'][d.role]})) for d in context.request.decisions)
    evidence = Document.of(header())
    request = replace(context.request, target=target.identity, generator=target.generator,
        required_capabilities=tuple(sorted(target.capabilities)), decisions=decisions,
        decision_digests=tuple(sorted(fingerprint(d, 'decision') for d in decisions)), approval_evidence=evidence)
    # Bounded host allowlist, NOT a production identity/approval provider.
    return source, replace(context, request=request, target=target,
        approval=FixtureApproval((approved,), decisions, evidence))


def run(output, builds):
    output.mkdir(parents=True, exist_ok=False)
    report = {'mode': 'FULL_NEGOTIATED_TARGET_GATE', 'phase6': 'OPEN', 'domains': {}}
    failed = False
    for domain in ('payment', 'case-management'):
        source, context = context_for(domain)
        compilation = compile_pipeline(source, context)
        evidence = {'canonicalDigest': context.request.snapshot_digest, 'audit': wire(compilation.audit)}
        report['domains'][domain] = evidence
        if not isinstance(compilation.result, Success):
            evidence['result'] = 'BLOCKED'
            evidence['diagnostics'] = wire(compilation.result.diagnostics)
            # Preserve worker details in addition to the neutral compiler fault.
            try:
                context.target.worker.call('negotiate', {'nodes': approved_snapshot(domain)['content']['nodes'],
                    'canonicalVersion': '0.2.0', 'required': ['semantic.execution-dataflow/0.3'], 'decisions': PROFILE['decisions']})
            except TargetWorkerError as error:
                evidence['targetAdmission'] = str(error)
            failed = True
            continue
        repeat_source, repeat_context = context_for(domain)
        repeat = compile_pipeline(repeat_source, repeat_context).result
        if not isinstance(repeat, Success) or repeat.output_digest != compilation.result.output_digest:
            raise RuntimeError('NONDETERMINISTIC_ARTIFACT_PLAN')
        directory = output / domain
        store = FilesystemArtifactStore(directory)
        store.apply(compilation.result.output)
        extension = 'frontend/src/extensions/identity.ts'
        store.adopt_human(extension)
        (directory / extension).write_text('// explicit host-owned identity integration\n')
        regeneration = compile_pipeline(source, replace(context, inventory=store.inventory())).result
        if not isinstance(regeneration, Success):
            raise RuntimeError('REGENERATION_FAILED')
        store.apply(regeneration.output)
        if (directory / extension).read_text() != '// explicit host-owned identity integration\n':
            raise RuntimeError('HUMAN_EXTENSION_OVERWRITTEN')
        mappings = json.loads((directory / 'acp/provenance.json').read_text())['artifacts']
        for mapping in mappings:
            if inspect_mapping(directory, mapping)['status'] != 'CURRENT':
                raise RuntimeError('PROVENANCE_FAILED')
        evidence.update(result='PIPELINE_PASS', artifactPlanDigest=compilation.result.output_digest,
                        ownership='PASS', provenance='PASS', checks={})
        if builds:
            test = directory / 'backend/src/test/java/acp/generated/ExplicitExecutionTest.java'
            test.parent.mkdir(parents=True, exist_ok=True)
            test.write_text(test_source(domain))
            (test.parent / 'TypedHttpTest.java').write_text(http_source(domain))
            for path, text in variants(domain).items():
                p = directory / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
            checks = [('backend-postgresql', 'backend', ['mvn', '-B', '-ntp', 'test']),
                ('frontend-lock', 'frontend', ['npm', 'ci', '--ignore-scripts', '--no-audit', '--no-fund']),
                ('frontend-types', 'frontend', ['npm', 'run', 'typecheck']),
                ('frontend-tests', 'frontend', ['npm', 'test']),
                ('frontend-build', 'frontend', ['npm', 'run', 'build']),
                ('browser-install', 'frontend', ['npx', '--no-install', 'playwright', 'install', '--with-deps', 'chromium']),
                ('browser-journeys', 'frontend', ['npm', 'run', 'e2e'])]
            for key, folder, command in checks:
                with (output / (domain + '-' + key + '.log')).open('wb') as log:
                    result = subprocess.run(command, cwd=directory / folder, stdout=log, stderr=subprocess.STDOUT, timeout=600)
                evidence['checks'][key] = 'PASS' if result.returncode == 0 else 'FAIL'
                if result.returncode:
                    failed = True
                    break
    report['result'] = 'BLOCKED' if failed else 'PIPELINE_CHECKS_PASS_PHASE6_EXIT_REVIEW_STILL_REQUIRED'
    (output / 'negotiated-report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
    return int(failed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-builds', action='store_true')
    args = parser.parse_args()
    raise SystemExit(run(args.output.absolute(), args.run_builds))
