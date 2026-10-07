import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import { performance } from 'node:perf_hooks';
import { createServices } from './services.mjs';
import { URI } from 'langium';

const started = performance.now();
const services = createServices();
// Force lazy parser construction into the explicit startup measurement.
void services.parser.LangiumParser;
const startupMs = performance.now() - started;
function plain(node) {
    switch (node.$type) {
        case 'RecordValue': {
            const result = {};
            for (const pair of node.pairs) {
                if (Object.hasOwn(result, pair.key)) throw Error('Duplicate object key');
                Object.defineProperty(result, pair.key, {value: plain(pair.value), enumerable: true});
            }
            return result;
        }
        case 'ListValue': return node.values.map(plain);
        case 'Text': return node.value;
        case 'IntegerValue': if (!Number.isSafeInteger(node.value)) throw Error('Unsafe integer'); return node.value;
        case 'BooleanValue': return node.value === 'true';
        case 'Null': return null;
        case 'Reference': return {id: node.target.$refText, revision: node.revision};
        case 'Money': return {kind:'Money', currency:node.currency, precision:node.precision, scale:node.scale, rounding:node.rounding};
        default: throw Error(`Unsupported AST ${node.$type}`);
    }
}
export async function parseText(text,runs=1,filename='native.acp'){
const measurements = [];
let parsed;
for (let i=0;i<runs;i++) {
    const start = performance.now();
    parsed = services.parser.LangiumParser.parse(text);
    measurements.push(performance.now()-start);
}
const errors = [...parsed.lexerErrors, ...parsed.parserErrors].map(e => {
    // Chevrotain's EOF token has no start position. EOF is an explicit parser
    // token, so its location is the end of this document, not a file fallback.
    if(e.token?.tokenType?.name==='EOF')return {message:e.message,line:text.split('\n').length,column:text.split('\n').at(-1).length+1};
    return {message:e.message,line:e.token?.startLine??e.line,column:e.token?.startColumn??e.column};
});
let model;
if (!errors.length && process.env.ACP_PARSE_ONLY !== '1') model = {...plain(parsed.value.header), nodes:parsed.value.declarations.map(d => {
    const body=plain(d.body);
    if (['kind','id','revision'].some(k=>Object.hasOwn(body,k))) throw Error('Reserved declaration identity in body');
    return {kind:d.kind, id:d.name, revision:d.revision, ...body};
})};
const spans = process.env.ACP_PARSE_ONLY === '1' ? [] : parsed.value.declarations.map(d => ({id:d.name, range:d.$cstNode?.range}));
let nativeServices;
if (process.env.ACP_EDITOR === '1') {
    const doc = services.shared.workspace.LangiumDocumentFactory.fromString(text, URI.file(filename));
    services.shared.workspace.LangiumDocuments.addDocument(doc);
    const start = performance.now();
    await services.shared.workspace.DocumentBuilder.build([doc], {validation:true});
    const validationMs = performance.now()-start;
    const position = doc.textDocument.positionAt(text.indexOf('ref ') + 6);
    const params = {textDocument:{uri:doc.uri.toString()}, position};
    const completionStart = performance.now();
    const completions = await services.lsp.CompletionProvider.getCompletion(doc, params);
    const completionMs = performance.now()-completionStart;
    const definition = await services.lsp.DefinitionProvider.getDefinition(doc, params);
    const references = await services.lsp.ReferencesProvider.findReferences(doc, {...params, context:{includeDeclaration:true}});
    const rename = await services.lsp.RenameProvider.rename(doc, {...params, newName:'RENAMED-STABLE-ID'});
    nativeServices = {validationMs, completionMs, diagnostics:doc.diagnostics, completionItems:completions?.items.length, definition, referenceCount:references.length, rename};
}
return {module:parsed.value.module, imports:parsed.value.imports, exports:parsed.value.declarations.filter(d=>d.exported).map(d=>d.name), candidate:'Langium 4.4.0', startupMs, parseMs:measurements, peakRssBytes:process.resourceUsage().maxRSS*1024, errors, model, spans, nativeServices};
}
if(process.argv[1]===fileURLToPath(import.meta.url))console.log(JSON.stringify(await parseText(fs.readFileSync(process.argv[2],'utf8'),Number(process.argv[3]??1),process.argv[2])));
