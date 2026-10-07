"""Safe related-location projection of existing ACP diagnostics, outside the IR."""
from validate import validate


def references(value):
    if isinstance(value,dict):
        if set(value)=={"id","revision"}:yield value["id"]
        else:
            for v in value.values():yield from references(v)
    elif isinstance(value,list):
        for v in value:yield from references(v)


def project(model, locations, mode="compile"):
    """Locations map stable IDs to all declaration spans (including duplicates).

    Related locations mean referenced declarations or transitions sharing an
    exact trigger. This conservative relationship is explicit; it is not a claim that a
    framework inferred causality. Never copy source text or semantic record data.
    """
    raw=validate(model,mode)
    nodes={n["id"]:n for n in model.get("nodes",[])}
    result=[]
    for diagnostic in raw:
        subject=diagnostic["subject"]
        spans=locations.get(subject,[])
        related=set(spans[1:])
        for target in references(nodes.get(subject,{})):
            related.update(locations.get(target,[]))
        for other in raw:
            node,peer=nodes.get(subject,{}),nodes.get(other["subject"],{})
            same_trigger=(node.get("kind")==peer.get("kind")=="Transition" and
                          node.get("data",{}).get("command")==peer.get("data",{}).get("command") and
                          node.get("data",{}).get("from")==peer.get("data",{}).get("from"))
            if same_trigger and other["code"]==diagnostic["code"] and other["subject"]!=subject:
                related.update(locations.get(other["subject"],[]))
        primary=spans[0] if spans else "domain.acp#L1C1"
        related.discard(primary)
        result.append({"code":diagnostic["code"],"subject":subject,
                       "primary":primary,"related":sorted(related),
                       "remediation":diagnostic["remediation"]})
    return sorted(result,key=lambda d:(d["code"],d["subject"],d["primary"],tuple(d["related"])))
