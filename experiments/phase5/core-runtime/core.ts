import {performance} from 'node:perf_hooks';
import assert from 'node:assert/strict';
import {Worker, isMainThread, parentPort, workerData} from 'node:worker_threads';
type Subject = Readonly<{id:string, revision:number}>;
type Diagnostic = Readonly<{code:string, subject:Subject, locator:string}>;
type Result = Readonly<{tag:'success', visited:readonly Subject[]}> | Readonly<{tag:'failure', diagnostic:Diagnostic}>;
interface GraphPort {successors(subject:Subject):readonly Subject[];}
function traverse(root:Subject, port:GraphPort, budget:number, cancelled:()=>boolean):Result {
 const pending=[root], seen=new Map<string,Subject>();
 for(let cursor=0;cursor<pending.length;cursor++) {
  const next=pending[cursor];
  const fail=(code:string):Result=>Object.freeze({tag:'failure',diagnostic:Object.freeze({code,subject:next,locator:`corpus/graph#${next.id}`})});
  if(cancelled())return fail('CANCELLED');
  const key=`${next.id}@${next.revision}`;
  if(seen.has(key))continue;
  if(seen.size>=budget)return fail('WORK_LIMIT');
  seen.set(key,next);pending.push(...port.successors(next));
 }return Object.freeze({tag:'success',visited:Object.freeze([...seen.values()])});
}
const count=Number(isMainThread ? process.argv[2] : workerData.count);
const port:GraphPort={successors:s=>Number(s.id)+1<count?[Object.freeze({id:String(Number(s.id)+1),revision:1})]:[]};
const root=Object.freeze({id:'0',revision:1}), graphMs=[];
for(let i=0;i<8;i++){const start=performance.now();const r=traverse(root,port,count,()=>false);assert(r.tag==='success'&&r.visited.length===count);graphMs.push(performance.now()-start);}
assert.equal(traverse(root,port,0,()=>false).tag,'failure');assert.equal(traverse(root,port,count,()=>true).tag,'failure');
if (!isMainThread) parentPort!.postMessage({visited:count});
else {
 const concurrentStart=performance.now();
 await Promise.all(Array.from({length:8},()=>new Promise<void>((resolve,reject)=>{
  const worker=new Worker(new URL(import.meta.url),{workerData:{count}});
  let received=false;
  worker.on('message',value=>{assert.equal(value.visited,count);received=true;});
  worker.on('error',reject);
  worker.on('exit',code=>code===0&&received?resolve():reject(new Error('Worker failed')));
 })));
 console.log(JSON.stringify({candidate:'TypeScript 5.9.3 / Node 24.21.0',nodes:count,graphMs,cancellation:true,workLimit:true,concurrentRuns:8,concurrentElapsedMs:performance.now()-concurrentStart,canonical:'Existing independent Node checker; no new candidate encoder'}));
}
