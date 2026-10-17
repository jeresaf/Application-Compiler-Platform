"""Inactive-by-default release admission boundary for a separately trusted host.

HostPins MUST originate outside the submitted application/configuration. There is
no CLI, environment discovery, built-in trust root, or operational activation.
Cryptographic fixtures test this interface; they never enroll a release profile.
The native predicate code is reused with only its JUnit source resolver replaced
in private function globals. Native modules and laboratory behavior are untouched.
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import FunctionType, SimpleNamespace
import base64

from .encoding import canonicalize, parse_canonical, signature_input
from .signatures import verify_ed25519
from .scoped.manifest import require, sha, time, path
from .scoped.verify import capture
from .scoped.witnesses import verify_source, junit_cases
import sys

SEAL = 'sha256:ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb'
RELEASE = 'acp-spring-vue-postgres/0.5.0'


@dataclass(frozen=True)
class TrustedKey:
    identity: str
    principal: str
    public: bytes
    role: str
    valid_from: datetime
    valid_until: datetime


@dataclass(frozen=True)
class HostPins:
    """Trusted evaluator-host input, never a field of a submitted manifest.

    Fresh revocation checkpoint and nonce come from the host's independent
    authority/execution channel. Reuse across unrelated requests is forbidden.
    Durable issuance/replay service and operational custody remain external.
    """
    authority_keys: tuple[TrustedKey, ...]
    configuration_digest: str
    revocation_digest: str
    registry_digest: str
    evaluator_inventory: bytes
    execution_inventory: bytes
    witness_inventory: bytes
    application_inventory: bytes
    evaluator_commit: str
    execution_commit: str
    witness_commit: str
    application_commit: str
    predicate_digest: str
    nonce: str
    now: datetime

    def __post_init__(self):
        require(type(self.authority_keys) is tuple and all(type(k) is TrustedKey for k in self.authority_keys), 'IMMUTABLE_HOST_PINS')
        require(len({k.identity for k in self.authority_keys}) == len(self.authority_keys), 'DUPLICATE_HOST_KEY')
        require(len({k.public for k in self.authority_keys}) == len(self.authority_keys), 'ALIASED_HOST_KEY')
        require(self.now.tzinfo == timezone.utc and len(self.nonce) >= 32, 'HOST_TIME_OR_CHALLENGE')
        for name in ('evaluator_inventory','execution_inventory','witness_inventory','application_inventory'):
            require(type(getattr(self,name)) is bytes, 'IMMUTABLE_HOST_PINS')
        for k in self.authority_keys:
            require(type(k.public) is bytes and len(k.public)==32 and k.valid_from.tzinfo==timezone.utc and k.valid_until.tzinfo==timezone.utc and k.valid_from<k.valid_until, 'HOST_KEY_VALIDITY')


def closed(value, fields):
    require(type(value) is dict and set(value)==set(fields.split()), 'CLOSED_RELEASE_RECORD')
    return value


def fresh(value, now):
    start,end=time(value['issuedAt']),time(value['expiresAt'])
    require(start <= now < end and now-start <= timedelta(hours=24) and start<end, 'STALE_RELEASE_EVIDENCE')


def signed(raw, fields, roles, keys, now, revoked=frozenset()):
    require(type(raw) is bytes and len(raw)<=1024*1024, 'RELEASE_RECORD_LIMIT')
    record=closed(parse_canonical(raw),'payload signatures');p=closed(record['payload'],fields)
    require(type(record['signatures']) is list and len(record['signatures'])==len(roles), 'RELEASE_SIGNATURE_THRESHOLD')
    fresh(p,now);by_id={k.identity:k for k in keys};seen_roles=set();principals=set()
    for signature in record['signatures']:
        s=closed(signature,'keyId signature');key=by_id.get(s['keyId'])
        require(key is not None and key.identity not in revoked and key.principal not in revoked, 'UNKNOWN_OR_REVOKED_RELEASE_KEY')
        require(key.role in roles and key.role not in seen_roles and key.principal not in principals, 'INDEPENDENT_RELEASE_ROLES')
        require(key.valid_from<=time(p['issuedAt'])<=now<key.valid_until, 'RELEASE_KEY_VALIDITY')
        encoded=s['signature'];require(type(encoded) is str and len(encoded)==86, 'RELEASE_SIGNATURE_ENCODING')
        decoded=base64.urlsafe_b64decode(encoded+'==')
        require(base64.urlsafe_b64encode(decoded).decode().rstrip('=')==encoded, 'RELEASE_SIGNATURE_ENCODING')
        verify_ed25519(key.public,decoded,signature_input(p));seen_roles.add(key.role);principals.add(key.principal)
    require(seen_roles==set(roles),'RELEASE_SIGNATURE_THRESHOLD')
    return p


def source(root, inventory, commit, description):
    closed(description,'treeDigest commit dependencyPath dependencyDigest entrypoint')
    require(description['commit']==commit,'RELEASE_SOURCE_PIN')
    verify_source(Path(root),{'source':description,'cases':[]},SimpleNamespace(source_inventory=inventory))


def evaluate(*, pins=None, configuration, revocation, registry, execution,
             record, binding, artifact_root, evaluator_root, execution_root,
             witness_root, application_root, native=None):
    """Evaluate ONE existing criterion. No approvals, journal or gate updates.

    Raw submissions convey no authority. A trusted host supplies all independent
    pins plus its own authenticated, fresh revocation head and reserved nonce.
    No production host/provider is registered by this implementation.
    """
    require(type(pins) is HostPins,'RELEASE_AUTHORITY_NOT_CONFIGURED')
    require(abs((datetime.now(timezone.utc)-pins.now).total_seconds())<=300,'STALE_HOST_CONTEXT')
    record=parse_canonical(canonicalize(record));binding=parse_canonical(canonicalize(binding))
    # Late import: laboratory callers do not acquire release dependencies/state.
    from tooling.audit import criteria
    require(native is None or native is criteria,'UNTRUSTED_EVALUATOR_MODULE')
    require(sha(Path(criteria.__file__).read_bytes())==pins.predicate_digest,'EVALUATOR_SOURCE_PIN')
    require(binding==criteria.current_binding(),'NATIVE_RELEASE_BINDING')
    require(binding['bundleDigest']==SEAL,'WRONG_SEALED_RELEASE')
    require(binding['executionCommit']==pins.application_commit,'APPLICATION_COMMIT_PIN')
    require(sha(configuration)==pins.configuration_digest and sha(revocation)==pins.revocation_digest and sha(registry)==pins.registry_digest,'RELEASE_RECORD_PIN')
    rev=signed(revocation,'schema issuedAt expiresAt configurationDigest revoked',{'REVOCATION'},pins.authority_keys,pins.now)
    require(rev['schema']=='acp-release-revocation/1' and rev['configurationDigest']==pins.configuration_digest,'REVOCATION_SCOPE')
    require(type(rev['revoked']) is list and all(type(x) is str for x in rev['revoked']) and len(set(rev['revoked']))==len(rev['revoked']),'REVOCATION_CONTENT')
    revoked=frozenset(rev['revoked'])
    require(all(k.identity not in revoked and k.principal not in revoked for k in pins.authority_keys if k.role=='REVOCATION'),'REVOKED_REVOCATION_AUTHORITY')
    cfg=signed(configuration,'schema issuedAt expiresAt release seal evaluator execution witness application executionContract keys decisions',{'PROJECT_AUTHORITY','SECURITY_AUTHORITY'},pins.authority_keys,pins.now,revoked)
    require(cfg['schema']=='acp-release-authority/1' and cfg['release']==RELEASE and cfg['seal']==SEAL,'WRONG_RELEASE_PROFILE')
    # These references are covered by both authority signatures; absence is not
    # replaced by a local approval boolean or an invented documentary decision.
    closed(cfg['decisions'],'keyCustody executionInfrastructure registrationScope')
    require(all(type(v) is str and len(v)==71 and v.startswith('sha256:') and all(c in '0123456789abcdef' for c in v[7:]) for v in cfg['decisions'].values()),'MISSING_AUTHORITY_DECISIONS')
    contract=closed(cfg['executionContract'],'executableDigest argv environmentDigest workingDirectory timeoutSeconds dependencyDigest')
    require(type(contract['argv']) is list and all(type(v) is str for v in contract['argv']) and contract['argv'], 'EXECUTION_ARGV')
    require(type(contract['timeoutSeconds']) is int and 0<contract['timeoutSeconds']<=86400,'EXECUTION_TIMEOUT')
    for field in ('executableDigest','environmentDigest','dependencyDigest'):
        require(type(contract[field]) is str and len(contract[field])==71 and contract[field].startswith('sha256:') and all(c in '0123456789abcdef' for c in contract[field][7:]),'EXECUTION_INPUT_DIGEST')
    require(type(contract['workingDirectory']) is str and contract['workingDirectory'].startswith('/'),'EXECUTION_WORKING_DIRECTORY')
    keys=[]
    require(type(cfg['keys']) is list and len(cfg['keys'])<=32,'RELEASE_KEYS')
    for row in cfg['keys']:
        k=closed(row,'identity principal public role validFrom validUntil')
        keys.append(TrustedKey(k['identity'],k['principal'],bytes.fromhex(k['public']),k['role'],time(k['validFrom']),time(k['validUntil'])))
    require(len({k.identity for k in keys+list(pins.authority_keys)})==len(keys)+len(pins.authority_keys) and len({k.public for k in keys+list(pins.authority_keys)})==len(keys)+len(pins.authority_keys) and len({k.principal for k in keys+list(pins.authority_keys)})==len(keys)+len(pins.authority_keys),'ALIASED_RELEASE_KEY')
    # Every active in-process admission dependency must equal its independently
    # pinned evaluator source, rather than merely a submitted evaluator checkout.
    active={__name__, 'tooling.audit.criteria'} | {n for n in sys.modules if n.startswith('engineering.evidence_admission.')}
    inventory={e['path']:e for e in parse_canonical(pins.evaluator_inventory)['files']}
    for name in active:
        module=sys.modules[name];filename=getattr(module,'__file__',None)
        if filename is None:continue
        relative=name.replace('.','/')+('/__init__.py' if Path(filename).name=='__init__.py' else '.py')
        require(relative in inventory and sha(Path(filename).read_bytes())==inventory[relative]['sha256'],'ACTIVE_EVALUATOR_SOURCE')
    r=signed(registry,'schema issuedAt expiresAt configurationDigest release seal predicateDigest cases',{'REGISTRAR','INDEPENDENT_REVIEWER'},keys,pins.now,revoked)
    require(r['schema']=='acp-release-registry/1' and r['configurationDigest']==pins.configuration_digest and r['release']==RELEASE and r['seal']==SEAL and r['predicateDigest']==pins.predicate_digest,'REGISTRY_SCOPE')
    # The record format, subject binding, freshness and semantic predicates are
    # still the native ones. Capture additionally rejects file/directory races.
    require(type(record) is dict and type(record.get('criterion')) is int,'CRITERION_RECORD')
    number=record['criterion'];require(number in criteria.SPECS,'UNKNOWN_CRITERION')
    require(type(r['cases']) is list and 0<len(r['cases'])<=256,'REGISTERED_CASE_LIMIT')
    cases={}
    witness_files={e['path']:e for e in parse_canonical(pins.witness_inventory)['files']}
    for case in r['cases']:
        c=closed(case,'criterion application witnessId caseId sourcePath className method assertionArtifactPaths')
        require(type(c['criterion']) is int and c['criterion']==number and c['application'] in binding['canonicalDigests'],'REGISTRY_CRITERION_SCOPE')
        identity=(number,c['application'],c['witnessId'],c['caseId']);require(identity not in cases,'DUPLICATE_REGISTERED_CASE')
        require(c['sourcePath'] in witness_files,'REGISTERED_SOURCE_REQUIRED')
        require(type(c['assertionArtifactPaths']) is list and c['assertionArtifactPaths'],'REGISTERED_ARTIFACT_REQUIRED')
        for item in c['assertionArtifactPaths']:path(item)
        cases[identity]=c
    require({c['application'] for c in cases.values()}==set(binding['canonicalDigests']),'INCOMPLETE_RELEASE_APPLICATIONS')
    require({c['method'] for c in cases.values()}==set(criteria.SPECS[number]['tests']),'REGISTERED_PREDICATE_METHODS')
    # Verify registered method/class bytes at the independently pinned Git tree.
    files=criteria.validate_record(number,record,Path(artifact_root),binding,pins.now)
    entries=[]
    for item in record['artifacts']:
        p=files[item['path']];entries.append({'path':item['path'],'size':p.stat().st_size,'sha256':item['sha256']})
    require(len(entries)==len(files) and len(entries)<=4096 and sum(e['size'] for e in entries)<=256*1024*1024,'RELEASE_ARTIFACT_LIMIT')
    artifacts=capture(Path(artifact_root),entries)
    att=signed(execution,'schema issuedAt expiresAt configurationDigest registryDigest revocationDigest release seal predicateDigest evaluatorCommit executionCommit witnessCommit applicationCommit recordDigest nonce observedInputs artifacts cases startedAt finishedAt resourceLimitEvents exitSignal exitCode cleanup',{'EXECUTOR','COLLECTOR'},keys,pins.now,revoked)
    expected={'schema':'acp-release-execution/1','configurationDigest':pins.configuration_digest,'registryDigest':pins.registry_digest,'revocationDigest':pins.revocation_digest,'release':RELEASE,'seal':SEAL,'predicateDigest':pins.predicate_digest,'evaluatorCommit':pins.evaluator_commit,'executionCommit':pins.execution_commit,'witnessCommit':pins.witness_commit,'applicationCommit':pins.application_commit,'recordDigest':sha(canonicalize(record)),'nonce':pins.nonce,'artifacts':{p:sha(raw) for p,raw in artifacts.items()},'cases':r['cases'],'exitCode':0,'cleanup':'COMPLETE','observedInputs':{'evaluator':cfg['evaluator'],'execution':cfg['execution'],'witness':cfg['witness'],'application':cfg['application'],'contract':cfg['executionContract']}}
    require(all(att[k]==v for k,v in expected.items()),'AUTHENTICATED_EXECUTION_BINDING')
    require(time(att['startedAt'])<=time(att['finishedAt'])<=time(att['issuedAt'])<=pins.now and (time(att['finishedAt'])-time(att['startedAt'])).total_seconds()<=contract['timeoutSeconds'] and att['resourceLimitEvents']==[] and att['exitSignal'] is None,'EXECUTION_OUTCOME')
    fresh({'issuedAt':att['startedAt'],'expiresAt':att['expiresAt']},pins.now)
    checked=set()
    for name,root in (('evaluator',evaluator_root),('execution',execution_root),('witness',witness_root),('application',application_root)):
        identity=(str(root),getattr(pins,name+'_inventory'),getattr(pins,name+'_commit'),canonicalize(cfg[name]))
        if identity not in checked:source(root,*identity[1:3],cfg[name]);checked.add(identity)
    verify_source(Path(witness_root),{'source':cfg['witness'],'cases':list(cases.values())},SimpleNamespace(source_inventory=pins.witness_inventory))
    junit_cases(artifacts,cases)
    with TemporaryDirectory(prefix='acp-release-verified-') as directory:
        snapshot=Path(directory);verified={}
        for name,raw in artifacts.items():
            target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);target.chmod(0o400);verified[name]=target
        # A private resolver, never a global monkeypatch: the exact same native
        # predicate code executes. Only independently registered JUnit sources
        # replace the sealed-template resolver for this one explicit invocation.
        def registered_junit(files,required,execution_commit=None,**kwargs):
            require(files==verified and execution_commit==pins.application_commit and set(required)=={c['method'] for c in cases.values()},'EXTERNAL_WITNESS_SCOPE')
            junit_cases(artifacts,cases)
        namespace=dict(criteria.validate.__globals__);namespace['junit']=registered_junit
        predicate=FunctionType(criteria.validate.__code__,namespace,criteria.validate.__name__,criteria.validate.__defaults__,criteria.validate.__closure__)
        namespace['validate']=predicate
        predicate(number,verified,binding,pins.now,{})
    # Detect post-verification source/artifact namespace replacement as well.
    require(capture(Path(artifact_root),entries)==artifacts,'RELEASE_ARTIFACT_CHANGED')
    checked=set()
    for name,root in (('evaluator',evaluator_root),('execution',execution_root),('witness',witness_root),('application',application_root)):
        identity=(str(root),getattr(pins,name+'_inventory'),getattr(pins,name+'_commit'),canonicalize(cfg[name]))
        if identity not in checked:source(root,*identity[1:3],cfg[name]);checked.add(identity)
    return {'criterion':number,'status':'PASS','release':RELEASE,'bundleDigest':SEAL,'recordDigest':sha(canonicalize(record)),'registryDigest':pins.registry_digest,'executionDigest':sha(execution),'releaseDisposition':'PHASE6_RELEASE_CLOSURE_BLOCKED','authority':'EVIDENCE_ONLY_NOT_RELEASE_APPROVAL'}
