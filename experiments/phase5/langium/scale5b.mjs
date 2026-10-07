import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {performance} from 'node:perf_hooks';
import {URI} from 'langium';
import {NodeFileSystem} from 'langium/node';
import {createServices} from './services.mjs';
const input=fs.readFileSync(process.argv[2],'utf8').trimEnd().split('\n');
const services=createServices(NodeFileSystem),tmp=fs.mkdtempSync(path.join(os.tmpdir(),'acp-scale-'));
try {
 const middle=Math.floor(input.length/2),texts=[[input[0],...input.slice(1,middle)].join('\n'),[input[0],...input.slice(middle)].join('\n')];
 const files=texts.map((text,i)=>{const file=path.join(tmp,`module-${i}.acp`);fs.writeFileSync(file,text);return file;});
 let start=performance.now();
 const documents=files.map((f,i)=>services.shared.workspace.LangiumDocumentFactory.fromString(texts[i],URI.file(f)));
 for(const d of documents)services.shared.workspace.LangiumDocuments.addDocument(d);
 const initialParseMs=performance.now()-start;
 start=performance.now();await services.shared.workspace.DocumentBuilder.build(documents,{validation:true});const initialNativeValidationMs=performance.now()-start;
 const measure=async(file,text)=>{fs.writeFileSync(file,text);const start=performance.now();await services.shared.workspace.DocumentBuilder.update([URI.file(file)],[]);return performance.now()-start;};
 const localEditMs=await measure(files[0],texts[0]+'\n');
 const dependentCrossFileEditMs=await measure(files[1],texts[1]+'\n');
 const before=documents.flatMap(d=>d.parseResult.value.declarations.map(n=>n.name));
 const renamed=texts[0].replace('"name":"DEC-ROOT"','"name":"Decision display label"');
 const labelRenameMs=await measure(files[0],renamed);
 const after=documents.flatMap(d=>d.parseResult.value.declarations.map(n=>n.name));
 if(JSON.stringify(before)!==JSON.stringify(after))throw Error('Stable identity changed');
 start=performance.now();const diagnostics=documents.flatMap(d=>d.diagnostics??[]);const diagnosticRefreshReadMs=performance.now()-start;
 console.log(JSON.stringify({initialParseMs,initialNativeValidationMs,localEditMs,dependentCrossFileEditMs,labelRenameMs,stableIdsPreserved:true,diagnosticRefreshReadMs,nativeDiagnosticCount:diagnostics.length,peakRssBytes:process.resourceUsage().maxRSS*1024,referenceUpdate:'Measured by shared ACP rename adapter; native references use stable IDs',incrementalSemanticValidation:'NOT_SUPPORTED: native linking/validation is not ACP Phase 4 semantic validation',scope:'Native document-builder invalidation/rebuild; parser may fully reparse changed documents. ACP module policy is independently enforced by host.'}));
} finally {fs.rmSync(tmp,{recursive:true,force:true});}
