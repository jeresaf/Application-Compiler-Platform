"""Location-only token index aligned to actual native declaration spans.

This does not lower semantics. The native parser remains authoritative; scanning
only projects source positions and exact-reference tokens onto its plain model.
"""
import json,re
from compiler_ports import SourceDiagnostic

TOKEN=re.compile(r'\s+|"(?:[^"\\]|\\.)*"|-?\d+|[A-Za-z_][A-Za-z_0-9]*|.',re.DOTALL)
HEADER=re.compile(r'(?:export\s+)?[A-Za-z_][A-Za-z_0-9]*\s+("(?:[^"\\]|\\.)*")\s*@\s*([0-9]+)\s*\{')

def locator(text,offset,path):
    prefix=text[:offset];return f'{path}#L{prefix.count(chr(10))+1}C{len(prefix.rsplit(chr(10),1)[-1])+1}'
def utf16_index(text,units):
    return len(text.encode('utf-16-le')[:units*2].decode('utf-16-le',errors='ignore'))
def position(text,line,column,utf16=False):
    lines=text.splitlines(keepends=True)
    if not isinstance(line,int) or not isinstance(column,int) or line<1 or column<0 or line>len(lines)+1:return None
    if line==len(lines)+1:return len(text) if column==0 else None
    base=sum(len(s) for s in lines[:line-1]);part=lines[line-1]
    offset=utf16_index(part,column) if utf16 else column
    return base+offset if offset<=len(part) else None

def details_for(documents,parsed):
    details={'declarations':{},'tokens':{},'references':{},'imports':{},'modules':{}}
    for document,(_,output) in zip(documents,parsed):
        text,path=document['text'],document['path'];ts=[(m.group(),m.start(),m.end()) for m in TOKEN.finditer(text) if not m.group().isspace()]
        for i,(token,start,end) in enumerate(ts[:-1]):
            if token in ('module','import') and ts[i+1][0].startswith('"'):
                name=json.loads(ts[i+1][0]);key='modules' if token=='module' else 'imports';details[key].setdefault(name,[]).append(locator(text,ts[i+1][1],path))
        for node,span in zip(output['model']['nodes'],output['spans']):
            if 'offset' in span:begin=utf16_index(text,span['offset'])
            elif 'range' in span:begin=position(text,span['range']['start']['line']+1,span['range']['start']['character'],True)
            else:begin=position(text,span['line'],span['column'])
            header=HEADER.match(text,begin)
            if not header or json.loads(header[1])!=node['id']:raise ValueError('Declaration span mismatch')
            identity=node['id'];details['declarations'][identity]=locator(text,header.start(1),path)
            values=details['tokens'].setdefault(identity,{});references=details['references'].setdefault(identity,[])
            cursor=next(i for i,t in enumerate(ts) if t[1]==header.end()-1)
            def value(i,pointer):
                token,start,_=ts[i];values[pointer]=locator(text,start,path)
                if token=='{':
                    i+=1
                    while ts[i][0]!='}':
                        key=json.loads(ts[i][0]);i+=2;i=value(i,pointer+'/'+key.replace('~','~0').replace('/','~1'))
                        if ts[i][0]==',':i+=1
                    return i+1
                if token=='[':
                    i+=1;index=0
                    while ts[i][0]!=']':
                        i=value(i,pointer+'/'+str(index));index+=1
                        if ts[i][0]==',':i+=1
                    return i+1
                if token=='ref':
                    location=locator(text,ts[i+1][1],path);values[pointer]=location
                    revision_location=locator(text,ts[i+3][1],path)
                    values[pointer+'/id']=location;values[pointer+'/revision']=revision_location
                    references.append({'id':json.loads(ts[i+1][0]),'revision':int(ts[i+3][0]),'location':location,'revisionLocation':revision_location,'path':pointer})
                    return i+4
                if token=='Money':return i+8
                return i+1
            value(cursor,'')
    return details

def syntax_diagnostics(candidate,document,errors):
    text,path=document['text'],document['path'];result=[]
    for error in errors:
        line,column=error.get('line'),error.get('column')
        if isinstance(column,int) and candidate!='antlr':column-=1
        offset=position(text,line,column,candidate!='antlr')
        subject=None
        if offset is not None:
            for header in HEADER.finditer(text[:offset+1]):
                identity=json.loads(header[1]);revision=int(header[2])
                if re.fullmatch(r'[A-Za-z][A-Za-z0-9._:-]{0,127}',identity) and 1<=revision<=9007199254740991:subject=(identity,revision)
        result.append(SourceDiagnostic('ACP-FRONTEND-SYNTAX',subject,locator(text,offset,path) if offset is not None else None,confidence='END_OF_INPUT' if offset==len(text) else 'TOKEN' if offset is not None else 'UNRECOVERABLE'))
    return tuple(result)

def module_diagnostic(error,documents,parsed,details):
    ids={n['id']:(n['id'],n['revision']) for _,o in parsed for n in o['model']['nodes']}
    subject=ids.get(error.subject);related_ids=set();locations=[]
    if subject:
        references=details['references'].get(subject[0],[])
        locations=[r['location'] for r in references] or [details['declarations'][subject[0]]]
        for _,o in parsed:
            for n in o['model']['nodes']:
                if n['id']!=subject[0] and n['id'] in o.get('exports',[]) and any(r['id'].split('::')[-1] in (n['id'],n['name']) for r in references):related_ids.add(ids[n['id']])
    else:
        actual={o.get('module') or path for path,o in parsed}
        if error.code=='MISSING_MODULE':locations=[loc for name,locs in details['imports'].items() if name not in actual for loc in locs]
        elif error.code=='DUPLICATE_IMPORT':locations=[loc for locs in details['imports'].values() if len(locs)>1 for loc in reversed(locs)]
        else:locations=[loc for locs in details['imports'].values() for loc in locs] or [loc for locs in details['modules'].values() for loc in locs]
    related=set(locations[1:])
    for identity,_ in related_ids:
        if identity in details['declarations']:related.add(details['declarations'][identity])
    primary=locations[0] if locations else None;related.discard(primary)
    return (SourceDiagnostic('ACP-MODULE-'+error.code,subject,primary,tuple(sorted(related_ids)),tuple(sorted(related)),'TOKEN' if primary else 'UNRECOVERABLE'),)
