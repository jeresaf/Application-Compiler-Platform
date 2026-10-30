import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
const [rootArg,moduleArg,depsArg,listArg]=process.argv.slice(2);
const root=path.resolve(rootArg),deps=path.resolve(depsArg),ts=(await import(pathToFileURL(path.resolve(moduleArg)).href)).default;
const names=JSON.parse(fs.readFileSync(listArg,'utf8'));
const virtual=path.join(root,'frontend/node_modules');
const physical=p=>p===virtual||p.startsWith(virtual+path.sep)?deps+p.slice(virtual.length):p;
const normalize=p=>p.replaceAll(virtual,'<DEPENDENCIES>').replaceAll(deps,'<DEPENDENCIES>').replaceAll(root,'<ROOT>');
const logical=p=>p.startsWith(virtual+path.sep)?normalize(p):p.startsWith(root+path.sep)?path.relative(root,p).replaceAll('\\','/'):normalize(p);
const configPath=path.join(root,'frontend/tsconfig.json');
const raw=fs.existsSync(configPath)?ts.readConfigFile(configPath,ts.sys.readFile):{config:{compilerOptions:{strict:true,target:'ES2022',module:'ESNext',moduleResolution:'Bundler'}}};
if(raw.error)throw Error('TSCONFIG_PARSE');
// Compiler options only: never execute tsconfig plugins or project build scripts.
const conversion=ts.convertCompilerOptionsFromJson(raw.config.compilerOptions??{},path.dirname(configPath));
const options={...conversion.options,noEmit:true,incremental:false,composite:false,plugins:[],typeRoots:[virtual+'/@types']};
const host=ts.createCompilerHost(options,true), read=host.readFile;
const sourcePaths=new Set(names.map(n=>path.join(root,n)));
const allowed=p=>p===deps||p.startsWith(deps+path.sep)||p===virtual||p.startsWith(virtual+path.sep)||sourcePaths.has(p)||p===path.join(root,'frontend/package.json');
host.readFile=p=>allowed(p)?read(physical(p)):undefined;host.fileExists=p=>allowed(p)&&ts.sys.fileExists(physical(p));host.directoryExists=p=>ts.sys.directoryExists(physical(p));
host.getDirectories=p=>ts.sys.getDirectories(physical(p));host.realpath=p=>p.startsWith(virtual)?p:ts.sys.realpath(p);
const program=ts.createProgram(names.map(n=>path.join(root,n)),options,host),checker=program.getTypeChecker();
const diagnostics=[...conversion.errors,...program.getSyntacticDiagnostics(),...program.getSemanticDiagnostics()].filter(d=>d.category===ts.DiagnosticCategory.Error).map(d=>({code:String(d.code),file:d.file?logical(d.file.fileName):'',start:d.start??0,end:(d.start??0)+(d.length??0),message:normalize(ts.flattenDiagnosticMessageText(d.messageText,' '))}));
for(const key of ['extends','references'])if(raw.config[key])diagnostics.push({code:'UNSUPPORTED_TSCONFIG',file:'frontend/tsconfig.json',start:0,end:0,message:'Unsupported configuration: '+key});
if(raw.config.compilerOptions?.plugins?.length)diagnostics.push({code:'UNSUPPORTED_TSCONFIG',file:'frontend/tsconfig.json',start:0,end:0,message:'Compiler plugins are not executed.'});
const definitions=[],references=[],relations=[],literals=[],byNode=new Map(),primary=new Map();
const ownFiles=new Set(names),units=program.getSourceFiles().filter(f=>ownFiles.has(logical(f.fileName)));
const resolved=s=>s&&(s.flags&ts.SymbolFlags.Alias)?checker.getAliasedSymbol(s):s;
const native=s=>s?normalize(checker.getFullyQualifiedName(s)):null;
const location=n=>({file:logical(n.getSourceFile().fileName),start:n.getStart(),end:n.end});
const bad=n=>{const l=location(n);return diagnostics.some(d=>d.file===l.file&&d.start<l.end&&d.end>=l.start);};
const symbol=n=>{try{return checker.getSymbolAtLocation(n);}catch{return undefined;}};
const definitionKinds=new Map([[ts.SyntaxKind.ClassDeclaration,'CLASS'],[ts.SyntaxKind.InterfaceDeclaration,'INTERFACE'],[ts.SyntaxKind.FunctionDeclaration,'FUNCTION'],[ts.SyntaxKind.MethodDeclaration,'METHOD'],[ts.SyntaxKind.MethodSignature,'METHOD'],[ts.SyntaxKind.Constructor,'CONSTRUCTOR'],[ts.SyntaxKind.VariableDeclaration,'VARIABLE'],[ts.SyntaxKind.PropertyDeclaration,'PROPERTY'],[ts.SyntaxKind.PropertySignature,'PROPERTY'],[ts.SyntaxKind.PropertyAssignment,'PROPERTY'],[ts.SyntaxKind.Parameter,'PARAMETER'],[ts.SyntaxKind.TypeAliasDeclaration,'TYPE_ALIAS'],[ts.SyntaxKind.TypeParameter,'TYPE_PARAMETER'],[ts.SyntaxKind.EnumDeclaration,'ENUM'],[ts.SyntaxKind.EnumMember,'ENUM_MEMBER'],[ts.SyntaxKind.ImportSpecifier,'IMPORT_ALIAS'],[ts.SyntaxKind.ImportClause,'IMPORT'],[ts.SyntaxKind.NamespaceImport,'IMPORT_ALIAS'],[ts.SyntaxKind.ModuleDeclaration,'MODULE']]);
function declare(n){const kind=definitionKinds.get(n.kind);if(!kind)return;const s=n.name?symbol(n.name):n.kind===ts.SyntaxKind.Constructor?symbol(n.parent.name):symbol(n);if(!s)return;const l=location(n),key=l.file+':'+l.start+':'+(native(s)??kind), name=n.name?.getText()??'constructor';
 const sig=ts.isFunctionLike(n)?checker.getSignatureFromDeclaration(n):null;
 const row={key,kind,name,native:native(s),exported:(ts.getModifiers(n)??[]).some(m=>m.kind===ts.SyntaxKind.ExportKeyword),...l,nameStart:n.name?.getStart()??null,nameEnd:n.name?.end??null,type:normalize(sig?checker.signatureToString(sig):checker.typeToString(checker.getTypeAtLocation(n))),container:null,confidence:bad(n)?'UNKNOWN':'KNOWN'};
 definitions.push(row);byNode.set(n,row);if(!primary.has(s))primary.set(s,row);
 if(n.initializer && ts.isStringLiteral(n.initializer))literals.push({symbol:key,value:n.initializer.text,revision:null,...location(n.initializer),basis:'NATIVE_STRING_INITIALIZER'});
}
for(const unit of units){const moduleRow={key:'module:'+logical(unit.fileName),kind:'MODULE',name:logical(unit.fileName),native:logical(unit.fileName),file:logical(unit.fileName),start:0,end:unit.end,type:'',container:null,confidence:'KNOWN'};definitions.push(moduleRow);byNode.set(unit,moduleRow);const moduleSymbol=symbol(unit);if(moduleSymbol)primary.set(moduleSymbol,moduleRow);function walk(n){declare(n);ts.forEachChild(n,walk);}walk(unit);}
function owner(n){for(let p=n.parent;p;p=p.parent)if(byNode.has(p))return byNode.get(p).key;return 'module:'+logical(n.getSourceFile().fileName);}
for(const [node,row] of byNode)if(!ts.isSourceFile(node))row.container=owner(node);
function binding(s,decl){s=resolved(s);if(!s||!s.declarations?.length)return null;if(decl&&byNode.has(decl))return byNode.get(decl).key;const d=primary.get(s)??s.declarations.map(x=>byNode.get(x)).find(Boolean);if(d)return d.key;if(s.declarations.some(x=>ownFiles.has(logical(x.getSourceFile().fileName))))return null;return 'external:'+native(s);}
function edge(n,kind,s,decl){s=resolved(s);const dest=binding(s,decl),known=dest!==null&&!bad(n);const row={kind,...location(n),from:owner(n),to:known?dest:null,native:known?native(s):null,confidence:known?'KNOWN':'UNRESOLVED'};(kind==='EXTENDS'||kind==='IMPLEMENTS'||kind==='TYPE_USES'?relations:references).push(row);}
for(const unit of units){function walk(n){
 if(ts.isIdentifier(n) && !(n.parent.name===n && byNode.has(n.parent)))edge(n,'REFERENCE',symbol(n));
 if(ts.isCallExpression(n)||ts.isNewExpression(n)){const sig=checker.getResolvedSignature(n),decl=sig?.declaration;edge(n,ts.isNewExpression(n)?'CONSTRUCT':'CALL',decl?.name?symbol(decl.name):symbol(n.expression),decl);}
 if(ts.isTypeReferenceNode(n))edge(n,'TYPE_USES',symbol(n.typeName));
 if(ts.isExpressionWithTypeArguments(n)&&ts.isHeritageClause(n.parent))edge(n,n.parent.token===ts.SyntaxKind.ImplementsKeyword?'IMPLEMENTS':'EXTENDS',symbol(n.expression));
 if(ts.isImportSpecifier(n)||ts.isNamespaceImport(n)||ts.isImportClause(n))edge(n,'IMPORT',n.name?symbol(n.name):null);
 if(ts.isExportSpecifier(n))edge(n,'EXPORT',symbol(n.name));
 if(ts.isObjectLiteralExpression(n)){
  const props=new Map(n.properties.filter(ts.isPropertyAssignment).map(p=>[p.name.getText().replaceAll('"','').replaceAll("'",''),p]));
  const id=props.get('id'),rev=props.get('revision');
  if(id&&ts.isStringLiteral(id.initializer)&&rev&&ts.isNumericLiteral(rev.initializer)){
   let d=n;while(d&&!byNode.has(d))d=d.parent;const row=d&&byNode.get(d);
   if(row)literals.push({symbol:row.key,value:id.initializer.text,revision:Number(rev.initializer.text),...location(id.initializer),basis:'NATIVE_ID_REVISION_OBJECT'});
  }
 }
 ts.forEachChild(n,walk);
}walk(unit);}
const inputs=program.getSourceFiles().filter(f=>!ownFiles.has(logical(f.fileName))).map(f=>({path:logical(f.fileName),sha256:crypto.createHash('sha256').update(fs.readFileSync(physical(f.fileName))).digest('hex')})).sort((a,b)=>a.path.localeCompare(b.path,'en'));
console.log(JSON.stringify({protocol:'acp-source-native/1',language:'TYPESCRIPT',toolVersion:ts.version,definitions,references,relations,literals,diagnostics,inputs}));
