"""Fixed synthetic qualification only. No candidate argv, code, mount or signing API."""
import ctypes
import errno
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time

from .encoding import canonicalize, parse_canonical
from .host_capabilities import digest, verify_runtime, runtime_identity
from .signatures import require

PYTHON_ROOT = '/tmp/acp-stage1-python3147'
NAMESPACES = ('user', 'mnt', 'pid', 'net', 'ipc', 'uts', 'cgroup')
SYSCALLS = tuple(sorted(('read write close openat newfstatat fstat statx lseek mmap mprotect munmap brk '
    'rt_sigaction rt_sigprocmask rt_sigreturn ioctl pread64 readv writev access faccessat faccessat2 '
    'pipe pipe2 select pselect6 poll ppoll sched_yield mremap madvise dup dup2 dup3 nanosleep clock_nanosleep '
    'getpid getppid gettid exit exit_group wait4 uname fcntl getcwd readlink readlinkat getdents64 '
    'getuid geteuid getgid getegid getgroups getresuid getresgid arch_prctl set_tid_address '
    'set_robust_list rseq futex prlimit64 getrandom clock_gettime gettimeofday sysinfo sigaltstack '
    'execve').split()))
SECCOMP_SPEC = {'schema': 'acp-phase6-lab-seccomp/1', 'architecture': 'x86_64',
                'defaultAction': 'ERRNO:EPERM', 'allow': list(SYSCALLS), 'badArchitectureAction': 'KILL_PROCESS'}
APPARMOR_PROPOSAL = '''abi <abi/4.0>,
include <tunables/global>
profile acp-bwrap-lab /usr/libexec/acp-lab/bwrap flags=(attach_disconnected,mediate_deleted) {
  include <abstractions/base>
  userns,
  capability sys_admin,
  capability sys_chroot,
  capability setuid,
  capability setgid,
  capability setpcap,
  mount,
  umount,
  pivot_root,
  /usr/libexec/acp-lab/bwrap rix,
  /usr/** r,
  /lib/** mr,
  /lib64/** mr,
  /tmp/acp-stage1-python3147/** mrix,
  /proc/** r,
  /proc/sys/user/max_user_namespaces w,
  /dev/null rw,
  /dev/zero rw,
  /dev/urandom r,
  /dev/random r,
  /tmp/acp-bwrap-probe-*/** rw,
  deny network,
  deny /home/** rwklx,
  deny /run/** rwklx,
  deny /sys/** wklx,
}
'''


def profile_for(runtime_digest):
    return {'schema': 'acp-phase6-lab-isolation/1', 'architecture': 'x86_64', 'runtimeDigest': runtime_digest,
            'namespaces': list(NAMESPACES), 'readOnlyMounts': ['/usr', '/lib', '/lib64', PYTHON_ROOT],
            'capabilities': [], 'environment': {'LANG': 'C', 'LC_ALL': 'C', 'PWD': '/', 'LD_LIBRARY_PATH': PYTHON_ROOT+'/lib'},
            'seccompDigest': digest(canonicalize(SECCOMP_SPEC)),
            'apparmorProposalDigest': digest(APPARMOR_PROPOSAL.encode()),
            'limits': {'memoryBytes': 100663296, 'pids': 8, 'cpuQuotaPercent': 20, 'swapBytes': 0, 'wallSeconds': 4}}


def validate_profile(raw, expected_digest, runtime_digest):
    require(type(raw) is bytes and digest(raw) == expected_digest, 'UNKNOWN_PROFILE_IDENTITY')
    require(parse_canonical(raw) == profile_for(runtime_digest), 'UNAPPROVED_ISOLATION_CONFIGURATION')
    return expected_digest


def seccomp_fd():
    """Compile only this closed x86-64 allowlist; caller cannot supply rules."""
    import platform
    require(platform.machine() == 'x86_64', 'UNSUPPORTED_SECCOMP_ARCHITECTURE')
    library = ctypes.CDLL('libseccomp.so.2', use_errno=True)
    library.seccomp_init.argtypes = [ctypes.c_uint32]; library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]; library.seccomp_syscall_resolve_name.restype = ctypes.c_int
    library.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    library.seccomp_export_bpf.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.seccomp_attr_set.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint32]
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    context = library.seccomp_init(0x00050000 | errno.EPERM)
    require(context, 'SECCOMP_UNAVAILABLE')
    fd = os.memfd_create('acp-lab-seccomp', os.MFD_CLOEXEC)
    try:
        require(library.seccomp_attr_set(context, 2, 0x80000000) == 0, 'SECCOMP_BAD_ARCH_ACTION_UNAVAILABLE')
        for name in SYSCALLS:
            number = library.seccomp_syscall_resolve_name(name.encode())
            require(number >= 0 and library.seccomp_rule_add(context, 0x7fff0000, number, 0) == 0, 'SECCOMP_RULE_UNAVAILABLE')
        require(library.seccomp_export_bpf(context, fd) == 0, 'SECCOMP_EXPORT_FAILED')
        os.lseek(fd, 0, os.SEEK_SET)
        return fd
    except BaseException:
        os.close(fd);raise
    finally:
        library.seccomp_release(context)


NAMESPACE_PROBE = r'''
import os
inherited={}
for fd in os.listdir('/proc/self/fd'):
 if int(fd)>2:
  try:inherited[fd]=os.readlink('/proc/self/fd/'+fd)
  except FileNotFoundError:pass
import ctypes,errno,json,socket,sys,gc
def read(path):
 with open(path) as stream:return stream.read()
lib=ctypes.CDLL(None,use_errno=True)
result={'pid':os.getpid(),'namespaces':{n:os.readlink('/proc/self/ns/'+n) for n in ['user','mnt','pid','net','ipc','uts','cgroup']},
 'capabilities':[r.strip() for r in read('/proc/self/status').splitlines() if r.startswith(('CapEff:','NoNewPrivs:','Seccomp:'))],
 'hostCanaryVisible':os.path.exists(sys.argv[1]) or os.path.exists('/proc/1/root'+sys.argv[1]),'hostHomeVisible':os.path.exists('/home'),
 'supervisorControlsVisible':os.path.exists('/run/user'),'processes':[p for p in os.listdir('/proc') if p.isdigit()],
 'routes':read('/proc/net/route'),'environment':dict(os.environ),
}
gc.collect()
result['extraDescriptors']=inherited
result['runtimeDescriptors']={}
for fd in os.listdir('/proc/self/fd'):
 if int(fd)>2:
  try:result['runtimeDescriptors'][fd]=os.readlink('/proc/self/fd/'+fd)
  except FileNotFoundError:pass
result['unshareReturn']=lib.unshare(0x10000000);result['unshareErrno']=ctypes.get_errno()
result['mountReturn']=lib.mount(None,b'/proc',None,0,None);result['mountErrno']=ctypes.get_errno()
result['setnsReturn']=lib.setns(-1,0);result['setnsErrno']=ctypes.get_errno()
result['ptraceReturn']=lib.ptrace(16,-1,0,0);result['ptraceErrno']=ctypes.get_errno()
result['bpfReturn']=lib.syscall(321,0,0,0);result['bpfErrno']=ctypes.get_errno()
result['capsetReturn']=lib.capset(None,None);result['capsetErrno']=ctypes.get_errno()
try:
 s=socket.socket();s.settimeout(.2);s.connect(('198.51.100.1',9));result['networkDenied']=False
except OSError as e:result['networkDenied']=True;result['networkErrno']=e.errno
print(json.dumps(result,sort_keys=True),flush=True)
'''


def namespace_probe(runtime_pin, runtime_pin_digest, profile_raw, profile_digest):
    identity, _ = runtime_identity();runtime_digest = verify_runtime(identity, runtime_pin, runtime_pin_digest)
    validate_profile(profile_raw, profile_digest, runtime_digest)
    host_ns = {name: os.readlink('/proc/self/ns/'+name) for name in NAMESPACES}
    fd = seccomp_fd()
    with tempfile.TemporaryDirectory(prefix='acp-bwrap-probe-') as directory:
        canary = Path(directory)/'protected-canary';canary.write_bytes(b'PUBLIC SYNTHETIC CANARY');canary.chmod(0o600)
        canary_fd = os.open(canary, os.O_RDONLY);os.set_inheritable(canary_fd, True)
        argv = ['/usr/bin/bwrap', '--unshare-user', '--unshare-pid', '--unshare-net', '--unshare-ipc', '--unshare-uts',
                '--unshare-cgroup', '--disable-userns', '--assert-userns-disabled', '--die-with-parent', '--new-session',
                '--cap-drop', 'ALL', '--clearenv', '--setenv', 'LANG', 'C', '--setenv', 'LC_ALL', 'C', '--setenv', 'PWD', '/', '--setenv', 'LD_LIBRARY_PATH', PYTHON_ROOT+'/lib']
        for path in ['/usr', '/lib', '/lib64', PYTHON_ROOT]:argv.extend(['--ro-bind', path, path])
        argv += ['--proc','/proc','--dev','/dev','--seccomp',str(fd),PYTHON_ROOT+'/bin/python3.14','-I','-c',NAMESPACE_PROBE,str(canary)]
        try:
            result = subprocess.run(argv, capture_output=True, text=True, timeout=10, close_fds=True, pass_fds=(fd,),
                                    env={'PATH':'/usr/bin:/bin','LANG':'C'})
        finally:
            os.close(fd);os.close(canary_fd)
        evidence = {'argv':argv,'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
                    'hostNamespaces':host_ns,'seccompProfileDigest':digest(canonicalize(SECCOMP_SPEC))}
        if result.returncode != 0:
            return dict(evidence,status='HOST_CAPABILITY_UNAVAILABLE')
        observed=json.loads(result.stdout)
        checks={'namespaces':all(observed['namespaces'][n]!=host_ns[n] for n in NAMESPACES),
                'filesystem':not observed['hostCanaryVisible'] and not observed['hostHomeVisible'],
                'controls':not observed['supervisorControlsVisible'], 'descriptors':not observed['extraDescriptors'], 'environment':observed['environment']==profile_for(runtime_digest)['environment'],
                'network':observed['networkDenied'] and len(observed['routes'].splitlines())==1,
                'seccomp':all(observed[n+'Return']==-1 and observed[n+'Errno']==errno.EPERM for n in ['unshare','mount','setns','ptrace','bpf','capset']),
                'capabilities':any(row.split()[-1]=='0000000000000000' for row in observed['capabilities'] if row.startswith('CapEff:')) and any(row.split()[-1]=='1' for row in observed['capabilities'] if row.startswith('NoNewPrivs:')),
                'privateProcesses':all(int(pid)<=4 for pid in observed['processes'])}
        return dict(evidence,observed=observed,checks=checks,status='SYNTHETIC_PROBE_PASSED' if all(checks.values()) else 'ISOLATION_ENFORCEMENT_FAILED')


RESOURCE_PROBE = r'''
import errno,json,os,sys,time
mode=sys.argv[1];group=open('/proc/self/cgroup').read().strip().split('::')[1];root='/sys/fs/cgroup'+group
read=lambda n:open(root+'/'+n).read().strip()
print(json.dumps({'pid':os.getpid(),'start':open('/proc/self/stat').read().split()[21],
 'group':group,'cpu':read('cpu.max'),'memory':read('memory.max'),'swap':read('memory.swap.max'),'pids':read('pids.max')}),flush=True)
if mode=='memory':
 blocks=[]
 for _ in range(192):blocks.append(bytearray(1024*1024))
elif mode=='pids':
 children=[];denied=False
 for _ in range(12):
  try:pid=os.fork()
  except OSError as e:denied=e.errno==errno.EAGAIN;break
  if pid==0:time.sleep(20);os._exit(0)
  children.append(pid)
 print(json.dumps({'children':children,'denied':denied,'events':read('pids.events')}),flush=True)
 for pid in children:os.kill(pid,9)
 for pid in children:os.waitpid(pid,0)
elif mode=='cpu':
 before=time.process_time();end=time.monotonic()+2
 while time.monotonic()<end:pass
 print(json.dumps({'cpuSeconds':time.process_time()-before,'stats':read('cpu.stat')}),flush=True)
elif mode=='deadline':
 pid=os.fork()
 if pid==0:time.sleep(20);os._exit(0)
 print(json.dumps({'children':[pid]}),flush=True);time.sleep(20)
'''


def resource_probe(mode, runtime_pin=None, runtime_pin_digest=None):
    """Only four fixed bounded synthetic programs; no arbitrary execution input."""
    require(mode in ('memory','pids','cpu','deadline'), 'UNAPPROVED_SYNTHETIC_PROBE')
    identity, _ = runtime_identity()
    verify_runtime(identity, runtime_pin, runtime_pin_digest)
    unit='acp-lab-probe-'+secrets.token_hex(8)
    argv=['/usr/bin/systemd-run','--user','--unit='+unit,'--service-type=exec',
          '--property=MemoryMax=96M','--property=MemorySwapMax=0','--property=TasksMax=8',
          '--property=CPUQuota=20%','--property=RuntimeMaxSec=4','--property=KillMode=control-group',
          '--property=TimeoutStopSec=1','--property=SendSIGKILL=yes','--property=OOMPolicy=kill',
          '--pipe','--wait',PYTHON_ROOT+'/bin/python3.14','-I','-c',RESOURCE_PROBE,mode]
    env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C','LD_LIBRARY_PATH':PYTHON_ROOT+'/lib',
         'XDG_RUNTIME_DIR':'/run/user/'+str(os.getuid()),
         'DBUS_SESSION_BUS_ADDRESS':'unix:path=/run/user/'+str(os.getuid())+'/bus'}
    started=time.monotonic();result=None
    try:
        result=subprocess.run(argv,env=env,capture_output=True,text=True,timeout=8,close_fds=True)
        rows=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        show=subprocess.run(['/usr/bin/systemctl','--user','show',unit,'-p','Result','-p','ExecMainStatus','-p','MemoryPeak','-p','CPUUsageNSec'],env=env,capture_output=True,text=True,timeout=5)
    except subprocess.TimeoutExpired:
        return {'mode':mode,'status':'HOST_CAPABILITY_UNAVAILABLE','reason':'SUPERVISOR_TIMEOUT'}
    finally:
        subprocess.run(['/usr/bin/systemctl','--user','stop',unit],env=env,capture_output=True,timeout=5)
        subprocess.run(['/usr/bin/systemctl','--user','reset-failed',unit],env=env,capture_output=True,timeout=5)
    elapsed=time.monotonic()-started
    evidence={'mode':mode,'argv':argv,'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
              'unitProperties':show.stdout,'elapsedSeconds':elapsed}
    if not rows:return dict(evidence,status='HOST_CAPABILITY_UNAVAILABLE')
    limits=rows[0]
    bounded=limits['memory']=='100663296' and limits['swap']=='0' and limits['pids']=='8' and limits['cpu'].split()[0]=='20000'
    if mode=='memory':enforced=result.returncode!=0 and 'oom-kill' in show.stdout
    elif mode=='pids':enforced=len(rows)>1 and rows[1]['denied'] and int(dict(line.split() for line in rows[1]['events'].splitlines())['max'])>0
    elif mode=='cpu':enforced=len(rows)>1 and 0.1<rows[1]['cpuSeconds']<0.9 and int(dict(line.split() for line in rows[1]['stats'].splitlines())['nr_throttled'])>0
    else:enforced=result.returncode!=0 and elapsed<8 and 'timeout' in show.stdout
    group=Path('/sys/fs/cgroup')/limits['group'].lstrip('/')
    known_pids=[limits['pid']]+[pid for row in rows[1:] for pid in row.get('children',[])]
    survivors=[pid for pid in known_pids if Path('/proc/'+str(pid)).exists()]
    cleanup=(not group.exists() or 'populated 0' in (group/'cgroup.events').read_text()) and not survivors
    evidence['survivingPids']=survivors
    return dict(evidence,limitsObserved=limits,checks={'limits':bounded,'enforcement':enforced,'cleanup':cleanup},
                status='SYNTHETIC_PROBE_PASSED' if bounded and enforced and cleanup else 'ISOLATION_ENFORCEMENT_FAILED')


def qualification_result(runtime_verified, apparmor_verified, namespace_evidence, resource_evidence):
    """No signature, admission or release result. Missing evidence always blocks."""
    require(type(runtime_verified) is bool and type(apparmor_verified) is bool, 'INVALID_QUALIFICATION_INPUT')
    required={'namespaces','filesystem','controls','descriptors','environment','network','seccomp','capabilities','privateProcesses'}
    checks=namespace_evidence.get('checks',{})
    passed=runtime_verified and apparmor_verified and namespace_evidence.get('status')=='SYNTHETIC_PROBE_PASSED'
    passed=passed and set(checks)==required and all(value is True for value in checks.values())
    passed=passed and set(resource_evidence)=={'memory','pids','cpu','deadline'} and all(
        row.get('mode')==mode and row.get('status')=='SYNTHETIC_PROBE_PASSED' and
        row.get('checks')=={'limits':True,'enforcement':True,'cleanup':True} and row.get('survivingPids')==[]
        for mode,row in resource_evidence.items())
    return {'status':'ISOLATION_QUALIFICATION_BLOCKED', 'laboratory':True, 'observationsComplete':bool(passed),
            'reason':'RUNTIME_SECURITY_ADVISORY_AND_PLATFORM_APPARMOR_REVIEW_REQUIRED', 'operationalSecurityEstablished':False}
