"""Safe source-sidecar projection into the compiler's immutable Failure algebra."""
import re
from compiler_contracts import Diagnostic,Subject
from compiler_ports import SourceDiagnostic

CODES=frozenset({'ACP-FRONTEND-SYNTAX','ACP-ID','ACP-REF','ACP-SHAPE','ACP-TYPE','ACP-WORKFLOW','ACP-ISSUE','ACP-SECURITY','ACP-TENANT','ACP-MODULE-MISSING_MODULE','ACP-MODULE-DUPLICATE_IMPORT','ACP-MODULE-CYCLIC_IMPORT','ACP-MODULE-VISIBILITY','ACP-MODULE-AMBIGUOUS_MODULE','ACP-MODULE-AMBIGUOUS_IMPORT','ACP-MODULE-AMBIGUOUS_REFERENCE','ACP-MODULE-DANGLING_REFERENCE','ACP-MODULE-DUPLICATE_ID','ACP-MODULE-APPLICATION_MISMATCH'})
from validate import REPAIR as SEMANTIC_CODES
CODES=CODES|frozenset('ACP-'+code for code in SEMANTIC_CODES)|frozenset('ACP-EVIDENCE-'+code for code in ('APPLICABILITY','BINDING','SHAPE','FRESHNESS','RESULT','MEASUREMENT','METHOD'))
CONFIDENCE=frozenset({'TOKEN','END_OF_INPUT','DECLARATION','UNRECOVERABLE'})
REPAIR='Repair the identified source tokens and exact references; retain stable semantic IDs and review policy changes.'

def transport(proposals,context,stage,provenance):
    """Reject unsafe adapter metadata; do not echo arbitrary explanation strings."""
    from compiler_core import safe_path
    if type(proposals) is not tuple or not proposals or len(proposals)>context.request.resources.diagnostics:raise ValueError('Diagnostics bound')
    def location(value):
        if value is None:return
        if type(value) is not str or len(value)>512:raise ValueError('Location')
        path,anchor=value.split('#',1);safe_path(path)
        if not re.fullmatch(r'L[1-9][0-9]*C[1-9][0-9]*',anchor):raise ValueError('Location')
    def subject(value):
        if type(value) is not tuple or len(value)!=2:raise ValueError('Subject')
        identity,revision=value
        if type(identity) is not str or not re.fullmatch(r'[A-Za-z][A-Za-z0-9._:-]{0,127}',identity) or type(revision) is not int or not 1<=revision<=9007199254740991:raise ValueError('Subject')
        return Subject(context.request.application,identity,revision)
    result=[]
    for p in proposals:
        if type(p) is not SourceDiagnostic or p.code not in CODES or p.confidence not in CONFIDENCE:raise ValueError('Diagnostic')
        if (p.location is None)!=(p.confidence=='UNRECOVERABLE'):raise ValueError('Confidence')
        location(p.location)
        if type(p.related) is not tuple or type(p.related_locations) is not tuple or len(p.related)>context.request.resources.nodes or len(p.related_locations)>context.request.resources.nodes:raise ValueError('Related')
        for span in p.related_locations:location(span)
        result.append(Diagnostic(p.code,'ERROR',stage,() if p.subject is None else (subject(p.subject),),p.location,tuple(sorted(set(subject(s) for s in p.related))),'Source validation failed.',REPAIR,provenance,tuple(sorted(set(p.related_locations))),p.confidence))
    from compiler_contracts import wire
    from canonical_json import canonical_bytes
    if len(canonical_bytes(wire(tuple(result))))>context.request.resources.output_bytes:raise ValueError("Diagnostics output bound")
    return tuple(sorted(result,key=lambda d:(d.code,d.subjects,d.location or '',d.related,d.related_locations)))

def semantic_proposals(model,source_map,details,diagnostics):
    nodes={n['id']:n for n in model.get('nodes',[]) if isinstance(n,dict) and isinstance(n.get('id'),str)}
    definitions=details.get('declarations',{});tokens=details.get('tokens',{});refs=details.get('references',{});result=[]
    for d in diagnostics:
        identity=d['subject'];node=nodes.get(identity);subject=(identity,node['revision']) if node else None
        path=d['path'].split('/',3)[3] if d['path'].startswith('/nodes/') and len(d['path'].split('/',3))==4 else ''
        path='/'+path if path else ''
        exact=tokens.get(identity,{}).get(path)
        primary=exact or definitions.get(identity) or source_map.get(identity)
        related_ids=set();related_locations=set()
        relevant=refs.get(identity,[])
        if exact:relevant=[r for r in relevant if r.get('location')==exact] or relevant
        for ref in relevant:
            target=nodes.get(ref['id'])
            if d['code']=='ACP-REF' and target and ref['revision']!=target['revision'] and ref.get('revisionLocation'):
                primary=ref['revisionLocation'];exact=primary
            if target and target['id']!=identity:
                related_ids.add((target['id'],target['revision']))
                if target['id'] in definitions:related_locations.add(definitions[target['id']])
        if d['code']=='ACP-WORKFLOW' and node and node.get('kind')=='Transition':
            for peer in nodes.values():
                if peer['id']!=identity and peer.get('kind')=='Transition' and peer['data'].get('command')==node['data'].get('command') and peer['data'].get('from')==node['data'].get('from'):
                    related_ids.add((peer['id'],peer['revision']))
                    if peer['id'] in definitions:related_locations.add(definitions[peer['id']])
        related_locations.discard(primary)
        result.append(SourceDiagnostic(d['code'],subject,primary,tuple(sorted(related_ids)),tuple(sorted(related_locations)),'TOKEN' if exact else 'DECLARATION' if primary else 'UNRECOVERABLE'))
    return tuple(result)
