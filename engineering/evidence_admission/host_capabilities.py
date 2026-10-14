"""Read-only laboratory host/runtime observations; no enrollment or qualification PASS."""
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import subprocess

from .encoding import canonicalize, parse_canonical
from .signatures import require

BWRAP = '/usr/bin/bwrap'
FEATURES = ('--unshare-user', '--unshare-pid', '--unshare-net', '--unshare-ipc', '--unshare-uts',
            '--unshare-cgroup', '--disable-userns', '--assert-userns-disabled', '--seccomp',
            '--die-with-parent', '--new-session', '--cap-drop', '--clearenv', '--ro-bind')


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


COMMANDS = {
    'version': (BWRAP, '--version'), 'features': (BWRAP, '--help'),
    'libraries': ('/usr/bin/ldd', BWRAP),
    'package': ('/usr/bin/dpkg-query', '-W', '-f=${Package} ${Version} ${Architecture}\n', 'bubblewrap'),
    'repository': ('/usr/bin/apt-cache', 'policy', 'bubblewrap'),
    'userManager': ('/usr/bin/systemctl', '--user', 'show', '-p', 'ControlGroup'),
    'apparmorStatus': ('/usr/sbin/aa-status', '--json'),
}


def _observe_command(name):
    require(type(name) is str and name in COMMANDS, 'UNAPPROVED_HOST_OBSERVATION')
    argv = list(COMMANDS[name])
    try:
        result = subprocess.run(argv, env={'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C'},
                                capture_output=True, text=True, timeout=15, close_fds=True)
        return {'argv': argv, 'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'argv': argv, 'exit': None, 'stdout': '', 'stderr': str(error), 'status': 'HOST_CAPABILITY_UNAVAILABLE'}


def runtime_identity():
    """Inspect only the fixed, root-owned system launcher, never candidate binaries."""
    path = Path(BWRAP); info = path.stat()
    require(info.st_uid == 0 and info.st_mode & 0o022 == 0 and not path.is_symlink(), 'UNTRUSTED_SYSTEM_LAUNCHER')
    commands = {name: _observe_command(name) for name in ('version','features','libraries','package','repository')}
    libraries = []
    for line in commands['libraries']['stdout'].splitlines():
        match = re.search(r'(?:=>\s*)?(/[^\s]+)', line)
        if match:
            library = Path(match[1]).resolve()
            libraries.append({'path': str(library), 'sha256': digest(library.read_bytes())})
    seccomp = Path('/usr/lib/x86_64-linux-gnu/libseccomp.so.2').resolve()
    libraries.append({'path': str(seccomp), 'sha256': digest(seccomp.read_bytes())})
    libraries.sort(key=lambda row: row['path'])
    require(libraries and all(command['exit'] == 0 for command in commands.values()), 'RUNTIME_INSPECTION_UNAVAILABLE')
    python = Path('/tmp/acp-stage1-python3147/bin/python3.14')
    python_library = Path('/tmp/acp-stage1-python3147/lib/libpython3.14.so.1.0')
    libraries.append({'path':str(python_library), 'sha256':digest(python_library.read_bytes())})
    libraries.sort(key=lambda row:row['path'])
    identity = {'qualificationInterpreterDigest':digest(python.read_bytes()), 'schema': 'acp-phase6-lab-runtime/1', 'binaryPath': BWRAP, 'binaryDigest': digest(path.read_bytes()),
                'package': commands['package']['stdout'].strip(), 'architecture': platform.machine(),
                'kernel': platform.release(), 'osRelease': read('/etc/os-release'), 'libraries': libraries,
                'features': [feature for feature in FEATURES if feature in commands['features']['stdout']]}
    return identity, commands


def verify_runtime(observed, pinned_raw, pinned_digest):
    """The immutable pin comes from an independent laboratory harness."""
    require(type(pinned_raw) is bytes and digest(pinned_raw) == pinned_digest, 'UNTRUSTED_RUNTIME_PIN')
    pinned = parse_canonical(pinned_raw)
    require(observed == pinned and set(observed) == {'schema', 'binaryPath', 'binaryDigest', 'package',
            'architecture', 'kernel', 'osRelease', 'libraries', 'features', 'qualificationInterpreterDigest'}, 'RUNTIME_IDENTITY_MISMATCH')
    require(observed['schema'] == 'acp-phase6-lab-runtime/1' and observed['architecture'] == 'x86_64', 'UNSUPPORTED_RUNTIME')
    require(observed['package'] in ('bubblewrap 0.9.0-1ubuntu0.3 amd64', 'bubblewrap 0.11.1-1ubuntu0.3 amd64'), 'UNSUPPORTED_BWRAP_VERSION')
    require(set(observed['features']) == set(FEATURES), 'MISSING_BWRAP_CONTROL')
    # Local 0.11.1 is diagnostic only. This does not make it an Ubuntu 24.04 release.
    return digest(canonicalize(observed))


def detect_host():
    """Visibility is reported separately from enforced/delegated capability."""
    identity, commands = runtime_identity()
    unit = _observe_command('userManager')
    group = unit['stdout'].strip().removeprefix('ControlGroup=') if unit['exit'] == 0 else None
    directory = Path('/sys/fs/cgroup') / group.lstrip('/') if group and group.startswith('/') else None
    return {'schema': 'acp-phase6-lab-host-observation/1', 'capturedAt': datetime.now(timezone.utc).isoformat(), 'runtime': identity, 'commands': commands,
            'userManager': unit, 'cgroup': None if directory is None else str(directory),
            'visibleControllers': read('/sys/fs/cgroup/cgroup.controllers'),
            'delegatedControllers': None if directory is None else read(directory/'cgroup.subtree_control'),
            'delegationEnforced': False,
            'usernsRestriction': read('/proc/sys/kernel/apparmor_restrict_unprivileged_userns'),
            'nestedUsernsRestriction': read('/proc/sys/kernel/apparmor_restrict_unprivileged_unconfined'),
            'apparmorProfileStatus': _observe_command('apparmorStatus'),
            'apparmorEnabled': read('/sys/module/apparmor/parameters/enabled'),
            'currentAppArmor': read('/proc/self/attr/current'),
            'status': 'OBSERVED_NOT_QUALIFIED'}
