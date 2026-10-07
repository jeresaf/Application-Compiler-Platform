"""Bounded experiment module policy, shared ACP adapter logic, not Canonical IR.

All module metadata comes from the real candidate parser. Stable IDs are global;
labels are module-local lookup conveniences. Imports are direct and cycles reject.
"""
import copy


class ModuleError(ValueError):
    def __init__(self, code, subject="", related=()):
        self.code, self.subject, self.related = code, subject, tuple(related)
        super().__init__(code)


def resolve(parsed):
    modules = {}
    for path, output in parsed:
        name = output.get("module") or path
        if name in modules:
            raise ModuleError("AMBIGUOUS_MODULE", related=(path, modules[name][0]))
        modules[name] = (path, output)
    for name, (path, output) in modules.items():
        imports = output.get("imports", [])
        if len(imports) != len(set(imports)):
            raise ModuleError("DUPLICATE_IMPORT", related=(path,))
        for target in imports:
            if target not in modules:
                raise ModuleError("MISSING_MODULE", related=(path,))
    active, visited = set(), set()
    def visit(name):
        if name in active:
            raise ModuleError("CYCLIC_IMPORT", related=tuple(sorted(modules[n][0] for n in active)))
        if name in visited: return
        active.add(name)
        for target in sorted(modules[name][1].get("imports", [])): visit(target)
        active.remove(name); visited.add(name)
    for name in sorted(modules): visit(name)
    declarations, labels, origins = {}, {}, {}
    for name, (path, output) in modules.items():
        for node in output["model"]["nodes"]:
            identity = node["id"]
            if identity in declarations:
                raise ModuleError("DUPLICATE_ID", identity, (origins[identity], path))
            declarations[identity] = (name, node)
            origins[identity] = path
            labels.setdefault((name, node["name"]), []).append(identity)
    def reference(ref, owner, subject):
        key = ref["id"]
        if "::" in key:
            target_module, label = key.split("::", 1)
            matches = [label] if label in declarations and declarations[label][0] == target_module else labels.get((target_module, label), [])
            if len(matches) != 1:
                raise ModuleError("AMBIGUOUS_REFERENCE" if matches else "DANGLING_REFERENCE", subject, (origins[subject],))
            key = matches[0]
        elif key not in declarations:
            local = labels.get((owner, key), [])
            imported = [identity for module in modules[owner][1].get("imports", [])
                        for identity in labels.get((module, key), [])
                        if identity in modules[module][1].get("exports", [])]
            matches = local or imported
            if len(matches) > 1:
                raise ModuleError("AMBIGUOUS_REFERENCE" if local else "AMBIGUOUS_IMPORT",
                                  subject, tuple(sorted({origins[subject], *(origins[k] for k in matches)})))
            if matches:
                key = matches[0]
        if key not in declarations:
            return ref  # Existing semantic Analyze diagnoses dangling exact refs.
        target_module, target = declarations[key]
        if target_module != owner:
            imports = modules[owner][1].get("imports", [])
            if target_module not in imports or key not in modules[target_module][1].get("exports", []):
                raise ModuleError("VISIBILITY", subject, (origins[subject], origins[key]))
        return {"id": key, "revision": ref["revision"]}
    def lower(value, owner, subject):
        if isinstance(value, dict):
            if set(value) == {"id", "revision"}: return reference(value, owner, subject)
            return {k:lower(v, owner, subject) for k,v in value.items()}
        if isinstance(value, list): return [lower(v, owner, subject) for v in value]
        return value
    root = copy.deepcopy(parsed[0][1]["model"])
    root["nodes"] = [lower(node, name, node["id"]) for name,(_,output) in modules.items() for node in output["model"]["nodes"]]
    # Dependency-only modules must declare the same application/model identity.
    if any(output["model"][k] != root[k] for _,output in parsed for k in ("applicationId","modelVersion")):
        raise ModuleError("APPLICATION_MISMATCH")
    return root, origins
