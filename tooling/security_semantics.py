"""Static obligations and small decision algebras, not a security executor."""


def policy_decision(outcomes, authenticated, same_tenant):
    if not authenticated or same_tenant is not True or not outcomes:
        return "DENY"
    if any(effect not in {"ALLOW", "DENY"} or match is None for effect, match in outcomes):
        return "DENY"
    if any(effect == "DENY" and match is True for effect, match in outcomes):
        return "DENY"
    return "ALLOW" if any(effect == "ALLOW" and match is True for effect, match in outcomes) else "DENY"


def disposal_allowed(age_seconds, retention_seconds, deletion_seconds, hold_active):
    return hold_active is False and age_seconds >= max(retention_seconds, deletion_seconds)


def checks(index, at, emit, types):
    nodes = list(index.values())
    kinds = lambda kind: [n for n in nodes if n["kind"] == kind]
    target = lambda r: index[r["id"]]
    ref = lambda n: {"id": n["id"], "revision": n["revision"]}
    def error(code, node, message, *path):
        emit(code, node, at(node, "data", *path), message)
    def boolean(node, expr, context, key):
        result = types.expression(node, expr, context, at(node, "data", key))
        if result is not None and result != {"kind": "Boolean"}:
            error("TYPE", node, "Policy condition must be Boolean.", key)

    for node in nodes:
        kind, d = node["kind"], node["data"]
        if kind == "Entity":
            if (d["tenancy"] == "SCOPED") != ("tenantField" in d):
                error("TENANT", node, "Only SCOPED resources must declare a tenant field.")
            if "tenantField" in d:
                field_type = target(d["tenantField"])["data"]["type"]
                if field_type["kind"] != "Identifier" or target(field_type["entity"])["data"]["tenancy"] != "TENANT_ROOT":
                    error("TENANT", node, "Tenant identifier must name a declared tenant root.")
        if kind == "AuthenticationModel":
            if target(d["actor"])["data"]["authentication"] != ref(node):
                error("SECURITY", node, "Authentication and actor must point to each other.")
            if d["assurance"] == "MULTI_FACTOR" and len(d["mechanisms"]) < 2:
                error("SECURITY", node, "Multi-factor authentication requires independent declared mechanisms.")
        if kind == "Actor" and target(d["authentication"])["data"]["actor"] != ref(node):
            error("SECURITY", node, "Actor uses another actor's authentication model.")
        if kind == "Scope":
            resource = target(d["resource"])["data"]
            actor_entity = target(target(d["actor"])["data"]["subject"])
            if resource["tenancy"] == "SCOPED":
                if d["mode"] != "SAME_TENANT" or d.get("resourceTenant") != resource.get("tenantField") or d.get("actorTenant") != actor_entity["data"].get("tenantField"):
                    error("TENANT", node, "Scoped resources require their exact actor/resource tenant fields.")
                elif target(d["resourceTenant"])["data"]["type"] != target(d["actorTenant"])["data"]["type"]:
                    error("TENANT", node, "Actor and resource must share the same tenant identity type.")
            elif d["mode"] != "GLOBAL" or "actorTenant" in d or "resourceTenant" in d:
                error("TENANT", node, "Global or tenant-root access uses an explicit global scope.")
        if kind == "Permission":
            if target(d["action"])["data"]["resource"] != d["resource"]:
                error("SECURITY", node, "Permission action belongs to another resource.")
        if kind == "Role":
            if any(target(p)["data"]["actor"] != d["actor"] for p in d["permissions"]):
                error("SECURITY", node, "Role permissions must apply to the role actor.")
        if kind == "RoleAssignment":
            if target(d["role"])["data"]["actor"] != d["actor"] or target(d["scope"])["data"]["actor"] != d["actor"]:
                error("SECURITY", node, "Assignment actor, role and scope disagree.")
        if kind == "Policy":
            permission, scope = target(d["permission"])["data"], target(d["scope"])["data"]
            if any(permission[k] != d[k] for k in ("actor", "resource", "action")) or any(scope[k] != d[k] for k in ("actor", "resource")):
                error("SECURITY", node, "Policy permission/scope does not match its actor/action/resource.")
            if any(d["permission"] not in target(r)["data"]["permissions"] for r in d["roles"]):
                error("SECURITY", node, "Policy role lacks its permission.")
        if kind == "PolicySet":
            if any(any(target(p)["data"][key] != d[key] for key in ("resource", "action")) for p in d["policies"]):
                error("SECURITY", node, "Policy set mixes different actions or resources.")
        if kind in {"Command", "Query"}:
            sets = [p for p in kinds("PolicySet") if p["data"]["action"] == ref(node)]
            applicable = [p for p in kinds("Policy") if p["data"]["action"] == ref(node)]
            if len(sets) != 1 or {p["id"] for p in applicable} != {r["id"] for r in sets[0]["data"]["policies"]}:
                error("SECURITY", node, "Each action needs exactly one complete policy set.")
        if kind == "DataClassification":
            if d["level"] in {"SENSITIVE", "SECRET"} and (d["audit"] != "READ_WRITE" or not d["encryptAtRest"] or not d["encryptInTransit"] or d["redaction"] == "NONE"):
                error("PRIVACY", node, "Sensitive classification requires audit, encryption and redaction.")
            if d["level"] == "SECRET" and (d["redaction"] != "OMIT" or d["export"] != "DENY"):
                error("PRIVACY", node, "Secret values must be omitted and export denied.")
        if kind == "Field":
            classification = target(d["classificationRef"])["data"]
            if classification["level"] != d["classification"]:
                error("PRIVACY", node, "Field classification label and obligation record disagree.")
            if classification["export"] == "PERMISSION_REQUIRED":
                if "exportPermission" not in d or target(d["exportPermission"])["data"]["resource"] != d["owner"]:
                    error("PRIVACY", node, "Export requires a permission on the data owner.")
        if kind == "SessionPolicy" and not d["idleSeconds"] <= d["absoluteSeconds"] or kind == "SessionPolicy" and d["reauthSeconds"] > d["absoluteSeconds"]:
            error("SECURITY", node, "Session idle/reauth durations must fit absolute expiry.")
        if kind == "RatePolicy" and d["burst"] > d["requests"]:
            error("SECURITY", node, "Burst cannot exceed the bounded request budget.")
        if kind == "DeletionPolicy":
            if (d["mode"] == "ANONYMIZE") != bool(d["fields"]):
                error("PRIVACY", node, "Only anonymization declares a nonempty field set.")
            entity = target(d["resource"])["data"]
            keys = entity["identity"] + ([entity["tenantField"]] if "tenantField" in entity else [])
            if any(target(f)["data"]["owner"] != d["resource"] or f in keys for f in d["fields"]):
                error("PRIVACY", node, "Anonymization must preserve identity/tenant keys and own its fields.")
        if kind == "LegalHold":
            if target(d["release"])["data"]["resource"] != d["resource"]:
                error("PRIVACY", node, "Hold release permission must address the held resource.")
            boolean(node, d["condition"], {"resource": d["resource"]}, "condition")
        if kind == "DataLifecycle":
            retention, deletion = target(d["retention"])["data"], target(d["deletion"])["data"]
            if any(target(r)["data"]["resource"] != d["resource"] for r in [d["retention"], d["deletion"], *d["holds"]]):
                error("PRIVACY", node, "Lifecycle policies must share a resource.")
            if retention["trigger"] != deletion["trigger"] or deletion["afterSeconds"] < retention["minimumSeconds"]:
                error("PRIVACY", node, "Deletion cannot precede retention or use a different age trigger.")
    for entity in kinds("Entity"):
        sensitive = any(n["kind"] == "Field" and n["data"]["owner"] == ref(entity) and n["data"]["classification"] in {"SENSITIVE", "SECRET"} for n in nodes)
        policies = [n for n in kinds("DataLifecycle") if n["data"]["resource"] == ref(entity)]
        if len(policies) > 1 or (sensitive and not policies):
            error("PRIVACY", entity, "Sensitive data requires one unambiguous lifecycle policy.")
