"""Future task-owned cluster launcher. No execution CLI; planning is nonexecuting.

The host-only authorization callback is a required interlock, not a human proof
format or operational authority. A separately authorized CI host must supply it.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

NAMES = ('initdb','postgres','pg_ctl','psql')
SCOPE = 'NEW_DISPOSABLE_POSTGRESQL_18_6_FOUR_SYNTHETIC_MIGRATION_TESTS'
IDENTITY_SQL = "SELECT json_build_array(current_setting('data_directory'),current_setting('listen_addresses'),current_setting('unix_socket_directories'),inet_server_addr() IS NULL,current_setting('server_version_num'),current_database(),current_user);"


def socket_path_fits(root,port):
    # Linux sockaddr_un.sun_path has 108 bytes including the terminator.
    return len(str(Path(root)/'pgsocket'/('.s.PGSQL.'+str(port))).encode('utf-8'))<108


def validate_policy(policy):
    root=Path(policy['root'])
    if (not root.is_absolute() or root.exists() or root.is_symlink() or any(p.is_symlink() for p in root.parents)
        or not re.fullmatch(r'acp-phase6-wave2-[A-Za-z0-9-]+',root.name)
        or any(c.isspace() or c in "'\\\"" for c in str(root))):
        raise ValueError('NEW_PRIVATE_CLUSTER_REQUIRED')
    if set(policy) != {'root','port','role','database','binaries','binaryHashes','source','candidateDigest','python','pythonSHA256'}:
        raise ValueError('CLOSED_CLUSTER_POLICY_REQUIRED')
    if type(policy['port']) is not int or not 1024<=policy['port']<=65535:
        raise ValueError('EXPLICIT_PORT_REQUIRED')
    for key in ('role','database'):
        if not re.fullmatch(r'acp_wave2_[a-z0-9_]+',policy[key]):raise ValueError('NONDEFAULT_IDENTITY_REQUIRED')
    if not re.fullmatch(r'[0-9a-f]{64}',policy['candidateDigest']):raise ValueError('CANDIDATE_DIGEST_REQUIRED')
    if set(policy['binaries']) != set(NAMES) or set(policy['binaryHashes']) != set(NAMES):
        raise ValueError('EXACT_BINARIES_REQUIRED')
    for name in NAMES:
        path=Path(policy['binaries'][name])
        if (not path.is_absolute() or path.name != name or not path.is_file() or path.is_symlink()
            or any(p.is_symlink() for p in path.parents) or path.stat().st_mode&0o022
            or not os.access(path,os.X_OK) or hashlib.sha256(path.read_bytes()).hexdigest()!=policy['binaryHashes'][name]):
            raise ValueError('BINARY_IDENTITY_MISMATCH')
    python=Path(policy['python'])
    if (not python.is_absolute() or not python.resolve().is_file() or not os.access(python,os.X_OK)
        or python.resolve().stat().st_mode&0o022 or hashlib.sha256(python.resolve().read_bytes()).hexdigest()!=policy['pythonSHA256']):
        raise ValueError('PYTHON_BINARY_IDENTITY_MISMATCH')
    return root


def validate_version(observed):
    if not re.fullmatch(r'.*\(PostgreSQL\) 18\.6(?: \([^\n]*\))?',observed.strip()):
        raise ValueError('POSTGRESQL_VERSION_REQUIRED')


def verify_server(root,identity,observed,*,pid_lines=None):
    root=Path(root);data=root/'pgdata';socket=root/'pgsocket'
    for directory in (root,data,socket):
        if directory.is_symlink() or directory.stat().st_uid != os.getuid() or directory.stat().st_mode&0o077:
            raise ValueError('PRIVATE_CLUSTER_OWNERSHIP_REQUIRED')
    lines=pid_lines if pid_lines is not None else (data/'postmaster.pid').read_text().splitlines()
    if (len(lines)<6 or lines[0]!=str(identity['pid']) or lines[1]!=str(data)
        or lines[3]!=str(identity['port']) or lines[4]!=str(socket) or lines[5]!=''):
        raise ValueError('POSTMASTER_IDENTITY_MISMATCH')
    expected=[str(data),'',str(socket),True,'180006',identity['database'],identity['role']]
    if observed!=expected:raise ValueError('SERVER_IDENTITY_MISMATCH')


def executable_identity(path, expected_hash):
    """Capture a launcher-approved executable, never PATH resolution."""
    import stat
    path=Path(path)
    if (not path.is_absolute() or path.is_symlink() or path.resolve(strict=True)!=path
        or any(p.is_symlink() for p in path.parents)):
        raise ValueError('EXECUTABLE_PATH_BINDING')
    metadata=path.stat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid not in {0,os.getuid()}
        or metadata.st_mode & 0o7022 or not os.access(path,os.X_OK)
        or not re.fullmatch(r'[0-9a-f]{64}',expected_hash)
        or hashlib.sha256(path.read_bytes()).hexdigest()!=expected_hash):
        raise ValueError('EXECUTABLE_IDENTITY_MISMATCH')
    return {'path':str(path),'sha256':expected_hash,'uid':metadata.st_uid,'mode':stat.S_IMODE(metadata.st_mode)}


def verify_executable(entry):
    if type(entry) is not dict or set(entry)!={'path','sha256','uid','mode'}:
        raise ValueError('EXECUTABLE_IDENTITY_MISMATCH')
    if executable_identity(entry['path'],entry['sha256'])!=entry:
        raise ValueError('EXECUTABLE_IDENTITY_MISMATCH')
    return entry['path']


def build_test_context(policy, identity, token, policy_digest):
    python=Path(policy['python']).resolve(strict=True)
    return {'version':'acp-owned-postgresql/2',**identity,'postmasterStartToken':token,
        'policyDigest':policy_digest,'candidateDigest':policy['candidateDigest'],
        'executables':{
            'psql':executable_identity(policy['binaries']['psql'],policy['binaryHashes']['psql']),
            'postgres':executable_identity(policy['binaries']['postgres'],policy['binaryHashes']['postgres']),
            'python':executable_identity(python,policy['pythonSHA256'])}}


def write_test_context(root, context):
    # Exclusive creation; never overwrite/reuse an earlier owned identity.
    content=(json.dumps(context,sort_keys=True,separators=(',',':'))+'\n').encode()
    descriptor=os.open(Path(root)/'owned-postgresql.json',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'wb') as stream:
        stream.write(content);stream.flush();os.fsync(stream.fileno())
    return {'ACP_QUALIFICATION_CONTEXT_SHA256':hashlib.sha256(content).hexdigest(),
            'ACP_QUALIFICATION_PSQL':context['executables']['psql']['path'],
            'ACP_QUALIFICATION_PSQL_SHA256':context['executables']['psql']['sha256']}


def test_client_context(root, environment):
    """Verify launcher handoff before the first connection and every SQL call.

    Integrity against accidental/stale/substituted inputs, not protection from
    a privileged same-UID observer replacing code, environment or files.
    """
    import stat
    root=Path(root)
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):raise ValueError('OWNED_CONTEXT_PATH')
    metadata=root.stat()
    if metadata.st_uid!=os.getuid() or stat.S_IMODE(metadata.st_mode)!=0o700:raise ValueError('OWNED_CONTEXT_OWNER')
    path=root/'owned-postgresql.json'
    if path.is_symlink():raise ValueError('OWNED_CONTEXT_PATH')
    metadata=path.stat()
    if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=os.getuid()
        or stat.S_IMODE(metadata.st_mode)!=0o600 or metadata.st_nlink!=1):raise ValueError('OWNED_CONTEXT_OWNER')
    content=path.read_bytes()
    if hashlib.sha256(content).hexdigest()!=environment.get('ACP_QUALIFICATION_CONTEXT_SHA256'):
        raise ValueError('OWNED_CONTEXT_DIGEST')
    context=json.loads(content)
    if (set(context)!={'version','pid','port','database','role','postmasterStartToken','policyDigest','candidateDigest','executables'}
        or context['version']!='acp-owned-postgresql/2' or set(context['executables'])!={'psql','postgres','python'}
        or not re.fullmatch(r'[0-9]+',context['postmasterStartToken'])
        or any(not re.fullmatch(r'[0-9a-f]{64}',context[k]) for k in ('policyDigest','candidateDigest'))):
        raise ValueError('OWNED_CONTEXT_SCHEMA')
    entry=context['executables']['psql']
    if (environment.get('ACP_QUALIFICATION_PSQL')!=entry['path']
        or environment.get('ACP_QUALIFICATION_PSQL_SHA256')!=entry['sha256']):raise ValueError('PSQL_LAUNCHER_BINDING')
    for executable in context['executables'].values():verify_executable(executable)
    import sys
    if (Path('/proc/self/exe').resolve(strict=True)!=Path(context['executables']['python']['path'])
        or Path(sys.executable).resolve(strict=True)!=Path(context['executables']['python']['path'])):
        raise ValueError('INTERPRETER_IDENTITY_MISMATCH')
    if process_identity(context['pid'],context['executables']['postgres']['path'],root/'pgdata')!=context['postmasterStartToken']:
        raise ValueError('POSTMASTER_START_TOKEN_MISMATCH')
    return context


def process_identity(pid,postgres,data):
    proc=Path('/proc')/str(pid)
    if proc.stat().st_uid!=os.getuid():raise ValueError('POSTMASTER_OWNER')
    arguments=(proc/'cmdline').read_bytes().split(b'\0')
    if arguments[:3] != [str(postgres).encode(),b'-D',str(data).encode()]:raise ValueError('POSTMASTER_COMMAND')
    # Field 22, parsed after the parenthesized comm, binds PID reuse.
    return (proc/'stat').read_text().rsplit(')',1)[1].split()[19]


def physical_plan(root):
    root=Path(root)
    return {'status':'PLANNED_NOT_EXECUTED' if socket_path_fits(root,55439) else 'BLOCKED_SOCKET_PATH_TOO_LONG','execution':'DISABLED_PENDING_SEPARATE_AUTHORIZATION',
        'scope':SCOPE,'root':str(root),'binaryVersions':{name:'PostgreSQL 18.6' for name in NAMES},
        'binaryPaths':'EXACT_PREINSTALLED_ABSOLUTE_PATHS_AND_SHA256_REQUIRED; NO_PATH_FALLBACK',
        'python':'CPython 3.14.7 required on future CI host','port':55439,'role':'acp_wave2_qualification_role','database':'acp_wave2_qualification_db',
        'actions':[
            {'action':'verify new root/candidate/policy/binary SHA256; require scoped host authorization callback','commands':[[f'<verified-{name}>','--version'] for name in NAMES]},
            {'action':'create new owner-only root, socket and log directories; reject all collisions'},
            {'argv':['<verified-initdb>','-D',str(root/'pgdata'),'-U','acp_wave2_qualification_role','--auth-local=trust','--auth-host=reject','--encoding=UTF8','--no-locale']},
            {'action':'write private postgresql.auto.conf','settings':{'listen_addresses':'','unix_socket_directories':str(root/'pgsocket'),'unix_socket_permissions':'0700','port':55439,'fsync':'on','synchronous_commit':'on','full_page_writes':'on'}},
            {'argv':['<verified-pg_ctl>','-D',str(root/'pgdata'),'-p','<verified-postgres>','-l',str(root/'pglogs/server.log'),'-w','-t','30','start']},
            {'action':'verify recorded postmaster PID, /proc UID/command/start token, private paths and exact server identity before SQL','identitySQL':IDENTITY_SQL},
            {'action':'explicit private-socket connection to newly owned bootstrap postgres DB; create dedicated test database only after exact identity verification'},
            {'action':'write exact owned-postgresql.json; reverify dedicated DB identity before selecting four tests'},
            {'argv':['<pinned-python>','-B','-m','unittest','test_phase6_physical_capture.PhysicalCapturedTests','-v'],'environment':{'ACP_WAVE2_ROOT':str(root),'ACP_PHYSICAL_EVIDENCE_LOG':str(root/'pglogs/sql-observations.jsonl')},'cwd':'<bound-candidate>/tooling/tests','timeoutSeconds':600},
            {'action':'reverify same PID/start token/data directory before stop; if uncertain refuse teardown and report BLOCKED_UNSAFE_TEARDOWN'},
            {'argv':['<verified-pg_ctl>','-D',str(root/'pgdata'),'-w','-t','30','-m','fast','stop'],'preserve':['pgdata','pglogs','SQL output/catalog/row digests']}],
        'noServices':True,'noTCP':True,'noInheritedDBCredentials':True,'noInstall':True,
        'limits':['Not authenticated deployed history','Synthetic backfills are not independent approvals','Generated application integration remains independent NOT_RUN','No operational confinement or release qualification claimed']}


def execute_future(policy, *, authorize=None, process=subprocess.run):
    """Not invoked by current CLI. Only a newly authorized trusted host calls this.

    All tests of this boundary are offline. No callback/proof is issued here.
    """
    policy_digest=hashlib.sha256(json.dumps(policy,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if authorize is None or authorize(SCOPE,policy_digest) is not True:
        raise PermissionError('SEPARATE_EXECUTION_AUTHORIZATION_REQUIRED')
    root=validate_policy(policy)
    if not socket_path_fits(root,policy['port']):raise ValueError('PRIVATE_SOCKET_PATH_TOO_LONG')
    from phase6_qualification import source_digest,scrub_environment
    if source_digest(policy['source'])!=policy['candidateDigest']:raise ValueError('CANDIDATE_IDENTITY_MISMATCH')
    # Pinned runtime and exact binary versions are prerequisites, not installed.
    env=scrub_environment({},root/'tmp')
    env.update(PATH='/usr/bin:/bin',LANG='C.UTF-8',PGPASSFILE='/dev/null',PGSERVICEFILE='/dev/null')
    def call(argv,sql=None,timeout=30,check=True):
        return process(argv,input=sql,text=True,capture_output=True,env=env,timeout=timeout,check=check)
    version=call([policy['python'],'-B','-I','-c','import platform;print(platform.python_implementation(),platform.python_version())'])
    if version.stdout.strip()!='CPython 3.14.7':raise ValueError('PINNED_RUNTIME_REQUIRED')
    for name in NAMES:
        observed=call([policy['binaries'][name],'--version']).stdout.strip()
        validate_version(observed)
    root.mkdir(mode=0o700)
    for directory in ('pgsocket','pglogs','tmp'):(root/directory).mkdir(mode=0o700)
    data=root/'pgdata';identity=None;token=None;start_attempted=False;report={'overall':'NOT_QUALIFIED','physical':'NOT_RUN','policyDigest':policy_digest}
    def client(database,sql):
        approved=executable_identity(policy['binaries']['psql'],policy['binaryHashes']['psql'])
        return call([verify_executable(approved),'-X','-A','-t','-v','ON_ERROR_STOP=1','-h',str(root/'pgsocket'),'-p',str(policy['port']),'-U',policy['role'],'-d',database],sql)
    try:
        call([policy['binaries']['initdb'],'-D',str(data),'-U',policy['role'],'--auth-local=trust','--auth-host=reject','--encoding=UTF8','--no-locale'])
        (data/'postgresql.auto.conf').write_text("listen_addresses=''\nunix_socket_directories='"+str(root/'pgsocket')+"'\nunix_socket_permissions=0700\nport="+str(policy['port'])+"\nfsync=on\nsynchronous_commit=on\nfull_page_writes=on\n")
        (data/'postgresql.auto.conf').chmod(0o600)
        start_attempted=True
        call([policy['binaries']['pg_ctl'],'-D',str(data),'-p',policy['binaries']['postgres'],'-l',str(root/'pglogs/server.log'),'-w','-t','30','start'],timeout=45)
        pid=int((data/'postmaster.pid').read_text().splitlines()[0])
        identity={'pid':pid,'port':policy['port'],'database':'postgres','role':policy['role']}
        token=process_identity(pid,policy['binaries']['postgres'],data)
        verify_server(root,identity,json.loads(client('postgres',IDENTITY_SQL).stdout))
        client('postgres',f"CREATE DATABASE {policy['database']} OWNER {policy['role']};")
        identity['database']=policy['database']
        verify_server(root,identity,json.loads(client(identity['database'],IDENTITY_SQL).stdout))
        context=build_test_context(policy,identity,token,policy_digest)
        env.update(write_test_context(root,context))
        env.update(ACP_WAVE2_ROOT=str(root),ACP_PHYSICAL_EVIDENCE_LOG=str(root/'pglogs/sql-observations.jsonl'))
        argv=[policy['python'],'-B','-m','unittest','test_phase6_physical_capture.PhysicalCapturedTests','-v']
        result=process(argv,cwd=Path(policy['source'])/'tooling/tests',env=env,text=True,capture_output=True,timeout=600)
        (root/'pglogs/tests.log').write_text(result.stdout+result.stderr)
        text=result.stdout+result.stderr
        passed=result.returncode==0 and re.search(r'^Ran 4 tests in ',text,re.M) and re.search(r'^OK$',text,re.M) and 'skipped=' not in text
        report.update(physical='PASS' if passed else 'FAIL',testCommand=argv,exitCode=result.returncode,identity=identity)
    except Exception as error:
        report.update(physical='FAIL',errorType=type(error).__name__,error=str(error),
            stdout=getattr(error,'stdout',None),stderr=getattr(error,'stderr',None))
        raise
    finally:
        if start_attempted:
            try:
                if identity is None or process_identity(identity['pid'],policy['binaries']['postgres'],data)!=token:raise ValueError('POSTMASTER_IDENTITY_CHANGED')
                verify_server(root,identity,json.loads(client(identity['database'],IDENTITY_SQL).stdout))
                call([policy['binaries']['pg_ctl'],'-D',str(data),'-w','-t','30','-m','fast','stop'],timeout=45)
                if Path('/proc',str(identity['pid'])).exists():raise ValueError('POSTMASTER_NOT_STOPPED')
            except Exception as error:
                report.update(physical='BLOCKED_UNSAFE_TEARDOWN',cleanupError=type(error).__name__)
                (root/'pglogs/launcher-result.json').write_text(json.dumps(report,indent=2))
                raise RuntimeError('BLOCKED_UNSAFE_TEARDOWN; preserve task-owned cluster for review') from error
        if root.exists():
            observations=root/'pglogs/sql-observations.jsonl'
            report['observationSHA256']=hashlib.sha256(observations.read_bytes()).hexdigest() if observations.exists() else None
            (root/'pglogs/launcher-result.json').write_text(json.dumps(report,indent=2))
    return report
