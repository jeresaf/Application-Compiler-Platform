"""Bounded observations of the unsealed candidate; never production SLOs."""
import hashlib
import json
import math
import statistics


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def summarize(samples, *, elapsed_ms=None, failures=0):
    if not samples or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in samples):
        raise ValueError('INVALID_MEASUREMENT')
    if type(failures) is not int or failures < 0:
        raise ValueError('INVALID_FAILURE_COUNT')
    ordered = sorted(samples)
    result = {'samples': samples, 'count': len(samples), 'failures': failures,
              'minimumMs': min(samples), 'maximumMs': max(samples),
              'meanMs': statistics.mean(samples), 'sampleStddevMs': statistics.stdev(samples) if len(samples) > 1 else None,
              'p50Ms': statistics.median(samples), 'percentileMethod': 'nearest rank; at least 100 observations per tail observation'}
    # Small samples do not establish tail percentiles. Even these are empirical,
    # not population confidence bounds or production acceptance thresholds.
    for name, q in (('p95Ms', .95), ('p99Ms', .99)):
        result[name] = ordered[math.ceil(q * len(ordered)) - 1] if len(ordered) * (1 - q) >= .999999 else None
    if elapsed_ms is not None:
        if not math.isfinite(elapsed_ms) or elapsed_ms <= 0:
            raise ValueError('INVALID_WALL_TIME')
        result.update(elapsedMs=elapsed_ms, throughputPerSecond=len(samples) * 1000 / elapsed_ms)
    return result


# Executed by real Playwright against generated production frontend + backend.
# Fixture reset and warmup are outside timing. No retry or latency pass threshold.
BROWSER = r'''import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import {ui} from '../src/task-ui-model';
const headers={Authorization:'Bearer browser-authorized'};
test('bounded real application performance',async({page,request,browser})=>{
 const results:any={browser:browser.version(),viewport:page.viewportSize(),pages:[],requests:[],query:[],action:[],concurrent:[],concurrentStatuses:{},concurrentSuccess:[],concurrentErrors:[],failures:0};
 const reset=async()=>expect((await request.post('/__test/reset',{headers})).status()).toBe(200);
 try {
 await reset();
 for(let i=0;i<10;i++){
  const started=performance.now();await page.goto('/');
  await expect(page.getByRole('button',{name:'Select fixture-resource',exact:true})).toBeVisible();
  results.pages.push(performance.now()-started);
 }
 const query=(worker?:number)=>request.post(ui.queryPath,{headers:worker===undefined?headers:{Authorization:'Bearer browser-perf-'+worker},data:{'QUERY-TEXT':''}});
 await reset();expect((await query()).status()).toBe(200);
 for(let i=0;i<100;i++){if(i%8===0)await reset();const start=performance.now();const r=await query();const duration=performance.now()-start;results.query.push(duration);results.requests.push({phase:"query",index:i,status:r.status(),durationMs:duration});expect(r.status()).toBe(200);}
 for(let i=0;i<20;i++){
  await reset();const start=performance.now();
  const r=await request.post(ui.actionPath,{headers,data:{expectedVersion:0,idempotencyKey:'perf-'+i,input:{[ui.resourceInputField]:'fixture-resource',[ui.textInputField]:'performance note'}}});
  const duration=performance.now()-start;results.action.push(duration);results.requests.push({phase:"action",index:i,status:r.status(),durationMs:duration});expect(r.status()).toBe(200);
  const facts=await (await request.get('/__test/facts',{headers})).json();expect(facts.events).toBe(EVENTS);
 }
 results.concurrentElapsedMs=0;
 for(let batch=0;batch<50;batch++){
  await reset();for(let worker=0;worker<4;worker++)expect((await query(worker)).status()).toBe(200);
  const start=performance.now();
  await Promise.all(Array.from({length:4},async(_,worker)=>{for(let i=0;i<1;i++){
   const begin=performance.now();const r=await query(worker);const duration=performance.now()-begin;results.concurrent.push(duration);results.requests.push({phase:"concurrent",batch,worker,index:i,status:r.status(),durationMs:duration});
   results.concurrentStatuses[r.status()]=(results.concurrentStatuses[r.status()]||0)+1;
   if(r.status()===200)results.concurrentSuccess.push(duration);else{results.failures++;results.concurrentErrors.push({status:r.status(),body:await r.text()});}
  }}));results.concurrentElapsedMs+=performance.now()-start;
 }results.concurrency=4;results.burstSize=4;
 await reset();for(let worker=0;worker<4;worker++)expect((await query(worker)).status()).toBe(200);
 results.overload={statuses:{},samples:[]};
 const overloadStart=performance.now();
 await Promise.all(Array.from({length:4},async(_,worker)=>{for(let i=0;i<50;i++){
  const begin=performance.now();const r=await query(worker);const duration=performance.now()-begin;results.overload.samples.push(duration);results.requests.push({phase:"overload",worker,index:i,status:r.status(),durationMs:duration});
  results.overload.statuses[r.status()]=(results.overload.statuses[r.status()]||0)+1;
  if(![200,429].includes(r.status()))(results.overload.errors??=[]).push({status:r.status(),body:await r.text()});
 }}));results.overload.elapsedMs=performance.now()-overloadStart;
 expect((await request.get('/__test/facts',{headers})).status()).toBe(200);
 expect(results.concurrentStatuses).toEqual({'200':200});expect(results.failures).toBe(0);
 for(const status of Object.keys(results.overload.statuses))expect([200,429]).toContain(Number(status));
 expect(results.overload.samples).toHaveLength(200);
 } finally {fs.writeFileSync('performance-'+test.info().project.name+'.json',JSON.stringify(results));}
});
'''
