"""Run existing real two-domain browser/OIDC suite with assertion-level links."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'tooling')]
from engineering.generator_builds import runtime as existing
from engineering.traceability.qualification import inputs, ownership_matrix, manifest, instrument, runtime_links, sha, require, live_ownership


@contextmanager
def source_tree(project, retained):
    """Exclude exactly the existing declared dependency output during scanning."""
    modules = Path(project)/'frontend/node_modules'
    retained = Path(retained)
    if retained.exists() or retained.is_symlink():
        raise FileExistsError(retained)
    modules.rename(retained)
    try:
        yield
    finally:
        if modules.exists() or modules.is_symlink():
            raise ValueError('DEPENDENCY_RESTORE_COLLISION')
        retained.rename(modules)


def dispatch_browser(project, domain, logs, *, workspace, records, original, traced):
    # Preserve the separately qualified cryptographic OIDC path; never replace it
    # with trusted-JWT component assertions or replay an earlier result.
    if logs == workspace/(domain+'-runtime')/'oidc':
        require(domain in records, 'OIDC_BEFORE_TRACED_RUNTIME')
        return original(project, domain, logs)
    require(domain not in records, 'DUPLICATE_RUNTIME')
    return traced(project, domain, logs)


def qualify(workspace):
    workspace = Path(workspace).absolute()
    # Existing runner rejects an existing destination and owns process/DB cleanup.
    bound_paths = ('engineering/traceability/qualification.py','engineering/traceability/runtime.py','engineering/generator_builds/runtime.py','engineering/traceability/backend.py')
    bound_sources = {p: sha((ROOT/p).read_bytes()) for p in bound_paths}
    records = {}
    original_browser, original_tests = existing.browser_gate.browser, existing.browser_gate.tests
    def browser(project, domain, logs):
        return dispatch_browser(project, domain, logs, workspace=workspace,
                                records=records, original=original_browser, traced=traced)
    def traced(project, domain, logs):
        candidate, snapshot, request, plan = inputs(domain)
        # Exercise native transactions on this domain's exact artifact lineage.
        matrix = ownership_matrix(workspace/(domain+'-ownership'), plan.artifacts[0])
        identity = project/'frontend/src/extensions/identity.ts'
        before = identity.read_bytes()
        try:
            # Exact external test adapter which the existing browser build consumes.
            # Native provenance scans sources only. Temporarily retain the exact
            # declared dependency output outside that source tree, then restore it
            # before compilation; never whitelist arbitrary source additions.
            with source_tree(project, workspace/(domain+'-trace-node-inputs')):
                live = live_ownership(project, plan)
                identity.write_text(existing.browser_gate.IDENTITY)
                provenance = manifest(project, candidate, snapshot, request, plan,
                                      human_paths=('frontend/src/extensions/identity.ts',))
            from engineering.traceability.backend import execute, FAMILIES
            backend = execute(project, domain, snapshot, provenance, logs)
            report = original_browser(project, domain, logs)
            existing.verify_report(report, 14)
            raw = (project/'frontend/browser-results.json').read_bytes()
            source = (project/'frontend/browser-tests/task.spec.ts').read_text()
            links = runtime_links(report, provenance, source, raw)
            require({l['kind'] for l in links+backend['links']} == FAMILIES, 'ALL_REPRESENTATIVE_FAMILIES_REQUIRED')
            # Retain original machine results and exact executed assertion source.
            (logs/'trace-browser-results.json').write_bytes(raw)
            (logs/'trace-task.spec.ts').write_text(source)
            (logs/'trace-provenance.json').write_text(json.dumps(provenance, sort_keys=True, indent=2)+'\n')
            records[domain] = {'scope':'QUALIFICATION_ONLY', 'ownership':matrix, 'liveOwnership':live,
                               'provenance':provenance, 'runtimeLinks':links, 'backend':backend,
                               'generatedSourceHashes':{r['artifact']:r['artifactSHA256'] for r in provenance['artifacts']}}
            return report
        finally:
            identity.write_bytes(before)
    try:
        existing.browser_gate.tests = lambda domain: instrument(original_tests(domain))
        existing.browser_gate.browser = browser
        result = existing.runtime(workspace)
        result['integratedOwnershipProvenanceTraceability'] = records
        result['scope'] = 'QUALIFICATION_ONLY'
        require(bound_sources == {p: sha((ROOT/p).read_bytes()) for p in bound_paths}, 'QUALIFICATION_SOURCE_CHANGED')
        result['executionSource'] = {'commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'files': bound_sources}
        (workspace/'traceability-results.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
        return result
    finally:
        existing.browser_gate.browser, existing.browser_gate.tests = original_browser, original_tests


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    qualify(parser.parse_args().workspace)
