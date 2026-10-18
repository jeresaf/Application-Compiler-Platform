"""Candidate-only performance/scaling qualification with raw retained measurements."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import zipfile
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.performance.runtime import qualify as performance
from engineering.performance.scaling import compile_fixture, measure_curve
from engineering.performance.measure import digest
from engineering.performance.rate_regression import qualify as rate_regression
from engineering.generator_builds import runtime as existing
from engineering.generator_builds.qualify import run, sha
from filesystem_artifacts import FilesystemArtifactStore
from compiler_contracts import Success
from target_worker import bundle_digest

SCALE_BROWSER=r'''import {test,expect} from '@playwright/test';import fs from 'node:fs';import {ui} from '../src/task-ui-model';
test('larger valid generated fixture renders unchanged business UI',async({page,browser})=>{
 const headers={Authorization:'Bearer browser-authorized'};
 expect((await page.request.post('/__test/reset',{headers})).status()).toBe(200);
 const samples=[];
 for(let i=0;i<5;i++){
  const start=performance.now();await page.goto('/');await expect(page.getByRole('button',{name:'Select fixture-resource',exact:true})).toBeVisible();samples.push(performance.now()-start);
  expect(await page.locator('thead th').count()).toBe(2);
  expect(await page.locator('section[data-semantic-id]').evaluateAll(es=>es.map(e=>e.getAttribute('data-semantic-id')))).toEqual(ui.screen.data.content.map(r=>r.id));
 }
 const bounds=await page.evaluate(()=>({elements:document.querySelectorAll('*').length,scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,jsHeap:(performance as any).memory?.usedJSHeapSize??null}));
 fs.writeFileSync('scaling-'+test.info().project.name+'.json',JSON.stringify({browser:browser.version(),samples,bounds,columns:ui.columns.length}));
});'''


def package(project,destination):
    """Measured compiled class/frontend bundle, not a deployable release archive."""
    roots=('backend/target/classes','frontend/dist')
    rows={}
    with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in roots:
            root=project/name
            if not root.is_dir():raise ValueError('MISSING_BUILD_OUTPUT:'+name)
            for path in sorted(root.rglob('*')):
                if path.is_symlink():raise ValueError('BUILD_OUTPUT_SYMLINK')
                if not path.is_file():continue
                relative=path.relative_to(project).as_posix();data=path.read_bytes()
                info=zipfile.ZipInfo(relative,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(info,data);rows[relative]={'bytes':len(data),'sha256':sha(path)}
    return {'compressedBytes':destination.stat().st_size,'uncompressedBytes':sum(v['bytes'] for v in rows.values()),
            'sha256':sha(destination),'files':rows,'scope':'compiled classes/resources and frontend distribution; not deployment acceptance'}


def scaled_applications(workspace, rows, baseline):
    gate=existing.browser_gate;original_tests=gate.tests
    results={}
    try:
        for domain in ('payment','case-management'):
            passed=[r for r in rows if r['domain']==domain and r['status']=='PASS']
            largest=max(passed,key=lambda r:r['extraOptionalFields'])
            if largest['extraOptionalFields']<=0:raise ValueError('NO_VALID_LARGER_GENERATED_FIXTURE')
            measured,compilation,snapshot,request=compile_fixture(domain,largest['extraOptionalFields'])
            if not isinstance(compilation,Success) or measured['artifactPlanDigest']!=largest['artifactPlanDigest']:
                raise ValueError('SCALING_SOURCE_DRIFT')
            project=workspace/(domain+'-larger');store=FilesystemArtifactStore(project);store.apply(compilation.output)
            store.adopt_human('frontend/src/extensions/identity.ts')
            original={p.relative_to(project).as_posix():sha(p) for p in project.rglob('*') if p.is_file()}
            run(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],project/'frontend')
            logs=workspace/(domain+'-larger-logs');logs.mkdir()
            gate.tests=lambda current:SCALE_BROWSER
            with existing.database():
                report=gate.browser(project,domain,logs)
                existing.verify_report(report,2)
            for relative,expected in original.items():
                if sha(project/relative)!=expected:raise ValueError('LARGER_SOURCE_MODIFIED:'+relative)
            views={}
            for view in ('COMPACT','EXPANDED'):
                path=project/'frontend'/f'scaling-{view}.json';views[view]=json.loads(path.read_text());(logs/path.name).write_bytes(path.read_bytes())
            (logs/'playwright-results.json').write_text(json.dumps(report,sort_keys=True))
            results[domain]={'largestSuccessfulFixture':largest,'browser':views,'databaseCleanup':'REMOVED',
                'baselinePackage':package(baseline/domain,workspace/(domain+'-baseline-build.zip')),
                'largerPackage':package(project,workspace/(domain+'-larger-build.zip')),'sourceHashes':original}
    finally:gate.tests=original_tests
    return results


def qualify(workspace):
    workspace=Path(workspace).absolute();workspace.mkdir(mode=0o700,exist_ok=False)
    bound={p.relative_to(ROOT).as_posix():sha(p) for folder in ('engineering/performance','verification/performance') for p in sorted((ROOT/folder).glob('*.py'))}
    started=datetime.now(timezone.utc).isoformat()
    with existing.supervised_processes():
        rate_results=rate_regression(workspace/'rate-regressions')
        performance_result=performance(workspace/'applications')
        rows=measure_curve(workspace/'scaling')
        applications=scaled_applications(workspace,rows,workspace/'applications')
    if bound!={p:sha(ROOT/p) for p in bound}:raise ValueError('MEASUREMENT_SOURCE_CHANGED')
    failures=sum(v['concurrent']['failures'] for app in performance_result['applications'].values() for trial in app['trials'] for v in trial['views'].values())
    if failures:raise ValueError('CONCURRENT_REQUEST_FAILURE')
    result={'scope':'QUALIFICATION_ONLY','releaseAcceptance':'NOT_GRANTED','phase6':'IN_PROGRESS','phase7':'NOT_STARTED',
        'releaseClosure':'BLOCKED','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'execution':{k:os.environ.get(k) for k in ('GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_SHA','RUNNER_OS','RUNNER_ARCH')},
        'sourceHashes':bound,'startedAt':started,'completedAt':datetime.now(timezone.utc).isoformat(),
        'sealedParent':'sha256:'+bundle_digest(),'candidate':performance_result['candidate'],
        'performanceResultSHA256':sha(workspace/'applications/performance-results.json'),
        'scalingResultSHA256':sha(workspace/'scaling/compiler-scaling.json'),'scalingBuilds':applications,
        'criteria':{'30':'BOUNDED_BASELINE_MEASURED',
                    '31':'BOUNDED_VALID_FIXTURE_SCALING_MEASURED'},
        'limitations':['No production SLO or arbitrary population capacity established.',
                      'The existing UI supports exactly one task table column; storage-field growth preserves that contract.',
                      'Compiler byte/node/depth limits compose; a 2000-node ceiling does not guarantee every 2000-node plan fits one MiB.',
                      'Host caches are not forcibly evicted; cold means new process/context.',
                      'Every timed in-capacity request must succeed; overload admits only HTTP 200 or 429, without retry.',
                      'No candidate result is sealed 0.5.0 release acceptance.'],
        'concurrentClockFailures':failures,'rateRegressions':rate_results}
    result['resultSHA256']=digest(result)
    (workspace/'qualification-results.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();qualify(a.workspace)
