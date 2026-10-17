"""Read-only B0 verifier. Every successful result is laboratory qualification only."""
from dataclasses import dataclass
import os
from pathlib import Path
import stat
from engineering.evidence_admission.encoding import canonicalize, parse_canonical
from .context import LabContext
from .manifest import manifest, digest, parse, path, require, sha, time
from .witnesses import authenticate, verify_source, registered_cases, junit_cases
from .human_reviews import verify_reviews


def capture(root, entries, *, source=False):
    """Capture through pinned descriptors; reject namespace mutation, including ABA."""
    root=Path(root)
    require(root.is_absolute() and '..' not in root.parts, 'UNSAFE_ARTIFACT_ROOT')
    expected={a['path']:a for a in entries}
    require(len(expected)==len(entries) and len(expected)<=4096, 'AMBIGUOUS_CAPTURE')
    result={}; handles=[]; bindings=[]; files=[]
    def stamp(s):
        return (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    def opened(parent,name,namespace=True):
        fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
        handles.append(fd);bindings.append((parent,name,fd,stamp(os.fstat(fd)),namespace))
        return fd
    anchor=os.open('/',os.O_RDONLY|os.O_DIRECTORY);handles.append(anchor)
    try:
        directory=anchor
        for index,component in enumerate(root.parts[1:],1):
            directory=opened(directory,component,namespace=index==len(root.parts)-1)
        def visit(fd,prefix):
            for name in os.listdir(fd):
                if source and not prefix and name=='.git':continue
                relative=prefix+name;path(relative)
                info=os.stat(name,dir_fd=fd,follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    require(any(p.startswith(relative+'/') for p in expected),'UNEXPECTED_ARTIFACT_DIRECTORY')
                    visit(opened(fd,name),relative+'/');continue
                require(relative in expected,'UNEXPECTED_ARTIFACT_OR_LIMIT')
                entry=expected[relative]
                file=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
                try:
                    before=os.fstat(file)
                    require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==entry['size'],'UNSAFE_ARTIFACT_FILE')
                    require(stamp(info)==stamp(before),'ARTIFACT_REPLACED')
                    if source:require(format(stat.S_IMODE(before.st_mode),'04o')==entry['mode'],'SOURCE_MODE')
                    chunks=[];total=0
                    while True:
                        chunk=os.read(file,min(65536,entry['size']+1-total))
                        if not chunk:break
                        total+=len(chunk);require(total<=entry['size'],'ARTIFACT_READ_LIMIT');chunks.append(chunk)
                    raw=b''.join(chunks)
                    require(stamp(before)==stamp(os.fstat(file))==stamp(os.stat(name,dir_fd=fd,follow_symlinks=False)),'ARTIFACT_CHANGED_DURING_CAPTURE')
                    require(len(raw)==entry['size'] and sha(raw)==entry['sha256'],'ARTIFACT_HASH')
                    result[relative]=raw;files.append((fd,name,stamp(before)))
                finally:os.close(file)
        visit(directory,'')
        require(set(result)==set(expected),'UNEXPECTED_OR_MISSING_ARTIFACT')
        for parent,name,before in files:
            require(before==stamp(os.stat(name,dir_fd=parent,follow_symlinks=False)),'ARTIFACT_CHANGED_AFTER_READ')
        for parent,name,fd,before,namespace in bindings:
            current=stamp(os.fstat(fd));linked=stamp(os.stat(name,dir_fd=parent,follow_symlinks=False))
            require((before==current==linked) if namespace else (before[:3]==current[:3]==linked[:3]),'CAPTURE_DIRECTORY_CHANGED')
    finally:
        for fd in reversed(handles):os.close(fd)
    return result


@dataclass(frozen=True)
class LabQualification:
    manifest_raw: bytes
    attestation_raw: bytes
    review_records: tuple[bytes,...]
    context: LabContext
    source_root: str
    artifact_root: str
    status: str = 'QUALIFICATION_ONLY'

    def reverify(self):
        require(self.status=='QUALIFICATION_ONLY','LABORATORY_ONLY')
        return qualify(self.manifest_raw,self.attestation_raw,self.review_records,self.context,Path(self.source_root),Path(self.artifact_root))

    @property
    def application_commit(self):return manifest(self.manifest_raw)['applicationSource']['commit']

    @property
    def cases(self):
        return registered_cases(manifest(self.manifest_raw),parse(self.context.scope,'release-witness-scope'))

    @property
    def artifact_hashes(self):return {a['path']:a['sha256'] for a in manifest(self.manifest_raw)['artifacts']}


def qualify(raw,attestation_raw,reviews,context,source_root,artifact_root):
    require(type(context) is LabContext,'EXTERNAL_LAB_CONTEXT_REQUIRED');context.check_current()
    m=manifest(raw);context.freshness(m['createdAt'],m['expiresAt'])
    for field,name in [('release','release'),('applicationSource','application_source'),('evaluator','evaluator'),('applications','subjects'),('policyRef','policy_ref'),('registrationCheckpoint','checkpoint')]:
        require(m[field]==context.value(name),'CONTEXT_BINDING:'+field)
    require(m['approvalReferences']==[],'UNSUPPORTED_AUTHORIZATION_PROFILE')  # no migration/semantic authority in B0
    scope=parse(context.scope,'release-witness-scope')
    require(scope['release']==m['release'] and scope['policyRef']==m['policyRef'],'REGISTRATION_SCOPE')
    context.freshness(scope['validFrom'],scope['validUntil'])
    for c in m['criteria']:
        require(set(c['applicationScope'])=={a['application'] for a in m['applications']},'INCOMPLETE_CRITERION_APPLICATION_SCOPE')
        if c['evidenceKind']!='HUMAN_REVIEW':require(c['registrationRef']==context.value('registration_ref'),'UNREGISTERED_WITNESS')
    verify_source(source_root,scope,context)
    cases=registered_cases(m,scope)
    artifacts=capture(artifact_root,m['artifacts'])
    require(artifacts[m['applicationSource']['inventory']]==context.source_inventory,'APPLICATION_SOURCE_INVENTORY')
    # In B0 the isolated fixture exports witness and application source together.
    require(m['applicationSource']['commit']==scope['source']['commit'] and m['applicationSource']['treeDigest']==scope['source']['treeDigest'],'SOURCE_CONSUMPTION_BINDING')
    if cases:
        a=parse(attestation_raw,'execution-attestation-v2');p=authenticate(a,context,{'EXECUTOR','COLLECTOR'})
        require(p['manifestDigest']==digest(raw) and p['release']==m['release'] and p['applicationSource']==m['applicationSource'] and p['evaluator']==m['evaluator'] and p['auditSessionId']==m['auditSessionId'],'ATTESTATION_SUBJECT')
        require(len(m['executions'])==1 and p['execution']==m['executions'][0] and p['registrationRef']==context.value('registration_ref'),'ATTESTATION_EXECUTION')
        require(p['termination']=={'kind':'NORMAL_EXIT','exitCode':0} and p['descendantCleanup']=='COMPLETE' and p['resourceLimitEvents']==[],'EXECUTION_FAILED_OR_UNCLEAN')
        require(p['monotonicDurationNanoseconds']<=30_000_000_000,'EXECUTION_DURATION_LIMIT')
        context.freshness(p['execution']['startedAt'],p['expiresAt'])
        require(time(p['execution']['finishedAt'])<=context.now,'FUTURE_EXECUTION')
        observations=[parse_canonical(r) for r in context.observations]
        require(len(observations)==1 and observations[0]==p,'INDEPENDENT_OBSERVATION_MISMATCH')
        require(p['observedInputs']==scope['expectedInputs'],'EXECUTABLE_OR_ENVIRONMENT_SUBSTITUTION')
        expected={(c['application'],c['witnessId'],c['caseId']):c for c in cases.values()}
        actual={}
        for case in p['cases']:
            key=(case['application'],case['witnessId'],case['caseId']);require(key not in actual and key in expected,'UNRELATED_OR_DUPLICATE_OBSERVED_CASE')
            require(case['outcome']=='PASSED' and case['assertionArtifactPaths']==expected[key]['assertionArtifactPaths'],'OBSERVED_ASSERTION_FAILURE')
            actual[key]=case
        require(set(actual)==set(expected),'MISSING_OBSERVED_CASE')
        require(p['nonce']==observations[0]['nonce'],'REPLAYED_NONCE')
        junit_cases(artifacts,cases)
    else:
        require(attestation_raw==b'' and not m['executions'],'UNRELATED_ATTESTATION')
    verify_reviews(reviews,m,digest(raw),artifacts,context)
    return LabQualification(raw,attestation_raw,reviews,context,str(source_root),str(artifact_root))
