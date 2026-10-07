"""ACP-specific bounded label edits; lexical spans never target stable-ID headers."""
import copy
import json
import re

DECODER=json.JSONDecoder()

def edits(line,body_start,old_label,new_label,qualified_old,qualified_new):
    """Scan quoted tokens and nesting, so nested `name` fields cannot be renamed."""
    changes=[];depth=0;i=body_start;found=0
    while i<len(line):
        if line[i]=='"':
            token,end=DECODER.raw_decode(line[i:]);end+=i
            tail=end
            while tail<len(line) and line[tail].isspace():tail+=1
            if depth==1 and token=='name' and line[tail:tail+1]==':':
                value_start=tail+1
                while line[value_start].isspace():value_start+=1
                value,length=DECODER.raw_decode(line[value_start:])
                if value==old_label:
                    changes.append((value_start,value_start+length,json.dumps(new_label,ensure_ascii=False)));found+=1
            i=end;continue
        if line.startswith('ref ',i):
            start=i+4
            while line[start].isspace():start+=1
            value,length=DECODER.raw_decode(line[start:])
            if value==qualified_old:changes.append((start,start+length,json.dumps(qualified_new)))
            i=start+length;continue
        if line[i] in '{[':depth+=1
        elif line[i] in '}]':depth-=1
        i+=1
    for start,end,text in reversed(sorted(changes)):line=line[:start]+text+line[end:]
    return line,found

def rename_label(documents,module,identity,old_label,new_label):
    if not isinstance(new_label,str) or not new_label or '::' in new_label:raise ValueError('LABEL')
    updated=copy.deepcopy(documents);found=0
    target=re.compile(r'(?:export )?\w+ '+re.escape(json.dumps(identity))+r' @ \d+ ')
    declaration=re.compile(r'(?:export )?\w+ "(?:[^"\\]|\\.)*" @ \d+ ')
    for document in updated:
        lines=document['text'].splitlines(keepends=True)
        for i,line in enumerate(lines):
            header=declaration.match(line)
            if not header:continue
            # Only the selected declaration permits a top-level label edit.
            selected=target.match(line)
            line,count=edits(line,header.end(),old_label if selected else object(),new_label,module+'::'+old_label,module+'::'+new_label)
            found+=count;lines[i]=line
        document['text']=''.join(lines)
    if found!=1:raise ValueError('AMBIGUOUS_LABEL')
    return updated
