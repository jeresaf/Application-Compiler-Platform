"""One request per disposable isolated target worker; stdout is protocol only."""
import ctypes
import errno
import json
from pathlib import Path
import resource
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import CapabilityError, encoded, lower, manifest, negotiate
from generation import plan, validate_plan

ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT / "profile.json").read_text())
TEMPLATES = {p.relative_to(ROOT / "templates").as_posix(): p.read_text(encoding="utf-8")
             for p in sorted((ROOT / "templates").rglob("*")) if p.is_file()}


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
    if request.get("protocol") != PROFILE["protocol"] or set(request) != {"protocol", "operation", "payload"}:
        raise CapabilityError("PROTOCOL")
    operation, payload = request["operation"], request["payload"]
    expected = {"handshake": set(), "manifest": set(), "negotiate": {"nodes", "required", "decisions"},
                "lower": {"nodes", "required", "decisions"}, "plan": {"model", "inventory"}, "validate-plan": {"artifacts"}}
    if operation not in expected or type(payload) is not dict or set(payload) != expected[operation]:
        raise CapabilityError("PAYLOAD")
    if operation == "handshake":
        return {"protocol": PROFILE["protocol"], "profile": PROFILE["profile"]}
    if operation == "manifest":
        return manifest(PROFILE)
    if operation == "negotiate":
        return negotiate(payload["nodes"], payload["required"], payload["decisions"], PROFILE)
    if operation == "lower":
        negotiate(payload["nodes"], payload["required"], payload["decisions"], PROFILE)
        return lower(payload["nodes"], PROFILE)
    if operation == "plan":
        model = payload["model"]
        # A supplied Target IR cannot bypass lowering constraints.
        negotiate(model["nodes"], [], PROFILE["decisions"], PROFILE)
        if model != lower(model["nodes"], PROFILE):
            raise CapabilityError("TARGET_IR")
        inventory = payload["inventory"]
        paths = set()
        for item in inventory:
            if set(item) != {"path", "digest", "owner"} or item["path"] in paths or item["owner"] not in manifest(PROFILE)["ownership"]:
                raise CapabilityError("INVENTORY")
            validate_plan([{"path": item["path"], "owner": item["owner"], "origins": ["inventory"], "verification": ["inventory"], "text": ""}])
            paths.add(item["path"])
        artifacts = plan(model, TEMPLATES, PROFILE, inventory)
        validate_plan(artifacts)
        return artifacts
    if operation == "validate-plan":
        return validate_plan(payload["artifacts"])
    raise CapabilityError("OPERATION")


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
