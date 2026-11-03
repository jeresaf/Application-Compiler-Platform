"""Raw bounded measurements; percentiles describe their declared populations only."""
import json,math,os,threading,time,urllib.request
from pathlib import Path
from collections import Counter
from engineering.performance.measure import summarize
from engineering.source_intelligence.model import require
from engineering.jobs.fixture import PREFIX


def distribution(samples):
    require(bool(samples),'H3_MISSING_SAMPLES')
    return summarize(samples)


def aggregate(rows,elapsed):
    require(rows and math.isfinite(elapsed) and elapsed>0,'H3_WALL_TIME')
    accepted=[r['milliseconds'] for r in rows if r['disposition']=='SUCCESS']
    rejected=[r['milliseconds'] for r in rows if r['disposition']=='EXPECTED_REJECTION']
    require(all(r['disposition'] in ('SUCCESS','EXPECTED_REJECTION') for r in rows),'H3_UNEXPECTED_ERROR')
    return {'population':len(rows),'statuses':dict(Counter(str(r['status']) for r in rows)),
            'successful':len(accepted),'expectedRejections':len(rejected),'unexpectedErrors':0,
            'allRequests':distribution([r['milliseconds'] for r in rows]),
            'successfulRequests':distribution(accepted) if accepted else None,
            'expectedRejectionsOnly':distribution(rejected) if rejected else None,
            'elapsedSeconds':elapsed,'requestsPerSecond':len(rows)/elapsed,
            'interpretation':'EMPIRICAL_BOUNDED_CLIENT_LATENCY; NOT_A_PRODUCTION_SLO'}


def process(pid):
    root=Path('/proc')/str(pid)
    try:
        raw=(root/'stat').read_text();fields=raw[raw.rfind(')')+2:].split()
        return {'pid':pid,'startTicks':int(fields[19]),'cpuSeconds':(int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK'),
                'rssBytes':int(fields[21])*os.sysconf('SC_PAGE_SIZE'),'threads':int(fields[17]),'openFDs':len(list((root/'fd').iterdir()))}
    except FileNotFoundError:return {'pid':pid,'exited':True}


class Sampler:
    def __init__(self,lab,session,interval):
        self.lab,self.session,self.interval=lab,session,interval;self.rows=[];self.errors=[];self.stop=threading.Event()
    def collect(self):
        while not self.stop.is_set():
            try:
                pg=self.lab.db.data("SELECT json_build_object('connections',count(*),'activeTransactions',count(*) FILTER(WHERE xact_start IS NOT NULL),'lockWaiters',count(*) FILTER(WHERE wait_event_type='Lock')) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()")
                pg['queue']=self.lab.db.data("SELECT json_build_object('pending',count(*) FILTER(WHERE state IN ('PENDING','RETRY')),'running',count(*) FILTER(WHERE state='RUNNING'),'terminal',count(*) FILTER(WHERE state IN ('COMPLETED','FAILED'))) FROM "+PREFIX+"_queue")
                with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(self.session.backend_port)+'/__test/h3-resources',headers={'Authorization':'Bearer browser-authorized'}),timeout=3) as response:pool=json.load(response)
                self.rows.append({'monotonic':time.monotonic(),'process':process(self.session.process.pid),'postgres':pg,'application':pool})
            except Exception as error:self.errors.append(type(error).__name__+':'+str(error))
            self.stop.wait(self.interval)
    def __enter__(self):
        self.thread=threading.Thread(target=self.collect,daemon=True);self.thread.start();return self
    def __exit__(self,*args):
        self.stop.set();self.thread.join(timeout=8);require(not self.thread.is_alive(),'H3_SAMPLER_LEAK')
    def result(self):
        require(self.rows and not self.errors,'H3_RESOURCE_SAMPLING_FAILED:'+str(self.errors[:2]))
        first,last=self.rows[0]['process'],self.rows[-1]['process'];elapsed=self.rows[-1]['monotonic']-self.rows[0]['monotonic']
        require(all(r['process'].get('startTicks')==first['startTicks'] for r in self.rows),'H3_PROCESS_IDENTITY_CHANGED')
        cpu=(last['cpuSeconds']-first['cpuSeconds'])/elapsed*100 if elapsed>0 else None
        return {'samples':self.rows,'maxRSSBytes':max(r['process']['rssBytes'] for r in self.rows),
                'processCPUPercentOfOneCore':cpu,'cpuInterpretation':'PROC_STAT_DELTA; MAY_EXCEED_100_ON_MULTICORE; SHARED_HOST',
                'maxConnections':max(r['postgres']['connections'] for r in self.rows),
                'maxActiveTransactions':max(r['postgres']['activeTransactions'] for r in self.rows),
                'maxPoolWaiters':max(r['application']['waiting'] for r in self.rows),
                'maxPendingQueue':max(r['postgres']['queue']['pending'] for r in self.rows),'maxRunningQueue':max(r['postgres']['queue']['running'] for r in self.rows),'samplerExcludedFromPostgresCounts':True}
