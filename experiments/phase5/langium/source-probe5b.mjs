import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
const area=process.env.ACP_SOURCE_AREA ?? path.resolve(import.meta.dirname,'../source-analysis');
const files=['generated.ts','extension.ts'].map(f=>path.join(area,f));
const program=ts.createProgram(files,{strict:true,noEmit:true,target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.NodeNext,moduleResolution:ts.ModuleResolutionKind.NodeNext});
const checker=program.getTypeChecker(),evidence=[];
for(const file of files){const source=program.getSourceFile(file);function visit(node){
 if(ts.isImportDeclaration(node))evidence.push({kind:'import',status:checker.getSymbolAtLocation(node.moduleSpecifier)?'KNOWN':'UNRESOLVED',file:path.basename(file),module:node.moduleSpecifier.text});
 if(ts.isImportSpecifier(node)){const symbol=checker.getSymbolAtLocation(node.name),target=symbol&&checker.getAliasedSymbol(symbol);evidence.push({kind:'alias',name:node.name.text,status:target?.declarations?.length?'KNOWN':'UNRESOLVED',target:target?.name});}
 if(ts.isClassDeclaration(node)||ts.isInterfaceDeclaration(node))evidence.push({kind:ts.isClassDeclaration(node)?'class':'interface',name:node.name?.text,status:checker.getSymbolAtLocation(node.name)?'KNOWN':'UNRESOLVED',heritage:node.heritageClauses?.map(c=>c.getText())??[]});
 if(ts.isCallExpression(node)){const symbol=checker.getSymbolAtLocation(node.expression),signature=checker.getResolvedSignature(node);evidence.push({kind:'call',name:node.expression.getText(),status:symbol&&signature?.declaration?'KNOWN':'UNRESOLVED',binding:signature?.declaration?.getText(),start:node.getStart(),end:node.end});}
 ts.forEachChild(node,visit);
 }visit(source);}
console.log(JSON.stringify({analyzer:'TypeScript '+ts.version,evidence,absent:{decorators:'ABSENT'},syntaxOnlyResolution:'UNKNOWN',ownership:'Exact marker extraction and rename continuity checked by host source5b.py'}));
