"""Source observations only; never application intent, approval, or release evidence."""
import hashlib,json,os,stat
from collections import Counter
from pathlib import Path

SCHEMA='acp-source-model/1'
CONFIDENCE={'KNOWN','UNKNOWN','UNRESOLVED','ABSENT'}
OWNERS={'COMPILER_OWNED','FRAMEWORK_OWNED','AI_MANAGED','HUMAN_OWNED'}
SUFFIXES={'.java','.ts','.tsx','.vue'}

def require(ok,reason):
    if not ok:raise ValueError(reason)
def encode(value):return (json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
def digest(value):return hashlib.sha256(encode(value)).hexdigest()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def safe(name):
    require(type(name) is str and name and not name.startswith('/') and '\\' not in name and all(x not in ('','.','..') for x in name.split('/')),'UNSAFE_PATH');return name

def read(root,name):
    root=Path(root).absolute();path=root/safe(name)
    require(not root.is_symlink(),'SOURCE_ROOT_SYMLINK')
    for p in (path,*path.parents):
        require(not p.is_symlink(),'SOURCE_SYMLINK:'+name)
        if p==root:break
    before=path.lstat();require(stat.S_ISREG(before.st_mode) and before.st_size<=2*1024*1024,'SOURCE_FILE_BOUND')
    flags=os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)
    with os.fdopen(os.open(path,flags),'rb') as f:
        opened=os.fstat(f.fileno());raw=f.read(2*1024*1024+1);after=os.fstat(f.fileno())
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    require(stamp(before)==stamp(opened)==stamp(after)==stamp(path.lstat()),'SOURCE_REPLACED:'+name)
    require(len(raw)<=2*1024*1024,'SOURCE_FILE_BOUND');raw.decode('utf-8');return raw

def sources(root):
    root=Path(root).absolute();require(root.is_dir() and not root.is_symlink(),'SOURCE_ROOT')
    names=[]
    for top in ('backend/src/main','frontend/src'):
        base=root/top
        if not base.exists():continue
        for current,dirs,files in os.walk(base,followlinks=False):
            for name in dirs+files:require(not (Path(current)/name).is_symlink(),'SOURCE_SYMLINK')
            for name in files:
                p=Path(current)/name
                if p.suffix in SUFFIXES:names.append(p.relative_to(root).as_posix())
    require(0<len(names)<=128,'SOURCE_FILE_COUNT');result={n:sha(read(root,n)) for n in sorted(names)}
    require(sum((root/n).stat().st_size for n in names)<=8*1024*1024,'SOURCE_TOTAL_BOUND');return result

def location(root,name,start,end):
    text=read(root,name).decode();units=text.encode('utf-16-le');length=len(units)//2
    require(type(start) is int and type(end) is int and 0<=start<=end<=length,'NATIVE_LOCATION')
    prefix=units[:start*2].decode('utf-16-le');fragment=units[start*2:end*2].decode('utf-16-le')
    return {'file':name,'start':start,'end':end,'offsetUnit':'UTF16_CODE_UNIT','line':prefix.count('\n')+1,'column':len(prefix.rsplit('\n',1)[-1].encode('utf-16-le'))//2+1,'byteStart':len(prefix.encode()),'byteEnd':len((prefix+fragment).encode())}

def sealed(model):
    result=dict(model);result['digest']=digest(model);return result

def validate(model):
    require(set(model)=={'schema','scope','bindingDigest','identity','files','symbols','externalSymbols','references','typeRelations','semanticMappings','artifactMappings','diagnostics','drift','completeness','digest'},'MODEL_FIELDS')
    require(model['schema']==SCHEMA and model['scope']=='ANALYSIS_ONLY','MODEL_VERSION_OR_SCOPE')
    require(model['digest']==digest({k:v for k,v in model.items() if k!='digest'}),'MODEL_DIGEST')
    symbols={s['id']:s for s in model['symbols']};external={s['id']:s for s in model['externalSymbols']}
    require(len(symbols)==len(model['symbols']) and len(external)==len(model['externalSymbols']) and not set(symbols)&set(external),'SYMBOL_IDENTITY')
    files={x['path']:x for x in model['files']};require(len(files)==len(model['files']),'FILE_IDENTITY')
    for s in symbols.values():require(s['confidence'] in CONFIDENCE and s['location']['file'] in files and s['sourceHash']==files[s['location']['file']]['sha256'],'SYMBOL_SOURCE_BINDING')
    for r in model['references']+model['typeRelations']:
        require(r['confidence'] in CONFIDENCE and r['location']['file'] in files and (r['from'] is None or r['from'] in symbols),'REFERENCE_SOURCE')
        require((r['confidence']=='KNOWN' and r['to'] in (set(symbols)|set(external))) or (r['confidence']!='KNOWN' and r['to'] is None),'REFERENCE_BINDING')
    for m in model['semanticMappings']:
        require(m['symbol'] in symbols and m['confidence']=='KNOWN' and symbols[m['symbol']]['confidence']=='KNOWN','SEMANTIC_SYMBOL')
        require(m['artifactSHA256']==symbols[m['symbol']]['sourceHash'] and m['bindingDigest']==model['bindingDigest'],'SEMANTIC_SOURCE_BINDING')
    require(model['completeness']['confidence'] in CONFIDENCE,'COMPLETENESS')
    if model['completeness']['fullyResolved']:
        require(not model['diagnostics'] and not model['completeness']['unsupportedFiles'] and not any(x['confidence']!='KNOWN' for x in model['references']+model['typeRelations']) and not any(d['severity']=='ERROR' for d in model['drift']),'FALSE_COMPLETENESS')
    return model

def current(model,root):
    validate(model);require(sources(root)=={f['path']:f['sha256'] for f in model['files']},'STALE_SOURCE_MODEL')
    require(model['identity']['auxiliaryHashes']=={n:sha(read(root,n)) if (Path(root)/n).is_file() else None for n in model['identity']['auxiliaryHashes']},'STALE_ANALYSIS_CONFIGURATION')
    require(sha(read(root,'acp/provenance.json'))==model['identity']['provenanceSHA256'] and sha(encode(json.loads(read(root,'.acp-store.json'))))==model['identity']['ownershipSHA256'],'STALE_PROVENANCE_OR_OWNERSHIP')

def impact(model,root,*,symbol=None,semantic=None):
    current(model,root);require((symbol is None)!=(semantic is None),'IMPACT_SELECTOR')
    seeds={symbol} if symbol else {m['symbol'] for m in model['semanticMappings'] if m['semantic']['id']==semantic}
    by={s['id']:s for s in model['symbols']};require(seeds and seeds<=set(by),'IMPACT_SYMBOL_OR_SEMANTIC_UNBOUND')
    adjacency={}
    for index,e in enumerate(model['references']+model['typeRelations']):
        if e['confidence']=='KNOWN':adjacency.setdefault(e['to'],[]).append((index,e))
    affected=set(seeds);pending=list(seeds);selected={}
    while pending:
        for index,e in adjacency.get(pending.pop(),[]):
            selected[index]=e
            if e['from'] is not None and e['from'] not in affected:
                affected.add(e['from']);pending.append(e['from'])
    edges=list(selected.values())
    return {'schema':'acp-source-impact/1','modelDigest':model['digest'],'bindingDigest':model['bindingDigest'],'seeds':sorted(seeds),'provenDependencies':sorted(edges,key=digest),'affectedDefinitions':[by[k] for k in sorted(affected)],'possibleImpacts':[e for e in model['references'] if e['confidence']!='KNOWN'],'completeness':model['completeness'],'authority':'NO_CHANGE_AUTHORIZATION','limitation':'Proven dependency does not prove a behavioral change. External callers, Vue SFC bodies and dynamic dispatch may be unknown.'}

def compare(before,after):
    validate(before);validate(after);require(before['bindingDigest']==after['bindingDigest'],'DIFFERENT_BASELINES')
    def graph(model):
        by={s['id']:s for s in model['symbols']+model['externalSymbols']}
        sig=lambda s:(s.get('language'),s.get('scopeKey',s.get('native')),s.get('kind'),s.get('type'),s.get('location',{}).get('file'))
        definitions={digest(sig(s)) for s in model['symbols'] if s['confidence']=='KNOWN'}
        refs={digest((e['kind'],sig(by[e['from']]) if e['from'] in by else None,sig(by[e['to']]))) for e in model['references']+model['typeRelations'] if e['confidence']=='KNOWN'}
        return definitions,refs
    a,b=graph(before),graph(after)
    ambiguous=sorted({key for m in (before,after) for key,count in Counter(s['scopeKey'] for s in m['symbols']).items() if count>1})
    changed=sorted(p for p in {f['path'] for f in before['files']}|{f['path'] for f in after['files']} if next((f['sha256'] for f in before['files'] if f['path']==p),None)!=next((f['sha256'] for f in after['files'] if f['path']==p),None))
    return {'schema':'acp-source-delta/1','before':before['digest'],'after':after['digest'],'changedFiles':changed,'invalidatedLocations':[s['location'] for s in before['symbols'] if s['location']['file'] in changed],'nativeDefinitionsAdded':len(b[0]-a[0]),'nativeDefinitionsRemoved':len(a[0]-b[0]),'nativeRelationsAdded':len(b[1]-a[1]),'nativeRelationsRemoved':len(a[1]-b[1]),'semanticChange':'UNKNOWN','definitionCorrespondence':'UNKNOWN' if ambiguous else 'KNOWN_STATIC_SIGNATURES_ONLY','ambiguousScopes':ambiguous,'completeness':after['completeness'],'authority':'NO_CHANGE_AUTHORIZATION'}
