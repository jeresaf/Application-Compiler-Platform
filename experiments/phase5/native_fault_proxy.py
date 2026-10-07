"""Transport-only corruption AFTER a real native parser response. Test fixture."""
import json,subprocess,sys
from native_frontend import native_command
raw=sys.stdin.buffer.readline(1048577)
p=subprocess.run(native_command(sys.argv[1]),input=raw,capture_output=True,timeout=90)
if p.returncode:raise SystemExit(p.returncode)
mode=sys.argv[2]
if mode=='malformed':sys.stdout.buffer.write(b'{bad\n')
elif mode=='oversize':sys.stdout.buffer.write(b' '*(1048577)+b'\n')
else:
    result=json.loads(p.stdout);result['id']='stale-request';sys.stdout.write(json.dumps(result)+'\n')
sys.stdout.flush()
