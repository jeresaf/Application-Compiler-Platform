"""Exact laboratory witness provenance; no activation or workload execution."""
import base64
import hashlib
import os
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
from engineering.evidence_admission.encoding import canonicalize, parse_canonical, signature_input
from engineering.evidence_admission.signatures import verify_ed25519
from engineering.evidence_admission.registration import source_inventory, source_tree_digest
from .context import LabContext
from .manifest import parse, require, sha, time, unique


def git_read(root,*args):
    # Candidate-local remote/promisor configuration must never execute a transport.
    env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C','GIT_CONFIG_NOSYSTEM':'1',
         'GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null',
         'GIT_NO_REPLACE_OBJECTS':'1','GIT_NO_LAZY_FETCH':'1','GIT_ALLOW_PROTOCOL':'',
         'GIT_OPTIONAL_LOCKS':'0'}
    result=subprocess.run(['/usr/bin/git','--no-pager','-c','core.fsmonitor=false',
                           '-c','core.hooksPath=/dev/null','-C',str(root),*args],
                          env=env,capture_output=True,timeout=30)
    require(result.returncode==0,'SOURCE_GIT_READ_FAILED')
    return result.stdout


def authenticate(record, context, roles):
    require(type(context) is LabContext, 'EXTERNAL_LAB_CONTEXT_REQUIRED')
    context.check_current()
    require(type(record) is dict and set(record) == {'payload','signatures'}, 'SIGNED_RECORD_REQUIRED')
    payload, signatures = record['payload'], record['signatures']
    require(type(signatures) is list and signatures, 'MISSING_SIGNATURE')
    unique(signatures, lambda s: s['signerId'], 'DUPLICATE_SIGNER')
    keys = {k.key_id:k for k in context.keys}
    seen = set()
    for s in signatures:
        require(set(s) == {'signerId','keyId','algorithm','signature'} and s['algorithm']=='Ed25519', 'SIGNATURE_PROFILE')
        key = keys.get(s['keyId'])
        require(key is not None and key.principal_id == s['signerId'], 'UNKNOWN_OR_MISMATCHED_SIGNER')
        require(key.key_id not in context.revoked_keys and key.principal_id not in context.revoked_principals, 'REVOKED_SIGNER')
        require(key.valid_from <= context.now < key.valid_until and key.valid_from <= time(payload['issuedAt']) < key.valid_until, 'KEY_VALIDITY')
        role = key.roles & set(roles)
        require(len(role) == 1 and not (role & seen), 'WRONG_OR_DUPLICATE_ROLE')
        encoded=s['signature']; require(type(encoded) is str and len(encoded)==86, 'SIGNATURE_ENCODING')
        raw=base64.urlsafe_b64decode(encoded+'==')
        require(base64.urlsafe_b64encode(raw).decode().rstrip('=') == encoded, 'SIGNATURE_ENCODING')
        verify_ed25519(key.public_key, raw, signature_input(payload));seen |= role
    require(seen == set(roles), 'SIGNATURE_THRESHOLD')
    context.freshness(payload['issuedAt'],payload['expiresAt'])
    return payload


def verify_source(root, scope, context):
    root=Path(root)
    from .verify import capture
    inventory=context.source_inventory
    entries=parse_canonical(inventory)['files']
    source_identity=root.lstat()
    capture(root,entries,source=True)
    git_identity=(root/'.git').stat()
    require(inventory == context.source_inventory, 'WITNESS_SOURCE_INVENTORY')
    require(source_tree_digest(inventory) == scope['source']['treeDigest'], 'WITNESS_SOURCE_TREE')
    require((root/'.git').is_dir() and not (root/'.git').is_symlink(), 'ORDINARY_GIT_REQUIRED')
    require(Path(git_read(root,'rev-parse','--show-toplevel').decode().strip()).resolve()==root.resolve(), 'WRONG_SOURCE_ROOT')
    require(git_read(root,'rev-parse','HEAD').decode().strip()==scope['source']['commit'], 'WITNESS_SOURCE_COMMIT')
    commit=scope['source']['commit']
    def object_bytes(kind,oid):
        raw=git_read(root,'cat-file',kind,oid)
        require(hashlib.new('sha1' if len(oid)==40 else 'sha256',kind.encode()+b' '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==oid,'GIT_OBJECT_IDENTITY')
        return raw
    raw_commit=object_bytes('commit',commit)
    tree_line=raw_commit.split(b'\n',1)[0]
    require(tree_line.startswith(b'tree '),'GIT_COMMIT_TREE')
    rows=[]
    def tree(oid,prefix='',depth=0):
        require(depth<=64,'GIT_TREE_DEPTH')
        raw=object_bytes('tree',oid);offset=0;width=len(commit)//2
        while offset<len(raw):
            end=raw.index(b'\0',offset);mode,name=raw[offset:end].split(b' ',1)
            child=raw[end+1:end+1+width].hex();offset=end+1+width
            require(len(child)==len(commit) and b'/' not in name and name not in (b'.',b'..'),'GIT_TREE_ENTRY')
            full=prefix+name.decode()
            if mode==b'40000':tree(child,full+'/',depth+1)
            else:
                require(len(rows)<4096,'SOURCE_INVENTORY_LIMIT')
                rows.append(mode+b' blob '+child.encode()+b'\t'+full.encode())
    tree(tree_line[5:].decode())
    actual={r['path']:r for r in parse_canonical(inventory)['files']};tracked=set();blobs={}
    for row in rows:
        if not row:continue
        meta,name=row.split(b'\t');mode,kind,oid=meta.split();name=name.decode()
        require(kind==b'blob' and mode in (b'100644',b'100755') and name in actual, 'UNSUPPORTED_SOURCE_ENTRY')
        blob=object_bytes('blob',oid.decode())
        require(sha(blob)==actual[name]['sha256'], 'SOURCE_NOT_AT_COMMIT')
        require(bool(int(actual[name]['mode'],8)&0o111)==(mode==b'100755'), 'SOURCE_MODE')
        require(name not in tracked,'DUPLICATE_GIT_PATH')
        tracked.add(name);blobs[name]=blob
    require(tracked == set(actual), 'UNTRACKED_SOURCE')
    dep=scope['source']['dependencyPath']
    require(dep in actual and actual[dep]['sha256']==scope['source']['dependencyDigest'], 'DEPENDENCY_SOURCE')
    require(scope['source']['entrypoint'] in actual, 'ENTRYPOINT_SOURCE')
    for c in scope['cases']:
        require(c['sourcePath'] in actual, 'ASSERTION_SOURCE')
        raw=blobs[c['sourcePath']].decode()
        require('void '+c['method']+'(' in raw and 'class '+c['className'].rsplit('.',1)[-1] in raw, 'UNREGISTERED_METHOD')
    capture(root,entries,source=True)
    current=(root/'.git').lstat()
    final_root=root.lstat()
    require((source_identity.st_dev,source_identity.st_ino,source_identity.st_mtime_ns,source_identity.st_ctime_ns)==(final_root.st_dev,final_root.st_ino,final_root.st_mtime_ns,final_root.st_ctime_ns),'SOURCE_DIRECTORY_CHANGED')
    require((root/'.git').is_dir() and not (root/'.git').is_symlink(),'GIT_DIRECTORY_CHANGED')
    require((git_identity.st_dev,git_identity.st_ino)==(current.st_dev,current.st_ino),'GIT_DIRECTORY_CHANGED')
    require(git_read(root,'rev-parse','HEAD').decode().strip()==commit,'SOURCE_HEAD_CHANGED')


def registered_cases(manifest, scope):
    expected={(c['criterion'],c['application'],c['witnessId'],c['caseId']):c for c in scope['cases']}
    require(len(expected)==len(scope['cases']), 'AMBIGUOUS_REGISTERED_CASE')
    submitted={}
    contracts={c['criterion']:c['digest'] for c in scope['predicateContracts']}
    for c in manifest['criteria']:
        require(c['predicateContractDigest']==contracts.get(c['criterion']), 'PREDICATE_CONTRACT')
        for w in c['witnesses']:
            k=(c['criterion'],w['application'],w['witnessId'],w['caseId'])
            require(k not in submitted and k in expected, 'UNREGISTERED_OR_DUPLICATE_CASE')
            require(w['assertionArtifactPaths']==expected[k]['assertionArtifactPaths'], 'ASSERTION_ARTIFACT_BINDING')
            submitted[k]=w
    require(set(submitted)==set(expected), 'INCOMPLETE_REGISTERED_CASES')
    return expected


def junit_cases(files, cases):
    found={}
    for path,raw in files.items():
        if not path.endswith('.xml'):continue
        require(b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper(), 'XML_ENTITY_FORBIDDEN')
        root=ET.fromstring(raw)
        require(all(node.tag in {'testsuites','testsuite','testcase','properties','property','system-out','system-err','failure','error','skipped','flakyFailure','flakyError','rerunFailure','rerunError'} for node in root.iter()),'UNSUPPORTED_JUNIT_ELEMENT')
        for tag in ('failure','error','skipped','flakyFailure','flakyError','rerunFailure','rerunError'):
            require(not list(root.iter(tag)), 'TEST_NOT_GREEN_OR_RETRIED')
        for suite in root.iter('testsuite'):
            for counter in ('failures','errors','skipped'):
                require(counter not in suite.attrib or suite.attrib[counter]=='0','JUNIT_COUNTER_FAILURE')
            require('tests' not in suite.attrib or suite.attrib['tests']==str(len(list(suite.iter('testcase')))),'JUNIT_COUNTER_MISMATCH')
        for case in root.iter('testcase'):
            k=(path,case.attrib.get('classname'),case.attrib.get('name'))
            require(k not in found,'DUPLICATE_JUNIT_CASE');found[k]=True
    expected=set()
    for c in cases.values():
        for p in c['assertionArtifactPaths']:
            if p.endswith('.xml'):expected.add((p,c['className'],c['method']))
    require(found and set(found)==expected, 'JUNIT_CASE_COVERAGE')


def external_junit(files, required, execution_commit, registration):
    # Explicit laboratory helper only. Native validate()/assess() never supply this argument.
    from .verify import LabQualification
    require(type(registration) is LabQualification, 'UNVERIFIED_REGISTRATION_OBJECT')
    registration.reverify()
    require(execution_commit==registration.application_commit, 'WRONG_EXECUTION_COMMIT')
    require(set(required)=={c['method'] for c in registration.cases.values()}, 'UNRELATED_CRITERION_TESTS')
    require(set(files)==set(registration.artifact_hashes), 'CHANGED_QUALIFIED_ARTIFACT')
    require(all(Path(v)==Path(registration.artifact_root)/k for k,v in files.items()), 'UNRELATED_ARTIFACT_ROOT')
    return None
