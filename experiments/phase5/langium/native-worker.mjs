import {parseText} from './probe.mjs';
import {createHash} from 'node:crypto';
import fs from 'node:fs';
const LIMIT=1048576,protocol='acp-frontend-wire/1',frontend='acp-experiment-langium/4.4.0';
function canonical(v){if(v===null||typeof v!=='object')return JSON.stringify(v);if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';}
function hash(v){return createHash('sha256').update(canonical(v)).digest('hex');}
function clean(output){const result={};for(const key of ['candidate','module','imports','exports','model','spans','errors'])if(output[key]!==undefined)result[key]=output[key];result.errors=result.errors.map(({message,...safe})=>safe);return JSON.parse(JSON.stringify(result));}
if(process.argv[2]==='--embedded'){
 const text=fs.readFileSync(process.argv[3],'utf8'),times=[];let expected;
 for(let i=0;i<6;i++){const start=process.hrtime.bigint();const output=clean(await parseText(text));times.push(Number((process.hrtime.bigint()-start)/1000n));const digest=hash(output);if(expected&&digest!==expected)throw Error('Shared parser state');expected=digest;}
 console.log(JSON.stringify({directCallMicroseconds:times,semanticDigest:expected,pid:process.pid}));
}else{
 const seen=new Set();let pending=Buffer.alloc(0),sequence=0;
 for await(const chunk of process.stdin){pending=Buffer.concat([pending,chunk]);
  while(pending.includes(10)){
   const end=pending.indexOf(10);if(end>LIMIT)process.exit(2);const line=pending.subarray(0,end);pending=pending.subarray(end+1);let request={},payload,status='SUCCESS';const start=process.hrtime.bigint();
   try{
    request=JSON.parse(line);if(canonical(request)!==line.toString("utf8"))throw Error("MALFORMED_REQUEST");if(!request||Array.isArray(request)||Object.keys(request).sort().join(',')!=='frontend,id,protocol,source')throw Error('MALFORMED_REQUEST');
    if(request.protocol!==protocol)throw Error('PROTOCOL_VERSION');if(request.frontend!==frontend)throw Error('FRONTEND_VERSION');
    if(typeof request.id!=='string'||!request.id||request.id.length>128)throw Error('REQUEST_ID');if(seen.has(request.id))throw Error('DUPLICATE_ID');seen.add(request.id);if(seen.size>1024)throw Error('SESSION_LIMIT');
    const source=request.source;if(source.version!=='acp-text/1'||source.frontend!==frontend)throw Error('FRONTEND_VERSION');if(!Array.isArray(source.documents)||!source.documents.length||source.documents.length>128)throw Error('MALFORMED_REQUEST');
    const documents=[];for(const doc of source.documents)documents.push({path:doc.path,output:clean(await parseText(doc.text))});
    payload={documents,metrics:{pid:process.pid,sequence:++sequence,nativeRequestMicroseconds:Number((process.hrtime.bigint()-start)/1000n),heapUsedBytes:process.memoryUsage().heapUsed}};
   }catch(error){status='FAILURE';payload={code:['MALFORMED_REQUEST','PROTOCOL_VERSION','FRONTEND_VERSION','REQUEST_ID','DUPLICATE_ID','SESSION_LIMIT'].includes(error.message)?error.message:'FRONTEND_FAILURE'};if(!request||typeof request!=='object')request={};}
   const response={protocol,frontend,id:request.id??null,requestDigest:hash(request),status,payload};let encoded=canonical(response);if(Buffer.byteLength(encoded)+1>LIMIT){response.status='FAILURE';response.payload={code:'RESPONSE_SIZE'};encoded=canonical(response);}process.stdout.write(encoded+'\n');
  }
  if(pending.length>LIMIT)process.exit(2);
 }
}
