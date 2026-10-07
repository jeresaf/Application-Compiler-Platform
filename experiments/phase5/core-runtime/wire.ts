/** Versioned representative Phase 4 slice; independent of Canonical Application. */
import {createHash} from 'node:crypto';
import {createInterface} from 'node:readline';
import {performance} from 'node:perf_hooks';
function canonical(v:any):string {if(v===null||typeof v!=='object')return JSON.stringify(v);if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';}
function freeze(v:any):any {if(v&&typeof v==='object'){Object.values(v).forEach(freeze);Object.freeze(v);}return v;}
type Request=Readonly<{protocol:string,id:string,canonicalInput:string,provenance:readonly unknown[],obligations:readonly unknown[],dependencies:Readonly<Record<string,readonly string[]>>,budget:number,cancelled:boolean,portVersion:string}>;
function execute(request:Request):any {
 const r=freeze(JSON.parse(JSON.stringify(request))) as Request;
 const visited:string[]=[],pending=['ROOT'];let code='';
 if(r.protocol!=='acp-core-wire/1')code='VERSION';
 else if(r.portVersion!=='graph/1')code='PORT';
 else if(canonical(JSON.parse(r.canonicalInput))!==r.canonicalInput)code='CANONICAL';
 while(!code&&pending.length){const id=pending.shift()!;if(r.cancelled){code='CANCELLED';break;}if(visited.includes(id))continue;if(visited.length>=r.budget){code='RESOURCE';break;}visited.push(id);pending.push(...(r.dependencies[id]??[]));}
 const hash=createHash('sha256').update('ACP\0acp-jcs-safe-v1\0canonical\0').update(canonical(JSON.parse(r.canonicalInput))).digest('hex');
 return freeze({protocol:'acp-core-wire/1',id:r.id,status:code?'FAILURE':'SUCCESS',diagnostics:code?[{code,subject:'ROOT',primary:'graph.acp#L1C1',related:[],remediation:'Repair the declared request or retry with valid authority and budgets.'}]:[],digest:'sha256:'+hash,provenance:r.provenance,obligations:r.obligations,visited,work:visited.length});
}
const lines=createInterface({input:process.stdin});
for await(const line of lines){const start=performance.now();const request=JSON.parse(line);const parsed=performance.now();const output=execute(request);const encoded=JSON.stringify(output);process.stdout.write(encoded+'\n');if(process.env.ACP_WIRE_METRICS)process.stderr.write(JSON.stringify({decodeMs:parsed-start,executeEncodeMs:performance.now()-parsed,inputBytes:Buffer.byteLength(line),outputBytes:Buffer.byteLength(encoded)})+'\n');}
