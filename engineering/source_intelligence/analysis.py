"""Join native facts to a separately pinned, original compiler/store baseline."""
from pathlib import Path
import json,sys,tempfile
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.source_intelligence.model import *
from engineering.source_intelligence import native
from compiler_contracts import fingerprint,wire,Owner
from filesystem_artifacts import FilesystemArtifactStore
from engineering.demo.pipeline import inputs
from engineering.generator_candidates.spring_vue_postgres_0_6.provenance import read_provenance
from deterministic_approval import approved_snapshot

BINDING='acp-source-baseline/1'

def prepare(workspace,domain):
    workspace=Path(workspace).absolute();workspace.mkdir(mode=0o700,exist_ok=False)
    candidate,snapshot,request,plan=inputs(domain);project=workspace/domain;store=FilesystemArtifactStore(project);store.apply(plan)
    store.adopt_human('frontend/src/extensions/identity.ts')
    plan=candidate.plan(snapshot,request,inventory=store.inventory());store.apply(plan)
    candidate.verify_materialized(project,plan,snapshot,request)
    document=read_provenance(project/'acp/provenance.json');maps={m['artifact']:m for m in document['artifacts']}
    files={row.path:{'sha256':sha((project/row.path).read_bytes()),'owner':str(row.owner),'contentDigest':row.digest,'origins':maps.get(row.path,{}).get('origins',[]),'historicalConfidence':maps.get(row.path,{}).get('locationConfidence','ABSENT')} for row in store.inventory()}
    baseline={'schema':BINDING,'scope':'ANALYSIS_BASELINE_NOT_AUTHORITY','domain':domain,'canonicalDigest':snapshot.read()['contentDigest'],'generator':candidate.generator,'compiler':request.compiler,'pipeline':request.pipeline,'artifactPlanDigest':fingerprint(plan),'files':files,'provenanceSHA256':sha((project/'acp/provenance.json').read_bytes()),'compilerExecutions':candidate.executions}
    destination=workspace/'source-baseline.json';destination.write_bytes(encode(baseline));pin=sha(destination.read_bytes());(workspace/'source-baseline.sha256').write_text(pin+'\n')
    return {'application':str(project),'binding':str(destination),'bindingSHA256':pin,'scope':'ANALYSIS_ONLY'}

def binding(path,pin):
    raw=Path(path).read_bytes();require(sha(raw)==pin,'BASELINE_DIGEST')
    b=json.loads(raw);require(set(b)=={'schema','scope','domain','canonicalDigest','generator','compiler','pipeline','artifactPlanDigest','files','provenanceSHA256','compilerExecutions'} and b['schema']==BINDING and b['scope']=='ANALYSIS_BASELINE_NOT_AUTHORITY','BASELINE_SCHEMA')
    from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
    from compiler_contracts import COMPILER,PIPELINE
    require(b['generator']==SuccessorCandidate().generator and b['compiler']==COMPILER and b['pipeline']==PIPELINE,'BASELINE_TOOL_IDENTITY')
    snapshot=approved_snapshot(b['domain']);require(b['canonicalDigest']==snapshot['contentDigest'],'BASELINE_CANONICAL_IDENTITY')
    revisions={n['id']:n['revision'] for n in snapshot['content']['nodes']}
    for name,f in b['files'].items():
        safe(name);require(set(f)=={'sha256','owner','contentDigest','origins','historicalConfidence'} and f['owner'] in OWNERS,'BASELINE_OWNERSHIP')
        for o in f['origins']:require(set(o)=={'id','revision'} and revisions.get(o['id'])==o['revision'],'FORGED_SEMANTIC_MAPPING')
    return b,revisions

def analyze(root,baseline,pin,*,maven_repo,node_modules,scratch=None):
    root=Path(root).absolute();node_modules=Path(node_modules).absolute();b,revisions=binding(baseline,pin)
    require(not Path(baseline).resolve().is_relative_to(root.resolve()),'BASELINE_MUST_BE_SEPARATE')
    if scratch is not None:require(not Path(scratch).resolve().is_relative_to(root.resolve()),'READ_ONLY_ANALYSIS_SCRATCH')
    before=sources(root);drift=[];expected=b['files'];metadata=json.loads(read(root,'.acp-store.json'))
    def finding(code,path,severity='ERROR'):drift.append({'code':code,'file':path,'severity':severity,'semanticChange':'UNKNOWN'})
    observed={};invalid_ownership=set()
    for name,f in expected.items():
        try:actual=sha(read(root,name));observed[name]=actual
        except FileNotFoundError:observed[name]=None;finding('MISSING_GENERATED_FILE',name);continue
        if actual!=f['sha256']:finding('HUMAN_EXTENSION_CHANGED' if f['owner']=='HUMAN_OWNED' else 'MODIFIED_GENERATED_FILE',name,'INFO' if f['owner']=='HUMAN_OWNED' else 'ERROR')
        owner=metadata.get(name,{}).get('owner')
        record=metadata.get(name,{})
        if record.get('digest')!=f['contentDigest'] or record.get('bytes')!='sha256:'+f['sha256']:
            invalid_ownership.add(name);finding('OWNERSHIP_RECORD_CONFLICT',name)
        if owner is None:finding('MISSING_OWNERSHIP',name)
        elif owner!=f['owner']:finding('OWNERSHIP_CONFLICT',name)
    for name in before:
        if name not in expected:finding('UNEXPECTED_SOURCE',name)
    prov_ok='acp/provenance.json' in expected and (root/'acp/provenance.json').is_file() and sha(read(root,'acp/provenance.json'))==b['provenanceSHA256']
    if not prov_ok:finding('STALE_OR_FORGED_PROVENANCE','acp/provenance.json')
    outputs=[]
    with tempfile.TemporaryDirectory(prefix='acp-source-native-',dir=scratch) as temp:
        temp=Path(temp)
        java_files=[n for n in before if n.endswith('.java')];ts_files=[n for n in before if n.endswith(('.ts','.tsx'))]
        if java_files:outputs.append(native.java(root,java_files,native.classpath(Path(maven_repo),b['domain']),temp))
        if ts_files:outputs.append(native.typescript(root,ts_files,node_modules,temp))
    require(observed=={n:sha(read(root,n)) if (root/n).is_file() else None for n in expected},'AUXILIARY_INPUT_CHANGED')
    require(before==sources(root) and sha(Path(baseline).read_bytes())==pin,'SOURCE_CHANGED_DURING_ANALYSIS')
    require(json.loads(read(root,'.acp-store.json'))==metadata,'OWNERSHIP_CHANGED_DURING_ANALYSIS')
    files=[{'path':n,'sha256':h,'ownership':expected.get(n,{}).get('owner','UNKNOWN') if n not in invalid_ownership and metadata.get(n,{}).get('owner')==expected.get(n,{}).get('owner') else 'UNKNOWN','language':'JAVA' if n.endswith('.java') else 'VUE_SFC' if n.endswith('.vue') else 'TYPESCRIPT'} for n,h in before.items()]
    symbols=[];refs=[];types=[];mappings=[];diagnostics=[];external={};keymap={};nativebyid={}
    for out in outputs:
        language=out['language']
        for d in out['definitions']:
            require(d['file'] in before and d['confidence'] in CONFIDENCE,'NATIVE_DEFINITION')
            id='symbol:'+digest([language,d['key']]);require((language,d['key']) not in keymap,'NATIVE_DUPLICATE_SYMBOL');keymap[language,d['key']]=id
            row={'id':id,'language':language,'kind':d['kind'],'name':d['name'],'native':d['native'],'type':d['type'],'confidence':d['confidence'],'location':location(root,d['file'],d['start'],d['end']),'exported':d.get('exported','UNKNOWN'),'sourceHash':before[d['file']],'ownership':next(f['ownership'] for f in files if f['path']==d['file'])}
            if d.get('nameStart') is not None:row['nameLocation']=location(root,d['file'],d['nameStart'],d['nameEnd'])
            symbols.append(row);nativebyid[id]=row
    for out in outputs:
        language=out['language']
        for d in out['definitions']:
            row=nativebyid[keymap[language,d['key']]];parent=keymap.get((language,d.get('container')))
            row['container']=parent
            if parent:
                refs.append({'kind':'CONTAINS','from':parent,'to':row['id'],'confidence':'KNOWN','location':row['location']})
    def scope(id,seen=()):
        require(id not in seen,'NATIVE_CONTAINER_CYCLE');r=nativebyid[id]
        return (scope(r['container'],(*seen,id)) if r['container'] else r['location']['file'])+'/'+r['kind']+':'+r['name']+(':'+r['type'] if r['kind'] in ('METHOD','FUNCTION','CONSTRUCTOR') else '')
    for id in nativebyid:nativebyid[id]['scopeKey']=scope(id)
    for out in outputs:
        language=out['language']
        for dest,rows in ((refs,out['references']),(types,out['relations'])):
            for e in rows:
                require(e['file'] in before and e['confidence'] in CONFIDENCE,'NATIVE_REFERENCE')
                target=None
                if e['confidence']=='KNOWN':
                    target=keymap.get((language,e['to']))
                    if target is None:
                        require(e['to'].startswith('external:') and e['native'],'NATIVE_TARGET_NOT_REGISTERED')
                        target='external:'+digest([language,e['native']]);external[target]={'id':target,'language':language,'native':e['native'],'kind':'EXTERNAL_OR_IMPLICIT_NATIVE_SYMBOL','type':None,'confidence':'KNOWN','declarationLocation':'ABSENT'}
                row={'kind':e['kind'],'from':keymap.get((language,e.get('from'))),'to':target,'confidence':e['confidence'],'location':location(root,e['file'],e['start'],e['end'])}
                dest.append(row)
        diagnostics.extend({'language':language,**{k:(v.replace(str(root),'<ROOT>') if isinstance(v,str) else v) for k,v in d.items()}} for d in out['diagnostics'])
        for lit in out['literals']:
            id=keymap.get((language,lit['symbol']));name=lit['file'];f=expected.get(name)
            if not id or not f or not prov_ok or before.get(name)!=f['sha256'] or nativebyid[id]['confidence']!='KNOWN' or nativebyid[id]['ownership']=='UNKNOWN':continue
            origins={o['id']:o['revision'] for o in f['origins']}
            revision=origins.get(lit['value'])
            if revision is None or (lit['revision'] is not None and lit['revision']!=revision):continue
            mappings.append({'symbol':id,'semantic':{'id':lit['value'],'revision':revision},'relationship':'EMBEDS_SEMANTIC_ID','confidence':'KNOWN','basis':lit['basis'],'literalLocation':location(root,name,lit['start'],lit['end']),'artifactSHA256':before[name],'provenanceSHA256':b['provenanceSHA256'],'bindingDigest':pin})
    def ordered(rows):return sorted({digest(r):r for r in rows}.values(),key=digest)
    unknown=[f['path'] for f in files if f['language']=='VUE_SFC'];unresolved=sum(r['confidence']!='KNOWN' for r in refs+types)
    complete=not diagnostics and not unknown and not unresolved and not any(d['severity']=='ERROR' for d in drift)
    result={'schema':SCHEMA,'scope':'ANALYSIS_ONLY','bindingDigest':pin,'identity':{**{k:b[k] for k in ('domain','canonicalDigest','generator','compiler','pipeline','artifactPlanDigest')},'provenanceSHA256':sha(read(root,'acp/provenance.json')) if (root/'acp/provenance.json').is_file() else None,'ownershipSHA256':sha(encode(metadata)),'auxiliaryHashes':{n:h for n,h in observed.items() if n not in before}},'files':files,'symbols':ordered(symbols),'externalSymbols':ordered(external.values()),'references':ordered(refs),'typeRelations':ordered(types),'semanticMappings':ordered(mappings),'artifactMappings':[{'artifact':n,'origins':f['origins'],'locationConfidence':f['historicalConfidence'],'current':prov_ok and before.get(n)==f['sha256']} for n,f in expected.items() if n in before], 'diagnostics':ordered(diagnostics),'drift':ordered(drift),'completeness':{'confidence':'KNOWN' if complete else 'UNKNOWN','fullyResolved':complete,'unsupportedFiles':unknown,'unresolvedRelationships':unresolved,'limitations':['Vue SFC bodies and templates are not analyzed.','No dynamic dispatch/runtime reachability or whole-ecosystem completeness claim.','Semantic links identify exact embedded ID references, not proof that a method implements the business concept.'],'nativeTools':[{k:o[k] for k in ('language','toolVersion','adapterSHA256','dependencyDigest','compilerSHA256')} for o in outputs]}}
    return validate(sealed(result))

from dataclasses import dataclass

@dataclass(frozen=True)
class NativeSourceAnalyzer:
    """Existing SourceAnalyzer port; filesystem/tool bindings belong to the host."""
    root: Path
    baseline: Path
    baseline_sha256: str
    maven_repo: Path
    node_modules: Path
    output: Path

    def analyze(self,source,query):
        from compiler_contracts import Document
        expected={'schema':'acp-source-input/1','bindingDigest':self.baseline_sha256,'files':sources(self.root)}
        require(source.read()==expected,'PORT_SOURCE_BINDING')
        require(query.read()=={'schema':'acp-source-query/1','operation':'MODEL'},'UNSUPPORTED_SOURCE_QUERY')
        result=analyze(self.root,self.baseline,self.baseline_sha256,maven_repo=self.maven_repo,node_modules=self.node_modules)
        require(expected['files']=={f['path']:f['sha256'] for f in result['files']},'PORT_SOURCE_CHANGED')
        require(not self.output.resolve().is_relative_to(self.root.resolve()),'READ_ONLY_ANALYSIS_OUTPUT')
        raw=encode(result)
        with self.output.open('xb') as stream:stream.write(raw)
        return Document.of({'schema':'acp-source-result/1','scope':'ANALYSIS_ONLY','modelDigest':result['digest'],'modelFileSHA256':sha(raw),'byteLength':len(raw),'completeness':result['completeness']})
