import fs from 'node:fs';
import path from 'node:path';
import {performance} from 'node:perf_hooks';
const ts=(await import(process.env.ACP_TS_MODULE ?? 'typescript')).default;
import {Parser, Language} from 'web-tree-sitter';
const area=path.resolve(import.meta.dirname,'../source-analysis');
const files=['generated.ts','extension.ts'].map(f=>path.join(area,f));
const start=performance.now();
const program=ts.createProgram(files,{strict:true,noEmit:true,target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.NodeNext,moduleResolution:ts.ModuleResolutionKind.NodeNext});
const checker=program.getTypeChecker();
const native=[];
for(const file of files){const source=program.getSourceFile(file); const visit=node=>{
 if(ts.isCallExpression(node)) {const signature=checker.getResolvedSignature(node);const symbol=checker.getSymbolAtLocation(node.expression);native.push({file:path.basename(file),text:node.expression.getText(),status:symbol&&signature?.declaration?'KNOWN':'UNRESOLVED',signature:signature?.declaration?.getText(),span:{start:node.getStart(),end:node.end}});}
 ts.forEachChild(node,visit);
};visit(source);}
const nativeMs=performance.now()-start;
const diagnostics=ts.getPreEmitDiagnostics(program).map(d=>({code:d.code,file:d.file&&path.basename(d.file.fileName),start:d.start,message:ts.flattenDiagnosticMessageText(d.messageText,' ')}));
await Parser.init();const parser=new Parser();
let syntax, syntaxError;
try {
 parser.setLanguage(await Language.load(path.resolve(import.meta.dirname,'node_modules/tree-sitter-wasms/out/tree-sitter-typescript.wasm')));
 syntax=files.map(file=>{const start=performance.now();const tree=parser.parse(fs.readFileSync(file,'utf8'));return {file:path.basename(file),parseMs:performance.now()-start,hasError:tree.rootNode.hasError,calls:tree.rootNode.descendantsOfType('call_expression').map(n=>({text:n.text,status:'UNKNOWN',span:{start:n.startIndex,end:n.endIndex}}))};});
} catch(error){syntaxError=String(error);}
console.log(JSON.stringify({versions:{typescript:ts.version,webTreeSitter:'0.25.10',wasmBundle:'0.1.13'},nativeMs,native,diagnostics,syntax,syntaxError,combined:native.map(n=>({...n,syntaxMatched:syntax?.some(f=>f.file===n.file&&f.calls.some(c=>c.span.start===n.span.start))??false})),absent:{feature:'decorators',status:'ABSENT',basis:'No decorator syntax in either complete fixture'}}));
