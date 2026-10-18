"""Real bounded startup, API and browser trials using existing disposable fixtures."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.generator_builds import runtime as existing
from engineering.generator_builds.qualify import run, sha
from engineering.traceability.qualification import inputs
from engineering.performance.measure import BROWSER, summarize, digest
from compiler_core import _ownership
from filesystem_artifacts import FilesystemArtifactStore


@contextmanager
def startup_observer():
    original_launch, original_open = subprocess.Popen, urllib.request.urlopen
    original_command=existing.browser_gate.command
    state = {}
    def launch(argv, *args, **kwargs):
        process = original_launch(argv, *args, **kwargs)
        if argv[0] == 'java' and 'acp.browser.BrowserServer' in argv:
            state.update(pid=process.pid, start=time.perf_counter(), executable=argv[0], argv=argv)
        return process
    def memory():
        return Path('/proc')/str(state['pid'])/'status'
    def command(argv, *args, **kwargs):
        value=original_command(argv,*args,**kwargs)
        if argv==['npm','run','e2e']:
            state['postWorkloadProcessStatus']=memory().read_text()
        return value
    def opened(url, *args, **kwargs):
        response = original_open(url, *args, **kwargs)
        if str(url).endswith('/actuator/health') and 'start' in state and 'readinessMs' not in state:
            state['readinessMs']=(time.perf_counter()-state['start'])*1000
            state['readyProcessStatus']=memory().read_text()
        return response
    subprocess.Popen, urllib.request.urlopen = launch, opened
    existing.browser_gate.command=command
    try: yield state
    finally:
        subprocess.Popen, urllib.request.urlopen = original_launch, original_open
        existing.browser_gate.command=original_command


def qualify(workspace):
    workspace=Path(workspace).absolute();workspace.mkdir(mode=0o700,exist_ok=False)
    gate=existing.browser_gate
    original_tests,original_source,original_config=gate.tests,gate.server_source,gate.CONFIG
    gate.CONFIG=gate.CONFIG.replace('timeout:60000','timeout:180000')
    result={'scope':'QUALIFICATION_ONLY','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'candidate':existing.SuccessorCandidate().descriptor(),'applications':{},
            'environment':{'python':platform.python_version(),'kernel':platform.release(),'machine':platform.machine(),
              'cpuCount':os.cpu_count(),'sharedHostLoad':os.getloadavg(),'meminfo':Path('/proc/meminfo').read_text(), 'cpuinfo':Path('/proc/cpuinfo').read_text(),
              'node':subprocess.check_output(['node','--version'],text=True).strip(),
              'java':subprocess.check_output(['java','-version'],stderr=subprocess.STDOUT,text=True).strip(),
              'maven':subprocess.check_output(['mvn','--version'],text=True).strip()},
            'workload':{'repetitions':3,'views':2,'querySamplesPerView':100,'actionSamplesPerView':20,'concurrentSamplesPerView':200,
              'concurrency':4,'burstSize':4,'sessionWarmupRequests':4,'overloadRequests':200,'pageSamplesPerView':10,'population':'1 resource, 1 actor, 2 tenants; fresh reset excluded from latency',
              'authentication':'existing trusted-JWT test component; one fixed authenticated event per server; not cryptographic issuer qualification',
              'coldDefinition':'first new JVM and browser context; OS/filesystem caches not evicted', 'warmDefinition':'later samples and new JVM trials using warm host caches',
              'knownLimitation':'concurrent requests can produce CLOCK_REVERSED when rate-clock sampling precedes row-lock order; recorded as failed requests, no retry or serialization',
              'limits':'unaltered actor token bucket: 100/minute, burst 10; bounded bursts reset fixture between batches; four independent worker sessions initialized before timing'}}
    try:
        for domain in ('payment','case-management'):
            candidate,snapshot,request,plan=inputs(domain)
            project=workspace/domain;store=FilesystemArtifactStore(project);store.apply(plan)
            store.adopt_human('frontend/src/extensions/identity.ts')
            inventory=store.inventory();plan=_ownership(candidate.plan(snapshot,request,inventory=inventory),inventory);store.apply(plan)
            owned={p.relative_to(project).as_posix():sha(p) for p in project.rglob('*') if p.is_file()}
            run(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],project/'frontend')
            if os.environ.get('CI')=='true':run(['npx','--no-install','playwright','install','--with-deps','chromium'],project/'frontend')
            # Pin the *test* authentication event across concurrent reads. No change
            # to production SessionGate or stale/expired/revoked acceptance rules.
            def source(current):
                return original_source(current).replace('public class BrowserServer {','public class BrowserServer {\n static final Instant AUTH_EVENT=Instant.now();').replace('var now=Instant.now();return Jwt','var now=AUTH_EVENT;return Jwt').replace('Set.of("browser-authorized",','Set.of("browser-perf-0","browser-perf-1","browser-perf-2","browser-perf-3","browser-authorized",').replace('.claim("sid",token.equals', '.claim("sid",token.startsWith("browser-perf-")?token:token.equals')
            gate.server_source=source
            gate.tests=lambda current:BROWSER.replace('EVENTS','1' if current=='payment' else '3')
            trials=[]
            with existing.database() as container:
                for repetition in range(3):
                    logs=workspace/f'{domain}-trial-{repetition}';logs.mkdir()
                    with startup_observer() as startup:
                        report=gate.browser(project,domain,logs)
                    existing.verify_report(report,2)
                    if (Path('/proc')/str(startup['pid'])).exists():raise ValueError('APPLICATION_PROCESS_LEAK')
                    startup['processCleanup']='REMOVED'
                    if 'readinessMs' not in startup:raise ValueError('NO_REAL_READINESS_OBSERVATION')
                    trial={'repetition':repetition,'startup':startup,'views':{}}
                    for view in ('COMPACT','EXPANDED'):
                        rawpath=project/'frontend'/f'performance-{view}.json'
                        raw=json.loads(rawpath.read_text());(logs/rawpath.name).write_bytes(rawpath.read_bytes())
                        if (len(raw['query']),len(raw['action']),len(raw['concurrent']),len(raw['pages']))!=(100,20,200,10):raise ValueError('MISSING_ACTUAL_SAMPLES')
                        trial['views'][view]={'rawSHA256':sha(rawpath),'browser':raw['browser'], 'viewport':raw['viewport'],
                           'query':summarize(raw['query']),'action':summarize(raw['action']),
                           'pages':{'coldContextFirstMs':raw['pages'][0],'warm':summarize(raw['pages'][1:])},
                           'concurrent':{**summarize(raw['concurrent'],elapsed_ms=raw['concurrentElapsedMs'],failures=raw['failures']),
                            'statuses':raw['concurrentStatuses'],'successLatency':summarize(raw['concurrentSuccess']),
                            'successfulThroughputPerSecond':len(raw['concurrentSuccess'])*1000/raw['concurrentElapsedMs']},
                           'overload':{**summarize(raw['overload']['samples'],elapsed_ms=raw['overload']['elapsedMs'],failures=sum(v for k,v in raw['overload']['statuses'].items() if k!='200')), 'statuses':raw['overload']['statuses']}}
                    (logs/'playwright-results.json').write_text(json.dumps(report,sort_keys=True))
                    trials.append(trial)
                version=existing.docker('exec',container,'psql','-U','acp_runtime','-d','acp_runtime','-Atc','SHOW server_version;')
                # Exact stored population measured independently of HTTP fixtures.
                schema='acp_browser_'+domain.replace('-','_')
                population=existing.docker('exec',container,'psql','-U','acp_runtime','-d','acp_runtime','-Atc',
                    "SELECT table_name FROM information_schema.tables WHERE table_schema='"+schema+"' ORDER BY table_name;")
            for relative,expected in owned.items():
                if sha(project/relative)!=expected:raise ValueError('GENERATED_SOURCE_CHANGED:'+relative)
            result['applications'][domain]={'postgres':version,'schemaTables':population.splitlines(),'trials':trials,
                'databaseCleanup':'REMOVED','sourceHashes':owned,'snapshot':snapshot.read()['contentDigest']}
            (workspace/'performance-results.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    finally:gate.tests,gate.server_source,gate.CONFIG=original_tests,original_source,original_config
    result['resultSHA256']=digest(result)
    (workspace/'performance-results.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
    with existing.supervised_processes():qualify(a.workspace)
