"""One request per disposable isolated target worker; stdout is protocol only."""
import ctypes
import errno
import json
from pathlib import Path
import resource
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parents[3] / 'tooling'))
from execution_model import validate_execution  # Closed neutral validator, preloaded before seccomp.
from deterministic_model import validate_deterministic
import deterministic_reference, deterministic_failures, deterministic_invocation
import phase1_semantics, security_semantics, execution_semantics, ui_semantics, quality_semantics, execution_canonical
from importlib.resources import files
from datetime import datetime
datetime.strptime('09:00:00', '%H:%M:%S')
for _zone in files('tzdata').joinpath('zones').read_text().splitlines():
    execution_semantics.zone(_zone)  # Only the pinned package; no host tzdb or post-confinement I/O.
''.encode('utf-16-be')  # JCS key ordering codec must be loaded before open() is denied.
from model import CapabilityError, encoded, lower, manifest, negotiate
from generation import plan, validate_plan
from target_worker import bundle_digest
BUNDLE_DIGEST = "sha256:" + bundle_digest()
from target_release import verify_release
# Verified after PROFILE loading below; failure is a structured fail-closed gate.
from execution_codegen import ExecutionGenerator  # Preload trusted generator before confinement.
import relations, delivery_jobs, privacy_lifecycle

ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT / "profile.json").read_text())
TEMPLATES = {p.relative_to(ROOT / "templates").as_posix(): p.read_text(encoding="utf-8")
             for p in sorted((ROOT / "templates").rglob("*")) if p.is_file()}


try:
    verify_release(PROFILE,BUNDLE_DIGEST)
    RELEASE_ERROR=None
except (ValueError,FileNotFoundError):
    RELEASE_ERROR="GENERATOR_VERSION_REUSE"


def sandbox():
    """Linux adapter confinement installed after trusted module/profile loading."""
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    library = ctypes.CDLL("libseccomp.so.2", use_errno=True)
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    context = library.seccomp_init(0x7fff0000)
    if not context:
        raise RuntimeError("SANDBOX")
    denied = "open openat openat2 creat socket socketpair connect bind listen accept accept4 getrandom time gettimeofday clock_gettime execve execveat fork vfork clone clone3 uname getuid geteuid getgid getegid readlink readlinkat statx newfstatat mount ptrace io_uring_setup".split()
    for name in denied:
        number = library.seccomp_syscall_resolve_name(name.encode())
        if number >= 0 and library.seccomp_rule_add(context, 0x50000 | errno.EPERM, number, 0):
            raise RuntimeError("SANDBOX")
    if library.seccomp_load(context):
        raise RuntimeError("SANDBOX")
    library.seccomp_release(context)


def handle(request):
    if RELEASE_ERROR: raise CapabilityError(RELEASE_ERROR)
    if request.get("protocol") != PROFILE["protocol"] or set(request) != {"protocol", "operation", "payload"}:
        raise CapabilityError("PROTOCOL")
    operation, payload = request["operation"], request["payload"]
    expected = {"handshake": set(), "manifest": set(), "negotiate": {"nodes", "required", "decisions"},
                "lower": {"nodes", "required", "decisions"}, "plan": {"model", "inventory"}, "validate-plan": {"artifacts"}}
    keys = set(payload) if type(payload) is dict else set()
    if operation in {'negotiate', 'lower'}:
        keys -= {'canonicalVersion'}
    if operation=='plan':
        keys -= {'build'}
    if operation not in expected or type(payload) is not dict or keys != expected[operation]:
        raise CapabilityError("PAYLOAD")
    if operation == "handshake":
        return {"protocol": PROFILE["protocol"], "profile": PROFILE["profile"]}
    if operation == "manifest":
        return manifest(PROFILE)
    if operation == "negotiate":
        validate_semantics(payload)
        return negotiate(payload["nodes"], payload["required"], payload["decisions"], PROFILE, payload.get('canonicalVersion', '0.1.0'))
    if operation == "lower":
        validate_semantics(payload)
        version = payload.get('canonicalVersion', '0.1.0')
        negotiate(payload["nodes"], payload["required"], payload["decisions"], PROFILE, version)
        return lower(payload["nodes"], PROFILE, version)
    if operation == "plan":
        model = payload["model"]
        if model.get('version')!=PROFILE.get('targetIRVersion','0.1.0') or model.get('profile')!=PROFILE['profile'] or model.get('generator')!=PROFILE['generator']:
            raise CapabilityError('TARGET_IR_VERSION')
        # A supplied Target IR cannot bypass lowering constraints.
        version = model.get('canonicalVersion', '0.1.0')
        validate_semantics({'canonicalVersion': version, 'nodes': model['nodes']})
        negotiate(model["nodes"], model.get('requiredCapabilities', []), PROFILE["decisions"], PROFILE, version)
        if model != lower(model["nodes"], PROFILE, version):
            raise CapabilityError("TARGET_IR")
        inventory = payload["inventory"]
        paths = set()
        for item in inventory:
            if set(item) != {"path", "digest", "owner"} or item["path"] in paths or item["owner"] not in manifest(PROFILE)["ownership"]:
                raise CapabilityError("INVENTORY")
            validate_plan([{"path": item["path"], "owner": item["owner"], "origins": ["inventory"], "verification": ["inventory"], "text": ""}])
            paths.add(item["path"])
        build = payload.get("build", {})
        if build and build.get("bundleDigest") != BUNDLE_DIGEST: raise CapabilityError("BUILD_IDENTITY")
        artifacts = plan(model, TEMPLATES, PROFILE, inventory, build={**build,"bundleDigest":BUNDLE_DIGEST})
        validate_plan(artifacts)
        return artifacts
    if operation == "validate-plan":
        return validate_plan(payload["artifacts"])
    raise CapabilityError("OPERATION")


def validate_semantics(payload):
    if payload.get('canonicalVersion') not in {'0.2.0', '0.3.0'}:
        return
    nodes = payload['nodes']
    source = {'modelVersion': '0.4.0' if payload['canonicalVersion']=='0.3.0' else '0.3.0', 'applicationId': 'worker-validation', 'snapshotId': 'WORKER-STRUCTURAL-CHECK',
              'nodes': nodes, 'issues': [], 'approvals': [
                  {'subject': {'id': n['id'], 'revision': n['revision']},
                   'reviewer': 'structural-check-only', 'evidence': 'host-approval-checked-separately'} for n in nodes]}
    validator = validate_deterministic if payload['canonicalVersion']=='0.3.0' else validate_execution
    if validator(source, 'compile'):
        raise CapabilityError('SEMANTIC_VALIDATION')


def main():
    try:
        sandbox()
    except Exception:
        sys.stdout.buffer.write(b'{"ok":false,"error":"SANDBOX_SETUP"}\n')
        return
    raw = sys.stdin.buffer.read(4000001)
    try:
        if len(raw) > 4000000:
            raise CapabilityError("RESOURCE_INPUT")
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise CapabilityError("DUPLICATE_KEY")
                result[key] = value
            return result
        request = json.loads(raw, object_pairs_hook=unique_pairs,
                             parse_constant=lambda value: (_ for _ in ()).throw(CapabilityError("NONFINITE_NUMBER")))
        result = {"ok": True, "result": handle(request)}
    except (CapabilityError, ValueError, KeyError, TypeError) as error:
        result = {"ok": False, "error": str(error) if isinstance(error, CapabilityError) else "INVALID_REQUEST"}
    data = encoded(result).encode()
    if len(data) > 16000000:
        data = b'{"ok":false,"error":"RESOURCE_OUTPUT"}\n'
    sys.stdout.buffer.write(data)


if __name__ == "__main__":
    main()
